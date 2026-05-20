#!/usr/bin/env python3
"""
NAME
===============================
Heatmap Instruments (heatmap_instruments.py)


BY
===============================
Mark Gotham


LICENCE:
===============================
Code = MIT. See [README](https://github.com/MarkGotham/Hauptstimme/tree/main#licence).


ABOUT:
===============================
For every CSV file matching a given suffix in a directory,
read the header row (only) as a series of instruments,
and plot a heatmap showing how many files contain at
least one instance of each canonical instrument type.

See also histogram_instruments.py.

Two layout modes are chosen automatically:
- <= 30 files leads to tall cell heatmap (annotated with counts)
- > 30 files defaults to compact pixel heatmap (no per-cell text)


USAGE:
===============================
    python heatmap.py

Options include
    --directory
    --suffix
    --out heatmap.png
    --mode

"""

import argparse
import csv
import io
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import numpy as np

from amads.instruments import instrument_classification

reg = instrument_classification.InstrumentRegistry()


# -----------------------------------------------------------------------------

# Supporting

def _parse_csv_row(line: str) -> list[str]:
    """Minimal CSV field splitter that respects double-quoted tokens."""
    return next(csv.reader(io.StringIO(line)))


def _parse_token(
        raw: str,
        ignore_list: list[str] = ["Qstamp_Start", "Qstamp_End"],
) -> tuple[str, str] | None:
    """
    Return (canonical_name, family) for a single instrument token
    or None.
    """
    if not raw:
        return None
    ignore_list = [s.strip().lower() for s in ignore_list]

    clean_raw = raw.strip().lower()
    if clean_raw in ignore_list:
        return None

    parsed = reg.parse(raw)
    if parsed:
        return parsed.canonical, parsed.family
    else:
        return None


def parse_header(header_line: str) -> list[tuple[str, str]]:
    """Return list of (canonical, family) tuples from a header row string."""
    tokens = _parse_csv_row(header_line)

    result = []
    for t in tokens:
        if not t.strip():
            continue
        parsed = _parse_token(t)
        if parsed:
            result.append(parsed)
    return result


# -----------------------------------------------------------------------------

# Family colour palette

FAMILY_ORDER = ["Woodwind", "Brass", "Strings", "Percussion", "Voice", "Keyboard", "Unknown"]

# Per-family colour ramps: (light_hex, dark_hex)  used to build a LinearSegmented cmap
FAMILY_CMAPS: dict[str, tuple[str, str]] = {
    "Woodwind":   ("#dde8f5", "#1a3d6e"),
    "Brass":      ("#f5e2d4", "#6b2a09"),
    "Strings":    ("#d4edd9", "#0f4020"),
    "Percussion": ("#ead4f0", "#4a1a5e"),
    "Voice":      ("#f0e4c0", "#5a3d00"),
    "Keyboard":   ("#c8eeee", "#0b3f3f"),
    "Unknown":    ("#e5e4e0", "#383735"),
}

# Single shared sequential ramp for the combined (canonical) mode
_SHARED_LIGHT, _SHARED_DARK = "#e8eaf6", "#1a237e"


def _family_cmap(family: str) -> mcolors.LinearSegmentedColormap:
    light, dark = FAMILY_CMAPS.get(family, ("#f0f0f0", "#222222"))
    return mcolors.LinearSegmentedColormap.from_list(family, ["#ffffff", light, dark])


# -----------------------------------------------------------------------------

# Corpus loading

def load_corpus(directory: Path, suffix: str) -> dict[str, list[tuple[str, str]]]:
    pattern = f"*{suffix}.csv"
    files = sorted(directory.rglob(pattern))
    if not files:
        sys.exit(f"No files matching '{pattern}' found in {directory}")
    corpus = {}
    for f in files:
        try:
            header = f.read_text(encoding="utf-8-sig").splitlines()[0]
            corpus[f.name] = parse_header(header)
        except Exception as e:
            print(f"  Warning: could not read {f.name}: {e}", file=sys.stderr)
    return corpus


# -----------------------------------------------------------------------------

# Matrix builders

def build_family_matrix(
    corpus: dict,
) -> tuple[list[str], list[str], np.ndarray]:
    """
    Returns (row_labels, col_labels, matrix) where matrix[r, c] is the
    number of parts belonging to family r in file c.
    """
    filenames = list(corpus.keys())
    families  = [f for f in FAMILY_ORDER
                 if any(fam == f for parts in corpus.values() for _, fam in parts)]
    mat = np.zeros((len(families), len(filenames)), dtype=int)
    for ci, fname in enumerate(filenames):
        for _, fam in corpus[fname]:
            if fam in families:
                mat[families.index(fam), ci] += 1
    return families, filenames, mat


def build_canonical_matrix(
    corpus: dict,
) -> tuple[list[str], list[str], np.ndarray, dict[str, str]]:  # added dict
    filenames = list(corpus.keys())
    fam_of: dict[str, str] = {}
    for parts in corpus.values():
        for canon, fam in parts:
            fam_of.setdefault(canon, fam)

    def sort_key(name):
        fidx = FAMILY_ORDER.index(fam_of[name]) if fam_of[name] in FAMILY_ORDER else 99
        return (fidx, name.lower())

    row_labels = sorted(fam_of.keys(), key=sort_key)
    mat = np.zeros((len(row_labels), len(filenames)), dtype=int)
    for ci, fname in enumerate(filenames):
        for canon, _ in corpus[fname]:
            if canon in row_labels:
                mat[row_labels.index(canon), ci] += 1

    return row_labels, filenames, mat, fam_of


# -----------------------------------------------------------------------------

# Plotting

def _short_name(filename: str, max_len: int = 22) -> str:
    stem = Path(filename).stem
    return stem if len(stem) <= max_len else "…" + stem[-(max_len - 1):]


def plot_family_heatmap(
    corpus: dict,
    out_path: Path,
    annotate: bool | None = None,
) -> None:
    families, filenames, mat = build_family_matrix(corpus)
    n_rows, n_cols = mat.shape
    compact = n_cols > 30 if annotate is None else not annotate

    col_labels = [_short_name(f) for f in filenames]

    cell_w  = 1.2 if compact else max(1.6, min(3.2, 180 / n_cols))
    cell_h  = 0.8
    fig_w   = max(8, n_cols * cell_w + 3.5)
    fig_h   = max(3, n_rows * cell_h + 2.0)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    # Draw each row with its own colour ramp so family identity is visible
    for ri, fam in enumerate(families):
        cmap  = _family_cmap(fam)
        vmax  = mat[ri].max() or 1
        for ci in range(n_cols):
            val  = mat[ri, ci]
            rgba = cmap(val / vmax if vmax else 0)
            rect = plt.Rectangle([ci - 0.5, ri - 0.5], 1, 1, color=rgba)
            ax.add_patch(rect)
            if not compact and val > 0:
                lum = 0.299*rgba[0] + 0.587*rgba[1] + 0.114*rgba[2]
                ax.text(ci, ri, str(val), ha="center", va="center",
                        fontsize=8, color="white" if lum < 0.55 else "#333333")

    # Grid lines
    for ci in range(n_cols + 1):
        ax.axvline(ci - 0.5, color="#dddddd", linewidth=0.4, zorder=2)
    for ri in range(n_rows + 1):
        ax.axhline(ri - 0.5, color="#dddddd", linewidth=0.4, zorder=2)

    ax.set_xlim(-0.5, n_cols - 0.5)
    ax.set_ylim(-0.5, n_rows - 0.5)
    ax.invert_yaxis()

    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(families, fontsize=10)
    ax.set_xticks(range(n_cols))
    ax.set_xticklabels(col_labels, rotation=45, ha="right",
                       fontsize=8 if n_cols > 20 else 9)
    ax.tick_params(length=0)
    ax.spines[:].set_visible(False)

    # Colour-swatch legend
    swatches = [
        mpatches.Patch(
            facecolor=_family_cmap(f)(0.75),
            edgecolor="#aaaaaa", linewidth=0.5,
            label=f,
        )
        for f in families
    ]
    ax.legend(handles=swatches, loc="upper right",
              bbox_to_anchor=(1.0, -0.18 - 0.03 * n_cols / 10),
              frameon=False, fontsize=9, ncol=min(4, len(families)),
              handlelength=1, handleheight=0.9, title="Family",
              title_fontsize=9)

    n_files = len(filenames)
    fig.suptitle(
        f"Instrument-family heatmap — {n_files} file{'s' if n_files != 1 else ''}\n"
        f"Cell value = number of parts  |  colour ramp is per-family",
        fontsize=11, fontweight="normal", x=0.01, ha="left",
    )

    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Saved → {out_path}")
    plt.close(fig)


def plot_canonical_heatmap(
    corpus: dict,
    out_path: Path,
    annotate: bool | None = None,
) -> None:
    """
    Heatmap with rows = canonical instrument types, colour-coded by family.
    Thin dividers separate families visually.
    """
    row_labels, filenames, mat, fam_of = build_canonical_matrix(corpus)
    n_rows, n_cols = mat.shape
    compact = n_cols > 30 if annotate is None else not annotate

    col_labels = [_short_name(f) for f in filenames]

    cell_w = max(1.2, min(3.0, 160 / n_cols))
    cell_h = 0.55
    fig_w  = max(9, n_cols * cell_w + 4.0)
    fig_h  = max(5, n_rows * cell_h + 2.5)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    prev_fam = None
    for ri, canon in enumerate(row_labels):
        fam  = fam_of.get(canon, "Unknown")
        cmap = _family_cmap(fam)
        vmax = mat[ri].max() or 1
        # Thin divider between families
        if fam != prev_fam and ri > 0:
            ax.axhline(ri - 0.5, color="#888888", linewidth=0.8, zorder=3)
        prev_fam = fam

        for ci in range(n_cols):
            val  = mat[ri, ci]
            rgba = cmap(val / vmax if vmax else 0)
            rect = plt.Rectangle([ci - 0.5, ri - 0.5], 1, 1, color=rgba)
            ax.add_patch(rect)
            if not compact and val > 0:
                lum = 0.299*rgba[0] + 0.587*rgba[1] + 0.114*rgba[2]
                ax.text(ci, ri, str(val), ha="center", va="center",
                        fontsize=7, color="white" if lum < 0.55 else "#333333")

    for ci in range(n_cols + 1):
        ax.axvline(ci - 0.5, color="#dddddd", linewidth=0.3, zorder=2)
    for ri in range(n_rows + 1):
        ax.axhline(ri - 0.5, color="#eeeeee", linewidth=0.3, zorder=1)

    ax.set_xlim(-0.5, n_cols - 0.5)
    ax.set_ylim(-0.5, n_rows - 0.5)
    ax.invert_yaxis()

    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(row_labels, fontsize=8)
    ax.set_xticks(range(n_cols))
    ax.set_xticklabels(col_labels, rotation=45, ha="right",
                       fontsize=8 if n_cols > 20 else 9)
    ax.tick_params(length=0)
    ax.spines[:].set_visible(False)

    # Family colour legend
    seen_fams = list(dict.fromkeys(fam_of.get(r, "Unknown") for r in row_labels))
    swatches = [
        mpatches.Patch(
            facecolor=_family_cmap(f)(0.75),
            edgecolor="#aaaaaa", linewidth=0.5,
            label=f,
        )
        for f in seen_fams
    ]
    ax.legend(handles=swatches, loc="upper right",
              bbox_to_anchor=(1.0, -0.15),
              frameon=False, fontsize=9,
              ncol=min(4, len(seen_fams)),
              handlelength=1, handleheight=0.9,
              title="Family", title_fontsize=9)

    n_files = len(filenames)
    fig.suptitle(
        f"Instrument-type heatmap — {n_files} file{'s' if n_files != 1 else ''}\n"
        f"Cell value = number of parts  |  dividers separate families",
        fontsize=11, fontweight="normal", x=0.01, ha="left",
    )

    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Saved → {out_path}")
    plt.close(fig)


# -----------------------------------------------------------------------------

# CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--directory",
        type=Path,
        default=Path("../data/"),
        help="Path to corpus directory"
    )
    ap.add_argument(
    "--suffix",
        default="_part_relations",
        help="Filename suffix (before `.csv`)"
    )
    ap.add_argument(
    "--out",
        default = "instrument_heatmap.pdf",
        help = "Output image path  (default: instrument_heatmap.pdf)"
    )
    ap.add_argument(
    "--min-files",
        type=int,
        default=4,
        metavar="N",
        help="Only show types present in ≥N files"
    )
    ap.add_argument(
        "--no-unknown",
        action="store_false",
        help="Exclude instruments that could not be classified to a known family",
    )
    ap.add_argument(
        "--mode",
        choices=["family", "canonical"],
        default="family",
        help="Row grouping: 'family' (default) or 'canonical' instrument types"
    )
    ap.add_argument(
        "--annotate", action=argparse.BooleanOptionalAction, default=None,
                    help="Force cell annotations on/off (auto: on for ≤30 files)")
    args = ap.parse_args()

    corpus = load_corpus(args.directory, args.suffix)
    n = len(corpus)
    print(f"Loaded {n} file(s).")

    if args.mode == "canonical":
        plot_canonical_heatmap(corpus, Path(args.out), args.annotate)
    else:
        plot_family_heatmap(corpus, Path(args.out), args.annotate)


if __name__ == "__main__":
    main()

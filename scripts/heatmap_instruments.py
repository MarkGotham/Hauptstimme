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

# CSV / token parsing

def _parse_csv_row(line: str) -> list[str]:
    """Minimal CSV field splitter that respects double-quoted tokens."""
    return next(csv.reader(io.StringIO(line)))


_IGNORE_SET: frozenset[str] = frozenset(
    s.strip().lower() for s in ("Qstamp_Start", "Qstamp_End")
)


def _parse_token(raw: str) -> tuple[str, str] | None:
    """
    Return (canonical_name, family) for a single instrument token
    or `None` for cases where the token is in the ignore list, or unrecognised.
    """
    if not raw:
        return None
    if raw.strip().lower() in _IGNORE_SET:
        return None

    parsed = reg.parse(raw)
    return (parsed.canonical, parsed.family) if parsed else None


def parse_header(header_line: str) -> list[tuple[str, str]]:
    """Return list of (canonical, family) tuples from a header row string."""
    result = []
    for t in _parse_csv_row(header_line):
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


def _family_cmap(family: str) -> mcolors.LinearSegmentedColormap:
    light, dark = FAMILY_CMAPS.get(family, ("#f0f0f0", "#222222"))
    return mcolors.LinearSegmentedColormap.from_list(family, ["#ffffff", light, dark])


# -----------------------------------------------------------------------------

# Corpus loading

def load_corpus(directory: Path, suffix: str) -> dict[str, list[tuple[str, str]]]:
    """
    Rglob for `*{suffix}.csv` files in the given directory.
    Keys are relative paths, e.g. "X/Y/Z_part_relations.csv",
    preserving folder structure for optional grouping.
    """
    pattern = f"*{suffix}.csv"
    files = sorted(directory.rglob(pattern))
    if not files:
        sys.exit(f"No files matching '{pattern}' found in {directory}")
    corpus: dict[str, list[tuple[str, str]]] = {}
    for f in files:
        try:
            header = f.read_text(encoding="utf-8-sig").splitlines()[0]
            key = str(f.relative_to(directory))
            corpus[key] = parse_header(header)
        except Exception as e:
            print(f"  Warning: could not read {f.name}: {e}", file=sys.stderr)
    return corpus


def group_corpus_by_folder(
    corpus: dict[str, list[tuple[str, str]]],
) -> dict[str, list[tuple[str, str]]]:
    """
    Collapse corpus keys by their top-level subdirectory,
    concatenating all parts so
    matrix cell values become summed counts across the group.

    Files directly under the root (no subdirectory) are grouped as "(root)".
    """
    grouped: dict[str, list[tuple[str, str]]] = {}
    for rel_path, parts in corpus.items():
        parts_obj = Path(rel_path).parts
        top = parts_obj[0] if len(parts_obj) > 1 else "(root)"
        grouped.setdefault(top, []).extend(parts)
    return grouped


# -----------------------------------------------------------------------------

# Matrix builders

def build_family_matrix(
    corpus: dict[str, list[tuple[str, str]]],
) -> tuple[list[str], list[str], np.ndarray]:
    """
    Returns (row_labels, col_labels, matrix) where matrix[r, c] is the
    number of parts belonging to family r in file/group c.
    """
    filenames = list(corpus.keys())
    families = [
        f for f in FAMILY_ORDER
        if any(fam == f for parts in corpus.values() for _, fam in parts)
    ]
    mat = np.zeros((len(families), len(filenames)), dtype=int)
    for ci, fname in enumerate(filenames):
        for _, fam in corpus[fname]:
            if fam in families:
                mat[families.index(fam), ci] += 1
    return families, filenames, mat


def build_canonical_matrix(
    corpus: dict[str, list[tuple[str, str]]],
) -> tuple[list[str], list[str], np.ndarray, dict[str, str]]:
    """
    Like `build_family_matrix` but where rows = canonical instrument types,
    sorted by family then name.
    Also returns `fam_of` for use in plotting.
    """
    filenames = list(corpus.keys())
    fam_of: dict[str, str] = {}
    for parts in corpus.values():
        for canon, fam in parts:
            fam_of.setdefault(canon, fam)

    def sort_key(name: str) -> tuple[int, str]:
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

# Shared helpers

def _short_name(key: str, max_len: int = 32) -> str:
    """
    Return a readable column label from a corpus key.
    Uses the file stem (basename without extension); truncates with a leading
    ellipsis if longer than max_len.
    """
    stem = Path(key).stem
    return stem if len(stem) <= max_len else "…" + stem[-(max_len - 1):]


def _is_compact(n_cols: int, annotate: bool | None) -> bool:
    """Determine whether to suppress per-cell annotations."""
    return not annotate if annotate is not None else n_cols > 30


def _apply_grid(ax, n_rows: int, n_cols: int) -> None:
    """Draw thin grid lines over the heatmap cells."""
    for ci in range(n_cols + 1):
        ax.axvline(ci - 0.5, color="#dddddd", linewidth=0.4, zorder=2)
    for ri in range(n_rows + 1):
        ax.axhline(ri - 0.5, color="#dddddd", linewidth=0.4, zorder=2)


def _set_col_labels(ax, col_labels: list[str], n_cols: int) -> None:
    """Apply x-axis tick labels at 90-degree rotation."""
    ax.set_xticks(range(n_cols))
    ax.set_xticklabels(
        col_labels,
        rotation=90,
        ha="center",
        fontsize=8 if n_cols > 20 else 9,
    )


# -----------------------------------------------------------------------------

# Plotting

def plot_family_heatmap(
    corpus: dict,
    out_path: Path,
    annotate: bool | None = None,
) -> None:
    families, filenames, mat = build_family_matrix(corpus)
    n_rows, n_cols = mat.shape
    compact = _is_compact(n_cols, annotate)

    col_labels = [_short_name(f) for f in filenames]

    cell_w = 1.2 if compact else max(1.6, min(3.2, 180 / n_cols))
    cell_h = 0.8
    fig_w  = max(8, n_cols * cell_w + 3.5)
    fig_h  = max(3, n_rows * cell_h + 2.0)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    for ri, fam in enumerate(families):
        cmap = _family_cmap(fam)
        vmax = mat[ri].max() or 1
        for ci in range(n_cols):
            val  = mat[ri, ci]
            rgba = cmap(val / vmax)
            ax.add_patch(plt.Rectangle([ci - 0.5, ri - 0.5], 1, 1, color=rgba))
            if not compact and val > 0:
                lum = 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2]
                ax.text(ci, ri, str(val), ha="center", va="center",
                        fontsize=8, color="white" if lum < 0.55 else "#333333")

    _apply_grid(ax, n_rows, n_cols)

    ax.set_xlim(-0.5, n_cols - 0.5)
    ax.set_ylim(-0.5, n_rows - 0.5)
    ax.invert_yaxis()

    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(families, fontsize=10)
    _set_col_labels(ax, col_labels, n_cols)
    ax.tick_params(length=0)
    ax.spines[:].set_visible(False)

    swatches = [
        mpatches.Patch(
            facecolor=_family_cmap(f)(0.75),
            edgecolor="#aaaaaa", linewidth=0.5,
            label=f,
        )
        for f in families
    ]
    fig.legend(
        handles=swatches,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.02),
        frameon=False, fontsize=9,
        ncol=min(len(families), 7),
        handlelength=1, handleheight=0.9,
        title="Family", title_fontsize=9,
    )

    n_files = len(filenames)
    fig.suptitle(
        f"Instrument-family heatmap — {n_files} column{'s' if n_files != 1 else ''}\n"
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
    compact = _is_compact(n_cols, annotate)

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

        if fam != prev_fam and ri > 0:
            ax.axhline(ri - 0.5, color="#888888", linewidth=0.8, zorder=3)
        prev_fam = fam

        for ci in range(n_cols):
            val  = mat[ri, ci]
            rgba = cmap(val / vmax)
            ax.add_patch(plt.Rectangle([ci - 0.5, ri - 0.5], 1, 1, color=rgba))
            if not compact and val > 0:
                lum = 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2]
                ax.text(ci, ri, str(val), ha="center", va="center",
                        fontsize=7, color="white" if lum < 0.55 else "#333333")

    # Fine grid (family dividers drawn above take priority via zorder)
    for ci in range(n_cols + 1):
        ax.axvline(ci - 0.5, color="#dddddd", linewidth=0.3, zorder=2)
    for ri in range(n_rows + 1):
        ax.axhline(ri - 0.5, color="#eeeeee", linewidth=0.3, zorder=1)

    ax.set_xlim(-0.5, n_cols - 0.5)
    ax.set_ylim(-0.5, n_rows - 0.5)
    ax.invert_yaxis()

    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(row_labels, fontsize=8)
    _set_col_labels(ax, col_labels, n_cols)
    ax.tick_params(length=0)
    ax.spines[:].set_visible(False)

    seen_fams = list(dict.fromkeys(fam_of.get(r, "Unknown") for r in row_labels))
    swatches = [
        mpatches.Patch(
            facecolor=_family_cmap(f)(0.75),
            edgecolor="#aaaaaa", linewidth=0.5,
            label=f,
        )
        for f in seen_fams
    ]
    fig.legend(
        handles=swatches,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.02),
        frameon=False, fontsize=9,
        ncol=min(len(seen_fams), 7),
        handlelength=1, handleheight=0.9,
        title="Family", title_fontsize=9,
    )

    n_files = len(filenames)
    fig.suptitle(
        f"Instrument-type heatmap — {n_files} column{'s' if n_files != 1 else ''}\n"
        f"Cell value = number of parts  |  dividers separate families",
        fontsize=11, fontweight="normal", x=0.01, ha="left",
    )

    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Saved → {out_path}")
    plt.close(fig)


# -----------------------------------------------------------------------------

# CLI


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
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
        default="instrument_heatmap.pdf",
        help="Output image path",
    )
    ap.add_argument(
        "--mode",
        choices=["family", "canonical"],
        default="family",
        help="Row grouping: 'family' (default) or 'canonical' instrument types",
    )
    ap.add_argument(
        "--annotate",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Force cell annotations on/off (auto: on for ≤30 columns)",
    )
    ap.add_argument(
        "--group-files",
        action="store_true",
        default=False,
        help="Group files by top-level subdirectory instead of showing individually",
    )
    ap.add_argument(
        "--group-files-threshold",
        type=int,
        default=40,
        metavar="N",
        help="Auto-group by folder when file count exceeds N (default: 40)",
    )
    args = ap.parse_args()

    corpus = load_corpus(args.directory, args.suffix)
    n = len(corpus)
    print(f"Loaded {n} file(s).")

    if args.group_files or n > args.group_files_threshold:
        reason = "flag set" if args.group_files else f">{args.group_files_threshold} files"
        print(f"Grouping {n} files by top-level folder ({reason}).")
        corpus = group_corpus_by_folder(corpus)
        print(f"  → {len(corpus)} group(s).")

    if args.mode == "canonical":
        plot_canonical_heatmap(corpus, Path(args.out), args.annotate)
    else:
        plot_family_heatmap(corpus, Path(args.out), args.annotate)


if __name__ == "__main__":
    main()

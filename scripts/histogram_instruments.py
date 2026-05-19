#!/usr/bin/env python3
"""
NAME
===============================
Histogram Instruments (histogram_instruments.py)


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
and plot a histogram showing how many files contain at
least one instance of each canonical instrument type.


USAGE:
===============================
    python histogram_instruments.py /path/to/corpus [options]

Options include:
    --suffix
    --out instrument_histogram.pdf
    --min-files

"""

import argparse
import csv
import io
import sys
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from amads.instruments import instrument_classification

reg = instrument_classification.InstrumentRegistry()

# -----------------------------------------------------------------------------


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

    clean_raw = raw.strip().lower()
    if clean_raw in [s.strip().lower() for s in ignore_list]:
        return None

    parsed = reg.parse(raw)
    if parsed:
        return parsed.canonical, parsed.family
    else:
        return None


# -----------------------------------------------------------------------------

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
FAMILY_COLORS = {
    "Woodwind":   "#3266ad",
    "Brass":  "#c45a1a",
    "Strings":    "#2a7a4f",
    "Percussion": "#8b4fa8",
    "Voice":  "#b08020",
    "Keyboard":   "#1a8a8a",
    "Unknown":    "#73726c",
}


# -----------------------------------------------------------------------------

# Corpus loading

def load_corpus(
        directory: Path = Path("../data/"),
        suffix: str = "_part_relations.csv",
) -> dict[str, list[tuple[str, str]]]:
    """
    Scan `directory` for files ending in the given `{suffix].csv` and
    parse the header row of each file.

    Returns:
        dict[str, list[tuple[str, str]]] for:
        {filename: [(canonical, family), ...]}
    """
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

# Analysis

def build_prevalence(corpus: dict, drop_unknown: bool = False) -> dict[str, dict]:
    """
    For each canonical instrument type return:
    {"family": str, "file_count": int, "total_parts": int}

    This data is grouped by family, then sorted by `file_count` descending within each family.
    """
    file_count: dict[str, int] = defaultdict(int)
    total_parts: dict[str, int] = defaultdict(int)
    families: dict[str, str] = {}

    for instruments in corpus.values():
        seen = set()
        for canon, fam in instruments:
            total_parts[canon] += 1
            families[canon] = fam
            if canon not in seen:
                file_count[canon] += 1
                seen.add(canon)

    def sort_key(name):
        fam = families[name]
        fidx = FAMILY_ORDER.index(fam) if fam in FAMILY_ORDER else 99
        return (fidx, -file_count[name])  # family group, then most-used first

    return {
        name: {
            "family": families[name],
            "file_count": file_count[name],
            "total_parts": total_parts[name],
        }
        for name in sorted(file_count, key=sort_key)
        if not (drop_unknown and families[name] == "Unknown")
    }


# -----------------------------------------------------------------------------

# Plot

def plot_histogram(
    corpus: dict,
    prevalence: dict,
    min_files: int,
    out_path: Path,
) -> None:
    n_files = len(corpus)

    # Filter
    data = {k: v for k, v in prevalence.items() if v["file_count"] >= min_files}
    if not data:
        sys.exit(f"No instrument types appear in ≥{min_files} files.")

    labels   = list(data.keys())
    counts   = [data[k]["file_count"]  for k in labels]
    percents = [100 * c / n_files      for c in counts]
    colors   = [FAMILY_COLORS.get(data[k]["family"], "#73726c") for k in labels]

    n = len(labels)
    bar_h = 0.55
    fig_h = max(4, n * 0.42 + 1.8)

    fig, ax = plt.subplots(figsize=(10, fig_h))
    y = np.arange(n)

    bars = ax.barh(y, counts, height=bar_h, color=colors, zorder=2)

    # Count labels
    for bar, cnt, pct in zip(bars, counts, percents):
        ax.text(
            bar.get_width() + 0.15, bar.get_y() + bar.get_height() / 2,
            f"{cnt}  ({pct:.0f}%)",
            va="center", ha="left", fontsize=9,
            color="#444444",
        )

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel(f"Number of files containing ≥{min_files} of this type", fontsize=10)
    ax.set_xlim(0, n_files * 1.22)
    ax.set_xticks(range(0, n_files + 1, 10))
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: str(int(v))))
    ax.axvline(n_files, color="#cccccc", linewidth=0.8, linestyle="--", zorder=1)
    ax.grid(axis="x", color="#eeeeee", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[["top","right","left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)

    # Legend
    handles = [
        mpatches.Patch(color=FAMILY_COLORS[f], label=f)
        for f in FAMILY_ORDER
        if any(data[k]["family"] == f for k in data)
    ]
    ax.legend(
        handles=handles, loc="lower right",
        frameon=True, fontsize=12, ncol=2,
        handlelength=1.4, handleheight=1.2,
    )

    fig.suptitle(
        f"Instrument prevalence across {n_files} file{'s' if n_files!=1 else ''}",
        fontsize=13, fontweight="normal", x=0.02, ha="left", y=1.01,
    )

    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Saved → {out_path}")
    plt.close(fig)


# -----------------------------------------------------------------------------

# CLI

def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
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
        default="instrument_histogram.pdf",
        help="Output image path  (default: instrument_histogram.pdf)"
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
    args = ap.parse_args()

    corpus = load_corpus(args.directory, args.suffix)
    prevalence = build_prevalence(corpus, drop_unknown=args.no_unknown)

    print(f"Loaded {len(corpus)} file(s), "
          f"{len(prevalence)} unique instrument type(s).")

    plot_histogram(corpus, prevalence, args.min_files, Path(args.out))


if __name__ == "__main__":
    main()

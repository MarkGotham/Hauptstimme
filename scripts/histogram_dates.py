#!/usr/bin/env python3
"""
NAME
===============================
Histogram Dates (histogram_dates.py)


BY
===============================
Mark Gotham


LICENCE:
===============================
Code = MIT. See [README](https://github.com/MarkGotham/Hauptstimme/tree/main#licence).


ABOUT:
===============================
Plot a histogram of composition dates from `sets.yaml`.

We assume each entry to have a single, indicative date.
Dates are complicated (as discussed in the paper),
this is an approximate measure only.

Usage:
    python histogram_dates.py [options]

Requirements:
    pip install pyyaml matplotlib
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import yaml


# ---------------------------------------------------------------------------

# Date parsing

def collect_dates(entries: list[dict], field: str = "date") -> list[tuple[str, float]]:
    """
    Return a list of (work_name, year) pairs
    for all cases where the field is present (skips that item otherwise).
    """
    results = []
    for entry in entries:
        composer = entry.get("path").split(",")[0]

        raw = entry.get(field)
        if raw is not None:
            results.append((composer, int(raw)))

    return results


# ---------------------------------------------------------------------------

# Binning

def auto_bin_size(years: list[float]) -> int:
    """Pick a round bin size based on the span of the data."""
    span = max(years) - min(years)
    if span <= 50:
        return 10
    if span <= 250:
        return 20
    return 50


def make_bins(years: list[int], bin_size: int) -> list[int]:
    """Return bin edges aligned to multiples of `bin_size`."""
    lo = int(min(years) // bin_size * bin_size)
    hi = int(max(years) // bin_size * bin_size) + bin_size
    return list(range(lo, hi + bin_size, bin_size))


# ---------------------------------------------------------------------------

# Plotting

def plot_histogram(
    years: list[int],
    names: list[str],
    bin_size: int,
    field: str,
    output: Optional[Path] = None,
) -> None:
    bins = make_bins(years, bin_size)

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#f9f6f0")
    ax.set_facecolor("#f9f6f0")

    n, edges, patches = ax.hist(
        years,
        bins=bins,
        color="#4a6fa5",
        edgecolor="#f9f6f0",
        linewidth=1.5,
        rwidth=0.85,
    )

    # Annotate bars with count and work names
    for count, left, patch in zip(n, edges[:-1], patches):
        if count == 0:
            continue
        # Which works fall in this bin?
        right = left + bin_size
        in_bin = [nm for nm, yr in zip(names, years) if left <= yr < right]

        # Count label above bar
        ax.text(
            patch.get_x() + patch.get_width() / 2,
            count + 0.05,
            str(int(count)),
            ha="center", va="bottom",
            fontsize=9, fontweight="bold", color="#333333",
        )

        # Composer names inside / below bar (rotated)
        label = "\n".join(list(set(in_bin)))
        ax.text(
            patch.get_x() + patch.get_width() / 2,
            count / 2,
            label,
            ha="center", va="center",
            fontsize=6.5, color="white", fontweight="bold",
            rotation=90 if len(in_bin) > 2 else 0,
            wrap=True,
        )

    ax.set_xlabel("Year", fontsize=11, labelpad=8, color="#333333")
    ax.set_ylabel("Number of works", fontsize=11, labelpad=8, color="#333333")
    ax.set_title(
        f"Histogram of {field.replace("_", " ")}\n"
        f"({len(years)} works, {bin_size}-year bins)",
        fontsize=12, pad=14, color="#222222",
    )

    ax.xaxis.set_major_locator(ticker.MultipleLocator(bin_size))
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.tick_params(colors="#555555")
    for spine in ax.spines.values():
        spine.set_edgecolor("#cccccc")

    ax.set_xlim(edges[0] - bin_size * 0.5, edges[-1] + bin_size * 0.5)
    ax.set_ylim(0, max(n) + 1.2)

    plt.tight_layout()

    if output:
        fig.savefig(output, dpi=150, bbox_inches="tight")
        print(f"Saved: {output}")
    else:
        plt.show()


# ---------------------------------------------------------------------------

# Entry point

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yaml", default="../data/sets.yaml",
        help="Path to sets.yaml (default: sets.yaml)",
    )
    parser.add_argument(
        "--field",
        choices=["date"], # placeholder in case of adding options later
        default="date",
        help="Which date field to use (placeholder: currently only one)",
    )
    parser.add_argument(
        "--bin-size", type=int, default=None, metavar="YEARS",
        help="Histogram bin width in years (default: auto)",
    )
    parser.add_argument(
        "--output", default="date_range.pdf", metavar="FILE",
        help="Save plot to file instead of displaying it.",
    )
    args = parser.parse_args()

    yaml_path = Path(args.yaml)
    if not yaml_path.exists():
        sys.exit(f"ERROR: file not found: {yaml_path}")

    with yaml_path.open() as f:
        entries = yaml.safe_load(f)

    pairs = collect_dates(entries, args.field)
    if not pairs:
        sys.exit(f"ERROR: no usable date values found for field='{args.field}'")

    names, years = zip(*pairs)
    years = list(years)

    skipped = len(entries) - len(pairs)
    if skipped:
        print(f"Note: {skipped} entries had no usable '{args.field}' date and were skipped.")

    bin_size = args.bin_size or auto_bin_size(years)
    print(f"Plotting {len(years)} works with {bin_size}-year bins "
          f"(span: {int(min(years))}–{int(max(years))})")

    output = Path(args.output) if args.output else None
    plot_histogram(years, list(names), bin_size, args.field, output)


if __name__ == "__main__":
    main()

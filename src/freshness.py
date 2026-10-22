"""
NAME
===============================
Freshness (freshness.py)


LICENCE:
===============================
Code = MIT. See [README](https://github.com/MarkGotham/Hauptstimme/tree/main#licence).


ABOUT:
===============================
One rule for deciding whether a derived file needs (re)building, shared by
every step of the corpus build.

Many files in the corpus are derived from others, in a chain:

    .mscz  ->  .mxl  ->  _annotations.csv, _melody.mxl, .krn, .csv
                     ->  _part_relations.csv (also needs .csv, _annotations.csv)
    .mscz  ->  .mm.json

The user chooses an `overwrite` mode:

- "stale" (the default for corpus builds): build if the derived file is
    missing, or if any source was modified more recently than it.
- "missing": build only if the derived file is missing,
    and never replace an existing one (even if its source has changed).
- "always": build regardless.

For derived files made of several outputs (e.g., annotations CSV *and*
melody score), pass them all: any missing output triggers a build, and
staleness is judged against the *oldest* output.

Because each step writes its output after reading its source, rebuilding
a file makes it newer than its own sources and, in turn, makes everything
derived from it stale, so a change to a .mscz cascades down the chain
automatically.

What modification times cannot see:
1.  Changes to code, annotation conventions (`annotation_jobs`),
    or the versions of music21/converter21/MuseScore. After any of these,
    use "always".
2.  Fresh clones and checkouts. Git sets modification times to when a file
    was checked out, not when it was committed, so after a clone (or
    CI run) the order is arbitrary. Use "always" there.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Union

OVERWRITE_MODES = ("stale", "missing", "always")

PathLike = Union[str, Path]
PathsLike = Union[PathLike, Iterable[PathLike]]


def check_overwrite_mode(overwrite: str) -> str:
    """
    Validate an overwrite mode.

    Raises:
        ValueError: If it is not one of `OVERWRITE_MODES`.
    """
    if overwrite not in OVERWRITE_MODES:
        raise ValueError(
            f"Error: overwrite must be one of {OVERWRITE_MODES}, " +
            f"not '{overwrite}'."
        )
    return overwrite


def _as_paths(paths: PathsLike) -> list[Path]:
    if isinstance(paths, (str, Path)):
        return [Path(paths)]
    return [Path(p) for p in paths]


def update_reason(
    sources: PathsLike,
    derived: PathsLike,
    overwrite: str = "stale"
) -> Optional[str]:
    """
    Say why a derived file (or set of files) needs building,
    or None if it should be left alone.

    Args:
        sources: The file(s) the derived file(s) are made from.
        derived: The derived file(s).
        overwrite: "stale", "missing" or "always" (see module docs).
            Default = "stale".

    Returns:
        None if nothing needs doing. Otherwise a short reason:
        "forced" (always), "missing", or "stale".

    Raises:
        ValueError: If the overwrite mode is invalid.
        FileNotFoundError: If a source doesn't exist (there is nothing to
            build from, which is an error in the build, not a reason to skip).
    """
    check_overwrite_mode(overwrite)
    source_paths = _as_paths(sources)
    derived_paths = _as_paths(derived)

    for source in source_paths:
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source}")

    if overwrite == "always":
        return "forced"

    if any(not d.exists() for d in derived_paths):
        return "missing"

    if overwrite == "missing":
        return None

    newest_source = max(s.stat().st_mtime_ns for s in source_paths)
    oldest_derived = min(d.stat().st_mtime_ns for d in derived_paths)
    # Strictly newer: equal times (coarse filesystem clocks) are not stale.
    return "stale" if newest_source > oldest_derived else None


def needs_update(
    sources: PathsLike,
    derived: PathsLike,
    overwrite: str = "stale",
    label: Optional[str] = None
) -> bool:
    """
    Whether a derived file (or set of files) needs building.
    See `update_reason` for the arguments.

    Args:
        label: If given, print one line saying what will be done and why
            (or that the file is up to date and skipped).
    """
    reason = update_reason(sources, derived, overwrite)
    if label is not None:
        if reason is None:
            print(f"  Up to date, skipping: {label}")
        else:
            print(f"  Building ({reason}): {label}")
    return reason is not None

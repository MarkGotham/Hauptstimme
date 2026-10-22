"""
NAME
===============================
Derive (derive.py)


LICENCE:
===============================
Code = MIT. See [README](https://github.com/MarkGotham/Hauptstimme/tree/main#licence).


ABOUT:
===============================
Derive the annotation-free versions of a score from the annotated
MusicXML (itself a conversion of the MuseScore file, the version of record).

For each annotated `<score>.mxl` this produces:
- `<score>.krn`: a Humdrum **kern file without annotations.
    This exists mainly for clean, line-based git diffs of the *music*
    (annotation changes show up in `_annotations.csv`; layout changes
    don't show up at all), and secondarily for use in VHV and the like.
    It is written alongside the score (or in `out_dir`).
- `<score>_plain.mxl`: the same score without annotations, as MusicXML.
    This goes under `build/plain/` (or `out_dir`), NOT the data folder.
    Several scripts glob the data folder for `*.mxl` and would otherwise
    mistake it for a corpus score.

What counts as an annotation is defined by exactly the same rule as in
`annotations.py` (`meets_restrictions`):
- `lyrics_not_text=True`: lyrics on notes whose text meets the restrictions
    (any other lyrics are real lyrics and are kept).
- `lyrics_not_text=False`: text expressions whose text meets the restrictions
    (any other text, e.g., 'arco', 'a2' or a tempo marking, is kept;
    real lyrics are not touched).

Notes:
1.  The kern is written by `converter21` (which replaces music21's Humdrum
    converter, and adds a writer). The chain is therefore
    MuseScore -> MusicXML -> music21 -> kern, and anything music21 does not
    model (e.g., layout, some directions) is not in the kern.
2.  The kern is post-processed to drop volatile `!!!software:` reference
    records (they carry tool version numbers, so would otherwise rewrite
    every file on every version bump).
3.  Pin `music21` and `converter21` (see requirements.txt): a version change
    can change the kern for every score. Regenerate the whole corpus in a
    single commit when bumping.
4.  `_plain.mxl` is written by music21, not by MuseScore, so it carries music21's
    round-trip changes (e.g., an empty text direction can appear beside a
    tempo marking, even with nothing stripped), and does not retain
    MuseScore's layout. It is the annotation-free *music*; for a faithful
    engraved copy, use the MuseScore file.
5.  Run `python3 -m src.derive <score.mxl>` for a single score. See
    `scripts/build_corpus.py` for the corpus-wide run with each work's
    annotation conventions.
"""
from __future__ import annotations

import re
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Dict, Optional, Union

from music21 import converter, expressions
from music21.stream.base import Score

from src.annotations import meets_restrictions
from src.constants import BUILD_PATH, DATA_PATH
from src.freshness import OVERWRITE_MODES, check_overwrite_mode, needs_update
from src.utils import validate_path

# Same default as `get_annotations_and_melody_scores`:
# a single letter with an optional prime.
DEFAULT_ANNOTATION_RESTRICTIONS = "[a-zA-Z]'?"

# Reference records that vary with the tool versions, not the music.
VOLATILE_KERN_LINES = re.compile(r"^!!!software:.*(?:\n|$)", re.MULTILINE)

_converter21_registered = False


def register_converter21() -> None:
    """
    Make music21 use converter21's Humdrum (and MEI) converters.

    This applies to the whole process (not just this module), which is
    harmless for the rest of this code base (it never parses kern),
    but is why registration happens lazily, here, rather than on import.
    """
    global _converter21_registered
    if not _converter21_registered:
        import converter21
        converter21.register()
        _converter21_registered = True


def strip_annotations(
    score: Score,
    lyrics_not_text: bool = True,
    annotation_restrictions: Optional[Union[list, str]] = (
        DEFAULT_ANNOTATION_RESTRICTIONS
    )
) -> int:
    """
    Remove the Hauptstimme annotations from a score, in place.

    Args:
        score: The (annotated) score. Modified in place.
        lyrics_not_text: Whether the annotations are lyrics (True)
            or text expressions (False). Default = True.
        annotation_restrictions: Which labels count as annotations,
            either a list of allowed values or a regex that requires a
            full match. As in `HauptstimmeAnnotations`, None means no
            restriction when the annotations are lyrics (so every lyric
            is an annotation) and is not allowed for text expressions.
            Default = "[a-zA-Z]'?".

    Returns:
        The number of annotations removed.

    Raises:
        ValueError: If `lyrics_not_text` is False and
            `annotation_restrictions` is None.
    """
    if not lyrics_not_text and annotation_restrictions is None:
        raise ValueError(
            "Error: When the annotations are text expressions, " +
            "restrictions are needed to prevent tempo readings etc. " +
            "being removed."
        )

    removed = 0

    if lyrics_not_text:
        # Notes only: as in extraction, lyrics on rests are not annotations.
        for n in score.recurse().notes:
            if not n.lyrics:
                continue
            kept = [
                lyric for lyric in n.lyrics
                if not meets_restrictions(
                    lyric.text or "", annotation_restrictions
                )
            ]
            if len(kept) != len(n.lyrics):
                removed += len(n.lyrics) - len(kept)
                n.lyrics = kept
    else:
        for t in list(score.recurse().getElementsByClass(
            expressions.TextExpression
        )):
            if meets_restrictions(str(t.content), annotation_restrictions):
                score.remove(t, recurse=True)
                removed += 1

    return removed


def clean_kern(text: str) -> str:
    """
    Normalise generated kern text for stable, tool-version-independent diffs:
    unix line endings, no volatile `!!!software:` records, one final newline.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = VOLATILE_KERN_LINES.sub("", text)
    return text.rstrip("\n") + "\n"


def write_krn(score: Score, path: Union[str, Path]) -> Path:
    """
    Write a score as Humdrum **kern, via converter21, and clean the result
    (see `clean_kern`).

    Args:
        score: The score to write.
        path: The destination .krn file path.

    Returns:
        The path written to.
    """
    register_converter21()
    path = Path(path)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_file = Path(tmp) / "score.krn"
        score.write("humdrum", fp=str(tmp_file))
        text = tmp_file.read_text(encoding="utf-8")

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(clean_kern(text))
    return path


def plain_mxl_path(
    score_mxl: Path,
    out_dir: Optional[Path] = None,
    mkdir: bool = True
) -> Path:
    """
    Where the annotation-free MusicXML for a score goes:
    `out_dir` if given, otherwise under `build/plain/`, mirroring the score's
    location in the data folder. Never inside the data folder itself.

    Args:
        mkdir: Whether to create the directory. Default = True. Pass False
            to only look up the path (e.g., to check whether it exists).
    """
    if out_dir is None:
        try:
            relative_dir = score_mxl.resolve().parent.relative_to(
                DATA_PATH.resolve()
            )
        except ValueError:
            relative_dir = Path()
        out_dir = BUILD_PATH / "plain" / relative_dir
    if mkdir:
        out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{score_mxl.stem}_plain.mxl"


def derive_score(
    score_mxl: Union[str, Path],
    out_dir: Optional[Union[str, Path]] = None,
    lyrics_not_text: bool = True,
    annotation_restrictions: Optional[Union[list, str]] = (
        DEFAULT_ANNOTATION_RESTRICTIONS
    ),
    krn: bool = True,
    plain_mxl: bool = True,
    overwrite: str = "always"
) -> Dict[str, Union[Path, int, None, list]]:
    """
    Derive the annotation-free kern and/or MusicXML for one score.

    Args:
        score_mxl: The annotated score's MusicXML file path.
        out_dir: Where to write the outputs. Default = None, meaning the
            .krn goes next to the score and the _plain.mxl under `build/`.
        lyrics_not_text: Whether the annotations are lyrics (True)
            or text expressions (False). Default = True.
        annotation_restrictions: Which labels count as annotations
            (see `strip_annotations`). Default = "[a-zA-Z]'?".
        krn: Whether to write the .krn file. Default = True.
        plain_mxl: Whether to write the _plain.mxl file. Default = True.
        overwrite: Whether to (re)write each output: "stale" (if missing
            or older than the score), "missing" (only if missing) or
            "always". Each output is judged separately, and the score is
            not even parsed if none needs writing. Default = "always"
            (an explicit call does what it says; corpus builds choose
            their own, see `scripts/build_corpus.py`).

    Returns:
        A dict with:
        - 'removed': the number of annotations stripped (None if the score
            was not parsed because everything was up to date).
        - 'krn' and 'plain_mxl': the paths written (if any).
        - 'skipped': the names of requested outputs left alone because
            they were up to date.
    """
    check_overwrite_mode(overwrite)
    score_mxl = validate_path(score_mxl)
    out_dir = validate_path(out_dir, dir=True) if out_dir is not None else None

    # Decide what to write, output by output (without creating directories).
    wanted = {}
    if krn:
        wanted["krn"] = (out_dir or score_mxl.parent) / f"{score_mxl.stem}.krn"
    if plain_mxl:
        wanted["plain_mxl"] = plain_mxl_path(score_mxl, out_dir, mkdir=False)

    todo = {}
    skipped = []
    for name, path in wanted.items():
        if needs_update(score_mxl, path, overwrite, label=path.name):
            todo[name] = path
        else:
            skipped.append(name)

    results: Dict[str, Union[Path, int, None, list]] = {
        "removed": None, "skipped": skipped
    }
    if not todo:
        return results

    register_converter21()

    # forceSource: never use music21's parse cache, which could hide changes.
    score = converter.parse(score_mxl, forceSource=True)
    if not isinstance(score, Score):
        raise ValueError("Error: Score is not of type 'music21.stream.Score'.")

    removed = strip_annotations(score, lyrics_not_text, annotation_restrictions)
    results["removed"] = removed
    if removed == 0:
        print(
            f"Warning: no annotations found in '{score_mxl.name}'. Check " +
            "that lyrics_not_text and annotation_restrictions are right " +
            "for this score."
        )

    # Exporters can modify the stream they are given, so give the second
    # one its own copy, taken before the first runs.
    plain_score = deepcopy(score) if "plain_mxl" in todo else None

    if "krn" in todo:
        results["krn"] = write_krn(score, todo["krn"])

    if plain_score is not None:
        plain_path = plain_mxl_path(score_mxl, out_dir, mkdir=True)
        plain_score.write("mxl", fp=str(plain_path))
        results["plain_mxl"] = plain_path

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Derive the annotation-free .krn and _plain.mxl for a score."
    )
    parser.add_argument("score", help="The annotated score's .mxl file.")
    parser.add_argument("-o", "--out", help="Output directory.")
    parser.add_argument(
        "-r", "--restr", default=DEFAULT_ANNOTATION_RESTRICTIONS,
        help="Annotation restrictions (a regex)."
    )
    parser.add_argument(
        "-t", "--text", action="store_true",
        help="The annotations are text expressions (not lyrics)."
    )
    parser.add_argument(
        "--overwrite", choices=OVERWRITE_MODES, default="always",
        help="Whether to rewrite outputs that exist. Default = always."
    )
    args = parser.parse_args()

    print(derive_score(
        args.score,
        out_dir=args.out,
        lyrics_not_text=not args.text,
        annotation_restrictions=args.restr,
        overwrite=args.overwrite
    ))

"""
Tests for src/derive.py.

Run from the repo root with `pytest tests/`.

- Unit tests use small synthetic scores.
- Corpus tests use the two smallest real movements, one per annotation
  convention, and check three things:
    1.  The number of annotations stripped equals the number of rows in
        the committed `_annotations.csv` (so stripping and extraction agree).
    2.  Output is deterministic.
    3.  The kern matches the committed golden file in tests/golden/.

The golden files pin the music21 and converter21 versions in
requirements.txt: if a version bump changes the kern, these fail, which is
the cue to regenerate the corpus in a single commit. To update the golden
files after an intended change:

    UPDATE_GOLDEN=1 pytest tests/test_derive.py
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest
from music21 import expressions, note, stream

from src.constants import DATA_PATH
from src.derive import clean_kern, derive_score, strip_annotations

GOLDEN = Path(__file__).parent / "golden"
UPDATE_GOLDEN = bool(os.environ.get("UPDATE_GOLDEN"))


def make_score(lyrics=(), texts=(), rest_lyric=None) -> stream.Score:
    """A one-part score with the given lyrics on notes and text expressions."""
    part = stream.Part()
    measure = stream.Measure(number=1)
    for lyric in lyrics:
        n = note.Note("C4", quarterLength=1)
        n.addLyric(lyric)
        measure.append(n)
    if rest_lyric is not None:
        r = note.Rest(quarterLength=1)
        r.addLyric(rest_lyric)
        measure.append(r)
    for text in texts:
        measure.insert(0, expressions.TextExpression(text))
    part.append(measure)
    score = stream.Score()
    score.insert(0, part)
    return score


def lyric_texts(score):
    return [lyric.text for n in score.recurse().notes for lyric in n.lyrics]


def text_contents(score):
    return [
        str(t.content)
        for t in score.recurse().getElementsByClass(expressions.TextExpression)
    ]


# --- strip_annotations -----------------------------------------------------

def test_strip_lyrics_default_restrictions():
    score = make_score(lyrics=["a", "b'", "Hal", "tr", "A"])
    removed = strip_annotations(score)
    assert removed == 3
    assert lyric_texts(score) == ["Hal", "tr"]


def test_strip_lyrics_custom_regex_and_list():
    score = make_score(lyrics=["a", "tr", "Hal"])
    assert strip_annotations(score, annotation_restrictions="[a-z]+") == 2
    assert lyric_texts(score) == ["Hal"]

    score = make_score(lyrics=["a", "b", "c"])
    assert strip_annotations(score, annotation_restrictions=["a", "c"]) == 2
    assert lyric_texts(score) == ["b"]


def test_strip_lyrics_none_restrictions_means_every_lyric():
    # As in HauptstimmeAnnotations, e.g. for Beach where all lyrics are annotations.
    score = make_score(lyrics=["a", "whatever"])
    assert strip_annotations(score, annotation_restrictions=None) == 2
    assert lyric_texts(score) == []


def test_strip_lyrics_leaves_lyrics_on_rests():
    # Lyrics on rests are not annotations (they don't survive conversion).
    score = make_score(lyrics=["a"], rest_lyric="a")
    assert strip_annotations(score) == 1
    rest = next(iter(score.recurse().getElementsByClass(note.Rest)))
    assert [lyric.text for lyric in rest.lyrics] == ["a"]


def test_strip_text_expressions_keeps_other_text_and_lyrics():
    score = make_score(
        lyrics=["Hal", "a"], texts=["a", "b'", "arco", "a2", "Allegro"]
    )
    removed = strip_annotations(score, lyrics_not_text=False)
    assert removed == 2
    assert sorted(text_contents(score)) == ["Allegro", "a2", "arco"]
    assert lyric_texts(score) == ["Hal", "a"]  # real lyrics untouched


def test_strip_text_expressions_requires_restrictions():
    with pytest.raises(ValueError):
        strip_annotations(
            make_score(texts=["a"]),
            lyrics_not_text=False,
            annotation_restrictions=None,
        )


# --- clean_kern ------------------------------------------------------------

def test_clean_kern_drops_only_volatile_software_lines():
    raw = (
        "!!!COM: Bach\r\n"
        "**kern\r\n"
        "4c\r\n"
        "*-\r\n"
        "!!!software: music21 v.9.1.0\r\n"
        "!!!software: MuseScore Studio 4.7.3\r\n"
        "!!!ONM: Op.1\r\n"
        "\r\n\r\n"
    )
    assert clean_kern(raw) == (
        "!!!COM: Bach\n**kern\n4c\n*-\n!!!ONM: Op.1\n"
    )


# --- corpus movements ------------------------------------------------------

# (stem relative to data/, annotations are lyrics?, restrictions)
# Smallest real movement of each convention. The conventions are those in
# scripts/build_corpus.py (`annotation_jobs`): Brandenburg uses the default,
# the B Minor Mass uses text expressions.
CORPUS_CASES = [
    pytest.param(
        "Bach,_Johann_Sebastian/Brandenburg_Concerto_No.3,_BWV.1048/2/Bach_BWV.1048_2",
        dict(lyrics_not_text=True),
        id="lyrics-Brandenburg3-2",
    ),
    pytest.param(
        "Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/22/Bach_BWV.232_22",
        dict(lyrics_not_text=False),
        id="text-BMinorMass-22",
    ),
]


@pytest.mark.parametrize("stem, kwargs", CORPUS_CASES)
def test_corpus_movement(stem, kwargs, tmp_path):
    mxl = DATA_PATH / f"{stem}.mxl"
    name = Path(stem).name

    out = derive_score(mxl, out_dir=tmp_path, **kwargs)

    # 1. Stripping agrees with extraction.
    n_rows = len(pd.read_csv(DATA_PATH / f"{stem}_annotations.csv"))
    assert out["removed"] == n_rows

    krn = out["krn"].read_text(encoding="utf-8")
    assert "!!!software" not in krn
    assert krn.endswith("\n") and "\r" not in krn

    # 2. Deterministic.
    (tmp_path / "again").mkdir()
    again = derive_score(mxl, out_dir=tmp_path / "again", **kwargs)
    assert again["krn"].read_text(encoding="utf-8") == krn

    # 3. Matches the golden file.
    golden = GOLDEN / f"{name}.krn"
    if UPDATE_GOLDEN:
        golden.write_text(krn, encoding="utf-8", newline="\n")
    assert golden.exists(), (
        f"No golden file {golden}; run UPDATE_GOLDEN=1 pytest tests/test_derive.py"
    )
    assert krn == golden.read_text(encoding="utf-8")


def test_plain_mxl_goes_to_out_dir_or_build_never_data(tmp_path, monkeypatch):
    import src.derive as derive

    stem = "Bach,_Johann_Sebastian/Brandenburg_Concerto_No.3,_BWV.1048/2/Bach_BWV.1048_2"
    mxl = DATA_PATH / f"{stem}.mxl"

    # Explicit out_dir: used as given, and no krn when not asked for.
    out = derive_score(mxl, out_dir=tmp_path, krn=False)
    assert out["plain_mxl"].parent == tmp_path
    assert "krn" not in out

    # Default: under build/plain/, mirroring the data layout, and not in data/
    # (several scripts glob data/ for *.mxl and would mistake a _plain.mxl
    # for a corpus score). BUILD_PATH is redirected so the test leaves
    # nothing behind in the repo.
    monkeypatch.setattr(derive, "BUILD_PATH", tmp_path / "build")
    default = derive.plain_mxl_path(mxl)
    assert default == (
        tmp_path / "build" / "plain" / Path(stem).parent / "Bach_BWV.1048_2_plain.mxl"
    )
    assert DATA_PATH.resolve() not in default.resolve().parents

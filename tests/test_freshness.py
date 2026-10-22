"""
Tests for the exists/staleness/overwrite rule (src/freshness.py) and for its
use in each step of the corpus build.

Run from the repo root with `pytest tests/`.

Modification times are always set explicitly (os.utime), never left to the
clock, so these tests don't depend on filesystem timestamp resolution.
"""
from __future__ import annotations

import os
import shutil
import stat
import sys
from pathlib import Path

import pytest

import src.utils
from src.annotations import get_annotations_and_melody_scores
from src.constants import DATA_PATH
from src.derive import derive_score
from src.freshness import needs_update, update_reason
from src.utils import musescore_convert

OLD, MID, NEW = 1_000_000_000, 1_100_000_000, 1_200_000_000  # seconds


def make(path: Path, mtime: int, text: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    os.utime(path, (mtime, mtime))
    return path


def mtime(path: Path) -> int:
    return path.stat().st_mtime_ns


# --- the rule itself -------------------------------------------------------

def test_missing_derived_is_built_in_stale_and_missing_modes(tmp_path):
    src_file = make(tmp_path / "a.mscz", MID)
    out = tmp_path / "a.mxl"
    assert update_reason(src_file, out, "stale") == "missing"
    assert update_reason(src_file, out, "missing") == "missing"
    assert update_reason(src_file, out, "always") == "forced"


def test_stale_means_source_strictly_newer(tmp_path):
    src_file = make(tmp_path / "a.mscz", MID)
    older = make(tmp_path / "older.mxl", OLD)
    same = make(tmp_path / "same.mxl", MID)
    newer = make(tmp_path / "newer.mxl", NEW)

    assert update_reason(src_file, older, "stale") == "stale"
    assert update_reason(src_file, same, "stale") is None   # equal: not stale
    assert update_reason(src_file, newer, "stale") is None


def test_missing_mode_never_replaces_an_existing_file(tmp_path):
    src_file = make(tmp_path / "a.mscz", NEW)
    old_output = make(tmp_path / "a.mxl", OLD)
    assert update_reason(src_file, old_output, "missing") is None
    assert update_reason(src_file, old_output, "always") == "forced"


def test_several_outputs_any_missing_builds_and_oldest_decides_staleness(tmp_path):
    src_file = make(tmp_path / "a.mxl", MID)
    fresh = make(tmp_path / "a_annotations.csv", NEW)
    stale = make(tmp_path / "a_melody.mxl", OLD)
    absent = tmp_path / "a_other.csv"

    assert update_reason(src_file, [fresh, stale], "stale") == "stale"
    assert update_reason(src_file, [fresh, absent], "missing") == "missing"
    assert update_reason(src_file, [fresh], "stale") is None


def test_several_sources_newest_decides_staleness(tmp_path):
    mxl = make(tmp_path / "a.mxl", OLD)
    mm = make(tmp_path / "a.mm.json", NEW)   # e.g. lightweight: needs both
    out = make(tmp_path / "a.csv", MID)
    assert update_reason([mxl, mm], out, "stale") == "stale"


def test_chain_cascades_through_modification_times(tmp_path):
    # mscz -> mxl -> csv. A newer mscz makes mxl stale; rebuilding the mxl
    # (writing it now) then makes csv stale.
    mscz = make(tmp_path / "a.mscz", NEW)
    mxl = make(tmp_path / "a.mxl", MID)
    csv = make(tmp_path / "a.csv", MID + 10)
    assert update_reason(mscz, mxl, "stale") == "stale"
    assert update_reason(mxl, csv, "stale") is None
    os.utime(mxl, (NEW + 10, NEW + 10))  # as if mxl had just been rebuilt
    assert update_reason(mxl, csv, "stale") == "stale"


def test_missing_source_is_an_error_not_a_skip(tmp_path):
    out = make(tmp_path / "a.mxl", MID)
    with pytest.raises(FileNotFoundError):
        update_reason(tmp_path / "nope.mscz", out, "stale")


def test_invalid_mode_rejected(tmp_path):
    src_file = make(tmp_path / "a.mscz", MID)
    with pytest.raises(ValueError):
        update_reason(src_file, tmp_path / "a.mxl", "sometimes")


def test_needs_update_reports_what_it_decides(tmp_path, capsys):
    src_file = make(tmp_path / "a.mscz", MID)
    fresh = make(tmp_path / "a.mxl", NEW)
    assert needs_update(src_file, fresh, "stale", label="a.mxl") is False
    assert "Up to date, skipping: a.mxl" in capsys.readouterr().out
    assert needs_update(src_file, tmp_path / "b.mxl", "stale", label="b.mxl")
    assert "Building (missing): b.mxl" in capsys.readouterr().out


# --- derive_score ----------------------------------------------------------

STEM = "Bach,_Johann_Sebastian/Brandenburg_Concerto_No.3,_BWV.1048/2/Bach_BWV.1048_2"


@pytest.fixture
def score(tmp_path):
    """A real (tiny) movement copied to a temp dir, dated MID."""
    dst = tmp_path / "score" / "Bach_BWV.1048_2.mxl"
    dst.parent.mkdir()
    shutil.copy(DATA_PATH / f"{STEM}.mxl", dst)
    os.utime(dst, (MID, MID))
    return dst


def test_derive_skips_everything_when_up_to_date_without_parsing(
    score, tmp_path, monkeypatch
):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    first = derive_score(score, out_dir=out_dir, overwrite="stale")
    assert first["removed"] == 1 and first["skipped"] == []
    krn, plain = first["krn"], first["plain_mxl"]
    before = (mtime(krn), mtime(plain))

    # Second run: nothing to do, so the score must not even be parsed.
    import src.derive as derive
    monkeypatch.setattr(
        derive.converter, "parse",
        lambda *a, **k: pytest.fail("score was parsed though up to date")
    )
    second = derive_score(score, out_dir=out_dir, overwrite="stale")
    assert second["removed"] is None
    assert sorted(second["skipped"]) == ["krn", "plain_mxl"]
    assert "krn" not in second and "plain_mxl" not in second
    assert (mtime(krn), mtime(plain)) == before


def test_derive_rewrites_only_the_stale_output(score, tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    out = derive_score(score, out_dir=out_dir)
    krn, plain = out["krn"], out["plain_mxl"]

    os.utime(krn, (OLD, OLD))            # krn now older than its source
    plain_before = mtime(plain)
    again = derive_score(score, out_dir=out_dir, overwrite="stale")

    assert list(k for k in ("krn", "plain_mxl") if k in again) == ["krn"]
    assert again["skipped"] == ["plain_mxl"]
    assert mtime(krn) > OLD * 10**9      # rewritten
    assert mtime(plain) == plain_before  # untouched


def test_derive_rebuilds_a_missing_output_even_in_missing_mode(score, tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    out = derive_score(score, out_dir=out_dir)
    out["plain_mxl"].unlink()
    krn_before = mtime(out["krn"])

    again = derive_score(score, out_dir=out_dir, overwrite="missing")
    assert "plain_mxl" in again and again["skipped"] == ["krn"]
    assert mtime(out["krn"]) == krn_before


def test_derive_missing_mode_ignores_staleness_always_does_not(score, tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    out = derive_score(score, out_dir=out_dir)
    os.utime(out["krn"], (OLD, OLD))
    os.utime(out["plain_mxl"], (OLD, OLD))

    kept = derive_score(score, out_dir=out_dir, overwrite="missing")
    assert sorted(kept["skipped"]) == ["krn", "plain_mxl"]
    assert mtime(out["krn"]) == OLD * 10**9

    forced = derive_score(score, out_dir=out_dir, overwrite="always")
    assert forced["skipped"] == [] and "krn" in forced and "plain_mxl" in forced
    assert mtime(out["krn"]) > OLD * 10**9


def test_derive_checking_does_not_create_the_build_directory(
    score, tmp_path, monkeypatch
):
    import src.derive as derive
    monkeypatch.setattr(derive, "BUILD_PATH", tmp_path / "build")
    derive_score(score, krn=True, plain_mxl=False, overwrite="stale")
    assert not (tmp_path / "build").exists()


# --- annotations batch -----------------------------------------------------

def test_annotations_batch_uses_overwrite_modes(score, tmp_path, monkeypatch):
    # get_corpus_files only allows paths inside DATA_PATH, so point it at tmp.
    monkeypatch.setattr(src.utils, "DATA_PATH", tmp_path)
    corpus = score.parent
    csv = corpus / "Bach_BWV.1048_2_annotations.csv"
    melody = corpus / "Bach_BWV.1048_2_melody.mxl"

    get_annotations_and_melody_scores(corpus, overwrite="stale")
    assert csv.exists() and melody.exists()
    before = (mtime(csv), mtime(melody))

    get_annotations_and_melody_scores(corpus, overwrite="stale")   # up to date
    assert (mtime(csv), mtime(melody)) == before

    os.utime(melody, (OLD, OLD))                                   # one stale
    get_annotations_and_melody_scores(corpus, overwrite="missing")
    assert mtime(melody) == OLD * 10**9                            # kept
    get_annotations_and_melody_scores(corpus, overwrite="stale")
    assert mtime(melody) > OLD * 10**9                             # rebuilt

    melody.unlink()                                                # one missing
    get_annotations_and_melody_scores(corpus, overwrite="missing")
    assert melody.exists()


def test_annotations_batch_ignores_derived_scores(score, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(src.utils, "DATA_PATH", tmp_path)
    shutil.copy(score, score.parent / "Bach_BWV.1048_2_plain.mxl")
    get_annotations_and_melody_scores(score.parent, overwrite="always")
    names = [line for line in capsys.readouterr().out.splitlines()
             if line.startswith("Score:")]
    assert names == ["Score: Bach_BWV.1048_2.mxl"]


# --- musescore_convert (with a fake MuseScore) -----------------------------

@pytest.mark.skipif(os.name == "nt", reason="fake executable is a shell script")
def test_musescore_convert_modes(tmp_path):
    fake = tmp_path / "fake_mscore"
    log = tmp_path / "calls.log"
    # Called as: fake -o <output> <input>
    fake.write_text(f'#!/bin/sh\necho "$3" >> "{log}"\ncp "$3" "$2"\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)

    corpus = tmp_path / "corpus"
    a = make(corpus / "a.mscz", MID, "a")
    b = make(corpus / "b.mscz", MID, "b")

    def run(mode):
        log.write_text("")
        musescore_convert(corpus, "mscz", "mxl", executable=str(fake), overwrite=mode)
        return sorted(Path(p).name for p in log.read_text().split())

    assert run("stale") == ["a.mscz", "b.mscz"]    # nothing exists yet
    assert run("stale") == []                       # all up to date

    os.utime(corpus / "a.mxl", (OLD, OLD))          # a's output is now stale
    assert run("missing") == []                     # never replaces
    assert run("stale") == ["a.mscz"]               # only the stale one
    assert run("always") == ["a.mscz", "b.mscz"]

    (corpus / "b.mxl").unlink()
    assert run("missing") == ["b.mscz"]


# --- build_corpus ----------------------------------------------------------

@pytest.fixture
def build_corpus():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    try:
        import build_corpus as bc
        yield bc
    finally:
        sys.path.pop(0)


def test_build_corpus_defaults_to_stale_and_rejects_bad_modes(build_corpus, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["build_corpus.py"])
    assert build_corpus.get_args().overwrite == "stale"
    monkeypatch.setattr(sys, "argv", ["build_corpus.py", "--overwrite", "always"])
    assert build_corpus.get_args().overwrite == "always"
    monkeypatch.setattr(sys, "argv", ["build_corpus.py", "--overwrite", "sometimes"])
    with pytest.raises(SystemExit):
        build_corpus.get_args()


def test_measure_maps_only_runs_ms3_on_stale_scores(build_corpus, tmp_path, monkeypatch):
    bc = build_corpus
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    # Stems chosen so one is a prefix of another, and one has regex characters.
    fresh = make(corpus / "Op.1_1.mscz", OLD)
    make(corpus / "Op.1_1.mm.json", MID)                 # up to date
    stale = make(corpus / "Op.1_10.mscz", NEW)
    make(corpus / "Op.1_10.mm.json", MID)                # stale
    absent = make(corpus / "Op.1_2.mscz", MID)           # no measure map

    monkeypatch.setattr(bc, "get_corpus_files", lambda *a, **k: [fresh, stale, absent])

    ms3_calls, processed = [], []

    def fake_run(cmd, **kwargs):
        ms3_calls.append(cmd)
        Path(".temp").mkdir(exist_ok=True)
        for f in (stale, absent):
            (Path(".temp") / f"{f.stem}.measures.tsv").write_text("")

    monkeypatch.setattr(bc.subprocess, "run", fake_run)
    monkeypatch.setattr(
        bc, "get_compressed_measure_map_given_measures",
        lambda mscz, tsv, verbose=False: processed.append(Path(mscz).name)
    )

    bc.get_corpus_measure_maps("stale")

    assert len(ms3_calls) == 1
    include = ms3_calls[0][ms3_calls[0].index("-i") + 1]
    import re
    assert re.search(include, "Op.1_10.mscz") and re.search(include, "Op.1_2.mscz")
    assert not re.search(include, "Op.1_1.mscz")    # prefix of a stale stem
    assert not re.search(include, "OpX1_10.mscz")   # '.' is escaped
    assert sorted(processed) == ["Op.1_10.mscz", "Op.1_2.mscz"]
    assert not (tmp_path / ".temp").exists()        # cleaned up


def test_measure_maps_skips_ms3_entirely_when_all_up_to_date(build_corpus, tmp_path, monkeypatch):
    bc = build_corpus
    monkeypatch.chdir(tmp_path)
    mscz = make(tmp_path / "Op.1_1.mscz", OLD)
    make(tmp_path / "Op.1_1.mm.json", MID)
    monkeypatch.setattr(bc, "get_corpus_files", lambda *a, **k: [mscz])
    monkeypatch.setattr(
        bc.subprocess, "run", lambda *a, **k: pytest.fail("ms3 ran though up to date")
    )
    bc.get_corpus_measure_maps("stale")


def test_lightweight_and_part_relations_stale_logic(build_corpus, tmp_path, monkeypatch):
    bc = build_corpus
    mscz = make(tmp_path / "Op.1_1.mscz", OLD)
    mxl = make(tmp_path / "Op.1_1.mxl", MID)
    mm = make(tmp_path / "Op.1_1.mm.json", MID)
    lw = make(tmp_path / "Op.1_1.csv", MID + 10)
    ann = make(tmp_path / "Op.1_1_annotations.csv", MID)
    rel = make(tmp_path / "Op.1_1_part_relations.csv", MID + 20)
    monkeypatch.setattr(bc, "get_corpus_files", lambda *a, **k: [mxl] if a == () and k.get("file_path") == "*.mxl" else [mscz])

    built = []
    monkeypatch.setattr(bc, "score_to_lightweight_df", lambda x, y: built.append("lw"))

    class Frame:
        def to_csv(self, path, index=False):
            built.append("rel")
    monkeypatch.setattr(bc, "get_part_relationship_summary", lambda *a: Frame())

    bc.get_corpus_lightweight_scores("stale")
    bc.get_corpus_part_relations("stale")
    assert built == []                                  # everything current

    os.utime(mm, (NEW, NEW))                            # measure map changed
    bc.get_corpus_lightweight_scores("stale")
    assert built == ["lw"]                              # lightweight is stale...
    bc.get_corpus_part_relations("stale")
    assert built == ["lw"]                              # ...but rel is judged on its own sources

    os.utime(ann, (NEW, NEW))                           # annotations changed
    bc.get_corpus_part_relations("stale")
    assert built == ["lw", "rel"]

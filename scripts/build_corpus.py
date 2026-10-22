"""
NAME
===============================
Build Corpus (build_corpus.py)


BY
===============================
Mark Gotham
Matthew Blessing


LICENCE:
===============================
Code = MIT. See [README](https://github.com/MarkGotham/Hauptstimme/tree/main#licence).


ABOUT:
===============================
Build the corpus from the .mscz files.

For each file:
- Convert to .mxl
- Get compressed measure map
- Get Hauptstimme annotations file and 'melody score'
- Get annotation-free .krn (and _plain.mxl under build/)
- Get lightweight score .csv

Then, create the rest of the metadata files from the finished
'sets.tsv' and 'composers.tsv' files.

Each derived file is only (re)built if needed, as set by `--overwrite`:
- stale (default): if it is missing, or a file it is made from is newer.
- missing: only if it is missing.
- always: regardless.
Modification times cannot see changes to code, the annotation conventions
in `annotation_jobs`, or tool versions, nor are they meaningful after a fresh
clone: use `--overwrite always` then. See `src/freshness.py`.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import os
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from pathlib import Path
from src.score_conversion import score_to_lightweight_df
from src.metadata import *
from src.utils import (
    musescore_convert, get_corpus_files, get_compressed_measure_map_given_measures
)
from src.annotations import get_annotations_and_melody_scores
from src.derive import derive_score
from src.freshness import OVERWRITE_MODES, needs_update
from src.part_relations import get_part_relationship_summary
from src.constants import DATA_PATH
from typing import cast, List


def get_corpus_measure_maps(overwrite: str = "always"):
    """
    Get compressed measure maps (.mm.json) for all scores in the corpus.

    Args:
        overwrite: "stale", "missing" or "always" (see `src/freshness.py`).
            Only scores that need a new measure map are passed to `ms3`.
    """
    mscz_files = cast(
        List[Path], get_corpus_files(file_path="*.mscz", pathlib=True)
    )
    todo = [
        f for f in mscz_files
        if needs_update(
            f, f.with_suffix(".mm.json"), overwrite, label=f"{f.stem}.mm.json"
        )
    ]
    if not todo:
        print("All measure maps are up to date.")
        return

    # Get measures info for the scores that need it.
    # (`-i` is a regex on file names, so limit ms3 to exactly these.)
    include = "^(?:" + "|".join(re.escape(f.stem) for f in todo) + r")\.mscz$"
    os.makedirs(".temp", exist_ok=True)
    subprocess.run(
        [
            "ms3", "extract", "-d", str(DATA_PATH), "-a", "-i", include,
            "-M", f"{os.getcwd()}/.temp", "-l", "c"
        ],
        check=False
    )

    # Remove '.measures' from all filenames
    for filename in os.listdir(".temp"):
        new_filename = filename.replace(".measures", "")
        old_file_path = os.path.join(".temp", filename)
        new_file_path = os.path.join(".temp", new_filename)

        # Rename the file
        os.rename(old_file_path, new_file_path)

    for mscz_file in todo:
        measures_file = f".temp/{mscz_file.with_suffix('.tsv').name}"
        get_compressed_measure_map_given_measures(
            mscz_file, measures_file, verbose=False
        )

    shutil.rmtree(".temp", ignore_errors=True)


def annotation_jobs():
    """
    The annotation conventions for each part of the corpus, as a list of
    (path, kwargs) pairs.

    kwargs are passed straight through to
    `get_annotations_and_melody_scores` and to `derive_score`, so omitting
    a key indicates use of the default:
    a single letter with an optional prime
    "[a-zA-Z]'?".

    Here we use that for most cases, including those known not to have the prime.
    Special cases are hard-corded with more flexible regex.

    One definition serves both extracting the annotations and stripping them
    to derive the annotation-free scores, so that the two always agree.
    """
    bach_path = DATA_PATH / "Bach,_Johann_Sebastian"
    beach_path = DATA_PATH / "Beach,_Amy"
    beethoven_path = DATA_PATH / "Beethoven,_Ludwig_van"
    boulanger_path = DATA_PATH / "Boulanger,_Lili"
    brahms_path = DATA_PATH / "Brahms,_Johannes"
    bruckner_path = DATA_PATH / "Bruckner,_Anton"
    haydn_path = DATA_PATH / "Haydn,_Franz"
    schubert_path = DATA_PATH / "Schubert,_Franz"

    TR_EXT = "([a-zA-Z]('+|!)?)|tr.?"  # Extended regex to include transition and more

    jobs = [
        (bach_path / "B_Minor_Mass,_BWV.232",
            dict(lyrics_not_text=False)),
        (bach_path / "Brandenburg_Concerto_No.3,_BWV.1048", {}),
        (bach_path / "Brandenburg_Concerto_No.4,_BWV.1049", {}),

        (beach_path, dict(
            annotation_restrictions=None # Unusually diverse annotations, and all/only lyrics.
        )),

        (beethoven_path / "Symphony_No.1,_Op.21", dict(
            annotation_restrictions= TR_EXT
        )),
        (beethoven_path / "Symphony_No.2,_Op.36", {}),
        (beethoven_path / "Symphony_No.3,_Op.55", {}),
        (beethoven_path / "Symphony_No.4,_Op.60", {}),
        (beethoven_path / "Symphony_No.5,_Op.67", {}),
        (beethoven_path / "Symphony_No.6,_Op.68", {}),
        (beethoven_path / "Symphony_No.7,_Op.92", {}),
        (beethoven_path / "Symphony_No.8,_Op.93", {}),
        (beethoven_path / "Symphony_No.9,_Op.125/1", {}),
        (beethoven_path / "Symphony_No.9,_Op.125/2", {}),
        (beethoven_path / "Symphony_No.9,_Op.125/3", {}),
        (beethoven_path / "Symphony_No.9,_Op.125/4", dict(
            lyrics_not_text=False, annotation_restrictions=TR_EXT
        )),

        (boulanger_path, {}),

        (brahms_path / "Symphony_No.1,_Op.68", {}),
        (brahms_path / "Symphony_No.2,_Op.73", {}),
        (brahms_path / "Symphony_No.3,_Op.90", {}),
        (brahms_path / "Symphony_No.4,_Op.98", {}),
        (brahms_path / "Ein_Deutsches_Requiem,_Op.45", dict(
            lyrics_not_text=False,
        )),

        (bruckner_path, {}),

        (haydn_path, {}),

        (schubert_path, {}),

    ]
    return jobs


def process_annotations_and_melody_scores(overwrite: str = "always"):
    """
    Get an annotation file and melody score for
    all scores in the corpus, using the conventions in `annotation_jobs`.

    Args:
        overwrite: "stale", "missing" or "always" (see `src/freshness.py`).
    """
    for path, kwargs in annotation_jobs():
        get_annotations_and_melody_scores(path, overwrite=overwrite, **kwargs)


def get_corpus_derived_scores(overwrite: str = "always"):
    """
    Derive the annotation-free scores for all scores in the corpus,
    using the conventions in `annotation_jobs`:
    - a .krn file next to each score (for clean diffs of the music),
    - a _plain.mxl file under build/plain/ (not in the data folder).

    Args:
        overwrite: "stale", "missing" or "always" (see `src/freshness.py`).
    """
    for path, kwargs in annotation_jobs():
        for mxl_file in get_corpus_files(path, file_path="*.mxl", pathlib=True):
            mxl_file = cast(Path, mxl_file)
            if mxl_file.name.endswith(("_melody.mxl", "_plain.mxl")):
                continue
            print("Deriving:", mxl_file.name)
            try:
                derive_score(mxl_file, overwrite=overwrite, **kwargs)
            except Exception as e:
                print(
                    "Warning: Failed to derive annotation-free scores for " +
                    f"'{mxl_file.name}' due to error: {e}"
                )


def get_corpus_lightweight_scores(overwrite: str = "always"):
    """
    Get a lightweight score file for every score in the corpus.

    Args:
        overwrite: "stale", "missing" or "always" (see `src/freshness.py`).
            A lightweight score is stale if its .mxl or measure map is newer.
    """
    mxl_files = get_corpus_files(file_path="*.mxl", pathlib=True)

    for mxl_file in mxl_files:
        mxl_file = cast(Path, mxl_file)
        if mxl_file.name.endswith(("_melody.mxl", "_plain.mxl")):
            continue
        mm_file = mxl_file.with_suffix(".mm.json")
        lw_file = mxl_file.with_suffix(".csv")
        if needs_update(
            [mxl_file, mm_file], lw_file, overwrite, label=lw_file.name
        ):
            score_to_lightweight_df(mxl_file, mm_file)


def get_corpus_part_relations(overwrite: str = "always"):
    """
    Get a part relationships summary for every score in the corpus.

    Args:
        overwrite: "stale", "missing" or "always" (see `src/freshness.py`).
            A summary is stale if its .mxl, lightweight score or annotations
            file is newer.
    """
    mscz_files = get_corpus_files(file_path="*.mscz", pathlib=True)

    for mscz_file in mscz_files:
        mscz_file = cast(Path, mscz_file)
        mxl_file = mscz_file.with_suffix(".mxl")
        lw_file = mscz_file.with_suffix(".csv")
        annotations_file = (
            mscz_file.parent / f"{mscz_file.stem}_annotations.csv"
        )
        csv_file = mscz_file.parent / f"{mscz_file.stem}_part_relations.csv"
        if not needs_update(
            [mxl_file, lw_file, annotations_file], csv_file, overwrite,
            label=csv_file.name
        ):
            continue
        df_summary = get_part_relationship_summary(
            mxl_file, lw_file, annotations_file
        )
        df_summary.to_csv(csv_file, index=False)


def get_corpus_alignment_tables():
    """
    Get an alignment file for every score in the corpus with at least 
    one public domain/open license recording on IMSLP.
    """
    # Imported here: aligning needs the `alignment` extra (synctoolbox etc.),
    # which the rest of the build does not.
    from src.alignment.score_audio_alignment import align_score_audios

    mscz_files = get_corpus_files(file_path="*.mscz", pathlib=True)
    audios = pd.read_csv(DATA_PATH / "audios.tsv", sep="\t")
    scores = pd.read_csv(DATA_PATH / "scores.tsv", sep="\t")

    for mscz_file in mscz_files:
        mscz_file = cast(Path, mscz_file)
        score_path = mscz_file.relative_to(DATA_PATH).parent.as_posix()
        score_info = scores[scores["path"] == score_path]
        score_audios = audios[audios["score_id"] == score_info["id"].item()]
        if not score_audios.empty:
            audio_files = []
            for _, audio in score_audios.iterrows():
                audio_file = [
                    audio["imslp_number"], audio["imslp_link"], None, None,
                    "full audio"
                ]
                audio_files.append(audio_file)
            mxl_file = mscz_file.with_suffix(".mxl")
            mm_file = mscz_file.with_suffix(".mm.json")
            align_score_audios(
                mxl_file, mm_file, audio_files, out_dir=mscz_file.parent
            )


def get_args():
    """
    Get the overwrite mode for the build.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Build the corpus: the files derived from each .mscz score " +
            "(.mxl, measure maps, annotations, melody scores, annotation-free " +
            ".krn, lightweight scores, part relations), then the audio " +
            "alignments and metadata."
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--overwrite",
        choices=OVERWRITE_MODES,
        default="stale",
        help=(
            "What to do with derived files that already exist.\n" +
            "  stale   (default): rebuild if missing, or if a source file is\n" +
            "          newer. A changed .mscz cascades down the chain.\n" +
            "  missing: only build what is missing; never replace.\n" +
            "  always: rebuild everything.\n" +
            "Use 'always' after changing code, annotation conventions or tool\n" +
            "versions, and after a fresh clone (git sets modification times to\n" +
            "checkout time, so 'stale' cannot be trusted). Applies to the\n" +
            "score-derived files, not the audio alignment and metadata steps."
        )
    )
    return parser.parse_args()


if __name__ == "__main__":
    overwrite = get_args().overwrite

    # Convert all scores to MusicXML files
    musescore_convert(DATA_PATH, "mscz", "mxl", overwrite=overwrite)

    # Get compressed measure maps
    get_corpus_measure_maps(overwrite)

    # Get annotations, and process melody scores, .csvs, part relationship summaries
    process_annotations_and_melody_scores(overwrite)
    get_corpus_derived_scores(overwrite)
    get_corpus_lightweight_scores(overwrite)
    get_corpus_part_relations(overwrite)

    # Audio:
    get_corpus_alignment_tables()
    user_region = "EU"
    create_audio_metadata(user_region)

    # Metadata:
    create_score_metadata()
    match_audios_to_scores()

    # NB: Manual cleanup for score names and audio-score matching required
    get_yaml_files()
    make_contents()

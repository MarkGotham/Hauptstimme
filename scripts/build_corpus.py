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
- Get lightweight score .csv

Then, create the rest of the metadata files from the finished
'sets.tsv' and 'composers.tsv' files.
"""
from __future__ import annotations

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
from src.part_relations import get_part_relationship_summary
from src.alignment.score_audio_alignment import align_score_audios
from src.constants import DATA_PATH
from typing import cast, List


def get_corpus_measure_maps():
    """
    Get compressed measure maps for all scores in the corpus.
    """
    # Get measures info for all scores
    os.makedirs(".temp", exist_ok=True)
    os.system(rf"ms3 extract -d '{DATA_PATH}' -a -i .*\.mscz -M " +
              f"'{os.getcwd()}/.temp' -l c")

    # Remove '.measures' from all filenames
    for filename in os.listdir(".temp"):
        new_filename = filename.replace(".measures", "")
        old_file_path = os.path.join(".temp", filename)
        new_file_path = os.path.join(".temp", new_filename)

        # Rename the file
        os.rename(old_file_path, new_file_path)

    mscz_files = get_corpus_files(file_path="*.mscz", pathlib=True)
    mscz_files = cast(List[Path], mscz_files)

    for mscz_file in mscz_files:
        measures_file = f".temp/{mscz_file.with_suffix('.tsv').name}"
        get_compressed_measure_map_given_measures(
            mscz_file, measures_file, verbose=False
        )

    os.system("rm -rf .temp")


def process_annotations_and_melody_scores():
    """
    Get an annotation file and melody score for
    all scores in the corpus.

    Compiles (path, kwargs) pairs per corpus.
    kwargs are passed straight through to `get_annotations_and_melody_scores`,
    so omitting key indicates use of the default:
    a single letter with an optional prime
    "[a-zA-Z]'?".

    Here we use that for most cases, including those known not to have the prime.
    Special cases are hard-corded with more flexible regex.
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

    for path, kwargs in jobs:
        get_annotations_and_melody_scores(path, **kwargs)


def get_corpus_lightweight_scores():
    """
    Get a lightweight score file for every score in the corpus.
    """
    mxl_files = get_corpus_files(file_path="*.mxl", pathlib=True)

    for mxl_file in mxl_files:
        mxl_file = cast(Path, mxl_file)
        if mxl_file.as_posix().endswith("_melody.mxl"):
            pass
        else:
            mm_file = mxl_file.with_suffix(".mm.json")
            score_to_lightweight_df(mxl_file, mm_file)


def get_corpus_part_relations():
    """
    Get a part relationships summary for every score in the corpus.
    """
    mscz_files = get_corpus_files(file_path="*.mscz", pathlib=True)

    for mscz_file in mscz_files:
        mscz_file = cast(Path, mscz_file)
        mxl_file = mscz_file.with_suffix(".mxl")
        lw_file = mscz_file.with_suffix(".csv")
        annotations_file = (
            mscz_file.parent / f"{mscz_file.stem}_annotations.csv"
        )
        df_summary = get_part_relationship_summary(
            mxl_file, lw_file, annotations_file
        )
        csv_file = mscz_file.parent / f"{mscz_file.stem}_part_relations.csv"
        df_summary.to_csv(csv_file, index=False)


def get_corpus_alignment_tables():
    """
    Get an alignment file for every score in the corpus with at least 
    one public domain/open license recording on IMSLP.
    """
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


if __name__ == "__main__":
    # Convert all scores to MusicXML files
    musescore_convert(DATA_PATH, "mscz", "mxl")

    # Get compressed measure maps
    get_corpus_measure_maps()

    # Get annotations, and process melody scores, .csvs, part relationship summaries
    process_annotations_and_melody_scores()
    get_corpus_lightweight_scores()
    get_corpus_part_relations()

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

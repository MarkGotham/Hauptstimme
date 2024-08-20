"""
NAME
===============================
Build Corpus (build_corpus.py)


BY
===============================
Matt Blessing, 2024


LICENCE:
===============================
Creative Commons Attribution-ShareAlike 4.0 International License
https://creativecommons.org/licenses/by-sa/4.0/


ABOUT:
===============================
Build the OpenScore Orchestra corpus from the .mscz files.

For each file:
- Convert to .mxl
- Get compressed measure map
- Get Hauptstimme annotations file and 'melody score'
- Get lightweight score .csv

Then, create the rest of the metadata files from the finished
'sets.tsv' and 'composers.tsv' files.
"""
import os
from hauptstimme.score_conversion import score_to_lightweight_df
from hauptstimme.metadata import *
from hauptstimme.utils import (
    ms3_convert, get_corpus_files, get_compressed_measure_map,
    get_compressed_measure_map_given_measures
)
from hauptstimme.annotations import get_annotations_and_melody_scores, get_annotations_and_melody_score
from hauptstimme.constants import CORPUS_PATH


def get_compressed_measure_maps():
    """
    Get a compressed measure map for every score in the corpus.
    """
    mscz_files = get_corpus_files(filename="*.mscz")

    for mscz_file in mscz_files:
        get_compressed_measure_map(mscz_file, verbose=False)


def get_corpus_measure_maps():
    """
    Get compressed measure maps for all scores in the corpus.
    """
    # Get measures info for all scores
    os.makedirs(".temp", exist_ok=True)
    os.system(rf"ms3 extract -d '{CORPUS_PATH}' -a -i .*\.mscz -M " +
              f"'{os.getcwd()}/.temp' -l c")

    # Remove '.measures' from all filenames
    for filename in os.listdir(".temp"):
        new_filename = filename.replace(".measures", "")
        old_file_path = os.path.join(".temp", filename)
        new_file_path = os.path.join(".temp", new_filename)

        # Rename the file
        os.rename(old_file_path, new_file_path)

    mscz_files = get_corpus_files(filename="*.mscz")

    for mscz_file in mscz_files:
        mscz_file_path = Path(mscz_file)
        measures_file = f".temp/{mscz_file_path.with_suffix('.tsv').name}"
        get_compressed_measure_map_given_measures(mscz_file, measures_file,
                                                  verbose=False)

    os.system("rm -rf .temp")


def get_lightweight_scores():
    """
    Get a lightweight score .csv for every score in the corpus.
    """
    mxl_files = get_corpus_files(filename="*.mxl")

    for mxl_file in mxl_files:
        score_to_lightweight_df(mxl_file)


if __name__ == "__main__":
    # Convert all scores to MusicXML files
    ms3_convert(CORPUS_PATH, "mscz", "mxl")

    # Get compressed measure maps
    get_corpus_measure_maps()

    # Get annotations file and melody score for all - NEED TO SORT SO ONES WITH LYRICS AND TEXT ARE SEPARATED!
    get_annotations_and_melody_scores(
        f"{CORPUS_PATH}/Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232",
        lyrics_not_text=False,
        annotation_restrictions="[a-zA-Z]"
    )
    get_annotations_and_melody_scores(
        f"{CORPUS_PATH}/Bach,_Johann_Sebastian/Brandenburg_Concerto_No.3,_BWV.1048"
    )
    get_annotations_and_melody_scores(
        f"{CORPUS_PATH}/Bach,_Johann_Sebastian/Brandenburg_Concerto_No.4,_BWV.1049"
    )
    get_annotations_and_melody_scores(
        f"{CORPUS_PATH}/Beach,_Amy",
        annotation_restrictions=r"([a-zA-Z]([a-zA-Z]|('+|!))?)|([a-zA-Z]\+[a-zA-Z])|cad\.|trans"
    )
    get_annotations_and_melody_scores(
        f"{CORPUS_PATH}/Beethoven,_Ludwig_van",
        annotation_restrictions="([a-zA-Z]('+|!)?)|tr.?"
    )
    get_annotations_and_melody_score(
        f"{CORPUS_PATH}/Beethoven,_Ludwig_van/Symphony_No.9,_Op.125/4/Beethoven_Op.125_4.mxl",
        lyrics_not_text=False,
        annotation_restrictions=["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
                                 "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z", "tr", "tr.", "c'"]
    )
    get_annotations_and_melody_scores(
        f"{CORPUS_PATH}/Brahms,_Johannes",
        annotation_restrictions="[a-zA-Z]'?"
    )
    get_annotations_and_melody_scores(
        f"{CORPUS_PATH}/Brahms,_Johannes/Ein_Deutsches_Requiem,_Op.45",
        lyrics_not_text=False,
        annotation_restrictions="[a-zA-Z]'?"
    )
    get_annotations_and_melody_scores(
        f"{CORPUS_PATH}/Bruckner,_Anton",
        annotation_restrictions="[a-zA-Z]'?"
    )

    # Get lightweight csv?
    get_lightweight_scores()

    # Get alignment table?

    user_region = "EU"
    create_audio_metadata(user_region)
    create_score_metadata()
    match_audios_to_scores()
    get_yaml_files()
    make_contents()
    # What will be needed here is to sort the ID column of each metadata file
    # And manual cleanup for score names and audio-score matching

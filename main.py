"""
NAME
===============================
Main - Get Score Files (main.py)


BY
===============================
Matt Blessing, 2024


LICENCE:
===============================
Creative Commons Attribution-ShareAlike 4.0 International License
https://creativecommons.org/licenses/by-sa/4.0/


ABOUT:
===============================
Given a score's .mscz file:
- Convert to .mxl
- Get compressed measure map
- Get Hauptstimme annotations file and 'melody score'
- Get lightweight score .csv
"""
import argparse
from hauptstimme.annotations import get_annotations_and_melody_score
from hauptstimme.constants import CORPUS_PATH

if __name__ == "__main__":

    # parser = argparse.ArgumentParser()

    # parser.add_argument("--path_to_score", type=str,
    #                     required=False,
    #                     help="Path to a score.")

    # args = parser.parse_args()
    # if args.process_one_score:
    #     process_one(path_to_score=CORPUS_PATH / args.path_to_score)
    # else:
    #     parser.print_help()
    # get_annotations_and_melody_score(
    #     f"{CORPUS_PATH}/Beethoven,_Ludwig_van/Symphony_No.2,_Op.36/1/Beethoven_Op.36_1.mxl")
    # get_annotations_and_melody_score(
    #     f"{CORPUS_PATH}/Beach,_Amy/Symphony_in_E_minor_(Gaelic),_Op.32/4/Beach_Op.32_4.mxl")
    get_annotations_and_melody_score(
        f"{CORPUS_PATH}/Brahms,_Johannes/Symphony_No.4,_Op.98/1/Brahms_Op.98_1.mxl")

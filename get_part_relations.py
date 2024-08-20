"""
NAME
===============================
Get Part Relations (get_part_relations.py)


BY
===============================
Matt Blessing, 2024


LICENCE:
===============================
Creative Commons Attribution-ShareAlike 4.0 International License
https://creativecommons.org/licenses/by-sa/4.0/


ABOUT:
===============================
This script produces a part relationship summary for a score, which
compares each instrument part to the 'main' melody part as well as
each other in each Hauptstimme annotation block.

It requires the .mxl file for a score.
"""
import argparse
from pathlib import Path
from hauptstimme.part_relations import get_part_relationship_summary
from hauptstimme.annotations import get_annotations_and_melody_score
from hauptstimme.score_conversion import score_to_lightweight_df


def get_args():
    """
    Get the lightweight .csv file and Hauptstimme annotations file for 
    the score passed from the command line.

    Returns:
        score_lw (str): The score's lightweight .csv file path.
        score_annotations (str): The score's Hauptstimme annotations 
            file path.

    Raises:
        ValueError: If the score file argument is not a .mxl file.
        ValueError: If the score file doesn't exist.
    """
    parser = argparse.ArgumentParser(
        description=("Produce a part relations summary for a score."),
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "score",
        help=("The relative path to the score's MusicXML file (.mxl).")
    )

    args = parser.parse_args()

    score_file = args.score
    score_file_path = Path(score_file)
    if score_file_path.suffix == ".mxl":
        if score_file_path.exists():
            score_lw_path = score_file_path.with_suffix(".csv")
            score_lw = score_lw_path.as_posix()
            if not score_lw_path.exists():
                print("Warning: The provided score has no lightweight .csv.")
                print("Creating lightweight .csv...")
                score_to_lightweight_df(score_file)
            score_annotations_path = (score_file_path.parent /
                                      (f"{score_file_path.stem}" +
                                       "_annotations.csv"))
            score_annotations = score_annotations_path.as_posix()
            if not score_annotations_path.exists():
                print("Warning: The provided score has no Hauptstimme " +
                      "annotations file.")
                print("Creating annotations file...")
                try:
                    get_annotations_and_melody_score(score_file)
                except:
                    get_annotations_and_melody_score(score_file,
                                                     lyrics_not_text=False)
        else:
            raise ValueError(
                "The provided score file does not exist.")
    else:
        raise ValueError(
            "The score file provided requires a .mxl extension.")

    return score_lw, score_annotations


if __name__ == "__main__":
    score_lw, score_annotations = get_args()

    # Get part relations summary
    df_summary = get_part_relationship_summary(score_lw, score_annotations)

    # Save as .csv file
    csv_file = f"{Path(score_lw).stem}_part_relations.csv"
    df_summary.to_csv(csv_file, index=False)

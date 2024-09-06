"""
NAME
===============================
Main (main.py)


BY
===============================
Matthew Blessing


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
- Get lightweight score file
- Get part relationships summary
"""
from __future__ import annotations

import argparse
from pathlib import Path
from hauptstimme.annotations import get_annotations_and_melody_score
from hauptstimme.score_conversion import score_to_lightweight_df
from hauptstimme.part_relations import get_part_relationship_summary
from hauptstimme.utils import ms3_convert, get_compressed_measure_map


def get_args():
    """
    Get the .mxl file, compressed measure map, Hauptstimme annotations
    file, melody score, and lightweight score file for a particular
    score.

    Returns:
        score_file_path (pathlib.Path): The score's MuseScore file
            path.
        out_dir (str): The path to the directory in which to save these
            files.
        annotation_restrictions (str|list): Restrictions for the 
            Hauptstimme annotations. If none, the default restrictions 
            will apply.
        text (bool): Whether the annotations are text expressions or 
            not.

    Raises:
        ValueError: If the score file argument is not a .mscz file.
        ValueError: If the score file doesn't exist.
        ValueError: If the output directory doesn't exist.
    """
    parser = argparse.ArgumentParser(
        description=("Obtain a score's .mxl file, compressed measure map, " +
                     "haupstimme annotations file, melody score, and " +
                     "lightweight score file."),
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "score",
        help="The path to the score's MuseScore file (.mscz)."
    )
    parser.add_argument(
        "-o",
        "--out",
        help=("The path to the directory in which to save the " +
              "score files.")
    )
    parser.add_argument(
        "-r",
        "--restr",
        help=("The annotation restrictions - either a regex string or list " +
              "of acceptable values. If no value provided, the default " +
              "value is used.")
    )
    parser.add_argument(
        "-t",
        "--text",
        action="store_true",
        help=("A boolean flag for if the Hauptstimme annotations are text " +
              "expressions.")
    )

    args = parser.parse_args()

    score_file = args.score
    score_file_path = Path(score_file)
    if score_file_path.suffix == ".mscz":
        if not score_file_path.exists():
            raise ValueError(
                "Error: The provided score file does not exist.")
    else:
        raise ValueError(
            "Error: The score file provided requires a .mscz extension.")

    if args.out:
        out_dir_path = Path(args.out)
        if out_dir_path.exists():
            out_dir = out_dir_path.as_posix()
        else:
            raise ValueError("Error: The output directory does not exist.")
    else:
        out_dir = None

    annotation_restrictions = args.restr
    text = args.text

    return score_file_path, out_dir, annotation_restrictions, text


if __name__ == "__main__":
    score_path, out_dir, annotation_restrictions, text = get_args()
    score_mxl = score_path.with_suffix(".mxl")
    # Get .mxl file
    ms3_convert(score_path.parent, "mscz", "mxl", score_path.stem)

    # Get measure map
    score_mm = get_compressed_measure_map(score_path)

    # Get annotations file and melody score
    if annotation_restrictions is None:
        get_annotations_and_melody_score(
            score_mxl, out_dir, not (text)
        )
    else:
        get_annotations_and_melody_score(
            score_mxl, out_dir, not (text), annotation_restrictions
        )

    # Get lightweight score file
    score_lw_df = score_to_lightweight_df(score_mxl, score_mm)

    # Get part relationships summary
    score_lw = score_path.with_suffix(".csv")
    score_annotations = (
        score_path.parent / f"{score_path.stem}_annotations.csv"
    )
    score_summary_df = get_part_relationship_summary(
        score_mxl, score_lw, score_annotations
    )
    score_summary_df.to_csv(
        score_path.parent / f"{score_path.stem}_part_relations.csv",
        index=False
    )

"""
NAME
===============================
Get Part Relations (get_part_relations.py)


BY
===============================
Matthew Blessing


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
from __future__ import annotations

import argparse
from pathlib import Path
from hauptstimme.part_relations import get_part_relationship_summary
from hauptstimme.annotations import get_annotations_and_melody_score
from hauptstimme.score_conversion import score_to_lightweight_df
from hauptstimme.utils import validate_path, get_compressed_measure_map
from typing import Tuple


def get_args() -> Tuple[Path, Path, Path]:
    """
    Get the lightweight .csv file and Hauptstimme annotations file for 
    the score passed from the command line.

    Returns:
        score_file: The score's MusicXML file path.
        score_lw: The score's lightweight .csv file path.
        score_annotations: The score's Hauptstimme annotations 
            file path.

    Raises:
        ValueError: If the score file argument is not a .mxl file.
        ValueError: If the score does not have an identically named
            MuseScore file.
    """
    parser = argparse.ArgumentParser(
        description="Produce a part relations summary for a score.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "score",
        help=("The path to the score's MusicXML file (.mxl). The score " +
              "must also have a MuseScore (.mscz) file.")
    )

    args = parser.parse_args()

    score_file = validate_path(args.score)
    if score_file.suffix == ".mxl":
        # Get lightweight score file
        score_lw = score_file.with_suffix(".csv")
        if not score_lw.exists():
            print("Warning: The provided score has no lightweight .csv.")
            print("Creating lightweight .csv...")
            score_mm = score_file.with_suffix(".mm.json")
            if not score_mm.exists():
                score_mscz = score_file.with_suffix(".mscz")
                if not score_mm.exists():
                    raise ValueError(
                        "Error: Score's .mscz file could not be found."
                    )
                get_compressed_measure_map(score_mscz)
            score_to_lightweight_df(score_file, score_mm)
        # Get annotations file
        score_annotations = (
            score_file.parent / f"{score_file.stem}_annotations.csv"
        )
        if not score_annotations.exists():
            print("Warning: The provided score has no Hauptstimme " +
                  "annotations file.")
            print("Creating annotations file...")
            try:
                get_annotations_and_melody_score(score_file)
            except:
                get_annotations_and_melody_score(
                    score_file, lyrics_not_text=False
                )
    else:
        raise ValueError(
            "Error: The score file provided requires a .mxl extension."
        )

    return score_file, score_lw, score_annotations


if __name__ == "__main__":
    score_mxl, score_lw, score_annotations = get_args()

    # Get part relations summary
    df_summary = get_part_relationship_summary(
        score_mxl, score_lw, score_annotations
    )

    # Save as .csv file
    csv_file = f"{score_mxl.stem}_part_relations.csv"
    df_summary.to_csv(csv_file, index=False)

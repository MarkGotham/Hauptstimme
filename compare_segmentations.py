"""
NAME
===============================
Compare Segmentations (compare_segmentations.py)


BY
===============================
Matthew Blessing


LICENCE:
===============================
Creative Commons Attribution-ShareAlike 4.0 International License
https://creativecommons.org/licenses/by-sa/4.0/


ABOUT:
===============================
This script compares automatic segmentation points to the Hauptstimme
points to see how well they align. The automatic segmentation points
include changepoint detection-based segmentation points and 
novelty-based segmentation points using tempogram and chromagram 
features.

It requires the .mxl file for a score.
"""
from __future__ import annotations

import librosa
import argparse
from pathlib import Path
from hauptstimme.score_conversion import score_to_lightweight_df
from hauptstimme.annotations import get_annotations_and_melody_score
from hauptstimme.segmentation import *
from hauptstimme.utils import get_compressed_measure_map, validate_path
from hauptstimme.constants import SAMPLE_RATE
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
        description=("Compare the Hauptstimme annotations as segmentation " +
                     "points to novelty-based segmentation points and " +
                     "changepoint detection segmentation points obtained" +
                     "from synthetic audio for a particular score."),
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "score",
        help=("The path to the score's MusicXML file (.mxl). The score " +
              "must also have an identically named MuseScore (.mscz) file.")
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

    # Generate synthetic score audio
    score_audio = score_mxl.with_suffix(".mp3")
    if not score_audio.exists():
        print("Computing score audio...")
        score_audio = get_score_audio(score_mxl)

    # Load the audio
    audio, _ = librosa.load(score_audio.as_posix())
    audio = audio[:120*SAMPLE_RATE]
    print("\nScore audio successfully loaded.")

    # Get lightweight score data frame
    score_lw = score_mxl.with_suffix(".csv")
    if not score_lw.exists():
        print("\nComputing score's lightweight .csv file...")
        score_mm = score_mxl.with_suffix(".mm.json")
        if not score_mm.exists():
            score_mscz = score_mxl.with_suffix(".mscz")
            if not score_mm.exists():
                raise ValueError(
                    "Error: Score's .mscz file could not be found."
                )
            get_compressed_measure_map(score_mscz)
        score_to_lightweight_df(score_mxl, score_mm)

    tau = 4             # Tolerance of 1 second
    round_to = 0.25
    haupt_seg_pts = get_hauptstimme_segmentation_points(
        score_lw, score_annotations, tstamp=True
    )
    haupt_seg_pts_vec = get_seg_pts_vec(haupt_seg_pts, round_to, 120)

    # Obtain novelty-based, tempogram-based segmentation points
    nb_seg_pts = novelty_based_segmentation(audio, plot=True)
    print("\nNovelty-based, tempogram-based segmentation completed.")
    nb_seg_pts_vec = get_seg_pts_vec(nb_seg_pts, round_to, 120)

    # Plot the Haupt-Novelty comparison
    P, R, F, _, _, _, _, _ = evaluate_seg_pts(
        haupt_seg_pts_vec, nb_seg_pts_vec, tau
    )
    print("\nHauptstimme points compared to novelty-based, tempogram-based" +
          " segmentation points:")
    print("P = %0.3f;  R = %0.3f;  F = %0.3f" % (P, R, F))
    fig, ax = plot_seg_pts_eval(
        haupt_seg_pts_vec, nb_seg_pts_vec, tau, round_to,
        other_seg_pts="Novelty-based, tempogram-based"
    )

    # Obtain novelty-based, chromagram-based segmentation points
    nb_seg_pts = novelty_based_segmentation(audio, "chromagram")
    print("\nNovelty-based, chromagram-based segmentation completed.")
    nb_seg_pts_vec = get_seg_pts_vec(nb_seg_pts, round_to, 120)

    # Plot the Haupt-Novelty comparison
    P, R, F, _, _, _, _, _ = evaluate_seg_pts(
        haupt_seg_pts_vec, nb_seg_pts_vec, tau
    )
    print(
        "\nHauptstimme points compared to novelty-based, chromagram-based " +
        "segmentation points:"
    )
    print("P = %0.3f;  R = %0.3f;  F = %0.3f" % (P, R, F))

    fig, ax = plot_seg_pts_eval(
        haupt_seg_pts_vec, nb_seg_pts_vec, tau, round_to,
        other_seg_pts="Novelty-based, chromagram-based"
    )

    # Obtain changepoint detection segmentation points
    cd_seg_pts = changepoint_segmentation(audio)
    print("\nChangepoint detection segmentation completed.")
    cd_seg_pts_vec = get_seg_pts_vec(cd_seg_pts, round_to, 120)

    # Plot the Haupt-Changepoint comparison
    P, R, F, _, _, _, _, _ = evaluate_seg_pts(
        haupt_seg_pts_vec, cd_seg_pts_vec, tau
    )
    print("\nHauptstimme points compared to changepoint detection-based" +
          " segmentation points:")
    print("P = %0.3f;  R = %0.3f;  F = %0.3f" % (P, R, F))
    fig, ax = plot_seg_pts_eval(
        haupt_seg_pts_vec, cd_seg_pts_vec, tau, round_to,
        other_seg_pts="Changepoint detection"
    )

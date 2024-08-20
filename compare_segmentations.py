"""
NAME
===============================
Compare Segmentations (compare_segmentations.py)


BY
===============================
Matt Blessing, 2024


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
import librosa
import argparse
from pathlib import Path
from hauptstimme.score_conversion import score_to_lightweight_df
from hauptstimme.annotations import get_annotations_and_melody_score
from hauptstimme.segmentation import *
from hauptstimme.constants import SAMPLE_RATE


def get_args():
    """
    Get the score file passed from the command line and the score's
    Hauptstimme annotations file.

    Returns:
        score_file (str): The score's MusicXML file path.
        score_annotations (str): The score's Hauptstimme annotations 
            file path.

    Raises:
        ValueError: If the score file argument is not a .mxl file.
        ValueError: If the score file doesn't exist.
    """
    parser = argparse.ArgumentParser(
        description=("Compare the Hauptstimme annotations as segmentation " +
                     "points to novelty-based segmentation points and " +
                     "changepoint detection segmentation points obtained" +
                     "from synthetic audio for a particular score."),
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "score",
        help=("The relative path to the score's MusicXML file.")
    )

    args = parser.parse_args()

    score_file = args.score
    score_file_path = Path(score_file)
    if score_file_path.suffix == ".mxl":
        if score_file_path.exists():
            score_annotations_path = (score_file_path.parent /
                                      f"{score_file_path.stem}_annotations.csv")
            if not score_annotations_path.exists():
                print("Warning: The provided score has no Hauptstimme " +
                      "annotations file.")
                print("Creating annotations file...")
                try:
                    get_annotations_and_melody_score(score_file)
                except:
                    get_annotations_and_melody_score(score_file,
                                                     lyrics_not_text=False)
            score_annotations = score_annotations_path.as_posix()
        else:
            raise ValueError(
                "Error: The provided score file does not exist.")
    else:
        raise ValueError(
            "Error: The score file provided requires a .mxl extension.")

    return score_file, score_annotations


if __name__ == "__main__":
    score_file, score_annotations = get_args()
    score_path = Path(score_file)

    # Generate synthetic score audio
    score_audio_path = score_path.with_suffix(".mp3")
    score_audio = score_audio_path.as_posix()
    if not score_audio_path.exists():
        print("Computing score audio...")
        score_audio = get_score_audio(score_file)

    # Load the audio
    audio, _ = librosa.load(score_audio)
    audio = audio[:120*SAMPLE_RATE]
    print("\nScore audio successfully loaded.")

    # Get lightweight score data frame
    score_lw_path = score_path.with_suffix(".csv")
    score_lw = score_lw_path.as_posix()
    if not score_lw_path.exists():
        print("\nComputing score's lightweight .csv file...")
        score_to_lightweight_df(score_file)

    tau = 4             # Tolerance of 1 seconds
    round_to = 0.25
    haupt_seg_pts = get_hauptstimme_segmentation_points(score_lw,
                                                        score_annotations,
                                                        tstamp=True)
    haupt_seg_pts_vec = get_seg_pts_vec(haupt_seg_pts, round_to, 120)

    # Obtain novelty-based, tempogram-based segmentation points
    nb_seg_pts = novelty_based_segmentation(audio, plot=True)
    print("\nNovelty-based, tempogram-based segmentation completed.")
    nb_seg_pts_vec = get_seg_pts_vec(nb_seg_pts, round_to, 120)

    # Plot the Haupt-Novelty comparison
    P, R, F, _, _, _, _, _ = evaluate_seg_pts(haupt_seg_pts_vec,
                                              nb_seg_pts_vec, tau)
    print("\nHauptstimme points compared to novelty-based, tempogram-based" +
          " segmentation points:")
    print("P = %0.3f;  R = %0.3f;  F = %0.3f" % (P, R, F))
    fig, ax = plot_seg_pts_eval(haupt_seg_pts_vec, nb_seg_pts_vec, tau,
                                round_to,
                                title=f"Beethoven Symphony 2, Movement 1",
                                other_seg_pts=f"Novelty-based, tempogram-based")

    # Obtain novelty-based, chromagram-based segmentation points
    nb_seg_pts = novelty_based_segmentation(audio, "chromagram")
    print("\nNovelty-based, chromagram-based segmentation completed.")
    nb_seg_pts_vec = get_seg_pts_vec(nb_seg_pts, round_to, 120)

    # Plot the Haupt-Novelty comparison
    P, R, F, _, _, _, _, _ = evaluate_seg_pts(haupt_seg_pts_vec,
                                              nb_seg_pts_vec, tau)
    print("\nHauptstimme points compared to novelty-based, chromagram-based" +
          " segmentation points:")
    print("P = %0.3f;  R = %0.3f;  F = %0.3f" % (P, R, F))

    fig, ax = plot_seg_pts_eval(haupt_seg_pts_vec, nb_seg_pts_vec, tau,
                                round_to,
                                title=f"Brahms Symphony 4, Movement 1",
                                other_seg_pts=f"Novelty-based, chromagram-based")

    # Obtain changepoint detection segmentation points
    cd_seg_pts = changepoint_segmentation(audio)
    print("\nChangepoint detection segmentation completed.")
    cd_seg_pts_vec = get_seg_pts_vec(cd_seg_pts, round_to, 120)

    # Plot the Haupt-Changepoint comparison
    P, R, F, _, _, _, _, _ = evaluate_seg_pts(haupt_seg_pts_vec,
                                              cd_seg_pts_vec, tau)
    print("\nHauptstimme points compared to changepoint detection-based" +
          " segmentation points:")
    print("P = %0.3f;  R = %0.3f;  F = %0.3f" % (P, R, F))
    fig, ax = plot_seg_pts_eval(haupt_seg_pts_vec, cd_seg_pts_vec, tau,
                                round_to,
                                title=f"Beethoven Symphony 2, Movement 1",
                                other_seg_pts=f"Changepoint detection")

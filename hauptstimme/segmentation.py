"""
NAME
===============================
Segmentation (segmentation.py)


BY
===============================
James Hui
Matthew Blessing


LICENCE:
===============================
Creative Commons Attribution-ShareAlike 4.0 International License
https://creativecommons.org/licenses/by-sa/4.0/


ABOUT:
===============================
Functions relating to the comparison of automatic segmentation of 
synthetic score audio and segmentation using Hauptstimme annotations.

References:
- M. Müller, "Chapter 4: Music Structure Analysis", in 
    Fundamentals of Music Processing - Using Python and Jupyter 
    Notebooks, 2nd ed., Springer Verlag, 2021.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import librosa
import ruptures as rpt
import libfmp.b
import libfmp.c3
import libfmp.c4
from pathlib import Path
from scipy import signal
from math import ceil
from matplotlib.colors import ListedColormap
from matplotlib.figure import Figure
from hauptstimme.utils import ms3_convert, validate_path
from hauptstimme.constants import SAMPLE_RATE
from hauptstimme.types import Scalar
from typing import cast, Tuple, Union, List, Optional


def ssm_from_audio(
    x: np.ndarray,
    L: int = 21,
    H: int = 5,
    L_smooth: int = 16,
    tempo_rel_set: np.ndarray = np.array([1]),
    shift_set: np.ndarray = np.array([0]),
    strategy: str = "relative",
    scale: bool = True,
    thresh: float = 0.15,
    penalty: float = 0.0,
    binarize: bool = False,
    features: str = "tempogram",
    plot: bool = False
) -> Tuple[np.ndarray, Scalar]:
    """
    Compute a self-similarity matrix for an audio file.

    Args:
        x: An audio signal.
        L: Length of smoothing filter. Default = 21.
        H: Downsampling factor. Default = 5.
        L_smooth: Length of filter. Default = 16.
        tempo_rel_set: Set of relative tempo values. Default = 
            np.array([1]).
        shift_set: Set of shift indices. Default = np.array([0]).
        strategy: Thresholding strategy. Default = 'relative'.
        scale: Whether to scale positive values to range [0, 1].
            Default = True.
        thresh: Threshold. Default = 0.15.
        penalty: Set values below threshold to value specified. Default
            = 0.0.
        binarize: Whether to binarize final matrix (set positive value 
            to 1 and otherwise 0). Default = False.
        features: Which feature representation to use to compute the 
            SSM (either 'chromagram' or 'tempogram'). Default = 
            'tempogram'.
        plot: Whether to plot the SSM or not.

    Returns:
        S: The self-similarity matrix.
        Fs_feature: The feature rate.

    References:
        This code was adapted from the FMP Chapter 4 SSM: Thresholding
        notebook available at: https://www.audiolabs-erlangen.de/FMP.
    """
    if features == "chromagram":
        C = librosa.feature.chroma_stft(
            y=x, sr=SAMPLE_RATE, tuning=0, norm=2,
            hop_length=2205, n_fft=4410
        )
    else:
        oenv = librosa.onset.onset_strength(
            y=x, sr=SAMPLE_RATE, hop_length=2205
        )
        C = librosa.feature.tempogram(
            onset_envelope=oenv, sr=SAMPLE_RATE, hop_length=2205
        )
    Fs_C = SAMPLE_RATE / 2205

    X, Fs_feature = libfmp.c3.smooth_downsample_feature_sequence(
        C, Fs_C, filt_len=L, down_sampling=H
    )
    X = libfmp.c3.normalize_feature_sequence(X, norm="2", threshold=0.001)

    # Compute SSM
    S, _ = libfmp.c4.compute_sm_ti(
        X, X, L=L_smooth, tempo_rel_set=tempo_rel_set,
        shift_set=shift_set, direction=2
    )
    S = libfmp.c4.threshold_matrix(
        S, thresh=thresh, strategy=strategy, scale=scale,
        penalty=penalty, binarize=binarize
    )

    if plot:
        cmap = libfmp.b.compressed_gray_cmap(alpha=-10)
        libfmp.b.plot_matrix(
            S, cmap=cmap, title="", ylabel="Time (seconds)",
            colorbar=True, figsize=(4, 3.4)
        )

    return S, Fs_feature


def novelty_based_segmentation(
    audio: np.ndarray,
    features: str = "tempogram",
    plot: bool = False
) -> np.ndarray:
    """
    Obtain a set of novelty-based segmentation points (timestamps in
    seconds) for an audio file.

    Args:
        audio: An audio signal.
        features: Which feature representation to use to compute the 
            SSM (either 'chromagram' or 'tempogram'). Default = 
            'tempogram'.
        plot: Whether to plot the SSM and novelty function or not.

    Returns:
        seg_pts: The novelty-based segmentation points in seconds.
    """
    # Get SSM
    S, Fs_feature = ssm_from_audio(
        audio, L=81, H=10, L_smooth=1,
        thresh=1, features=features, plot=plot
    )

    # Compute novelty function from SSM
    L_kernel = 5
    nov = libfmp.c4.compute_novelty_ssm(S, L=L_kernel, exclude=True)

    # Find indices of peaks in the novelty function
    peaks = signal.find_peaks(nov)[0]

    # Convert peak indices to seconds
    seg_pts = peaks / Fs_feature

    if plot:
        libfmp.b.plot_signal(
            nov, int(Fs_feature), figsize=(8, 2), color="k",
            title="Novelty Function"
        )
        plt.vlines(
            seg_pts, 0, 1.1, color="r", linestyle=":", linewidth=1
        )
        plt.show()

    return seg_pts


def changepoint_segmentation(
    audio: np.ndarray,
    target_duration: Scalar = 10
) -> np.ndarray:
    """
    Obtain a set of change points (timestamps in seconds) for an audio 
    file.

    Args:
        audio: An audio signal.
        target_duration: The target duration of each segment in 
            seconds.

    Returns:
        change_pts: The change points in seconds.
    """
    # Compute the onset strength
    hop_length_tempo = 256
    oenv = librosa.onset.onset_strength(
        y=audio, sr=SAMPLE_RATE, hop_length=hop_length_tempo
    )

    # Compute the tempogram
    tempogram = librosa.feature.tempogram(
        onset_envelope=oenv,
        sr=SAMPLE_RATE,
        hop_length=hop_length_tempo,
    )

    algo = rpt.KernelCPD(kernel="linear").fit(tempogram.T)

    # Calculate number of change points to have based on target segment
    # duration
    signal_duration = len(audio) / SAMPLE_RATE
    num_change_pts = int(signal_duration / target_duration)

    # Estimate the change points
    change_pts = cast(List[int], algo.predict(n_bkps=num_change_pts))

    # Convert the estimated change points from indices to seconds
    change_pts = librosa.frames_to_time(
        change_pts, sr=SAMPLE_RATE, hop_length=hop_length_tempo
    )

    return change_pts


def get_hauptstimme_segmentation_points(
    score_lw: Union[str, Path],
    score_annotations: Union[str, Path],
    tstamp: bool = False
) -> List[float]:
    """
    Get the timestamps (in quarter notes or seconds) for each 
    Hauptstimme annotation, which can be viewed as segmentation points.

    Args:
        score_lw: The path to the lightweight data frame for a 
            particular score.
        score_annotations: The path to the Hauptstimme annotations file
            for the score.
        tstamp: Whether the timestamps should be in seconds or not. 
            Default = False.

    Returns:
        seg_pts: The Hauptstimme segmentation points. 
    """
    score_lw = validate_path(score_lw)
    score_annotations = validate_path(score_annotations)

    df_score_lw = pd.read_csv(score_lw)
    df_annotations = pd.read_csv(score_annotations)

    df_annotations.rename(columns={"qstamp": "score_qstamp"}, inplace=True)
    df_merged = df_score_lw.merge(df_annotations, on=["measure", "beat"])

    if tstamp:
        seg_pts = df_merged["tstamp"].sort_values().to_list()
    else:
        seg_pts = df_merged["qstamp"].sort_values().to_list()

    return seg_pts


def get_score_audio(
    score_file: Union[str, Path],
    out_dir=None
) -> Path:
    """
    Obtain synthetic audio for a score.

    Args:
        score_file: The path to the score's MuseScore or MusicXML file.
        out_dir : The path to the directory in which the audio will be
            saved. Default = None.

    Return:
        score_audio: The path to the score audio.
    """
    score_file = validate_path(score_file)

    if out_dir is None:
        out_dir = score_file.parent
    else:
        out_dir = validate_path(out_dir, dir=True)

    ext = score_file.suffix[1:]
    ms3_convert(
        score_file.parent, ext, "mp3", score_file.stem, out_dir=out_dir
    )

    score_audio = out_dir / f"{score_file.stem}.mp3"

    return score_audio


def compute_prf(
    num_tp: int,
    num_fn: int,
    num_fp: int
) -> Tuple[float, float, float]:
    """
    Compute the precision P, recall R, and F-score F given the number
    of TP, FN, and FP.

    Args:
        num_tp: Number of true positives.
        num_fn: Number of false negatives.
        num_fp: Number of false positives.

    Returns:
        P: Precision.
        R: Recall.
        F: F-score.

    References:
        This code was adapted from the FMP Chapter 4 Evaluation
        notebook available at: https://www.audiolabs-erlangen.de/FMP.
    """
    P = num_tp / (num_tp + num_fp)
    R = num_tp / (num_tp + num_fn)

    if (P + R) > 0:
        F = 2*P*R / (P + R)
    else:
        F = 0

    return P, R, F


def evaluate_seg_pts(
    seg_pts_ref: np.ndarray,
    seg_pts: np.ndarray,
    tau: int
) -> Tuple[float, float, float, int, int, int, np.ndarray, np.ndarray]:
    """
    Compute evaluation measures for two sets of segmentation points.

    Args:
        seg_pts_ref: A binary vector for the reference segmentation 
            points.
        seg_pts: A binary vector for the estimated segmentation points.
        tau: The tolerance parameter, where |s_{k+1} - s_k| > 2*tau for
            all k in both sets of segmentation points.

    Returns:
        P: Precision.
        R: Recall.
        F: F-score.
        num_tp: Number of true positives.
        num_fn: Number of false negatives.
        num_fp: Number of false positives.
        seg_pts_ref_tol: An array for the reference segmentation points
            with the tolerance added.
        seg_pts_eval: An array indicating the TPs, FNs, and FPs.

    References:
        This code was adapted from the FMP Chapter 4 Evaluation
        notebook available at: https://www.audiolabs-erlangen.de/FMP.
    """
    N = len(seg_pts_ref)
    num_tp = 0
    num_fn = 0
    num_fp = 0
    seg_pts_ref_tol = np.zeros((np.array([seg_pts_ref])).shape)
    seg_pts_eval = np.zeros((np.array([seg_pts_ref])).shape)

    for n in range(N):
        # Get tolerance range in reference segmentation point array
        min_match_index = max(0, n - tau)
        max_match_index = min(N - 1, n + tau)

        # If a reference segmentation point
        if seg_pts_ref[n] == 1:
            # Set values in tolerance range = 1
            seg_pts_ref_tol[:, min_match_index:max_match_index+1] = 1
            # Set segmentation point value = 2
            seg_pts_ref_tol[:, n] = 2
            # Determine TPs and FNs
            temp = int(sum(seg_pts[min_match_index:max_match_index+1]))
            if temp > 0:
                num_tp += temp
            else:
                num_fn += 1
                seg_pts_eval[:, n] = 2

        # If an estimated segmentation point
        if seg_pts[n] == 1:
            # Determine TPs and FPs
            if sum(seg_pts_ref[min_match_index:max_match_index+1]) == 0:
                num_fp += 1
                seg_pts_eval[:, n] = 1
            else:
                seg_pts_eval[:, n] = 3

    # Ensure that no segmentation points are covered up by the
    # tolerance regions
    for n in range(N):
        # If a reference segmentation point
        if seg_pts_ref[n] == 1:
            # Set segmentation point value = 2
            seg_pts_ref_tol[:, n] = 2

    P, R, F = compute_prf(num_tp, num_fn, num_fp)

    return P, R, F, num_tp, num_fn, num_fp, seg_pts_ref_tol, seg_pts_eval


def plot_seg_pts_eval(
    haupt_seg_pts: np.ndarray,
    seg_pts: np.ndarray,
    tau: int,
    round_to: Scalar,
    figsize: Tuple[Scalar, Scalar] = (8, 3),
    title: str = "",
    other_seg_pts: str = ""
) -> Tuple[Figure, np.ndarray]:
    """
    Plot the reference segmentation points with tolerance regions, the 
    estimated segmentation points, and the evaluation.

    Args:
        haupt_seg_pts: A binary vector for the Hauptstimme segmentation
            points.
        seg_pts: A binary vector for the automatedsegmentation points.
        tau: The tolerance parameter. For Hauptstimme segmentation 
            point at index i, we search for estimated segmentation 
            point matches in the index range i ± tau.
        round_to: The time in seconds between each vector index.
        figsize: The size of the figure. A tuple containing 2 floats. 
            Default = (8, 3).
        title: A title for the whole figure.
        other_seg_pts: The type of automated segmentation points (e.g.,
            'Novelty-based').

    Returns:
        fig: The plot figure.
        ax: The plot axis.

    References:
        This code was adapted from the FMP Chapter 4 Evaluation
        notebook available at: https://www.audiolabs-erlangen.de/FMP.
    """
    # Perform evaluation
    eval = evaluate_seg_pts(haupt_seg_pts, seg_pts, tau)
    haupt_seg_pts_tol, seg_pts_eval = eval[-2:]

    # Define figure
    fig, ax = plt.subplots(
        3,
        2,
        figsize=figsize,
        gridspec_kw={
            "width_ratios": [1, 0.02],
            "wspace": 0.02,
            "height_ratios": [1.5, 1, 2]
        },
        constrained_layout=True
    )

    fig.suptitle(title, fontsize=18)

    start_index = 0
    end_index = len(haupt_seg_pts)

    # Get color maps
    color_list = ["white", "grey", "black", "red", "blue", "green"]
    # Haupt has 3 colors: white, grey, black
    haupt_cmap = ListedColormap(color_list[:3])
    # Automated has 2 colors: white, black
    auto_cmap = ListedColormap([color_list[0], color_list[2]])
    # Evaluation has 4 colors: white, red, blue, green
    eval_cmap = ListedColormap([color_list[0]] + color_list[3:])

    # Plot Hauptstimme segmentation points
    im = ax[0, 0].imshow(
        haupt_seg_pts_tol, cmap=haupt_cmap, interpolation="nearest",
        aspect="auto"
    )
    ax[0, 0].set_title(
        f"Hauptstimme segmentation points (with tolerance ±{tau*round_to} " +
        "secs)",
        fontsize=12
    )
    im.set_clim(vmin=-0.5, vmax=2.5)
    ax[0, 0].set_xticks([])
    ax[0, 0].set_yticks([])

    # Plot color bar
    ax_cb = plt.colorbar(im, cax=ax[0, 1])
    ax_cb.set_ticks(np.arange(0, 3, 1))
    ax_cb.set_ticklabels(
        ["", "Tolerance Region", "Segmentation Pt."], fontsize=10
    )

    # Plot automated segmentation points
    im = ax[1, 0].imshow(
        np.array([seg_pts]), cmap=auto_cmap,
        interpolation="nearest", aspect="auto"
    )
    ax[1, 0].set_title(f"{other_seg_pts} segmentation points", fontsize=12)
    im.set_clim(vmin=-0.5, vmax=1.5)
    ax[1, 0].set_xticks([])
    ax[1, 0].set_yticks([])

    # Plot color bar
    ax_cb = plt.colorbar(im, cax=ax[1, 1])
    ax_cb.set_ticks(np.arange(0, 2, 1))
    ax_cb.set_ticklabels(["", "Segmentation Pt."], fontsize=10)

    # Plot evaluation
    im = ax[2, 0].imshow(
        seg_pts_eval, cmap=eval_cmap,
        interpolation="nearest", aspect="auto"
    )
    ax[2, 0].set_title("Evaluation", fontsize=12)
    im.set_clim(vmin=-0.5, vmax=3.5)
    xticks = np.linspace(start_index, end_index - 1, 11)
    ax[2, 0].set_xticks(xticks, [x*round_to for x in xticks])
    ax[2, 0].set_yticks([])
    ax[2, 0].set_xlabel("Time (secs)")

    # Plot color bar
    ax_cb = plt.colorbar(im, cax=ax[2, 1])
    ax_cb.set_ticks(np.arange(0, 4, 1))
    ax_cb.set_ticklabels(["", "FP", "FN", "TP"], fontsize=10)

    plt.show()

    return fig, ax


def get_seg_pts_vec(
    seg_pts: Union[List[float], np.ndarray],
    round_to: Scalar,
    max_tstamp: Optional[Scalar] = None
) -> np.ndarray:
    """
    Get a binary vector for a set of segmentation points rounded to
    `round_to` seconds up to a given maximum time.

    Args:
        seg_pts: An array of segmentation point timestamps.
        round_to: A number of seconds to round each segmentation point 
            to.
        max_tstamp: A maximum timestamp to include segmentationpoints 
            up until. Default = None.

    Returns:
        seg_pts_vec: The binary segmentation points vector.
    """
    if max_tstamp is None:
        max_tstamp = seg_pts[-1]
    max_tstamp = cast(Scalar, max_tstamp)

    # Round all segmentation points
    seg_pts = np.unique(seg_pts)
    seg_pts_rounded = np.round(seg_pts/round_to) * round_to

    # Round `max_tstamp` to nearest 10
    max_tstamp_rounded = ceil(max_tstamp/10) * 10
    # Get all timestamps
    all_tstamps = np.arange(0, max_tstamp_rounded + round_to, round_to)

    # Create a binary vector indicating where the segmentation points
    # are
    seg_pts_vec = np.zeros_like(all_tstamps)
    for pt in seg_pts_rounded:
        if pt < max_tstamp_rounded:
            seg_pts_vec[int(pt/round_to)] = 1

    return seg_pts_vec

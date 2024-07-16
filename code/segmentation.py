from music21 import *
import matplotlib.pyplot as plt
import librosa
import numpy as np
from IPython.display import Audio, display
import ruptures as rpt
import pandas as pd
from matplotlib.cbook import boxplot_stats
import libfmp
from scipy import signal as sig
from scipy.ndimage import filters, median_filter, gaussian_filter1d
import libfmp.c6
import libfmp.c4
import os
from convert_csv import convert_mxml_to_csv
from utils import *
# from SSM import *


def fig_ax(figsize=(15, 5), dpi=150):
    """Return a (matplotlib) figure and ax objects with given size."""
    return plt.subplots(figsize=figsize, dpi=dpi)


def get_sum_of_cost(algo, n_bkps):
    """Return the sum of costs for the change points `bkps`"""
    bkps = algo.predict(n_bkps=n_bkps)
    return algo.cost.sum_of_costs(bkps)


def plot_function_peak_positions(nov, Fs_nov, peaks, title='', figsize=(8,2)):
    peaks_sec = peaks/Fs_nov
    fig, ax, line = libfmp.b.plot_signal(nov, Fs_nov, figsize=figsize, color='k', title=title)
    plt.vlines(peaks_sec, 0, 1.1, color='r', linestyle=':', linewidth=1)



def fmp_novelty_segment(signal, Fs=22050):
    """
    Given audio signal, return segmentation points in time (seconds) from beginning
    """
    x, x_duration, X, Fs_X, S, I = compute_sm_from_audio(signal, Fs=Fs, L=81, H=10, L_smooth=1, thresh=1)
    L_kernel = 5  # smaller kernel size --> finer novelty function, more noise --> shorter segments
    nov = libfmp.c4.compute_novelty_ssm(S, L=L_kernel, exclude=True)

    peaks = sig.find_peaks(nov)[0]  # find peaks in novelty function in seconds


    # title = 'Scipy peak picking (Fs=%3.0f) for long segment from %ds to %ds ' % (Fs_X, start, end)
    # plot_function_peak_positions(nov, Fs_X, peaks, title)
    # plt.show()

    return peaks


def ruptures_changepoint_segment(signal, Fs, target_duration=10):
    """
    Given audio signal, return segmentation points in time (seconds) from beginning

    Args:
        signal: audio signal
        Fs: sampling rate
        target_duration: target duration of each segment in seconds
    """

    # Compute the onset strength
    hop_length_tempo = 256
    oenv = librosa.onset.onset_strength(
        y=signal, sr=Fs, hop_length=hop_length_tempo
    )
    # Compute the tempogram
    tempogram = librosa.feature.tempogram(
        onset_envelope=oenv,
        sr=Fs,
        hop_length=hop_length_tempo,
    )
    algo = rpt.KernelCPD(kernel="linear").fit(tempogram.T)

    signal_duration = len(signal) / Fs
    # calc number of breakpoints based on segment duration target
    n_bkps_max = int(signal_duration / target_duration)

    _ = algo.predict(n_bkps=n_bkps_max)
    bkps = algo.predict(n_bkps=n_bkps_max)
    # Convert the estimated change points (frame counts) to actual timestamps
    bkps_times = librosa.frames_to_time(bkps, sr=Fs, hop_length=hop_length_tempo)

    return bkps_times




"""
Sample usage:
Get rough structure of the piece using ruptures changepoint detection (according to tempogram)
get fine segmentation points in each rough segment using FMP novelty function
"""
if __name__ == "__main__":
    audiofile_path = REPO_PATH / "test" / "ms3_test" / "outputs" / "score.mp3"
    s, Fs = librosa.load(audiofile_path)
    peaks = fmp_novelty_segment(s, Fs=Fs)
    print('Points from FMP Novelty Segmentation:')
    print(peaks)
    peaks = ruptures_changepoint_segment(s, Fs, target_duration=10)
    print('Points from Ruptures Changepoint-detection Segmentation:')
    print(peaks)



    
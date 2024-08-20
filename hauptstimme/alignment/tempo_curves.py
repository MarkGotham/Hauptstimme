"""
NAME
===============================
Tempo Curves (tempo_curves.py)


BY
===============================
Matt Blessing, 2024


LICENCE:
===============================
Creative Commons Attribution-ShareAlike 4.0 International License
https://creativecommons.org/licenses/by-sa/4.0/


ABOUT:
===============================
Functions for computing and plotting tempo curves of audio recordings
aligned to a score.

`get_tempo_curve` computes a tempo curve given a set of qstamps and a
corresponding set of tstamps in an audio recording.

`alignment_table_to_tempo_curves` computes a tempo curve for every
audio recording in an alignment table.

`plot_tempo_curve` plots a tempo curve.

`plot_alignment_table_tempo_curves` plots the tempo curves for a set of
audio recordings in an alignment table on the same axes.

References:
- M. Müller, "Section 3.3.2. Application: Tempo Curves", in 
	Fundamentals of Music Processing - Using Python and Jupyter 
    Notebooks, 2nd ed., Springer Verlag, 2021.
"""
import numpy as np
import matplotlib.pyplot as plt
from scipy import signal, ndimage
from matplotlib.ticker import ScalarFormatter
from hauptstimme.constants import FEATURE_RATE


def get_tempo_curve(qstamps, tstamps, window_len=4):
    """
    Given a set of symbolic quarter note timestamps in a score and the 
    corresponding set of timestamps in an audio recording, compute the 
    tempo at each timestamp in the audio recording.

    Args:
        qstamps (array like): A set of symbolic quarter note timestamps
            in the score (in ascending order)
        tstamps (array like): A set of timestamps in the audio 
            recording.
        window_len (int): The length of the window used to smooth the 
            tempo curve (in seconds). Default = 4.

    Returns:
        tempos_smooth (np.array): The tempo at each timestamp in the 
            audio recording.
    """
    # Compute the tempos
    qstamps_diff = np.diff(qstamps)
    tstamps_diff = np.diff(tstamps)
    tempos = qstamps_diff / tstamps_diff * 60

    # Smooth the tempo curve
    filter_len = int(window_len * FEATURE_RATE)
    filter_window = signal.windows.hann(filter_len)  # Hann window
    filter_window /= np.sum(filter_window)
    tempos_smooth = ndimage.convolve(tempos, filter_window)
    tempos_smooth = np.append(tempos_smooth, tempos_smooth[[-1]])

    return tempos_smooth


def alignment_table_to_tempo_curves(df_alignment):
    """
    Given an alignment table for a score and a set of audio files, 
    compute a tempo curve for each audio file.

    Args:
        df_alignment (pd.DataFrame): An alignment table.

    Returns:
        tempo_curves (list): A list containing the tempo curve data for
            each audio file.
    """
    tempo_curves = []

    qstamps = df_alignment["qstamp"].to_numpy()

    # Audio timestamp columns are from the 5th column onwards
    for audio in df_alignment.columns[4:]:
        tempos = get_tempo_curve(qstamps, df_alignment[audio].to_numpy())
        tempo_curves.append(tempos)

    return tempo_curves


def plot_tempo_curve(time_axis, tempo_curve, ax=None, figsize=(8, 3),
                     logscale=False, xlabel="Time (quarter notes)",
                     ylabel="Tempo (quarter notes per minute)", xlim=None,
                     ylim=None, label=""):
    """
    Plot a tempo curve.

    Args:
        time_axis (array like): The time axis for the tempo curve 
            (could be timestamps in quarter notes or seconds).
        tempo_curve (array like): The tempo curve data.
        ax (plt.axis): If given, will plot onto the axis, otherwise 
            will plot as a new figure. Default = None.
        figsize (tuple): The size of the figure. A tuple containing 2
            integers. Default = (8, 3).
        logscale (bool): Whether to use a logarithmic tempo axis.
            Default = False.
        xlabel (str): The x-axis label. Default = 'Time (quarter 
            notes)'.
        ylabel (str): The y-axis label. Default = 'Tempo (quarter 
            notes per minute)'.
        xlim (list): The x-axis limits specified as a list of 2 floats.
            Default = None.
        ylim (list): The y-axis limits specified as a list of 2 floats.
            Default = None.
        label (str): A label to identify the tempo curve. Default = ''.

    Returns:
        fig (matplotlib.figure): The tempo curve figure.
        ax (plt.axis): The tempo curve axis.

    References:
        This code was adapted from the FMP Chapter 3 Tempo Curves 
        notebook available at: https://www.audiolabs-erlangen.de/FMP.
    """
    fig = None

    if ax is None:
        fig = plt.figure(figsize=figsize)
        ax = plt.subplot(1, 1, 1)

    ax.plot(time_axis, tempo_curve, label=label)
    ax.set_title("Tempo curve")

    if xlim is None:
        # If no x limits given, update them based on the data
        xlim = list(ax.get_xlim())
        time_axis = list(time_axis)
        time_lower = time_axis[0]
        time_upper = time_axis[-1]
        if time_lower < xlim[0]:
            xlim[0] = time_lower
        if time_upper > xlim[1]:
            xlim[1] = time_upper
    if ylim is None:
        # If no y limits given, update them based on the data
        ylim = list(ax.get_ylim())
        tempo_lower = np.min(tempo_curve) * 0.9
        tempo_upper = np.max(tempo_curve) * 1.1
        if tempo_lower < ylim[0]:
            ylim[0] = tempo_lower
        if tempo_upper > ylim[1]:
            ylim[1] = tempo_upper

    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    ax.grid(True, which="both")

    if logscale:
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(ScalarFormatter())
        ax.yaxis.set_minor_formatter(ScalarFormatter())

    return fig, ax


def plot_alignment_table_tempo_curves(
    df_alignment, tempo_curves, time_axis="qstamp", figsize=(8, 3),
    logscale=False, xlabel="Time (quarter notes)",
    ylabel="Tempo (quarter notes per minute)", xlim=None, ylim=None,
    ignore_if_larger=None
):
    """
    Plot (on the same axis) the tempo curves for a set of audio 
    recordings of the same score. 

    Args:
        pd.DataFrame df_alignment (pd.DataFrame): An alignment table.
        tempo_curves (list): A list containing the tempo curve data for
                each audio file.
        time_axis (str): A string indicating whether to have the time 
            axis in quarter notes or seconds. Either 'qstamp' or 
            'tstamp'. Default = 'qstamp'.
        figsize (tuple): The size of the figure. A tuple containing 2
            integers. Default = (8, 3).
        logscale (bool): Whether to use a logarithmic tempo axis.
            Default = False.
        xlabel (str): The x-axis label. Default = 'Time (quarter 
            notes)'. Should be changed if `time_axis` = 'tstamp'.
        ylabel (str): The y-axis label. Default = 'Tempo (quarter 
            notes per minute)'. Should be changed if `time_axis` = 
            'tstamp'.
        xlim (list): The x-axis limits specified as a list of 2 floats.
            Default = None.
        ylim (list): The y-axis limits specified as a list of 2 floats.
            Default = None.
        ignore_if_larger (float): If a recording contains a tempo value
            larger than this number, the tempo curve will be ignored.
            Primary use is to ignore audio recordings with extremely
            large tempo values due to missing repeats.

    Returns:
        fig (matplotlib.figure): The tempo curve figure.
        ax (plt.axis): The tempo curve axis.
    """
    fig, ax = plt.subplots(1, 1, figsize=figsize)
    ax.set_xlim([0, 1])

    if ignore_if_larger is None:
        # Set `ignore_if_larger` = the maximum tempo + 1
        ignore_if_larger = 0
        for tempos in tempo_curves:
            if ignore_if_larger < max(tempos):
                ignore_if_larger = max(tempos) + 1

    # Audio timestamp columns are from the 5th column onwards
    for i, audio in enumerate(df_alignment.columns[4:]):
        if time_axis == "tstamp":
            time_axis_values = df_alignment[audio]
        else:
            time_axis_values = df_alignment["qstamp"]

        tempos = tempo_curves[i]
        if (tempos > ignore_if_larger).any():
            print(
                f"Warning: recording '{audio.replace('_tstamp', '')}' has",
                "been excluded as it contains at least one tempo value",
                f"greater than {ignore_if_larger}.")
        else:
            plot_tempo_curve(time_axis_values, tempos, ax=ax,
                             logscale=logscale, xlabel=xlabel, ylabel=ylabel,
                             xlim=xlim, ylim=ylim,
                             label=audio.replace("_tstamp", ""))

    fig.legend(
        title="Audio recording",
        bbox_to_anchor=(1.22, 1),
        bbox_transform=ax.transAxes
    )

    return fig, ax

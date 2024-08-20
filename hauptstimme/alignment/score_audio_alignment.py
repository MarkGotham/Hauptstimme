"""
NAME
===============================
Score-Audio Alignment (score_audio_alignment.py)


BY
===============================
Matt Blessing, 2024


LICENCE:
===============================
Creative Commons Attribution-ShareAlike 4.0 International License
https://creativecommons.org/licenses/by-sa/4.0/


ABOUT:
===============================
Functions for aligning a set of audio recordings to a score.

`get_features_from_audio` and `get_features_from_score` compute the 
quantized chroma features and DLNCO features for an audio file and a
score data frame, respectively.

`align_score_audio` aligns an audio file to a score, obtaining 
corresponding timestamp pairs in the two sources.

`align_score_audios` aligns a set of audio files to a score, obtaining
an alignment table containing, for each note event:
- Quarter note timestamps `score_qstamp` and `qstamp`
- Measure and beat number
- Timestamps in seconds in each audio file

`align_hauptstimme_annotations` merges a Hauptstimme annotations.csv 
file with an alignment table, obtaining a timestamp in each audio file
for each annotation.

`alignment_table_to_measure_timestamps` obtains a set of timestamps 
approximating the start of each measure in an audio file.

References:
- M. Müller et al., Sync Toolbox: A Python Package for Efficient, 
    Robust, and Accurate Music Synchronization, Journal of Open Source 
    Software (JOSS), 6(64), 2021.
- M. R. H. Gotham et al., The 'Measure Map': an inter-operable standard
    for aligning symbolic music, In Proc. of the 10th Int. Conf. on 
    Digital Libraries for Musicology, Milan, Italy, 2023, pp. 91-99.
"""
import pandas as pd
import numpy as np
import librosa
import re
from pathlib import Path
from scipy import interpolate
from music21 import converter
from synctoolbox.dtw.mrmsdtw import sync_via_mrmsdtw
from synctoolbox.dtw.utils import (
    compute_optimal_chroma_shift,
    shift_chroma_vectors,
    make_path_strictly_monotonic
)
from synctoolbox.feature.csv_tools import (
    df_to_pitch_features,
    df_to_pitch_onset_features
)
from synctoolbox.feature.chroma import (
    pitch_to_chroma,
    quantize_chroma,
    quantized_chroma_to_CENS
)
from synctoolbox.feature.dlnco import pitch_onset_features_to_DLNCO
from synctoolbox.feature.pitch import audio_to_pitch_features
from synctoolbox.feature.pitch_onset import audio_to_pitch_onset_features
from synctoolbox.feature.utils import estimate_tuning
from hauptstimme.alignment.scraping import load_audio_from_url
from hauptstimme.score_conversion import score_measure_map_to_df
from hauptstimme.constants import (
    SAMPLE_RATE, FEATURE_RATE, STEP_WEIGHTS, THRESHOLD_REC, ROUNDING_VALUE
)


def get_features_from_audio(audio, tuning_offset):
    """
    Compute quantized chroma and DLNCO features for an audio file.

    Args:
        audio (np.ndarray): An audio file.
        tuning_offset (int): The estimated tuning deviation for the 
            audio file.

    Returns:
        f_chroma_quantized (np.ndarray): The quantized chroma features.
        f_DLNCO (np.ndarray): The DLNCO features.

    References:
        This code was adapted from the Sync Toolbox Audio-Score 
        Synchronization Demo available at:
        https://github.com/meinardmueller/synctoolbox/blob/master/sync_audio_score_full.ipynb.
    """
    f_pitch = audio_to_pitch_features(f_audio=audio,
                                      Fs=SAMPLE_RATE,
                                      tuning_offset=tuning_offset,
                                      feature_rate=FEATURE_RATE)
    f_chroma = pitch_to_chroma(f_pitch=f_pitch)
    f_chroma_quantized = quantize_chroma(f_chroma=f_chroma)

    f_pitch_onset = audio_to_pitch_onset_features(f_audio=audio,
                                                  Fs=SAMPLE_RATE,
                                                  tuning_offset=tuning_offset)
    print()  # To deal with the use of print(..., end="") in above func
    f_DLNCO = pitch_onset_features_to_DLNCO(
        f_peaks=f_pitch_onset,
        feature_rate=FEATURE_RATE,
        feature_sequence_length=f_chroma_quantized.shape[1]
    )

    return f_chroma_quantized, f_DLNCO


def get_features_from_score(df_score):
    """
    Compute quantized chroma and DLNCO features for a data frame 
    containing all note events in a score.

    Args:
        df_score (pd.DataFrame): A data frame of note events in a 
            score.
    Returns:
        f_chroma_quantized (np.ndarray): The quantized chroma features.
        f_DLNCO (np.ndarray): The DLNCO features.

    References:
        This code was adapted from the Sync Toolbox Audio-Score 
        Synchronization Demo available at:
        https://github.com/meinardmueller/synctoolbox/blob/master/sync_audio_score_full.ipynb.
    """
    f_pitch = df_to_pitch_features(df_score, feature_rate=FEATURE_RATE)
    f_chroma = pitch_to_chroma(f_pitch=f_pitch)
    f_chroma_quantized = quantize_chroma(f_chroma=f_chroma)

    f_pitch_onset = df_to_pitch_onset_features(df_score)
    f_DLNCO = pitch_onset_features_to_DLNCO(
        f_peaks=f_pitch_onset,
        feature_rate=FEATURE_RATE,
        feature_sequence_length=f_chroma_quantized.shape[1]
    )

    return f_chroma_quantized, f_DLNCO


def align_score_audio(df_score, audio_file):
    """    
    Produce a data frame containing the timestamps corresponding to 
    note onset positions in the score and audio, which can used to 
    build an alignment table.

    Args:
        df_score (pd.DataFrame): A data frame containing info for all
            note events in the score.
            Columns:
                start (float): The note's time offset in seconds with
                    repeats expanded (equivalent to 'tstamp').
                duration (float): The note's duration in seconds.                
                pitch (int): The note's MIDI note number.
                velocity (float): The note's velocity.
                instrument (str): The name of the instrument playing
                    the note.
        list audio_file: A list containing:
            audio_id (str): An identifier for the audio file.
            audio_filename (str): Its local filename or URL.
            A time range to extract from the audio file for alignment, 
                specified by:
                start (datetime.time): A start timestamp.
                end (datetime.time): An end timestamp.
            desc (str): A description of which portion of the audio
                    is to be used.

    Returns:
        aligned_onset_times (pd.DataFrame): A data frame containing the
            times corresponding to note onset positions in the score 
            and audio.

    References:
        This code was adapted from the Sync Toolbox Audio-Score 
        Synchronization Demo available at:
        https://github.com/meinardmueller/synctoolbox/blob/master/sync_audio_score_full.ipynb.
    """
    # Get info about audio file
    audio_id = audio_file[0]
    audio_filename = audio_file[1]
    start = audio_file[2]
    end = audio_file[3]
    # Compute the range of audio file samples to use in the alignment
    if start:
        start_secs = (start.hour*60 + start.minute)*60 + start.second
        start_sample = start_secs * SAMPLE_RATE
    else:
        start_secs = 0
        start_sample = None
    if end:
        end_secs = (end.hour*60 + end.minute)*60 + end.second
        end_sample = end_secs * SAMPLE_RATE + 1
    else:
        end_sample = None

    url_regex = (r"(http(s)?:\/\/.)?(www\.)?" +
                 r"[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}" +
                 r"\b([-a-zA-Z0-9@:%_\+.~#?&//=]*)")
    # Load in audio recording
    if re.match(url_regex, audio_filename):
        # If a URL to the audio file is given
        audio = load_audio_from_url(audio_filename)
        # Crop audio file as necessary
        audio = audio[start_sample:end_sample]
    else:
        # If a local filename is given
        audio, _ = librosa.load(audio_filename, sr=SAMPLE_RATE)
        # Crop audio file as necessary
        audio = audio[start_sample:end_sample]

    # Estimate the tuning deviations in the audio recording
    tuning_offset = estimate_tuning(audio, SAMPLE_RATE)
    print(f"Estimated tuning deviation for recording: {tuning_offset} cents")

    # Compute quantized chroma and DLNCO features for the audio and score
    f_chroma_quantized_audio, f_DLNCO_audio = get_features_from_audio(
        audio, tuning_offset)
    f_chroma_quantized_score, f_DLNCO_score = get_features_from_score(
        df_score)

    # Find the optimal shift of chroma vectors between the audio and score
    f_cens_1hz_audio = quantized_chroma_to_CENS(
        f_chroma_quantized_audio, 201, 50, FEATURE_RATE)[0]
    f_cens_1hz_score = quantized_chroma_to_CENS(
        f_chroma_quantized_score, 201, 50, FEATURE_RATE)[0]
    opt_chroma_shift = compute_optimal_chroma_shift(
        f_cens_1hz_audio, f_cens_1hz_score)
    print("Pitch shift between the audio recording and score, determined by",
          f"DTW: {opt_chroma_shift} bins")

    # Apply the shift to the score
    f_chroma_quantized_score = shift_chroma_vectors(f_chroma_quantized_score,
                                                    opt_chroma_shift)
    f_DLNCO_score = shift_chroma_vectors(f_DLNCO_score, opt_chroma_shift)

    # Perform MrMsDTW
    wp = sync_via_mrmsdtw(f_chroma1=f_chroma_quantized_audio,
                          f_onset1=f_DLNCO_audio,
                          f_chroma2=f_chroma_quantized_score,
                          f_onset2=f_DLNCO_score,
                          input_feature_rate=FEATURE_RATE,
                          step_weights=STEP_WEIGHTS,
                          threshold_rec=THRESHOLD_REC)

    # Make warping path strictly monotonic
    wp = make_path_strictly_monotonic(wp)

    # Use warping path to identify the start and end times of each note event
    # in the audio
    df_score["end"] = df_score["start"] + df_score["duration"]
    df_score_warped = df_score.copy(deep=True)
    df_score_warped[["start", "end"]] = interpolate.interp1d(
        wp[1] / FEATURE_RATE,
        wp[0] / FEATURE_RATE,
        kind="linear",
        fill_value="extrapolate")(df_score[["start", "end"]])
    df_score_warped["duration"] = (df_score_warped["end"] -
                                   df_score_warped["start"])

    # Create a data frame containing the times corresponding to note
    # onset positions in the score and audio
    score_onset_times = df_score.groupby("start").size().index
    audio_onset_times = (df_score_warped.groupby("start").size().index +
                         start_secs)
    audio_onset_times = np.round(audio_onset_times, ROUNDING_VALUE)
    aligned_onset_times = pd.DataFrame(
        {"score_tstamp": score_onset_times,
         f"{audio_id}_tstamp": audio_onset_times}
    )

    return aligned_onset_times


def align_score_audios(score_file, measure_map_file, audio_files, out_dir=None):
    """
    Produce an alignment table for a score and a set of audio files and
    save as a .csv file.

    Args:
        score_file (str): The local filename of the score as a MusicXML
            file.
        measure_map_file (str): The local filename of the measure map 
            for the score.
        audio_files (list): A 2D list containing a list for each audio
            file that contains:
                audio_id (str): An identifier for the audio file.
                audio_filename (str): Its local filename or URL.
                A time range to extract from the audio file for 
                    alignment, specified by:
                    start (datetime.time): A start timestamp.
                    end (datetime.time): An end timestamp.
                desc (str): A description of which portion of the audio
                        is to be used.
        out_dir (str): The path to the directory in which the alignment
            table will be saved. Default = None.

    Returns:
        df_alignment (pd.DataFrame): The alignment table.
            Columns:
                score_qstamp (float): The note's time offset in quarter
                    notes in the score.
                qstamp (float): The note's time offset in quarter notes
                    with repeats expanded.
                measure (int): The note's measure number.
                beat (float): The beat in the measure at which the note
                    is played.
                {audio file 1}_tstamp (float): The note's time offset
                    in seconds in audio file 1.
                ...
                {audio file n}_tstamp (float): The note's time offset
                    in seconds in audio file n.
    """
    # Load in MusicXML file for score
    score = converter.parse(score_file)

    # Load in measure map for score
    if measure_map_file.endswith(".json"):
        measure_map = pd.read_json(measure_map_file)
    elif measure_map_file.endswith(".csv"):
        measure_map = pd.read_csv(measure_map_file)

    # Convert score and measure map into a data frame of note events
    df_score_full = score_measure_map_to_df(score, measure_map)
    # Add an offset to the note events so they do not begin on zero,
    # which prevents the timestamps 0.0 from always being aligned
    df_score_full["tstamp"] += 1

    # Convert the note events data frame to one used for alignment
    df_score = (
        df_score_full.rename(columns={"tstamp": "start"})
        [["start", "duration", "pitch", "velocity", "instrument"]]
    )

    # Convert the note events data frame to alignment table format (one
    # row for each note position after repeats expanded)
    df_alignment = (
        df_score_full[["score_qstamp", "qstamp", "measure", "beat", "tstamp"]]
        .drop_duplicates()
        .rename(columns={"tstamp": "score_tstamp"})
        .sort_values("score_tstamp")
    )

    # Iteratively add a timestamp column for each audio file to the
    # alignment table
    for audio_file in audio_files:
        print(f"\nAligning audio file '{audio_file[1]}' to the score",
              f"'{score_file}'.")
        aligned_onset_times = align_score_audio(df_score, audio_file)
        df_alignment = df_alignment.merge(aligned_onset_times)

    # Drop score timestamp column
    df_alignment = df_alignment.drop(columns="score_tstamp")

    # Create .csv file
    score_file_path = Path(score_file)
    if out_dir is None:
        csv_file = f"{score_file_path.stem}_alignment.csv"
    else:
        out_dir_path = Path(out_dir)
        csv_file = (out_dir_path / f"{score_file_path.stem}_alignment.csv")
    df_alignment.to_csv(csv_file, index=False)

    print(f"\nThe alignment table was saved to '{csv_file}'.")

    return df_alignment


def align_hauptstimme_annotations(alignment_file, annotations_file, out_dir=None):
    """
    Given a Hauptstimme annotations .csv file, align them with a set of 
    audio files by merging the annotations with an alignment table.
    Save the aligned annotations as a .csv file.

    Args:
        alignment_file (str): The local filename of the alignment 
            table.
        annotations_file (str): The local filename of the Hauptstimme
            annotations file.
        out_dir (str): The path to the directory in which the aligned 
            annotations file will be saved. Default = None.

    Returns:
        df_aligned_annotations (pd.DataFrame): The aligned annotations
            table.
            Columns:
                score_qstamp (float): The note's time offset in quarter
                    notes in the score.
                qstamp (float): The note's time offset in quarter notes
                    with repeats expanded.
                measure (int): The note's measure number.
                beat (float): The beat in the measure at which the note
                    is played.
                {audio file 1}_tstamp (float): The note's time offset
                    in seconds in audio file 1.
                ...
                {audio file n}_tstamp (float): The note's time offset
                    in seconds in audio file n.
                measure_fraction (float): The note's beat as a fraction
                    of the measure length in beats.
                label (str): The annotation label.
                part_name (str): The name (abbreviated) of the type of 
                    instrument playing in the part that was annotated.
                    Example: "Vln" for a violin.
                part_num (int): The position of the annotated part in 
                    the score (0 = top stave).
                full_part_name (str): An abbreviation of the instrument
                    part name that was annotated. Example: "Vln 1" for 
                    the first of multiple violins.
    """
    df_alignment = pd.read_csv(alignment_file)
    df_annotations = pd.read_csv(annotations_file)

    # Rename Hauptstimme qstamp column to score_qstamp
    df_annotations.rename(columns={"qstamp": "score_qstamp"}, inplace=True)

    df_aligned_annotations = df_alignment.merge(df_annotations)

    # Create .csv file
    annotations_file_path = Path(annotations_file)
    if out_dir is None:
        csv_file = f"{annotations_file_path.stem}_aligned.csv"
    else:
        out_dir_path = Path(out_dir)
        csv_file = (out_dir_path /
                    f"{annotations_file_path.stem}_aligned.csv")
    df_aligned_annotations.to_csv(csv_file, index=False)

    print(f"\nThe aligned annotations were saved to '{csv_file}'.")

    return df_aligned_annotations


def alignment_table_to_measure_timestamps(alignment_file, audio_id):
    """
    Convert an alignment table to timestamps approximating the start of
    each measure in a particular audio file that can be imported into a
    TiLiA beat timeline and save as a .csv file.

    Args:
        alignment_file (str): The local filename of the alignment 
            table.
        audio_id (str): An identifier for the audio file in the table.

    Returns:
        measure_tstamps (pd.DataFrame): A data frame containing the 
            approximate measure timestamps in the audio file.
    """
    df_alignment = pd.read_csv(alignment_file)

    # Rename columns appropriately for TiLiA
    measure_tstamps = df_alignment.rename(columns={
        "measure": "measure_number",
        f"{audio_id}_tstamp": "time"}
    )

    # Only keep timestamps for the first beat of each bar
    measure_tstamps["is_first_in_measure"] = measure_tstamps["beat"] == 1
    measure_tstamps = measure_tstamps[
        measure_tstamps["is_first_in_measure"] == True]

    # Drop columns that aren't needed
    measure_tstamps = measure_tstamps.drop(
        columns=["score_qstamp", "qstamp", "beat"]
    )

    # Create .csv file
    csv_file = f"{audio_id}_measure_tstamps.csv"
    measure_tstamps.to_csv(csv_file, index=False)

    print(f"\nThe measure timestamps were saved to '{csv_file}'.")

    return measure_tstamps

"""
NAME
===============================
Compare Annotations (compare_annotations.py)


BY
===============================
Matthew Blessing


LICENCE:
===============================
Code = MIT. See [README](https://github.com/MarkGotham/Hauptstimme/tree/main#licence).

ABOUT:
===============================
Functions used when comparing Hauptstimme annotations with another set 
of annotations, such as the focal instrument of a video.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from music21 import instrument
from math import ceil
from src.types import ArrayLike, Scalar
from typing import cast, List, Optional


def get_default_instrument_names(instruments: ArrayLike) -> List[str]:
    """
    Convert the instrument names in a set of annotations to the default
    Music21 instrument names.

    Args:
        instruments: An array of instrument names/abbreviations.

    Return:
        default_instruments: A list of the default instrument names.
    """
    default_instruments = []

    for i in instruments:
        try:
            instr_class = instrument.fromString(i).__class__()
            if instr_class is not None:
                instr = instr_class.instrumentName
        except:
            instr = np.nan
        default_instruments.append(instr)

    return default_instruments


def get_annotations_vec(
    df_annotations: pd.DataFrame,
    tstamp_col: str,
    annotation_col: str,
    round_to: Scalar,
    start_tstamp: Scalar = 0,
    end_tstamp: Optional[Scalar] = None
) -> List[float]:
    """
    Convert a data frame containing a column of timestamps and a column
    of annotations into a timeline vector indicating the annotation at 
    each timestamp.

    Args:
        df_annotations: A data frame containing a set of annotations at
            various timestamps.
        tstamp_col: The name of the timestamp column.
        annotation_col: The name of the annotation column.
        round_to: The number of seconds to round each timestamp to.
        start_tstamp: The start timestamp for the annotations vector.
            Default = 0.
        end_tstamp: The end timestamp for the annotations vector. 
            Default = None.

    Returns: 
        annotations_vec: A vector indicating the annotation at each 
            timestamp between `start_tstamp` and `end_tstamp`.
    """
    if end_tstamp is None:
        end_tstamp = df_annotations[tstamp_col].max()
    end_tstamp = cast(Scalar, end_tstamp)

    # Round timestamps to `round_to` seconds
    df_annotations[tstamp_col] = np.round(
        df_annotations[tstamp_col]/round_to
    ) * round_to

    # Round `end_tstamp` to nearest 10
    # end_tstamp_rounded = ceil(end_tstamp/10) * 10]
    start_tstamp_rounded = round(start_tstamp/round_to) * round_to
    end_tstamp_rounded = round(end_tstamp/round_to) * round_to

    # Get all timestamps up to the end timestamp for the vector
    all_tstamps = np.arange(0, end_tstamp_rounded + round_to, round_to)

    # Get annotations vector
    annotations_vec = [np.nan]*len(all_tstamps)
    df_annotations.reset_index(drop=True, inplace=True)
    for i, row in df_annotations.iterrows():
        i = cast(int, i)
        tstamp = row[tstamp_col]
        # Get the timestamp of the next annotation
        if i + 1 < len(df_annotations):
            next_tstamp = df_annotations.loc[i+1, tstamp_col]
        else:
            next_tstamp = end_tstamp_rounded
        # Fill the vector up to then with the current annotation
        for t in np.arange(tstamp, next_tstamp + round_to, round_to):  # type: ignore
            if t <= end_tstamp_rounded:
                annotations_vec[int(t/round_to)] = row[annotation_col]

    # Take annotation vector from the start timestamp onwards
    annotations_vec = annotations_vec[int(start_tstamp_rounded/round_to):]

    return annotations_vec


def haupt_video_comparison(
    aligned_annotations_df: pd.DataFrame,
    score_summary_df: pd.DataFrame,
    video_annotations_vec: List[float],
    score_tstamp_col: str,
    round_to: Scalar,
    start_tstamp: Scalar = 0,
    unison_full_match: bool = True,
    cant_match_category: bool = True
):
    """
    Compare a video annotations vector starting from `start_tstamp` to
    the score's part relationship summary to see how the video 
    annotations and Hauptstimme annotations relate. Print the results.

    Args:
        aligned_annotations_df: A data frame containing the Hauptstimme
            annotations with timestamps in the video.
        score_summary_df: A part relationship summary for the score.
        video_annotations_vec: A vector indicating the annotation at each 
            timestamp between `start_tstamp` and some end timestamp.
        score_tstamp_col: The name of the timestamp column in 
            `aligned_annotations_df`.
        round_to: The number of seconds to round each timestamp to.
        start_tstamp: The start timestamp for the annotations vector.
            Default = 0.
        unison_full_match: Whether instruments being played in unison with
            the main part should be considered full matches (True) or 
            partial matches (False). Default = True.
        cant_match_category: Whether there should be a separate 'Can't 
            match category' for video annotations for which either the
            instrument couldn't be determined or they were for the whole 
            orchestra or the conductor. Default = True.
    """
    # Initialise counts
    match = 0
    partial = 0
    no = 0
    cant = 0

    # Iterate through video annotations
    for i, video_annotation in enumerate(video_annotations_vec):
        #  If the video annotation didn't convert (could have been the whole orchestra
        # or was just not recognisable) or was for the conductor
        if pd.isna(video_annotation) or video_annotation == "Conductor":
            if cant_match_category:
                cant += 1
            else:
                no += 1
        else:
            video_annotation = str(video_annotation)

            #  Get video annotation timestamp
            tstamp = i*round_to + start_tstamp
            # Get qstamp corresponding to timestamp
            qstamp = aligned_annotations_df[
                aligned_annotations_df[score_tstamp_col] <= tstamp
            ].iloc[-1]["qstamp"]

            # Get the corresponding score part relationships summary row
            summary_row = score_summary_df[
                score_summary_df["qstamp_start"] == qstamp
            ]

            # Get the part relationships for the video annotation instrument
            instr_relations = ""
            for col in score_summary_df.columns:
                if video_annotation in col:
                    part_relations = summary_row[col].item()
                    if not pd.isna(part_relations):
                        instr_relations += part_relations

            # If it is the main part
            if "Main Part" in instr_relations:
                match += 1
            # If it is playing in unison with the main part
            elif "U(Main)" in instr_relations:
                if unison_full_match:
                    match += 1
                else:
                    partial += 1
            # If P8(Main) or Px(Main)
            elif "Main" in instr_relations:
                partial += 1
            # If no relationship with the main part
            else:
                no += 1

    # Compute and display results
    match_percent = match/len(video_annotations_vec) * 100
    partial_percent = partial/len(video_annotations_vec) * 100
    no_percent = no/len(video_annotations_vec) * 100
    print("Match percentage:", match_percent)
    print("Partial match percentage:", partial_percent)
    print("No match percentage:", no_percent)
    if cant_match_category:
        cant_percent = cant/len(video_annotations_vec) * 100
        print("Can't match percentage:", cant_percent)

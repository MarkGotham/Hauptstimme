"""
NAME
===============================
Compare Annotations (compare_annotations.py)


BY
===============================
Matthew Blessing


LICENCE:
===============================
Creative Commons Attribution-ShareAlike 4.0 International License
https://creativecommons.org/licenses/by-sa/4.0/


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
from hauptstimme.types import ArrayLike, Scalar
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
            instr_class = instrument.fromString(i).__class__
            instr = instr_class().instrumentName
        except:
            instr = np.nan
        default_instruments.append(instr)

    return default_instruments


def get_annotations_vec(
    df_annotations: pd.DataFrame,
    tstamp_col: str,
    annotation_col: str,
    round_to: Scalar,
    max_tstamp: Optional[Scalar] = None
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
        max_tstamp: A maximum timestamp for the annotations vector. 
            Default = None.

    Returns: 
        annotations_vec: A vector indicating the annotation at each 
            timestamp up to `max_tstamp`.
    """
    if max_tstamp is None:
        max_tstamp = df_annotations[tstamp_col].max()
    max_tstamp = cast(Scalar, max_tstamp)

    # Round timestamps to `round_to` seconds
    df_annotations[tstamp_col] = np.round(
        df_annotations[tstamp_col]/round_to) * round_to

    # Round `max_tstamp` to nearest 10
    max_tstamp_rounded = ceil(max_tstamp/10) * 10
    # Get all timestamps
    all_tstamps = np.arange(0, max_tstamp_rounded + round_to, round_to)

    # Get annotations vector
    annotations_vec = [np.nan]*len(all_tstamps)
    df_annotations.reset_index(drop=True, inplace=True)
    for i, row in df_annotations.iterrows():
        i = cast(int, i)
        tstamp = row[tstamp_col]
        if i + 1 < len(df_annotations):
            next_tstamp = df_annotations.loc[i+1, tstamp_col]
        else:
            next_tstamp = max_tstamp_rounded
        for t in np.arange(tstamp, next_tstamp + round_to, round_to):  # type: ignore
            if t <= max_tstamp_rounded:
                annotations_vec[int(t/round_to)] = row[annotation_col]

    return annotations_vec

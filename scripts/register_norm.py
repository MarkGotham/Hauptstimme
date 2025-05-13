"""
NAME
===============================
Register Normalisation by Pitch Class (register_norm.py)


BY
===============================
Mark Gotham


LICENCE:
===============================
Code = MIT. See [README](https://github.com/MarkGotham/Hauptstimme/tree/main#licence).


ABOUT:
===============================
This script takes the MIDI note number of pitches in a source and normalises by pitch class.
Why?
If we want to compare the presence of notes across the register, we can take the raw note usage,
but this will be complicated by the much higher usage of certain pitch classes over others.
Put another way, there tend to be more notes in key than out of key, regardless of register.
Normalising each _pitch_ by the proportional use of the corresponding pitch _class_
gives a clearer picture of _register_ usage alone, independent of key.
"""
from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd
from collections import Counter
import matplotlib.pyplot as plt

__author__ = "Mark Gotham"

current_path = Path('.')
SAMPLE_FILE = current_path / "demo_files" / "Beethoven_Op.36_1_note_events.csv"
data = pd.read_csv(SAMPLE_FILE)


def register_to_counter(
        df: pd.DataFrame = data,
        int_column: str = "pitch",
        float_column: str = "duration_quarter",
        step_size: int = 1,
        norm_by_pc: bool = True,
        plot: bool = False
):
    """
    Take every note expressed by its MIDI number and duration,
    convert to a Counter,
    optionally normalise by PC,
    optionally plot.

    Args:
        df (pd.DataFrame): Input DataFrame.
        int_column (str): Name of the column containing pitch midi number
            (integer values to be used as keys for the `Counter` object).
        float_column (str): Name of the column containing duration
            (float values to sum for the values of the `Counter`).
        step_size (int): The step size for plotting on the x-axis. Defaults to 1 (one per MIDI number).
        norm_by_pc (bool): If True, normalise by pitch class.
        plot (bool): If True, plot and show. In all cases, return the Counter object.

    Returns:
        collections.Counter: A Counter object with integer values as keys and cumulative duration for weights as values.
    """
    counter = Counter()
    for index, row in df.iterrows():
        int_val = row[int_column]
        float_val = row[float_column]
        counter[int_val] += float_val

    if norm_by_pc:
        _, counter = compress_and_normalize(counter)

    sorted_keys = sorted(counter.keys())
    min_val = min(sorted_keys)
    max_val = max(sorted_keys)
    x_values = np.arange(int(min_val), int(max_val) + 1, step_size)

    y_values = []
    for x in x_values:
        y_values.append(
            # x-value, or 0 if x not used (not in the counter)
            counter.get(x, 0.0)
        )

    if plot:
        plt.figure(figsize=(10, 6))
        plt.plot(x_values, y_values, marker='o')
        plt.xlabel("Pitch (MIDI)")
        plt.ylabel(f"Weight (duration in quarter notes), norm={norm_by_pc}")
        plt.grid(True)
        plt.xticks(x_values)
        plt.xticks(
            np.arange(int(min_val / 10) * 10, max_val, 10)
        )
        plt.savefig(f"./{norm_by_pc}.pdf")

    return counter


def compress_and_normalize(counter: Counter) -> tuple[Counter, Counter]:
    """
    Normalise a `Counter` object with _pitch_ (MIDI) as the key
    according to the overall weightings by pitch _class_.

    Args:
        counter: Any `Counter` object with integer keys (representing MIDI pitch) and float values.

    Returns:
        A tuple containing two `Counter` objects,
        1) `compressed_counter`: A Counter with keys mapped to 0-11 using mod 12.
        2) `normalized_counter`: Another Counter based on the original,
        with values normalised by the corresponding weight from the compressed counter.
    """
    compressed_counter = Counter()
    for key, value in counter.items():
        compressed_key = key % 12
        compressed_counter[compressed_key] += value

    normalized_counter = Counter()
    for key, value in counter.items():
        compressed_key = key % 12
        normalization_weight = compressed_counter[compressed_key]
        normalized_counter[key] = value / normalization_weight

    return compressed_counter, normalized_counter

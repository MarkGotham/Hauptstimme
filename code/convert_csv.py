"""
NAME
===============================
Convert CSV (convert_csv.py)


BY
===============================
JamesHLS and Matt Blessing, 2024


LICENCE:
===============================
Creative Commons Attribution-ShareAlike 4.0 International License
https://creativecommons.org/licenses/by-sa/4.0/


ABOUT:
===============================
Convert a score to a lightweight csv file.

TODO: CLEAN THIS UP

"""

import numpy as np
import pandas as pd
import utils
from collections import Counter
from music21 import chord, clef, converter, expressions, meter, note, stream, tempo

pd.options.display.max_columns = 100
pd.options.display.max_rows = 100
pd.options.display.max_colwidth = 100
pd.options.display.width = 200
pd.set_option("display.expand_frame_repr", False)

clef_dict = {
    "Violin": [clef.TrebleClef(), clef.Treble8vaClef()],
    "Viola": [clef.TrebleClef(), clef.AltoClef()],
    "Violoncello": [clef.TrebleClef(), clef.TenorClef(), clef.BassClef()],
    "Contrabass": [clef.BassClef(), clef.Bass8vbClef()],

    "Flute": [clef.TrebleClef(), clef.Treble8vaClef()],
    "Oboe": [clef.TrebleClef()],
    "Clarinet": [clef.TrebleClef()],
    "Bassoon": [clef.BassClef(), clef.TenorClef()],
    "Contrabassoon": [clef.BassClef(), clef.Bass8vbClef()],

    "Trumpet": [clef.TrebleClef()],
    "Horn": [clef.TrebleClef(), clef.BassClef()],
    "Trombone": [clef.TenorClef(), clef.BassClef()],
    "Tuba": [clef.BassClef(), clef.Bass8vbClef()],

    "Timpani": [clef.BassClef()]
}


def convert_mxml_to_csv(score, output_file_name, output_invalid_clefs=False):
    """
    Convert mxml -> csv with this format:
    qstamp | bar | beat | instrument1 | instrument2 | instrument3 | ... | instrumentN

    - if note lasts till after next qstamp, it will be repeated in the next row
    - scientific pitch notation
    - bar is integer
    - qstamp and beat are floats, depends on the rhythm, increment may not be constant
        e.g. (1, 2, 2.5, 3, 4, 5, 6, 7.25, 7.5, 7.75, 8)
    - if chord, cell will contain top note
    - if qstamp exists, find current instrument column and rewrite cell
    - r to represent rest
    """

    instruments = [part.getInstrument().instrumentName for part in score.parts]

    # give each instrument a unique name, where each duplicate is appended with a number, starting from 1
    dup = dict(Counter(instruments))
    uniques = np.unique(instruments)
    instruments = [key if i == 0 else key + " " +
                   str(i + 1) for key in uniques for i in range(dup[key])]

    df = pd.DataFrame(columns=["qstamp", "bar", "beat"] + instruments)

    tempos = {}
    time_sigs = {}

    parsed_parts = []

    invalid_clefs_dict = {
        "instrument": [],
        "bar": [],
        "clef": []
    }

    for partnum, part in enumerate(score.parts):
        part = part.toSoundingPitch()

        instrument_name = part.getInstrument().instrumentName
        is_duplicate = instrument_name + " " + "1" in instruments
        if is_duplicate:
            instrument_name = instrument_name + " " + "1"
        x = 1
        while instrument_name in parsed_parts:
            x += 1
            instrument_name = part.getInstrument().instrumentName + " " + str(x)
        parsed_parts.append(instrument_name)

        print(instrument_name)
        if True:
            lookup_name = utils.get_lookup_name(instrument_name)
            accepted_clefs = clef_dict.get(lookup_name)
            if accepted_clefs is None:
                print(instrument_name, "not found in clef_dict")
            elements = part.flatten()

            curr_time_sig = None
            for n in elements:  # get first time signature
                if n.offset != 0:
                    break
                if isinstance(n, meter.TimeSignature):
                    time_sigs[n.measureNumber] = n
                    curr_time_sig = n
                    break

            for n in elements:
                qstamp = n.offset

                if isinstance(elements, stream.Measure):
                    qstamp += elements.offset

                if partnum == 0:
                    if isinstance(n, meter.TimeSignature):
                        time_sigs[n.measureNumber] = n
                        curr_time_sig = n
                        continue

                    # If a tempo marking written as a text expression (e.g., Adagio)
                    if isinstance(n, expressions.TextExpression):
                        # Get default bpm for this tempo
                        bpm = tempo.defaultTempoValues.get(n.content.lower())
                        if bpm:
                            # Convert bpm to quarter note bpm
                            quarter_bpm = bpm * curr_time_sig.denominator / 4
                            tempos[n.measureNumber] = quarter_bpm
                        continue
                    elif isinstance(n, tempo.MetronomeMark):
                        # Get quarter note bpm
                        tempos[n.measureNumber] = n.getQuarterBPM()
                        continue

                if isinstance(n, note.Note):
                    cell_input = n.nameWithOctave
                elif isinstance(n, chord.Chord):
                    cell_input = [
                        chord_note.nameWithOctave for chord_note in n][-1]
                elif isinstance(n, note.Rest):
                    cell_input = "r"
                elif "Clef" in n.classes:
                    if not accepted_clefs is None:
                        accepted = n in accepted_clefs
                        if not accepted:
                            print(
                                f"Invalid clef {n} found in bar {n.measureNumber}")

                            # For invalid clefs csv file
                            if output_invalid_clefs:
                                invalid_clefs_dict["instrument"].append(
                                    instrument_name)
                                invalid_clefs_dict["bar"].append(
                                    n.measureNumber)
                                invalid_clefs_dict["clef"].append(n.name)
                    continue
                else:
                    continue

                if qstamp in df["qstamp"].values:
                    df.loc[df["qstamp"] == qstamp,
                           instrument_name] = cell_input
                else:
                    new_row = {"qstamp": qstamp,
                               "bar": n.measureNumber,
                               "beat": n.beat,
                               instrument_name: cell_input}
                    df = pd.concat(
                        [df, pd.DataFrame(new_row, index=[0])], ignore_index=True)

    df.sort_values(by=["qstamp"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    # If no tempo info then use default of 120bpm
    if 1 not in tempos:
        tempos = {1: 120.0}  #  bar numbering should always start at 1

    # Determine the tempo at each measure
    max_measure = df["bar"].max()
    tempo_marking_measures = sorted(tempos.keys())
    curr_tempo_marking_index = 0
    curr_tempo = tempos.get(1)
    for measure in range(1, max_measure + 1):
        # Check if there is a tempo change at the current measure
        if curr_tempo_marking_index < len(tempo_marking_measures) and measure == tempo_marking_measures[curr_tempo_marking_index]:
            # Update the current tempo
            curr_tempo = tempos[measure]
            curr_tempo_marking_index += 1
        # Assign the current tempo to the current measure
        tempos[measure] = curr_tempo

    max_qstamp = df["qstamp"].max()
    next_tstamp = 0.
    for i, row in df.iterrows():
        # Get current quarter note BPM
        curr_quarter_bpm = tempos[row["bar"]]
        # Get current length of a quarter note
        curr_quarter_length = 60 / curr_quarter_bpm

        # Get the timestamp
        df.loc[i, "time_offset"] = next_tstamp

        if row["qstamp"] != max_qstamp:
            # Calculate the timestamp for the next note event
            diff = df.loc[i + 1]["qstamp"] - row["qstamp"]
            next_tstamp += diff * curr_quarter_length

    # time_offset column: in seconds
    df.ffill(inplace=True)  # fill NaNs with previous value
    df.to_csv(output_file_name, index=False)
    print("Score saved to", output_file_name)

    if output_invalid_clefs:
        invalid_clefs_df = pd.DataFrame(invalid_clefs_dict)
        if not invalid_clefs_df.empty:
            invalid_clefs_df.to_csv(output_file_name.replace(
                ".csv", "_invalid_clefs.csv"), index=False)
            print("Invalid clefs saved to", output_file_name.replace(
                ".csv", "_invalid_clefs.csv"))
        else:
            print("No invalid clefs found")

    return df


if __name__ == "__main__":
    file_path = utils.REPO_PATH / "test" / "score_clef.mxl"
    score = converter.parse(file_path).expandRepeats()
    dataframe = convert_mxml_to_csv(score, str(file_path).replace(
        file_path.suffix, ".csv"), output_invalid_clefs=True)
    dataframe = dataframe.set_index("qstamp")

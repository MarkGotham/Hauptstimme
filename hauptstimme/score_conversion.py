"""
NAME
===============================
Score Conversion (score_conversion.py)


BY
===============================
Matthew Blessing


LICENCE:
===============================
Code = MIT. See [README](https://github.com/MarkGotham/Hauptstimme/tree/main#licence)


ABOUT:
===============================
Given a Music21 score object, convert to a data frame.

`score_measure_to_df` gives a data frame used for alignment, which,
for each note event, contains:
    - All timestamps (`score_qstamp`, `qstamp`, and `tstamp`)
    - Measure and beat number
    - Instrument name
    - Duration, pitch, velocity

`score_to_df` gives a data frame which, for each note event, contains:
    - Timestamps (`qstamp`, and `tstamp`)
    - Measure and beat number
    - Instrument name
    - Duration, pitch, velocity

`score_to_lightweight_df` gives a data frame used to provide a
lightweight overview of the score, which is used for comparing
instrument usage. It also saves this as a .csv.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from music21 import converter, chord, note, tempo, pitch, instrument
from music21.stream.base import Score, Part, Measure
from music21.meter.base import TimeSignature
from pathlib import Path
from hauptstimme.utils import validate_path
from hauptstimme.constants import ROUNDING_VALUE
from typing import cast, Union, Optional


def score_measure_map_to_df(
    score: Score,
    measure_map: pd.DataFrame
) -> pd.DataFrame:
    """
    Convert a score and measure map into a data frame containing
    information about all note events.

    Notes:
        Doesn't take into account fermatas, accelerandos, ritardandos,
        etc.
        Ignores grace notes.
        All float columns are rounded to 4 d.p.

    Args:
        score: A music21 score.
        measure_map: A measure map for the score.

    Returns:
        df_score: A data frame containing information
            for each note event.
            Columns:
                score_qstamp (float): The note's time offset in quarter
                    notes in the score.
                qstamp (float): The note's time offset in quarter notes
                    with repeats expanded.
                tstamp (float): The note's time offset in seconds with
                    repeats expanded.
                measure (int): The note's measure number.
                beat (float): The beat in the measure at which the note
                    is played.
                instrument (str): The name of the instrument playing
                    the note.
                duration_quarter (float): The note's duration in
                    quarter notes.
                duration (float): The note's duration in seconds.
                pitch (int): The note's MIDI note number.
                velocity (float): The note's velocity.

    Raises:
        ValueError: If a particular measure has no associated time 
            signature.
        ValueError: If an instrument has unpitched notes but isn't of 
            type 'UnpitchedPercussion'.
    """
    print("\nConverting score to a data frame containing all note events...")

    df_score = pd.DataFrame(
        columns=[
            "score_qstamp", "qstamp", "tstamp", "measure", "beat",
            "instrument", "duration_quarter", "duration", "pitch", "velocity"
        ]
    )

    tempos = {}

    for part_num, part in enumerate(score.parts):
        part = cast(Part, part.toSoundingPitch())
        instrument_name = part.partName
        elements = part.flatten()

        for n in elements:
            score_qstamp = round(float(n.offset), ROUNDING_VALUE)
            measure = n.measureNumber
            if n.measureNumber is None:
                continue
            beat = round(float(n.beat), ROUNDING_VALUE)

            curr_time_sig = n.getContextByClass(TimeSignature)
            if curr_time_sig is None:
                # Sometimes the time signature is defined after the
                # notes in the first measure, so it isn't picked up by
                # `getContextByClass`
                if measure == 1:
                    curr_time_sig = next(
                        part.recurse()
                        .getElementsByClass(TimeSignature)
                    )
                if curr_time_sig is None:
                    raise ValueError(
                        f"Error: The elements in measure {measure} " +
                        "have no associated time signature."
                    )

            # Deal with beats issue when there are multiple voices
            # Manually calculate beat
            measure_obj = n.getContextByClass(Measure)
            num_voices = len(measure_obj.voices)
            if num_voices > 1:
                beat = (
                    1 + (n.offset - measure_obj.offset) /
                    curr_time_sig.beatDuration.quarterLength
                )
                beat = round(float(beat), ROUNDING_VALUE)

            if part_num == 0:
                if isinstance(n, tempo.MetronomeMark):
                    # Get quarter note BPM directly from tempo marking
                    tempos[measure] = n.getQuarterBPM()
                    print(f"Tempo in measure {measure}: {tempos[measure]}")
                    continue

            if isinstance(n, note.Note):
                # Ignore grace notes (they have duration 0)
                if not n.duration.isGrace:
                    # Add row for note
                    row = {
                        "score_qstamp": score_qstamp,
                        "measure": measure,
                        "beat": beat,
                        "instrument": instrument_name,
                        "duration_quarter": round(
                            float(n.duration.quarterLength), ROUNDING_VALUE
                        ),
                        "pitch": n.pitch.midi,
                        "velocity": round(n.volume.realized, ROUNDING_VALUE)
                    }
                    df_score = pd.concat(
                        [df_score, pd.DataFrame(row, index=[0])]
                    )
            elif isinstance(n, chord.Chord):
                # Add row for each note in chord
                for chord_note in n:
                    chord_note = cast(note.Note, chord_note)
                    # Ignore grace notes (they have duration 0)
                    if not chord_note.duration.isGrace:
                        row = {
                            "score_qstamp": score_qstamp,
                            "measure": measure,
                            "beat": beat,
                            "instrument": instrument_name,
                            "duration_quarter": round(
                                float(chord_note.duration.quarterLength),
                                ROUNDING_VALUE
                            ),
                            "pitch": chord_note.pitch.midi,
                            "velocity": round(
                                chord_note.volume.realized, ROUNDING_VALUE
                            )
                        }
                        df_score = pd.concat(
                            [df_score, pd.DataFrame(row, index=[0])]
                        )
            elif isinstance(n, note.Unpitched):
                # Ignore grace notes (they have duration 0)
                if not n.duration.isGrace:
                    instr = n.getContextByClass(
                        instrument.UnpitchedPercussion
                    )
                    if instr is not None:
                        pitch = instr.percMapPitch
                    else:
                        raise ValueError(
                            f"Error: Part '{instrument_name}' contains " +
                            "unpitched notes but it isn't an " +
                            "'UnpitchedPercussion' instrument."
                        )
                    # Add row for note
                    row = {
                        "score_qstamp": score_qstamp,
                        "measure": measure,
                        "beat": beat,
                        "instrument": instrument_name,
                        "duration_quarter": round(
                            float(n.duration.quarterLength), ROUNDING_VALUE
                        ),
                        "pitch": pitch,
                        "velocity": round(n.volume.realized, ROUNDING_VALUE)
                    }
                    df_score = pd.concat(
                        [df_score, pd.DataFrame(row, index=[0])]
                    )

    df_score.sort_values("qstamp", inplace=True)
    df_score.reset_index(drop=True, inplace=True)

    # If no tempo info then use default of 120 BPM
    if 1 not in tempos:
        tempos = {1: 120.0}

    # Get a list indicating the order in which the measures are played
    # when expanding repeats
    measures = []
    curr_id = int(measure_map.iloc[0, 0])  # type: ignore
    while curr_id != -1:
        measure_map_row = measure_map[measure_map["ID"] == curr_id]
        if len(measure_map_row) == 0:
            # If the measure map is compressed, it won't have an entry
            # for measures where next = current + 1, so move on
            next_id = curr_id + 1
        else:
            next_ids = measure_map_row["next"].item()
            if len(next_ids) > 1:
                # If more than one next ID, then remove the first one
                # from the list
                next_id = next_ids.pop(0)
            else:
                next_id = next_ids[0]
        measures.append(curr_id)
        curr_id = next_id

    # Determine the tempo at each measure
    max_measure = max(measures)
    tempo_marking_measures = sorted(tempos.keys())
    curr_tempo_marking_index = 0
    curr_tempo = tempos.get(1)
    for measure in range(1, max_measure + 1):
        # Check if there is a tempo change at the current measure
        if (curr_tempo_marking_index < len(tempo_marking_measures) and
                measure == tempo_marking_measures[curr_tempo_marking_index]):
            # Update the current tempo
            curr_tempo = tempos[measure]
            curr_tempo_marking_index += 1
        # Assign the current tempo to the current measure
        tempos[measure] = cast(float, curr_tempo)

    df_score["qstamp"] = [list() for _ in range(len(df_score))]
    df_score["tstamp"] = [list() for _ in range(len(df_score))]
    # Get the indices of every note event at each score qstamp
    df_score_qstamp_measure = (
        df_score.groupby(["score_qstamp", "measure"])
        .apply(lambda x: x.index.to_list())
        .reset_index()
        .rename(columns={0: "indices"})
    )
    qstamp = 0
    tstamp = 0.
    for measure in measures:
        # Get current quarter note BPM
        curr_quarter_bpm = tempos[measure]
        # Get current length of a quarter note
        curr_quarter_length = 60 / curr_quarter_bpm

        # Get measure start and end score qstamps
        measure_obj = cast(Measure, score.parts[0].measure(measure))
        measure_start = round(float(measure_obj.offset), ROUNDING_VALUE)
        measure_end = round(
            float(measure_start + measure_obj.duration.quarterLength),
            ROUNDING_VALUE
        )

        # Initialise previous score qstamp with the start of the measure
        prev_score_qstamp = measure_start

        # Iterate through all note events in the measure
        df_measure_notes = df_score_qstamp_measure[
            df_score_qstamp_measure["measure"] == measure
        ]
        for _, row in df_measure_notes.iterrows():
            # Get the note duration in seconds
            dur = cast(
                pd.Series, df_score.loc[row["indices"], "duration_quarter"]
            )
            df_score.loc[row["indices"], "duration"] = np.round(
                dur * curr_quarter_length,
                ROUNDING_VALUE
            )

            # Calculate the timestamp for this note event
            diff = row["score_qstamp"] - prev_score_qstamp
            qstamp += diff
            tstamp += diff * curr_quarter_length

            # Get a list of qstamps and tstamps for each note
            # There can be more than one due to repeats
            for index in row["indices"]:
                df_score.at[index, "qstamp"].append(qstamp)
                df_score.at[index, "tstamp"].append(
                    round(tstamp, ROUNDING_VALUE)
                )

            prev_score_qstamp = row["score_qstamp"]

        # Get qstamp for end of the measure
        diff = measure_end - row["score_qstamp"]
        qstamp += diff
        tstamp += diff*curr_quarter_length

    # Convert rows containing lists into multiple rows
    df_score = df_score.explode(["qstamp", "tstamp"]).apply(
        pd.to_numeric, errors="ignore"
    )
    df_score.sort_values("qstamp", inplace=True)
    df_score.reset_index(drop=True, inplace=True)

    print("Conversion successful.")

    return df_score


def score_to_df(score: Score) -> pd.DataFrame:
    """
    Convert a score into a data frame containing information about all 
    note events.

    Notes:
        Doesn't take into account fermatas, accelerandos, ritardandos,
        etc.
        Ignores grace notes.
        All float columns are rounded to 4 d.p.
        Like the above function, but doesn't obtain the `score_qstamp`
        column.

    Args:
        score: A music21 score.

    Returns:
        df_score: A data frame containing information for each note 
            event.
            Columns:
                qstamp (float): The note's time offset in quarter notes
                    with repeats expanded.
                tstamp (float): The note's time offset in seconds with
                    repeats expanded.
                measure (int): The note's measure number.
                beat (float): The beat in the measure at which the note
                    is played.
                instrument (str): The name of the instrument playing
                    the note.
                duration_quarter (float): The note's duration in
                    quarter notes.
                duration (float): The note's duration in seconds.
                pitch (int): The note's MIDI note number.
                velocity (float): The note's velocity.

    Raises:
        ValueError: If a particular measure has no associated time 
            signature.
        ValueError: If an instrument has unpitched notes but isn't of 
            type 'UnpitchedInstrument'.
    """
    print("\nConverting score to a data frame containing all note events...")

    df_score = pd.DataFrame(
        columns=[
            "qstamp", "tstamp", "measure", "beat", "instrument",
            "duration_quarter", "duration", "pitch", "velocity"
        ]
    )

    tempos = {}

    for part_num, part in enumerate(score.parts):
        part = cast(Part, part.toSoundingPitch())
        instrument_name = part.partName
        elements = part.flatten()

        for n in elements:
            qstamp = round(float(n.offset), ROUNDING_VALUE)
            measure = n.measureNumber
            if n.measureNumber is None:
                continue
            beat = round(float(n.beat), ROUNDING_VALUE)

            curr_time_sig = n.getContextByClass(TimeSignature)
            if curr_time_sig is None:
                # Sometimes the time signature is defined after the
                # notes in the first measure, so it isn't picked up by
                # `getContextByClass`
                if measure == 1:
                    curr_time_sig = next(
                        part.recurse()
                        .getElementsByClass(TimeSignature)
                    )
                if curr_time_sig is None:
                    raise ValueError(
                        f"Error: The elements in measure {measure} " +
                        "have no associated time signature."
                    )

            # Deal with beats issue when there are multiple voices
            # Manually calculate beat
            measure_obj = n.getContextByClass(Measure)
            num_voices = len(measure_obj.voices)
            if num_voices > 1:
                beat = (
                    1 + (n.offset - measure_obj.offset) /
                    curr_time_sig.beatDuration.quarterLength
                )
                beat = round(float(beat), ROUNDING_VALUE)

            if part_num == 0:
                if isinstance(n, tempo.MetronomeMark):
                    # Get quarter note BPM directly from tempo marking
                    tempos[measure] = n.getQuarterBPM()
                    print(f"Tempo in measure {measure}: {tempos[measure]}")
                    continue

            if isinstance(n, note.Note):
                # Ignore grace notes (they have duration 0)
                if not n.duration.isGrace:
                    # Add row for note
                    row = {
                        "qstamp": qstamp,
                        "measure": measure,
                        "beat": beat,
                        "instrument": instrument_name,
                        "duration_quarter": round(
                            float(n.duration.quarterLength), ROUNDING_VALUE
                        ),
                        "pitch": n.pitch.midi,
                        "velocity": round(n.volume.realized, ROUNDING_VALUE)
                    }
                    df_score = pd.concat(
                        [df_score, pd.DataFrame(row, index=[0])]
                    )
            elif isinstance(n, chord.Chord):
                # Add row for each note in chord
                for chord_note in n:
                    chord_note = cast(note.Note, chord_note)
                    # Ignore grace notes (they have duration 0)
                    if not chord_note.duration.isGrace:
                        row = {
                            "qstamp": qstamp,
                            "measure": measure,
                            "beat": beat,
                            "instrument": instrument_name,
                            "duration_quarter": round(
                                float(chord_note.duration.quarterLength),
                                ROUNDING_VALUE
                            ),
                            "pitch": chord_note.pitch.midi,
                            "velocity": round(
                                chord_note.volume.realized, ROUNDING_VALUE
                            )
                        }
                        df_score = pd.concat(
                            [df_score, pd.DataFrame(row, index=[0])]
                        )
            elif isinstance(n, note.Unpitched):
                # Ignore grace notes (they have duration 0)
                if not n.duration.isGrace:
                    instr = n.getContextByClass(
                        instrument.UnpitchedPercussion
                    )
                    if instr is not None:
                        pitch = instr.percMapPitch
                    else:
                        raise ValueError(
                            f"Error: Part '{instrument_name}' contains " +
                            "unpitched notes but it isn't an " +
                            "'UnpitchedPercussion' instrument."
                        )
                    # Add row for note
                    row = {
                        "qstamp": qstamp,
                        "measure": measure,
                        "beat": beat,
                        "instrument": instrument_name,
                        "duration_quarter": round(
                            float(n.duration.quarterLength), ROUNDING_VALUE
                        ),
                        "pitch": pitch,
                        "velocity": round(n.volume.realized, ROUNDING_VALUE)
                    }
                    df_score = pd.concat(
                        [df_score, pd.DataFrame(row, index=[0])]
                    )

    df_score.sort_values("qstamp", inplace=True)
    df_score.reset_index(drop=True, inplace=True)

    # If no tempo info then use default of 120 BPM
    if 1 not in tempos:
        tempos = {1: 120.0}

    # Determine the tempo at each measure
    max_measure = df_score["measure"].max()
    tempo_marking_measures = sorted(tempos.keys())
    curr_tempo_marking_index = 0
    curr_tempo = tempos.get(1)
    for measure in range(1, max_measure + 1):
        # Check if there is a tempo change at the current measure
        if (curr_tempo_marking_index < len(tempo_marking_measures) and
                measure == tempo_marking_measures[curr_tempo_marking_index]):
            # Update the current tempo
            curr_tempo = tempos[measure]
            curr_tempo_marking_index += 1
        # Assign the current tempo to the current measure
        tempos[measure] = cast(float, curr_tempo)

    max_qstamp = df_score["qstamp"].max()
    next_tstamp = 0.
    for i, row in df_score.iterrows():
        i = cast(int, i)
        # Get current quarter note BPM
        curr_quarter_bpm = tempos[row["measure"]]
        # Get current length of a quarter note
        curr_quarter_length = 60 / curr_quarter_bpm

        # Get the note duration in seconds
        df_score.at[i, "duration"] = round(
            row["duration_quarter"] * curr_quarter_length, ROUNDING_VALUE
        )

        # Get the timestamp
        df_score.at[i, "tstamp"] = round(next_tstamp, ROUNDING_VALUE)

        if row["qstamp"] != max_qstamp:
            # Calculate the timestamp for the next note event
            diff = df_score.loc[i + 1, "qstamp"] - row["qstamp"]
            next_tstamp += diff*curr_quarter_length

    print("Conversion successful.")

    return df_score


def score_to_lightweight_df(
    score_file: Union[str, Path],
    mm_file: Optional[Union[str, Path]] = None
) -> pd.DataFrame:
    """
    Convert a score into a 'lightweight' data frame that summarises the
    score (which instruments are playing at each point in time) and
    save as a .csv file.

    Notes:
        It is highly preferred that the measure map is used to
        produce the lightweight data frame since Music21's 
        '.expandRepeats()' seems to not expand repeats with voltas
        for the first stave in some scores.
        Each cell in an instrument column indicates the highest pitch
        being played at that time, or "r" if no pitch playing.
        Pitches are given in Scientific Pitch Notation instead of MIDI
        note numbers for readability.
        Doesn't take into account fermatas, accelerandos, ritardandos,
        etc.
        Ignores grace notes.
        All float columns are rounded to 4 d.p.

    Args:
        score_file: The path to the score's MusicXML file.
        mm_file: The path to the score's measure map file. Default = 
            None.

    Returns:
        df_score_lw: A data frame containing 'lightweight' information 
            for each qstamp.
            Columns:
                qstamp (float): The time offset in quarter notes with
                    repeats expanded.
                tstamp (float): The time offset in seconds with repeats
                    expanded.
                measure (int): The measure number.
                beat (float): The beat in the measure at which the note
                    is played.
                {instrument 1} (str): The highest pitch being played by
                    instrument 1 at the corresponding qstamp.
                ...
                {instrument n} (str): The highest pitch being played by
                    instrument n at the corresponding qstamp.

    Raises:
        ValueError: If there are notes at a particular qstamp with 
            different beat values. Each qstamp should match to one
            measure number and beat value only.
    """
    # Load in MusicXML file for score
    score_file = validate_path(score_file)
    score = converter.parse(score_file)
    if not isinstance(score, Score):
        raise ValueError(
            "Error: Score is not of type 'music21.Score'."
        )
    score = cast(Score, score)

    if mm_file:
        # Load in measure map file for score
        mm_file = validate_path(mm_file)
        measure_map = pd.read_json(mm_file)
        df_score = score_measure_map_to_df(score, measure_map)
    else:
        df_score = score_to_df(score.expandRepeats())

    # Test if each qstamp has a unique beat value
    # This should always be the case but Music21 has some bugs
    beat_test = (
        df_score.groupby("qstamp")["beat"]
        .apply(pd.Series.nunique)
        .reset_index()
    )
    beat_test_bool = beat_test["beat"] != 1
    if beat_test_bool.any():
        csv_file = score_file.with_suffix(".csv")
        df_score.to_csv(csv_file, index=False)
        raise ValueError(
            "Error: There are notes at qstamp(s) " +
            ", ".join([
                str(q) for q in
                beat_test.loc[beat_test_bool, "qstamp"].unique()
            ]) +
            " with different beat values.\nSaving full score data frame at '" +
            csv_file.as_posix() +
            "' for inspection."
        )

    # Get a list of pitches for each instrument at each qstamp
    df_score_lw = (
        df_score.groupby(["qstamp", "tstamp", "measure", "beat",
                          "instrument"])["pitch"]
        .apply(list)
        .reset_index()
        .pivot_table(
            index=["qstamp", "tstamp", "measure", "beat"],
            columns="instrument",
            values="pitch",
            aggfunc="first"
        )
        .reset_index()
    )
    df_score_lw.columns = df_score_lw.columns.values

    # Add columns for instruments with no notes and reorder the columns
    # based on appearance in the score
    columns = ["qstamp", "tstamp", "measure", "beat"]
    for part in score.parts:
        part_name = part.partName
        if part_name not in df_score_lw.columns:
            df_score_lw[part_name] = np.nan
        if part_name not in columns:
            columns.append(part_name)
    df_score_lw = df_score_lw[columns]

    # Get the highest pitch for each cell containing multiple pitches
    for col in df_score_lw.columns[4:]:
        df_score_lw[col] = df_score_lw[col].apply(
            lambda x: max(x) if isinstance(x, list) else x
        )

    final_index = df_score_lw.index[-1]
    # Iterate through the instruments
    for instrument in df_score_lw.columns[4:]:
        done = False
        i = 0
        while not done:
            row = df_score_lw.loc[i, :]
            # Get the highest pitch being played by the instrument
            note_mnn = cast(int, row[instrument])
            if pd.isna(note_mnn):
                # If no highest pitch, then there is a rest
                df_score_lw.loc[i, instrument] = "r"
            else:
                # Convert MIDI note number to Scientific Pitch Notation
                note_spn = pitch.Pitch(note_mnn).nameWithOctave
                df_score_lw.loc[i, instrument] = note_spn
                # Get note duration in quarter notes
                note_dur_quarter = df_score.loc[
                    ((df_score["qstamp"] == row["qstamp"]) &
                     (df_score["instrument"] == instrument) &
                     (df_score["pitch"] == note_mnn)),
                    "duration_quarter"
                ]
                if len(note_dur_quarter) != 0:
                    note_dur_quarter = note_dur_quarter.unique()[0].item()
                    # Get qstamp that note ends on
                    note_end_qstamp = row["qstamp"] + note_dur_quarter
                    if i < final_index:
                        j = i + 1
                        # Fill the cells up until this qstamp with this
                        # note, so missing values indicate rests
                        while df_score_lw.loc[j, "qstamp"] < note_end_qstamp:
                            df_score_lw.loc[j, instrument] = note_spn
                            j += 1
                            if j > final_index:
                                break
            i += 1
            if i > df_score_lw.index[-1]:
                done = True

    # Create .csv file
    csv_file = score_file.with_suffix(".csv")
    df_score_lw.to_csv(csv_file, index=False)

    print(f"\nThe lightweight .csv was saved to '{csv_file}'.")

    return df_score_lw

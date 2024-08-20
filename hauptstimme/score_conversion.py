"""
NAME
===============================
Score Conversion (score_conversion.py)


BY
===============================
Matt Blessing, 2024


LICENCE:
===============================
Creative Commons Attribution-ShareAlike 4.0 International License
https://creativecommons.org/licenses/by-sa/4.0/


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
import pandas as pd
from music21 import (
    converter, chord, expressions, note, stream, tempo, meter, pitch
)
from pathlib import Path
from hauptstimme.constants import ROUNDING_VALUE


def score_measure_map_to_df(score, measure_map):
    """
    Convert a score and measure map into a data frame containing
    information about all note events.

    Notes:
        Doesn't take into account fermatas, accelerandos, ritardandos,
        etc.
        Ignores grace notes.
        All float columns are rounded to 4 d.p.

    Args:
        score (music21.stream.Score): A music21 score.
        measure_map (pd.DataFrame): A measure map for the score.

    Returns:
        df_score (pd.DataFrame): A data frame containing information
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
    """
    print("\nConverting score to a data frame containing all note events...")

    df_score = pd.DataFrame(
        columns=["score_qstamp", "qstamp", "tstamp", "measure", "beat",
                 "instrument", "duration_quarter", "duration", "pitch",
                 "velocity"]
    )

    tempos = {}
    time_sigs = {}

    # Get initial time signature
    # This is needed now in case the initial tempo is defined as a text
    # expression before the time signature is defined
    curr_time_sig = None
    for n in score.parts[0].flatten():
        if isinstance(n, meter.TimeSignature):
            time_sigs[n.measureNumber] = n
            curr_time_sig = n
            break

    for part_num, part in enumerate(score.parts):
        part = part.toSoundingPitch()
        instrument_name = part.partName
        elements = part.flatten()

        for n in elements:
            score_qstamp = round(float(n.offset), ROUNDING_VALUE)
            measure = n.measureNumber
            beat = round(float(n.beat), ROUNDING_VALUE)

            # Skips things like instrument etc.
            if n.measureNumber is None:
                continue

            # Deal with issue with beats when there are multiple voices
            # Manually calculate beat
            measure_obj = part.measure(measure)
            num_voices = len(measure_obj.voices)
            if num_voices > 0:
                beat = (1 + (n.offset - measure_obj.offset) /
                        curr_time_sig.beatDuration.quarterLength)
                beat = round(float(beat), ROUNDING_VALUE)

            ################################################
            # Don't think this is needed
            if isinstance(elements, stream.Measure):
                print("MEASURE", elements)
                score_qstamp += elements.offset
            ################################################

            if part_num == 0:
                if isinstance(n, meter.TimeSignature):
                    time_sigs[measure] = n
                    curr_time_sig = n
                    continue

                if isinstance(n, tempo.MetronomeMark):
                    # Get quarter note BPM directly from tempo marking
                    tempos[measure] = n.getQuarterBPM()
                    print("TEMPO1", tempos[measure], measure)
                    continue
                # If a tempo marking is written as a text expression
                # (e.g., 'Adagio')
                elif isinstance(n, expressions.TextExpression):
                    # Get tempo's default BPM
                    bpm = tempo.defaultTempoValues.get(n.content.lower())
                    if bpm:
                        # Convert BPM to quarter note BPM
                        quarter_bpm = bpm * curr_time_sig.denominator / 4
                        tempos[measure] = quarter_bpm
                        print("TEMPO2", tempos[measure], measure)
                    continue

                ################################################
                # Don't think I need these
                elif isinstance(n, tempo.TempoIndication):
                    if isinstance(n, tempo.MetricModulation):
                        if n.oldMetronome.number:
                            tempos[measure] = n.oldMetronome.number
                            print("TEMPO3", tempos[measure], measure)
                    elif n.number:
                        tempos[measure] = n.number
                        print("TEMPO4", tempos[measure], measure)
                    elif n.numberSounding:
                        tempos[measure] = n.numberSounding
                        print("TEMPO5", tempos[measure], measure)
                ################################################

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
                        [df_score, pd.DataFrame(row, index=[0])])
            elif isinstance(n, chord.Chord):
                # Add row for each note in chord
                for chord_note in n:
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
                        [df_score, pd.DataFrame(row, index=[0])])

    df_score.sort_values("qstamp", inplace=True)
    df_score.reset_index(drop=True, inplace=True)

    # If no tempo info then use default of 120 BPM
    if 1 not in tempos:
        tempos = {1: 120.0}

    # Get a list indicating the order in which the measures are played
    # when expanding repeats
    measures = []
    curr_id = int(measure_map.iloc[0, 0])
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
        tempos[measure] = curr_tempo

    df_score["qstamp"] = [list() for _ in range(len(df_score))]
    df_score["tstamp"] = [list() for _ in range(len(df_score))]
    # Get the indices of every note event at each score qstamp
    df_score_qstamp_measure = (
        df_score.groupby(["score_qstamp", "measure"])
        .apply(lambda x: x.index.to_list())
        .reset_index()
        .rename(columns={0: "indices"})
    )
    max_score_qstamp = df_score["score_qstamp"].max()
    next_qstamp = 0
    next_tstamp = 0.
    for measure in measures:
        # Get current quarter note BPM
        curr_quarter_bpm = tempos[measure]
        # Get current length of a quarter note
        curr_quarter_length = 60 / curr_quarter_bpm

        # Iterate through all note events in the measure
        df_measure_notes = df_score_qstamp_measure[
            df_score_qstamp_measure["measure"] == measure
        ]
        for i, row in df_measure_notes.iterrows():
            # Get the note duration in seconds
            dur = df_score.loc[row["indices"], "duration_quarter"]
            df_score.loc[row["indices"], "duration"] = round(
                dur * curr_quarter_length,
                ROUNDING_VALUE
            )

            # Get a list of qstamps and tstamps for each note
            # There can be more than one due to repeats
            for index in row["indices"]:
                df_score.loc[index, "qstamp"].append(next_qstamp)
                df_score.loc[index, "tstamp"].append(round(next_tstamp,
                                                           ROUNDING_VALUE))

            if row["score_qstamp"] != max_score_qstamp:
                # Calculate the timestamp for the next note event
                diff = (df_score_qstamp_measure.iloc[i + 1]["score_qstamp"]
                        - row["score_qstamp"])
                next_qstamp += diff
                next_tstamp += diff*curr_quarter_length

    # Convert rows containing lists into multiple rows
    df_score = df_score.explode(["qstamp", "tstamp"]).apply(
        pd.to_numeric, errors="ignore").reset_index(drop=True)

    print("Conversion successful.")

    return df_score


def score_to_df(score):
    """
    Convert a score into a data frame containing information about all note
    events.

    Notes:
        Doesn't take into account fermatas, accelerandos, ritardandos,
        etc.
        Ignores grace notes.
        All float columns are rounded to 4 d.p.
        Like the above function, but doesn't obtain the `score_qstamp`
        column.

    Args:
        score (music21.stream.Score): A music21 score.

    Returns:
        df_score (pd.DataFrame): A data frame containing information
            for each note event.
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
    """
    print("\nConverting score to a data frame containing all note events...")

    df_score = pd.DataFrame(
        columns=["qstamp", "tstamp", "measure", "beat", "instrument",
                 "duration_quarter", "duration", "pitch", "velocity"]
    )

    tempos = {}
    time_sigs = {}

    # Get initial time signature
    # This is needed now in case the initial tempo is defined as a text
    # expression before the time signature is defined
    curr_time_sig = None
    for n in score.parts[0].flatten():
        if isinstance(n, meter.TimeSignature):
            time_sigs[n.measureNumber] = n
            curr_time_sig = n
            break

    for part_num, part in enumerate(score.parts):
        part = part.toSoundingPitch()
        instrument_name = part.partName
        elements = part.flatten()

        for n in elements:
            qstamp = round(float(n.offset), ROUNDING_VALUE)
            measure = n.measureNumber
            beat = round(float(n.beat), ROUNDING_VALUE)

            # Skips things like instrument etc.
            if n.measureNumber is None:
                continue

            # Deal with issue with beats when there are multiple voices
            # Manually calculate beat
            measure_obj = part.measure(measure)
            num_voices = len(measure_obj.voices)
            if num_voices > 0:
                beat = (1 + (n.offset - measure_obj.offset) /
                        curr_time_sig.beatDuration.quarterLength)
                beat = round(float(beat), ROUNDING_VALUE)

            ################################################
            # Don't think this is needed
            if isinstance(elements, stream.Measure):
                print("MEASURE", elements)
                qstamp += elements.offset
            ################################################

            if part_num == 0:
                if isinstance(n, meter.TimeSignature):
                    time_sigs[measure] = n
                    curr_time_sig = n
                    continue

                if isinstance(n, tempo.MetronomeMark):
                    # Get quarter note BPM directly from tempo marking
                    tempos[measure] = n.getQuarterBPM()
                    print("TEMPO1", tempos[measure], measure)
                    curr_tempo = tempos[measure]
                    continue
                # If a tempo marking is written as a text expression
                # (e.g., 'Adagio')
                elif isinstance(n, expressions.TextExpression):
                    # Get tempo's default BPM
                    bpm = tempo.defaultTempoValues.get(n.content.lower())
                    if bpm:
                        # Convert BPM to quarter note BPM
                        quarter_bpm = (
                            bpm * curr_time_sig.beatDuration.quarterLength
                        )
                        tempos[measure] = quarter_bpm
                        print("TEMPO2", tempos[measure], measure)
                    continue

                ################################################
                # Don't think I need these
                elif isinstance(n, tempo.TempoIndication):
                    if isinstance(n, tempo.MetricModulation):
                        if n.oldMetronome.number:
                            tempos[measure] = n.oldMetronome.number
                            print("TEMPO3", tempos[measure], measure)
                    elif n.number:
                        tempos[measure] = n.number
                        print("TEMPO4", tempos[measure], measure)
                    elif n.numberSounding:
                        tempos[measure] = n.numberSounding
                        print("TEMPO5", tempos[measure], measure)
                ################################################

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
                        [df_score, pd.DataFrame(row, index=[0])])
            elif isinstance(n, chord.Chord):
                # Add row for each note in chord
                for chord_note in n:
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
                        [df_score, pd.DataFrame(row, index=[0])])

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
        tempos[measure] = curr_tempo

    max_qstamp = df_score["qstamp"].max()
    next_tstamp = 0.
    for i, row in df_score.iterrows():
        # Get current quarter note BPM
        curr_quarter_bpm = tempos[row["measure"]]
        # Get current length of a quarter note
        curr_quarter_length = 60 / curr_quarter_bpm

        # Get the note duration in seconds
        df_score.loc[i, "duration"] = round(
            row["duration_quarter"]*curr_quarter_length, ROUNDING_VALUE)

        # Get the timestamp
        df_score.loc[i, "tstamp"] = round(next_tstamp, ROUNDING_VALUE)

        if row["qstamp"] != max_qstamp:
            # Calculate the timestamp for the next note event
            diff = df_score.loc[i + 1]["qstamp"] - row["qstamp"]
            next_tstamp += diff*curr_quarter_length

    print("Conversion successful.")

    return df_score


def score_to_lightweight_df(score_file):
    """
    Convert a score into a 'lightweight' data frame that summarises the
    score (which instruments are playing at each point in time) and
    save as a .csv file.

    Notes:
        Each cell in an instrument column indicates the highest pitch
        being played at that time, or "r" if no pitch playing.
        Pitches are given in Scientific Pitch Notation instead of MIDI
        note numbers for readability.
        Doesn't take into account fermatas, accelerandos, ritardandos,
        etc.
        Ignores grace notes.
        All float columns are rounded to 4 d.p.

    Args:
        score_file (str): The local filename of the score as a MusicXML
            file.

    Returns:
        df_score_lw (pd.DataFrame): A data frame containing
            'lightweight' information for each qstamp.
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
    score = converter.parse(score_file)

    df_score = score_to_df(score.expandRepeats())
    score_file_path = Path(score_file)
    csv_file = score_file_path.with_suffix(".full.csv")
    df_score.to_csv(csv_file, index=False)

    # Test if each qstamp has a unique beat value
    # This should always be the case but Music21 has some bugs
    beat_test = (
        df_score.groupby("qstamp")["beat"]
        .apply(lambda x: len(x.unique()))
        .reset_index()
    )
    if (beat_test["beat"] != 1).any():
        raise ValueError("Error: There are notes at a particular qstamp " +
                         "with different beat values.")

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

    # Reorder the columns based on appearance in the score
    columns = ["qstamp", "tstamp", "measure", "beat"]
    for part in score.parts:
        part_name = part.partName
        if part_name in df_score_lw.columns and part_name not in columns:
            columns.append(part_name)
    df_score_lw = df_score_lw[columns]

    # Get the highest pitch for each cell containing multiple pitches
    for col in df_score_lw.columns[4:]:
        df_score_lw[col] = df_score_lw[col].apply(
            lambda x: max(x) if isinstance(x, list) else x)

    # Iterate through the instruments
    for instrument in df_score_lw.columns[4:]:
        done = False
        i = 0
        while not done:
            row = df_score_lw.loc[i, :]
            # Get the highest pitch being played by the instrument
            note_mnn = row[instrument]
            if pd.isna(note_mnn):
                # If no highest pitch, then there is a rest
                df_score_lw.loc[i, instrument] = "r"
            else:
                # Convert MIDI note number to Scientific Pitch Notation
                note_spn = pitch.Pitch(note_mnn).nameWithOctave
                df_score_lw.loc[i, instrument] = note_spn
                # Get note duration in quarter notes
                note_dur_quarter = df_score.loc[(
                    (df_score["qstamp"] == row["qstamp"]) &
                    (df_score["instrument"] == instrument) &
                    (df_score["pitch"] == note_mnn)), "duration_quarter"]
                if len(note_dur_quarter) != 0:
                    note_dur_quarter = note_dur_quarter.unique()[0].item()
                    # Get qstamp that note ends on
                    note_end_qstamp = row["qstamp"] + note_dur_quarter
                    if i < df_score_lw.index[-1]:
                        j = i + 1
                        # Fill the cells up until this qstamp with this
                        # note, so missing values indicate rests
                        while df_score_lw.loc[j, "qstamp"] < note_end_qstamp:
                            df_score_lw.loc[j, instrument] = note_spn
                            j += 1
            i += 1
            if i > df_score_lw.index[-1]:
                done = True

    # Create .csv file
    score_file_path = Path(score_file)
    csv_file = score_file_path.with_suffix(".csv")
    df_score_lw.to_csv(csv_file, index=False)

    print(f"\nThe lightweight .csv was saved to '{csv_file}'.")

    return df_score_lw

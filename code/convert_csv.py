import numpy as np
from music21 import *
import pandas as pd
import utils
from collections import Counter


pd.options.display.max_columns = 100
pd.options.display.max_rows = 100
pd.options.display.max_colwidth = 100
pd.options.display.width = 200
pd.set_option('display.expand_frame_repr', False)


"""
Dictionary of valid clefs as below.

string family 
    Violin: treble 
    Viola: treble, alto 
    Cello (violoncello): treble, tenor, bass 
    Double bass: bass, bass8vb 

woodwind family 
    Flute: treble 
    Oboe: treble 
    Clarinet: treble (yes, exclusively, even when E3) 
    Bassoon: bass 

brass family 
    Trumpet: treble 
    French horn: treble, bass 
    Trombone: tenor, bass 
    Tuba: bass 

percussion family 
    Only timpani matter for us: bass clef 
"""

clef_dict = {
    "Violin": [clef.TrebleClef(), clef.Treble8vaClef()],
    "Viola": [clef.TrebleClef(), clef.AltoClef()],
    "Violoncello": [clef.TrebleClef(), clef.TenorClef(), clef.BassClef()],
    "Contrabass": [clef.BassClef(), clef.Bass8vbClef()],

    "Flute": [clef.TrebleClef(), clef.Treble8vaClef()],
    "Oboe": [clef.TrebleClef()],
    "Clarinet": [clef.TrebleClef()],
    "Bassoon": [clef.BassClef()],
    "Contrabassoon": [clef.BassClef()],

    "Trumpet": [clef.TrebleClef()],
    "Horn": [clef.TrebleClef(), clef.BassClef()],
    "Trombone": [clef.TenorClef(), clef.BassClef()],
    "Tuba": [clef.BassClef()],

    "Timpani": [clef.BassClef()]
}



def convert_mxml_to_csv(s, output_file_name, qlength=None, use_default_tempo=True):
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

    parts = s.parts.stream()
    instruments = [part.getInstrument().instrumentName for part in parts.parts]
    
    # give each instrument a unique name, where each duplicate is appended with a number, starting from 1
    dup = dict(Counter(instruments))
    uniques = np.unique(instruments)
    instruments = [key if i == 0 else key + " " + str(i+1) for key in uniques for i in range(dup[key])]

            

    df = pd.DataFrame(columns=['qstamp', 'bar', 'beat'] + instruments)

    tempos = {}
    time_sigs = {}


    parsed_parts = []
    for partnum, part in enumerate(parts.parts):
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

 
            current_time_sig = None
            for n in elements:  # get first time signature
                if n.offset != 0:
                    break
                if isinstance(n, meter.TimeSignature):
                    time_sigs[n.measureNumber] = n
                    current_time_sig = n
                    break
            for n in elements:
                qstamp = n.offset
                if isinstance(elements, stream.Measure):
                    qstamp += elements.offset
                if partnum == 0:
                    if isinstance(n, meter.TimeSignature):
                        time_sigs[n.measureNumber] = n
                        current_time_sig = n
                        continue

                    # Tempo texts
                    elif isinstance(n, expressions.TextExpression):
                        mm = tempo.defaultTempoValues.get(n.content.lower())
                        if mm is not None:
                            tempos[n.measureNumber] = mm
                        continue
                    # Different types of TempoIndications
                    elif isinstance(n, tempo.TempoIndication):
                        if isinstance(n, tempo.MetricModulation):
                            if n.oldMetronome.number:
                                tempos[n.measureNumber] = n.oldMetronome.number
                        elif n.number:
                            tempos[n.measureNumber] = n.number
                        elif n.numberSounding:
                            # numberSounding gets number of Metronome that is used but not displayed, meaning bpm in quarter notes

                            # search current bar for time signature, if not found, use previous time signature
                            current_bar = [x for x in elements if x.measureNumber == n.measureNumber]
                            if current_bar:
                                current_bar = [x for x in current_bar if isinstance(x, meter.TimeSignature)]
                                if current_bar:
                                    current_time_sig = current_bar[0]


                            tempos[n.measureNumber] = n.numberSounding*current_time_sig.denominator/4  

                        continue
                
                if isinstance(n, note.Note):
                    cell_input = n.nameWithOctave
                elif isinstance(n, chord.Chord):
                    cell_input = [chord_note.nameWithOctave for chord_note in n][-1]
                elif isinstance(n, note.Rest):
                    cell_input = 'r'
                elif "Clef" in n.classes:
                    if not accepted_clefs is None:
                        accepted = n in accepted_clefs
                        if not accepted:
                            print(f"Invalid clef {n} found in bar {n.measureNumber}")
                    continue
                else:
                    continue
                if qstamp in df['qstamp'].values:
                    df.loc[df['qstamp'] == qstamp, instrument_name] = cell_input
                else:
                    new_row = {'qstamp': qstamp,
                            'bar': n.measureNumber,
                            'beat': n.beat,
                            instrument_name: cell_input}
                    df = pd.concat([df, pd.DataFrame(new_row, index=[0])], ignore_index=True)
    df.sort_values(by=['qstamp'], inplace=True)
    df.reset_index(drop=True, inplace=True)


    # check if TempoIndication exists
    # If no TempoIndication in MusicXML, ask for user input
    if not tempos:
        if not use_default_tempo:
            print("No TempoIndication found, would you like to input tempos? (y/n)")
            user_input = input()
            if user_input.lower() == 'y':
                """
                user input: bar, bpm ('q' when finished, if empty use default)        
                """
                tempos = {}
                while True:
                    bar_input = input("bar: (q to finish)")
                    if bar_input == 'q':
                        break
                    bpm_input = input(f"bpm from bar {bar_input}: ")
                    if bpm_input == 'q':
                        break
                    if not bar_input.isdigit() or not bpm_input.isdigit():
                        print("Invalid input")
                        continue
                    
                    bar_num = int(bar_input)
                    tempos[bar_num] = int(bpm_input)
                # display tempos

        # if no user input, use default
        if not tempos:
            print("Using default")
            """
               default assign
               X/2: halfnote=60BPM; 
               X/4 = q=120BPM etc.
               time_sig base * 30 = bpm
            """
            ts_to_bpm = lambda bar_num: time_sigs.get(max(k for k in time_sigs.keys() if k <= bar_num)).denominator * 30
            tempos = {k: ts_to_bpm(k) for k, v in time_sigs.items()}
    # get time_offset from tempos and time_sigs
    def get_time_offset(offset, ts, bpm):
        if qlength:
            quarter_length = qlength
        else:
            quarter_length = 60 / (bpm / (ts.denominator / 4))
        # quarter_length = 60 / bpm
        # then get time_offset
        return offset * quarter_length

    curr_ts = time_sigs.get(0.0)
    curr_bpm = tempos.get(0.0)
    curr_time_offset = 0.0
    for i, row in df.iterrows():
        if row['bar'] in time_sigs:
            curr_ts = time_sigs[row['bar']]
        if row['bar'] in tempos:
            curr_bpm = tempos[row['bar']]
        # curr_time_offset += difference between current and next qstamp
        if i == 0:
            df.at[i, 'time_offset'] = 0
        else:
            diff = row['qstamp'] - df.iloc[i-1]['qstamp']
            curr_time_offset += get_time_offset(diff, curr_ts, curr_bpm)
        df.loc[i, "time_offset"] = curr_time_offset

    # time_offset column: in seconds
    df.ffill(inplace=True)  # fill NaNs with previous value
    df.to_csv(output_file_name, index=False)
    print("saved to", output_file_name)
    return df


if __name__ == '__main__':
    filename = 'scores/Brahms_Symphony_1_first_movement.mxl'
    score = converter.parse(filename).expandRepeats()

    dataframe = convert_mxml_to_csv(score, f"{filename.split('/')[1][:-4]}.csv")
    dataframe = dataframe.set_index('qstamp')
    print(dataframe)
    print(dataframe.columns)



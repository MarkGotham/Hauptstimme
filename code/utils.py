import inflect
import re
from music21 import *
import pandas as pd
import numpy as np
p = inflect.engine()


def find_nearest(arr, x):
    arr = np.asarray(arr)
    idx = (np.abs(arr - x)).argmin()
    return arr[idx]


def depluralize(word):
    return p.singular_noun(word) or word


def get_lookup_name(instrument_name):
   
    #lookup_name = depluralize(max(instrument_name.split(), key=len))
    lookup_name = depluralize(max(instrument_name.split(), key=len))

    return lookup_name


def sort_by_pitch(all_notes):
    sort_by_notes = (lambda l: sorted(l,  # Sort the list
                                      key=lambda i:  # Key used to sort the list, takes a single string as input
                                      # Outputs an integer; the lower the integer, the lower the note
                                      12 * int(i[-1])  # Multiply the octave number by 12
                                      + " D EF G A B".find(i[0])  # Add the number of the note within that octave;
                                      # C = -1 up to B = 10
                                      - ord(i[1]) / 48  # Subtract the ASCII code of the second character;
                                      # Ends up with sharpened notes having higher values than
                                      # no-accidental ones, which have a higher value than flattened ones
                                      )
                     )

    minus_signs = re.compile(r'-')
    notes_minus = [minus_signs.sub('b', note) for note in all_notes]  # replace minus signs with b for the sort function

    sorted_notes_minus = sort_by_notes(notes_minus)
    sorted_notes = [re.compile(r'b').sub('-', note) for note in sorted_notes_minus]  # replace b with minus signs

    return sorted_notes
    # TODO: edit lambda function so this is not necessary


def convert_mxml_to_csv(file, output_file):
    """
    Convert mxml -> csv with this format:
    qstamp | bar | beat | instrument1 | instrument2 | instrument3 |

    - if note lasts longer than a qstamp, it will be repeated in the next row
    - scientific pitch notation
    - bar is integer
    - qstamp and beat are floats, depends on the rhythm, increment may not be constant
        e.g. (1, 2, 2.5, 3, 4, 5, 6, 7.25, 7.5, 7.75, 8)
    - if chord, cell will contain array of notes
    - if qstamp exists, find current instrument column and rewrite cell
    - r to represent rest
    """

    score = converter.parse(file)
    parts = instrument.partitionByInstrument(score)
    print(len(parts))
    instruments = [part.getInstrument().instrumentName for part in parts.parts]

    df = pd.DataFrame(columns=['qstamp', 'bar', 'beat'] + instruments)

    for part in parts:
        print(part)
        instrument_name = part.getInstrument().instrumentName
        notes = part.flat.notes
        for note in notes:
            if note.isChord:  # array of notes as strings
                df[instrument_name] = df[instrument_name].astype(object)
                notes_array = [chord_note.nameWithOctave for chord_note in note]
                print(notes_array)
                if note.offset in df['qstamp'].values:
                    try:
                        df.loc[df['qstamp'] == note.offset, instrument_name] = str(notes_array)
                    except ValueError as e:
                        print("ValueError: could not assign chord to qstamp")
                        print(df[df['qstamp'] == note.offset])
                        print(df.loc[df['qstamp'] == note.offset, instrument_name])
                        print("note.offset:", note.offset)
                        print("df['qstamp'].values:", df['qstamp'].values)
                        print(notes_array)
                        print(e)
                        input()

                else:
                    df = df.append({'qstamp': note.offset, 'bar': note.measureNumber, 'beat': note.beat,
                                    instrument_name: notes_array}, ignore_index=True)
            else:  # string of single note
                if note.offset in df['qstamp'].values:
                    df.loc[df['qstamp'] == note.offset, instrument_name] = note.nameWithOctave
                else:
                    new_row = {'qstamp': note.offset,
                               'bar': note.measureNumber,
                               'beat': note.beat,
                               instrument_name: note.nameWithOctave}
                    df = df.append(new_row, ignore_index=True)

    df = df.fillna(method='ffill')

    df = df.sort_values(by=['qstamp', 'bar', 'beat'])
    df.to_csv(output_file, index=False)
    return df







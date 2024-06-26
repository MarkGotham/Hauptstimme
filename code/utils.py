import inflect
import re
import numpy as np
import pandas as pd
p = inflect.engine()
from pathlib import Path
from music21 import instrument

CODE_PATH = Path(__file__).parent
REPO_PATH = CODE_PATH.parent
CORPUS_PATH = REPO_PATH / "corpus"


def get_corpus_files(
    sub_corpus_path: Path = CORPUS_PATH,
    file_name: str = "*.mxl",
) -> list[Path]:
    """
    Get and return paths to files matching conditions for the given file_name.

    Args:
        sub_corpus_path: the sub-corpus to run.
            Defaults to CORPUS_PATH (all corpora).
            Accepts any sub-path thereof.
            Checks ensure both that the path `.exists()` and `.is_relative_to(CORPUS_FOLDER)`
        file_name (str): select all files matching this file_name. Defaults to "score.mxl".
        Alternatively, specify either an exact file name or
        use the wildcard "*" to match patterns, e.g., "*.mxl" for all .mxl files

    Returns: list of file paths.
    """

    assert sub_corpus_path.is_relative_to(CORPUS_PATH)
    assert sub_corpus_path.exists()
    return [x for x in sub_corpus_path.rglob(file_name)]


def get_ground_truth(haupstimme_path=REPO_PATH / "test" / "annotations.csv", csvfile=REPO_PATH / "test" / "score.csv", return_type='qstamp'):

    dataframe = pd.read_csv(csvfile)

    haupstimme = pd.read_csv(haupstimme_path)
    haupstimme['measure'] = haupstimme['measure'].astype(int)
    dataframe['bar'] = dataframe['bar'].astype(int)
    

    # columns: measure,beat,label,partName,partNum
    haupstimme_segment_qstamps = set()
    haupstimme['beat'] = haupstimme['beat'].astype(float)
    if dataframe['beat'].dtype == 'O':
        dataframe['beat'] = dataframe['beat'].apply(eval)
    dataframe.round(2)
    haupstimme.round(2)


    for i, row in haupstimme.iterrows():
        samebar = dataframe[(dataframe['bar'] == row['measure'])]
        df_closest = samebar.iloc[(samebar['beat'].astype(float)-float(row['beat'])).abs().argsort()]
        """
        because there can be multiple qstamps/timestamps that correspond to the same bar same beat when expandRepeats()
        is used in music21, e.g. in bar 200, end repeat sign, we go back to bar 40, but qstamp keeps increasing
        """
        closest_value = df_closest['beat'].values[0]
        df_closest = df_closest[df_closest['beat'] == closest_value]
        for i in df_closest[return_type].values:
            haupstimme_segment_qstamps.add(i)
    haupstimme_segment_qstamps = list(haupstimme_segment_qstamps)
    if isinstance(haupstimme_segment_qstamps, str):
        haupstimme_segment_qstamps = sorted(haupstimme_segment_qstamps, key=lambda x: eval(x))
    else:
        haupstimme_segment_qstamps = sorted(haupstimme_segment_qstamps)
    return haupstimme_segment_qstamps


def get_melody_assignments(haupstimme_path=REPO_PATH / "test" / "annotations.csv", csvfile=REPO_PATH / "test" / "score.csv"):
    score_df = pd.read_csv(csvfile)
    haupstimme_df = pd.read_csv(haupstimme_path)
    score_instruments = score_df.columns[3:-1]
    score_instruments_abbr = [instrument.fromString(x).instrumentAbbreviation for x in score_instruments]

    melody_assignments = [row[1]['partName'] for row in haupstimme_df.iterrows()]
    melody_assignment_indices = [score_instruments_abbr.index(x) for x in melody_assignments]
    return melody_assignment_indices




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

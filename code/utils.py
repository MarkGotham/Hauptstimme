import inflect
import re
import numpy as np
p = inflect.engine()
from pathlib import Path

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

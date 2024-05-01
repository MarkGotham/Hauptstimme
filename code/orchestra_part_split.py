"""
NAME
===============================
Orchestra part split (orchestra_part_split.py)


BY
===============================
Mark Gotham


LICENCE:
===============================
Creative Commons Attribution-ShareAlike 4.0 International License
https://creativecommons.org/licenses/by-sa/4.0/


ABOUT:
===============================
Orchestral _scores_ typically place pairs of like parts on the same stove
(both flute 1 and 2, for example).
Orchestral _parts_ however are provided separately for those two flute players.
While proprietary software handles this dual layout,
open source libraries do not.
Music21, for example, has a `voicesToPart` function
specifically for splitting two voices within a measure,
but this is only a small part of the consideration.
This module handles a wider set of considerations.

For details of included vs not included functionality, see `split_part`.

"""

import copy

from music21 import converter, instrument, key, layout, stream
from pathlib import Path, PurePath


CODE_PATH = Path(__file__).parent
REPO_PATH = CODE_PATH.parent


def split_part(
        p: stream.Part,
        handle_part_name: bool = True
) -> tuple[stream.Part, stream.Part]:
    """
    This script creates a duplicate part
    and then filters the part and the duplicate to remove double voices and chords.
    The first part retains the top voice and top note of a chord,
    the second part retains lowest voice and lowest note in any chords.
    This should provide part of the solution with no new errors added.

    Text such as `solo`, `a1`, and `a2` and similar markings which are encoded only as text
    are simply reproduced and not processed.
    This may change in the future (e.g., excluding `a1` parts from the second voice).
    Then again, it's arguably better to err on the side of too much.
    It's quite easy to verify and delete passages marked "a1" manually,
    and much more difficulty to notice that something absent is missing.

    3+ parts on the same stave are not handled.
    It is rare (and arguably 'wrong') to do this on wind parts.
    As such, any third middle voice that is encoded is ignored/removed.

    A note to those looking at how this works in practice:
    music21 counts
    _pitches from the bottom up_ and
    _voices from the top down_.

    @param p: The input part.
    @return: The two output parts, combined in a list.
    """
    new_part_1 = copy.deepcopy(p)
    new_part_2 = copy.deepcopy(p)

    # Chords. NB counting bottom up
    for n in new_part_1.recurse().notesAndRests:
        if n.isChord:
            pitches = n.pitches
            for i in range(len(pitches) - 1):
                n.remove(pitches[i])  # remove pitch 1 to n-1

    for n in new_part_2.recurse().notesAndRests:
        if n.isChord:
            pitches = n.pitches
            for i in range(1, len(pitches)):
                n.remove(pitches[i])  # remove pitch 2 to n
        if n.lyric:
            print(f"*** removing lyric {n.lyric} from {new_part_2.partName}, measure {n.measureNumber}")
            n.lyric = None

    # Voices NB counting top down
    for m in new_part_1.getElementsByClass(stream.Measure):
        if m.hasVoices:  # len(m.voices) > 1
            for i in range(1, len(m.voices)):
                m.remove(m.voices[i])  # remove voices 2 to n
            m.flattenUnnecessaryVoices()

    for m in new_part_2.getElementsByClass(stream.Measure):
        if m.hasVoices:  # len(m.voices) > 1
            for i in range(len(m.voices) - 1):
                m.remove(m.voices[i])  # remove voices 1 to n-1
            m.flattenUnnecessaryVoices()

    if handle_part_name:
        i = instrument.fromString(p.partName)
        abbrev = i.instrumentAbbreviation
        new_part_1.partName = i.instrumentName + " 1"  # almost all cases, manual change needed for horns 3-4.
        new_part_2.partName = i.instrumentName + " 2"
        new_part_1.partAbbreviation = abbrev + " 1"
        new_part_2.partAbbreviation = abbrev + " 2"

    return new_part_1, new_part_2


def process_one_score(
    path: Path = REPO_PATH / "test",
    file_name: str = "score.mxl",
) -> None:
    """
    Take an orchestral score,
    identify from relevant instruments for splitting
    (i.e., wind and brass only,
    e.g., flute but not violin),
    and run `split_part` on them to return an expanded score.
    """
    score = converter.parse(path / file_name)

    for p in score.parts:
        i = p.getInstrument(returnDefault=False)
        if "BrassInstrument" in i.classes:
            transposition_check(p)
            # ^^ NB transposition check alternative:
            # p.toSoundingPitch(inPlace=True)
            # p.getInstrument().transposition = None
            p.recurse().stream().removeByClass(key.KeySignature)
            # ^^ `removeByClass is not defined on StreamIterators. Call .stream() first for efficiency`
            new1, new2 = split_part(p)
            score.remove(p)
            score.insert(0, new1)
            score.insert(0, new2)
        elif "WoodwindInstrument" in i.classes:  # Both transpose and split
            transposition_check(p)
            new1, new2 = split_part(p)
            score.remove(p)
            score.insert(0, new1)
            score.insert(0, new2)
        else:
            score.remove(p)
            score.insert(0, p)

    score = clean_up(score)

    path_parts = PurePath(path).parts[-3:]
    score.metadata.composer = path_parts[0].replace("_", " ")
    score.metadata.title = path_parts[1].replace("_", " ")
    score.metadata.movementName = path_parts[1].replace("_", " ")
    # ^^^ sic, movementName also symphony due to MuseScore display defaults
    score.metadata.movementNumber = path_parts[2]

    try:
        file_name = "_".join(
            [
                path_parts[0].split(",")[0],  # "<Lastname>"
                path_parts[1].split(",_")[1],  # "Op.<number>"
                path_parts[2]  # E.g., "<Mvt number>"
            ]
        ) + ".mxl"
    except:
        file_name = "test.mxl"

    score.write("mxl", path / file_name)


def transposition_check(p: stream.Part) -> None:
    """
    Check if an instrument is transposing.
    If non-transposing return None.
    If transposing, check whether the transposition matches the name.
    If they match then fine, no action.
    If not, change the transposition on the instrument object.

    @param p: a part in a score.
    @return: None
    """
    fs = instrument.fromString(p.partName).transposition

    if fs is None:
        print(p, "is non-transposing")
        return None

    if fs == p.getInstrument().transposition:
        print(p, "is transposing and the interval matches")
        return
    else:
        # change the transposition in place probably better than replace() instrument object
        print(p, f" *** changing transposition interval to {fs}")
        p.getInstrument().transposition = fs


def clean_up(s: stream.Score):
    """
    Basic layout clean up on a score.
    Remove all manual style adjustment including stem direction.

    @param s: The Score.
    @return: That same score, cleaned up ;)
    """
    layouts = s.recurse().getElementsByClass(layout.ScoreLayout)
    for l in layouts:
        print("1, ", l)
        s.remove(l)

    for item in s.recurse():  # recurse needed? or top level only?
        if "layout" in item.classes:
            print("2, ", item)
            s.remove(item)
        elif "Note" in item.classes:
            item.stemDirection = "unspecified"
        elif "Slur" in item.classes:
            item.placement = None

    # for n in s.recurse().notes:
    #     n.stemDirection = "unspecified"

    return s


# ------------------------------------------------------------------------------

if __name__ == "__main__":
    process_one_score()

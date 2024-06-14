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

from music21 import converter, instrument, key, layout, pitch, stream, articulations, dynamics
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
                n.remove(pitches[i])  # remove all pitches except the last (highest) one

    for n in new_part_2.recurse().notesAndRests:
        if n.isChord:
            pitches = n.pitches
            for i in range(1, len(pitches)):
                n.remove(pitches[i])  # remove all pitches except the first (lowest) one
        if n.lyric:  # should all be duplicates in this expansion.
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
        trans = ""
        if i.transposition:  # Lead with "Bb Clarinet" to help MuseScore's bad instrument recognition algorithm.
            trans = pitch.Pitch("C").transpose(i.transposition).name.replace("-", "b")
        # NB: 1-2 numbering works in almost all cases; manual change needed for the occasional horns 3-4.
        new_part_1.partName = f"{trans} {i.classes[0]} 1"
        new_part_2.partName = f"{trans} {i.classes[0]} 2"
        new_part_1.partAbbreviation = i.instrumentAbbreviation + " 1"
        new_part_2.partAbbreviation = i.instrumentAbbreviation + " 2"

    return new_part_1, new_part_2


def process_one_score(
    path_to_score: Path = REPO_PATH / "test" / "split_test_score_in.mxl",
    file_name_out: str | None = None,
) -> None:
    """
    Take an orchestral score,
    identify from relevant instruments for splitting
    (i.e., wind and brass only,
    e.g., flute but not violin),
    and run `split_part` on them to return an expanded score.
    """
    score = converter.parse(path_to_score)

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
            # Part name here too, without transposition
            i = instrument.fromString(p.partName)
            p.partName = i.classes[0]
            p.partAbbreviation = i.instrumentAbbreviation
            score.insert(0, p)

    score = clean_up(score)

    path_parts = PurePath(path_to_score.parent).parts[-3:]
    score.metadata.composer = path_parts[0].replace("_", " ")
    score.metadata.title = path_parts[1].replace("_", " ")
    score.metadata.movementName = path_parts[1].replace("_", " ")
    # ^^^ sic, movementName also symphony due to MuseScore display defaults
    score.metadata.movementNumber = path_parts[2]
    score.metadata.opusNumber = path_parts[1].split(",_")[1]  # "Op.<number>", "BWV.242", etc.
    score.metadata.copyright = "Score: CC0 1.0 Universal; Annotations: CC-By-SA"

    if not file_name_out:
        try:
            file_name_out = "_".join(
                [
                    score.metadata.composer.split(",")[0],  # "<Lastname>"
                    score.metadata.opusNumber,
                    score.metadata.movementNumber
                ]
            ) + ".mxl"
        except:
            file_name_out = "test.mxl"

    score.write("mxl", path_to_score.parent / file_name_out)


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


def clean_up(
        s: stream.Score | str | Path,
        map_accent_to_sf: bool = False,
        delete_moderation: bool = True,
):
    """
    Basic layout clean up on a score.
    Remove all manual style adjustment including stem direction.

    TODO Others to consider:
    Where there’s two dynamics at the same time,
    delete one given some order of likelihood.

    @param s: The Score, or a path to one.
    @param map_accent_to_sf: hard-coded functionality for replacing accents with sf
    @param delete_moderation: remove all cases of mp and mf (rare in specific styles and therefore editorial).
    @return: That same score, cleaned up ;)
    """
    if type(s) != stream.Score:
        s = converter.parse(s)

    layouts = s.recurse().getElementsByClass(layout.ScoreLayout)
    for l in layouts:
        s.remove(l)

    for item in s.recurse():  # recurse needed? or top level only?
        if "layout" in item.classes:
            context = item.getContextByClass(stream.Stream)
            context.remove(item)
        elif "Note" in item.classes:
            item.stemDirection = "unspecified"
        elif "Slur" in item.classes:
            item.placement = None
        elif "Dynamic" in item.classes and delete_moderation:
            if item.value in ["mp", "mf"]:
                context = item.getContextByClass(stream.Stream)
                context.remove(item)

    for n in s.recurse().notes:
        n.stemDirection = "unspecified"

        if n.articulations and map_accent_to_sf:
            for x in n.articulations:
                if "Accent" in x.classes:
                    n.articulations.remove(x)

                    m = n.getContextByClass(stream.Measure)
                    o = n.offset
                    m.insert(o, dynamics.Dynamic("sf"))

    return s


# ------------------------------------------------------------------------------

if __name__ == "__main__":
    process_one_score()

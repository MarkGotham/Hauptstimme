"""
NAME
===============================
Orchestra Part Split (orchestra_part_split.py)


BY
===============================
Mark Gotham


LICENCE:
===============================
Creative Commons Attribution-ShareAlike 4.0 International License
https://creativecommons.org/licenses/by-sa/4.0/


ABOUT:
===============================
Orchestral scores typically place pairs of like parts on the same stave
(e.g., both flutes 1 and 2). Orchestral parts, however, are provided 
separately for those two flute players.
While proprietary software handles this dual layout, open source 
libraries do not. Music21, for example, has a `voicesToPart` function 
specifically for splitting two voices within a measure, but this is 
only a small part of the consideration.
This code handles a wider set of considerations.

Potential Future TODOs:
- Add proper XML IDs like .instrumentId = "wind.reed.clarinet.bflat" to
improve MS4 parsing.
- In score cleanup: only keep one dynamic after split and delete 
dynamics with no notes
"""
from __future__ import annotations


import copy

from attr import validate
from music21 import (
    converter, instrument, key, layout, pitch, stream, dynamics, chord, note
)
from music21.stream.base import Part, Measure, Score, Stream
from pathlib import Path
from hauptstimme.utils import get_corpus_files, validate_path
from hauptstimme.constants import CORPUS_PATH
from typing import Union, Tuple, Optional, cast


def split_part(
    part: Part,
    handle_part_name: bool = True
) -> Tuple[Part, Part]:
    """
    Split a score part into two parts: the first part retains the top 
    voice and the top note of any chords, while the second part retains
    the lowest voice and the lowest note in any chord.

    Text markings such as 'solo', 'a1', etc. are simply duplicated 
    since it is quite easy to verify and delete passages marked, for
    example, with 'a1' manually, and much more difficulty to notice 
    that something is missing.

    3+ parts on the same stave are not handled. It is rare (and 
    arguably 'wrong') to do this on wind parts, so any middle voices
    are ignored.

    Args:
        part: A part of a score.

    Returns:
        The two output parts.
    """
    new_part1 = copy.deepcopy(part)
    new_part2 = copy.deepcopy(part)

    # Note voices are counted from top down

    for m in new_part1.getElementsByClass(Measure):
        if len(m.voices) > 1:
            # Remove all but the top voice
            for i in range(len(m.voices) - 1, 0, -1):
                m.remove(m.voices[i])
            m.flattenUnnecessaryVoices(inPlace=True)

    for m in new_part2.getElementsByClass(Measure):
        if len(m.voices) > 1:
            # Remove all but the bottom voice
            for i in range(len(m.voices) - 1):
                m.remove(m.voices[i])
            m.flattenUnnecessaryVoices(inPlace=True)

    for n in new_part1.recurse().notesAndRests:
        # Replace chords with the top note
        if isinstance(n, chord.Chord):
            new_n = n.notes[-1]
            new_n.offset = n.offset
            for lyric in n.lyrics:
                new_n.addLyric(lyric.text)
                new_n.lyrics[-1].style.color = lyric.style.color
            n = new_n
        # elif isinstance(n, note.Rest):

    for n in new_part2.recurse().notesAndRests:
        # Replace chords with the bottom note
        if isinstance(n, chord.Chord):
            new_n = n.notes[0]
            new_n.offset = n.offset
            for lyric in n.lyrics:
                new_n.addLyric(lyric.text)
                new_n.lyrics[-1].style.color = lyric.style.color
            n = new_n
        # Remove lyrics from this part as they will all be duplicates
        if n.lyric:
            print(
                f"Removing lyric '{n.lyric}' from {new_part2.partName}, " +
                f"measure {n.measureNumber}."
            )
            n.lyric = None
        # elif isinstance(n, note.Rest):

    if handle_part_name:
        i = part.getInstrument()
        if i is not None:
            trans = ""
            # Add transposition to start of instrument name, e.g.,
            # 'A Clarinet'
            if i.transposition:
                trans = pitch.Pitch("C").transpose(
                    i.transposition
                ).name.replace("-", "b")
            # This works in almost all cases but manual change is
            # needed for the occasional horns 3-4
            new_part1.partName = f"{trans} {i.classes[0]} 1".strip()
            new_part2.partName = f"{trans} {i.classes[0]} 2".strip()
            new_part1.partAbbreviation = i.instrumentAbbreviation + " 1"  # type: ignore
            new_part2.partAbbreviation = i.instrumentAbbreviation + " 2"  # type: ignore

    for p in [new_part1, new_part2]:
        p.makeRests(fillGaps=False, inPlace=True, hideRests=False)

    return new_part1, new_part2


def transposition_check(part: Part):
    """
    Check whether the transposition of an instrument matches its name.
    If they don't match, change the instrument object transposition to
    match the name.

    Args:
        part: A part of a score.
    """
    try:
        trans_from_name = instrument.fromString(part.partName).transposition
    except:
        print(f"Warning: Could not parse instrument name '{part.partName}'" +
              ", so unable to check transposition.")
        return

    if trans_from_name is None:
        # No transposition in name
        return

    part_instrument = part.getInstrument()
    if not part_instrument:
        raise ValueError(
            f"Error: Part '{part.partName}' has no instrument object."
        )

    if trans_from_name == part_instrument.transposition:
        # Transpositions in name and instrument object match
        return
    else:
        # Transpositions in name and instrument object don't match
        # Update instrument object transposition
        part_instrument.transposition = trans_from_name


def clean_score(
        score: Score,
        map_accent_to_sf: bool = False,
        delete_moderation: bool = True,
        do_measure_length: bool = False,
) -> Score:
    """
    Perform basic layout clean up on a score and remove all manual 
    style adjustment including stem direction.

    Args:
        score: The score.
        map_accent_to_sf: Whether to replace accents with `sf`.
        delete_moderation: Whether to delete all cases of `mp` and `mf`.
        do_measure_length: Whether to check and correct measure lengths: 
            shorter is fine (anacruses) but longer is wrong.

    Returns:
        The cleaned up score.
    """
    layouts = score.recurse().getElementsByClass(layout.ScoreLayout)
    for l in layouts:
        score.remove(l)

    for item in score.recurse():
        if "layout" in item.classes:
            context = item.getContextByClass(Stream)
            context.remove(item)
        elif "Note" in item.classes:
            item.stemDirection = "unspecified"
        elif "Slur" in item.classes:
            item.placement = None
        elif "Dynamic" in item.classes and delete_moderation:
            if item.value in ["mp", "mf"]:
                context = item.getContextByClass(Stream)
                context.remove(item)

    for part in score.parts:
        # Deal with rests and notes at the same position
        for n in part.recurse().notesAndRests:
            if "Rest" in n.classes:
                m = cast(Measure, n.getContextByClass(Measure))
                prev = n.previous()
                next = n.next()
                if prev is not None:
                    if "Rest" not in prev.classes:
                        # If the previous object is a note and has the
                        # same offset as this rest, remove
                        if n.offset == prev.offset:
                            m.remove(n)
                            print("Removing a rest with the same start time" +
                                  f" as a note in measure {n.measureNumber}.")
                if next is not None:
                    if "Rest" not in next.classes:
                        if n.offset == next.offset:
                            m.remove(n)
                            print("Removing a rest with the same start time" +
                                  f" as a note in measure {n.measureNumber}.")

            if isinstance(n, note.Note):
                n.stemDirection = None

            if n.articulations and map_accent_to_sf:
                for a in n.articulations:
                    if "Accent" in a.classes:
                        n.articulations.remove(a)

                        m = cast(Measure, n.getContextByClass(Measure))
                        o = n.offset
                        m.insert(o, dynamics.Dynamic("sf"))

        part.makeRests(inPlace=True)

        # If there's still a bar duration warping ...
        if do_measure_length:
            current_ts_duration = 10
            for measure in part.getElementsByClass(Measure):
                ts = measure.timeSignature
                if ts:
                    current_ts_duration = ts.barDuration.quarterLength
                if measure.duration.quarterLength > current_ts_duration:
                    print(
                        "Corrected overlong measure length from",
                        measure.duration.quarterLength,
                        "to",
                        current_ts_duration,
                        f"in measure {measure.measureNumber}."
                    )
                    measure.duration.quarterLength = current_ts_duration

    return score


def expand_score(
    score_mxl: Union[str, Path],
    out_name: Optional[Union[str, Path]] = None
):
    """
    Take an orchestral score, identify relevant instruments for 
    splitting (i.e., wind and brass only), and return an expanded 
    score.

    Args:
        score_mxl: The score's MusicXML file path.
        out_name: The new file name for the expanded score.

    Raises:
        ValueError: If the score does not get converted to a 'Score' 
            type.
    """
    score_mxl = validate_path(score_mxl)

    score = converter.parse(score_mxl)
    if not isinstance(score, Score):
        raise ValueError(
            "Error: Score is not of type 'music21.stream.Score'."
        )

    for part in score.parts:
        i = part.getInstrument()
        if i is None:
            continue
        if "BrassInstrument" in i.classes:
            transposition_check(part)
            # ^^ Transposition check alternative:
            # p.toSoundingPitch(inPlace=True)
            # p.getInstrument().transposition = None
            # part.recurse().stream().removeByClass(key.KeySignature)
            new_part1, new_part2 = split_part(part)
            score.remove(part)
            score.append(new_part1)
            score.append(new_part2)
        elif "WoodwindInstrument" in i.classes:
            transposition_check(part)
            new_part1, new_part2 = split_part(part)
            score.remove(part)
            score.append(new_part1)
            score.append(new_part2)
        else:
            score.remove(part)
            # Update part name
            try:
                i = instrument.fromString(part.partName)
                part.partName = i.classes[0]
                part.partAbbreviation = i.instrumentAbbreviation
            except:
                print(
                    f"Could not parse instrument name {part.partName}, " +
                    "skipping this part."
                )
            score.append(part)

    score = clean_score(score)

    try:
        path_parts = Path(score_mxl.parent).parts[-3:]
        score.metadata.composer = path_parts[0].replace("_", " ")
        score.metadata.title = path_parts[1].split(",_")[0].replace("_", " ")
        score.metadata.movementNumber = path_parts[2]
        score.metadata.opusNumber = path_parts[1].split(",_")[1]
        score.metadata.copyright = "Score: CC0 1.0 Universal; Annotations: CC-By-SA"
    except:
        print("Warning: Adding score metadata failed, skipping this.")

    if out_name is None:
        try:
            file_name_out = "_".join(
                [
                    score.metadata.composer.split(",")[0],  # Composer surname
                    score.metadata.opusNumber,
                    score.metadata.movementNumber
                ]
            ) + ".mxl"
        except:
            file_name_out = "expanded_score.mxl"

    score.write("mxl", score_mxl.parent / file_name_out)


def expand_scores(
    corpus_sub_dir: Union[str, Path] = CORPUS_PATH
):
    """
    Perform splitting and cleaning for all scores in the corpus, with 
    the option to do for a sub section of the corpus.

    Args:
        corpus_sub_dir: The path to a subdirectory within the corpus to
            get files from. Default = CORPUS_PATH.
    """
    for file_path in get_corpus_files(
        corpus_sub_dir, file_path="*.mxl", pathlib=True
    ):
        file_path = cast(Path, file_path)

        print("Score:", file_path.name)
        expand_score(file_path)

"""
NAME
===============================
Hauptstimme (hauptstimme.py)


BY
===============================
Mark Gotham and Matt Blessing, 2024


LICENCE:
===============================
Creative Commons Attribution-ShareAlike 4.0 International License
https://creativecommons.org/licenses/by-sa/4.0/


ABOUT:
===============================
Functionality for extracting the Hauptstimme annotations from a score,
writing this data to a .csv, and producing a 'melody score'.

Notes:
1.  The end of an annotation is given by the start of the next.
2.  Annotations must be appended to a particular note start.
    Lyrics on rests do not convert.
3.  Each annotation is for a specific voice within a part (e.g. Flute 1
    instead of 1 and 2).

Possibly TODO:
- test robustness / flexibility with settable voices
- additional functionality to extract <all> or <first_instance> of theme
- remove `other_part` stuff?
"""
import re
import pandas as pd
from math import inf
from fractions import Fraction
from copy import deepcopy
from pathlib import Path
from music21 import (
    converter, clef, expressions, instrument, stream, chord, tempo, spanner,
    dynamics, note, meter, exceptions21
)
from hauptstimme.utils import get_corpus_files
from hauptstimme.constants import CORPUS_PATH, ROUNDING_VALUE


def get_measure_fraction(element):
    """
    Get offset in terms of the fraction of the measure to have elapsed.
    Provides interoperability with TiLiA and Erlangen.

    Args:
        element: A Music21 object to compute the measure fraction for.
            Likely a note.

    Returns:
        The measure fraction.
    """
    return (element.offset /
            element.getContextByClass("Measure").duration.quarterLength)


def get_annotation_info(n, part, curr_time_sig):
    """
    Get relevant information for the note or text expression containing
    a Hauptstimme annotation.

    Args:
        n: A Music21 object to compute the information for. Here, n is
            either a note or text expression.
        part (music21.stream.Stream): The score part containing `n`.
        curr_time_sig (music21.meter.TimeSignature): The current time
            signature.

    Returns:
        info (dict): The qstamp, measure, beat, measure fraction, and
            offset for `n`.
    """
    info = {
        "qstamp": n.getOffsetInHierarchy(part),
        "measure": n.measureNumber,
        "beat": n.beat,
        "measure_fraction": get_measure_fraction(n),
        "offset": n.offset,
    }

    if info["measure"] is not None:
        # Deal with issue with beats when there are multiple voices
        # Manually calculate beat
        measure_obj = part.measure(info["measure"])
        num_voices = len(measure_obj.voices)
        if num_voices > 0:
            info["beat"] = (1 + (n.offset - measure_obj.offset) /
                            curr_time_sig.beatDuration.quarterLength)

    return info


def hauptstimme_round(value):
    """
    A custom rounding function for the Hauptstimme annotations data.

    Notes:
        Sometimes qstamps, beats, and more can be expressed as
        fractions, so we want to convert these to floats for
        consistency.
        We only do this when creating the Hauptstimme annotations
        .csv file.

    Args:
        value (any): A value in the Hauptstimme annotations data.

    Returns:
        If value is a Fraction: the rounded value as a float.
        If value is a float: the rounded value.
        If value is neither of the above: the unchanged value.
    """
    if isinstance(value, Fraction):
        return round(float(value), ROUNDING_VALUE)
    elif isinstance(value, float):
        return round(value, ROUNDING_VALUE)
    return value


class HauptstimmeAnnotations:
    """
    A class to extract the Hauptstimme annotations from a score and
    create the annotations file and melody score.
    """

    def __init__(
        self,
        score_mxl: str,
        lyrics_not_text: bool = True,
        annotation_restrictions: list | str | None = None,
        melody_score_format: str = "mxl",
        instrument_labels: bool = True,
        add_slurs: bool = True,
        add_dynamics: bool = True
    ):
        """
        Args:
            score_mxl: The score's MusicXML file path.
            lyrics_not_text: Whether the annotations are lyrics (True)
                or text expressions (False). Default = True.
            annotation_restrictions: Restrictions for the annotation
                labels. They may be expressed either one of two ways:
                1.  A list of allowed values,
                    e.g., ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i']
                2.  A regex that requires a full match,
                    e.g., '\w', which is equivalent to '[a-zA-Z0-9_]'
                    and matches any single letter, numeric digit, or
                    underscore character.
                Default = None.
            melody_score_format: The file type for the melody score.
                Default = 'mxl'.
            instrument_labels: Whether to include instrument labels in
                the melody score or not. Default = True.
            add_slurs: Whether to include slurs in the melody score or
                not, with slurs that overlap annotation blocks being
                adjusted. Default = True.
            add_dynamics: Whether to include dynamic markings including
                hairpins in the melody score or not. Default = True.
        """
        self.score_path = Path(score_mxl)
        self.score = converter.parse(score_mxl)

        self.lyrics_not_text = lyrics_not_text
        self.annotation_restrictions = annotation_restrictions
        if not lyrics_not_text and annotation_restrictions is None:
            raise ValueError("Error: When the annotations are text " +
                             "expressions, restrictions are needed to " +
                             "prevent tempo readings etc. being " +
                             "included.")

        # Extract the annotations
        self.annotations = self.get_annotations()

        self.melody_score_format = melody_score_format
        self.instrument_labels = instrument_labels
        self.add_slurs = add_slurs
        self.add_dynamics = add_dynamics

        # Create the melody score
        self.melody_part = self.init_melody_part()
        self.current_clef = None
        self.make_melody_part()

    def meets_restrictions(self, annotation_label: str) -> bool:
        """
        Determine whether an annotation label complies with the label
        restrictions.

        Args:
            annotation_label: The annotation label.
        """
        # If no restrictions
        if self.annotation_restrictions is None:
            return True

        # If a regex restriction
        if type(self.annotation_restrictions) == str:
            if re.fullmatch(self.annotation_restrictions, annotation_label):
                return True
            else:
                return False
        # If a list of accepted values
        elif type(self.annotation_restrictions) == list:
            if annotation_label in self.annotation_restrictions:
                return True
            else:
                return False
        else:
            raise TypeError("Error: Invalid restrictions type.")

    def annotations_from_lyrics(self, part: stream.Part, part_info: dict):
        """
        Extract the annotations from the lyrics in a particular part of the
        score.

        Args:
            part: A part of the score.
            part_info: The part name, number, and instrument name.
        """
        annotations = []

        for n in part.recurse().notesAndRests:
            if n.lyric:
                if n.isRest:
                    print(f"Warning: Measure {n.measureNumber} contains a " +
                          "lyric attached to a rest. Ignoring this lyric.")
                elif not self.meets_restrictions(n.lyric):
                    print(f"Warning: Ignoring annotation '{n.lyric}' in " +
                          f"measure {n.measureNumber} as it does not meet " +
                          "the annotation restrictions.")
                else:
                    curr_time_sig = n.getContextByClass(meter.TimeSignature)
                    note_info = get_annotation_info(n, part, curr_time_sig)
                    annotation = part_info | note_info | {
                        "label": n.lyric.replace(",", "")
                    }
                    annotations.append(annotation)

        return annotations

    def annotations_from_text(self, part: stream.Part, part_info: dict):
        """
        Extract the annotations from the text expressions in a
        particular part of the score.

        Args:
            part: A part of the score.
            part_info: The part name, number, and instrument name.
        """
        annotations = []

        for t in part.recurse().getElementsByClass(
                expressions.TextExpression):
            label = str(t.content)

            if self.meets_restrictions(label):
                curr_time_sig = t.getContextByClass(meter.TimeSignature)
                text_info = get_annotation_info(t, part, curr_time_sig)
                annotation = part_info | text_info | {
                    "label": label.replace(",", "")
                }
                annotations.append(annotation)
            else:
                print(f"Warning: Excluding invalid annotation {label} in " +
                      "measure",
                      t.getContextByClass(stream.Measure).measureNumber)

        return annotations

    def set_annotation_ends(self, annotations: list):
        """
        Define the end of each annotation.

        Args:
            annotations: A list of annotations.
        """
        for index in range(len(annotations) - 1):
            annotation = annotations[index]
            next_annotation = annotations[index + 1]

            annotation["end_measure"] = next_annotation["measure"]
            annotation["end_offset"] = next_annotation["offset"]
            annotation["end_qstamp"] = next_annotation["qstamp"]

        # Special case of last annotation
        last_measure = self.score.parts[0].getElementsByClass("Measure")[-1]
        last_annotation = annotations[-1]
        last_annotation["end_measure"] = last_measure.measureNumber
        last_annotation["end_offset"] = inf
        last_annotation["end_qstamp"] = inf

        return annotations

    def get_annotations(self):
        """
        Retrieve the Hauptstimme annotations from either the lyrics or
        text expressions.
        """
        annotations = []

        for part_count, part in enumerate(self.score.parts):
            part = part.toSoundingPitch()
            # Get an abbreviation of the part name (e.g., 'Vln 1')
            part_abbrev = part.partAbbreviation
            # Get an abbreviation of the instrument name (e.g., 'Vln')
            try:
                part_instrument = instrument.fromString(part.partName)
            except exceptions21.InstrumentException as e:
                part_instrument = part.getInstrument()
                # # This fails if the instrument can't be found
                # print(f"Warning: {e} (it could not be found in " +
                #         "Music21's database). Please manually enter " +
                #         "another version of the instrument name (see " +
                #         "https://github.com/cuthbertLab/music21/blob/" +
                #         "204e9d0b9eec2f2d6ff8d8d3b13c41f912050604/" +
                #         "music21/languageExcerpts/instrumentLookup.py).")
                # # If so, the user must input a valid instrument name
                # part_instrument = None
                # while part_instrument is None:
                #     user_input = input()
                #     try:
                #         part_instrument = instrument.fromString(user_input)
                #     except Exception as e:
                #         print("Same issue - try again.")
            instrument_abbrev = part_instrument.instrumentAbbreviation

            # Get annotation info that only depends on the part
            part_info = {
                "part": part_abbrev,
                "part_num": part_count,
                "instrument": instrument_abbrev
            }

            # Get the annotations in this part
            if self.lyrics_not_text:
                part_annotations = self.annotations_from_lyrics(
                    part, part_info)
            else:
                part_annotations = self.annotations_from_text(
                    part, part_info)

            annotations += part_annotations

        print(f"Retrieved {len(annotations)} annotations.")
        annotations.sort(key=lambda x: x["qstamp"])
        annotations = self.set_annotation_ends(annotations)

        return annotations

    def write_annotations_file(self, out_dir: str | None = None):
        """
        Write the Hauptstimme annotations to a .csv file.

        Args:
            out_dir: The path to the directory in which the annotations
                file will be saved. Default = None.
        """
        columns = ["qstamp", "measure", "beat", "measure_fraction",
                   "label", "part", "part_num", "instrument"]

        if len(self.annotations) == 0:
            print("Error: Score has no annotations.")
        else:
            # Get annotations .csv filename
            if out_dir is None:
                csv_file = (self.score_path.parent /
                            f"{self.score_path.stem}_annotations.csv")
            else:
                out_dir_path = Path(out_dir)
                csv_file = (out_dir_path /
                            f"{self.score_path.stem}_annotations.csv")

            # Convert Fractions to floats and round entries
            annotations = []
            for annotation in self.annotations:
                annotations.append({k: hauptstimme_round(v)
                                    for k, v in annotation.items()})

            df_annotations = pd.DataFrame(annotations, columns=columns)
            df_annotations.to_csv(csv_file, index=False)

    def init_melody_part(self):
        """
        Initialise the melody part with the first part in the score
        since this will contain the score's tempo information.
        """
        # This will be the sole part in the melody score
        melody_part = self.score.parts[0].template(
            fillWithRests=False,
            removeClasses=["GeneralNote", "Dynamic", "Expression", "Clef",
                           "Instrument", "SystemLayout", "StaffLayout",
                           "LayoutBase", "PageLayout", "Slur",
                           "DynamicWedge"]
        )
        melody_part.coreElementsChanged()
        melody_part.id = "Melody Score"
        melody_part.partName = "Melody Score"

        # Only keep the last tempo marking in each measure (the one
        # that is actually used in playback)
        for measure in melody_part.getElementsByClass(stream.Measure):
            tempos = measure.getElementsByClass(tempo.MetronomeMark)
            if tempos:
                for tempo_mark in tempos[:-1]:
                    measure.remove(tempo_mark)

        return melody_part

    def add_clef(
        self,
        new_clef: clef.Clef,
        offset: float | int,
        measure_num: int
    ):
        """
        Add a clef to the melody part when the context changes.

        Notes:
            Two clefs are equal if:
            - their class is the same,
            - their sign is the same,
            - their line is the same and
            - their octave change is the same.

        Args:
            new_clef: The new clef.
            offset: The offset of the clef in the measure.
            measure_num: The measure number.
        """
        if new_clef != self.current_clef:
            self.melody_part.measure(measure_num).insert(offset, new_clef)
            self.current_clef = new_clef

    def add_label(
            self,
            label: str,
            offset: float | int,
            measure_num: int,
            placement: str = "above"
    ):
        """
        Add a label to the melody part where there is an annotation.

        Notes:
            This is used to add annotation labels that are text
            expressions and instrument labels.

        Args:
            label: The label.
            offset: The offset of the annotation in the measure.
            measure_num: The measure number.
            placement: Where the label should be placed.
        """
        t = expressions.TextExpression(label)
        t.placement = placement
        self.melody_part.measure(measure_num).insert(offset, t)

    def transfer_from_measure(
        self,
        annotation_part: stream.Part,
        annotation: dict,
        measure_num: int,
        first_measure: bool = False
    ):
        """
        Transfer the notes, rests, and potentially dynamic markings in
        a measure that lie within the start and end qstamps from the
        part containing an annotation to the melody part.

        Notes:
            If a note overlaps the end of the annotation block, then
            its duration will be shortened.

        Args:
            annotation_part: The score part containing the annotation.
            annotation: The annotation information.
            measure_num: The measure number.
            first_measure: Whether measure `measure_num` is the first
                measure of the annotation block.
        """
        measure = annotation_part.measure(measure_num)

        start_qstamp = annotation["qstamp"]
        end_qstamp = annotation["end_qstamp"]

        # Only include notes and rests from first voice
        num_voices = len(measure.voices)
        if num_voices > 0:
            notes_rests = measure.voices[0].notesAndRests
        else:
            notes_rests = measure.notesAndRests

        for n in notes_rests:
            # Get note qstamp
            qstamp = n.getOffsetInHierarchy(annotation_part)

            # Replace chords with the top note
            if isinstance(n, chord.Chord):
                new_n = n.notes[-1]
                new_n.offset = n.offset
                for lyric in n.lyrics:
                    new_n.addLyric(lyric.text)
                    new_n.lyrics[-1].style.color = lyric.style.color
                n = new_n
                # TODO: Adjust this in orchestra_split

            if start_qstamp:
                if qstamp < start_qstamp:
                    # If note starts playing before annotation, then
                    # ignore
                    continue

            if end_qstamp:
                if qstamp >= end_qstamp:
                    # If note falls in next annotation block, then
                    # ignore
                    continue

                if qstamp + n.quarterLength > end_qstamp:
                    # Note goes beyond end of annotation so shorten its
                    # length
                    n.augmentOrDiminish(
                        (end_qstamp - qstamp) / n.duration.quarterLength,
                        inPlace=True
                    )

            # Insert note into melody part
            self.melody_part.measure(measure_num).insert(n.offset, n)

        if first_measure:
            start_offset = annotation["offset"]
            # Get clef for the measure
            new_clef = deepcopy(notes_rests[0].getContextByClass(clef.Clef))
            self.add_clef(new_clef, start_offset, measure_num)

            if self.instrument_labels:
                self.add_label(annotation_part.partAbbreviation,
                               start_offset, measure_num)

            # If annotations are text expressions, add annotation
            if not self.lyrics_not_text:
                label = annotation["label"]
                self.add_label(label, start_offset,
                               measure_num, placement="below")

        if self.add_dynamics:
            # Add dynamics markings
            for d in measure.getElementsByClass(dynamics.Dynamic):
                qstamp = d.getOffsetInHierarchy(annotation_part)
                if start_qstamp:
                    if qstamp < start_qstamp:
                        continue

                if end_qstamp:
                    if qstamp >= end_qstamp:
                        continue

                self.melody_part.measure(measure_num).insert(d.offset, d)

    def make_melody_part(self):
        """
        Produce a single score part containing the main melody
        extracted from the Hauptstimme annotations.
        """
        for annotation in self.annotations:
            annotation_part = self.score.parts[annotation["part_num"]]
            start_measure = annotation["measure"]
            end_measure = annotation["end_measure"]

            # If whole annotation block is in one measure
            if start_measure == end_measure:
                self.transfer_from_measure(
                    annotation_part,
                    annotation,
                    start_measure,
                    first_measure=True
                )
            # If annotation block spans multiple measures
            else:
                # First measure
                self.transfer_from_measure(
                    annotation_part,
                    annotation,
                    start_measure,
                    first_measure=True
                )
                # Rest of the measures
                for measure_num in range(start_measure + 1, end_measure + 1):
                    self.transfer_from_measure(
                        annotation_part,
                        annotation,
                        measure_num
                    )

        # Handle ties that overlap Hauptstimme blocks
        open_ties = {}
        for n in self.melody_part.flatten().notes:
            if n.tie:
                if isinstance(n, note.Note):
                    note_mnn = n.pitch.midi
                else:
                    note_mnn = n.pitches[0].midi
                tie_type = n.tie.type
                if tie_type == "start":
                    open_ties[note_mnn] = [n]
                elif tie_type == "continue":
                    open_ties[note_mnn].append(n)
                elif tie_type == "stop":
                    if note_mnn in open_ties:
                        # Remove from tracking if tie is closed
                        del open_ties[note_mnn]

        # Remove any unfinished ties
        for tie_notes in open_ties.values():
            if len(tie_notes) > 1:
                # If tie has a 'continue' note, then set this to 'stop'
                tie_notes[-1].tie.type = "stop"
            else:
                # If tie has no 'continue' note, then remove tie
                tie_notes[0].tie = None

        if self.add_slurs:
            melody_slurs = {}
            for part in self.score.parts:
                # Get slurs and the elements they span
                slurs = {}
                for slur in part.getElementsByClass(spanner.Slur):
                    slur_notes = slur.getSpannedElementIds()
                    slurs[slur] = slur_notes

                # Identify which notes in the melody part are spanned
                # by these slurs
                for n in self.melody_part.flatten().notes:
                    for slur, slur_notes in slurs.items():
                        if n.id in slur_notes:
                            if slur not in melody_slurs:
                                melody_slurs[slur] = []
                            melody_slurs[slur].append(n)

            # Create new slurs for the melody part
            for slur, slur_notes in melody_slurs.items():
                if len(slur_notes) > 1:
                    new_slur = spanner.Slur()
                    new_slur.addSpannedElements(slur_notes)
                    self.melody_part.insert(0, new_slur)

        if self.add_dynamics:
            melody_hairpins = {}
            for part in self.score.parts:
                # Get hairpins and the elements they span
                hairpins = {}
                for hairpin in part.getElementsByClass(dynamics.DynamicWedge):
                    hairpin_notes = hairpin.getSpannedElementIds()
                    hairpins[hairpin] = hairpin_notes

                # Identify which notes and rests in the melody part are
                # spanned by these hairpins
                for n in self.melody_part.flatten().notesAndRests:
                    for hairpin, hairpin_notes in hairpins.items():
                        if n.id in hairpin_notes:
                            if hairpin not in melody_hairpins:
                                melody_hairpins[hairpin] = []
                            melody_hairpins[hairpin].append(n)

            # Create new hairpins for the melody part
            for hairpin, hairpin_notes in melody_hairpins.items():
                if hairpin.type == "crescendo":
                    new_hairpin = dynamics.Crescendo()
                elif hairpin.type == "diminuendo":
                    new_hairpin = dynamics.Diminuendo()
                new_hairpin.addSpannedElements(hairpin_notes)
                self.melody_part.insert(0, new_hairpin)

        self.melody_part.makeBeams(inPlace=True)
        # self.melody_part.makeRests(fillGaps=True, in_place=True, hideRests=False)
        # TODO: currently no effect. Also unnecessary? Any regions that have no active elements.

    # def make_other_part(self):
    #     """
    #     Insert a second part:
    #     currently simply a one-stave synthesis of the full score using chordify.
    #     TODO:
    #     - remove duplicated (if this note in melody_part then ignore)
    #     - possibly "bass line" alternative (lowest somewhat more reliable than highest for melody)
    #     """
    #     self.other_part = self.score.chordify()

    def write_melody_score(
            self,
            out_dir: str | None = None,
            other_part: bool = False,
            bass_part: bool = False
    ):
        """
        Write the melody score file.
        """
        melody_score = stream.Score()
        melody_score.append(self.melody_part)

        # Metadata
        md = self.score.metadata
        md.movementName += " - Melody Score"
        md.composer = self.score.metadata.composer
        melody_score.metadata = md

        # if other_part:  #
        #     if not self.other_part:
        #         self.make_other_part()

        #     melody_score.insert(0, self.other_part)

        # if bass_part:  #
        #     if not self.other_part:
        #         self.make_other_part()

        #     # Chords. NB counting bottom up. TODO copied from `orchestra_part_split`. Refactor?
        #     for n in self.other_part.recurse().notesAndRests:
        #         if n.isChord:
        #             pitches = n.pitches
        #             for i in range(len(pitches) - 1):
        #                 # remove all pitches except the last (highest) one
        #                 n.remove(pitches[i])

        #     melody_score.insert(0, self.other_part)

        if out_dir is None:
            melody_score_file = (
                self.score_path.parent /
                f"{self.score_path.stem}_melody.{self.melody_score_format}"
            )
        else:
            out_dir_path = Path(out_dir)
            melody_score_file = (out_dir_path /
                                 (f"{self.score_path.stem}_melody." +
                                  f"{self.melody_score_format}"))

        melody_score.write(fmt=self.melody_score_format, fp=melody_score_file)


def get_annotations_and_melody_score(
    score_mxl: str,
    out_dir: str | None = None,
    lyrics_not_text: bool = True,
    annotation_restrictions: list | str | None = "[a-zA-Z]'?",
    melody_score_format: str = "mxl",
    instrument_labels: bool = True,
    add_slurs: bool = True,
    add_dynamics: bool = True
):
    """
    Get the Hauptstimme annotations file and melody score for a
    particular score.

    Args:
        score_mxl: The score's MusicXML file path.
        out_dir: A path to the directory to save the annotations file
            and melody score to. Default = None.
        lyrics_not_text: Whether the annotations are lyrics (True)
            or text expressions (False). Default = True.
        annotation_restrictions: Restrictions for the annotation
            labels. They may be expressed either one of two ways:
            1.  A list of allowed values,
                e.g., ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i']
            2.  A regex that requires a full match,
                e.g., '\w', which is equivalent to '[a-zA-Z0-9_]'
                and matches any single letter, numeric digit, or
                underscore character.
            Default = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i',
            'tr', 'x', 'y', 'z'].
        melody_score_format: The file type for the melody score.
            Default = 'mxl'.
        instrument_labels: Whether to include instrument labels in
            the melody score or not. Default = True.
        add_slurs: Whether to include slurs in the melody score or
            not, with slurs that overlap annotation blocks being
            adjusted. Default = True.
        add_dynamics: Whether to include dynamic markings including
            hairpins in the melody score or not. Default = True.
    """
    annotations_handler = HauptstimmeAnnotations(
        score_mxl,
        lyrics_not_text,
        annotation_restrictions,
        melody_score_format,
        instrument_labels,
        add_slurs,
        add_dynamics
    )

    annotations_handler.write_annotations_file(out_dir)
    annotations_handler.write_melody_score(out_dir)


def get_annotations_and_melody_scores(
    corpus_sub_dir: str = CORPUS_PATH,
    replace: bool = True,
    lyrics_not_text: bool = True,
    annotation_restrictions: list | str | None = "(\w|\w')"
) -> None:
    """
    Get the Hauptstimme annotations file and melody score for all
    scores in the corpus, with the option to do for a sub section of
    the corpus.

    Args:
        corpus_sub_dir: The path to a subdirectory within the corpus to
            get files from. Default = CORPUS_PATH.
        replace: Whether to replace the annotation files/melody scores
            for scores that already have them. Default = True
        lyrics_not_text: Whether the annotations are lyrics (True) or
            text expressions (False). Default = True.
        annotation_restrictions: Restrictions for the annotation
            labels. They may be expressed either one of two ways:
            1.  A list of allowed values,
                e.g., ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i']
            2.  A regex that requires a full match,
                e.g., '\w', which is equivalent to '[a-zA-Z0-9_]'
                and matches any single letter, numeric digit, or
                underscore character.
            Default = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i',
            'tr', 'x', 'y', 'z'].
    """
    for file in get_corpus_files(corpus_sub_dir, filename="*.mxl"):
        file_path = Path(file)

        if file_path.name.endswith("_melody.mxl"):
            # Ignore melody scores
            continue

        print("Score:", file_path.name)

        if replace:
            try:
                get_annotations_and_melody_score(
                    file, lyrics_not_text=lyrics_not_text,
                    annotation_restrictions=annotation_restrictions
                )
            except Exception as e:
                print("Warning: Failed to get annotations file and melody " +
                      f"score for '{file_path.name}' due to error: {e}.")
        else:
            annotations_file = (file_path.parent /
                                f"{file_path.stem}_annotations.csv")
            if annotations_file.exists():
                print(f"Skipping '{file_path.name}' since it already has " +
                      "an annotations file and melody score.")
            else:
                try:
                    get_annotations_and_melody_score(
                        file, lyrics_not_text=lyrics_not_text)
                except Exception as e:
                    print("Warning: Failed to get annotations file and " +
                          f"melody score for '{file_path.name}'due to " +
                          f"error: {e}.")

"""
NAME
===============================
HAUPTSTIMME (hauptstimme.py)


BY
===============================
Mark Gotham, 2020-


LICENCE:
===============================
Creative Commons Attribution-ShareAlike 4.0 International License
https://creativecommons.org/licenses/by-sa/4.0/


ABOUT:
===============================
Given a score annotated with which part has the main melody at any one time;
- retrieve those annotations and:
- (optionally) write that data to csv; and/or
- (optionally) make a mini-score with just that main melody / principal line / hauptstimme.

Notes:
1.
Currently no tag for melody end. Given by start of next segment.
2.
Annotations must be appended to the start of a note
- e.g., lyrics on rests do not convert.
- annotations falling within/between note starts cause problems.
3.
Annotation on a specific voice within a part (e.g., flute 1 only, not 1 and 2):
- this is supported for extraction
- the annotations csv will still only give the generic instrument name.

Possibly TODO:
- specific items in the code below identified with TODO
- test robustness / flexibility with settable voices
- review layout: Keep tempo and rehearsal marks; lose page breaks specifically
- alternative music21 methods for the transfer of notes.
- additional functionality to extract <all> or <first_instance> of theme
- efficiency throughout ;)

"""
from pathlib import Path
from music21 import converter
from music21 import clef
from music21 import expressions
from music21 import instrument
from music21 import metadata
from music21 import stream

import re

from . import CORPUS_PATH


class ScoreThemeAnnotation:
    """
    End-to-end handling of
    importing a score,
    extracting annotations and
    (optionally) writing data and melody score files.
    """

    def __init__(
            self,
            path_to_score: Path,
            part_for_template: int | str | instrument.Instrument | None = instrument.Violin(),
            out_format: str = "mxl",
            restrictions: list | str | None = None
    ):

        self.path_to_score = path_to_score
        self.score = converter.parse(self.path_to_score).toSoundingPitch()  # NB transpose
        self.check_transposed()

        self.part_for_template = part_for_template
        self.out_format = out_format

        self.transfer_part = None
        self.orderedAnnotationsList = None
        self.melody_part = None
        self.other_part = None
        self.cleared_formatting = False
        self.currentClef = "Treble"
        self.restrictions = restrictions

    def check_transposed(self):
        """
        Double-checks the transposition of orchestral scores to sounding pitch.
        """
        for p in self.score.parts:
            if not p.atSoundingPitch:
                raise ValueError("Despite attempting to set the score to sounding pitch, " +
                                 f"{p.partName} is still not transposed.")

    def getAnnotations(
            self,
            simplify_part_name: bool = True,
            where: str = "lyric"):
        """
        Retrieve manually added annotations from either the lyrics or text expressions.

        User-defined restrictions are optional (default is None)
        See notes at `meetsRestrictions`.
        """

        failMessage = "This tag does not conform to the user specified restrictions for ..."

        self.orderedAnnotationsList = []

        partCount = 0

        for this_part in self.score.parts:

            partName = this_part.partName
            if simplify_part_name:
                try:
                    partName = instrument.fromString(partName).instrumentAbbreviation
                except:
                    pass  # No sense in crashing the whole thing for this.
                    # NB: may wish to preserve violin I vs II

            if where == "lyric":
                self.annotationsFromLyric(this_part, partName, partCount)
            elif where == "te":
                self.annotationsFromTE(this_part, partName, partCount)
            else:
                print("`where` invalid: must be `lyric` or `te`. Stopping")
                return

            partCount += 1

        print(f"Done: retrieved {len(self.orderedAnnotationsList)} annotations")
        self.orderedAnnotationsList.sort(key=lambda x: x["qstamp"])
        self.setAnnotationEnds()

    def annotationsFromLyric(
            self, this_part: stream.Part, partName, partCount):

        for n in this_part.recurse().notesAndRests:

            if n.lyric:

                if n.isRest:  # NB: Rests with lyrics do not convert.
                    print(f"Lyric attached to rest in measure {n.measureNumber}. Ignored.")
                    continue

                if self.restrictions and not meets_restrictions(n.lyric):
                    print(f"Excluding invalid annotation: {n.lyric}")
                    continue

                # if no restrictions, and / or restriction conditions are met:
                segmentData = {"measure": n.measureNumber,
                               "offset": n.offset,
                               "beat": n.beat,
                               "partName": partName,
                               "partNum": partCount,
                               "label": n.lyric,
                               "qstamp": n.getOffsetInHierarchy(this_part),
                               "clef": n.getContextByClass("Clef"),
                               "voice": 0}  # TODO handle all as extension of the note class?
                # if n.getContextByClass("Voice"):  # No voices. Running on one part per stave scores.
                #     segmentData["voice"] = n.getContextByClass("Voice").id  # NB not number

                self.orderedAnnotationsList.append(segmentData)

    def annotationsFromTE(
            self, this_part: stream.Part, part_name, part_count):
        """
        See also getAnnotationsFromLyrics().
        This is the equivalent method for getting annotations from text expressions
        (`expressions.TextExpression`).
        """
        for te in this_part.recurse().getElementsByClass(expressions.TextExpression):
            if self.restrictions and not meets_restrictions(str(te)):
                print(f"Excluding invalid annotation: {te}")
                continue

            # if no restrictions, and / or restriction conditions are met:
            segmentData = {"measure": te.getContextByClass(stream.Measure).number,
                           "offset": te.offset,
                           "beat": te.beat,
                           "partName": part_name,
                           "partNum": part_count,
                           "label": te.content.replace(",", ""),  # TODO cut any commas to avoid csv errors.
                           "qstamp": te.getOffsetInHierarchy(this_part),
                           "clef": te.getContextByClass("Clef"),
                           "voice": 0}  # TODO handle all as extension of the note class?

            self.orderedAnnotationsList.append(segmentData)

        part_count += 1

        print(f"Done: {len(self.orderedAnnotationsList)} annotations")
        self.orderedAnnotationsList.sort(key=lambda x: x["qstamp"])

        if len(self.orderedAnnotationsList) == 0:  # No annotations, so nothing to sort.
            return
        else:
            self.setAnnotationEnds()

    def setAnnotationEnds(self):
        """
        Having retrieved annotations (getAnnotationsFromLyrics), if there are any, then sort them.

        TODO: more elegant solution
        """

        for index in range(len(self.orderedAnnotationsList) - 1):  # Last entry handled below.
            thisEntry = self.orderedAnnotationsList[index]
            nextEntry = self.orderedAnnotationsList[index + 1]

            thisEntry["endMeasure"] = nextEntry["measure"]
            thisEntry["endOffset"] = nextEntry["offset"]  # Not to be uses for comparison (often 0)
            thisEntry["endqstamp"] = nextEntry["qstamp"]

        # Special case of last melody entry.
        lastMeasure = self.score.parts[0].getElementsByClass("Measure")[-1]
        lastEntry = self.orderedAnnotationsList[-1]
        lastEntry["endMeasure"] = lastMeasure.measureNumber
        lastEntry["endOffset"] = 50  # Fake number, longer than any real bar
        lastEntry["endqstamp"] = lastEntry["qstamp"] + 10000  # Same, fake

    def writeAnalysis(
            self,
            out_path: Path | None,
            headers: list | None = None
    ):
        """
        Write the analysis (self.orderedAnnotationsList) information to a csv file.
        """

        if headers is None:
            headers = ["qstamp", "measure", "beat", "label", "partName", "partNum"]

        if len(self.orderedAnnotationsList) == 0:
            print(f"Fail: no annotations.")
            return

        else:
            if not out_path:
                out_path = self.path_to_score.parent
            pathToAnnotation = out_path / f"{self.path_to_score.stem}_annotations.csv"
            with open(pathToAnnotation, "w") as f:
                f.write(",".join(headers) + "\n")
                for annotationDict in self.orderedAnnotationsList:
                    annotationDict["beat"] = intBeat(annotationDict["beat"])
                    line = [str(annotationDict[h]) for h in headers]
                    f.write(",".join(line) + "\n")
            f.close()

    def makeMelody_part(self):
        """
        Make a mini-score with just the main melody as retrieved from the annotations.
        
        Uses music21 stream.template to start with,
        removing the clef and instrument classes,
        and not "filling with rests",
        
        Uses measure information to handle voices,
        then qstamp for end comparison.
        
        The default partForTemplate is the violin.
        This is settable at the class init with any of the following:
        - instrument.Instrument object (best practice);
        - int for a part number (if you"re sure!);
        - str for an instrument name*.

        *Approximate matches are supported in so far as they are recognisable
        through the (recently updated) music21.instrument.fromString() function.
        """
        self.prepareTemplate()

        self.currentClef = self.melody_part[clef.Clef].first()

        for thisEntry in self.orderedAnnotationsList:

            pNum = thisEntry["partNum"]

            self.transfer_part = self.score.parts[pNum]

            firstmeasure_num = thisEntry["measure"]
            lastmeasure_num = thisEntry["endMeasure"]

            # Whole entry in one measure (first = last):
            if firstmeasure_num == lastmeasure_num:

                # Both constraints:
                self.transferNotes(firstmeasure_num,
                                   start_offset_constraint=thisEntry["offset"],
                                   end_offset_constraint=thisEntry["endqstamp"],
                                   clef_also=True,
                                   voice=thisEntry["voice"])

            else:  # Entry spans more than one measure:

                # First measure, start constraint only
                self.transferNotes(firstmeasure_num,
                                   start_offset_constraint=thisEntry["offset"],
                                   clef_also=True,
                                   voice=thisEntry["voice"])

                # Middle measures, no constraint
                # (Does not run in the case of entry spanning 1 or 2 measures only.)
                for thismeasure_num in range(firstmeasure_num + 1, lastmeasure_num):
                    self.transferNotes(thismeasure_num,
                                       voice=thisEntry["voice"])

                # Last measure, end constraint only
                self.transferNotes(lastmeasure_num,
                                   end_offset_constraint=thisEntry["endqstamp"],
                                   voice=thisEntry["voice"])

        # self.melody_part.makeRests(fillGaps=True, in_place=True, hideRests=False)
        # TODO: currently no effect. Also unnecessary? Any regions that have no active elements.

    def prepareTemplate(self):
        """
        _prepare a template part to fill.
        Includes check that user selected (given) instrument matches one of the existing parts.
        Note: may be replaced by __eq__ on m21 when implemented.
        """

        part_num_to_use = 0  # for unspecified. Overwritten by user preference.

        if self.part_for_template:

            # _prep type to int
            if isinstance(self.part_for_template, int):  # fine, use that
                part_num_to_use = self.part_for_template

            else:  # via instrument.Instrument object
                if isinstance(self.part_for_template, str):  # str to object (or error if not)
                    self.part_for_template = instrument.fromString(self.part_for_template)
                # Check now an instrument.Instrument object
                if not isinstance(self.part_for_template, instrument.Instrument):
                    raise ValueError("Invalid instrument object")

                # Run conversion to int
                count = 0
                for p in self.score.parts:
                    this_instrument = instrument.fromString(p.partName)
                    if this_instrument.classes == self.part_for_template.classes:
                        part_num_to_use = count
                        break
                    else:
                        count += 1

        self.melody_part = self.score.parts[part_num_to_use].template(fillWithRests=False)
        # TODO consider using removeClasses=["Clef", "Instrument"]. prev. raised error.

    def transferNotes(
            self,
            measure_num: int,
            start_offset_constraint: float | None = None,
            end_offset_constraint: float | None = None,
            clef_also: bool = False,
            voice: int = 0
    ):
        """
        Transfer notes for a measure with optional start- and or end_offset_constraint.
        
        Both start and end constraint for single, within-measure entries.
        
        For a longer span:
        - start constraint only for the first measure;
        - end constraint only for the last;
        - neither in the middle.
        """

        thisMeasure = self.transfer_part.measure(measure_num)
        noteList = get_note_list(thisMeasure, voice_number=voice)

        for n in noteList:

            if start_offset_constraint and (n.offset < start_offset_constraint):
                # This note starts before beginning, so ignore entirely
                # NB: this works as long as annotations always begin on a note (required)
                continue

            if end_offset_constraint:
                noteqstamp = n.getOffsetInHierarchy(self.transfer_part)
                if noteqstamp < end_offset_constraint:  # Sic not <=
                    if noteqstamp + n.quarterLength > end_offset_constraint:
                        # Overlapping, so shorten duration:
                        n.quarterLength = end_offset_constraint - noteqstamp
                    # Insert, shortened where necessary
                    self.melody_part.measure(measure_num).insert(n.offset, n)
                continue

            # Otherwise:
            self.melody_part.measure(measure_num).insert(n.offset, n)

        # Clef, after the relevant measure is done.
        if clef_also:
            thisClef = noteList[0].getContextByClass("Clef")
            self.possiblyAddClef(thisClef, start_offset_constraint, measure_num)
            # Note: start_offset_constraint = offset of the span. Do not use noteList

    def possiblyAddClef(
            self,
            thisClef: clef.Clef,
            thisOffset: float | int,
            measureNumber: int):
        """
        Add clef to melody_part where the context changes (e.g., violin to cello).
        """
        if thisClef != self.currentClef:
            self.melody_part.measure(measureNumber).insert(thisOffset, thisClef)
            self.currentClef = thisClef

    def clear_formatting(self):
        """
        Clears formatting from orchestral score that would be inappropriate
        in the melody-only condition.
        
        _possibly TODO:
        - handle this with removeClasses within prepareTemplate.
        - test cases for each, e.g., prev. issue with page breaks.
        - slurs and hairpins limited: remove only if crossing Hauptstimme sections?
        """

        if self.cleared_formatting:
            return

        if not self.melody_part:
            self.makeMelody_part()

        for x in self.melody_part.recurse():
            if any(cls in x.classes for cls in
                   ["LayoutBase", "_pageLayout", "SystemLayout", "layout", "Slur", "DynamicWedge"]
                   ):
                self.melody_part.remove(x)
            if "Note" in x.classes:
                x.stemDirection = None  # equivalent to "unspecified"
            # if "Beam" in x.classes:  # Alternative to the below, if special case handling. note.beam.

        self.melody_part.makeBeams(inPlace=True)

        self.cleared_formatting = True

    def writeMelodyScore(
            self,
            out_path: Path | None,
            clearFormatting: bool = True,
            insert_partLabels: bool = True,
            other_part: bool = False,
            bass_part: bool = False
    ):
        """
        Writes the final melody part (made using makeMelody_part).
        Call directly to both make and write.
        """

        if not self.melody_part:
            self.makeMelody_part()

        if clearFormatting:
            if not self.cleared_formatting:
                self.clear_formatting()

        melodyScore = stream.Score()
        melodyScore.insert(0, self.melody_part)

        if insert_partLabels:
            for thisEntry in self.orderedAnnotationsList:
                te = expressions.TextExpression(thisEntry["partName"])
                te.placement = "above"
                self.melody_part.measure(thisEntry["measure"]).insert(thisEntry["offset"], te)

        # Metadata: Generic placeholders or from original score
        md = self.score.metadata
        melodyScore.insert(0, md)

        md.movementTitle = "Melody Score"
        # mvt = PurePath(self.in_path).parts[-2:-1]

        if not self.score.metadata.composer:
            md.composer = "Composer unknown"
            # md.composer = self.score.metadata.composer

        if other_part:  #
            if not self.other_part:
                self.make_other_part()
            melodyScore.insert(0, self.other_part)

        if bass_part:  #
            if not self.other_part:
                self.make_other_part()
            # Chords. NB counting bottom up. TODO copied from `orchestra_part_split`. Refactor shared.
            for n in other_part.recurse().notesAndRests:
                if n.isChord:
                    pitches = n.pitches
                    for i in range(len(pitches) - 1):
                        n.remove(pitches[i])  # remove all pitches except the last (highest) one

            melodyScore.insert(0, other_part)  # altered in place. Ok in all cases. We never need the other part again.

        if not out_path:
            out_path = self.path_to_score.parent
        out_path = out_path / f"{self.path_to_score.stem}_melody.{self.out_format}"
        melodyScore.write(fmt=self.out_format, fp=out_path)

    def make_other_part(self):
        """
        Insert a second part:
        currently simply a one-stave synthesis of the full score using chordify.
        TODO:
        - remove duplicated (if this note in melody_part then ignore)
        - possibly "bass line" alternative (lowest somewhat more reliable than highest for melody)
        """
        self.other_part = self.score.chordify()


# Static

def intBeat(beat):
    """Beats as integers, or rounded decimals"""
    if int(beat) == beat:
        return int(beat)
    else:
        return round(float(beat), 2)


def get_note_list(
        this_measure: stream.Measure,
        voice_number: int = 0
):
    """
    Retrieves the notes and rests from a measure.

    In the case of multi-voice measures, this returns just one voice.

    The choice of which voice is settable with voice_number argument.
    It defaults to 0 (the top voice).

    @param this_measure: stream.Measure object
    @param voice_number: (optionally) chose a voice in the case of In the case of multi-voice measures.
    @return:
    """
    num_voices = len(this_measure.voices)
    if num_voices > 0:
        return this_measure.voices[voice_number].notesAndRests
    else:
        return this_measure.notesAndRests


def meets_restrictions(
        annotation_string: str,
        restrictions: str | list | None
) -> bool:
    """
    Tests whether an annotation string (`annotationString`)
    meets set restriction conditions (set by `restrictions`).

    Restriction may be expressed either one of two ways.

    The first option is an explicit list,
    e.g.
    ["1", "2", "3", "4", "5", "6", "7", "8", "9"]
    or
    ["a", "b", "c", "d", "e", "f", "g", "h", "i"].
    
    >>> meets_restrictions("a", restrictions = ["a", "b"])
    True

    >>> meets_restrictions("a", restrictions = ["b", "c"])
    False
    
    The second option is a regex.

    If restrictions is a str, then it is assumed to be a regex pattern
    and each annotation will be tested against it with full match.

    For example, setting the `restrictions` argument to "\w"
    would be equivalent to `[a-zA-Z0-9_]`, meaning that the
    matches any (single) letter, numeric digit, or underscore character.

    >>> meets_restrictions("a", restrictions="\w")
    True

    >>> meets_restrictions("1", restrictions="\w")
    True

    >>> meets_restrictions("A", restrictions="\w")
    True

    >>> meets_restrictions("ABC", restrictions="\w")
    False

    This option should not be used for longer annotations like "a-dev" or "first theme".
    To avoid any such restriction, the default sets `restrictions = None`.

    """
    if type(restrictions) == str:
        if re.fullmatch(restrictions, annotation_string):
            return True
        return False
    elif type(restrictions) == list:
        if annotation_string in restrictions:
            return True
        return False
    else:
        raise TypeError("Invalid restrictions type.")


def process_one(
        path_to_score: Path,
        out_path_data: Path | None = None,
        out_path_score: Path | None = None,
        where: str = "lyric",
        part_for_template: int | str | instrument.Instrument | None = instrument.Violin(),
) -> None:
    """
    Update the tabular and melody scores for one source file.
    Straightforward realisation with no restrictions, other part, etc.
    """

    info = ScoreThemeAnnotation(path_to_score, part_for_template=part_for_template)
    info.getAnnotations(where=where)

    if not out_path_data:
        out_path_data = path_to_score.parent
    info.writeAnalysis(out_path_data)

    if not out_path_score:
        out_path_score = path_to_score.parent
    info.writeMelodyScore(out_path_score)


def get_corpus_files(
    sub_corpus_path: Path = CORPUS_PATH,
    file_name: str = "Beach*.mxl",
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


def updateAll(
        sub_corpus_path: Path = CORPUS_PATH,
        replace: bool = True
) -> None:
    """
    Update the tabular and melody scores for all source files in the corpus.
    @param sub_corpus_path: The part of the corpus to run on, default to all.
    @param replace: If true and there is already an "annotations.csv" file in this
        directory, then replace it; otherwise continue.
    """
    for f in get_corpus_files(sub_corpus_path):
        print(f"Processing {f}")
        p = f.parent
        if not replace:
            annotations = p / "annotations.csv"
            if annotations.exists:
                continue
        process_one(f)


# ------------------------------------------------------------------------------

if __name__ == "__main__":
    import doctest
    doctest.testmod()

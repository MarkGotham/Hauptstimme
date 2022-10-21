"""
===============================
HAUPTSTIMME (hauptstimme.py)
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

from music21 import converter
from music21 import clef
from music21 import expressions
from music21 import instrument
from music21 import metadata
from music21 import stream

import os
import re
import unittest

from typing import Optional


class ScoreThemeAnnotation:
    """
    End-to-end handling of
    importing a score,
    extracting annotations and
    (optionally) writing data and melody score files.
    """

    def __init__(self,
                 inPath: str,
                 fileName: str,
                 partForTemplate: int | str | instrument.Instrument | None = instrument.Violin(),
                 outFormat: str = "mxl"
                 ):

        pathToScore = os.path.join(inPath, fileName)
        self.score = converter.parse(pathToScore).toSoundingPitch()  # NB transpose
        self.checkTransposed()

        self.partForTemplate = partForTemplate
        self.outFormat = outFormat

        self.transferPart = None
        self.orderedAnnotationsList = None
        self.melodyPart = None
        self.otherPart = None
        self.clearedFormatting = False
        self.currentClef = "Treble"

    def checkTransposed(self):
        """
        Double-checks the transposition of orchestral scores to sounding pitch.
        """
        for p in self.score.parts:
            if not p.atSoundingPitch:
                raise ValueError("Despite attempting to set the score to sounding pitch, " +
                                 f"{p.partName} is still not transposed.")

    def getAnnotations(self,
                       restrictions: list | str | None = None):
        """
        Retrieve manually added lyrics from a part.
        Used for the identifying "the" melody and / or structural matters.

        This uses lyrics because it is easy to extract and to avoid false positives:
        - text expression can have numerals (in "1. solo", for instance).
        - no actual lyrics in almost any of this repertoire (except e.g., Beethoven 9/iv);
        - even where the score would have lyrics, 
        they are easy to remove for these purposes and often not
        present anyway (e.g., not converted by OMR).

        User-defined restrictions are optional (default is None).
        Restriction may be expressed either one of two ways.

        The first option is an explicit list,
        e.g.
        ["1", "2", "3", "4", "5", "6", "7", "8", "9"]
        or
        ["a", "b", "c", "d", "e", "f", "g", "h", "i"].

        The second option is a regex.
        If restrictions is a str, then it is assumed to be a regex pattern
        and each annotation will be tested against it with full match.

        For example, setting the `restrictions` argument to "\w"
        would be equivalent to `[a-zA-Z0-9_]`, meaning that the
        matches any (single) letter, numeric digit, or underscore character.

        This option should not be used for longer annotations like "a-dev" or "first theme".
        To avoid any such restriction, the default sets `restrictions = None`.
        """

        failMessage = "This tag does not conform to the user specified restrictions for ..."

        self.orderedAnnotationsList = []

        partCount = 0

        for thisPart in self.score.parts:

            # Simply part name
            partName = thisPart.partName
            partName = instrument.fromString(partName).instrumentAbbreviation
            # TODO: preserve violin I vs II and sim. Add abbreviation with part number to music21?

            for n in thisPart.recurse().notesAndRests:

                if n.lyric:

                    if n.isRest:  # NB: Rests with lyrics do not convert.
                        print(f"Lyric attached to rest in measure {n.measureNumber}. Ignored.")
                        continue

                    if restrictions:
                        if type(restrictions) == str:
                            if not re.fullmatch(restrictions, n.lyric):
                                print(failMessage)
                                print(f"... regex: '{n.lyric}' in m.{n.measureNumber}")
                                continue
                        elif type(restrictions) == list:
                            if n.lyric not in restrictions:
                                print(failMessage)
                                print(f"... list membership: '{n.lyric}' in m.{n.measureNumber}")
                                continue
                        else:
                            raise TypeError("Invalid restrictions type.")

                    # if no restrictions, and / or restriction conditions are met:
                    segmentData = {"measure": n.measureNumber,
                                   "offset": n.offset,
                                   "beat": n.beat,
                                   "partName": partName,
                                   "partNum": partCount,
                                   "label": n.lyric,
                                   "offsetInH": n.getOffsetInHierarchy(thisPart),
                                   "clef": n.getContextByClass("Clef"),
                                   "voice": 0}  # TODO handle all as extension of the note class?
                    if n.getContextByClass("Voice"):
                        segmentData["voice"] = n.getContextByClass("Voice").id  # NB not number

                    self.orderedAnnotationsList.append(segmentData)

            partCount += 1

        print(f"Done: {len(self.orderedAnnotationsList)} annotations")
        self.orderedAnnotationsList.sort(key=lambda x: x["offsetInH"])

        if len(self.orderedAnnotationsList) == 0:  # No annotations, so nothing to sort.
            return
        else:
            self.setAnnotationEnds()

    def setAnnotationEnds(self):
        """
        Having retrieved annotations (getAnnotations), if there are any, then sort them.

        TODO: more elegant solution
        """

        for index in range(len(self.orderedAnnotationsList) - 1):  # Last entry handled below.
            thisEntry = self.orderedAnnotationsList[index]
            nextEntry = self.orderedAnnotationsList[index + 1]

            thisEntry["endMeasure"] = nextEntry["measure"]
            thisEntry["endOffset"] = nextEntry["offset"]  # Not to be uses for comparison (often 0)
            thisEntry["endOffsetInH"] = nextEntry["offsetInH"]

        # Special case of last melody entry.
        lastMeasure = self.score.parts[0].getElementsByClass("Measure")[-1]
        lastEntry = self.orderedAnnotationsList[-1]
        lastEntry["endMeasure"] = lastMeasure.measureNumber
        lastEntry["endOffset"] = 50  # Fake number, longer than any real bar
        lastEntry["endOffsetInH"] = lastEntry["offsetInH"] + 10000  # Same, fake

    def writeAnalysis(self,
                      outPath,
                      headers: list | None = None
                      ):
        """
        Write the analysis (self.orderedAnnotationsList) information to a csv file.
        """

        if headers is None:
            headers = ["measure", "beat", "label", "partName", "partNum"]

        if len(self.orderedAnnotationsList) == 0:
            print(f"Fail: no annotations.")
            return

        else:
            pathToAnnotation = os.path.join(outPath, "annotations.csv")
            with open(pathToAnnotation, "w") as f:
                f.write(",".join(headers) + "\n")
                for annotationDict in self.orderedAnnotationsList:
                    annotationDict["beat"] = intBeat(annotationDict["beat"])
                    line = [str(annotationDict[h]) for h in headers]
                    f.write(",".join(line) + "\n")
            f.close()

    def makeMelodyPart(self):
        """
        Make a mini-score with just the main melody as retrieved from the annotations.
        
        Uses music21 stream.template to start with,
        removing the clef and instrument classes,
        and not "filling with rests",
        
        Uses measure information to handle voices,
        then offsetInH for end comparison.
        
        The default partForTemplate is the violin.
        This is settable at the class init with any of the following:
        - instrument.Instrument object (best practice);
        - int for a part number (if you"re sure!);
        - str for an instrument name*.

        *Approximate matches are supported in so far as they are recognisable
        through the (recently updated) music21.instrument.fromString() function.
        """
        self.prepareTemplate()

        self.currentClef = self.melodyPart[clef.Clef].first()

        for thisEntry in self.orderedAnnotationsList:

            pNum = thisEntry["partNum"]

            self.transferPart = self.score.parts[pNum]

            firstMeasureNo = thisEntry["measure"]
            lastMeasureNo = thisEntry["endMeasure"]

            # Whole entry in one measure (first = last):
            if firstMeasureNo == lastMeasureNo:

                # Both constraints:
                self.transferNotes(firstMeasureNo,
                                   startConstraint=thisEntry["offset"],
                                   endConstraint=thisEntry["endOffsetInH"],
                                   clefAlso=True,
                                   voice=thisEntry["voice"])

            else:  # Entry spans more than one measure:

                # First measure, start constraint only
                self.transferNotes(firstMeasureNo,
                                   startConstraint=thisEntry["offset"],
                                   clefAlso=True,
                                   voice=thisEntry["voice"])

                # Middle measures, no constraint
                # (Does not run in the case of entry spanning 1 or 2 measures only.)
                for thisMeasureNo in range(firstMeasureNo + 1, lastMeasureNo):
                    self.transferNotes(thisMeasureNo,
                                       voice=thisEntry["voice"])

                # Last measure, end constraint only
                self.transferNotes(lastMeasureNo,
                                   endConstraint=thisEntry["endOffsetInH"],
                                   voice=thisEntry["voice"])

        # self.melodyPart.makeRests(fillGaps=True, inPlace=True, hideRests=False)
        # TODO: currently no effect. Also unnecessary? Any regions that have no active elements.

    def prepareTemplate(self):
        """
        Prepare a template part to fill.
        Includes check that user selected (given) instrument matches one of the existing parts.
        Note: may be replaced by __eq__ on m21 when implemented.
        """

        partNumToUse = 0  # for unspecified. Overwritten by user preference.

        if self.partForTemplate:

            # Prep type to int
            if isinstance(self.partForTemplate, int):  # fine, use that
                partNumToUse = self.partForTemplate

            else:  # via instrument.Instrument object
                if isinstance(self.partForTemplate, str):  # str to object (or error if not)
                    self.partForTemplate = instrument.fromString(self.partForTemplate)
                # Check now an instrument.Instrument object
                if not isinstance(self.partForTemplate, instrument.Instrument):
                    raise ValueError("Invalid instrument object")

                # Run conversion to int
                count = 0
                for p in self.score.parts:
                    thisInstrument = instrument.fromString(p.partName)
                    if thisInstrument.classes == self.partForTemplate.classes:
                        partNumToUse = count
                        break
                    else:
                        count += 1

        self.melodyPart = self.score.parts[partNumToUse].template(fillWithRests=False)
        # TODO consider using removeClasses=["Clef", "Instrument"]. prev. raised error.

    def transferNotes(self,
                      measureNo: int,
                      startConstraint: Optional = None,
                      endConstraint: Optional = None,
                      clefAlso: bool = False,
                      voice: int = 0
                      ):
        """
        Transfer notes for a measure with optional start- and or endConstraint.
        
        Both start and end constraint for single, within-measure entries.
        
        For a longer span:
        - start constraint only for the first measure;
        - end constraint only for the last;
        - neither in the middle.
        """

        thisMeasure = self.transferPart.measure(measureNo)
        noteList = getNoteList(thisMeasure, voiceNumber=voice)

        for n in noteList:

            if startConstraint and (n.offset < startConstraint):
                # This note starts before beginning, so ignore entirely
                # NB: this works as long as annotations always begin on a note (required)
                continue

            if endConstraint:
                noteOffsetInH = n.getOffsetInHierarchy(self.transferPart)
                if noteOffsetInH < endConstraint:  # Sic not <=
                    if noteOffsetInH + n.quarterLength > endConstraint:
                        # Overlapping, so shorten duration:
                        n.quarterLength = endConstraint - noteOffsetInH
                    # Insert, shortened where necessary
                    self.melodyPart.measure(measureNo).insert(n.offset, n)
                continue

            # Otherwise:
            self.melodyPart.measure(measureNo).insert(n.offset, n)

        # Clef, after the relevant measure is done.
        if clefAlso:
            thisClef = noteList[0].getContextByClass("Clef")
            self.possiblyAddClef(thisClef, startConstraint, measureNo)
            # Note: startConstraint = offset of the span. Do not use noteList

    def possiblyAddClef(self,
                        thisClef: clef.Clef,
                        thisOffset: float | int,
                        measureNumber: int):
        """
        Add clef to melodyPart where the context changes (e.g., violin to cello).
        """
        if thisClef != self.currentClef:
            self.melodyPart.measure(measureNumber).insert(thisOffset, thisClef)
            self.currentClef = thisClef

    def clearFormatting(self):
        """
        Clears formatting from orchestral score that would be inappropriate
        in the melody-only condition.
        
        Possibly TODO:
        - handle this with removeClasses within prepareTemplate.
        - test cases for each, e.g., prev. issue with page breaks.
        - slurs and hairpins limited: remove only if crossing Hauptstimme sections?
        """

        if self.clearedFormatting:
            return

        if not self.melodyPart:
            self.makeMelodyPart()

        for x in self.melodyPart.recurse():
            if any(cls in x.classes for cls in
                   ["LayoutBase", "PageLayout", "SystemLayout", "layout", "Slur", "DynamicWedge"]
                   ):
                self.melodyPart.remove(x)
            if "Note" in x.classes:
                x.stemDirection = None  # equivalent to "unspecified"

        self.clearedFormatting = True

    def writeMelodyScore(self,
                         outPath,
                         clearFormatting=True,
                         insertPartLabels=True,
                         otherPart=False):
        """
        Writes the final melody part (made using makeMelodyPart).
        Call directly to both make and write.
        """

        if not self.melodyPart:
            self.makeMelodyPart()

        if clearFormatting:
            if not self.clearedFormatting:
                self.clearFormatting()

        melodyScore = stream.Score()
        melodyScore.insert(0, self.melodyPart)

        if insertPartLabels:
            for thisEntry in self.orderedAnnotationsList:
                te = expressions.TextExpression(thisEntry["partName"])
                te.placement = "above"
                self.melodyPart.measure(thisEntry["measure"]).insert(thisEntry["offset"], te)

        # Metadata: Generic placeholders or from original score

        md = metadata.Metadata()
        melodyScore.insert(0, md)

        md.title = "Melody Score"
        if self.score.metadata.title:
            md.title = ": ".join([self.score.metadata.title, md.title])

        md.composer = "Composer unknown"
        if self.score.metadata.composer:
            md.composer = self.score.metadata.composer

        if otherPart:  # default False
            if not self.otherPart:
                self.makeOtherPart()
            melodyScore.insert(0, self.otherPart)

        name = "melody." + self.outFormat
        melodyScore.write(fmt=self.outFormat, fp=os.path.join(outPath, name))

    def makeOtherPart(self):
        """
        Insert a second part:
        currently simply a one-stave synthesis of the full score using chordify.
        TODO:
        - remove duplicated (if this note in melodyPart then ignore)
        - possibly "bass line" alternative (lowest somewhat more reliable than highest for melody)
        """
        self.otherPart = self.score.chordify()


# Static

def intBeat(beat):
    """Beats as integers, or rounded decimals"""
    if int(beat) == beat:
        return int(beat)
    else:
        return round(float(beat), 2)


def getNoteList(thisMeasure, voiceNumber: int = 0):
    """
    Retrieves the notes and rests from a measure.

    In the case of multi-voice measures, this returns just one voice.

    The choice of which voice is settable with voiceNumber argument.
    It defaults to 0 (the top voice).
    """
    numVoices = len(thisMeasure.voices)
    if numVoices > 0:
        return thisMeasure.voices[voiceNumber].notesAndRests
    else:
        return thisMeasure.notesAndRests


def processOne(inPath: str,
               inFile: str,
               outPathData: str = ".",
               outPathScore: str = ".",
               partForTemplate: int | str | instrument.Instrument | None = instrument.Violin(),
               ):
    """
    Update the tabular and melody scores for one source file.
    Straightforward realisation with no restrictions, other part, etc.
    """
    info = ScoreThemeAnnotation(inPath, inFile, partForTemplate=partForTemplate)
    info.getAnnotations(restrictions=None)
    info.writeAnalysis(outPathData)
    info.writeMelodyScore(outPathScore)


corpusBasePath = os.path.join(os.path.dirname((os.path.realpath(__file__))), "..", "corpus")


def renameAll(fileFormat: str = ".csv",
              newName: str = "annotations"
              ):
    """
    Rename all files to the corpus standard.
    """
    for p, dname, fname in os.walk(corpusBasePath):
        for name in fname:
            if not name.endswith(fileFormat):
                continue
            before = os.path.join(p, name)
            after = os.path.join(p, newName + fileFormat)
            os.rename(before, after)


def updateAll(replace: bool = True):
    """
    Update the tabular and melody scores for all source files in the corpus.
    """
    for p, dname, fname in os.walk(corpusBasePath):
        for name in fname:
            if not name.endswith(".mxl"):  # hardcoded
                continue
            if not replace:
                annotations = os.path.join(p, "annotations.csv")
                if os.path.exists(annotations):
                    continue

            processOne(p, name, outPathData=p, outPathScore=p)


class Test(unittest.TestCase):

    def testHauptstimme(self):
        """
        Test case for a shortened version of Brahms 4-i,
        including a test of all 3 partForTemplate formats (int, str, instrument object).
        """

        p = os.path.join(corpusBasePath, "test/")  # Short form (long form option below)
        # p = os.path.join(corpusBasePath, "Brahms,_Johannes/Symphony_No.4,_Op.98/I")
        f = "score.mxl"

        for i in [8, 'violin', instrument.Violin()]:
            processOne(p, f, outPathData=p, outPathScore=p, partForTemplate=i)


if __name__ == "__main__":
    unittest.main()

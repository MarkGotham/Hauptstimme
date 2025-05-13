# Hauptstimme

When listening to music, our attention is drawn back and forth between different elements.
Often this is guided by following the main, most prominent melodic line: the _Hauptstimme_.
This repo is about that effect, providing:
- a corpus of orchestral scores, with human analysis annotations for where they think the "main theme" is,
- code for processing this - e.g., for creating a summative "melody score".


## Annotation task

Please see [this explanation](./annotation.md)
for more details on the annotation method and FAQs.

Here is an example of what the annotated scores look like.
This is a famous melody (the start of the main theme in Beethoven's 5th)
that's distributed among several parts.

![Annotated score extract](extract_example.png).


## Score design choices

Apart from the annotations, the scores themselves are introduced here for the first time.
As such, we also explain the [stylistic design criteria here](./score_design.md)
(Note: This content may move to the [OpenScore GitHub](https://github.com/openscore)).


## Corpus Summary

The full, core corpus consists of c.100 movements.

|Composer|Large scale work/s|Movements|
|---|---|---|
Bach, Johann Sebastian|B Minor Mass, BWV.232|27|
Bach, Johann Sebastian|Brandenburg Concerto No.3, BWV.1048|3|
Bach, Johann Sebastian|Brandenburg Concerto No.4, BWV.1049|3|
Beach, Amy|Symphony in E minor (Gaelic), Op.32|4|
Beethoven, Ludwig van|Complete Symphonies (1–9) |37|
Brahms, Johannes|Ein Deutsches Requiem, Op.45|1 (from 7)|
Brahms, Johannes|Complete Symphonies (1–4) | 16 |
Bruckner, Anton|Symphony No.5, WAB.105| 4/5 |

Movement numbering is complex in the following cases:
- Bach: B Minor Mass. The movements are numbered according to NBAII (1–23) and are split by movement where possible (e.g., 7a from 7b), but not in the case of dovetail (e.g., 4a and 4b are one with double bar line and editorial tempo marking).
- Bruckner: Symphony No.5, WAB.105. We split the 3rd movement into two files.

All of these cases include the files in the format `<identifier>` plus:
- `.mscz`: The annotated MuseScore file. Edit this file.
- `.mxl`: A conversion of the `.mscz` file.
- `_annotations.csv`: Information about each annotation including the qstamp, theme label, and instrument.
- `_melody.mxl`: The annotated melody segments stitched together to form a single-stave 'melody score'.
- `.mm.json`: The compressed ['measure map'](https://dl.acm.org/doi/10.1145/3625135.3625136) – a lightweight representation of the bar information to enable alignment with other corpora.
- `.csv`: A 'lightweight' .csv file extracted from the full score (with repeats expanded), indicating the highest pitch being played by each instrument part at every timestamp in which a change occurs in the score.
- `_part_relations.csv`: A derived analysis of the interplay between the score parts in each Hauptstimme annotation block.
- `_alignment.csv`: An alignment table containing timestamps for each score note onset in a set of public domain / open license audio recordings obtained from IMSLP. (These files only exist for scores where such recordings are available.)

The filename structure is as follows:
```
<composer>/<symphony>/<movement>/<files>
```

## Code Summary

We provide the `hauptstimme` package as well as the following code:
- `main.py`: Take a score's MuseScore file and produces the rest of the files specified above (except the alignment table).
- `build_corpus.py`: Produce all corpus files from each score's MuseScore file.
- `get_part_relations.py`: Take a score's MusicXML file and produce a part relationships summary.
- `compare_segmentations.py`: Take a score's MusicXML file and perform a comparison of the Hauptstimme annotation points to three different sets of automatic segmentation points (novelty-based (tempogram features), novelty-based (chromagram features), and changepoint detection-based).
- `align_score_audios.py`: Take a score's MuseScore/MusicXML file and a set of audio files, then align the audio files to the score, producing an alignment table.
- `demo.ipynb`: A demonstration of how functions in the haupstimme package can be used.

Possible future TODOs:
- Renumbering scores based on measure maps.
- Analysis of hypotheses such as 'loud dynamic and lots of unison = camera on whole orchestra'.
- Distance between melodic blocks and clustering.
- Extracting all instances of a particular theme.
- Allowing multiple annotations at the same timestamp (currently causes issues with the part relationship summaries, but would be useful in the case of polyphony).
- Produce instrument range data from our corpus (see `range_data_adler_chon_huron_devlieger.csv`)

Development was done in Python 3.11.

## Acknowledgements

Many thanks to:
- Deutsche Telekom for funding part of this work in the context of the 'Beethoven X' project.
- Fellow 'Beethoven X' project team members for discussions.
- Annotators:
  - On the 'Beethoven X' project, including Nicolai Böhlefeld and many others.
  - At Cornell, Eastman, TU Dortmund, Durham, and elsewhere.
- Transcribers, both:
  - in our immediate team, and 
  - more widely across the MuseScore community, members who made transcriptions freely available under the CCO licence and named their source edition.


## Licence 

- Scores: CC0 1.0 Universal
- Annotations: CC-By-SA
- Code: MIT

All scores have been copied from clearly identified and unequivocally public source editions on IMSLP.
Transcribers have committed to making these transcriptions using that public source edition, and working from scratch.
We have confidence in our team and their work but obviously cannot make any guarantees.
If you see anything that we ought to review, please let us know.


## Citation

To follow.

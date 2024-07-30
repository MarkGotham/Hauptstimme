# Hauptstimme

When listening to music, our attention is drawn back and forth between different elements.
Often this is guided by following the main, most prominent melodic line: the _hauptstimme_.
This repo is about that effect, providing:
- a corpus of orchestral scores, with human analysis annotations for where they think the "main theme" is.
- code for processing this, e.g., for creating a summative "melody score"


## Annotation task

Please see [this explanation](./annotation.md)
for more details on the annotation method and FAQs.


## Score design choices

Apart from the annotations, the scores themselves are introduced here for the first time.
As such, we also explain the [stylistic design criteria here](./score_design.md)
(Note: This content may move to the [OpenScore GitHub](https://github.com/openscore))


## Corpus Summary

```
<composer>/<symphony>/<movement>/<files>
```

The full, core corpus consists of over 100 movements:

- Bach, JS:
  - B Minor Mass,
    - 27 movements (ish ... depending on how you count it).
    - NB the movements numbered here according to NBAII (1–23) are are split by movement ...
      - ... where possible (e.g., 7a from 7b)
      - ... not in the case of dovetail (e.g., 4a.-b. as one with double bar line and editorial tempo marking).
  - Brandenburg Concerto No.3 (BWV 1048)
    - 3 movements
  - Brandenburg Concerto No.4 (BWV 1049)
    - 3 movements
- Beach, Amy:
  - 1 symphony, the 'Gaelic',
    - 4 movements
- Beethoven
  - 9 symphonies
    - 37 movements
- Brahms, Johannes:
  - 4 symphonies,
    - 16 movements
- Bruckner, Anton:
  - 1 symphony, the 5th,
    - 4 movements

All of these cases include the files in the format `<identifier>` plus:
- `.mscz`: The annotated MuseScore file. Edit this file.
- `.mxl`: A conversion of the `.mscz` file.
- `_annotations.csv`: The qstamp, bar, beat, theme label and instrument of each annotation.
- `_melody.mxl` these melody segments stitched together in one single-stave files


## Acknowledgements

Many thanks to:
- Deutsche Telekom for funding part of this work in the context of the 'Beethoven X' project
- Fellow 'Beethoven X' project team members for discussions.
- Annotators 
  - On the 'Beethoven X' project, including Nicolai Böhlefeld and many others.
  - At Cornell, Eastman, TU Dortmund, Durham, and elsewhere.
- Transcribers, both:
  - in our immediate team, and 
  - more widely across the MuseScore community, members who made transcriptions freely available under the CCO licence and named their source edition.


## Licence 

- Scores: CC0 1.0 Universal
- Annotations: CC-By-SA
- Code: CC-By-SA

All scores have been copied from clearly identified and unequivocally public source editions on IMSLP.
Transcribers have committed to making these transcriptions using that public source edition, and working from scratch.
We have confidence in our team and their work but obviously cannot make any guarantees.
If you see anything that we ought to review, please let us know.


## Citation

To follow ;). Provisionally Martins et al. 2024.

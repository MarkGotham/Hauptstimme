# Hauptstimme

When listening to music, our attention is drawn back and forth between different elements.
Often this is guided by following the main, most prominent melodic line: the _hauptstimme_.
This repo is about that effect, providing
- a corpus of orchestral scores, with human analysis annotations for where they think the "main theme" is.
- code for processing this, e.g., for creating a summative "melody score"

Please see [this explanation on fourscoreandmore](https://fourscoreandmore.org/hauptstimme/)
for more details on the annotation method and FAQs.

## Corpus Directory

```
<composer>/<symphony>/<movement>/<files>
```

The full, core corpus consists of c.102 movements:

- Bach, JS:
  - B Minor Mass,
    - 27 movements (depending on how you count it).
    - NB the movements numbered here according to NBAII (1–23) are are split by movement ...
      - ... where possible (e.g., 7a from 7b)
      - ... not in the case of dovetail (e.g., 4a.-b. as one with double bar line and editorial tempo marking).
  - Brandenburg Concerto No.3 (BWV 1048)
    - 3 movements
  - Brandenburg Concerto No.4 (BWV 1049)
    - 3 movements
  - Fuga (Ricercata) a 6 voci, from *The Musical Offering*, BWV 1079, orchestrated by Anton von Webern
    - 1 movement
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

Again, please see [fourscoreandmore for images and more](https://fourscoreandmore.org/hauptstimme/).

## Score design choices

- In the `.mss` style:
  - Justify full page, max staff size to fill (but not overfill). 
  - All present instrument showing at all time (none hidden).
  - Import the `.mss` style file in-app or with the command line:
    - `mscore <before_file_name>.mscz --style <style-file-name>.mss -o <after_file_name>.mscz`.
- Every part on a separate stave (e.g., Flute 1 separate from Flute 2) for clarity and interoperability.
  - This partly through the `orchestra_part_split` functionality.
  - Connect bar lines through those like instruments e.g., Flutes 1 and 2; Horns 1, 2, and 3.
- Part names:
  - Full part names in the format `<transposition where relevant> <instrument> <number>`, e.g., `A Clarinet 2`.
  - Abbreviated names without transposition or period character, e.g., `Cl 2`.
  - String instruments in the singular e.g., `Violin 1` (as in 'the violin 1 part')

## Acknowledgements

Many thanks to:
- Deutsche Telekom for funding part of this work in the context of the 'Beethoven X' project
- Fellow 'Beethoven X' project team members for discussions.
- Annotators 
  - On the 'Beethoven X' project, including Nicolai Böhlefeld and many others.
  - At Cornell, Eastman, TU Dortmund, Durham, and elsewhere.
- Transcribers in our team, and the wider MuseScore community for making their transcriptions freely available under the CCO licence, notably:
  
## Licence 

- Scores: CC0 1.0 Universal
- Annotations: CC-By-SA
- Code: CC-By-SA


## Citation

To follow ;). Provisionally Martins et al. 2024.

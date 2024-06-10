# Hauptstimme

When listening to music, our attention is drawn back and forth between different elements.
Often this is guided by following the main, most prominent melodic line: the _hauptstimme_.
This repo is about that effect, providing
- a corpus of orchestral scores, with human analysis annotations for where they think the "main theme" is.
- code for processing this, e.g., for creating a summative "melody score"

## The Annotation Task, in Brief:

- Identify where the 'main' melody is throughout an orchestral movement.
  - Note: Clearly this is partly a subjective judgement. Do not aim for 'perfection'
- Name those melodies.
  - By default, simply use 'a', 'b', 'c' for each successive theme.
  - If you prefer to use names like 'fate theme' that's fine – just be consistent.
- Annotate the scores with a 'lyric' text below the start of each new melody in the relevant part, i.e.:
  - Identify the start of a theme,
  - Click on a note:
    - the specific note where the theme starts …
    - … in the most prominent instrument (e.g., the first violin),
  - Press Ctrl+L (Windows) or CMD+L (Mac) to insert a 'lyrics text'
  - Enter the theme label (e.g., 'a' for the first theme you identify) as a lyric.
  - Click anywhere else to exit the text entry mode and continue.
  - Rinse and repeat! (Copy'n'paste can be helpful here.)

Please see [this explanation on fourscoreandmore](https://fourscoreandmore.org/hauptstimme/) for more details and FAQs.

## Code

- [hauptstimme.py](./code/hauptstimme.py): the main module for extracting and processing annotations
- [Large_red_lyrics.mss](./code/Large_red_lyrics.mss): a style sheet which makes all the lyric annotations large (font size 30) and in colour (red). To apply this style to a file in the corpus, put the `.mss` file in your MuseScore style folder and run 
`mscore <before_file_name>.mscz --style large_red_lyrics.mss -o <after_file_name>.mscz`.

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

## Acknowledgements

Many thanks to:
- Deutsche Telekom for funding part of this work in the context of the 'Beethoven X' project
- Fellow 'Beethoven X' project team members for discussions.
- Annotators 
  - On the 'Beethoven X' project, including Nicolai Böhlefeld and many others.
  - At Cornell, Eastman, TU Dortmund, Durham, and elsewhere.
- MuseScore users for transcribing scores and making them freely available under the CCO licence, notably:
  - Jay W: [Brahms Symphonies](https://musescore.com/user/43726/sets/5150330)
  - Mike320: [Beach Symphony](https://musescore.com/user/6105546/sets/4187216)

# Hauptstimme Annotation Task

When listening to music, our attention is drawn back and forth between different elements.
Often this is guided by following the main, most prominent melodic line: the _Hauptstimme_.
This task aims to capture something of that effect.


## The Main Task, in Brief:

- Identify where the 'main' melody is throughout an orchestral movement.
  - Note: Clearly this is partly a subjective judgement. Do not aim for 'perfection'.
- Name those melodies.
  - By default, simply use 'a', 'b', 'c' for each successive theme.
  - If you prefer to use names like 'fate theme' that's fine – just be consistent.
- Annotate the scores at the start of each new melody, either:
  - with a 'lyric' text below the relevant part, or
  - if the score already has lyrics, with a 'stave text' expression above the relevant part.
- I.e.:
  - Identify the start of a theme,
  - Click on a note:
    - the specific note where the theme starts …
    - … in the most prominent instrument (e.g., the first violin),
  - Either:
    - press Ctrl+L (Windows) or CMD+L (Mac) to insert a 'lyric' text, or 
    - if the score already has lyrics, press Ctrl+**T** (Windows) or CMD+**T** (Mac) to insert a 'stave text' expression.
  - Enter the theme label (e.g., 'a' for the first theme you identify) in the text box that appears.
  - Click anywhere else to exit the text entry mode and continue.
  - Rinse and repeat! (Copy & paste can be helpful here.)


## Review phase

- Use the 'melody score' to review. It's easier to spot errors there, e.g.:
  - Missing labels (e.g., 100 measures with no change).
  - Inconsistent labels (e.g., same theme labelled differently when it returns).
- Make any changes in the original score, not the 'melody score'.


## Further notes, suggestions, and FAQs

**What do I do when there's more than one theme at once?**
- Please still chose the one you hear as 'primary', as the _Hauptstimme_.
  - We're not aiming for a comprehensive analysis of all themes / motives used.
  - We only want _your view_ of the _main melody_ (which melody is most prominent, and in which instrument).
  - This is a judgement call and sometimes there's no single 'right' answer.
  - All corpora (indeed all analysis) involve some trade-off of this kind.
- Some rules of thumb, with all else being equal. In general, chose the part which ... :
  - ... is **fastest-moving** ... but not figuration / filler (melodies need a moment to breath between phrases!).
  - ... is **highest** ... but not "descant"-style lines above the main tune.
  - ... **resolves voice-leading** correctly by connecting to segments before and after in the same voice and octave (i.e., avoiding large leaps). ... but not at the expense of the "true" line.
  - ... is **consistent**, e.g.,:
    - In a fugue, go for every entrance of the subject/answer.
      - Pick out the first note however it has been altered (it's common to alter the first note of a fugue).
      - Pick one set of corresponding parts in the case of a double canon.
  - ... marks the **start of high-level groupings**, e.g., 2- and 4- bar phrases and new formal structural sections.


**What do I do when more than one instrument is playing the main theme?**

(This will obviously happen a lot!) Here are some more rules of thumb:

- Choose the one you think is most prominent (e.g., Flute 1).
	- Certain instruments tend to take priority. 
  - E.g., in choral-orchestral music, we tend to prioritise the voices. Exceptions include Bach's practice of bringing the trumpets in later-on in the movement (within corpus see the final movement of the B Minor Mass).
	- More generally, the loudest instruments are often the most prominent. Those trumpets again...
- **Don't** label all the instruments with this theme:
  - We have code to retrieve this relationship between parts automatically.
  - It's often useful to be made to choose the _main_ instrument, even if that's sometimes arbitrary.
- If you find that the musical choice is completely arbitrary, then opt for solutions that solve for the criteria listed for the previous FAQ, e.g., staying in the same octave as the segments before and after (to avoid large leaps).


**What about rests?**

- Annotations (lyrics or text expressions) must always be added to _notes_ and not rests.
  - MuseScore will let you add a lyric to a rest, but this will get lost in conversion, so avoid doing that.
- We can (often) have rests between phrases by leaving the filler unannotated (rest at the end of the preceding segment).


**Can basslines be melodic?**

- In theory, yes.
- In practice, we almost never want a bassline Hauptstimme annotation.
	- We can pick up the bassline as a separate part for 2-voice reduction automatically.
- Chose the bassline if there’s really nothing else going or it simply IS the melody.


**Where do themes end?**

- That's defined by where the next one starts.
- There are cases where that's not ideal, but ...
  - it's not worth doubling the scale of this task by also specifying endings,
  - we don't support overlapping here (we enforce _a single moment_ of change).


**Must I use MuseScore?**

- For the _musical preparation_ of getting to know the score, you may well want to prefer to do this away from MuseScore. This part is entirely up to you! 
- E.g., you could use:
  - a physical, printed copy of the score with an actual recording of the work, and then
  - transfer the annotations / observations over later.
- For the *annotation / mark up* you can use any notation package that exports MusicXML (e.g., Dorico, Finale, Sibelius).


**What melody label / tag / names can I use?**

- In general, just use 'a', 'b', etc.
  - We all know that these themes will be altered at subsequent appearances, but if you really want to indicate a greater change from 'a' etc., then you might like to adopt one of the following conventions:
    - Brackets: (a).
    - Prime: a'.
    - Combinations: a+b.
    - 'Dev': a-dev.
- That said, you're welcome to use anything you like. Feel free to go into detail:
  - E.g., "first subject group, main, 'fate' theme, motiv x"
  - (… but obviously it's a lot more work to keep track of all that.)
- While the _Hauptstimme_ will usually be melodic, there are some moments with cadential fragments or the like where you want to register the movement between instruments, but where no melodic label fits. We have two main options in these cases:
  - use the prevailing melodic label (if it feels like a continuation of the context),
  - reserve a new special label like 'x' for these 'non-melodic melodies'.
- We can also use different Hauptstimme labels to annotate more different contrapuntal lines.


**What about when there are lyrics?**	
 
- Use text expression for the annotation (as mentioned above).
- The start of musical phrases will often align with textual phrases (sentences, or even single words), but no need to force this: follow the music; we have other automatic tools for handling text.


**'More is more' or 'less is more'?**

- If in doubt, _more is more_! E.g., these annotations can also mark phrase boundaries:
  - For instance, repeatedly entering the same label (e.g., 'a') on the same instrumental part is still valuable if it indicated each iteration of a motiv.
    - That's valuable information and doesn't detract from the main task or pose any problem for the code.
  - In such cases, it's useful to have an annotation on the start of each larger section even if the instrument and label stay the same, so again, be sure to add an extra one even if the melody stays in the same part.
- There is no _minimum length of gap_. Some moments call for extremely quick alternations, e.g., occasional "hocket", such as in the first movement of the B Minor Mass where Bach goes back and forth every second eighth note.
	- (For certain tasks, we may use code to simplify these moments such that extremely short durations are combined, so aim to make the last such entry the start of a longer section.)
  - Exceptions include "filler" between themes: if it's not a melodic theme, we don't need it.
    - E.g., B Minor Mass 7a, bar 2: we could follow the "filler" movement, but in bar 1 we see “the theme” quite clearly, so leave the bar 2 version to match that. Elsewhere, it’s more complex.
- We aim for a _maximum gap_ between annotations of roughly 4 bars.

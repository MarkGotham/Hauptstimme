"""
NAME
===============================
Part Relationships (part_relationships.py)


BY
===============================
James Hui and Matt Blessing, 2024


LICENCE:
===============================
Creative Commons Attribution-ShareAlike 4.0 International License
https://creativecommons.org/licenses/by-sa/4.0/


ABOUT:
===============================
Functions for producing part relationship summaries for scores.
These compare each instrument part to the 'main' melody part as well as
each other in each Hauptstimme annotation block.
"""
import pandas as pd


def get_pitch_class(pitch):
    """
    Given a pitch in Scientific Pitch Notation (SPN), obtain the pitch
    class.

    Args:
        pitch (str): A pitch in SPN.

    Returns:
        The pitch class.
    """
    return pitch[:-1]


def get_enharmonic_pitch_class(pitch):
    """
    Given a pitch in Scientific Pitch Notation (SPN), obtain the
    enharmonic pitch class (G = G# = Gb).

    Args:
        pitch (str): A pitch in SPN.

    Returns:
        The enharmonic pitch class.
    """
    return pitch[0]


class Part_Relations:
    """
    A class to summarise the part relationships in a particular region 
    of a score.
    Can be used to build a summary of the part relationships in an 
    entire score.
    """

    def __init__(self, df_score_lw, qstamp_start, qstamp_end):
        """
        Args:
            df_score_lw (pd.DataFrame): The lightweight data frame for
                a score.
            qstamp_start (scalar): The qstamp at the start of the 
                region. 
            qstamp_end (scalar): The qstamp at the end of the region.

        Raises:
            ValueError: If the region contains no notes.
        """
        self.instruments = df_score_lw.columns[4:].tolist()
        self.df_block_lw = df_score_lw[(df_score_lw["qstamp"] >= qstamp_start)
                                       & (df_score_lw["qstamp"] <= qstamp_end)]
        if self.df_block_lw.empty:
            raise ValueError(
                "Error: No data found between start and end qstamps.")

        self.qstamp_start = qstamp_start
        self.qstamp_end = qstamp_end

        self.note_order = ["C", "D", "E", "F", "G", "A", "B"]
        self.notes_per_octave = len(self.note_order)

    def is_unison(self, instrument1, instrument2):
        """
        Args:
            instrument1 (str): The first instrument's name.
            instrument2 (str): The second instrument's name.

        Returns:
            Whether the two instruments are playing in unison 
            throughout the score region (bool).

        Raises:
            ValueError: If either instrument does not exist in the score.
        """
        if (instrument1 not in self.df_block_lw.columns or
                instrument2 not in self.df_block_lw.columns):
            raise ValueError("Error: Instrument not found in data frame.")

        if self.df_block_lw[instrument1].equals(
                self.df_block_lw[instrument2]):
            if (self.df_block_lw[instrument1] == "r").all():
                return False
            else:
                return True
        return False

    def is_parallel_octave(self, instrument1, instrument2):
        """
        Args:
            instrument1 (str): The first instrument's name.
            instrument2 (str): The second instrument's name.

        Returns:
            Whether the two instruments are playing parallel octaves 
            throughout the score region (bool).

        Raises:
            ValueError: If either instrument does not exist in the score.
        """
        if (instrument1 not in self.df_block_lw.columns or
                instrument2 not in self.df_block_lw.columns):
            raise ValueError("Error: Instrument not found in data frame.")

        if self.df_block_lw[instrument1].apply(get_pitch_class).equals(
                self.df_block_lw[instrument2].apply(get_pitch_class)):
            if (self.df_block_lw[instrument1] == "r").all():
                return False
            else:
                return True
        return False

    def is_parallel_interval(self, instrument1, instrument2, interval):
        """
        Args:
            instrument1 (str): The first instrument's name.
            instrument2 (str): The second instrument's name.

        Returns:
            Whether the two instruments are playing a parallel 
            non-octave interval throughout the score region (bool).

        Raises:
            ValueError: If either instrument does not exist in the score.
            ValueError: If the interval is not in a valid range.
        """
        if (instrument1 not in self.df_block_lw.columns or
                instrument2 not in self.df_block_lw.columns):
            raise ValueError("Error: Instrument not found in data frame.")

        if interval < 1 or interval >= self.notes_per_octave:
            raise ValueError("Error: Interval must be between 1 and " +
                             f"{self.notes_per_octave - 1} inclusive.")

        if (self.df_block_lw[instrument1] == "r").all():
            return False

        for _, row in self.df_block_lw.iterrows():
            notes_pair = row[[instrument1, instrument2]].values
            if "r" in notes_pair:
                # If one is a rest and one is a note
                if notes_pair[0] != notes_pair[1]:
                    return False
            else:
                note_values = [
                    self.note_order.index(get_enharmonic_pitch_class(note))
                    for note in notes_pair
                ]
                note_values.sort()

                if (note_values[1] - note_values[0]) != interval:
                    return False

        return True

    def get_summary_row(self, main_part):
        """
        Args:
            main_part (int): The index of the instrument playing the
                "Main Part".

        Returns:
            row (pd.DataFrame): A row summarising the part relations
                in a particular score region.
        """
        row = {"qstamp_start": self.qstamp_start,
               "qstamp_end": self.qstamp_end}

        # `instrument` = the instrument whose row entry we are writing
        for instrument in self.instruments:
            row[instrument] = []
            # `other_instrument` = the instrument we are comparing to
            for other_instrument in self.instruments:
                if instrument == self.instruments[main_part]:
                    row[instrument] = "Main Part"
                    continue

                if instrument == other_instrument:
                    # Don't compare part to itself
                    continue

                if other_instrument == self.instruments[main_part]:
                    other_instr_text = "Main"
                else:
                    other_instr_text = other_instrument

                if self.is_unison(instrument, other_instrument):
                    row[instrument].append(f"U({other_instr_text})")
                elif self.is_parallel_octave(instrument, other_instrument):
                    row[instrument].append(f"P8({other_instr_text})")
                else:
                    for interval in range(1, self.notes_per_octave):
                        if self.is_parallel_interval(instrument,
                                                     other_instrument,
                                                     interval):
                            row[instrument].append(f"P{interval}" +
                                                   f"({other_instr_text})")
                            break
            if isinstance(row[instrument], list):
                row[instrument] = "&".join(row[instrument])

        return row


def get_part_relationship_summary(lightweight_score_filename,
                                  annotations_filename):
    """
    Given a score as a lightweight data frame and a data frame for the
    score's Hauptstimme annotations, get a data frame summarising the
    relationships between parts in each Hauptstimme annotation block.

    Args:
        lightweight_score_filename (str): The local filename of the
            'lightweight' score .csv file.
        annotations_filename (str): The local filename of the
            Hauptstimme annotations file.

    Returns:
        df_summary (pd.DataFrame): A data frame summarising the part
            relationships in each Hauptstimme annotation block.
    """
    df_score_lw = pd.read_csv(lightweight_score_filename)
    df_annotations = pd.read_csv(annotations_filename)

    df_annotations.rename(columns={"qstamp": "score_qstamp"}, inplace=True)
    df_merged = df_score_lw.merge(df_annotations, on=["measure", "beat"])
    # Get the Hauptstimme segmentation points
    seg_pts = df_merged["qstamp"].sort_values().to_list()
    # Get the part number for each annotation (will correspond to index
    # in the instrument columns of the lightweight score data frame)
    melody_parts = df_merged["part_num"].to_list()

    # Get pairs of segmentation points that create regions in the score
    annotation_block_pts = list(zip(seg_pts, seg_pts[1:]))
    annotation_block_pts.append((seg_pts[-1], df_score_lw["qstamp"].max()))

    df_summary = pd.DataFrame(
        columns=["qstamp_start", "qstamp_end", *df_score_lw.columns[4:]])

    # Iteratively build part relations summary data frame
    for i, (start, end) in enumerate(annotation_block_pts):
        block_summary = Part_Relations(df_score_lw, start, end)
        block_summary_row = pd.DataFrame(
            block_summary.get_summary_row(melody_parts[i]),
            index=[0]
        )
        df_summary = pd.concat([df_summary, block_summary_row])

    df_summary.reset_index(drop=True, inplace=True)

    return df_summary

"""
NAME
===============================
Instrument Parts Comparisons (comparisons.py)


BY
===============================
JamesHLS, 2024


LICENCE:
===============================
Creative Commons Attribution-ShareAlike 4.0 International License
https://creativecommons.org/licenses/by-sa/4.0/


ABOUT:
===============================
Given a score csv file and segmentation points, find parallel harmonies between different instrument parts in each segment

"""
import pandas as pd
import numpy as np
import utils
import os


def remove_octave_number(note):
    return note[:-1]


class Compare:
    def __init__(self, source, q_start, q_end, fill_rests=False):
        # error checking
        self.instruments = source.columns[3:-1].tolist()
        # check type of source['qstamp'] & q_start, q_end
        if not isinstance(q_start, (int, float)) or not isinstance(q_end, (int, float)):
            raise ValueError("q_start and q_end must be integers or floats")
        if not isinstance(source['qstamp'][0], (int, float)):
            raise ValueError("qstamp in source must be integers or floats")
        if q_start > q_end:
            raise ValueError("Start qstamp must be less than end qstamp")
        self.complete_segment = source[(source['qstamp'] >= q_start) & (source['qstamp'] <= q_end)]
        if self.complete_segment.empty:
            raise ValueError("No data found between start and end qstamps")
        
        if fill_rests:
            self.complete_segment = self.complete_segment.replace('r', pd.NA)
            self.complete_segment = self.complete_segment.ffill()
        self.complete_segment = self.complete_segment.fillna('r')  # start of piece rests when fill_rests / NaN values when not fill_rests
        
        self.q_start = q_start
        self.q_end = q_end
        # note ordering array
        self.note_order = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
        self.notes_per_octave = len(self.note_order)  # 7

    def output(self, instrument1=None, instrument2=None):
        if instrument1 and instrument2:
            return self.complete_segment[['qstamp', instrument1, instrument2]]
        return self.complete_segment

    def is_unison(self, instrument1, instrument2):
        if instrument1 not in self.complete_segment.columns or instrument2 not in self.complete_segment.columns:
            raise ValueError("Instrument not found in dataframe")
        segment = self.complete_segment[['qstamp', instrument1, instrument2]]
        if segment[instrument1].equals(segment[instrument2]):
            return True
        return False

    def is_parallel_octave(self, instrument1, instrument2):
        if instrument1 not in self.complete_segment.columns or instrument2 not in self.complete_segment.columns:
            raise ValueError("Instrument not found in dataframe")
        segment = self.complete_segment[['qstamp', instrument1, instrument2]]
        if segment[instrument1].apply(remove_octave_number).equals(
                segment[instrument2].apply(remove_octave_number)
        ):
            return True
        return False

    def is_parallel_interval(self, instrument1, instrument2, interval):
        if instrument1 not in self.complete_segment.columns or instrument2 not in self.complete_segment.columns:
            raise ValueError("Instrument not found in dataframe")
        segment = self.complete_segment[['qstamp', instrument1, instrument2]]
        interval -= 1  # 1 = unison, 2 = 1 note apart, etc.
        if interval < 0:
            raise ValueError("Interval must be at least 1")
        if interval > self.notes_per_octave:
            raise ValueError("Interval must be less than or equal to 7")

        for _, row in segment.iterrows():
            notes_pair = row.values[1:]
            if 'r' in notes_pair:
                if notes_pair[0] == notes_pair[1]:  # both are rests
                    continue
                else:  # one is a rest, one is a note
                    return False

            # note_values = note[0] index + octave_number * 7
            note_values = [self.note_order.index(note[0]) for note in notes_pair]
            note_values.sort()

            if (note_values[1]  - note_values[0] ) == interval:
                continue
            else:
                return False
        return True

    def is_parallel_abs_interval(self, instrument1, instrument2, interval):
        if instrument1 not in self.complete_segment.columns or instrument2 not in self.complete_segment.columns:
            raise ValueError("Instrument not found in dataframe")
        segment = self.complete_segment[['qstamp', instrument1, instrument2]]
        interval -= 1
        if interval < 0:
            raise ValueError("Interval must be at least 1")
        if interval > self.notes_per_octave:
            raise ValueError("Interval must be less than or equal to 7")

        for _, row in segment.iterrows():
            notes_pair = row.values[1:]
            if 'r' in notes_pair:
                if notes_pair[0] == notes_pair[1]:
                    continue
                else:
                    return False
            note_values = [self.note_order.index(note[0]) + int(note[-1]) * self.notes_per_octave for note in notes_pair]
            note_values.sort()
            if note_values[1] - note_values[0] == interval:
                continue
            else:
                return False
        return True
    
    def get_summary_row(self, main_part=0):
        col_names = ['q_start', 'q_end']+self.instruments
        row = {'q_start': self.q_start, 'q_end': self.q_end}

        parallel_pairs = [[] for _ in range(8)]  # 0: unison, 1: parallel 2, 2: parallel 3, etc.

        # main_part = self.instruments.index("Violins 1")

        for i, instrument in enumerate(self.instruments):
            if i == main_part:
                row[instrument] = 'Main Part'
            else:
                # find relationship between main_part and other instruments
                # parallel_pairs array to keep track, remove in the future if not needed
                found = False
                if self.is_unison(self.instruments[main_part], instrument):
                    row[instrument] = "U(Main)"
                    parallel_pairs[0].append((self.instruments[main_part], instrument))
                    found = True
                elif self.is_parallel_octave(self.instruments[main_part], instrument):
                    row[instrument] = "P8(Main)"
                    parallel_pairs[7].append((self.instruments[main_part], instrument))
                    found = True
                for interval in range(2, 8):
                    if self.is_parallel_interval(self.instruments[main_part], instrument, interval):
                        row[instrument] = f"P{interval}(Main)"
                        parallel_pairs[interval-1].append((self.instruments[main_part], instrument))
                        found = True
                        break
                if not found:
                    row[instrument] = "N(Main)"
        for instrument in self.instruments:
            if instrument == self.instruments[main_part]:
                continue
            # find relationship between all instruments
            for i, other_instrument in enumerate(self.instruments):
                if instrument == other_instrument or other_instrument == self.instruments[main_part]:
                    continue
 
                if self.is_unison(instrument, other_instrument):
                    parallel_pairs[0].append((instrument, other_instrument))
                    row[instrument] += f"&U({other_instrument})"
                elif self.is_parallel_octave(instrument, other_instrument):
                    parallel_pairs[7].append((instrument, other_instrument))
                    row[instrument] += f"&P8({other_instrument})"
                else:
                    for interval in range(2, 8):
                        if self.is_parallel_interval(instrument, other_instrument, interval):
                            parallel_pairs[interval-1].append((instrument, other_instrument))
                            row[instrument] += f"&P{interval}({other_instrument})"
                            break
                
        return row

    def generate_score_summary(self, df, segment_points, main_parts=[]):
        # returns a dataframe
        # segment_points: list of qstamps where each segment starts / ends
        # main_parts: array of main parts in each segment

        if len(main_parts) < len(segment_points) - 1:
            # fill with 0s after the last provided main part
            main_parts += [0] * (len(segment_points) - 1 - len(main_parts))
        elif len(main_parts) > len(segment_points) - 1:
            raise ValueError("Too many main parts provided")
        start_end_pairs = list(zip(segment_points, segment_points[1:]))
        summary = pd.DataFrame(columns=['q_start', 'q_end']+self.instruments)
        for i, (start, end) in enumerate(start_end_pairs):
            seg = Compare(df, start, end)
            summary = pd.concat([summary, pd.DataFrame(seg.get_summary_row(main_part=main_parts[i]), index=[0])])
        return summary


if __name__ == '__main__':
    pd.options.display.max_columns = 100
    pd.options.display.max_rows = 50
    pd.options.display.max_colwidth = 100
    pd.options.display.width = 200
    filename = utils.REPO_PATH / "test" / "score.csv"
    df = pd.read_csv(filename)

    # # qstamps where each bar starts as segmentation points for example
    # segment_points = df.loc[df['beat'] == 1]['qstamp'].tolist()
    # print('segment points at: ')
    # print(segment_points)

    # qstamps where the main melody changes according to annotations.csv
    segment_points = utils.get_ground_truth()
    print('segment points at: ')
    print(segment_points)

    segment_count = len(segment_points) - 1
    # Clarinet (instrument index 0) as main part through all segments as an example
    melodies = [0 for _ in range(segment_count)]
    melodies = utils.get_melody_assignments()

    C = Compare(df, segment_points[0], segment_points[-1], fill_rests=True)
    summary = C.generate_score_summary(df, segment_points, melodies)
    summary.to_csv(str(filename).replace(".csv", "_relations.csv"), index=False)





    # rows where flute is 'r', but only the first row if consecutive

    # no_consecs = df.loc[df["Flute"] != df["Flute"].shift()]
    # rests = no_consecs.loc[no_consecs["Flute"] == 'r']['qstamp']
    # print(rests)








# seg = Compare(df, 0, 3, 'Flute', 'Oboe')
# print(seg.segment)
# print(f"Unison: Flute and Oboe 0 to 3: {seg.is_unison()}")
# print(f"Parallel Octave: Flute and Oboe 0 to 3: {seg.is_parallel_octave()}")
# print(f"Parallel 3rd: Flute and Oboe 0 to 3: {seg.is_parallel_interval(3)}")
# print("\n\n")
#
# seg = Compare(df, 0, 1, 'Flute', 'Timpani')
# print(seg.segment)
# print("Unison: Flute and Timpani 0 to 3: ", seg.is_unison())
# print("Octave: Flute and Timpani 0 to 3: ", seg.is_parallel_octave())
# print("Parallel 3rd: Flute and Timpani 0 to 3: ", seg.is_parallel_interval(3))
# print("\n\n")
#
# seg = Compare(df, 0, 3, 'Flute', 'Bb Clarinet')
# print(seg.segment)
# print("Unison: Flute and Bb Clarinet 0 to 3: ", seg.is_unison())
# print("Octave: Flute and Bb Clarinet 0 to 3: ", seg.is_parallel_octave())
# print("Parallel 2nd: Flute and Bb Clarinet 0 to 3: ", seg.is_parallel_interval(2))
# print("Parallel abs 2nd: Flute and Bb Clarinet 0 to 3: ", seg.is_parallel_abs_interval(2))
# print("\n\n")
#
#
# print("PARALLEL INTERVAL------------")
# seg = Compare(df, 1.5, 2.5, "Violas", "Violoncellos")
# print(seg.segment)
# print("Parallel 7ths: Violas and Vioncellos 1.5 to 2.5: ", seg.is_parallel_interval(7))
# print("Should this return true for parallel 7ths?")
# print("\n\n")
#
# seg = Compare(df, 0, 3, 'Flute', 'Bassoon')
# print(seg.segment)
# print("Parallel-1: Flute and Bassoon 0 to 1: ", seg.is_parallel_interval(1))
# print("Abs Parallel-1: Flute and Bassoon 0 to 1: ", seg.is_parallel_abs_interval(1))
# # CHECK: octave jumps
# print("^^^ confirm this case, where bassoon jumps octaves ^^^")



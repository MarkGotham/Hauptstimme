"""
NAME
===============================
Compare Part Relations (compare_part_relations.py)


BY
===============================
Mark Gotham


LICENCE:
===============================
Code = MIT. See [README](https://github.com/MarkGotham/Hauptstimme/tree/main#licence).


ABOUT:
===============================
Given part relation CSV files,
extract instances of parts playing together and produce aggregate statistics.


USAGE:
===============================
Run 'python3 compare_segmentations.py {score_mxl_file}'.


"""
from __future__ import annotations

from collections import Counter
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path

import instrument_classification


def process_csv_files(
        directory: str | Path = Path("../data/"),
        pattern="*_part_relations.csv"
) -> Counter:
    """
    Parse all CSV files containing part relations (`*_part_relations.csv`).

    Note:
    This assumes the csvs have the following columns:
    - first "qstamp_start" and "qstamp_end": this is used to calculate duration per segment.
    - followed by a list of all parts (this [2:] is currently hard-coded).
    """
    tally = Counter()
    dir_path = Path(directory)
    file_paths = list(dir_path.rglob(pattern))

    print(f"Processing {len(file_paths)} files...")

    reg = instrument_classification.InstrumentRegistry()

    for file_path in file_paths:
        try:
            df = pd.read_csv(file_path)
            df['q_length'] = df["qstamp_end"] - df["qstamp_start"]

            # Hard-coded part columns (i.e., excluding the timestamp columns)
            part_columns = list(df.columns[2:])

            for col in part_columns:

                canonical_name = reg.parse(str(col)).canonical
                col_data = df[col].astype(str)

                # Check "Main" or "U". E.g., "Main Part" or "U(Violin 2)"
                starts_with_main = col_data.str.startswith("Main", na=False)
                starts_with_u = col_data.str.startswith("U", na=False)

                mask = starts_with_main | starts_with_u

                # Add the q_length to the tally
                active_lengths = df.loc[mask, 'q_length']

                if len(active_lengths) > 0:
                    tally[canonical_name] += active_lengths.sum()

        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    return tally


def main(how_many: int = 12):
    c = process_csv_files()
    x_s, y_s = zip(*c.most_common(how_many))
    plt.bar(x_s, y_s)
    plt.xlabel(f'Instruments (top {how_many})')
    plt.ylabel('Time (q length) on main melody')
    plt.xticks(rotation=90)
    plt.tight_layout()
    plt.savefig("main_instruments.pdf")


if __name__ == "__main__":
    main()

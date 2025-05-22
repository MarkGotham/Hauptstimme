"""
NAME
===============================
Metadata (metadata.py)


BY
===============================
Matthew Blessing


LICENCE:
===============================
Code = MIT. See [README](https://github.com/MarkGotham/Hauptstimme/tree/main#licence).

ABOUT:
===============================
Functions for creating the audio and score metadata files for the
corpus.

`create_audio_metadata` scrapes the IMSLP wiki page of each set in the
corpus, then creates the 'audios.json' and 'audios.tsv' metadata files.

`create_score_metadata` initialises the 'scores.tsv' metadata file.

`match_audios_to_scores` updates the 'scores.tsv' and 'audios.tsv'
metadata files by matching audio recordings named, e.g., "1. ..." to
a particular score, enabling the 'name' field for the score to be 
updated based on the recording name and the 'score_id' field for the
audio to be updated.

`get_yaml_files` converts all .tsv files to .yaml.

`make_contents` produces the 'README.md' for the corpus. This is a 
tabular summary with raw file links to enable direct download.
"""
from __future__ import annotations

import pandas as pd
import json
import re
import markdown
from pathlib import Path
from src.utils import csv_to_yaml
from src.alignment.scraping import (
    get_imslp_audio_files, get_github_repo_files
)
from src.constants import REPO_AUTHOR, REPO_NAME, DATA_PATH, DATA_DIR


def create_audio_metadata(user_region: str):
    """
    Create a JSON audio metadata file 'audios.json' and initialise the 
    'audios.tsv' metadata file for the IMSLP recording files used for 
    alignment.

    Notes:
        Requires 'sets.tsv' and 'composers.tsv' to be complete.

    Args:
        user_region: The user region (e.g., EU, US).
    """
    sets = pd.read_csv(DATA_PATH / "sets.tsv", sep="\t")
    composers = pd.read_csv(DATA_PATH / "composers.tsv", sep="\t")

    metadata = []
    for _, composer_row in composers.iterrows():
        print(composer_row["name"], end=" - ")
        composer_metadata = {
            "composer": composer_row["name"],
            "compositions": []
        }
        # Get the composer's sets in the corpus
        composer_sets = (
            sets[sets["composer_id"] == composer_row["id"]]
            .reset_index(drop=True)
        )
        num_sets = len(composer_sets)
        for j, set_row in composer_sets.iterrows():
            print(set_row["name"], end=" ")
            # Get metadata for this set's recordings
            recordings_metadata = get_imslp_audio_files(
                set_row["imslp_link"],
                user_region
            )
            set_metadata = {
                "title": set_row["name"],
                "recordings": recordings_metadata
            }
            composer_metadata["compositions"].append(set_metadata)
            if j == num_sets - 1:
                print(f"({len(recordings_metadata)} recordings)")
            else:
                print(f"({len(recordings_metadata)} recordings)", end=", ")
        metadata.append(composer_metadata)

    # Write 'audios.json'
    with open(DATA_PATH / "audios.json", "w") as json_file:
        json.dump(metadata, json_file, indent=2)

    # Write this metadata to 'audios.tsv'
    audios = []
    i = 0
    for composer in metadata:
        for work in composer["compositions"]:
            for rec in work["recordings"]:
                for rec_file in rec["recording_files"]:
                    audios.append({
                        "id": i,
                        "performers": rec["performers"],
                        "publisher": rec["publisher"],
                        "year": rec["year"],
                        "imslp_number": rec_file["imslp_number"],
                        "imslp_link": rec_file["imslp_link"],
                        "score_id": None
                    })
                    i += 1
    audios_df = pd.DataFrame(
        audios,
        columns=[
            "id", "performers", "publisher", "year",
            "imslp_number", "imslp_link", "score_id"
        ]
    )
    # Int64 enforces the values being integers despite there being
    # missing values
    audios_df["year"] = audios_df["year"].astype("Int64")

    # Write 'audios.tsv'
    audios_df.to_csv(DATA_PATH / "audios.tsv", sep="\t", index=False)


def create_score_metadata():
    """
    Initialise the 'scores.tsv' metadata file for the corpus.
    """
    mscz_file_urls = get_github_repo_files(
        REPO_AUTHOR, REPO_NAME, ".mscz", DATA_PATH.name
    )

    sets = pd.read_csv(DATA_PATH / "sets.tsv", sep="\t")

    # Get all score paths
    scores = []
    i = 0
    for file in mscz_file_urls:
        filename_split = file.split("/")
        set_path = "/".join(filename_split[8:-2])
        set_id = sets[sets["path"] == set_path]["id"].item()
        scores.append({
            "id": i,
            "path": f"{set_path}/{filename_split[-1]}",
            "name": None,
            "set_id": set_id
        })
        i += 1

    scores_df = pd.DataFrame(
        scores, columns=["id", "path", "name", "set_id"])

    scores_df.to_csv(DATA_PATH / "scores.tsv", sep="\t", index=False)


def roman_to_int(roman: str) -> int:
    """
    Convert a roman numeral string into an integer.

    Args:
        roman: The roman numeral.

    Returns:
        total: The integer value.
    """
    roman_values = {
        "I": 1,
        "V": 5,
        "X": 10,
        "L": 50,
        "C": 100,
        "D": 500,
        "M": 1000
    }
    total = 0
    prev_value = 0
    for char in reversed(roman):
        value = roman_values[char]
        if value < prev_value:
            total -= value
        else:
            total += value
        prev_value = value
    return total


def match_audios_to_scores():
    """
    Update the 'audios.tsv' and 'scores.tsv' metadata files by
    matching the audio files in the metadata to their scores.

    Notes:
        This works for recordings named, e.g., '1. .. '.
        The audio file 'score_id' field is updated.
        For the scores that have audio files of this form, this updates
        their 'name' field in the metadata.
        The rest have to be done manually.
    """
    audios_metadata = json.load(open(DATA_PATH / "audios.json"))

    sets = pd.read_csv(DATA_PATH / "sets.tsv", sep="\t")
    scores = pd.read_csv(DATA_PATH / "scores.tsv", sep="\t")
    audios = pd.read_csv(DATA_PATH / "audios.tsv", sep="\t")

    for composer in audios_metadata:
        for work in composer["compositions"]:
            work_id = sets[sets["name"] == work["title"]]["id"].item()
            work_scores = scores[scores["set_id"] == work_id]
            for rec in work["recordings"]:
                # If the number of scores in the set is the same as the
                # number of recording files, then its likely that the
                # numbers align with the scores
                if len(rec["recording_files"]) == len(work_scores):
                    for rec_file in rec["recording_files"]:
                        number_match = re.match(
                            r"^(\d+|[IVXLCDM]+)\.\s+",
                            rec_file["name"],
                            flags=re.IGNORECASE
                        )
                        # If recording name starts with '{num}. '
                        if number_match:
                            number = number_match.group(1)
                            # If number is in roman numerals
                            if re.match(
                                r"^[IVXLCDM]+$",
                                number,
                                flags=re.IGNORECASE
                            ):
                                number = roman_to_int(number.upper())
                            else:
                                number = int(number)
                            # Find score corresponding to this number
                            work_score_nums = (
                                work_scores["path"].str.split("/").str[-1]
                            )
                            score_id = work_scores.loc[
                                work_score_nums == str(number),
                                "id"
                            ].item()
                            # Update this score's name in the metadata
                            score_bool = scores["id"] == score_id
                            scores.loc[score_bool, "name"] = re.sub(
                                r"^(\d+|[IVXLCDM]+)\.\s+", "",
                                rec_file["name"], 1)
                            # Add score ID to audio metadata
                            audios_bool = (
                                audios["imslp_number"] ==
                                rec_file["imslp_number"]
                            )
                            audios.loc[audios_bool, "score_id"] = score_id

    audios.to_csv(DATA_PATH / "audios.tsv", sep="\t", index=False)
    scores.to_csv(DATA_PATH / "scores.tsv", sep="\t", index=False)


def get_yaml_files():
    """
    Produce a .yaml file for each .tsv metadata file.
    """
    meta_files = ["sets", "scores", "audios", "composers"]

    for meta_file in meta_files:
        csv_to_yaml(DATA_PATH / f"{meta_file}.tsv", "\t")


def make_contents():
    """
    Produce a tabular summary of files committed to the corpus with raw
    file links to enable direct download. This is the 'README.md'.
    """
    with open(DATA_PATH / "README.md", "w") as md_f:
        md_f.write("## Corpus contents with direct download links\n")
        md_f.write("|composer|collection|movement|score|-|melody|\n")
        md_f.write("|---|---|---|---|---|---|\n")

        contents = []

        mscz_files = get_github_repo_files(
            REPO_AUTHOR, REPO_NAME, ".mscz", DATA_PATH.name)

        num_scores = len(mscz_files)

        for i in range(num_scores):
            mscz_file = Path(mscz_files[i])
            composer, collection, movement = [
                info.replace("_", " ") for info in
                mscz_file.parts[-4:-1]
            ]
            # If collection has no movements
            if composer == DATA_DIR:
                composer = collection
                collection = movement
                movement = ""

            mxl_file = mscz_file.with_suffix(".mxl")
            melody_file = mscz_file.parent / f"{mscz_file.stem}_melody.mxl"

            line = [
                composer, collection, movement,
                f"[.mscz]({mscz_file.as_posix()})",
                f"[.mxl]({mxl_file.as_posix()})",
                f"[melody.mxl]({melody_file.as_posix()})\n"
            ]

            contents.append("|".join(line))

        for line in contents:
            md_f.write(line)

    with open(DATA_PATH / "README.html", "w") as html_f:
        with open(DATA_PATH / "README.md", "r") as md_f:
            contents = md_f.read()
        contents = markdown.markdown(
            contents, extensions=["markdown.extensions.tables"]
        )
        contents = "<body>\n" + contents.replace(
            "<table>\n", '<table id="README" class="display">'
        )
        contents += '<link rel="stylesheet" href="https://cdn.datatables.net/2.1.7/css/dataTables.dataTables.css"/>\n'
        contents += '<script src="https://ajax.googleapis.com/ajax/libs/jquery/2.1.3/jquery.min.js"></script>\n'
        contents += '<script src="https://cdn.datatables.net/2.1.7/js/dataTables.js"></script>\n'
        contents += '<script src="search.js"></script>\n'
        contents += '</body>\n'
        html_f.write(contents)

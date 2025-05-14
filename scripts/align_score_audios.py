"""
NAME
===============================
Align Score Audios (align_score_audios.py)


BY
===============================
Matthew Blessing


LICENCE:
===============================
Code = MIT. See [README](https://github.com/MarkGotham/Hauptstimme/tree/main#licence).

ABOUT:
===============================
This script aligns a set of audio files to a score.

It requires a score's MuseScore or MusicXML file and a set of audio 
files (.mp3, .wav, or .flac).

There are two ways to provide arguments when running this script from
the command line:
1.  Providing audio file paths with -a:
    'python3 align_score_audios.py {score file} -a {audio file 1} ...'
2.  Providing audio file data with -f:
    'python3 align_score_audios.py {score file} -f {audio data file}',
    where the audio data file contains, e.g.:
    '''
    UK ldn_symph_orc.mp3   00:00:07    00:05:50
    US ptsbrg_symph_orc.mp3
    GER brln_symph_orc.mp3  00:12:23
    '''
    Notes:
        Each line contains audio info separated by tabs.
        Audio files have:
        - A unique ID for the alignment table.
        - A file path or URL.
        - (Optional) A start timestamp.
        - (Optional) An end timestamp.
        Audio files can either have no specified time range (e.g., US
        in the above example), only a start timestamp (e.g., GER), or
        both start and end timestamps (e.g., UK).
"""
from __future__ import annotations

import sys
import os
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

import argparse
import time
import datetime
from pathlib import Path
from src.alignment.score_audio_alignment import *
from src.utils import get_compressed_measure_map, ms3_convert
from src.types import AudioData
from typing import Tuple, List


def validate_args(
    args: argparse.Namespace
) -> Tuple[Path, Path, Path, List[AudioData]]:
    """
    Validate the arguments parsed from the command line.

    Args:
        args: An object holding the arguments parsed from the command 
            line.

    Returns:
        score_mscz: The score's MuseScore file path.
        score_mxl: The score's MusicXML file path.
        score_mm: The score's measure map file path.
        audios: A 2D list containing a list for each audio
            file that contains:
                audio_id: An identifier for the audio file.
                audio_path: The path to or URL for the audio file.
                A time range to extract from the audio file for
                    alignment, specified by:
                    start: A start timestamp.
                    end: An end timestamp.
                desc: A description of which portion of the audio is to
                    be used.

    Raises:
        ValueError. If the score file provided is not a .mscz or .mxl 
            file.
        ValueError: If both the -a and -f arguments are missing.
        ValueError: If the start timestamp for an audio file is not
            given in hh:mm:ss format.
        ValueError: If no audio files were provided.
    """
    score_file = args.score
    score_file = validate_path(score_file)
    score_file_dir = score_file.parent

    if score_file.suffix == ".mscz":
        score_mscz = score_file
        # Get MusicXML file
        score_mxl = score_file.with_suffix(".mxl")
        if not score_mxl.exists():
            print("Warning: The provided score has no MusicXML file.")
            print("Creating MusicXML file...")
            ms3_convert(
                score_file_dir, "mscz", "mxl", score_file.stem
            )
    elif score_file.suffix == ".mxl":
        score_mxl = score_file
        # Get MuseScore file
        score_mscz = score_file.with_suffix(".mscz")
        if not score_mscz.exists():
            print("Warning: The provided score has no MuseScore file.")
            print("Creating MuseScore file...")
            ms3_convert(
                score_file_dir, "mxl", "mscz", score_file.stem
            )
    else:
        raise ValueError("Error: The score file provided requires a " +
                         ".mscz or .mxl extension.")

    # Get measure map
    score_mm = score_file.with_suffix(".mm.json")
    if not score_mm.exists():
        print("Warning: The provided score has no measure map.")
        print("Creating measure map...")
        get_compressed_measure_map(score_mscz)

    audios = []

    if args.audios:
        audios_data = args.audios
    elif args.audios_file:
        audios_file = open(args.audios_file, "r")
        audios_data = audios_file.readlines()
    else:
        raise ValueError("Error: Both the -a and -f arguments are missing.")

    for audio_data in audios_data:
        audio_data = audio_data.strip()

        # Audio data from -f will contain info separated by tabs
        audio_data = audio_data.split("\t")
        num_args = len(audio_data)

        ignore = False
        audio_id = None
        start = None
        end = None
        if num_args == 1:
            audio_path = audio_data[0]
            desc = "full audio"
        elif num_args == 2:
            audio_id, audio_path = audio_data
            desc = "full audio"
        elif num_args >= 3:
            audio_id, audio_path, start = audio_data[:3]
            desc = f"{start} onwards"
            if num_args == 4:
                end = audio_data[3]
                desc = f"{start}-{end}"
        else:
            ignore = True

        if ignore:
            print(f"Warning: Excluding '{audio_path}' due to invalid data" +
                  f"in '{args.audios_file}'. Please run with argument -h " +
                  "for more information.")
        else:
            if audio_path.endswith((".mp3", ".wav", ".flac")):
                if audio_id is None:
                    # Audio has no identifier, but this is needed
                    audio_id = input("Enter a string to represent the " +
                                     f"audio file '{audio_path}' in the " +
                                     "alignment table (e.g., 'Ldn_Symph_Orc'" +
                                     " or 'Karajan1950').\n")
                if start is not None:
                    try:
                        start = datetime.datetime.strptime(
                            start, "%H:%M:%S"
                        ).time()
                    except ValueError:
                        raise ValueError(
                            f"Error: {start} is not in hh:mm:ss format."
                        )
                if end is not None:
                    try:
                        end = datetime.datetime.strptime(
                            end, "%H:%M:%S"
                        ).time()
                    except ValueError:
                        raise ValueError(
                            f"Error: {end} is not in hh:mm:ss format."
                        )

                audios.append([audio_id, audio_path, start, end, desc])
            else:
                print(f"Warning: Excluding '{audio_path}' as it is not a " +
                      ".mp3, .wav or .flac file.")

    if len(audios) == 0:
        raise ValueError("Error: No valid audio files were provided.")

    audios_string = ", ".join(
        [f"{audio[0]} - '{audio[1]}' ({audio[4]})" for audio in audios]
    )
    print(f"MuseScore file: '{score_mscz}', \n" +
          f"MusicXML file: '{score_mxl}', \n" +
          f"Measure map file: '{score_mm}', \n" +
          f"Audio files: {audios_string}.")

    time.sleep(1)

    return score_mscz, score_mxl, score_mm, audios


def get_args() -> Tuple[Path, Path, Path, List[AudioData]]:
    """
    Obtain the validated set of arguments parsed from the command line.

    Returns:
        score_mscz: The score's MuseScore file path.
        score_mxl: The score's MusicXML file path.
        score_mm: The score's measure map file path.
        audios: A 2D list containing a list for each audio file that
            contains:
                audio_id: An identifier for the audio file.
                audio_path: The path to or URL for the audio file.
                A time range to extract from the audio file for
                    alignment, specified by:
                    start: A start timestamp.
                    end: An end timestamp.
                desc: A description of which portion of the audio is to
                    be used.
    """
    parser = argparse.ArgumentParser(
        description=("Align one or more audio files to a score, producing " +
                     "an alignment table.\nMust provide the score's " +
                     "MuseScore file (.mszc) or MusicXML (.mxl) file, as " +
                     "well as either the -a or -f argument."),
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "score",
        help=("The path to the score's MuseScore file (.mscz) or MusicXML" +
              "file (.mxl).")
    )
    parser.add_argument(
        "-a",
        "--audios",
        nargs="+",
        help=("The paths (or URLs) to the audio files to align to the score" +
              ". Either .mp3, .wav or .flac.")
    )
    parser.add_argument(
        "-f",
        "--audios_file",
        help=("The path to a .txt file containing the following information" +
              " for each audio file on a separate line:\n" +
              "- A unique string to identify the audio file in the " +
              "alignment table (e.g., 'Ldn_Symph_Orc' or 'Karajan1950').\n" +
              "- The audio file path or URL.\n" +
              "- (Optional) Start and end timestamps (hh:mm:ss) " +
              "indicating alignment a subset of the audio to the score. " +
              "Either only the start timestamp should be provided, or both " +
              "the start and end.")
    )

    args = parser.parse_args()
    score_mscz, score_mxl, score_mm, audios = validate_args(args)

    return score_mscz, score_mxl, score_mm, audios


if __name__ == "__main__":
    print("\nWelcome to score-audio alignment!")

    score_mscz, score_mxl, score_mm, audios = get_args()

    align_score_audios(score_mxl, score_mm, audios)

"""
NAME
===============================
Align Score Audios (align_score_audios.py)


BY
===============================
Matt Blessing, 2024


LICENCE:
===============================
Creative Commons Attribution-ShareAlike 4.0 International License
https://creativecommons.org/licenses/by-sa/4.0/


ABOUT:
===============================
This script aligns a set of audio files to a score.

It requires a score's .mscz and .mxl file, as well as (optionally) the
score's (compressed) measure map and a set of audio files (.mp3 or 
.wav).

There are a few ways to provide arguments when running this script from
the command line:
1.  Providing the score files and audio files:
    'python3 align_score_audios.py -s score.mscz score.mxl 
    -a audio1.mp3 audio2.mp3 {...}'
2.  Providing the score files, measure map, and audio files:
    'python3 align_score_audios.py -s score.mscz score.mxl 
    -m score.mm.json -a audio1.mp3 audio2.mp3 {...}'
3.  Providing a file paths file containing the score files,
    (optionally) the measure map, and info about the audio files. 
    Specifically, the info includes, e.g. 'filenames.txt':
    '''
    score.mscz
    score.mxl
    score.mm.json
    UK ldn_symph_orc.mp3   00:00:07    00:05:50
    US ptsbrg_symph_orc.mp3
    GER brln_symph_orc.mp3  00:12:23
    '''
    Notes:
        The audio file info is separated by tabs.
        Audio files can either have no specified time range (e.g., US), 
        start and end timestamps (e.g., UK), or only a start timestamp
        (e.g., GER).
    Then running:
    'python3 score_audio_alignment.py -f filenames.txt'
"""
import argparse
import time
from datetime import datetime
from hauptstimme.alignment.score_audio_alignment import *
from hauptstimme.utils import get_compressed_measure_map


def get_arg_mode(args):
    """
    Determine the 'argument mode' based on which arguments were passed.

    Args:
        args (argparse.Namespace): An object holding the values parsed
            from the command line arguments.

    Returns:
        mode (str): Either 'regular' if the -s and -a arguments were 
            passed and no -f argument was passed, or 'file_path_file' 
            if the -f argument was passed and no -s and -a arguments 
            were passed.

    Raises:
        ValueError: If neither: the -s and -a arguments are provided
            with no -f argument or the -f argument is provided with no
            -s and -a arguments.
    """
    if args.score_files and args.audios and args.file_paths is None:
        mode = "regular"
    elif args.score_files is None and args.audios is None and args.file_paths:
        mode = "file_path_file"
    else:
        raise ValueError(
            "Error: An invalid set of arguments were provided. Either " +
            "provide the score files and audio files, or provide all file " +
            "paths in a .txt file.")

    return mode


def validate_args(args, mode):
    """
    Validate the argument values parsed from the command line.

    Args:
        args (argparse.Namespace): An object holding the values parsed
            from the command line arguments.
        mode (str): The 'argument mode' indicating which arguments were
            given.

    Returns:
        score_mscz (str): The score's MuseScore file path.
        score_mxl (str): The score's MusicXML file path.
        score_mm (str): The score's measure map file path.
        audios (list): A 2D list containing a list for each audio
            file that contains:
                audio_id (str): An identifier for the audio file.
                audio_filename (str): Its local filename or URL.
                A time range to extract from the audio file for 
                    alignment, specified by:
                    start (datetime.time): A start timestamp.
                    end (datetime.time): An end timestamp.
                desc (str): A description of which portion of the audio
                        is to be used.

    Raises:
        ValueError: If the start timestamp for an audio file is not 
            given in hh:mm:ss format.
        ValueError: If no MuseScore file was provided.
        ValueError: If no MusicXML file was provided.
        ValueError: If no audio files were provided.
    """
    score_mscz = None
    score_mxl = None
    score_mm = None
    audios = []

    if mode == "regular":
        print("\nValidating the provided file paths...")
        file_paths = args.score_files + args.audios
        if args.measure_map:
            file_paths += [args.measure_map]
    elif mode == "file_path_file":
        print("\nValidating the provided file of file paths...")
        file = open(args.file_paths, "r")
        file_paths = file.readlines()

    for file_path in file_paths:
        file_path = file_path.strip()
        file_path_line_split = file_path.split("\t")
        num_args = len(file_path_line_split)
        # If file_path contains strings separated by tabs, then it is
        # likely information for an audio file
        if num_args > 1:
            audio_id = file_path_line_split[0]
            file_path = file_path_line_split[1]
            if not Path(file_path).exists():
                print(f"Warning: Excluding '{file_path}' as it doesn't exist.")
                continue
            start = None
            end = None
            if file_path.endswith(".mp3") or file_path.endswith(".wav"):
                if num_args >= 3:
                    # The third value is always going to be the start
                    # timestamp
                    start = file_path_line_split[2]
                    try:
                        start = datetime.strptime(start, "%H:%M:%S").time()
                    except ValueError:
                        raise ValueError(
                            f"Error: {start} is not in hh:mm:ss format."
                        )
                    if num_args == 4:
                        # If there is a fourth value, it is the end
                        # timestamp
                        end = file_path_line_split[3]
                        try:
                            end = datetime.strptime(end, "%H:%M:%S").time()
                        except ValueError:
                            raise ValueError(
                                f"Error: {end} is not in hh:mm:ss format."
                            )
                    if end:
                        desc = f"{start}-{end}"
                    else:
                        desc = f"{start} onwards"
                else:
                    desc = "full audio"
                audios.append([audio_id, file_path, start, end, desc])
        else:
            if not Path(file_path).exists():
                print(f"Warning: Excluding '{file_path}' as it doesn't exist.")
                continue
            if file_path.endswith(".mscz"):
                score_mscz = file_path
            elif file_path.endswith(".mxl"):
                score_mxl = file_path
            elif file_path.endswith(".json") or file_path.endswith(".csv"):
                score_mm = file_path
            elif file_path.endswith(".mp3") or file_path.endswith(".wav"):
                # Audio has no identifier, but this is needed
                audio_id = input("Enter a string to represent the audio " +
                                 f"file '{file_path}' in the alignment " +
                                 "table (e.g., 'Ldn_Symph_Orc' or " +
                                 "'Karajan1950').\n")
                audios.append([audio_id, file_path, None, None, "full audio"])
            else:
                print(f"Warning: Excluding '{file_path}' as it is not a " +
                      ".mscz, .mxl, .mp3 or .wav file.")

    if score_mscz is None:
        raise ValueError("Error: No MuseScore file provided.")
    elif score_mxl is None:
        raise ValueError("Error: No MusicXML file provided.")
    elif len(audios) == 0:
        raise ValueError("Error: No valid audio files were provided.")

    audios_string = ", ".join(
        [f"{audio[0]} - '{audio[1]}' ({audio[3]})" for audio in audios]
    )
    if score_mm:
        print(
            f"Validation complete.\nMuseScore file: '{score_mscz}', \n" +
            f"MusicXML file: '{score_mxl}', \n" +
            f"Measure map file: '{score_mm}', \n" +
            f"Audio files: {audios_string}.")
    else:
        print(
            f"Validation complete.\nMuseScore file: '{score_mscz}', \n" +
            f"MusicXML file: '{score_mxl}', \n" +
            f"Audio files: {audios_string}.")
        # Get the score's measure map
        score_mm = get_compressed_measure_map(score_mscz)

    time.sleep(1)

    return score_mscz, score_mxl, score_mm, audios


def get_args():
    """
    Obtain the validated set of arguments passed in the command line.

    Returns:
        score_mscz (str): The score's MuseScore file path.
        score_mxl (str): The score's MusicXML file path.
        score_mm (str): The score's measure map file path.
        audios (list): A 2D list containing a list for each audio
            file that contains:
                audio_id (str): An identifier for the audio file.
                audio_filename (str): Its local filename or URL.
                A time range to extract from the audio file for 
                    alignment, specified by:
                    start (datetime.time): A start timestamp.
                    end (datetime.time): An end timestamp.
                desc (str): A description of which portion of the audio
                        is to be used.
    """
    parser = argparse.ArgumentParser(
        description=("Align one or more audio files to a score.\n" +
                     "Either provide the -s, -m (optional), -a arguments, " +
                     "or just provide the -f argument."),
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "-s",
        "--score-files",
        nargs=2,
        help=("The relative path to both the MuseScore file and MusicXML " +
              "file for the score that the audio files will be aligned to.")
    )
    parser.add_argument(
        "-m",
        "--measure-map",
        help=("The measure map for the score that the audio files will be " +
              "aligned to. If not provided it will be created and saved.")
    )
    parser.add_argument(
        "-a",
        "--audios",
        nargs="+",
        help=("The relative paths (or URLs) to the audio files to align to " +
              "the score. Must be .mp3 or .wav files.")
    )
    parser.add_argument(
        "-f",
        "--file_paths",
        help=("The relative path to a .txt file containing (each on a " +
              "separate line):\n" +
              "- the score's MuseScore file path\n" +
              "- the score's MusicXML file path\n" +
              "- (optional) the score's measure map file path\n" +
              "- for each audio file (with each audio file on a separate " +
              "line and the data for each audio file on one line separated " +
              "by tabs):\n" +
              "  * a unique string to identify the audio file in the " +
              "alignment table (e.g., 'Ldn_Symph_Orc' or 'Karajan1950')\n" +
              "  * the audio file path\n" +
              "  * (optional) start and end timestamps (hh:mm:ss) " +
              "indicating to align a subset of the audio to the score\n" +
              "    (either only start, or both start and end)\n")
    )

    args = parser.parse_args()
    mode = get_arg_mode(args)
    score_mscz, score_mxl, score_mm, audios = validate_args(args, mode)

    return score_mscz, score_mxl, score_mm, audios


if __name__ == "__main__":
    print("\nWelcome to score-audio alignment!")

    score_mscz, score_mxl, score_mm, audios = get_args()

    align_score_audios(score_mxl, score_mm, audios)

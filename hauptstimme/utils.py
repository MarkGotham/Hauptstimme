import time
import os
import subprocess
import pandas as pd
import yaml
from pymeasuremap import base
from pathlib import Path
from hauptstimme.constants import CORPUS_PATH


def get_corpus_files(corpus_sub_dir: str = CORPUS_PATH,
                     filename: str = "*.mxl") -> list[str]:
    """
    Get paths to files in the corpus that match the filename pattern.

    Args:
        corpus_sub_dir (str): The path to a subdirectory within the 
            corpus to get files from. Default = CORPUS_PATH.
        filename_regex (str): A pattern that the names of the files 
            must match to be included.

    Returns: 
        A list of file paths.

    Raises:
        AssertionError: If the subdirectory is not relative to the 
            corpus directory.
        AssertionError: If the subdirectory doesn't exist.
    """
    corpus_sub_dir_path = Path(corpus_sub_dir)

    assert corpus_sub_dir_path.is_relative_to(CORPUS_PATH)
    assert corpus_sub_dir_path.exists()

    return [file.as_posix() for file in corpus_sub_dir_path.rglob(filename)]


def ms3_convert(input_dir, input_ext, output_ext, regex=".*"):
    """
    Convert all files in a directory (that match a particular regex
    pattern) with a particular extension into a different type.

    Args:
        input_dir (str): The relative path to the directory containing 
            the files.
        input_ext (str): The extension of the file type to convert 
            from (e.g., 'mxl').
        output_ext (str): The extension of the file type to convert to.
        regex (str): A regular expression to filter the names (not
            including extension) of the files being converted.

    Raises:
        ValueError: If the input directory does not exist.
    """
    # Check if the input directory exists
    if not os.path.exists(input_dir):
        raise ValueError("Error. Input directory does not exist.")

    command = (f"ms3 convert -d '{input_dir}' -o '{input_dir}' " +
               rf"-i {regex}\.{input_ext} --format {output_ext} " +
               f"--extensions {input_ext} -l c")

    # Deal with 'ms3 convert' not recognising MuseScore 4 installations
    try:
        subprocess.run(command,
                       shell=True,
                       check=True,
                       stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        try:
            program_files = os.environ["PROGRAMFILES"]
            ms4_path = os.path.join(
                program_files, r"MuseScore 4\bin\MuseScore4.exe")
            subprocess.run(
                command + f" -m '{ms4_path}'",
                shell=True,
                check=True)
        except KeyError:
            ms4_path = "/Applications/MuseScore 4.app/Contents/MacOS/mscore"
            subprocess.run(
                command + f" -m '{ms4_path}'",
                shell=True,
                check=True)


def get_measure_map(score_mscz, verbose=True):
    """
    Get a score's measure map.

    Notes:
        Downloads the measure map into the same directory as the score.

    Args:
        score_mscz (str): The relative path to the score's MuseScore 
            file.
        verbose (bool): Whether to include print statements. Default = 
            True.

    Returns:
        score_mm (str): The relative path to the score's measure map 
            file.
    """
    if verbose:
        print("\nNow creating a measure map for the score...")
        time.sleep(1)
    # Create a measure map for the score
    score_mscz_path = Path(score_mscz)
    os.makedirs(".score_audio_alignment_temp", exist_ok=True)
    os.system(f"ms3 extract -d '{score_mscz_path.parent.as_posix()}' -a -i " +
              f"'{score_mscz_path.name}' -M " +
              f"'{os.getcwd()}/.score_audio_alignment_temp' -l c")
    os.rename(
        f".score_audio_alignment_temp/{score_mscz_path.stem}.measures.tsv",
        f".score_audio_alignment_temp/{score_mscz_path.stem}.tsv"
    )
    os.system(f"MM convert -d .score_audio_alignment_temp -o " +
              f"'{score_mscz_path.parent.as_posix()}' -l c")
    os.system("rm -rf .score_audio_alignment_temp")

    score_mm = score_mscz_path.with_suffix(".mm.json").as_posix()
    if verbose:
        print(f"Measure map '{score_mm}' created successfully.")

    return score_mm


def get_measure_map_given_measures(score_mscz, score_measures, verbose=True):
    """
    Get a score's measure map given that it already has a .measures.tsv
    file.

    Notes:
        Downloads the measure map into the same directory as the score.

    Args:
        score_mscz (str): The relative path to the score's MuseScore 
            file.
        score_measures (str): The relative path to the score's 
            .measures.tsv file.
        verbose (bool): Whether to include print statements. Default = 
            True.

    Returns:
        score_mm (str): The relative path to the score's measure map 
            file.
    """
    if verbose:
        print("\nNow creating a measure map for the score...")
        time.sleep(1)
    # Create a measure map for the score
    score_mscz_path = Path(score_mscz)
    score_measures_path = Path(score_measures)
    os.system(f"MM convert -d '{score_measures_path.parent.as_posix()}' -o " +
              f"'{score_mscz_path.parent.as_posix()}' -r " +
              f"'{score_measures_path.name}' -l c")

    score_mm = score_mscz_path.with_suffix(".mm.json").as_posix()
    if verbose:
        print(f"Measure map '{score_mm}' created successfully.")

    return score_mm


def compress_measure_map(score_mm):
    """
    Compress a measure map.

    Args:
        score_mm (str): The relative path to a score's measure map.
    """
    mm = base.MeasureMap.from_json_file(score_mm)
    compressed_mm = mm.compress()
    compressed_mm.to_json_file(score_mm)


def get_compressed_measure_map(score_mscz, verbose=True):
    """
    Get a score's compressed measure map.

    Notes:
        Downloads the compressed measure map into the same directory as
        the score.

    Args:
        score_mscz (str): The relative path to the score's MuseScore 
            file.
        verbose (bool): Whether to include print statements. Default = 
            True.

    Returns:
        score_mm (str): The relative path to the score's compressed
            measure map file.
    """
    score_mm = get_measure_map(score_mscz, verbose)
    compress_measure_map(score_mm)

    return score_mm


def get_compressed_measure_map_given_measures(
    score_mscz,
    score_measures,
    verbose=True
):
    """
    Get the compressed measure map for a score that already has a 
    .measures.tsv file.

    Notes:
        Downloads the compressed measure map into the same directory as
        the score.

    Args:
        score_mscz (str): The relative path to the score's MuseScore 
            file.
        score_measures (str): The relative path to the score's 
            .measures.tsv file.
        verbose (bool): Whether to include print statements. Default = 
            True.

    Returns:
        score_mm (str): The relative path to the score's compressed
            measure map file.
    """
    score_mm = get_measure_map_given_measures(score_mscz, score_measures,
                                              verbose)
    compress_measure_map(score_mm)

    return score_mm


def csv_to_yaml(csv_file, sep):
    """
    Convert a .csv file to a .yaml file. Used for creating the corpus
    metadata.

    Args:
        csv_file (str): The .csv file name.
        sep (str): The .csv file separator.
    """
    csv = pd.read_csv(csv_file, sep=sep)

    csv_file_path = Path(csv_file)
    with open(csv_file_path.with_suffix(".yaml"), "w+") as out:
        yaml.dump(csv.to_dict(orient="records"), out, sort_keys=False)

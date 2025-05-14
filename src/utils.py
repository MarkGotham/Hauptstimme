from __future__ import annotations

import time
import os
import subprocess
import pandas as pd
import yaml
from music21.stream import Part, Measure
from pymeasuremap import base
from pathlib import Path
from src.constants import DATA_PATH
from typing import Union, List, Optional


def get_corpus_files(
    corpus_sub_dir: Union[str, Path] = DATA_PATH,
    file_path: str = "*.mxl",
    pathlib: bool = False
) -> Union[List[str], List[Path]]:
    """
    Get paths to files in the corpus that match the filename pattern.

    Args:
        corpus_sub_dir: The path to a subdirectory within the 
            corpus to get files from. Default = DATA_PATH.
        file_path: A pattern that the names of the files 
            must match to be included.
        pathlib: Whether the output list should contain pathlib paths
            (True) or strings (False). Default = False.

    Returns: 
        files: A list of filepaths.

    Raises:
        AssertionError: If the subdirectory is not relative to the 
            corpus directory.
        AssertionError: If the subdirectory doesn't exist.
    """
    corpus_sub_dir = validate_path(corpus_sub_dir, dir=True)

    assert corpus_sub_dir.is_relative_to(DATA_PATH)
    assert corpus_sub_dir.exists()

    files = []
    for file in corpus_sub_dir.rglob(file_path):
        if pathlib:
            files.append(file)
        else:
            files.append(file.as_posix())

    return files


def ms3_convert(
    input_dir: Union[str, Path],
    input_ext: str,
    output_ext: str,
    regex: str = ".*",
    out_dir: Optional[Union[str, Path]] = None
):
    """
    Convert all files in a directory (that match a particular regex
    pattern) with a particular extension into a different type.

    Args:
        input_dir: The path to the directory containing the files.
        input_ext: The extension of the file type to convert from 
            (e.g., 'mxl').
        output_ext: The extension of the file type to convert to.
        regex: A regular expression to filter the names (notincluding 
            extension) of the files being converted.
        out_dir: The path to the directory in which the converted files
            will be saved. Default = None.
    """
    # Check if the input directory exists
    input_dir = validate_path(input_dir, dir=True)

    if out_dir is None:
        out_dir = input_dir
    else:
        out_dir = validate_path(out_dir, dir=True)

    command = (f'ms3 convert -d "{input_dir}" -o "{out_dir}" ' +
               rf'-i "{regex}\.{input_ext}" --format {output_ext} ' +
               f"--extensions {input_ext} -l c")

    # Deal with 'ms3 convert' not recognising MuseScore 4 installations
    try:
        subprocess.run(
            command,
            shell=True,
            check=True,
            stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        try:
            program_files = os.environ["PROGRAMFILES"]
            ms4_path = os.path.join(
                program_files, r"MuseScore 4\bin\MuseScore4.exe"
            )
            subprocess.run(
                command + f' -m "{ms4_path}"',
                shell=True,
                check=True
            )
        except KeyError:
            ms4_path = "/Applications/MuseScore 4.app/Contents/MacOS/mscore"
            subprocess.run(
                command + f' -m "{ms4_path}"',
                shell=True,
                check=True
            )


def get_measure_map(
    score_mscz: Union[str, Path],
    verbose: bool = True
) -> Path:
    """
    Get a score's measure map.

    Notes:
        Downloads the measure map into the same directory as the score.

    Args:
        score_mscz: The path to the score's MuseScore file.
        verbose: Whether to include print statements. Default = True.

    Returns:
        score_mm: The path to the score's measure map file.
    """
    if verbose:
        print("\nNow creating a measure map for the score...")
        time.sleep(1)
    # Create a measure map for the score
    score_mscz = validate_path(score_mscz)
    os.makedirs(".score_audio_alignment_temp", exist_ok=True)
    os.system(
        f'ms3 extract -d "{score_mscz.parent}" -a -i "{score_mscz.name}" ' +
        f'-M "{os.getcwd()}/.score_audio_alignment_temp" -l c'
    )
    os.rename(
        f".score_audio_alignment_temp/{score_mscz.stem}.measures.tsv",
        f".score_audio_alignment_temp/{score_mscz.stem}.tsv"
    )
    os.system(
        f"MM convert -d .score_audio_alignment_temp -o " +
        f'"{score_mscz.parent}" -l c'
    )
    os.system("rm -rf .score_audio_alignment_temp")

    score_mm = score_mscz.with_suffix(".mm.json")
    if verbose:
        print(
            f"Measure map '{score_mm}' created successfully."
        )

    return score_mm


def get_measure_map_given_measures(
    score_mscz: Union[str, Path],
    score_measures: Union[str, Path],
    verbose: bool = True
) -> Path:
    """
    Get a score's measure map given that it already has a .measures.tsv
    file.

    Notes:
        Downloads the measure map into the same directory as the score.

    Args:
        score_mscz: The path to the score's MuseScore file.
        score_measures: The path to the score's .measures.tsv 
            file.
        verbose: Whether to include print statements. Default = True.

    Returns:
        score_mm: The path to the score's measure map file.
    """
    if verbose:
        print("\nNow creating a measure map for the score...")
        time.sleep(1)
    # Create a measure map for the score
    score_mscz = validate_path(score_mscz)
    score_measures = validate_path(score_measures)
    os.system(
        f'MM convert -d "{score_measures.parent}" -o "{score_mscz.parent}" ' +
        f'-r "{score_measures.name}" -l c'
    )

    score_mm = score_mscz.with_suffix(".mm.json")
    if verbose:
        print(f"Measure map '{score_mm}' created successfully.")

    return score_mm


def compress_measure_map(score_mm: Union[str, Path]):
    """
    Compress a measure map.

    Args:
        score_mm: The path to a score's measure map.
    """
    mm = base.MeasureMap.from_json_file(score_mm)
    compressed_mm = mm.compress()
    compressed_mm.to_json_file(score_mm)


def get_compressed_measure_map(
    score_mscz: Union[str, Path],
    verbose: bool = True
) -> Path:
    """
    Get a score's compressed measure map.

    Notes:
        Downloads the compressed measure map into the same directory as
        the score.

    Args:
        score_mscz: The path to the score's MuseScore file.
        verbose: Whether to include print statements. Default = True.

    Returns:
        score_mm: The path to the score's compressed measure map file.
    """
    score_mm = get_measure_map(score_mscz, verbose)
    compress_measure_map(score_mm)

    return score_mm


def get_compressed_measure_map_given_measures(
    score_mscz: Union[str, Path],
    score_measures: Union[str, Path],
    verbose: bool = True
) -> Path:
    """
    Get the compressed measure map for a score that already has a 
    .measures.tsv file.

    Notes:
        Downloads the compressed measure map into the same directory as
        the score.

    Args:
        score_mscz: The path to the score's MuseScore file.
        score_measures: The path to the score's .measures.tsv 
            file.
        verbose: Whether to include print statements. Default = True.

    Returns:
        score_mm: The path to the score's compressed measure map file.
    """
    score_mm = get_measure_map_given_measures(
        score_mscz, score_measures, verbose
    )
    compress_measure_map(score_mm)

    return score_mm


def csv_to_yaml(
    csv_file: Union[str, Path],
    sep: Optional[str] = None
):
    """
    Convert a .csv file to a .yaml file. Used for creating the corpus
    metadata.

    Args:
        csv_file: The .csv file name.
        sep: The .csv file separator.
    """
    csv_file = validate_path(csv_file)
    csv = pd.read_csv(csv_file, sep=sep)

    with open(csv_file.with_suffix(".yaml"), "w+") as out:
        yaml.dump(csv.to_dict(orient="records"), out, sort_keys=False)


def validate_path(path: Union[str, Path], dir=False) -> Path:
    """
    Determine whether a provided path is an existing file/directory.

    Args:
        path: A path.
        dir: Whether the path should be for a directory. Default = 
            False.

    Returns:
        path: The path as a `Path`.

    Raises:
        ValueError: If the file/directory does not exist.
    """
    if isinstance(path, str):
        path = Path(path)

    if dir:
        if not path.is_dir():
            raise ValueError(f"Error: '{path}' isn't an existing directory.")
    else:
        if not path.is_file():
            raise ValueError(f"Error: '{path}' isn't an existing file.")

    return path


def check_measure_exists(
    part: Part,
    measure_num: int,
) -> Measure:
    """
    Check whether a measure exists in a part.

    Args:
        part: A score part.
        measure_num: A measure number.

    Returns:
        measure: Either the measure or None.

    Raises:
        ValueError: If the measure does not exist.
    """
    measure = part.measure(measure_num)
    if measure is None:
        raise ValueError(
            f"Error: There is no measure {measure_num} in part " +
            f"'{part.partName}'."
        )
    return measure

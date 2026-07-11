from __future__ import annotations

import os
import subprocess
import tempfile
import pandas as pd
import yaml
from music21.stream.base import Part, Measure
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
        ValueError: If the subdirectory is not relative to the
            corpus directory.
        ValueError: If the subdirectory doesn't exist.
    """
    corpus_sub_dir = validate_path(corpus_sub_dir, dir=True)

    if not corpus_sub_dir.is_relative_to(DATA_PATH):
        raise ValueError(
            f"'{corpus_sub_dir}' must be inside DATA_PATH ({DATA_PATH})"
        )
    if not corpus_sub_dir.exists():
        raise ValueError(f"'{corpus_sub_dir}' does not exist")

    files = []
    for file in corpus_sub_dir.rglob(file_path):
        files.append(file if pathlib else file.as_posix())

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
            (e.g., 'mscz').
        output_ext: The extension of the file type to convert to.
        regex: A regular expression to filter the file names (excluding
            extension) of the files being converted.
        out_dir: The path to the directory in which the converted files
            will be saved. Default = None.
    """
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
        program_files = os.environ.get("PROGRAMFILES")
        if program_files:
            ms4_path = os.path.join(
                program_files, r"MuseScore 4\bin\MuseScore4.exe"
            )
        else:
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

    score_mscz = validate_path(score_mscz)

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            f'ms3 extract -d "{score_mscz.parent}" -a '
            f'-i "{score_mscz.name}" -M "{tmp}" -l c',
            shell=True,
            check=True
        )
        os.rename(
            f"{tmp}/{score_mscz.stem}.measures.tsv",
            f"{tmp}/{score_mscz.stem}.tsv"
        )
        subprocess.run(
            f'MM convert -d "{tmp}" -o "{score_mscz.parent}" -l c',
            shell=True,
            check=True
        )

    score_mm = score_mscz.with_suffix(".mm.json")
    if verbose:
        print(f"Measure map '{score_mm}' created successfully.")

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

    score_mscz = validate_path(score_mscz)
    score_measures = validate_path(score_measures)
    subprocess.run(
        f'MM convert -d "{score_measures.parent}" -o "{score_mscz.parent}" '
        f'-r "{score_measures.name}" -l c',
        shell=True,
        check=True
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
    sep: str = ","
):
    """
    Convert a .csv file to a .yaml file. Used for creating the corpus
    metadata.

    Args:
        csv_file: The .csv file name.
        sep: The .csv file separator. Default = ",".
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
        measure: The measure.

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

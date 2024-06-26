# -*- coding: utf-8 -*-
"""
NAME:
===============================
Corpus Conversion (corpus_conversion.py)

BY:
===============================
Mark Gotham


LICENCE:
===============================

Creative Commons Attribution-ShareAlike 4.0 International License
https://creativecommons.org/licenses/by-sa/4.0/


ABOUT:
===============================

Basic script for updating `corpus_conversion.json` file with
the latest contents of the corpus so that it can be used 
for batch conversion of all scores (mscz files) to mxl.

Implement the batch conversion with the current 
`corpus_conversion.json` from this folder with the command:
>>> mscore -j corpus_conversion.json

Note: you need to have `mscore` for this.
If that"s not set up and you only want to run this rarely,
you may wish to add to `PATH` the directory containing `mscore` as frollows (for macOS):
```
export PATH=$PATH:/Applications/MuseScore\ 4.app/Contents/MacOS/
```

To create a new / updated version of the `corpus_conversion.json` file
using this script, run
>>> python3 corpus_conversion.py

This makes or updates the .json file with paired paths in this format:
    {
    "in": "../corpus/<Composer>/<Set>/<Movement>/<tite>.mscx",
    "out": "../corpus/<Composer>/<Set>/<Movement>/<tite>.mscx",
    }

For conversion to another file format, before the relevant step/s above,
replace ".mxl" with the desired format (".pdf" or ".mid") either
directly in the `corpus_conversion.json` file or
in this script (the `out_format` in the prep_conversion_doc function).

For more information, and for a within-app plugin alternative, see
https://musescore.org/en/handbook/3/command-line-options#Run_a_batch_job_converting_multiple_documents

"""

import json
from utils import CODE_PATH, CORPUS_PATH, get_corpus_files


composers = [
    "Bach,_Johann_Sebastian",
    "Beach,_Amy",
    "Beethoven,_Ludwig_van",
    "Brahms,_Johannes",
    "Bruckner,_Anton"
]


def prep_conversion_by_composer(
        composer: str = "Bruckner,_Anton",
        in_format: str = ".mscz",
        out_format: str = ".mxl",
        write: bool = True
) -> None:
    """
    Prepares a list of dicts with in / out paths of proposed conversions
    specific to each composer of the corpus.
    Optionally writes to a `corpus_conversion.json` file in this folder.
    """
    if composer not in composers:
        raise ValueError("Invalid composer name")

    if in_format not in [".mscz", ".mxl", ".pdf", ".mid"]:
        raise ValueError(f"Invalid `in_format`: {in_format}")

    if out_format not in [".mscz", ".mxl", ".pdf", ".mid"]:
        raise ValueError(f"Invalid `out_format`: {out_format}")

    files = get_corpus_files(
        sub_corpus_path=CORPUS_PATH / composer,
        file_name="*" + in_format,
    )

    out_data = []
    for f in files:
        s = str(f).replace(str(CORPUS_PATH), "../corpus")
        x = {"in": s,
             "out": s.replace(in_format, out_format)
             }
        out_data.append(x)

    if write:
        out_path = CODE_PATH / f"corpus_conversion_{composer.split(',')[0]}.json"
        with open(out_path, "w") as json_file:
            json.dump(
                sorted(out_data, key=lambda d: d["in"]),
                json_file,
                indent=4,
                sort_keys=True
            )


def make_contents():
    """
    Make / update a markdown tabular summary of files committed to the corpus,
    using the path to raw file for direct download.
    """

    raw = "https://github.com/MarkGotham/Hauptstimme/raw/main/corpus/"

    with open(CORPUS_PATH / "README.md", "w") as f:
        for x in (
                "## Corpus contents with direct download links\n",
                "|composer|collection|movement|score|-|melody|",
                "|---|---|---|---|---|---|"
        ):
            f.write(x + "\n")

        out_info = []
        for file_path in get_corpus_files(
                CORPUS_PATH,
                file_name="*_melody.mxl"
        ):
            path_to_dir = file_path.parent
            path_parts = path_to_dir.parts[-3:]
            composer, collection, movement = [x.replace("_", " ") for x in path_parts]

            melody = str(path_to_dir).replace(str(CORPUS_PATH), raw)
            mscz = melody.replace("_melody.mxl", ".mscz")
            mxl = melody.replace(".mscz", ".mxl")

            out_info.append(
                "|".join(
                    [composer, collection, movement, f"[.mscz]({mscz})", f"[.mxl]({mxl})", f"[melody.mxl]({melody})\n"]
                )
            )

        out_info.sort()
        for i in out_info:
            f.write(i)


if __name__ == "__main__":
    for c in composers:
        prep_conversion_by_composer(c)
    make_contents()

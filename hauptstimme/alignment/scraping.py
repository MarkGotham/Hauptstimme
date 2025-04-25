"""
NAME
===============================
Scraping (scraping.py)


BY
===============================
Matthew Blessing


LICENCE:
===============================
Code = MIT. See [README](https://github.com/MarkGotham/Hauptstimme/tree/main#licence)


ABOUT:
===============================
Functions relating to scraping files from web pages.

`get_github_repo_files` obtains URLs for all files of a particular type
from a particular GitHub repository.

`get_imslp_audio_files` scrapes the IMSLP wiki page of a particular
composition, obtaining metadata about each set of public domain
recordings, facilitating use for alignment.

`load_audio_from_url` loads an audio file into a NumPy array from a 
URL.

`download_file_from_url` downloads a file from a URL.
"""
from __future__ import annotations

import requests
import re
import time
import unicodedata
import librosa
import numpy as np
from pathlib import Path
from bs4 import BeautifulSoup, element
from io import BytesIO
from hauptstimme.utils import validate_path
from hauptstimme.types import Metadata
from typing import cast, List, Union


def get_github_repo_files(
    owner: str,
    repo: str,
    ext: str,
    regex: str = ""
) -> List[str]:
    """
    Get URLs to download all files with a particular file extension on 
    a GitHub repository.

    Args:
        owner: The owner of the GitHub repository's username.
        repo: The repository name.
        ext: The file extension.
        regex: Only include files that match this regex pattern.
            Default = ''.

    Returns:
        file_urls: A list of URLs to the files.
    """
    url = (f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?" +
           "recursive=1")

    time.sleep(1)  # Wait 1 second (GitHub crawl delay)
    response = requests.get(url)
    response_json = response.json()

    file_urls = []

    for file in response_json["tree"]:
        path = file["path"]
        if path.endswith(ext) and re.search(regex, path):
            file_urls.append(
                f"https://github.com/{owner}/{repo}/blob/main/{path}?raw=true"
            )

    return file_urls


def get_imslp_audio_files(
    url: str,
    user_region: str,
    ignore_complete: bool = True
) -> Metadata:
    """
    Scrape a particular composition's IMSLP wiki page to obtain 
    metadata about public domain recordings of the composition, 
    including URLs, performers, and more.

    Args:
        url: A URL for a composition's IMSLP wiki page.
        user_region: An abbreviation of the country/region where the 
            user is based (e.g., EU, US).
        ignore_complete: A flag for whether to ignore complete 
            recordings and just include recordings for each movement.
            Default = True.

    Returns:
        metadata: A list containing metadata for each group of 
            recordings (including a link for each recording file).
    """
    time.sleep(2)  # Wait 2 seconds (IMSLP crawl delay)
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    include_files = True

    metadata = []

    # Iterate through the groups of recordings
    elements = soup.find("div", id="tabAudio1")
    if elements:
        elements = cast(element.Tag, elements)
        for e in elements:
            # Ignore blank lines
            if not isinstance(e, element.NavigableString):
                e = cast(element.Tag, e)
                header = e.find("span", class_="mw-headline")
                if header:
                    header_text = header.get_text()
                    if header_text in ["Recordings", "Complete"]:
                        # Only include files in the "Recordings"
                        # section under the "Complete" heading or no
                        # heading
                        include_files = True
                    else:
                        include_files = False
                elif include_files:
                    # Find URLs
                    urls = []
                    hidden_span_tags = e.find_all("span", class_="hidden")
                    for hidden_span_tag in hidden_span_tags:
                        url_tag = hidden_span_tag.find(
                            "a", href=re.compile(r"\.(mp3|wav|flac)$")
                        )
                        if url_tag:
                            urls.append(
                                f"https://imslp.org{url_tag.get('href')}"
                            )
                    if len(urls) == 0:
                        continue

                    # Find IMSLP numbers
                    imslp_numbers = []
                    imslp_tags = e.find_all("a", class_="one-star")
                    for imslp_tag in imslp_tags:
                        imslp_numbers.append(imslp_tag.get("id"))
                    if len(imslp_numbers) == 0:
                        continue

                    # Find recording names
                    names = []
                    name_tags = e.find_all("span", title="Download this file")
                    for name_tag in name_tags:
                        name = name_tag.get_text()
                        name = unicodedata.normalize("NFKD", name).strip()
                        if name.split()[0] == "Complete":
                            if ignore_complete:
                                # Ignore recordings of full work
                                urls.pop(len(names))
                            else:
                                names.append("Complete Recording")
                        else:
                            names.append(name)
                    if len(names) == 0:
                        continue

                    # Find performers of recordings
                    performers = None
                    performers_tag = e.find("span", class_="pcat")
                    # If there is "Performer Pages" info
                    if performers_tag:
                        performers_tag = cast(element.Tag, performers_tag)
                        performer_url_tags = performers_tag.find_all("a")
                        performers = ", ".join(
                            [p.get_text().strip() for p in performer_url_tags]
                        )
                    else:
                        performers_tag = e.find(
                            "th", string=re.compile("Performers")
                        )
                        # If there is "Performers" info
                        if performers_tag:
                            if performers_tag.parent:
                                performers_text = performers_tag.parent.find(
                                    "td"
                                )
                                performers_text = cast(
                                    element.Tag, performers_text
                                )
                                for br in performers_text.find_all("br"):
                                    br.replace_with(" ")
                                performers = (
                                    performers_text.get_text().strip()
                                )

                    # Find publishing information of recordings
                    year = None
                    publisher = None
                    publish_tag = e.find(
                        "th", string=re.compile("Publisher Info.")
                    )
                    if publish_tag:
                        if publish_tag.parent:
                            publish_text = publish_tag.parent.find("td")
                            if publish_text:
                                publish_text = publish_text.get_text()
                                year_regex = (
                                    r",\s(1[0-9]{3}|2[0-9]{3}|[3-9][0-9]{3}" +
                                    r"|[1-9][0-9]{4,})"
                                )
                                year_match = re.search(
                                    year_regex, publish_text
                                )
                                if year_match:
                                    year = year_match.group(1)
                                publisher = re.sub(
                                    year_regex, "", publish_text, 1
                                )
                                publisher = re.sub(
                                    r"\s+", " ", publisher
                                ).strip()

                    # Get copyright info
                    copyright_tag = e.find(
                        "a",
                        string=re.compile(
                            r"\b(Public Domain|Creative Commons Zero|" +
                            r"EFF Open Audio License)\b"
                        )
                    )
                    non_pd_regions = e.find(
                        "span", style="color:red",
                        string=re.compile(r"^Non-PD")
                    )
                    if copyright_tag:
                        ignore_file = False
                        # Check if user is in any of the non-public
                        # domain regions
                        if non_pd_regions:
                            for text in non_pd_regions.get_text().split(","):
                                non_pd_region = text[7:]
                                if non_pd_region == user_region:
                                    # Ignore recordings if they are
                                    # non-public domain in the region
                                    # where the user is based
                                    ignore_file = True
                                    break
                            if ignore_file:
                                continue
                    else:
                        continue

                    # Each group of recordings has performers,
                    # publishing information, the year they were
                    # published, and audio files
                    recordings_metadata = {
                        "performers": performers,
                        "publisher": publisher,
                        "year": year,
                        "recording_files": []
                    }
                    # For each file, add the recording name, its IMSLP
                    # number, and a file link to the metadata
                    num_recordings = len(urls)
                    for i in range(num_recordings):
                        recordings_metadata["recording_files"].append(
                            {
                                "name": names[i],
                                "imslp_number": int(imslp_numbers[i]),
                                "imslp_link": urls[i]
                            }
                        )

                    metadata.append(recordings_metadata)

    return metadata


def load_audio_from_url(audio_url: str) -> np.ndarray:
    """
    Load an audio file at the given URL into a numpy array.

    Args:
        audio_url: A URL to an audio file.

    Returns:
        audio: The audio data.
    """
    response = requests.get(audio_url)
    audio_bytes = BytesIO(response.content)
    audio, _ = librosa.load(audio_bytes)

    return audio


def download_file_from_url(
    file_url: str,
    file_name: str,
    dir: Union[str, Path] = ""
):
    """
    Download a file given its URL.

    Args:
        file_url: A file URL.
        file_name: The filename to give the file.
        dir: A path to the directory in which to download the file.
    """
    dir = validate_path(dir, dir=True)

    ext = Path(file_url).suffix
    file_path = dir / Path(file_name).with_suffix(ext)

    response = requests.get(file_url)
    with open(file_path, mode="wb") as file:
        file.write(response.content)

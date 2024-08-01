from pathlib import Path
TEST_DIR = Path(__file__).parent
REPO_DIR = TEST_DIR.parent
import sys
sys.path.append(REPO_DIR / "code")


import unittest
from code.hauptstimme import *
from code.orchestra_part_split import *
from music21 import instrument


class Test(unittest.TestCase):

    def testHauptstimme(self):
        """
        Test case for a shortened version of Brahms 4-i,
        including a test of all 3 partForTemplate formats (int, str, instrument object).
        """

        p = TEST_DIR / "score.mxl"

        for i in [8, 'violin', instrument.Violin()]:
            process_one(p, part_for_template=i)

    def test_accent_to_sf(self):
        clean_up(TEST_DIR / "accent_test.mxl", map_accent_to_sf = True)

    def split(self):
        split_one(file_name_out="split_test_score_out.mxl")


# ------------------------------------------------------------------------------

from pathlib import Path
import unittest
from code import CODE_PATH, CORPUS_PATH, hauptstimme


class Test(unittest.TestCase):

    def testHauptstimme(self):
        """
        Test case for a shortened version of Brahms 4-i,
        including a test of all 3 partForTemplate formats (int, str, instrument object).
        """

        p = CORPUS_PATH / "sq"
        f = "score.mxl"

        # for i in [8, 'violin', instrument.Violin()]:
        hauptstimme.process_one(p, f, outPathData=p, outPathScore=p)  #, partForTemplate=i)


# ------------------------------------------------------------------------------

from __future__ import annotations

import pathlib
import numpy as np

CODE_PATH = pathlib.Path(__file__).parent
REPO_PATH = CODE_PATH.parent
CORPUS_PATH = REPO_PATH / "OpenScoreOrchestra"

SAMPLE_RATE = 22050
FEATURE_RATE = 50
STEP_WEIGHTS = np.array([1.5, 1.5, 2.0])
THRESHOLD_REC = 10 ** 6

ROUNDING_VALUE = 4

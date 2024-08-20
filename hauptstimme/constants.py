import pathlib
import numpy as np

code_path = pathlib.Path(__file__).parent
repo_path = code_path.parent
corpus_path = repo_path / "OpenScoreOrchestra"
CODE_PATH = code_path.as_posix()
REPO_PATH = repo_path.as_posix()
CORPUS_PATH = corpus_path.as_posix()

SAMPLE_RATE = 22050
FEATURE_RATE = 50
STEP_WEIGHTS = np.array([1.5, 1.5, 2.0])
THRESHOLD_REC = 10 ** 6

ROUNDING_VALUE = 4

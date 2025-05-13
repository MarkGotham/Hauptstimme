from __future__ import annotations

import numpy as np
import pandas as pd
import datetime
from typing import Union, List, Any, Dict, Tuple, Optional

ArrayLike = Union[List[Any], np.ndarray, pd.Series]
Scalar = Union[int, float]

RecFileMetadata = Dict[str, Union[str, int]]
RecordingsMetadata = Dict[
    str, Optional[Union[str, List[RecFileMetadata]]]
]
Metadata = List[RecordingsMetadata]

AudioData = Tuple[
    str, str, Optional[datetime.time], Optional[datetime.time], str
]

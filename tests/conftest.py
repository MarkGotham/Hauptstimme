import sys
from pathlib import Path

# Same convention as scripts/: make `src` importable from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

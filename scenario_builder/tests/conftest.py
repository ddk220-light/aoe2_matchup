import sys
from pathlib import Path

SB = Path(__file__).resolve().parents[1]          # scenario_builder/
if str(SB) not in sys.path:
    sys.path.insert(0, str(SB))

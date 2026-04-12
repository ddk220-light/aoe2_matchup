import os
import sys

# Make webapp importable from tests/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))

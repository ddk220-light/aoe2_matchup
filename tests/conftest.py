import os
import sys

# Make webapp modules importable bare (import app) AND as a namespace package
# (import webapp.battle_outcome) — the repo root is NOT on sys.path when the
# suite is launched as plain `pytest` (e.g. CI) instead of `python -m pytest`.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "webapp"))
sys.path.insert(0, _ROOT)

import pytest
import app as flask_app

@pytest.fixture
def client():
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        yield c

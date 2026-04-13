import os
import sys

# Make webapp importable from tests/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))

import pytest
import app as flask_app

@pytest.fixture
def client():
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        yield c

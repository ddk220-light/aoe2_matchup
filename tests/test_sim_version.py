import os
import tempfile
import pytest
from sim_version import compute_sim_version


def test_returns_16_char_hex():
    v = compute_sim_version()
    assert isinstance(v, str)
    assert len(v) == 16
    int(v, 16)  # parses as hex


def test_changes_when_a_source_file_changes(tmp_path):
    f1 = tmp_path / "a.py"
    f1.write_text("x = 1\n")
    f2 = tmp_path / "b.py"
    f2.write_text("y = 2\n")
    v_before = compute_sim_version([str(f1), str(f2)])
    f1.write_text("x = 999\n")
    v_after = compute_sim_version([str(f1), str(f2)])
    assert v_before != v_after


def test_stable_when_files_unchanged(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("payload\n")
    assert compute_sim_version([str(f)]) == compute_sim_version([str(f)])

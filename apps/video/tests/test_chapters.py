# apps/video/tests/test_chapters.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto.chapters import write_chapters, _civ_adj


def test_chapter_lines_from_labels(tmp_path):
    # NB: write_chapters keeps the existing "M:SS - label" format (see
    # test_pure.py::test_write_chapters); the (label, duration_seconds) pairing is
    # the invariant. Cumulative starts: 0.0, 12.0, 32.5 -> floored to 0/12/32s.
    out = tmp_path / "chapters.txt"
    write_chapters([("Intro", 12.0), ("Expected win #1 — Heavy Camel Rider", 20.5),
                    ("Expected win #2 — Shrivamsha Rider", 18.0)], out)
    lines = out.read_text().splitlines()
    assert lines[0].startswith("0:00")
    assert lines[0].endswith("- Intro")
    assert "Expected win #1" in lines[1] and lines[1].startswith("0:12")
    assert lines[2].startswith("0:32")   # 12.0 + 20.5 -> 32s floor


def test_civ_adj_moved():
    assert _civ_adj("Aztecs") == "Aztec"
    assert _civ_adj("Chinese") == "Chinese"
    assert _civ_adj("Armenians") == "Armenian"

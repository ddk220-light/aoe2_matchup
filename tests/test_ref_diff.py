# tests/test_ref_diff.py
import os, sqlite3, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))
import ref_diff


def _mk(path, rows):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE ref_units (civ_name TEXT, unit_slug TEXT, age TEXT, "
              "base_hp REAL, base_attack REAL, base_cost_food REAL, base_cost_wood REAL, "
              "base_cost_gold REAL, base_train_time REAL)")
    c.executemany("INSERT INTO ref_units VALUES (?,?,?,?,?,?,?,?,?)", rows)
    c.commit(); c.close()


def test_diff_detects_changed_fields(tmp_path):
    prev = str(tmp_path / "prev.db"); new = str(tmp_path / "new.db")
    _mk(prev, [("Wei", "tiger_cavalry_wei", "Imperial", 115, 12, 70, 0, 90, 15)])
    _mk(new,  [("Wei", "tiger_cavalry_wei", "Imperial", 110, 12, 70, 0, 90, 18)])
    deltas, changed_slugs = ref_diff.diff(prev, new)
    fields = {(d["civ_name"], d["unit_slug"], d["field"]): (d["old_value"], d["new_value"])
              for d in deltas}
    assert fields[("Wei", "tiger_cavalry_wei", "base_hp")] == (115, 110)
    assert fields[("Wei", "tiger_cavalry_wei", "base_train_time")] == (15, 18)
    assert "tiger_cavalry_wei" in changed_slugs


def test_diff_no_change(tmp_path):
    prev = str(tmp_path / "p.db"); new = str(tmp_path / "n.db")
    _mk(prev, [("Franks", "knight", "Imperial", 100, 10, 60, 0, 75, 30)])
    _mk(new,  [("Franks", "knight", "Imperial", 100, 10, 60, 0, 75, 30)])
    deltas, changed_slugs = ref_diff.diff(prev, new)
    assert deltas == [] and changed_slugs == set()

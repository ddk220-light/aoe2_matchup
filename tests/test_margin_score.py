import json
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "data" / "validation" / "tape_runs.db"
FIXTURE = REPO / "aoe2x" / "validation" / "tape_margins.json"


def test_fixture_rows_all_exist_in_the_corpus():
    corpus = json.loads((REPO / "aoe2x/validation/tape_corpus.json").read_text(encoding="utf-8"))["rows"]
    keys = {(r["subject_civ"], r["subject_slug"], r["opp_civ"], r["opp_slug"]) for r in corpus}
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))["rows"]
    assert len(fx) == 11
    for r in fx:
        k = (r["subject_civ"], r["subject_slug"], r["opp_civ"], r["opp_slug"])
        assert k in keys, f"fixture row not in corpus: {k}"


def test_hp_pct_convention_reproduces_the_documented_numbers():
    from aoe2x.validation.margin_score import tape_hp_pct
    # 1844/(4*620), 1354/(6*320), 798/(7*180), 833/(15*95)
    assert abs(tape_hp_pct(1844, 4, 620) - 0.7435) < 0.0005
    assert abs(tape_hp_pct(1354, 6, 320) - 0.7052) < 0.0005
    assert abs(tape_hp_pct(798, 7, 180) - 0.6333) < 0.0005
    assert abs(tape_hp_pct(833, 15, 95) - 0.5846) < 0.0005


def test_score_run_returns_two_maes_for_an_existing_run():
    from aoe2x.validation.margin_score import score_run
    db = sqlite3.connect(str(DB))
    tag = db.execute(
        "SELECT run_tag FROM tape_runs WHERE engine='simulation_real.py'"
        " ORDER BY started_utc DESC LIMIT 1").fetchone()[0]
    res = score_run(str(DB), tag)
    assert res["survivor_mae"] >= 0.0
    assert res["hp_mae_pp"] >= 0.0
    assert len(res["rows"]) >= 1
    # every scored row must name which side the tape reports
    for r in res["rows"]:
        assert r["side"] in ("subject", "opp")

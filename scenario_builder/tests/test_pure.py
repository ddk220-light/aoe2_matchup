"""Unit tests for the pipeline's pure logic — the parts whose past regressions are
narrated in code comments (readout parsing, count cleaning, sidecar repair) plus the
new hp-merge alignment. No game, no screen, no ffmpeg.

Run from scenario_builder/:  .venv\\Scripts\\python.exe -m pytest tests -q
"""
import json

import pytest

from overlay.readout import parse_counts
from overlay.video_extract import _clean_monotonic
from overlay.overlay_hp import clean_rows, _interp
from overlay.hp_merge import align_offset, merge_rows, merge_sidecars
from overlay.hud import hud_band_height


# --------------------------------------------------------------------------- #
# readout parsing
# --------------------------------------------------------------------------- #
class TestParseCounts:
    def test_plain(self):
        assert parse_counts("Elite Guecha Warrior: 30 vs Elite Arambai: 24") == (30, 24)

    def test_spaces_dropped_around_vs(self):
        assert parse_counts("EliteGuechaWarrior:27vsEliteArambai:16") == (27, 16)

    def test_zero_read_as_letter_O(self):
        # the real-world regression: '30' OCR'd as '3O' silently became 3
        assert parse_counts("EliteGuechaWarrior:3OvsEliteArambai:23") == (30, 23)

    def test_one_read_as_letter_l(self):
        assert parse_counts("Foo:l8 vs Bar:12") == (18, 12)

    def test_lowercased_input(self):
        # the screen watcher lowercases OCR text before parsing
        assert parse_counts("elite guecha warrior:3o vs elite arambai:2o") == (30, 20)

    def test_title_form_falls_back_to_vs_split(self):
        assert parse_counts("30 Elite Temple Guard  VS  24 Elite Jaguar Warrior") == (30, 24)

    def test_garbage_is_none(self):
        assert parse_counts("the quick brown fox") is None
        assert parse_counts("") is None

    def test_lone_zero_read_as_letter_o(self):
        # the army-wiped reading: 'Elite Guecha Warrior: 0' OCRs as ':o' — must be 0,
        # or the loser's count freezes above zero (real regression from the sweep)
        assert parse_counts("elite guecha warrior:o vs elite berserk:23") == (0, 23)

    def test_long_letter_runs_still_rejected(self):
        # short lookalike tokens are counts ('o'=0, 'l'=1); LONG letter runs are noise
        assert parse_counts("name:Ilo vs other:oIl") is None


# --------------------------------------------------------------------------- #
# survivor-count cleaning (footage OCR)
# --------------------------------------------------------------------------- #
class TestCleanMonotonic:
    def test_low_first_misread_does_not_poison_series(self):
        # the real-world regression: first sample read 3 instead of 30; forward-min
        # then clamped the WHOLE series to 3
        assert _clean_monotonic([3, 30, 30, 29, 28], cap=30)[0] == 30

    def test_high_single_misread_is_filtered(self):
        # '4' split into '44' for one frame
        out = _clean_monotonic([30, 28, 44, 27, 26], cap=30)
        assert max(out) <= 30
        assert out == sorted(out, reverse=True)

    def test_low_single_misread_is_filtered(self):
        # 27 read as 2 for one frame must not create 25 phantom deaths
        out = _clean_monotonic([28, 27, 2, 26, 25], cap=30)
        assert out[2] >= 26

    def test_monotonic_non_increasing(self):
        out = _clean_monotonic([30, 29, 29, 30, 28], cap=30)
        assert all(a >= b for a, b in zip(out, out[1:]))

    def test_empty(self):
        assert _clean_monotonic([], cap=30) == []


# --------------------------------------------------------------------------- #
# gRPC sidecar repair + interpolation
# --------------------------------------------------------------------------- #
def _rows(counts1, hp1, counts2=None, hp2=None):
    counts2 = counts2 or [30] * len(counts1)
    hp2 = hp2 or [3000.0] * len(counts1)
    return [{"game_s": float(i),
             "side1": {"count": c1, "hp": h1},
             "side2": {"count": c2, "hp": h2}}
            for i, (c1, h1, c2, h2) in enumerate(zip(counts1, hp1, counts2, hp2))]


class TestCleanRows:
    def test_count_dip_is_lifted(self):
        rows = clean_rows(_rows([30, 0, 28], [3000, 2800, 2600]))
        assert [r["side1"]["count"] for r in rows] == [30, 28, 28]

    def test_hp_dropout_is_interpolated(self):
        # 20 units alive but ~0 total HP (<1 hp/unit) is a decode dropout
        rows = clean_rows(_rows([30, 20, 20], [3000.0, 5.0, 1800.0]))
        assert rows[1]["side1"]["hp"] == pytest.approx(2400.0, abs=1.0)

    def test_healing_rise_is_preserved(self):
        rows = clean_rows(_rows([30, 30, 30], [2000.0, 2200.0, 2400.0]))
        assert [r["side1"]["hp"] for r in rows] == [2000.0, 2200.0, 2400.0]

    def test_interp_steps_count_and_lerps_hp(self):
        rows = _rows([30, 20], [3000.0, 2000.0])
        cnt, hp = _interp(rows, 0.5, "side1")
        assert hp == pytest.approx(2500.0)
        assert cnt in (20, 30)


# --------------------------------------------------------------------------- #
# hp-merge alignment (OCR clock + gRPC HP)
# --------------------------------------------------------------------------- #
def _linear_counts(n, start, deaths_per_s):
    return [max(0, round(start - deaths_per_s * t)) for t in range(n)]


class TestHpMerge:
    def test_align_recovers_known_offset(self):
        # same death curve, gRPC clock 3s ahead of the OCR clock
        ocr = _rows(_linear_counts(20, 30, 1.5), [0] * 20)
        grpc_counts = [30] * 3 + _linear_counts(20, 30, 1.5)   # shifted by +3s
        grpc = _rows(grpc_counts, [100.0] * len(grpc_counts))
        delta, rmse = align_offset(ocr, grpc, d0=0.0, span=6.0, step=0.5)
        assert delta == pytest.approx(3.0, abs=0.5)
        assert rmse < 1.0

    def test_merge_rows_takes_ocr_counts_and_grpc_hp(self):
        ocr = _rows([30, 25, 20], [30, 25, 20])
        grpc = _rows([30, 25, 20], [3000.0, 2400.0, 1700.0])
        merged = merge_rows(ocr, grpc, delta=0.0)
        assert [r["side1"]["count"] for r in merged] == [30, 25, 20]
        assert [r["side1"]["hp"] for r in merged] == [3000.0, 2400.0, 1700.0]

    def test_quality_gate_rejects_disagreeing_series(self, tmp_path):
        ocr = {"video_game_start_s": 8.0,
               "rows": _rows(_linear_counts(15, 30, 2.0), [0] * 15)}
        grpc = {"video_game_start_s": 8.0,
                "rows": _rows([30] * 15, [3000.0] * 15)}      # nobody dies: disagrees
        po, pg = tmp_path / "o.json", tmp_path / "g.json"
        po.write_text(json.dumps(ocr)); pg.write_text(json.dumps(grpc))
        assert merge_sidecars(po, pg, tmp_path / "m.json", logfn=lambda m: None) is None

    def test_merge_sidecars_roundtrip(self, tmp_path):
        counts = _linear_counts(15, 30, 2.0)
        ocr = {"video_game_start_s": 8.0, "rows": _rows(counts, counts)}
        grpc = {"video_game_start_s": 8.0,
                "rows": _rows(counts, [c * 90.0 for c in counts])}
        po, pg = tmp_path / "o.json", tmp_path / "g.json"
        po.write_text(json.dumps(ocr)); pg.write_text(json.dumps(grpc))
        out = merge_sidecars(po, pg, tmp_path / "m.json", logfn=lambda m: None)
        assert out
        merged = json.loads((tmp_path / "m.json").read_text())
        assert merged["source"] == "ocr_counts+grpc_hp"
        assert merged["rows"][0]["side1"]["hp"] == pytest.approx(2700.0, abs=200.0)


# --------------------------------------------------------------------------- #
# combat math (the duel block on the live cards)
# --------------------------------------------------------------------------- #
class TestCombatMath:
    def test_base_damage_minus_armor(self):
        from overlay.combat_math import damage_per_hit
        assert damage_per_hit({4: 10}, {4: 3, 3: 0}) == 7.0

    def test_bonus_applies_only_with_class_membership(self):
        from overlay.combat_math import damage_per_hit
        # +4 vs class 15 counts only when the defender HAS class 15
        assert damage_per_hit({3: 12, 15: 4}, {3: 7, 4: 5, 15: 0}) == 9.0
        assert damage_per_hit({3: 12, 15: 4}, {3: 7, 4: 5}) == 5.0

    def test_minimum_one_damage(self):
        from overlay.combat_math import damage_per_hit
        assert damage_per_hit({4: 2}, {4: 10, 3: 0}) == 1.0

    def test_charge_folds_into_first_hit_through_armor(self):
        from overlay.combat_math import damage_per_hit
        assert damage_per_hit({4: 8}, {4: 3, 3: 0}, extra_base=25) == 30.0
        assert damage_per_hit({4: 8}, {4: 3, 3: 0}, extra_base=25,
                              ignore_armor=True) == 5.0 + 25.0

    def test_primary_damage_class_guecha_style(self):
        from overlay.combat_math import primary_damage_class
        assert primary_damage_class({3: 12, 4: 0}) == 3   # melee unit, pierce damage
        assert primary_damage_class({4: 14, 3: 0}) == 4

    def test_duel_hits_ttk_dps(self):
        from overlay.combat_math import duel
        att = {"attacks": {4: 10}, "reload_s": 2.0, "is_ranged": False}
        dfd = {"armors": {4: 0, 3: 0}, "hp": 35}
        d = duel(att, dfd)
        assert d["dmg"] == 10.0 and d["hits"] == 4
        assert d["ttk_s"] == 6.0 and d["dps"] == 5.0

    def test_duel_charged_first_hit_reduces_hits(self):
        from overlay.combat_math import duel
        att = {"attacks": {4: 10}, "reload_s": 2.0,
               "charge": {"melee": 10, "recharge_s": 20, "ignores_armor": False}}
        dfd = {"armors": {4: 0, 3: 0}, "hp": 35}
        d = duel(att, dfd)
        assert d["first_hit"] == 20.0 and d["hits"] == 3

    def test_duel_accuracy_scales_dps_for_ranged(self):
        from overlay.combat_math import duel
        att = {"attacks": {3: 10}, "reload_s": 2.0, "is_ranged": True,
               "accuracy_pct": 50}
        dfd = {"armors": {4: 0, 3: 0}, "hp": 20}
        assert duel(att, dfd)["dps"] == 2.5

    def test_duel_missing_data_is_none(self):
        from overlay.combat_math import duel
        assert duel({"attacks": {}}, {"armors": {}, "hp": 50}) is None


# --------------------------------------------------------------------------- #
# gRPC-primary sanity gate
# --------------------------------------------------------------------------- #
class TestGrpcSane:
    def _sc(self, c1, c2):
        return {"rows": _rows(c1, [c * 90.0 for c in c1], c2, [c * 85.0 for c in c2])}

    def test_clean_resolved_fight_is_sane(self):
        from overlay.hp_merge import grpc_sane
        d = self._sc(_linear_counts(20, 30, 1.0), _linear_counts(20, 24, 1.5))
        assert grpc_sane(d, (30, 24)) is True

    def test_wrong_start_counts_rejected(self):
        from overlay.hp_merge import grpc_sane
        d = self._sc(_linear_counts(20, 30, 1.0), _linear_counts(20, 24, 1.5))
        assert grpc_sane(d, (30, 20)) is False      # decode lost units at the seed

    def test_flickering_counts_rejected(self):
        from overlay.hp_merge import grpc_sane
        c1 = [30, 27, 30, 26, 30, 25, 30, 24, 0, 0]  # repeated dropout-recovery
        d = self._sc(c1, [24] * 10)
        assert grpc_sane(d, (30, 24)) is False

    def test_unresolved_short_fight_rejected(self):
        from overlay.hp_merge import grpc_sane
        d = self._sc([30, 29, 28, 27, 26, 25], [24, 23, 22, 21, 20, 19])
        assert grpc_sane(d, (30, 24)) is False      # nobody at 0 and only ~5s of rows

    def test_too_few_rows_rejected(self):
        from overlay.hp_merge import grpc_sane
        assert grpc_sane({"rows": _rows([30, 0], [1, 0])}, (30, 30)) is False


# --------------------------------------------------------------------------- #
# equal-resources math (website weights, 3000 budget, train batches)
# --------------------------------------------------------------------------- #
class TestEqualResourceCounts:
    def _patch(self, monkeypatch, w1, w2):
        import overlay.overlay_data as od
        monkeypatch.setattr(od, "get_unit_card", lambda civ, slug, *a, **k: {
            "cost": {"weighted": w1 if slug == "a" else w2}})

    def test_cheaper_side_takes_the_cap(self, monkeypatch):
        from auto.orchestrate_matchup import equal_resource_counts
        self._patch(monkeypatch, 50.0, 100.0)          # 30 x 50 = 1500 <= 3000
        assert equal_resource_counts("C1", "a", "C2", "b") == (30, 15)

    def test_budget_shrinks_the_cap(self, monkeypatch):
        from auto.orchestrate_matchup import equal_resource_counts
        self._patch(monkeypatch, 125.0, 250.0)         # 3000 // 125 = 24 < 30
        assert equal_resource_counts("C1", "a", "C2", "b") == (24, 12)

    def test_side2_cheaper(self, monkeypatch):
        from auto.orchestrate_matchup import equal_resource_counts
        self._patch(monkeypatch, 125.0, 105.0)         # n2 = min(30, 28) = 28
        assert equal_resource_counts("C1", "a", "C2", "b") == (23, 28)

    def test_cost_weights_match_the_website(self):
        # overlay_data mirrors webapp/simulation_real.py — fail loudly on drift
        import re
        from pathlib import Path
        from overlay import overlay_data as od
        src = (Path(__file__).resolve().parents[2]
               / "webapp" / "simulation_real.py").read_text(encoding="utf-8")
        for name, val in (("FOOD", od.COST_WEIGHT_FOOD), ("WOOD", od.COST_WEIGHT_WOOD),
                          ("GOLD", od.COST_WEIGHT_GOLD)):
            m = re.search(rf"COST_WEIGHT_{name}\s*=\s*([0-9.]+)", src)
            assert m, f"COST_WEIGHT_{name} not found in simulation_real.py"
            assert float(m.group(1)) == val, f"COST_WEIGHT_{name} drifted"


@pytest.mark.skipif(
    not __import__("pathlib").Path(__file__).resolve()
        .parents[2].joinpath("webapp", "aoe2_reference.db").exists(),
    reason="reference DB not built")
class TestUnitCardCosts:
    def test_blackwood_archer_batch_of_two(self):
        from overlay.overlay_data import get_unit_card
        c = get_unit_card("Tupi", "elite_blackwood_archer_tupi")["cost"]
        assert c["batch"] == 2
        assert c["wood"] == 17.5 and c["gold"] == 22.5      # 35w/45g buys TWO
        assert c["train"]["total"] == 80
        assert c["weighted"] == round(17.5 * 0.7 + 22.5 * 1.5, 2)

    def test_mayan_plumed_discount_in_cost(self):
        from overlay.overlay_data import get_unit_card
        c = get_unit_card("Mayans", "elite_plumed_archer_mayans")["cost"]
        assert (c["wood"], c["gold"]) == (39, 39)           # 55/55 base, -30% Imperial

    def test_white_feather_guard_icon_resolves(self):
        from overlay.overlay_data import get_unit_card
        icon = get_unit_card("Shu", "elite_white_feather_guard_shu")["icon"]
        assert icon.endswith("Elite_White_Feather_Crossbowman.png")




# --------------------------------------------------------------------------- #
# gRPC sidecar clock conversion (stream = game-sim seconds at GAME_SPEED)
# --------------------------------------------------------------------------- #
class TestGrpcSidecarClock:
    def test_write_sidecar_converts_stream_clock_to_video_seconds(self, tmp_path):
        import json
        from auto import grpc_capture
        from auto.config import GAME_SPEED
        pfx = str(tmp_path / "run")
        with open(pfx + ".hp_log.jsonl", "w") as f:
            f.write(json.dumps({"game_s": 0.0, "side1": {"count": 24, "hp": 1440},
                                "side2": {"count": 30, "hp": 2250}}) + "\n")
            f.write(json.dumps({"game_s": 28.82, "side1": {"count": 0, "hp": 0},
                                "side2": {"count": 24, "hp": 1644}}) + "\n")
        with open(pfx + ".meta.json", "w") as f:
            json.dump({"wall0_epoch": 1000.0, "end_game_s": 28.82}, f)
        out = grpc_capture.write_sidecar(pfx, t_rec=990.0)
        with open(out) as f:
            d = json.load(f)
        assert d["clock"] == "video" and d["game_speed"] == GAME_SPEED
        assert d["rows"][0]["game_s"] == 0.0
        assert d["rows"][-1]["game_s"] == round(28.82 / GAME_SPEED, 2)
        assert d["end_game_s"] == round(28.82 / GAME_SPEED, 2)
        assert d["video_game_start_s"] == 10.0


# --------------------------------------------------------------------------- #
# momentum trend (centre-plate arrows)
# --------------------------------------------------------------------------- #
class TestBattleTrend:
    def test_side1_winning_the_trade(self):
        from overlay.overlay_hp import battle_trend
        rows = _rows([30, 30, 30, 29], [0] * 4, [24, 20, 15, 10], [0] * 4)
        assert battle_trend(rows, 3.0) == (1, -1)

    def test_even_trade_is_neutral(self):
        from overlay.overlay_hp import battle_trend
        rows = _rows([30, 28, 26, 24], [0] * 4, [24, 22, 20, 18], [0] * 4)
        assert battle_trend(rows, 3.0) == (0, 0)

    def test_too_early_is_neutral(self):
        from overlay.overlay_hp import battle_trend
        rows = _rows([30, 20], [0] * 2, [24, 24], [0] * 2)
        assert battle_trend(rows, 1.0) == (0, 0)


# --------------------------------------------------------------------------- #
# pixel game-start anchor
# --------------------------------------------------------------------------- #
class TestFindGameStart:
    def _write_clip(self, path, fps=10, segs=()):
        """segs = [(seconds, luma), ...] — write a flat-luma test clip."""
        import cv2
        import numpy as np
        vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (160, 90))
        for secs, luma in segs:
            fr = np.full((90, 160, 3), luma, dtype=np.uint8)
            for _ in range(int(secs * fps)):
                vw.write(fr)
        vw.release()

    def test_detects_load_to_game_jump(self, tmp_path):
        from overlay.video_extract import find_game_start
        p = tmp_path / "t.mp4"
        # editor -> click flash (short, must be debounced) -> load screen -> game
        self._write_clip(p, segs=[(3.0, 32), (0.2, 200), (3.0, 22), (4.0, 130)])
        v0 = find_game_start(str(p))
        assert v0 == pytest.approx(6.2, abs=0.35)

    def test_no_game_means_none(self, tmp_path):
        from overlay.video_extract import find_game_start
        p = tmp_path / "t.mp4"
        self._write_clip(p, segs=[(6.0, 30)])          # menu only, never bright
        assert find_game_start(str(p)) is None


# --------------------------------------------------------------------------- #
# compose helpers
# --------------------------------------------------------------------------- #
class TestComposeHelpers:
    def test_battle_end_at(self, tmp_path):
        from overlay.compose import _battle_end_at
        rows = _rows([30, 28, 25, 25, 25], [0] * 5)        # last change at game_s=2
        sc = tmp_path / "x.hp.json"
        sc.write_text(json.dumps({"video_game_start_s": 8.0, "rows": rows}))
        assert _battle_end_at(sc, buffer=2.5) == pytest.approx(8.0 + 2.0 + 2.5)

    def test_battle_end_at_unreadable_is_none(self, tmp_path):
        from overlay.compose import _battle_end_at
        assert _battle_end_at(tmp_path / "missing.json") is None

    def test_sidecar_summary_winner_by_elimination(self, tmp_path):
        from overlay.compose import _sidecar_summary
        rows = _rows([30, 25, 23], [3000.0, 2400.0, 2310.0],
                     [24, 10, 0], [2040.0, 800.0, 0.0])
        sc = tmp_path / "s.hp.json"
        sc.write_text(json.dumps({"video_game_start_s": 8.0, "rows": rows,
                                  "source": "ocr_readout"}))
        s = _sidecar_summary(sc, counts=(30, 24))
        assert s["winner"] == 1
        assert s["s1"] == {"start": 30, "left": 23, "hp": pytest.approx(0.77)}
        assert s["s2"]["left"] == 0 and s["s2"]["hp"] == 0.0
        assert s["true_hp"] is False
        assert s["duration_s"] == pytest.approx(2.0)   # last count change at game_s=2

    def test_verdict_thresholds(self):
        from overlay.render_card import _verdict
        mk = lambda hp, w=1: {"winner": w, "s1": {"hp": hp}, "s2": {"hp": 0.0}}
        assert _verdict(mk(0.77)) == "Decisive victory"
        assert _verdict(mk(0.45)) == "Clear victory"
        assert _verdict(mk(0.10)) == "Close call"
        assert _verdict({"winner": 0}) == "Stalemate"

    def test_sidecar_summary_cap_hit_hp_decides(self, tmp_path):
        from overlay.compose import _sidecar_summary
        rows = _rows([30, 28], [3000.0, 1500.0], [24, 20], [2040.0, 1700.0])
        sc = tmp_path / "s.hp.json"
        sc.write_text(json.dumps({"video_game_start_s": 8.0, "rows": rows,
                                  "source": "ocr_counts+grpc_hp"}))
        s = _sidecar_summary(sc, counts=(30, 24))
        assert s["winner"] == 2          # 83% HP beats 50%
        assert s["true_hp"] is True

    def test_sidecar_summary_unreadable_is_none(self, tmp_path):
        from overlay.compose import _sidecar_summary
        assert _sidecar_summary(tmp_path / "missing.json") is None

    def test_atempo_chain(self):
        from overlay.compose import _atempo_chain
        assert _atempo_chain(1.5) == "atempo=1.50000"
        assert _atempo_chain(6.0) == "atempo=2.0,atempo=2.0,atempo=1.50000"   # 2*2*1.5

    def test_hud_band_height_scales(self):
        assert hud_band_height(1440) == 144
        assert hud_band_height(720) == 74


# --------------------------------------------------------------------------- #
# batch helpers
# --------------------------------------------------------------------------- #
class TestBatchHelpers:
    def test_slice_1based(self):
        from auto.batch_matchups import _slice_1based
        assert _slice_1based("", 10) == (0, 10)
        assert _slice_1based("1:5", 10) == (0, 5)
        assert _slice_1based("3:", 10) == (2, 10)
        assert _slice_1based(":4", 10) == (0, 4)

    def test_civ_adj(self):
        from auto.batch_matchups import _civ_adj
        assert _civ_adj("Aztecs") == "Aztec"
        assert _civ_adj("Chinese") == "Chinese"
        assert _civ_adj("Armenians") == "Armenian"

    def test_parse_matchup(self):
        from auto.batch_matchups import _parse_matchup
        m = _parse_matchup("Muisca:s1:Aztecs:s2:Some Name: with colon")
        assert m["civ1"] == "Muisca" and m["name"] == "Some Name: with colon"

    def test_write_chapters(self, tmp_path):
        from auto.batch_matchups import write_chapters
        p = write_chapters([("First", 65.0), ("Second", 30.0), ("Third", 3600.0)],
                           tmp_path / "ch.txt")
        lines = p.read_text().strip().splitlines()
        assert lines[0] == "0:00 - First"
        assert lines[1] == "1:05 - Second"
        assert lines[2] == "1:35 - Third"


# --------------------------------------------------------------------------- #
# scenario-build positioning
# --------------------------------------------------------------------------- #
class TestChoosePositions:
    def test_same_count_keeps_formation(self):
        from build_run import _choose_positions
        pos = [(0, 0), (1, 0), (0, 1), (1, 1)]
        assert _choose_positions(pos, 4) == pos

    def test_fewer_keeps_compact_core(self):
        from build_run import _choose_positions
        pos = [(0, 0), (1, 0), (0, 1), (1, 1), (10, 10)]
        out = _choose_positions(pos, 4)
        assert len(out) == 4 and (10, 10) not in out

    def test_more_adds_extras(self):
        from build_run import _choose_positions
        out = _choose_positions([(0, 0), (2, 0)], 5)
        assert len(out) == 5

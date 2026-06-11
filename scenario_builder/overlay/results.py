"""
results.py — results extraction for the matchup pipeline.

Two providers behind one shape (`MatchResult`), so the overlay renderer doesn't
care where the numbers came from:

  * extract_sim_results()   - runs the project's POSITION-BASED engine
    (webapp/simulation_real.py, the one the matchup table uses) and samples a
    survivor/HP timeline tick-by-tick. Truthful + testable with no game needed.
    Drives the live HUD + outro card today.

  * extract_video_results() - STUB for the real-game path: read the on-screen
    survivor numbers that the scenario's `count_units_into_variable` ->
    `display_instructions` puts up, or the post-game stats screen. Needs game
    footage + an OCR engine (Tesseract/pytesseract) or fixed-font digit template
    matching. Documented here; wired in once recording works.

Note: we DON'T modify simulation_real.py — we reuse its public surface
(BattleSimulation.setup_team / step / alive_count / total_hp) and run our own
sampling loop.
"""
from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

_REPO = Path(__file__).resolve().parents[2]
_WEBAPP = _REPO / "webapp"
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from aoe2x.sim import simulation_real as SR  # noqa: E402

UNITS_DB = _WEBAPP / "aoe2_units.db"


@dataclass
class MatchResult:
    civ1: str
    slug1: str
    civ2: str
    slug2: str
    start1: int
    start2: int
    winner: int                 # 1, 2, or 0 (draw)
    survivors1: int
    survivors2: int
    hp1_pct: float              # surviving-side total HP fraction
    hp2_pct: float
    duration_s: float
    end_reason: str
    engine: str
    # per-sample series: each item {t, s1, s2, hp1, hp2}
    timeline: List[dict] = field(default_factory=list)
    # for video OCR: absolute window (s) of the readable readout in the SOURCE clip,
    # so callers can trim the recording to just the fight. 0.0 for sim results.
    fight_start_s: float = 0.0
    fight_end_s: float = 0.0

    @property
    def winner_label(self) -> str:
        return {1: "team1", 2: "team2", 0: "draw"}[self.winner]


def load_unit(civ: str, slug: str, db_path=UNITS_DB) -> dict:
    """Load a fully-upgraded unit row from aoe2_units.db and prepare it for the sim."""
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    try:
        rows = db.execute(
            """SELECT us.*, u.age_id FROM unit_stats us
               JOIN units u ON us.unit_id = u.id
               JOIN civilizations c ON us.civ_id = c.id
               WHERE c.name=? AND u.slug=? AND us.has_unit=1
               ORDER BY u.age_id DESC""",
            (civ, slug),
        ).fetchall()
        if not rows:
            raise ValueError(f"No unit {civ}/{slug} in {db_path}")
        return SR.prepare_combat_unit(dict(rows[0]))
    finally:
        db.close()


def extract_sim_results(civ1: str, slug1: str, civ2: str, slug2: str,
                        fixed_count: int = 30, sample_hz: float = 2.0,
                        max_seconds: float = 180.0, seed: int = 1234) -> MatchResult:
    """Run the position-based engine and sample a survivor/HP timeline."""
    import random
    random.seed(seed)

    u1 = load_unit(civ1, slug1)
    u2 = load_unit(civ2, slug2)
    count1, count2 = SR._calc_counts(u1, u2, 0, fixed_count, None, None)

    sim = SR.BattleSimulation()
    sim.setup_team(1, u1, count1)
    sim.setup_team(2, u2, count2)

    DT = SR.DT
    max_ticks = int(max_seconds / DT)
    sample_every = max(1, int((1.0 / sample_hz) / DT))  # ticks between samples

    def snap(t):
        return {
            "t": round(t, 2),
            "s1": sim.alive_count(1),
            "s2": sim.alive_count(2),
            "hp1": round(sim.total_hp(1) / max(1.0, sim.total_max_hp(1)), 3),
            "hp2": round(sim.total_hp(2) / max(1.0, sim.total_max_hp(2)), 3),
        }

    timeline = [{"t": 0.0, "s1": count1, "s2": count2, "hp1": 1.0, "hp2": 1.0}]
    elapsed = 0
    for tick in range(max_ticks):
        sim.step(DT)
        elapsed = tick + 1
        t = elapsed * DT
        if elapsed % sample_every == 0:
            timeline.append(snap(t))
        if sim.winner is not None:
            timeline.append(snap(t))
            break
    else:
        # hit time cap -> decide by HP (mirror engine's rule)
        hp1 = sim.total_hp(1) / max(1.0, sim.total_max_hp(1))
        hp2 = sim.total_hp(2) / max(1.0, sim.total_max_hp(2))
        sim.winner = 1 if hp1 > hp2 else (2 if hp2 > hp1 else 0)
        sim.end_reason = "time_cap"

    return MatchResult(
        civ1=civ1, slug1=slug1, civ2=civ2, slug2=slug2,
        start1=count1, start2=count2,
        winner=sim.winner if sim.winner is not None else 0,
        survivors1=sim.alive_count(1), survivors2=sim.alive_count(2),
        hp1_pct=round(sim.total_hp(1) / max(1.0, sim.total_max_hp(1)), 3),
        hp2_pct=round(sim.total_hp(2) / max(1.0, sim.total_max_hp(2)), 3),
        duration_s=round(elapsed * DT, 2),
        end_reason=sim.end_reason or "eliminated",
        engine="position_based",
        timeline=timeline,
    )


def extract_video_results(*args, **kwargs):
    """STUB — real-game extraction from recorded footage.

    Plan when footage exists:
      1. The scenario displays live survivor counts via count_units_into_variable
         -> display_instructions in a known screen region.
      2. Sample frames (e.g. 2 fps), crop the count region(s), and read the digits
         with either:
           - pytesseract (needs Tesseract-OCR binary installed), or
           - fixed-font digit template matching with Pillow (no extra binary;
             robust because the in-game font is constant).
      3. Also OCR the post-game stats screen (Military Units Killed) as a cross-check.
      4. Return the same MatchResult shape so the renderer is source-agnostic.
    """
    raise NotImplementedError(
        "Video/OCR results extraction is not wired yet (blocked on game footage "
        "+ OCR engine). Use extract_sim_results() for now.")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    r = extract_sim_results("Wu", "elite_fire_archer_wu", "Wu", "jian_swordsman_wu")
    print(f"{r.start1} {r.slug1}  vs  {r.start2} {r.slug2}")
    print(f"winner=team{r.winner}  survivors {r.survivors1}-{r.survivors2}  "
          f"hp {r.hp1_pct:.0%}/{r.hp2_pct:.0%}  in {r.duration_s}s  ({r.end_reason})")
    print(f"timeline samples: {len(r.timeline)}")
    for row in r.timeline[::max(1, len(r.timeline) // 12)]:
        print(f"  t={row['t']:5.1f}s  s1={row['s1']:2d} s2={row['s2']:2d}  "
              f"hp1={row['hp1']:.0%} hp2={row['hp2']:.0%}")

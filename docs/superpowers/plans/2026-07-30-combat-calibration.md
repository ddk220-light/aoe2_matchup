# Combat Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fit the JS battle engine's combat dynamics to real AoE2 fights recorded at ~60 Hz, by making the engine emit the recordings' own event shapes and scoring both through one shared extractor.

**Architecture:** Phase 1 (Tasks 1–5) builds the rig: ingest a drop → truth cards → engine event recorder → 20-seed sim runs → scorer, ending with a BASELINE scoreboard. Phase 2 (Tasks 6–11) fits the engine one mechanism at a time, re-scoring both spike tapes after each change.

**Tech Stack:** Python 3 (stdlib + sqlite3), Node 20.10.0 (ESM, `node:test`). No new dependencies.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-30-combat-calibration-design.md`.
- **One extractor.** `aoe2x/calibration/extract.py` computes every metric and consumes tape-format events regardless of origin. The engine emits the tape's shapes so both pass through identical code. Never write a second metric implementation for the sim side.
- **Engine edits** are confined to `apps/website/static/js/engine/*.js` and require `node --test tests/js/engine/` plus `node tools/simjs/parity_check.mjs`. Parity must stay green through Task 3; it breaks deliberately in Phase 2 and is re-captured once, in Task 11.
- **Never write into `tools/simjs/golden/`** except Task 11.
- **Never modify** `aoe2x/sim/simulation_real.py` or `aoe2x/dbgen/config_combat.py` (byte-hashed into a cache key).
- **Counts come from each tape's `meta.json`**, never from a count rule — three incompatible rules exist in this repo.
- Seeds are `1..N`, never `0..N-1` (`rng.js` does `(seed >>> 0) || 1`, so seed 0 aliases seed 1).
- Large data lives outside the repo at `D:/AI/aoe2_golden/`; only truth cards, the manifest, and run outputs are committed.
- Branch `improved-simulation`. Commit after every task. Do not push. Never `git add -A` — the tree has unrelated pre-existing modifications under `graphics/`, `lab/sheep_probe.py`, `data/golden/derived_data.db`.
- Spike zip: `C:/Users/ddk22/Downloads/aoe2_golden_spike_2026-07-29.zip`.

## Verified metric definitions

These were validated against the drop's own `GROUND_TRUTH.md`. **7 of 8 reproduce exactly** — use them verbatim.

- **Swing grouping:** damage events grouped by `attacker`; consecutive events within `SWING_EPS = 0.15 s` are ONE swing (trample hits several victims in one swing). Verified insensitive to ε over 0.05–0.30; reproduces the elephant's published swing count of 53 exactly.
- **`swing_interval_median`:** per unit, the median of its consecutive-swing gaps; then the median over units.
- **`swing_interval_fastest`:** the minimum over **all** gaps from all units (NOT the min of per-unit medians).
- **`churn`:** median − fastest.
- **`projectiles_fired`:** count of **distinct `id` values** in `missiles.jsonl` for that owner. The missile stream is a ~60 Hz position tracker, so raw row counts are ~18× too high.
- **`effective_accuracy`:** landed hits ÷ distinct missile ids.

Expected values (assert these in Task 2):

| fight | side | median | fastest | fired | hits | accuracy |
|---|---|---|---|---|---|---|
| steppe vs arbalester | Arbalester | 1.974 | 1.582 | 381 | 350 | 91.9% |
| steppe vs arbalester | Elite Steppe Lancer | 2.284 | 2.006 | — | 68 | — |
| HC vs elephant | Hand Cannoneer | 4.000 | 3.510 | 380 | 368 | 96.8% |
| HC vs elephant | Elite Battle Elephant | **6.246** | 2.016 | — | 68 | — |

**Known definitional difference:** the elephant's median is 6.246 under our definition vs 5.672 published. The drop's extractor evidently filters long idle gaps (that unit's gaps include 36.6 s, 25.6 s, 23.0 s alongside true ~2 s reloads). Ours is the authority because it is applied identically to tape and sim; the difference is recorded, not chased. Assert 6.246.

---

## Task 1: Ingest + manifest + truth-card storage

**Files:**
- Create: `aoe2x/calibration/__init__.py`, `aoe2x/calibration/ingest.py`
- Test: `tests/test_calibration_ingest.py`
- Output: `D:/AI/aoe2_golden/tapes/<tag>/`, `data/calibration/manifest.json`

**Interfaces:**
- Produces: `manifest.json` = `{"fights": [{tag, zip_sha256, drop, side1: {owner, unit_name, civ, slug, count}, side2: {...}, duration_s, stream_hz, ingested_utc}]}`. Tasks 2–5 read it.
- Exposes `ingest_zip(zip_path) -> list[str]` (tags ingested) and `resolve_civ(unit_name, matchups) -> (civ, slug)`.

**Civ resolution:** tapes name units, not civs. Match `meta.json`'s composition unit names against `matchups_91.json` `label1`/`label2` to get `(civ, slug)`. Then cross-validate against `data/golden/aoe2_reference.db` `ref_units` at `age='Imperial'`: the resolved unit's `final_hp` must equal the tape's observed spawn HP (the max `hp` seen for that owner at the earliest `t` in `units.jsonl`). **Hard-fail with both values printed on mismatch** — never guess. Known-good: Japanese Hand Cannoneer (40 hp), Burmese Elite Battle Elephant (320 hp), Chinese Arbalester, Cumans Elite Steppe Lancer.

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
ZIP = Path("C:/Users/ddk22/Downloads/aoe2_golden_spike_2026-07-29.zip")
MANIFEST = REPO / "data" / "calibration" / "manifest.json"

def test_ingest_spike_zip():
    from aoe2x.calibration.ingest import ingest_zip
    tags = ingest_zip(str(ZIP))
    assert set(tags) == {"hand_cannoneer__vs__elite_elephant", "elite_steppe__vs__arbalester"}
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    fights = {f["tag"]: f for f in m["fights"]}
    hc = fights["hand_cannoneer__vs__elite_elephant"]
    sides = {s["unit_name"]: s for s in (hc["side1"], hc["side2"])}
    assert sides["Hand Cannoneer"]["civ"] == "Japanese"
    assert sides["Hand Cannoneer"]["count"] == 21
    assert sides["Elite Battle Elephant"]["civ"] == "Burmese"
    assert sides["Elite Battle Elephant"]["count"] == 12
    assert abs(hc["duration_s"] - 152.31) < 0.01

def test_ingest_is_idempotent():
    from aoe2x.calibration.ingest import ingest_zip
    before = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ingest_zip(str(ZIP))
    after = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert len(before["fights"]) == len(after["fights"])

def test_hp_cross_validation_rejects_wrong_civ():
    from aoe2x.calibration.ingest import validate_unit
    validate_unit("Burmese", "elite_elephant", observed_hp=320.0)   # must not raise
    try:
        validate_unit("Bengalis", "elite_elephant", observed_hp=999.0)
        assert False, "expected a hard failure on HP mismatch"
    except Exception:
        pass
```

- [ ] **Step 2: Run test to verify it fails** — `python -m pytest tests/test_calibration_ingest.py -v` → FAIL (no module).

- [ ] **Step 3: Implement `ingest.py`.** Extract the zip to a temp dir, copy `decoded/*` to `D:/AI/aoe2_golden/tapes/<tag>/` (create parents), copy the raw zip to `D:/AI/aoe2_golden/drops/`, and copy `matchups_91.json` next to the manifest as `data/calibration/matchups.json` (it is the civ authority and belongs in the repo). Derive each fight's tag from the decoded filenames. Read `meta.json` for composition, counts, duration, `stream_hz`. Resolve civs and cross-validate as described. Append to `manifest.json`, keyed by `tag`, skipping tags already present with the same `zip_sha256`.

- [ ] **Step 4: Run tests to verify they pass** — all 3 pass.

- [ ] **Step 5: Commit**

```bash
git add aoe2x/calibration/__init__.py aoe2x/calibration/ingest.py tests/test_calibration_ingest.py data/calibration/manifest.json data/calibration/matchups.json
git commit -m "calibration: ingest recorded-fight drops, resolve civs, build manifest"
```

---

## Task 2: The shared truth-card extractor

**Files:**
- Create: `aoe2x/calibration/extract.py`
- Test: `tests/test_calibration_extract.py`
- Output: `data/calibration/truth/<tag>.json`

**Interfaces:**
- Consumes: `manifest.json`; tape streams from `D:/AI/aoe2_golden/tapes/<tag>/`.
- Produces: `extract_card(damage_events, missile_events, composition) -> dict` and a CLI writing `data/calibration/truth/<tag>.json`. **This function is called on sim events too (Task 4) — it must not import or assume anything tape-specific.**

Card shape:

```json
{"tag": "...", "duration_s": 152.31,
 "sides": {"side2": {"unit_name": "Hand Cannoneer", "civ": "Japanese", "slug": "hand_cannoneer",
                     "start_count": 21, "survivors": 0, "hp_remaining": 0,
                     "hits_landed": 368, "damage_dealt": 2912.0, "kills": 7,
                     "swing_interval_median": 4.000, "swing_interval_fastest": 3.510, "churn": 0.490,
                     "swing_count": 380, "projectiles_fired": 380, "effective_accuracy": 0.968,
                     "damage_histogram": {"8": 360, "4": 8},
                     "trample_multi_rate": 0.0, "trample_victims_mean": 0.0, "trample_victims_max": 0,
                     "first_blood": 0.98, "n_events": {"swings": 380, "gaps": 359, "projectiles": 380}}}}
```

Use the **Verified metric definitions** section above verbatim. `SWING_EPS = 0.15`. Trample stats: a swing with >1 victim is a multi-hit; `splash_fraction` is the modal non-maximal damage ÷ modal maximal damage within multi-victim swings.

- [ ] **Step 1: Write the failing test** — assert every value in the expected-values table above (tolerance 0.005 for intervals, 0.001 for accuracy, exact for counts), plus:

```python
def test_extractor_is_source_agnostic():
    """The same function must accept synthetic sim-shaped events."""
    from aoe2x.calibration.extract import extract_card
    dmg = [{"t": 1.0, "attacker": 1, "victim": 9, "damage": 5.0, "victim_hp_after": 15.0,
            "kill": False, "attacker_owner": 2, "victim_owner": 3},
           {"t": 3.0, "attacker": 1, "victim": 9, "damage": 5.0, "victim_hp_after": 10.0,
            "kill": False, "attacker_owner": 2, "victim_owner": 3}]
    card = extract_card(dmg, [], {"side2": {"unit_name": "X", "count": 1},
                                  "side3": {"unit_name": "Y", "count": 1}})
    assert card["sides"]["side2"]["swing_interval_median"] == 2.0
    assert card["sides"]["side2"]["hits_landed"] == 2

def test_trample_multi_victim_detection():
    from aoe2x.calibration.extract import extract_card
    dmg = [{"t": 5.0, "attacker": 1, "victim": 9, "damage": 18.0, "victim_hp_after": 1.0,
            "kill": False, "attacker_owner": 3, "victim_owner": 2},
           {"t": 5.02, "attacker": 1, "victim": 10, "damage": 4.5, "victim_hp_after": 1.0,
            "kill": False, "attacker_owner": 3, "victim_owner": 2}]
    card = extract_card(dmg, [], {"side3": {"unit_name": "E", "count": 1},
                                  "side2": {"unit_name": "H", "count": 2}})
    s = card["sides"]["side3"]
    assert s["swing_count"] == 1, "same attacker within SWING_EPS is ONE swing"
    assert s["trample_multi_rate"] == 1.0
    assert s["trample_victims_max"] == 2
```

- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement `extract.py`** per the verified definitions.
- [ ] **Step 4: Run to verify it passes.** If any tape assertion misses, the definition is wrong — fix the extractor, never the expected value. The one exception is the elephant median: 6.246 is correct for our definition (the published 5.672 uses idle-gap filtering we deliberately do not copy).
- [ ] **Step 5: Generate both cards** — `python -m aoe2x.calibration.extract --all` writes `data/calibration/truth/*.json`.
- [ ] **Step 6: Commit** (`aoe2x/calibration/extract.py`, the test, `data/calibration/truth/*.json`).

---

## Task 3: Engine event recorder (parity MUST stay green)

**Files:**
- Modify: `apps/website/static/js/engine/sim.js`, `apps/website/static/js/engine/battle_unit.js`
- Test: `tests/js/engine/event_log.test.mjs`

**Interfaces:**
- Produces: `sim.eventLog` — `null` by default. When set to `{damage: [], missiles: []}` the engine appends tape-shaped records. Task 4 consumes it.

Hook points, both beside existing `combatStats` hooks so the precedent is followed:
- `takeDamage(amount, attacker)` at [battle_unit.js:1171](apps/website/static/js/engine/battle_unit.js:1171) — the single funnel for ALL damage (direct, splash, trample, charge, bleed). Append after the HP is applied: `{t: sim.battleTime, attacker: attacker.id, victim: this.id, damage: <applied>, victim_hp_after: this.currentHp, kill: <died this call>, attacker_owner: attacker.team, victim_owner: this.team}`.
- Projectile spawn (`fireProjectile`, and the extra/charge projectile paths) — `{t, id: <unique>, fired_from: this.id, owner: this.team}`. Every projectile must get a distinct `id`; the extractor counts distinct ids.

**This must not change a single fight.** `stateHash()` ([sim.js:232](apps/website/static/js/engine/sim.js:232)) hashes only `x, y, currentHp, state` per unit plus four sim values — the log is invisible to it, exactly as `combatStats` is.

- [ ] **Step 1: Write the failing test**

```javascript
import { test } from "node:test";
import assert from "node:assert/strict";
import { createSimulation } from "../../../apps/website/static/js/engine/index.js";

const ARCHER = { hp: 40, attack: 6, attack_range: 5, attack_speed: 0.5, attack_delay: 0.2,
    movement_speed: 0.96, melee_armor: 0, pierce_armor: 0, outline_size: 0.2, accuracy: 100,
    unit_name: "A", cost_food: 0, cost_wood: 25, cost_gold: 45, hp_regen: 0 };
const MELEE = { hp: 100, attack: 10, attack_range: 0, attack_speed: 0.5, attack_delay: 0,
    movement_speed: 1.2, melee_armor: 0, pierce_armor: 0, outline_size: 0.3, accuracy: 100,
    unit_name: "M", cost_food: 60, cost_wood: 0, cost_gold: 20, hp_regen: 0 };

function run(seed, withLog) {
    const sim = createSimulation({ teams: [
        { combatDict: ARCHER, slug: "a", civ: "Britons", count: 5 },
        { combatDict: MELEE, slug: "m", civ: "Franks", count: 5 }], seed });
    if (withLog) sim.eventLog = { damage: [], missiles: [] };
    const hashes = [];
    let ticks = 0;
    while (sim.winner === null && ticks < 60 * 120) {
        sim.step(1 / 60); ticks++;
        if (ticks % 60 === 0) hashes.push(sim.stateHash());
    }
    return { hashes, log: sim.eventLog, winner: sim.winner, time: sim.battleTime };
}

test("recording does not perturb the simulation", () => {
    const off = run(1, false), on = run(1, true);
    assert.deepEqual(on.hashes, off.hashes, "stateHash stream must be identical");
    assert.equal(on.winner, off.winner);
    assert.equal(on.time, off.time);
});

test("eventLog defaults to null and costs nothing", () => {
    const r = run(2, false);
    assert.equal(r.log, null);
});

test("damage events carry the tape's shape", () => {
    const r = run(3, true);
    assert.ok(r.log.damage.length > 0);
    for (const e of r.log.damage.slice(0, 20)) {
        for (const k of ["t", "attacker", "victim", "damage", "victim_hp_after",
                         "kill", "attacker_owner", "victim_owner"]) {
            assert.ok(e[k] !== undefined, `missing ${k}`);
        }
        assert.ok(e.attacker_owner !== e.victim_owner, "damage must cross teams");
    }
    const kills = r.log.damage.filter((e) => e.kill).length;
    assert.ok(kills > 0, "kill flags must be set");
});

test("every projectile gets a distinct id", () => {
    const r = run(4, true);
    assert.ok(r.log.missiles.length > 0);
    const ids = new Set(r.log.missiles.map((m) => m.id));
    assert.equal(ids.size, r.log.missiles.length, "projectile ids must be unique");
});
```

- [ ] **Step 2: Run to verify it fails** — `node --test tests/js/engine/event_log.test.mjs`.
- [ ] **Step 3: Implement.** Initialise `this.eventLog = null` in the `Simulation` constructor near `combatStats`. Add the two hooks. Give each projectile a monotonically increasing id from a sim-level counter — **the counter must live on `sim.eventLog`, not on `sim`**, so it cannot exist when recording is off and therefore cannot affect determinism.
- [ ] **Step 4: Run to verify it passes** — all 4 tests.
- [ ] **Step 5: PARITY GATE** — `node tools/simjs/parity_check.mjs` must exit 0, and `node --test tests/js/engine/` must be green. A parity failure here means recording leaked into the physics; fix it, do not re-capture.
- [ ] **Step 6: Commit.**

---

## Task 4: Calibration runner

**Files:**
- Create: `tools/simjs/calib_runner.mjs`
- Test: `tests/js/calib_runner.test.mjs`

**Interfaces:**
- Consumes: `data/calibration/manifest.json`, `sim.eventLog`, `buildFight`-style team construction.
- Produces: `D:/AI/aoe2_golden/simruns/<tag>/seed-<n>.json` = `{tag, seed, duration_s, winner, damage: [...], missiles: [...], sides: {...}}` in tape event shape, plus end-state survivors/HP per side.

Combat dicts come from `data/golden/aoe2_reference.db` via a small Python helper reusing `build_combat_dict_from_ref` — generalise `tools/simjs/dump_tape_dicts.py` into `tools/simjs/dump_calib_dicts.py` reading the manifest instead of the old corpus, writing `data/calibration/combat_dicts.json`. Counts come from the manifest (i.e. from each tape's `meta.json`). **20 seeds, 1..20.** Cap at 600 s.

- [ ] **Step 1: Write the failing test** — assert `runCalibFight` returns tape-shaped `damage`/`missiles` arrays, that two runs at the same seed are identical, and that seed 20 and seed 1 differ.
- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement** `dump_calib_dicts.py` and `calib_runner.mjs`.
- [ ] **Step 4: Run to verify it passes**, then run for real: `node tools/simjs/calib_runner.mjs --seeds 20` over both manifest fights.
- [ ] **Step 5: Commit** (scripts + `data/calibration/combat_dicts.json`; NOT the sim run outputs, which live outside the repo).

---

## Task 5: Scorer + BASELINE scoreboard

**Files:**
- Create: `aoe2x/calibration/score.py`
- Test: `tests/test_calibration_score.py`
- Output: `data/calibration/runs/<stamp>-baseline.json`, `docs/architecture/calibration-rig.md`

**Interfaces:**
- Consumes: truth cards, sim run files (via `extract_card` — the SAME extractor).
- Produces: `score_fight(tag) -> {metrics: [{name, side, tape, sim_median, sim_p10, sim_p90, delta, verdict}], verdict, rerolls: [...]}`.

Verdicts: **MATCH** (tape inside sim p10–p90, or within tolerance), **MISMATCH**, **INCONCLUSIVE** (tape's own `n` too small: binomial 95% CI on a rate wider than tolerance, or fewer than 5 gaps for an interval). Gated metrics: swing median/fastest/churn, effective accuracy, damage histogram, hits/damage/kills, survivors, hp_remaining, trample stats (when the unit has trample). Reported-only: first blood, duration, distance.

- [ ] **Step 1: Write the failing test** — a synthetic card pair proving MATCH/MISMATCH/INCONCLUSIVE each trigger, and that a metric absent from one side does not crash.
- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement `score.py`.**
- [ ] **Step 4: Run to verify it passes.**
- [ ] **Step 5: Produce the BASELINE** — `python -m aoe2x.calibration.score --all --label baseline`. Record every MISMATCH; this is the fitting backlog's evidence.
- [ ] **Step 6: Write `docs/architecture/calibration-rig.md`** — what the rig is, the four commands to run it end to end, the verified metric definitions, the elephant-median definitional difference, and the BASELINE table.
- [ ] **Step 7: Commit.**

---

## Phase 2 — the fit

Each task: measure → change ONE mechanism → re-score both tapes → keep only if its target metrics move toward tape and no other gated metric regresses. Every task ends with `node --test tests/js/engine/` green. Parity WILL break from Task 6 onward; that is expected and is re-captured once in Task 11.

## Task 6: Crowd churn

**Files:** `apps/website/static/js/engine/battle_unit.js`, `constants.js`, `tests/js/engine/churn.test.mjs`

Tape: elephant churn **+3.654 s** (median 5.672 vs fastest 2.018), steppe lancer **+0.278 s**, hand cannoneer **+0.494 s**. The JS engine has no churn mechanism (`grep -i churn apps/website/static/js/engine/*.js` returns nothing); `simulation_real.py` has one (`CHURN_MAX`, neighbour-scaled) — read it as the reference shape, but do NOT import or copy its fitted constant, which was tuned on different geometry.

- [ ] **Step 1:** Read `simulation_real.py`'s churn implementation and record its shape in the report.
- [ ] **Step 2:** Write a test asserting that with several allies adjacent, a unit's effective swing interval exceeds its nominal reload, and that with no neighbours it equals the nominal reload.
- [ ] **Step 3:** Run to verify it fails.
- [ ] **Step 4:** Implement neighbour-scaled churn with the constant in `constants.js`.
- [ ] **Step 5:** Fit the constant: for candidate values, run `calib_runner` + `score` and record elephant/lancer/HC churn. **One constant must satisfy all three** — that is the test of the mechanism's shape. Report the sweep table.
- [ ] **Step 6:** Re-score both tapes; confirm no gated metric regresses.
- [ ] **Step 7:** Commit with the sweep table in the message.

## Task 7: Effective accuracy against large targets

**Files:** `apps/website/static/js/engine/battle_unit.js`, `tests/js/engine/accuracy.test.mjs`

Tape: Hand Cannoneer **96.8%** effective (368/380) vs 65% paper, against Elite Battle Elephants (large hitbox). Arbalester **91.9%** (350/381) vs 90% paper, against Steppe Lancers. So the effect scales with target size — a blanket accuracy inflation is wrong and the arbalester row is the guard against it.

The engine already models misses that graze (`missDamagePercent`, default 0.5×), confirmed by the tape's HC damage histogram (`8×360, 4×8` — full hits plus half-damage grazes).

- [ ] **Step 1:** Read the current miss/graze path ([battle_unit.js:726-790](apps/website/static/js/engine/battle_unit.js:726)) and record how a missed shot currently resolves.
- [ ] **Step 2:** Write a test: a miss against a large-radius target lands more often than against a small-radius target, holding paper accuracy fixed.
- [ ] **Step 3:** Run to verify it fails.
- [ ] **Step 4:** Implement hit-capture as a function of target radius.
- [ ] **Step 5:** Fit against BOTH tapes; HC must approach 96.8% while the arbalester stays near 91.9%.
- [ ] **Step 6:** Re-score; commit with the measured before/after.

## Task 8: Trample audit and fit

**Files:** `apps/website/static/js/engine/battle_unit.js` and/or `aoe2x/dbgen/config_combat.py`, `tests/js/engine/trample.test.mjs`

Tape: **7 of 53** elephant swings hit >1 victim (13%), mean **3.14** victims, max **7**, splash fraction **0.25**, damage support `18×32, 17.5×6, 13×3, 8.5×1, 4.5×15, 4×11`.

- [ ] **Step 1:** Query `ref_units` for Burmese `elite_elephant`'s `trample_percent`, `trample_radius`, `trample_flat_damage` and record them. If they are zero, the mechanism is configured off and that alone explains the gap.
- [ ] **Step 2:** Write a test pinning multi-victim rate and splash fraction for a clustered target group.
- [ ] **Step 3:** Run to verify it fails.
- [ ] **Step 4:** Fit radius/percent. **If the fix belongs in `config_combat.py`, note that it is byte-hashed into `sim_version` — flag it in the report and make the change in one commit.**
- [ ] **Step 5:** Re-score; commit.

## Task 9: Reload-model investigation (report only)

**Files:** report only, unless a defect is proven.

Arbalester's fastest observed interval is **1.582 s**, below its 2.0 s paper reload. Investigate: Thumb Ring, `attack_delay` vs `reloadTime` bookkeeping, frame quantisation, or a genuine model gap. Compare against the engine's own fastest interval from the Task 5 baseline.

- [ ] **Step 1:** Pull Chinese arbalester's `final_reload_time`, `attack_delay`, and Thumb Ring status from `ref_units`.
- [ ] **Step 2:** Compute the engine's fastest interval from the baseline sim runs.
- [ ] **Step 3:** Write the finding into the report. **Change nothing unless a defect is proven**; if one is, write a failing test first and treat it as its own task.
- [ ] **Step 4:** Commit the report note (docs only).

## Task 10: Pursuit fix (revived)

**Files:** `apps/website/static/js/engine/battle_unit.js`, `constants.js`, `tests/js/engine/pursuit.test.mjs`

The design, constants, and verified line-level details are in `docs/superpowers/specs/2026-07-29-target-thrash-design.md` §2–§3 — read it. The HC-vs-elephant tape is the thrash pair: the sim grinds ~340 s where the tape resolves in 152.31 s.

Implement, in this order, each with its own test: (a) express the stuck bar as a rate — `STUCK_PROGRESS_RATE = 30` px/s, which is exactly today's `0.5` per sub-step at dt=1/60 (`30 * (1/60) === 0.5` in IEEE-754), so this alone must not change any fight; (b) the exemption `stalled && !(pursuing && receding)` with `PURSUIT_FRACTION = 0.35`, `RECEDE_EPS = 0.05`, snapshotting the pre-avoidance intent vector before the avoidance blend overwrites `dx`/`dy`, and measuring **post-clamp** displacement; (c) re-stamp `lastDistToTarget` when its baseline is older than one sub-step; (d) a stalled chaser takes an enemy already within reach, respecting `minAttackRange`.

- [ ] **Steps:** test-first for each of (a)–(d); after (a), parity must still be green; after (b) it will break. Re-score both tapes at the end — the HC-vs-elephant duration should fall sharply toward 152 s.
- [ ] Commit each of (a)–(d) separately.

## Task 11: Golden re-capture, final scoreboard, docs

**Files:** `tools/simjs/capture_golden.mjs` (create), `tools/simjs/golden/panel.json` + `panel.meta.json`, `docs/architecture/calibration-rig.md`, the spec.

`parity_capture.mjs` is dead — it `vm`-evals `simulate.js`, now an ESM shell with no copy of the sim. Build `capture_golden.mjs` driving `runFight` from `headless.mjs`, with `--verify` (compare against `panel.json`) and `--write --reason "..."` (requires a reason, recorded in `panel.meta.json`).

- [ ] **Step 1:** Build the tool; `--verify` will FAIL now (behaviour changed) — that is expected.
- [ ] **Step 2:** Re-capture with a reason naming the calibration changes.
- [ ] **Step 3:** `node tools/simjs/parity_check.mjs` → exit 0 again.
- [ ] **Step 4:** Final scoreboard: `python -m aoe2x.calibration.score --all --label after-fit`; append BEFORE/AFTER to `docs/architecture/calibration-rig.md` and a Results section to the spec, including the reroll list.
- [ ] **Step 5:** `python -m pytest` and `node --test tests/js/engine/` green.
- [ ] **Step 6:** Commit.

---

## Self-Review

**Spec coverage:** §3.1 storage → Task 1. §3.2 ingest → Task 1. §3.3 extractor → Task 2. §3.4 recorder → Task 3. §3.5 runner → Task 4. §3.6 scorer → Task 5. §4 fit backlog items 1–5 → Tasks 6, 7, 8, 9, 10. §5 auto-pickup → controller-side monitor (not a task). §6 reuse/retire → Tasks 4 (dict dumper) and 11 (capture tool). §7 risks → Task 3 (recorder perturbation), Task 2 (trample attribution via SWING_EPS), Task 1 (civ resolution). §8 success criteria → Task 11.

**Type consistency:** `extract_card(damage, missiles, composition)` is defined in Task 2 and called by Tasks 4 and 5. Manifest fields written in Task 1 are read in Tasks 2, 4, 5. `sim.eventLog = {damage, missiles}` from Task 3 is consumed by Task 4. Truth-card keys in Task 2's shape are the metric names Task 5 scores.

**Ordering:** Tasks 1→2→3→4→5 are strictly sequential (each consumes the last). Task 3 must land before Task 4. Phase 2 tasks each depend on Task 5's scorer. Task 11 must be last.

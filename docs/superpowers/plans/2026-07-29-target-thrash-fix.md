# Target-Thrash Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop chasing units in the shared JS engine from blacklisting the target they are walking straight at every 0.8 s, and prove the change against real recorded in-game fights.

**Architecture:** Two halves, strictly ordered. **Half 1 (Tasks 1–6)** builds a validation rig that replays the 38-row tape corpus (real filmed AoE2 fights) through the JS engine and records results into the existing `data/validation/tape_runs.db`, producing a BEFORE score with the engine untouched. **Half 2 (Tasks 7–13)** changes the engine: first a provably bit-identical refactor (parity must stay green), then the behavioral fix (parity must break, then be re-captured), then AFTER scoring.

**Tech Stack:** Node 20.10.0 (ESM, `node:test`), Python 3 / PyPy (stdlib + sqlite3 only — no new dependencies, there is no `node_modules` in this repo), SQLite.

## Global Constraints

- **Engine files are `apps/website/static/js/engine/*.js` only.** Any edit there requires `node tools/simjs/parity_check.mjs` and `node --test tests/js/engine/`. Per CLAUDE.md sync rule 1 a deliberate behavior change must fail parity and then be answered by a re-capture with the reason recorded.
- **Never write to `tools/simjs/golden/`** except in Task 12 (the deliberate re-capture). It is the write-once parity baseline.
- **Never modify `aoe2x/sim/simulation_real.py` or `aoe2x/dbgen/config_combat.py`** — they are byte-hashed into `sim_version`; even a comment stales every matchup row.
- **Never modify `tools/simjs/headless.mjs`'s returned `final` object.** `parity_check.mjs:144` compares `JSON.stringify({snapshots, final})` against the golden; one extra key fails the gate with a bogus "divergence".
- **Seeds are `1..5`, never `0..4`.** `rng.js:5` does `(seed >>> 0) || 1`, so `makeRng(0)` and `makeRng(1)` are the same stream — `range(5)` would silently double-count a seed.
- **JS army counts are literal integers read from a plan file.** The JS side does zero cost arithmetic. Three incompatible count rules exist (tape rule, Battle-Sim resources rule, Battle-Sim pop rule) and no Battle-Sim count matches any tape row.
- **Constants:** `STUCK_PROGRESS_RATE = 30` (px/s), `PURSUIT_FRACTION = 0.35`, `RECEDE_EPS = 0.05`. Exact values, from the spec.
- **Commit after every task.** Branch is `improved-simulation`. Do not push. Do not touch `main` or `staging`.
- Spec: `docs/superpowers/specs/2026-07-29-target-thrash-design.md`.

---

## File Structure

**Create:**

| file | responsibility |
|---|---|
| `tools/simjs/dump_tape_dicts.py` | Export corpus combat dicts + the per-row army-count plan. The single count authority (imports `tape_rig`). |
| `tools/simjs/tape_runner.mjs` | Drive the JS engine over the plan; emit one JSON record per fight. No SQLite, no cost math. |
| `aoe2x/validation/tape_rig_js.py` | Orchestrate: build plan → spawn runner → write `tape_runs`/`tape_battles` rows. |
| `aoe2x/validation/tape_margins.json` | Margin ground truth as a committed fixture, with provenance. |
| `aoe2x/validation/margin_score.py` | Score any `run_tag` in the DB against the margin fixture. Engine-agnostic. |
| `tools/simjs/capture_golden.mjs` | Re-capture the golden panel from `engine/` (replaces the broken `parity_capture.mjs` path). |
| `tests/js/engine/pursuit.test.mjs` | Unit tests for the pursuit predicate. |

**Modify:** `apps/website/static/js/engine/constants.js` (3 constants), `apps/website/static/js/engine/battle_unit.js` (`moveTowardTarget`, constructor fields), `aoe2x/validation/report.py` (`cmd_list`, `cmd_diff` guard), `tools/simjs/golden/panel.json` + `panel.meta.json` (Task 12 only), `docs/architecture/runbooks.md`.

---

## Task 1: Corpus dicts + count plan

**Files:**
- Create: `tools/simjs/dump_tape_dicts.py`
- Output: `data/validation/tape_combat_dicts.json`, `data/validation/tape_plan.json`

**Interfaces:**
- Consumes: `aoe2x.validation.tape_rig.weighted_cost`, `.arena_counts`, `.load_unit`; `aoe2x.sim.combat_unit_loader.build_combat_dict_from_ref`.
- Produces: `tape_plan.json` = `{"rows": [ {plan_id, subject_civ, subject_slug, opp_civ, opp_slug, tape_outcome, counts: {tape: [n1,n2], equal_resource: [n1,n2], equal_count: [n1,n2]}, cost: {my_food,my_wood,my_gold,opp_food,opp_wood,opp_gold}} ]}`; `tape_combat_dicts.json` = `{"<Civ>|<slug>": <combat dict>}`. Task 2 and Task 3 both read these.

- [ ] **Step 1: Write the failing test**

Create `tests/test_tape_plan.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLAN = REPO / "data" / "validation" / "tape_plan.json"
DICTS = REPO / "data" / "validation" / "tape_combat_dicts.json"


def test_dump_tape_dicts_produces_plan_and_dicts():
    subprocess.run([sys.executable, "tools/simjs/dump_tape_dicts.py"],
                   cwd=str(REPO), check=True, capture_output=True)
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    dicts = json.loads(DICTS.read_text(encoding="utf-8"))

    assert len(plan["rows"]) == 38
    # every unit referenced by the plan has a combat dict
    for r in plan["rows"]:
        assert f'{r["subject_civ"]}|{r["subject_slug"]}' in dicts
        assert f'{r["opp_civ"]}|{r["opp_slug"]}' in dicts
    # the recorder's own cost rule must reproduce the recorded counts exactly
    for r in plan["rows"]:
        assert r["counts"]["equal_resource"] == r["counts"]["tape"], r["plan_id"]
    # equal_count is N v N at the subject count
    for r in plan["rows"]:
        n1, _ = r["counts"]["tape"]
        assert r["counts"]["equal_count"] == [n1, n1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tape_plan.py -v`
Expected: FAIL — `dump_tape_dicts.py` does not exist (subprocess raises `CalledProcessError`).

- [ ] **Step 3: Write the implementation**

Create `tools/simjs/dump_tape_dicts.py`:

```python
"""Export the tape corpus for the JS engine: combat dicts + an army-count plan.

Counterpart of dump_combat_dicts.py (which serves the golden parity panel). This
one serves the tape-validation rig, so it writes to data/validation/ and NEVER
to tools/simjs/golden/ -- that directory is the write-once parity baseline.

The plan file exists so the JS runner performs ZERO cost arithmetic. Three
incompatible army-count rules live in this repo (the recorder's weighted-cost
rule here, and two Battle Sim page rules in simulate.js); only this one produces
counts that mean anything against `tape_outcome`. Python owns it because
tape_rig.arena_counts is already proven to reproduce all 38 recorded counts.

    python tools/simjs/dump_tape_dicts.py

Fails loudly on any slug missing from the reference DB.
"""

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aoe2x.sim.combat_unit_loader import build_combat_dict_from_ref  # noqa: E402
from aoe2x.validation.tape_rig import arena_counts, weighted_cost    # noqa: E402

CORPUS = ROOT / "aoe2x" / "validation" / "tape_corpus.json"
REF_DB = ROOT / "data" / "golden" / "aoe2_reference.db"
OUT_DIR = ROOT / "data" / "validation"


def main() -> None:
    rows = json.loads(CORPUS.read_text(encoding="utf-8"))["rows"]
    con = sqlite3.connect(str(REF_DB))
    con.row_factory = sqlite3.Row

    ref_cache = {}

    def ref(civ, slug):
        if (civ, slug) not in ref_cache:
            r = con.execute(
                "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=?"
                " AND age='Imperial'", (civ, slug)).fetchone()
            ref_cache[(civ, slug)] = r
        return ref_cache[(civ, slug)]

    dicts, plan, missing = {}, [], []
    for r in rows:
        r1 = ref(r["subject_civ"], r["subject_slug"])
        r2 = ref(r["opp_civ"], r["opp_slug"])
        if r1 is None:
            missing.append(f'{r["subject_civ"]}/{r["subject_slug"]}')
            continue
        if r2 is None:
            missing.append(f'{r["opp_civ"]}/{r["opp_slug"]}')
            continue

        dicts[f'{r["subject_civ"]}|{r["subject_slug"]}'] = build_combat_dict_from_ref(r1)
        dicts[f'{r["opp_civ"]}|{r["opp_slug"]}'] = build_combat_dict_from_ref(r2)

        n1, n2 = r["n_subject"], r["n_opp"]
        eq_res = list(arena_counts(weighted_cost(r1), weighted_cost(r2)))
        plan.append({
            "plan_id": f'{r["subject_slug"]}__vs__{r["opp_civ"]}_{r["opp_slug"]}',
            "subject_civ": r["subject_civ"], "subject_slug": r["subject_slug"],
            "opp_civ": r["opp_civ"], "opp_slug": r["opp_slug"],
            "tape_outcome": r["tape_outcome"],
            "counts": {"tape": [n1, n2], "equal_resource": eq_res,
                       "equal_count": [n1, n1]},
            "cost": {
                "my_food": float(r1["final_cost_food"] or 0),
                "my_wood": float(r1["final_cost_wood"] or 0),
                "my_gold": float(r1["final_cost_gold"] or 0),
                "opp_food": float(r2["final_cost_food"] or 0),
                "opp_wood": float(r2["final_cost_wood"] or 0),
                "opp_gold": float(r2["final_cost_gold"] or 0),
            },
        })

    if missing:
        sys.exit("NOT IN DB: " + ", ".join(sorted(set(missing))))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "tape_combat_dicts.json").write_text(
        json.dumps(dicts, indent=1, sort_keys=True), encoding="utf-8")
    (OUT_DIR / "tape_plan.json").write_text(
        json.dumps({"rows": plan}, indent=1), encoding="utf-8")
    print(f"wrote {len(dicts)} dicts and {len(plan)} plan rows -> {OUT_DIR}")

    drift = [p["plan_id"] for p in plan
             if p["counts"]["equal_resource"] != p["counts"]["tape"]]
    if drift:
        print(f"WARNING cost-model drift on {len(drift)} rows: {drift[:5]}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tape_plan.py -v`
Expected: PASS. If the `equal_resource == tape` assertion fails, STOP — the cost model has drifted and that is a finding, not a bug to paper over. Report it.

- [ ] **Step 5: Commit**

```bash
git add tools/simjs/dump_tape_dicts.py tests/test_tape_plan.py data/validation/tape_plan.json data/validation/tape_combat_dicts.json
git commit -m "validation: export tape corpus dicts + army-count plan for the JS engine"
```

---

## Task 2: JS tape runner

**Files:**
- Create: `tools/simjs/tape_runner.mjs`
- Test: `tests/js/tape_runner.test.mjs`

**Interfaces:**
- Consumes: `buildFight({dicts, row, seed})` from `tools/simjs/headless.mjs` (row needs `civ1, slug1, n1, civ2, slug2, n2`); `data/validation/tape_plan.json`, `data/validation/tape_combat_dicts.json`.
- Produces: exported `runTapeFight({dicts, plan_row, scale, seed, maxSeconds})` returning
  `{winner, end_reason, game_time_s, team1_hp_pct, team1_survivors, team2_hp_pct, team2_survivors, signed_score, wall_ms}`;
  and a CLI writing a JSON array to stdout. Task 3 consumes the CLI output.

**Key semantics (must match the Python rig so columns are comparable):**
- `team_hp_pct` = `sum(currentHp of LIVING units) / sum(maxHp over the WHOLE starting team)`. The denominator includes corpses (mirrors `simulation_real.total_max_hp`). Sum live `maxHp` at runtime — never `n * dict.hp` — because `maxHp` mutates (aura HP bonus, transform, dismount).
- `signed_score` = `(team1_hp_pct - team2_hp_pct) * 100.0`. The Python rig's `hasattr(SR, "signed_score")` check is False at runtime, so all 14 existing runs used exactly this fallback.
- `winner`: `sim.winner` is `1 | 2 | 0 | null`. `null` means the cap was hit with both alive → adjudicate by HP% (`hp1 > hp2 ? 1 : hp2 > hp1 ? 2 : 0`) and set `end_reason = "time_cap"`. Otherwise `end_reason = "eliminated"`.

- [ ] **Step 1: Write the failing test**

Create `tests/js/tape_runner.test.mjs`:

```javascript
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { runTapeFight } from "../../tools/simjs/tape_runner.mjs";

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const dicts = JSON.parse(readFileSync(path.join(REPO, "data/validation/tape_combat_dicts.json"), "utf8"));
const plan = JSON.parse(readFileSync(path.join(REPO, "data/validation/tape_plan.json"), "utf8")).rows;

test("runTapeFight returns a complete, well-formed record", () => {
    const r = runTapeFight({ dicts, plan_row: plan[0], scale: "tape", seed: 1, maxSeconds: 600 });
    for (const k of ["winner", "end_reason", "game_time_s", "team1_hp_pct",
                     "team1_survivors", "team2_hp_pct", "team2_survivors",
                     "signed_score", "wall_ms"]) {
        assert.ok(r[k] !== undefined, `missing ${k}`);
    }
    assert.ok([0, 1, 2].includes(r.winner), `winner must be adjudicated, got ${r.winner}`);
    assert.ok(["eliminated", "time_cap"].includes(r.end_reason));
    assert.ok(r.team1_hp_pct >= 0 && r.team1_hp_pct <= 1);
    assert.ok(r.team2_hp_pct >= 0 && r.team2_hp_pct <= 1);
});

test("same seed is deterministic; seed 0 aliases seed 1", () => {
    const a = runTapeFight({ dicts, plan_row: plan[0], scale: "tape", seed: 3, maxSeconds: 600 });
    const b = runTapeFight({ dicts, plan_row: plan[0], scale: "tape", seed: 3, maxSeconds: 600 });
    assert.equal(a.game_time_s, b.game_time_s);
    assert.equal(a.signed_score, b.signed_score);

    const s0 = runTapeFight({ dicts, plan_row: plan[0], scale: "tape", seed: 0, maxSeconds: 600 });
    const s1 = runTapeFight({ dicts, plan_row: plan[0], scale: "tape", seed: 1, maxSeconds: 600 });
    assert.equal(s0.game_time_s, s1.game_time_s, "seed 0 must alias seed 1 (rng.js `|| 1`)");
});

test("signed_score is the hp%-difference fallback the Python rig used", () => {
    const r = runTapeFight({ dicts, plan_row: plan[0], scale: "tape", seed: 1, maxSeconds: 600 });
    const expected = (r.team1_hp_pct - r.team2_hp_pct) * 100.0;
    assert.ok(Math.abs(r.signed_score - expected) < 1e-9);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/js/tape_runner.test.mjs`
Expected: FAIL — cannot resolve `tape_runner.mjs`.

- [ ] **Step 3: Write the implementation**

Create `tools/simjs/tape_runner.mjs`:

```javascript
// Replays the tape corpus (real recorded in-game fights) through the EXTRACTED
// engine and emits one record per fight for aoe2x/validation/tape_rig_js.py to
// insert into data/validation/tape_runs.db.
//
//     node tools/simjs/tape_runner.mjs --scales tape,equal_count --seeds 5 > out.json
//
// Deliberate constraints:
//   * imports buildFight (NOT runFight) -- runFight's `final` shape is frozen by
//     parity_check.mjs; this file needs different columns, so it drives its own
//     tick loop over the same spawn path;
//   * ZERO count arithmetic. Counts come from data/validation/tape_plan.json,
//     which Python computed with the recorder's own rule;
//   * seeds are 1..N. makeRng(0) === makeRng(1) (rng.js `(seed>>>0) || 1`), so a
//     0-based range silently double-counts a seed;
//   * integer tick budget, matching headless.mjs and the golden capture.
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { buildFight, STEP, MAX_SECONDS } from "./headless.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../..");

export function loadTapeDicts() {
    return JSON.parse(readFileSync(
        path.join(REPO, "data/validation/tape_combat_dicts.json"), "utf8"));
}

export function loadTapePlan() {
    return JSON.parse(readFileSync(
        path.join(REPO, "data/validation/tape_plan.json"), "utf8")).rows;
}

// hp% denominator is the WHOLE starting team including corpses, mirroring
// simulation_real.total_max_hp. maxHp mutates at runtime (aura/transform/
// dismount), so sum the live objects rather than count * dict.hp.
function hpPct(team) {
    let cur = 0, max = 0;
    for (const u of team) {
        max += u.maxHp;
        if (u.state !== "dead") cur += u.currentHp;
    }
    return max > 0 ? cur / max : 0;
}

export function runTapeFight({ dicts, plan_row, scale, seed, maxSeconds = MAX_SECONDS }) {
    const [n1, n2] = plan_row.counts[scale];
    const row = {
        civ1: plan_row.subject_civ, slug1: plan_row.subject_slug, n1,
        civ2: plan_row.opp_civ, slug2: plan_row.opp_slug, n2,
    };
    const sim = buildFight({ dicts, row, seed });

    const maxTicks = Math.round(maxSeconds * 60);
    const t0 = process.hrtime.bigint();
    let ticks = 0;
    while (sim.winner === null && ticks < maxTicks) {
        sim.step(STEP);
        ticks++;
    }
    const wall_ms = Number(process.hrtime.bigint() - t0) / 1e6;

    const hp1 = hpPct(sim.team1);
    const hp2 = hpPct(sim.team2);
    const alive = (team) => team.filter((u) => u.state !== "dead").length;

    // sim.winner === null means the cap was hit with both sides alive. The JS
    // engine declines to break that tie; adjudicate by HP% so the agreement
    // figure is comparable with simulation_real's cap rule, and keep
    // end_reason='time_cap' as the marker that this row was adjudicated.
    let winner = sim.winner;
    let end_reason = "eliminated";
    if (winner === null) {
        end_reason = "time_cap";
        winner = hp1 > hp2 ? 1 : hp2 > hp1 ? 2 : 0;
    }

    return {
        winner,
        end_reason,
        game_time_s: sim.battleTime,
        team1_hp_pct: hp1,
        team1_survivors: alive(sim.team1),
        team2_hp_pct: hp2,
        team2_survivors: alive(sim.team2),
        signed_score: (hp1 - hp2) * 100.0,
        wall_ms,
    };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
    const argv = process.argv.slice(2);
    const flag = (name, dflt) => {
        const i = argv.indexOf(name);
        return i >= 0 && i + 1 < argv.length ? argv[i + 1] : dflt;
    };
    const scales = flag("--scales", "tape,equal_count").split(",").map((s) => s.trim()).filter(Boolean);
    const nSeeds = Number(flag("--seeds", "5"));
    const maxSeconds = Number(flag("--max-seconds", String(MAX_SECONDS)));

    const dicts = loadTapeDicts();
    const plan = loadTapePlan();
    const out = [];
    for (const pr of plan) {
        for (const scale of scales) {
            if (!pr.counts[scale]) throw new Error(`plan row ${pr.plan_id} has no scale "${scale}"`);
            for (let seed = 1; seed <= nSeeds; seed++) {
                const r = runTapeFight({ dicts, plan_row: pr, scale, seed, maxSeconds });
                out.push({ plan_id: pr.plan_id, scale, seed, n1: pr.counts[scale][0],
                           n2: pr.counts[scale][1], ...r });
            }
        }
    }
    process.stdout.write(JSON.stringify(out));
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test tests/js/tape_runner.test.mjs`
Expected: PASS (3 tests).

Then confirm the engine is untouched: `node tools/simjs/parity_check.mjs`
Expected: exit 0, "PARITY OK".

- [ ] **Step 5: Smoke-run the CLI and check cost**

Run: `node tools/simjs/tape_runner.mjs --scales tape --seeds 1 > /tmp/tape_smoke.json && node -e "const a=require('fs').readFileSync('/tmp/tape_smoke.json','utf8');const j=JSON.parse(a);console.log(j.length,'fights');console.log(j.slice(0,3))"`
Expected: 38 fights, each with a `winner` in {0,1,2}. Whole corpus should be seconds, not minutes.

- [ ] **Step 6: Commit**

```bash
git add tools/simjs/tape_runner.mjs tests/js/tape_runner.test.mjs
git commit -m "validation: JS tape runner over the extracted engine"
```

---

## Task 3: Python recorder → tape_runs.db

**Files:**
- Create: `aoe2x/validation/tape_rig_js.py`
- Test: `tests/test_tape_rig_js.py`

**Interfaces:**
- Consumes: `tape_rig.SCHEMA`, `tape_rig._git`, `tape_rig.make_run_tag`; `tools/simjs/tape_runner.mjs` CLI; `compute_sim_version(file_paths=...)`.
- Produces: one `tape_runs` row + one `tape_battles` row per fight, `engine='js apps/website/static/js/engine'`. Task 5 and Task 13 read these.

**Column conventions (spec §6):**
- `engine` = `'js apps/website/static/js/engine'` — the ONLY column distinguishing engines, so it must be exact and greppable.
- `sim_version` = `compute_sim_version(sorted(glob('apps/website/static/js/engine/*.js')))`. Never reuse the Python `sim_version`.
- `python_impl` is `NOT NULL` and semantically wrong for a JS run → record the Node version (e.g. `'Node v20.10.0'`) and say so in `notes`. Do not rename the column; `report.py:56` reads it.
- `max_seconds` = 600.0.
- `team*_value_lost` = `Σ per-unit cost × (1 − hp/maxHp)`, full cost when dead. The JS engine has no resource bookkeeping, so approximate from survivors and hp%: `value_lost = total_value × (1 − hp_pct)`. Kill-bonus resource gains are omitted; note it. Nothing in `report.py` reads this column.

- [ ] **Step 1: Write the failing test**

Create `tests/test_tape_rig_js.py`:

```python
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_tape_rig_js_records_a_js_run(tmp_path):
    db_path = tmp_path / "t.db"
    subprocess.run(
        [sys.executable, "-m", "aoe2x.validation.tape_rig_js",
         "--label", "unit-test", "--seeds", "1", "--scales", "tape",
         "--out", str(db_path)],
        cwd=str(REPO), check=True, capture_output=True)

    db = sqlite3.connect(str(db_path))
    runs = list(db.execute(
        "SELECT run_tag, engine, python_impl, max_seconds, seeds, n_fights FROM tape_runs"))
    assert len(runs) == 1
    run_tag, engine, impl, max_s, seeds, n_fights = runs[0]
    assert engine == "js apps/website/static/js/engine"
    assert impl.startswith("Node ")
    assert max_s == 600.0
    assert seeds == 1
    assert n_fights == 38

    battles = list(db.execute(
        "SELECT winner, end_reason, sim_outcome, agrees, tape_outcome,"
        " team1_hp_pct, my_count, opp_count FROM tape_battles WHERE run_tag=?",
        (run_tag,)))
    assert len(battles) == 38
    for w, er, so, ag, tape, hp1, n1, n2 in battles:
        assert w in (0, 1, 2)
        assert er in ("eliminated", "time_cap")
        assert so in ("win", "loss")
        assert ag in (0, 1)
        assert so == ("win" if w == 1 else "loss")
        assert 0.0 <= hp1 <= 1.0
        assert n1 >= 1 and n2 >= 1


def test_js_sim_version_differs_from_python():
    from aoe2x.validation.tape_rig_js import js_sim_version
    from aoe2x.sim.sim_version import compute_sim_version
    assert js_sim_version() != compute_sim_version()
    assert len(js_sim_version()) == 16
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tape_rig_js.py -v`
Expected: FAIL — no module `aoe2x.validation.tape_rig_js`.

- [ ] **Step 3: Write the implementation**

Create `aoe2x/validation/tape_rig_js.py`:

```python
"""Tape-validation rig for the JAVASCRIPT engine (apps/website/static/js/engine/).

Sibling of tape_rig.py, which scores simulation_real.py. Same corpus, same
tape_runs.db, same 31-column tape_battles INSERT -- so
`python -m aoe2x.validation.report --diff <py_tag> <js_tag>` works unchanged.

    python tools/simjs/dump_tape_dicts.py          # refresh dicts + plan first
    python -m aoe2x.validation.tape_rig_js --label js-before

Division of labour: Python owns the army counts (tape_rig.arena_counts, the only
rule proven to reproduce all 38 recorded counts) and the SQLite write; Node owns
the fights. Python does the DB write because this repo has no node_modules and no
better-sqlite3 -- a native dependency for ~380 inserts is not worth it.
"""
from __future__ import annotations

import argparse
import glob
import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from aoe2x.sim.sim_version import compute_sim_version                  # noqa: E402
from aoe2x.validation.tape_rig import SCHEMA, _git, make_run_tag       # noqa: E402

ENGINE_GLOB = str(REPO / "apps" / "website" / "static" / "js" / "engine" / "*.js")
ENGINE_LABEL = "js apps/website/static/js/engine"
PLAN = REPO / "data" / "validation" / "tape_plan.json"
OUT_DB = REPO / "data" / "validation" / "tape_runs.db"
RUNNER = REPO / "tools" / "simjs" / "tape_runner.mjs"


def js_sim_version() -> str:
    """Hash the extracted engine's sources -- the JS analogue of sim_version."""
    files = sorted(glob.glob(ENGINE_GLOB))
    if not files:
        sys.exit(f"no engine files matched {ENGINE_GLOB}")
    return compute_sim_version(file_paths=files)


def node_version() -> str:
    out = subprocess.run(["node", "--version"], capture_output=True, check=True)
    return "Node " + out.stdout.decode().strip()


def run_node(scales, seeds, max_seconds):
    proc = subprocess.run(
        ["node", str(RUNNER), "--scales", ",".join(scales),
         "--seeds", str(seeds), "--max-seconds", str(max_seconds)],
        cwd=str(REPO), capture_output=True)
    if proc.returncode != 0:
        sys.exit("tape_runner.mjs failed:\n" + proc.stderr.decode()[-4000:])
    return json.loads(proc.stdout.decode())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", default="js-run")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--max-seconds", type=float, default=600.0)
    ap.add_argument("--scales", default="tape,equal_count")
    ap.add_argument("--out", default=str(OUT_DB))
    ap.add_argument("--notes", default="")
    a = ap.parse_args()

    if not PLAN.exists():
        sys.exit(f"{PLAN} missing -- run: python tools/simjs/dump_tape_dicts.py")

    scales = [s.strip() for s in a.scales.split(",") if s.strip()]
    plan = {r["plan_id"]: r for r in
            json.loads(PLAN.read_text(encoding="utf-8"))["rows"]}

    sim_version = js_sim_version()
    run_tag = make_run_tag(a.label, sim_version)
    impl = node_version()
    notes = (a.notes + " | " if a.notes else "") + (
        "JS engine run. seeds are 1..N (rng.js aliases seed 0 to 1). "
        "winner===null at the cap is adjudicated by HP% with end_reason='time_cap'. "
        "python_impl holds the NODE version. team*_value_lost is approximated from "
        "hp_pct (the JS engine keeps no resource bookkeeping; kill-bonus gains omitted). "
        "At tape counts the spawn column overflows the 600px map and some units start "
        "clamped to the bottom edge -- production-faithful and parity-locked."
    )

    out_path = Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(out_path))
    db.executescript(SCHEMA)
    db.execute(
        "INSERT INTO tape_runs (run_tag, run_label, started_utc, sim_version, engine,"
        " python_impl, git_commit, git_branch, git_dirty, seeds, max_seconds, scales, notes)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (run_tag, a.label, datetime.now(timezone.utc).isoformat(), sim_version,
         ENGINE_LABEL, impl, _git("rev-parse", "HEAD"),
         _git("rev-parse", "--abbrev-ref", "HEAD"),
         1 if _git("status", "--porcelain", default="") else 0,
         a.seeds, a.max_seconds, ",".join(scales), notes))
    db.commit()

    print(f"run_tag      {run_tag}")
    print(f"engine       {ENGINE_LABEL}   sim_version {sim_version[:12]}")
    print(f"runtime      {impl}")
    print(f"corpus       {len(plan)} matchups x {len(scales)} scales x {a.seeds} seeds")
    print()

    t0 = time.perf_counter()
    fights = run_node(scales, a.seeds, a.max_seconds)
    wall_s = time.perf_counter() - t0

    agree = {s: [0, 0] for s in scales}
    wins = {}
    for f in fights:
        pr = plan[f["plan_id"]]
        c = pr["cost"]
        my_value = (c["my_food"] + c["my_wood"] + c["my_gold"]) * f["n1"]
        opp_value = (c["opp_food"] + c["opp_wood"] + c["opp_gold"]) * f["n2"]
        sim_outcome = "win" if f["winner"] == 1 else "loss"
        agrees = (None if pr["tape_outcome"] is None
                  else int(sim_outcome == pr["tape_outcome"]))
        db.execute(
            "INSERT INTO tape_battles (run_tag, my_civ, my_unit_slug, opp_civ,"
            " opp_unit_slug, scale, seed, my_count, opp_count, my_cost_food,"
            " my_cost_wood, my_cost_gold, opp_cost_food, opp_cost_wood,"
            " opp_cost_gold, winner, end_reason, game_time_s, team1_hp_pct,"
            " team1_survivors, team1_value_lost, team2_hp_pct, team2_survivors,"
            " team2_value_lost, team1_start_count, team2_start_count,"
            " signed_score, tape_outcome, sim_outcome, agrees, wall_ms)"
            " VALUES (" + ",".join("?" * 31) + ")",
            (run_tag, pr["subject_civ"], pr["subject_slug"], pr["opp_civ"],
             pr["opp_slug"], f["scale"], f["seed"], f["n1"], f["n2"],
             c["my_food"], c["my_wood"], c["my_gold"],
             c["opp_food"], c["opp_wood"], c["opp_gold"],
             f["winner"], f["end_reason"], round(f["game_time_s"], 3),
             round(f["team1_hp_pct"], 4), f["team1_survivors"],
             round(my_value * (1.0 - f["team1_hp_pct"]), 2),
             round(f["team2_hp_pct"], 4), f["team2_survivors"],
             round(opp_value * (1.0 - f["team2_hp_pct"]), 2),
             f["n1"], f["n2"], round(f["signed_score"], 3),
             pr["tape_outcome"], sim_outcome, agrees, round(f["wall_ms"], 2)))
        key = (f["plan_id"], f["scale"])
        wins[key] = wins.get(key, 0) + (1 if f["winner"] == 1 else 0)
    db.commit()

    for (plan_id, scale), w in sorted(wins.items()):
        pr = plan[plan_id]
        majority = "win" if w * 2 >= a.seeds else "loss"
        ok = (majority == pr["tape_outcome"])
        agree[scale][0] += int(ok)
        agree[scale][1] += 1
        if scale == scales[0]:
            print(f"  {'OK ' if ok else 'XX '}{pr['subject_slug'][:26]:<26}"
                  f" vs {pr['opp_slug'][:28]:<28} tape={pr['tape_outcome']:<4}"
                  f" sim={majority:<4} wr={w}/{a.seeds}")

    db.execute("UPDATE tape_runs SET finished_utc=?, n_matchups=?, n_fights=?, wall_s=?"
               " WHERE run_tag=?",
               (datetime.now(timezone.utc).isoformat(), len(plan), len(fights),
                round(wall_s, 2), run_tag))
    db.commit()

    print()
    for s in scales:
        ok, tot = agree[s]
        print(f"AGREEMENT [{s:<14}] {ok}/{tot}  ({100.0*ok/max(1,tot):.0f}%)")
    print(f"\n{len(fights)} fights in {wall_s:.1f}s"
          f"  ({1000*wall_s/max(1,len(fights)):.0f} ms/fight)")
    print(f"recorded -> {out_path}  (run_tag {run_tag})")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_tape_rig_js.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add aoe2x/validation/tape_rig_js.py tests/test_tape_rig_js.py
git commit -m "validation: record JS-engine tape runs into tape_runs.db"
```

---

## Task 4: report.py — make JS and Python runs distinguishable

**Files:**
- Modify: `aoe2x/validation/report.py:55-67` (`cmd_list`), `:83-114` (`cmd_diff`)
- Test: `tests/test_report_engine_column.py`

**Interfaces:**
- Consumes: `tape_runs` rows written by Task 3.
- Produces: no new API. `--list` prints `engine` and `max_seconds`; `--diff` warns on mismatched engine/cap/seeds.

**Why:** `cmd_list`'s SELECT omits `engine` and `max_seconds`, so a JS run is indistinguishable from a Python one in the listing. And `cmd_diff` prints "mean fight length Xs -> Ys", which is meaningless across a 180 s and a 600 s cap — exactly the comparison this project is about to make.

- [ ] **Step 1: Write the failing test**

Create `tests/test_report_engine_column.py`:

```python
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "data" / "validation" / "tape_runs.db"


def test_list_shows_engine_and_max_seconds():
    out = subprocess.run(
        [sys.executable, "-m", "aoe2x.validation.report", "--list"],
        cwd=str(REPO), check=True, capture_output=True).stdout.decode()
    assert "simulation_real.py" in out, "engine column must be printed"
    assert "max_s=" in out, "max_seconds must be printed"


def test_diff_warns_across_engines_or_caps():
    db = sqlite3.connect(str(DB))
    tags = {}
    for tag, engine, max_s in db.execute(
            "SELECT run_tag, engine, max_seconds FROM tape_runs ORDER BY started_utc"):
        tags.setdefault((engine, max_s), tag)
    pairs = list(tags.values())
    if len(pairs) < 2:
        return  # nothing to compare yet
    out = subprocess.run(
        [sys.executable, "-m", "aoe2x.validation.report", "--diff", pairs[0], pairs[-1]],
        cwd=str(REPO), check=True, capture_output=True).stdout.decode()
    assert "WARNING" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report_engine_column.py -v`
Expected: FAIL on `assert "max_s=" in out`.

- [ ] **Step 3: Edit `cmd_list`**

Replace `report.py:55-67` with:

```python
def cmd_list(db):
    q = ("SELECT run_tag, run_label, started_utc, python_impl, sim_version,"
         " git_branch, git_dirty, seeds, scales, n_fights, wall_s,"
         " engine, max_seconds"
         " FROM tape_runs ORDER BY started_utc")
    rows = list(db.execute(q))
    if not rows:
        print("no runs recorded")
        return
    for r in rows:
        dirty = " *dirty" if r[6] else ""
        print(f"{r[0]}")
        print(f"    {r[2][:19]}  {r[3]}  sv={r[4][:12]}  {r[5]}{dirty}")
        print(f"    engine={r[11]}  max_s={r[12]}")
        print(f"    seeds={r[7]} scales={r[8]} fights={r[9]} wall={r[10]}s")
```

- [ ] **Step 4: Add the diff guard**

Insert at the top of `cmd_diff`, immediately after `def cmd_diff(db, before, after):`:

```python
    meta = {}
    for tag in (before, after):
        row = db.execute(
            "SELECT engine, max_seconds, seeds FROM tape_runs WHERE run_tag=?",
            (tag,)).fetchone()
        if row is None:
            print(f"WARNING: no tape_runs row for {tag}")
            row = ("?", None, None)
        meta[tag] = row
    b_meta, a_meta = meta[before], meta[after]
    for i, what in enumerate(("engine", "max_seconds", "seeds")):
        if b_meta[i] != a_meta[i]:
            print(f"WARNING: {what} differs — {before}={b_meta[i]!r}"
                  f" vs {after}={a_meta[i]!r}. Fight-length and agreement"
                  f" comparisons across this difference are not like-for-like.")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_report_engine_column.py -v`
Expected: PASS (2 tests). Also run `python -m aoe2x.validation.report --list` and eyeball that the 14 existing runs print `engine=simulation_real.py max_s=180.0` (or 600.0).

- [ ] **Step 6: Commit**

```bash
git add aoe2x/validation/report.py tests/test_report_engine_column.py
git commit -m "validation(report): surface engine + max_seconds, warn on cross-engine diffs"
```

---

## Task 5: Margin ground truth + scorer

**Files:**
- Create: `aoe2x/validation/tape_margins.json`, `aoe2x/validation/margin_score.py`
- Test: `tests/test_margin_score.py`

**Interfaces:**
- Consumes: `tape_runs.db` (`tape_battles` at `scale='tape'`), `data/golden/aoe2_reference.db` for per-unit `final_hp`.
- Produces: `margin_score.score_run(db_path, run_tag) -> {"survivor_mae": float, "hp_mae_pp": float, "rows": [...]}`. Task 13 reads this.

**Why this is the primary metric:** the corpus win/loss bit was the Python engine's training set, so it cannot rank engines. Margins (survivor counts, HP%) move on rows whose bit never flips — which is exactly what a target-commitment fix does.

**Ground truth provenance:** all 11 rows come from the `_ingame_note` field of
`git show origin/aoe2_ai_for_simulation:apps/video/sim_v2/overrides/imp_slinger.json`
(blob `3d40397455295eda34e671a0416aa6e3cf92bef9`). Every row is `imp_slinger` as
the subject and exists in `tape_corpus.json`. The HP% convention, verified to
reproduce the numbers in the migration doc §3.2, is
`tape_hp / (STARTING count × per-unit final_hp)` — the starting count, not
survivors: `833/(15*95) = 58.46%`, not `833/(13*95)`. That matches
`simulation_real.total_max_hp`, which sums over the whole starting team.

- [ ] **Step 1: Write the ground-truth fixture**

Create `aoe2x/validation/tape_margins.json`:

```json
{
  "_comment": "Margin ground truth for the tape corpus: recorded survivor counts and remaining HP from real in-game fights. Scored by aoe2x/validation/margin_score.py. Unlike the win/loss bit (which was simulation_real.py's training set) these numbers were never fitted against, so they can rank engines.",
  "_provenance": {
    "source": "git show origin/aoe2_ai_for_simulation:apps/video/sim_v2/overrides/imp_slinger.json -> _ingame_note",
    "blob": "3d40397455295eda34e671a0416aa6e3cf92bef9",
    "recorded": "2026-07-27",
    "quote": "Tapes: 21 Slinger vs 4 War Elephant -> 0 Slingers, 4 elephants at 1844hp; vs 6 Battle Elephant -> 0 Slingers, 6 at 1354hp; vs 7 Paladin -> 0 Slingers, 7 at 798hp (x2 runs); vs 15 Hussar -> 0 Slingers, 13 at 833hp. Confirming the other direction: vs 9 Temple Guard -> 18 Slingers left; vs 9 Teutonic Knight -> 18 left; vs 15 Champion -> 18 left."
  },
  "_hp_pct_convention": "tape_hp / (STARTING count * per-unit final_hp from data/golden/aoe2_reference.db). Starting count, NOT survivors -- matches simulation_real.total_max_hp.",
  "rows": [
    {"subject_civ": "Incas", "subject_slug": "imp_slinger", "opp_civ": "Persians", "opp_slug": "elite_war_elephant_persians",
     "subject_survivors": 0, "opp_survivors": 4, "opp_hp": 1844},
    {"subject_civ": "Incas", "subject_slug": "imp_slinger", "opp_civ": "Bengalis", "opp_slug": "elite_elephant",
     "subject_survivors": 0, "opp_survivors": 6, "opp_hp": 1354},
    {"subject_civ": "Incas", "subject_slug": "imp_slinger", "opp_civ": "Huns", "opp_slug": "paladin",
     "subject_survivors": 0, "opp_survivors": 7, "opp_hp": 798},
    {"subject_civ": "Incas", "subject_slug": "imp_slinger", "opp_civ": "Bulgarians", "opp_slug": "hussar",
     "subject_survivors": 0, "opp_survivors": 13, "opp_hp": 833},
    {"subject_civ": "Incas", "subject_slug": "imp_slinger", "opp_civ": "Muisca", "opp_slug": "elite_temple_guard_muisca",
     "subject_survivors": 18, "opp_survivors": null, "opp_hp": null},
    {"subject_civ": "Incas", "subject_slug": "imp_slinger", "opp_civ": "Teutons", "opp_slug": "elite_teutonic_knight_teutons",
     "subject_survivors": 18, "opp_survivors": null, "opp_hp": null},
    {"subject_civ": "Incas", "subject_slug": "imp_slinger", "opp_civ": "Berbers", "opp_slug": "champion",
     "subject_survivors": 18, "opp_survivors": null, "opp_hp": null},
    {"subject_civ": "Incas", "subject_slug": "imp_slinger", "opp_civ": "Chinese", "opp_slug": "elite_chu_ko_nu_chinese",
     "subject_survivors": 9, "opp_survivors": 0, "opp_hp": 0},
    {"subject_civ": "Incas", "subject_slug": "imp_slinger", "opp_civ": "Bohemians", "opp_slug": "elite_hussite_wagon_bohemians",
     "subject_survivors": 9, "opp_survivors": null, "opp_hp": null},
    {"subject_civ": "Incas", "subject_slug": "imp_slinger", "opp_civ": "Armenians", "opp_slug": "imp_elite_skirm",
     "subject_survivors": 0, "opp_survivors": 17, "opp_hp": null},
    {"subject_civ": "Incas", "subject_slug": "imp_slinger", "opp_civ": "Byzantines", "opp_slug": "elite_cataphract_byzantines",
     "subject_survivors": 16, "opp_survivors": null, "opp_hp": null}
  ]
}
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_margin_score.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_margin_score.py -v`
Expected: FAIL — no module `aoe2x.validation.margin_score`.

- [ ] **Step 4: Write the scorer**

Create `aoe2x/validation/margin_score.py`:

```python
"""Score a tape run's MARGINS (survivor counts, HP%) against recorded truth.

The corpus win/loss bit was simulation_real.py's training set and can no longer
rank engines; margins were never fitted against, and they move on rows whose bit
never flips. Reads data/validation/tape_runs.db, so it is engine-agnostic and
retro-scores every historical run.

    python -m aoe2x.validation.margin_score --run <run_tag>
    python -m aoe2x.validation.margin_score --diff <before_tag> <after_tag>

MAE convention (pinned here so numbers are reproducible): average the seeds'
values FIRST, then take the absolute error against truth, then mean over rows.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

FIXTURE = Path(__file__).resolve().parent / "tape_margins.json"
REF_DB = REPO / "data" / "golden" / "aoe2_reference.db"
DEFAULT_DB = REPO / "data" / "validation" / "tape_runs.db"


def tape_hp_pct(tape_hp, starting_count, per_unit_hp):
    """Recorded HP as a fraction of the STARTING team's max HP.

    Starting count, not survivors -- the same denominator as
    simulation_real.total_max_hp, so tape truth and sim output share a scale.
    """
    denom = float(starting_count) * float(per_unit_hp)
    return (tape_hp / denom) if denom > 0 else 0.0


def _unit_hp(civ, slug):
    con = sqlite3.connect(str(REF_DB))
    row = con.execute(
        "SELECT final_hp FROM ref_units WHERE civ_name=? AND unit_slug=?"
        " AND age='Imperial'", (civ, slug)).fetchone()
    if row is None:
        raise SystemExit(f"no ref_units row for {civ}/{slug}")
    return float(row[0])


def score_run(db_path, run_tag):
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))["rows"]
    db = sqlite3.connect(str(db_path))

    surv_errs, hp_errs, out = [], [], []
    for f in fx:
        row = db.execute(
            "SELECT AVG(team1_survivors), AVG(team2_survivors),"
            "       AVG(team1_hp_pct), AVG(team2_hp_pct),"
            "       AVG(my_count), AVG(opp_count), COUNT(*)"
            " FROM tape_battles"
            " WHERE run_tag=? AND scale='tape' AND my_civ=? AND my_unit_slug=?"
            "   AND opp_civ=? AND opp_unit_slug=?",
            (run_tag, f["subject_civ"], f["subject_slug"],
             f["opp_civ"], f["opp_slug"])).fetchone()
        if row is None or row[6] == 0:
            continue
        s1, s2, hp1, hp2, n1, n2, n = row

        # Which side does the tape report? Score that side.
        if f["opp_survivors"] is not None:
            side, sim_surv, truth_surv = "opp", s2, f["opp_survivors"]
        else:
            side, sim_surv, truth_surv = "subject", s1, f["subject_survivors"]
        surv_err = abs(sim_surv - truth_surv)
        surv_errs.append(surv_err)

        hp_err = None
        if f["opp_hp"] is not None:
            truth_hp = tape_hp_pct(f["opp_hp"], n2, _unit_hp(f["opp_civ"], f["opp_slug"]))
            hp_err = abs(hp2 - truth_hp) * 100.0
            hp_errs.append(hp_err)

        out.append({
            "opp": f'{f["opp_civ"]}/{f["opp_slug"]}', "side": side, "seeds": n,
            "sim_survivors": round(sim_surv, 2), "tape_survivors": truth_surv,
            "survivor_err": round(surv_err, 2),
            "hp_err_pp": None if hp_err is None else round(hp_err, 2),
        })

    return {
        "run_tag": run_tag,
        "survivor_mae": (sum(surv_errs) / len(surv_errs)) if surv_errs else 0.0,
        "hp_mae_pp": (sum(hp_errs) / len(hp_errs)) if hp_errs else 0.0,
        "n_survivor_rows": len(surv_errs), "n_hp_rows": len(hp_errs),
        "rows": out,
    }


def _print(res):
    print(f"\n=== MARGINS {res['run_tag']} ===")
    print(f"survivor MAE {res['survivor_mae']:.2f} units  ({res['n_survivor_rows']} rows)")
    print(f"HP MAE       {res['hp_mae_pp']:.2f} pp     ({res['n_hp_rows']} rows)")
    for r in sorted(res["rows"], key=lambda x: -x["survivor_err"]):
        hp = "    -" if r["hp_err_pp"] is None else f"{r['hp_err_pp']:5.1f}pp"
        print(f"  {r['opp'][:44]:<44} [{r['side']:<7}]"
              f" sim={r['sim_survivors']:>5} tape={r['tape_survivors']:>3}"
              f" err={r['survivor_err']:>5.2f}  hp_err={hp}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--run")
    ap.add_argument("--diff", nargs=2, metavar=("BEFORE", "AFTER"))
    a = ap.parse_args()
    if a.diff:
        b, c = score_run(a.db, a.diff[0]), score_run(a.db, a.diff[1])
        _print(b)
        _print(c)
        print(f"\nsurvivor MAE {b['survivor_mae']:.2f} -> {c['survivor_mae']:.2f}"
              f"   ({c['survivor_mae'] - b['survivor_mae']:+.2f})")
        print(f"HP MAE       {b['hp_mae_pp']:.2f} -> {c['hp_mae_pp']:.2f}"
              f"   ({c['hp_mae_pp'] - b['hp_mae_pp']:+.2f} pp)")
    elif a.run:
        _print(score_run(a.db, a.run))
    else:
        sys.exit("pass --run <tag> or --diff <before> <after>")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_margin_score.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Cross-check against the documented figures**

Run: `python -m aoe2x.validation.margin_score --run review-current-7c4e06c0-20260729T002708Z-sv7c4e06c0`
Expected: prints a survivor MAE and HP MAE. The migration doc §3.2 records 2.62 units / 8.51 pp for the shipped Python engine. **If the numbers differ materially, do not "fix" the scorer to match** — record both in the commit message and flag it; the doc's figures were computed ad hoc and the pinned convention here is the reproducible one.

- [ ] **Step 7: Commit**

```bash
git add aoe2x/validation/tape_margins.json aoe2x/validation/margin_score.py tests/test_margin_score.py
git commit -m "validation: margin ground truth fixture + engine-agnostic margin scorer"
```

---

## Task 6: BEFORE measurement (engine untouched)

**Files:**
- Modify: `data/validation/tape_runs.db` (two new runs, additive)
- Create: `docs/architecture/tape-rig-js.md`

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: two `run_tag`s recorded in the doc — the JS BEFORE tag and a 600 s Python reference tag. Task 13 diffs against them.

**This task changes no engine code.** Its output is a number.

- [ ] **Step 1: Verify the engine is clean before measuring**

Run: `git status --porcelain apps/website/static/js/engine/`
Expected: empty. If not, STOP — the BEFORE number must be measured on unmodified engine sources.

Run: `node tools/simjs/parity_check.mjs`
Expected: exit 0.

- [ ] **Step 2: Record the JS BEFORE run**

```bash
python tools/simjs/dump_tape_dicts.py
python -m aoe2x.validation.tape_rig_js --label js-before --seeds 5 --scales tape,equal_count
```

Note the printed `run_tag` and both AGREEMENT lines.

- [ ] **Step 3: Mint a like-for-like Python reference at the same cap**

The existing HEAD Python run is at `max_seconds=180`; the JS runs at 600. Run the Python rig at 600 s so the comparison is like-for-like (~2 minutes):

```bash
python -m aoe2x.validation.tape_rig --label py-head-600s --seeds 5 --max-seconds 600 --scales tape,equal_count
```

- [ ] **Step 4: Score margins for both**

```bash
python -m aoe2x.validation.margin_score --diff <py_head_600s_tag> <js_before_tag>
```

- [ ] **Step 5: Write the findings doc**

Create `docs/architecture/tape-rig-js.md` recording: what the rig is and how to run it (the three commands), the two `run_tag`s with their bit agreement (tape + equal_count) and margin MAEs, the recording conventions (seeds 1..5, HP%-adjudicated caps, node version in `python_impl`, value_lost approximation, spawn-overflow caveat), and an explicit note that the corpus bit favours the Python engine because it was its training set.

- [ ] **Step 6: Commit**

```bash
git add data/validation/tape_runs.db docs/architecture/tape-rig-js.md
git commit -m "validation: BEFORE scores — JS engine and 600s Python reference on the tape corpus"
```

---

## Task 7: Behavior-neutral refactor (parity MUST stay green)

**Files:**
- Modify: `apps/website/static/js/engine/constants.js`, `apps/website/static/js/engine/battle_unit.js:1282-1345`
- Test: `tests/js/engine/pursuit.test.mjs`

**Interfaces:**
- Consumes: nothing new.
- Produces: exported `STUCK_PROGRESS_RATE`, `PURSUIT_FRACTION`, `RECEDE_EPS` from `constants.js`; locals `toTgtX/toTgtY/entryX/entryY/intentProgress` inside `moveTowardTarget`. Task 9 uses `intentProgress`.

**This task must not change a single fight.** It converts the bar to a rate and computes the intent projection without acting on it. `30 * (1/60) === 0.5` exactly in IEEE-754 (verified), so at the production sub-step the arithmetic is bit-identical. Parity staying green is the proof the refactor didn't leak into the physics.

- [ ] **Step 1: Write the failing test**

Create `tests/js/engine/pursuit.test.mjs`:

```javascript
import { test } from "node:test";
import assert from "node:assert/strict";
import {
    STUCK_PROGRESS_RATE, PURSUIT_FRACTION, RECEDE_EPS,
} from "../../../apps/website/static/js/engine/constants.js";

test("pursuit constants have their specified values", () => {
    assert.equal(STUCK_PROGRESS_RATE, 30);
    assert.equal(PURSUIT_FRACTION, 0.35);
    assert.equal(RECEDE_EPS, 0.05);
});

test("the rate form is bit-identical to the old per-frame constant at dt=1/60", () => {
    // The pre-refactor code used `- 0.5` per sub-step. Expressing it as a rate
    // must not perturb a single fight at the production sub-step.
    assert.equal(STUCK_PROGRESS_RATE * (1 / 60), 0.5);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/js/engine/pursuit.test.mjs`
Expected: FAIL — the three constants are not exported.

- [ ] **Step 3: Add the constants**

Append to `apps/website/static/js/engine/constants.js`:

```javascript
// ===== PURSUIT / STUCK DETECTION =====
// Minimum closing speed, in PX PER SECOND, below which a chase counts as
// "stalled". This was written as a bare `- 0.5` inside moveTowardTarget, i.e.
// 0.5 px per SUB-STEP, which silently made physics depend on tick rate: the
// same literal demands 1.0 tiles/s at 60 fps but only 0.5 tiles/s at 30 Hz
// (simulation_real.py:186-195 documents the same defect and normalised its copy
// to a rate). 30 px/s reproduces the old literal EXACTLY at dt = 1/60
// (30 * (1/60) === 0.5 in IEEE-754), so converting the form changed no fight;
// it only becomes load-bearing if the sub-step ever moves.
export const STUCK_PROGRESS_RATE = 30;

// A chase counts as genuine pursuit when the unit's actual displacement,
// projected on the direction to its target, is at least this fraction of the
// distance it could have covered. Not a fitted value: because velocity is
// renormalised every sub-step with 0.3 smoothing, a unit whose desired
// direction is on target always scores >= 0.9035 of full progress (analytic
// floor over all prior headings, including a 180-degree reversal), so any
// threshold at or below 0.9 accepts every honest pursuit. Outcomes were
// measured identical across 0.2 / 0.35 / 0.5.
export const PURSUIT_FRACTION = 0.35;

// Float-noise guard on the "is my target actually running away from me" test,
// as a fraction of the chaser's own per-step distance. Not a behaviour knob.
export const RECEDE_EPS = 0.05;
```

- [ ] **Step 4: Refactor `moveTowardTarget`**

In `battle_unit.js`, add the three names to the existing import from `./constants.js`.

Then, inside `moveTowardTarget`, immediately after `dx /= dist; dy /= dist;` (currently line 1289), insert:

```javascript
        // Snapshot the pre-avoidance intent: dx/dy are `let` and get overwritten
        // by the avoidance blend below, so the direction to the target is not
        // recoverable afterwards. entryX/entryY let the stuck test measure ACTUAL
        // (post-clamp) displacement rather than the intended step, so a unit
        // pinned against the map edge reads as zero progress, not full progress.
        const toTgtX = dx, toTgtY = dy;
        const entryX = this.x, entryY = this.y;
```

Then replace the stuck-detection block (currently lines 1332-1344) with:

```javascript
        // Stuck detection: if not making progress, mark target as blocked
        const newDist = this.distanceTo(this.target);
        const moveAmount2 = this.moveSpeed * dt;
        const intentProgress =
            (this.x - entryX) * toTgtX + (this.y - entryY) * toTgtY;
        const stalled =
            newDist >= this.lastDistToTarget - STUCK_PROGRESS_RATE * dt;
        void intentProgress; // consumed in the pursuit exemption (next commit)
        void moveAmount2;
        if (stalled) {
            this.stuckTimer += dt;
        } else {
            this.stuckTimer = Math.max(0, this.stuckTimer - dt * 2);
        }
        this.lastDistToTarget = newDist;
        if (this.stuckTimer > 0.8) {
            this.blockedTargets.add(this.target);
            this.target = null; // force re-target next frame
            this.stuckTimer = 0;
        }
```

- [ ] **Step 5: Run the tests and the parity gate**

Run: `node --test tests/js/engine/`
Expected: PASS, including the two new tests.

Run: `node tools/simjs/parity_check.mjs`
Expected: **exit 0, "PARITY OK"**. If this fails, the refactor leaked into the physics — revert and find the difference. Do NOT re-capture the golden for this task.

- [ ] **Step 6: Commit**

```bash
git add apps/website/static/js/engine/constants.js apps/website/static/js/engine/battle_unit.js tests/js/engine/pursuit.test.mjs
git commit -m "refactor(engine): express the stuck bar as a rate, capture pursuit intent

Behaviour-neutral: 30 px/s * (1/60) === 0.5 exactly, so this reproduces the old
per-frame literal bit-for-bit at the production sub-step. parity_check.mjs stays
green, which is the proof. Removes the tick-rate coupling that made the same
constant mean 1.0 tiles/s at 60fps and 0.5 tiles/s at 30Hz."
```

---

## Task 8: New golden capture path

**Files:**
- Create: `tools/simjs/capture_golden.mjs`

**Interfaces:**
- Consumes: `runFight`, `loadDicts`, `loadSpec`, `MAX_SECONDS` from `headless.mjs`; `tools/simjs/golden/panel_spec.json`, `panel.meta.json`.
- Produces: a CLI that writes `panel.json` + updates `panel.meta.json`. Task 10 uses it.

**Why now:** `parity_capture.mjs` drives `legacy_harness.cjs`, which `vm`-evals `simulate.js` as a script — but `simulate.js` is now an ESM page shell with top-level imports and holds no copy of the sim, so `panel.json` can no longer be regenerated. Task 10 will deliberately break parity and needs a working re-capture. Building it **now**, while the engine is still behavior-identical, gives a free correctness proof: the new tool must reproduce the existing `panel.json` byte-for-byte.

- [ ] **Step 1: Write the tool**

Create `tools/simjs/capture_golden.mjs`:

```javascript
// Capture the golden parity panel FROM THE EXTRACTED ENGINE.
//
// Replaces the parity_capture.mjs path, which drove legacy_harness.cjs ->
// vm-eval of simulate.js. That no longer works: simulate.js is an ESM page shell
// with top-level imports and holds no copy of the sim. Since parity_check.mjs
// already proves runFight() reproduces the legacy panel for all 205 fights, this
// tool is a faithful successor -- and running it on an unchanged engine must
// reproduce panel.json byte-for-byte, which is how it was validated.
//
//     node tools/simjs/capture_golden.mjs --verify        # must match panel.json
//     node tools/simjs/capture_golden.mjs --write --reason "..."
//
// --write REQUIRES --reason. A golden re-capture erases the previous bit-exact
// baseline, so the justification is recorded in panel.meta.json alongside the
// provenance (CLAUDE.md cross-file sync rule 1).
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { runFight, loadDicts, loadSpec, MAX_SECONDS } from "./headless.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PANEL = path.join(HERE, "golden/panel.json");
const META = path.join(HERE, "golden/panel.meta.json");

const argv = process.argv.slice(2);
const has = (f) => argv.includes(f);
const flag = (f) => {
    const i = argv.indexOf(f);
    return i >= 0 && i + 1 < argv.length ? argv[i + 1] : null;
};

const meta = JSON.parse(readFileSync(META, "utf8"));
const seeds = meta.seeds;
const dicts = loadDicts();
const spec = loadSpec();

const captured = [];
for (const row of spec) {
    for (const seed of seeds) {
        const r = runFight({ dicts, row, seed, maxSeconds: MAX_SECONDS });
        captured.push({ ...row, seed, snapshots: r.snapshots, final: r.final });
    }
}
console.log(`captured ${captured.length} fights (${spec.length} rows x ${seeds.length} seeds)`);

if (has("--verify")) {
    const golden = JSON.parse(readFileSync(PANEL, "utf8"));
    if (golden.length !== captured.length) {
        console.error(`COUNT MISMATCH: golden ${golden.length} vs captured ${captured.length}`);
        process.exit(1);
    }
    let diverged = 0;
    for (let i = 0; i < golden.length; i++) {
        const a = JSON.stringify({ snapshots: captured[i].snapshots, final: captured[i].final });
        const b = JSON.stringify({ snapshots: golden[i].snapshots, final: golden[i].final });
        if (a !== b) {
            if (diverged < 5) console.error(`DIVERGED: ${golden[i].id} seed ${golden[i].seed}`);
            diverged++;
        }
    }
    if (diverged) {
        console.error(`\n${diverged}/${golden.length} fights differ from panel.json`);
        process.exit(1);
    }
    console.log("VERIFY OK — capture reproduces panel.json exactly");
    process.exit(0);
}

if (has("--write")) {
    const reason = flag("--reason");
    if (!reason) {
        console.error("--write requires --reason \"why the golden is being replaced\"");
        process.exit(2);
    }
    writeFileSync(PANEL, JSON.stringify(captured));
    meta.capturedBy = "tools/simjs/capture_golden.mjs";
    meta.rowCount = spec.length;
    meta.fightCount = captured.length;
    meta.maxSeconds = MAX_SECONDS;
    meta.recaptureReason = reason;
    meta.recaptureHistory = [...(meta.recaptureHistory || []), reason];
    writeFileSync(META, JSON.stringify(meta, null, 1));
    console.log(`wrote ${PANEL}\nreason recorded: ${reason}`);
    process.exit(0);
}

console.error("usage: node tools/simjs/capture_golden.mjs (--verify | --write --reason \"...\")");
process.exit(2);
```

- [ ] **Step 2: Prove it reproduces the existing golden**

Run: `node tools/simjs/capture_golden.mjs --verify`
Expected: "VERIFY OK — capture reproduces panel.json exactly", exit 0.

If this fails, the tool is wrong (the engine is still behavior-identical at this point) — fix the tool, not the golden.

- [ ] **Step 3: Commit**

```bash
git add tools/simjs/capture_golden.mjs
git commit -m "tools(simjs): golden re-capture path driven from the extracted engine

parity_capture.mjs is dead: it vm-evals simulate.js, now an ESM shell with no
copy of the sim. Validated by reproducing panel.json byte-for-byte on an
unchanged engine (--verify)."
```

---

## Task 9: The pursuit exemption (parity WILL break)

**Files:**
- Modify: `apps/website/static/js/engine/battle_unit.js` (constructor + `moveTowardTarget`)
- Test: `tests/js/engine/pursuit.test.mjs` (extend)

**Interfaces:**
- Consumes: `intentProgress`, `toTgtX/toTgtY`, `PURSUIT_FRACTION`, `RECEDE_EPS` from Task 7.
- Produces: `this.prevTargetX`, `this.prevTargetY`, `this.prevTargetRef` instance fields; the `stalled && !(pursuing && receding)` accumulation condition.

**The design decision:** we do NOT gate on "wedged". A plain `stalled && wedged` gate was measured deleting 89–99.8% of melee-scrum blacklist events — it removes the fan-out mechanism instead of narrowing it. Adding the `receding` conjunct (only exempt a chase when the target is *actually fleeing*) retains ~49% of scrum blacklisting while still fixing the pathological pairs.

`stateHash()` (`sim.js:232-244`) hashes only `x, y, currentHp, state` per unit plus four sim-level values — the new fields are invisible to it, as `stuckTimer` and `vx/vy` already are.

- [ ] **Step 1: Write the failing tests**

Append to `tests/js/engine/pursuit.test.mjs`:

```javascript
import { createSimulation } from "../../../apps/website/static/js/engine/index.js";

const ARCHER = {
    hp: 40, attack: 6, attack_range: 5, attack_speed: 0.5, attack_delay: 0.2,
    movement_speed: 0.96, melee_armor: 0, pierce_armor: 0, outline_size: 0.2,
    accuracy: 100, unit_name: "Test Archer",
    cost_food: 0, cost_wood: 25, cost_gold: 45, hp_regen: 0,
};
const SLOW_MELEE = {
    hp: 400, attack: 12, attack_range: 0, attack_speed: 0.5, attack_delay: 0,
    movement_speed: 0.99, melee_armor: 2, pierce_armor: 2, outline_size: 0.5,
    accuracy: 100, unit_name: "Test Elephant",
    cost_food: 100, cost_wood: 0, cost_gold: 80, hp_regen: 0,
};

function fight(count, seed, maxSeconds) {
    const sim = createSimulation({
        teams: [
            { combatDict: ARCHER, slug: "test_archer", civ: "Britons", count },
            { combatDict: SLOW_MELEE, slug: "test_elephant", civ: "Bengalis", count },
        ],
        seed,
    });
    const maxTicks = Math.round(maxSeconds * 60);
    let ticks = 0, switches = 0;
    const prev = new Map(sim.team2.map((u) => [u, u.target]));
    while (sim.winner === null && ticks < maxTicks) {
        sim.step(1 / 60);
        ticks++;
        for (const u of sim.team2) {
            if (u.state !== "dead" && u.target !== prev.get(u)) {
                switches++;
                prev.set(u, u.target);
            }
        }
    }
    return { winner: sim.winner, time: sim.battleTime, switches, ticks };
}

test("a slow melee unit closing on a stationary target is never declared stuck", () => {
    const sim = createSimulation({
        teams: [
            { combatDict: ARCHER, slug: "test_archer", civ: "Britons", count: 1 },
            { combatDict: SLOW_MELEE, slug: "test_elephant", civ: "Bengalis", count: 1 },
        ],
        seed: 1,
    });
    const archer = sim.team1[0], ele = sim.team2[0];
    archer.moveSpeed = 0;            // pin it
    archer.attackDelay = 1e9;        // and silence it
    archer.attackCooldown = 1e9;
    const d0 = ele.distanceTo(archer);
    for (let i = 0; i < 60 * 5; i++) sim.step(1 / 60);
    assert.ok(ele.distanceTo(archer) < d0 - 100, "the elephant must actually close");
    assert.equal(ele.blockedTargets.size, 0,
        "closing at full speed on a stationary target must never blacklist it");
});

test("the pursuit exemption collapses target thrashing", () => {
    const r = fight(10, 1, 600);
    // Pre-fix this fight ran hundreds of seconds with >10 switches/sec.
    const perSec = r.switches / Math.max(r.time, 1);
    assert.ok(perSec < 4, `target switches/sec too high: ${perSec.toFixed(1)}`);
    assert.notEqual(r.winner, null, "the fight must resolve inside the cap");
});

test("determinism: identical seeds produce identical fights", () => {
    const a = fight(6, 4, 600);
    const b = fight(6, 4, 600);
    assert.deepEqual(a, b);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test tests/js/engine/pursuit.test.mjs`
Expected: FAIL on "closing at full speed on a stationary target must never blacklist it" (`blockedTargets.size` is 1+), and likely on the switches/sec assertion.

- [ ] **Step 3: Add the instance fields**

In the `BattleUnit` constructor, immediately after `this.blockedTargets = new Set();` (currently line 223), insert:

```javascript
        // Previous-tick target position, for the "is my target actually running
        // away from me" half of the pursuit exemption. Decision bookkeeping
        // only: stateHash() hashes x/y/currentHp/state per unit, so like
        // stuckTimer and vx/vy these never enter the parity hash.
        this.prevTargetX = 0;
        this.prevTargetY = 0;
        this.prevTargetRef = null;
```

- [ ] **Step 4: Apply the exemption**

In `moveTowardTarget`, replace the block written in Task 7 (from `const newDist =` through the `if (this.stuckTimer > 0.8) { ... }`) with:

```javascript
        // Stuck detection. The bar alone cannot tell an obstructed unit from one
        // that is simply slower than what it is chasing, and the old response --
        // blacklist the target and re-acquire the nearest -- turned every chase
        // into a 0.8s oscillation between enemies on opposite flanks.
        //
        // So the scope is INVERTED: keep today's semantics everywhere, and
        // EXEMPT only the provably legitimate case -- this unit is walking at its
        // target AND the target is genuinely running away. Gating on "obstructed"
        // instead was measured deleting 89-99.8% of melee-scrum blacklist events,
        // i.e. removing the fan-out mechanism rather than narrowing it.
        const newDist = this.distanceTo(this.target);
        const stepDist = this.moveSpeed * dt;
        const intentProgress =
            (this.x - entryX) * toTgtX + (this.y - entryY) * toTgtY;
        const stalled =
            newDist >= this.lastDistToTarget - STUCK_PROGRESS_RATE * dt;
        const pursuing = intentProgress >= PURSUIT_FRACTION * stepDist;
        // Radial component of the TARGET's own motion since last tick: positive
        // means it is opening the gap. Unknown on the first tick against a new
        // target, which counts as receding so a fresh chase is never punished.
        const receding =
            this.prevTargetRef !== this.target
                ? true
                : (this.target.x - this.prevTargetX) * toTgtX
                  + (this.target.y - this.prevTargetY) * toTgtY
                  > RECEDE_EPS * stepDist;
        if (stalled && !(pursuing && receding)) {
            this.stuckTimer += dt;
        } else {
            this.stuckTimer = Math.max(0, this.stuckTimer - dt * 2);
        }
        this.lastDistToTarget = newDist;
        this.prevTargetX = this.target.x;
        this.prevTargetY = this.target.y;
        this.prevTargetRef = this.target;
        if (this.stuckTimer > 0.8) {
            this.blockedTargets.add(this.target);
            this.target = null; // force re-target next frame
            this.stuckTimer = 0;
        }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `node --test tests/js/engine/`
Expected: PASS, all files.

- [ ] **Step 6: Confirm parity breaks (this is the signal, not a failure)**

Run: `node tools/simjs/parity_check.mjs`
Expected: **non-zero exit with DIVERGED lines.** Record how many fights diverged from the summary output. If parity *passes*, the exemption is not firing — investigate before continuing.

Do NOT re-capture the golden yet; Tasks 10 and 11 also change behavior, and one re-capture at the end of the behavioral work keeps the provenance clean.

- [ ] **Step 7: Commit**

```bash
git add apps/website/static/js/engine/battle_unit.js tests/js/engine/pursuit.test.mjs
git commit -m "fix(engine): exempt genuine pursuit from stuck detection

A chasing unit no longer blacklists the target it is walking straight at. The
bar demanded 1.0 tile/s of closing speed -- unreachable for the seven roster
units slower than that, and for any chase of a kiter -- so every pursuit
oscillated between flanks every 0.8s and armies never arrived.

Scope is inverted deliberately: today's semantics are kept everywhere and only
'walking at it AND it is fleeing' is exempted. Gating on 'obstructed' instead
measured out at 89-99.8% of melee-scrum blacklist events deleted.

parity_check.mjs fails by design; golden re-capture follows once the behavioural
work lands."
```

---

## Task 10: Stale distance baseline

**Files:**
- Modify: `apps/website/static/js/engine/battle_unit.js` (constructor, `findTarget`, `moveTowardTarget`)
- Test: `tests/js/engine/pursuit.test.mjs` (extend)

**Interfaces:**
- Consumes: Task 9's block.
- Produces: `this.lastDistTime` instance field.

**Why:** `lastDistToTarget` is written only inside `moveTowardTarget` (`:1339`) and `findTarget` (`:1367-1369`). `moveAwayFromTarget` and every attacking branch leave it untouched. So a ranged unit that kites or attacks for N frames and then re-enters the moving branch compares an N-frame-old distance against a one-frame bar — `stalled` is not a rate at all for such units. `this.sim.battleTime` is available on every unit.

- [ ] **Step 1: Write the failing test**

Append to `tests/js/engine/pursuit.test.mjs`:

```javascript
test("the distance baseline is re-stamped after a gap, not judged across it", () => {
    const sim = createSimulation({
        teams: [
            { combatDict: ARCHER, slug: "test_archer", civ: "Britons", count: 1 },
            { combatDict: SLOW_MELEE, slug: "test_elephant", civ: "Bengalis", count: 1 },
        ],
        seed: 1,
    });
    const ele = sim.team2[0];
    for (let i = 0; i < 60; i++) sim.step(1 / 60);
    assert.ok(Number.isFinite(ele.lastDistTime), "lastDistTime must be stamped");
    // Simulate a gap: the unit spent time in a non-moving branch.
    const staleDist = ele.lastDistToTarget;
    ele.lastDistTime -= 5.0;
    ele.lastDistToTarget = 1e6;   // absurd stale baseline
    sim.step(1 / 60);
    assert.ok(ele.lastDistToTarget < 1e5,
        "a stale baseline must be re-stamped from the current distance");
    assert.ok(staleDist > 0);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/js/engine/pursuit.test.mjs`
Expected: FAIL — `lastDistTime` is `undefined`.

- [ ] **Step 3: Add the field**

In the constructor, immediately after `this.lastDistToTarget = Infinity;` (currently line 222), insert:

```javascript
        // battleTime at which lastDistToTarget was stamped. The baseline is only
        // written in moveTowardTarget and findTarget -- kiting and attacking
        // branches leave it alone -- so without this a unit re-entering the
        // moving branch after N frames judges an N-frame displacement against a
        // one-sub-step bar.
        this.lastDistTime = -Infinity;
```

- [ ] **Step 4: Stamp it in `findTarget`**

In `findTarget`, immediately after the existing `this.lastDistToTarget = this.target ? this.distanceTo(this.target) : Infinity;` assignment, insert:

```javascript
        this.lastDistTime = this.sim ? this.sim.battleTime : 0;
```

- [ ] **Step 5: Use it in `moveTowardTarget`**

In the Task 9 block, replace the single `const stalled = ...` line with:

```javascript
        // A baseline older than one sub-step spans an unknown interval (the unit
        // was kiting or attacking), so re-stamp instead of judging across it.
        const now = this.sim ? this.sim.battleTime : 0;
        const baselineFresh = now - this.lastDistTime <= dt * 1.5;
        const stalled = baselineFresh
            && newDist >= this.lastDistToTarget - STUCK_PROGRESS_RATE * dt;
```

And immediately after the existing `this.lastDistToTarget = newDist;`, insert:

```javascript
        this.lastDistTime = now;
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `node --test tests/js/engine/`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/website/static/js/engine/battle_unit.js tests/js/engine/pursuit.test.mjs
git commit -m "fix(engine): re-stamp the distance baseline instead of judging across a gap

lastDistToTarget is written only in moveTowardTarget and findTarget, so a ranged
unit that kited or attacked for N frames compared an N-frame displacement
against a one-sub-step bar. The 'stalled' test is now a real rate."
```

---

## Task 11: Reachability swap (idle-chaser escape)

**Files:**
- Modify: `apps/website/static/js/engine/battle_unit.js` (`moveTowardTarget`)
- Test: `tests/js/engine/pursuit.test.mjs` (extend)

**Interfaces:**
- Consumes: Task 10's block; the existing `inRange()` predicate.
- Produces: no new fields.

**Why:** commitment without an escape strands units. Measured on a committed Siege-Ram-vs-Arbalester fight: 4 of 10 rams were alive for all 36,000 ticks with `inRange()` true on **zero** of them (their own r=26 allies filled the corner), while two other rams stood within reach of a *different* arbalester on 26–27% of ticks and never swung. The old stuck detector accidentally prevented this. Fix: when stalled, if another living enemy is already within reach, take it. No new constant; reuses `inRange`'s own arithmetic.

- [ ] **Step 1: Write the failing test**

Append to `tests/js/engine/pursuit.test.mjs`:

```javascript
test("a stalled unit takes an enemy already within reach", () => {
    const sim = createSimulation({
        teams: [
            { combatDict: ARCHER, slug: "test_archer", civ: "Britons", count: 2 },
            { combatDict: SLOW_MELEE, slug: "test_elephant", civ: "Bengalis", count: 1 },
        ],
        seed: 1,
    });
    const ele = sim.team2[0];
    const far = sim.team1[0], near = sim.team1[1];

    // Commit the elephant to the FAR archer, then park the other one on top of it.
    ele.x = 450; ele.y = 300;
    far.x = 60;  far.y = 300;
    near.x = 450 + ele.radius + near.radius; near.y = 300;
    ele.target = far;
    ele.lastDistToTarget = ele.distanceTo(far);
    ele.lastDistTime = sim.battleTime;
    far.moveSpeed = ele.moveSpeed * 2;   // it can outrun the elephant

    for (let i = 0; i < 120; i++) sim.step(1 / 60);
    assert.notEqual(ele.target, far,
        "with a reachable enemy adjacent, the chaser must not stay committed to an unreachable one");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/js/engine/pursuit.test.mjs`
Expected: FAIL — the elephant stays committed to `far`.

- [ ] **Step 3: Implement the swap**

In `moveTowardTarget`, replace the final `if (this.stuckTimer > 0.8) { ... }` block with:

```javascript
        if (stalled) {
            // Escape hatch for a target we cannot reach at all: if something else
            // is already inside our swing radius, hit that instead of walking at
            // an enemy our own crowd is boxing us away from. Costs no blacklist
            // entry and no timer -- the swap IS the resolution.
            const enemies = this.team === 1 ? this.sim.team2 : this.sim.team1;
            for (const e of enemies) {
                if (e === this.target || e.state === "dead") continue;
                const d = this.distanceTo(e);
                // Same predicate as inRange(), including the minimum-range dead
                // zone, so a siege unit cannot swap onto something too close.
                if (this.minAttackRange > 0 && d < this.minAttackRange) continue;
                if (d <= this.attackRange + this.radius + e.radius) {
                    this.target = e;
                    this.stuckTimer = 0;
                    this.lastDistToTarget = this.distanceTo(e);
                    this.lastDistTime = now;
                    this.prevTargetRef = null;
                    return;
                }
            }
        }
        if (this.stuckTimer > 0.8) {
            this.blockedTargets.add(this.target);
            this.target = null; // force re-target next frame
            this.stuckTimer = 0;
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test tests/js/engine/`
Expected: PASS, all files.

- [ ] **Step 5: Commit**

```bash
git add apps/website/static/js/engine/battle_unit.js tests/js/engine/pursuit.test.mjs
git commit -m "fix(engine): a stalled chaser takes an enemy already within reach

Commitment without an escape strands units: measured 4 of 10 rams alive for a
whole fight with inRange() true on zero ticks, boxed out of a corner by their
own allies, while two others stood in reach of a different enemy and never
swung. Reuses inRange's arithmetic; no new constant."
```

---

## Task 12: Re-capture the golden panel

**Files:**
- Modify: `tools/simjs/golden/panel.json`, `tools/simjs/golden/panel.meta.json`

**Interfaces:**
- Consumes: `tools/simjs/capture_golden.mjs` from Task 8.
- Produces: a golden panel matching the post-fix engine, so `parity_check.mjs` guards future changes again.

- [ ] **Step 1: Confirm the tests are green and parity is red for the right reason**

Run: `node --test tests/js/engine/`
Expected: PASS.

Run: `node tools/simjs/parity_check.mjs`
Expected: non-zero exit. Note the diverged count.

- [ ] **Step 2: Record the pre-fix golden's identity**

Run: `git log --oneline -1 -- tools/simjs/golden/panel.json` and `python -c "import json;print(json.load(open('tools/simjs/golden/panel.meta.json')))"`.
Keep the output for the commit message — the old baseline stays recoverable through git history.

- [ ] **Step 3: Re-capture**

```bash
node tools/simjs/capture_golden.mjs --write --reason "Pursuit exemption (docs/superpowers/specs/2026-07-29-target-thrash-design.md): moveTowardTarget no longer blacklists a target the unit is walking straight at while that target flees; distance baseline re-stamped after a gap; stalled chaser takes an enemy already in reach. Deliberate behaviour change -- the pre-fix panel is preserved in git history."
```

- [ ] **Step 4: Verify the gate is green again**

Run: `node tools/simjs/parity_check.mjs`
Expected: exit 0, "PARITY OK".

Run: `node tools/simjs/capture_golden.mjs --verify`
Expected: "VERIFY OK" (the capture is now self-consistent).

- [ ] **Step 5: Commit**

```bash
git add tools/simjs/golden/panel.json tools/simjs/golden/panel.meta.json
git commit -m "golden: re-capture the parity panel after the pursuit fix

Deliberate behaviour change per CLAUDE.md sync rule 1. The pre-fix panel and its
meta are preserved in git history; recaptureReason records why."
```

---

## Task 13: AFTER measurement and findings

**Files:**
- Modify: `data/validation/tape_runs.db`, `docs/architecture/tape-rig-js.md`, `docs/architecture/runbooks.md`, `docs/superpowers/specs/2026-07-29-target-thrash-design.md`

**Interfaces:**
- Consumes: everything above; the BEFORE `run_tag`s from Task 6.
- Produces: the AFTER `run_tag` and a verdict on the spec's §8.1 open question.

- [ ] **Step 1: Record the AFTER run**

```bash
python -m aoe2x.validation.tape_rig_js --label js-after-pursuit-fix --seeds 5 --scales tape,equal_count
```

- [ ] **Step 2: Diff bit agreement and margins**

```bash
python -m aoe2x.validation.report --list
python -m aoe2x.validation.report --diff <js_before_tag> <js_after_tag>
python -m aoe2x.validation.margin_score --diff <js_before_tag> <js_after_tag>
```

- [ ] **Step 3: Check the sensitivity claim**

The spec claims `PURSUIT_FRACTION` is not load-bearing. Verify through the rig: temporarily set it to `0.2`, run `python -m aoe2x.validation.tape_rig_js --label js-frac020 --seeds 5 --scales tape`, then `0.5` as `js-frac050`, then restore `0.35` and confirm `git diff` on the engine is empty. Compare the three tape-scale agreement numbers and margin MAEs.
Expected: materially identical. If they differ, the constant IS load-bearing and that contradicts the spec — report it rather than picking the best score.

- [ ] **Step 4: Re-run the cross-engine comparison as a secondary lens**

```bash
python lab/cross_engine/run_py.py --dicts-only
node lab/cross_engine/run_js.mjs
python lab/cross_engine/compare.py
```
Expected: timeouts 0 (was 7); agreement around 92%; the residual disagreements all pointing the same direction (the closing melee unit winning in JS). Record the numbers.

- [ ] **Step 5: Answer the open question in the spec**

Append a "Results" section to `docs/superpowers/specs/2026-07-29-target-thrash-design.md` recording: BEFORE/AFTER bit agreement (tape + equal_count), BEFORE/AFTER margin MAEs, the sensitivity result, the cross-engine numbers, and — explicitly — **whether the tape supports the melee-ward winner flips.** If it does not, say so plainly and note that the next lever is the corner-pin geometry (spawn runway / arena size), not the predicate.

- [ ] **Step 6: Update the runbook**

Add a section to `docs/architecture/runbooks.md`: "when the JS engine's behaviour changes" — run `node --test tests/js/engine/`, expect `parity_check.mjs` to fail, re-capture with `capture_golden.mjs --write --reason "..."`, and score BEFORE/AFTER with `tape_rig_js` + `margin_score`. Note that `parity_capture.mjs` is superseded.

- [ ] **Step 7: Commit**

```bash
git add data/validation/tape_runs.db docs/architecture/tape-rig-js.md docs/architecture/runbooks.md docs/superpowers/specs/2026-07-29-target-thrash-design.md
git commit -m "validation: AFTER scores for the pursuit fix + runbook for JS engine changes"
```

- [ ] **Step 8: Full suite**

Run: `python -m pytest` and `node --test tests/js/engine/` and `node tools/simjs/parity_check.mjs`
Expected: all green. Report any failure with its output rather than working around it.

---

## Self-Review

**Spec coverage:** §1 root cause → Tasks 7, 9 (both defects). §2 predicate + constants → Tasks 7, 9. §3a stale baseline → Task 10. §3b reachability swap → Task 11. §4 measured results → Tasks 6, 13. §5 out-of-scope → recorded, no tasks (correct). §6 rig → Tasks 1–5, conventions in Tasks 2–3. §7 ladder + broken re-capture blocker → Tasks 6, 8, 12, 13. §8 risks → Task 13 Step 5 (flip direction), Task 13 Step 3 (sensitivity), Task 11 (idle chasers), Task 12 (provenance). §9 prediction ledger → Task 13 Steps 2/4. §10 success criteria → Task 13 Step 8.

**Type consistency:** `plan_row.counts[scale]` is `[n1, n2]` throughout (Tasks 1, 2). `runTapeFight` returns exactly the nine keys Task 3's INSERT reads plus the four the CLI adds (`plan_id`, `scale`, `seed`, `n1`, `n2`). `score_run` returns `survivor_mae`/`hp_mae_pp`/`rows`, matching the Task 5 test and Task 13's usage. `js_sim_version()` is used by both the Task 3 test and the module itself. In JS, `toTgtX/toTgtY/entryX/entryY` are introduced in Task 7 and consumed in Task 9; `now` is introduced in Task 10 and used in Task 11's swap — Task 11 depends on Task 10 landing first (they are sequential).

**Known ordering constraint:** Task 8 must land before Task 12 (needs the capture tool) and is validated only while the engine is still behavior-identical — so it must come before Task 9. Tasks 9 → 10 → 11 are strictly sequential because each edits the same block.

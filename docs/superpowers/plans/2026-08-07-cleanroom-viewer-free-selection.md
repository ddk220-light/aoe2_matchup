# Clean-room Viewer Free Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the clean-room lab viewer run any pair of the 14 tested units at any army sizes, with every spawn position produced by one programmatic placement module derived from — and verified against — the recorded tapes.

**Architecture:** Six new/changed modules under `aoe2x/js_simulation/`. A placement module replaces the fixture-derived synthetic formation; a unit registry carries class and base cost; a purchase solver derives default counts; a new `/api/fight` endpoint composes them and returns a slim playback. Recorded tapes move to display-and-regression only — no fixture supplies a starting position on the request path.

**Tech Stack:** Node ESM (no build step, no dependencies), `node:test` + `node:assert/strict`, Python 3 + stdlib `sqlite3` for the one-time derivation and export tools.

**Spec:** `docs/superpowers/specs/2026-08-07-cleanroom-viewer-free-selection-design.md`

## Global Constraints

- Repository root for all paths: `D:/AI/aoe2_matchup`. All commands run from there.
- Engine modules under `aoe2x/js_simulation/src/` take no new runtime dependencies and read no files at runtime except through an injected loader.
- Tests run with `node --test aoe2x/js_simulation/tests`. Every task leaves this green.
- Calibrated engine configuration is `engagement: "pursuit"`, `orders: true`. After Task 1 these are the committed defaults.
- Purchase cost weights are exactly `food + wood + 1.5 * gold`, over `ref_units.base_cost_*` (NOT `final_cost_*`).
- Army size cap per side is 21, which is what the archive recorded. A side-2 siege block caps at 16 (`sideCapacity(2, "siege")`). Counts beyond a family's capacity are a clean error, never extrapolated geometry.
- Existing endpoints `/api/matchup/*` and `/api/champion/*` keep their current behaviour and response shape. They are regression surface; the viewer stops calling them.
- Commit on the current branch (`codex/cleanroom-champion-sim`). Do not check out or push `staging` or `main`.

---

## File Structure

| Path | Responsibility |
|---|---|
| `aoe2x/js_simulation/src/combat/experiments.js` | *modify* — config from a defaults object, env overrides |
| `aoe2x/js_simulation/src/combat/ai-orders.js` | *modify* — same, for `ORDERS_ENABLED` |
| `aoe2x/js_simulation/src/engine-config.js` | *create* — the one place calibrated defaults live |
| `aoe2x/js_simulation/tools/derive_placement.py` | *create* — one-time analysis of `spawns.json` → generated table |
| `aoe2x/js_simulation/src/placement-table.js` | *create, generated* — ordered cell sequence per family |
| `aoe2x/js_simulation/src/placement.js` | *create* — `placeArmy`, `resolveFamily`, `sideCapacity` |
| `aoe2x/js_simulation/src/unit-registry.js` | *create* — 14 units: slug, label, civ, master, fixture, class, baseCost |
| `aoe2x/js_simulation/src/purchase.js` | *create* — `weightedCost`, `deriveCounts` |
| `aoe2x/js_simulation/src/fight.js` | *create* — compose registry + placement + engine → slim playback |
| `aoe2x/js_simulation/server.mjs` | *modify* — add `/api/units` and `/api/fight` |
| `aoe2x/js_simulation/viewer/index.html` | *modify* — two unit selects + two count inputs |
| `aoe2x/js_simulation/viewer/app.js` | *modify* — drive `/api/fight`, read slim snapshots |

---

### Task 1: Pin the calibrated engine configuration

Today `src/combat/experiments.js` and `src/combat/ai-orders.js` read `process.env` at module load. The corpus runs under `AOE2X_EXP_ENGAGEMENT=pursuit AOE2X_EXP_ORDERS=1`; the README's start command sets neither, so the viewer silently runs a different engine. This task makes the calibrated values the committed defaults and proves the engine's output is unchanged when they were previously supplied by env.

**Files:**
- Create: `aoe2x/js_simulation/src/engine-config.js`
- Create: `aoe2x/js_simulation/tools/capture_config_baseline.mjs`
- Create: `aoe2x/js_simulation/tests/fixtures/config_baseline.json` (generated)
- Modify: `aoe2x/js_simulation/src/combat/experiments.js:38-52`
- Modify: `aoe2x/js_simulation/src/combat/ai-orders.js:33-36`
- Test: `aoe2x/js_simulation/tests/engine-config.test.mjs`

**Interfaces:**
- Consumes: nothing.
- Produces: `src/engine-config.js` exporting `ENGINE_CONFIG` — a frozen object with keys `engagement` (string), `pursuit` (string), `orders` (boolean), `avoid` (string), `step` (string), `minRange` (string), `kiteEngage` (string). `experiments.js` keeps its existing named exports (`ENGAGEMENT_FOLLOWS_PURSUIT`, `REEVALUATE_EVERY_TICK`, `REEVALUATE_ON_BLOCKED`, `REEVALUATE_ON_SWING`, `AVOID_ALL_BODIES`, `BIMODAL_STEP`, `STEER_AROUND_BODIES`, `MIN_RANGE_SUPPRESSES_SHOOTER`, `KITE_ENGAGE_BLOCKER`, `ANY_EXPERIMENT`, `shouldReevaluatePursuit`, `describeExperiment`) with identical types. `ai-orders.js` keeps `ORDERS_ENABLED` (boolean).

- [ ] **Step 1: Capture the pre-change baseline**

Write `aoe2x/js_simulation/tools/capture_config_baseline.mjs`:

```javascript
// Capture the current engine output for every recorded matchup ratio, so the
// config-pinning change can be proven output-neutral. Run this BEFORE editing
// experiments.js / ai-orders.js, with the calibrated flags set.
import { writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { matchupNames, matchupPlayback, matchupRatios } from "../src/matchup-playback.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = pathToFileURL(path.resolve(here, "..") + "/");

const rows = [];
for (const name of matchupNames()) {
  for (const ratio of await matchupRatios(root, name)) {
    const playback = await matchupPlayback(root, name, ratio);
    rows.push({
      name,
      ratio,
      ticks: playback.ticks,
      winnerOwner: playback.winnerOwner,
      winnerHp: playback.winnerHp,
      finalStateHash: playback.finalStateHash,
      eventLogHash: playback.eventLogHash,
    });
  }
}
rows.sort((a, b) => (a.name === b.name ? a.ratio.localeCompare(b.ratio) : a.name.localeCompare(b.name)));
writeFileSync(
  path.join(here, "..", "tests", "fixtures", "config_baseline.json"),
  `${JSON.stringify({ schemaVersion: 1, rows }, null, 2)}\n`,
);
console.log(`captured ${rows.length} ratios`);
```

Then run it with the flags explicitly set:

```bash
cd /d/AI/aoe2_matchup && mkdir -p aoe2x/js_simulation/tests/fixtures && AOE2X_EXP_ENGAGEMENT=pursuit AOE2X_EXP_ORDERS=1 node aoe2x/js_simulation/tools/capture_config_baseline.mjs
```

Expected: prints `captured N ratios` where N is at least 100, and writes `tests/fixtures/config_baseline.json`.

- [ ] **Step 2: Write the failing test**

Create `aoe2x/js_simulation/tests/engine-config.test.mjs`:

```javascript
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

import { ENGINE_CONFIG } from "../src/engine-config.js";
import { ENGAGEMENT_FOLLOWS_PURSUIT } from "../src/combat/experiments.js";
import { ORDERS_ENABLED } from "../src/combat/ai-orders.js";
import { matchupPlayback } from "../src/matchup-playback.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = pathToFileURL(path.resolve(here, "..") + "/");

test("calibrated configuration is the committed default", () => {
  assert.equal(ENGINE_CONFIG.engagement, "pursuit");
  assert.equal(ENGINE_CONFIG.orders, true);
  assert.equal(ENGAGEMENT_FOLLOWS_PURSUIT, true);
  assert.equal(ORDERS_ENABLED, true);
});

test("pinning the config changes no engine output", async () => {
  const baseline = JSON.parse(await readFile(
    new URL("./fixtures/config_baseline.json", import.meta.url), "utf8"));
  assert.ok(baseline.rows.length > 0, "baseline must not be empty");
  for (const row of baseline.rows) {
    const playback = await matchupPlayback(root, row.name, row.ratio);
    assert.equal(playback.ticks, row.ticks, `${row.name} ${row.ratio} ticks`);
    assert.equal(playback.winnerOwner, row.winnerOwner, `${row.name} ${row.ratio} winner`);
    assert.equal(playback.winnerHp, row.winnerHp, `${row.name} ${row.ratio} winnerHp`);
    assert.equal(playback.finalStateHash, row.finalStateHash, `${row.name} ${row.ratio} state hash`);
    assert.equal(playback.eventLogHash, row.eventLogHash, `${row.name} ${row.ratio} event hash`);
  }
});
```

- [ ] **Step 3: Run the test with no env flags, verify it fails**

```bash
cd /d/AI/aoe2_matchup && node --test aoe2x/js_simulation/tests/engine-config.test.mjs
```

Expected: FAIL — `Cannot find module .../src/engine-config.js`.

- [ ] **Step 4: Create the config module**

Create `aoe2x/js_simulation/src/engine-config.js`:

```javascript
// The calibrated engine configuration, as committed defaults.
//
// These are the values every number in docs/ was measured under. They used to
// live only in environment variables, which meant a viewer started per the
// README ran a different engine than the corpus. Environment variables still
// override, so experiment sweeps work exactly as before.
const DEFAULTS = Object.freeze({
  engagement: "pursuit",
  pursuit: "",
  orders: true,
  avoid: "",
  step: "",
  minRange: "",
  kiteEngage: "",
});


function envString(name, fallback) {
  const value = process.env?.[name];
  return value === undefined || value === "" ? fallback : value;
}


function envBoolean(name, fallback) {
  const value = process.env?.[name];
  if (value === undefined || value === "") return fallback;
  return value === "1";
}


export const ENGINE_CONFIG = Object.freeze({
  engagement: envString("AOE2X_EXP_ENGAGEMENT", DEFAULTS.engagement),
  pursuit: envString("AOE2X_EXP_PURSUIT", DEFAULTS.pursuit),
  orders: envBoolean("AOE2X_EXP_ORDERS", DEFAULTS.orders),
  avoid: envString("AOE2X_EXP_AVOID", DEFAULTS.avoid),
  step: envString("AOE2X_EXP_STEP", DEFAULTS.step),
  minRange: envString("AOE2X_EXP_MINRANGE", DEFAULTS.minRange),
  kiteEngage: envString("AOE2X_EXP_KITE_ENGAGE", DEFAULTS.kiteEngage),
});
```

Note the `process.env?.` optional chaining: it makes these modules load in a browser, where `process` is undefined. That is not the goal of this task, but it costs nothing and removes the only two loader-time blockers.

- [ ] **Step 5: Point experiments.js at the config module**

In `aoe2x/js_simulation/src/combat/experiments.js`, replace the seven `process.env` reads (lines 38–52) with reads from `ENGINE_CONFIG`. Add the import at the top of the file, below the existing comment block:

```javascript
import { ENGINE_CONFIG } from "../engine-config.js";

const engagement = ENGINE_CONFIG.engagement;
const pursuit = ENGINE_CONFIG.pursuit;
const orders = ENGINE_CONFIG.orders ? "1" : "";
const avoid = ENGINE_CONFIG.avoid;
const step = ENGINE_CONFIG.step;
const minRange = ENGINE_CONFIG.minRange;
const kiteEngage = ENGINE_CONFIG.kiteEngage;
```

Leave every line below unchanged — the validation blocks, the derived `export const` booleans, `shouldReevaluatePursuit` and `describeExperiment` all keep working because the local variable names and types are identical.

- [ ] **Step 6: Point ai-orders.js at the config module**

In `aoe2x/js_simulation/src/combat/ai-orders.js`, replace line 33:

```javascript
export const ORDERS_ENABLED = process.env.AOE2X_EXP_ORDERS === "1";
```

with:

```javascript
import { ENGINE_CONFIG } from "../engine-config.js";

export const ORDERS_ENABLED = ENGINE_CONFIG.orders;
```

Move the `import` to the top of the file with the other imports. Leave line 36 (`RESCUE_DISABLED`) alone — it is a debug-only switch with no calibrated value, and it already defaults off.

- [ ] **Step 7: Run the test with no env flags, verify it passes**

```bash
cd /d/AI/aoe2_matchup && node --test aoe2x/js_simulation/tests/engine-config.test.mjs
```

Expected: PASS, both tests. This is the proof: with no environment variables set at all, the engine now reproduces every hash captured under the flags.

- [ ] **Step 8: Run the whole suite**

```bash
cd /d/AI/aoe2_matchup && node --test aoe2x/js_simulation/tests
```

Expected: no new failures compared to before this task. Record the pass/fail counts; the suite has known pre-existing failures and those may remain.

- [ ] **Step 9: Update the README run command**

In `aoe2x/js_simulation/README.md`, the "Run the viewer" section currently shows a bare `node aoe2x/js_simulation/server.mjs`. Add one sentence directly beneath the code block:

```markdown
The calibrated configuration (`engagement=pursuit`, `orders=1`) is now the
committed default in `src/engine-config.js`; the `AOE2X_EXP_*` environment
variables still override it for experiment sweeps.
```

- [ ] **Step 10: Commit**

```bash
cd /d/AI/aoe2_matchup && git add aoe2x/js_simulation/src/engine-config.js aoe2x/js_simulation/src/combat/experiments.js aoe2x/js_simulation/src/combat/ai-orders.js aoe2x/js_simulation/tools/capture_config_baseline.mjs aoe2x/js_simulation/tests/engine-config.test.mjs aoe2x/js_simulation/tests/fixtures/config_baseline.json aoe2x/js_simulation/README.md && git commit -m "feat(sim): pin the calibrated engine config as the committed default

The corpus runs under AOE2X_EXP_ENGAGEMENT=pursuit AOE2X_EXP_ORDERS=1, read
from process.env at module load; the README's start command sets neither, so a
viewer started as documented ran a different engine than every measured number.

Config now lives in src/engine-config.js with the calibrated values as
defaults, env still overriding. Proven output-neutral: every recorded matchup
ratio reproduces its pre-change ticks, winner, winner HP, final-state hash and
event-log hash with no environment variables set.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Placement module derived from the recorded spawns

`calibration/fixtures/spawns.json` holds 339 recorded layouts (678 side-layouts). This task turns them into an exact ordered cell sequence per family, and gates it on regenerating every recorded layout.

**The key is `(owner, family)` and nothing else.** This was measured, not guessed: with that key, all 678 recorded side-layouts regenerate exactly. Two earlier keyings do NOT work and must not be reintroduced — keying on the band edge collides (kite and rvr both put side 3 at edge 10.5 with different blocks; melee-vs-melee and siege-vs-melee both put side 2 at edge 6.5 with different blocks), and the corpus's own three-way category collides too (it lumps siege-vs-melee in with melee-vs-melee). The band edge is an *output* of the fill order — it varies with army size inside a single family — so it is not a parameter of anything.

The four families, decided from the two units' combat classes:

| family | condition | meaning |
|---|---|---|
| `rvr` | both sides ranged (`mobile_ranged` or `siege_ranged`) | ranged vs ranged |
| `kite` | exactly one side `mobile_ranged`, the other melee | the kiting archive |
| `siege` | exactly one side `siege_ranged`, the other melee | siege vs melee |
| `waves` | both sides melee | the melee archive |

Order matters: test `rvr` first, then `kite`, then `siege`, then `waves`.

Owner 2 fills from the front of its own half, owner 3 from the front of the other; the derivation recovers the order from the data rather than assuming a shape.

**Files:**
- Create: `aoe2x/js_simulation/tools/derive_placement.py`
- Create: `aoe2x/js_simulation/src/placement-table.js` (generated)
- Create: `aoe2x/js_simulation/src/placement.js`
- Test: `aoe2x/js_simulation/tests/placement.test.mjs`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `src/placement-table.js` exporting `PLACEMENT_TABLE` — a frozen object keyed `"<owner>@<family>"` (e.g. `"2@kite"`), each value a frozen array of `[x, y]` pairs in fill order; and `PLACEMENT_PROVENANCE` — frozen `{ source, layouts, sideLayouts, exact, residue }`.
  - `src/placement.js` exporting `placeArmy({ owner, count, family })` → frozen array of `{ x, y }`; `resolveFamily({ side2Class, side3Class })` → one of `"rvr" | "kite" | "siege" | "waves"`; `sideCapacity(owner, family)` → integer, the number of derived cells available.

- [ ] **Step 1: Write the derivation tool**

Create `aoe2x/js_simulation/tools/derive_placement.py`:

```python
"""Derive the tapes' spawn fill order and emit src/placement-table.js.

Within a family keyed by (owner, family), the recorded layouts nest: the
N-unit layout is the first N cells of a larger layout in the same family. So
the fill order is recoverable exactly -- walk the family's layouts smallest
first and append whatever each one adds.

    python aoe2x/js_simulation/tools/derive_placement.py
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPAWNS = ROOT / "calibration" / "fixtures" / "spawns.json"
OUTPUT = ROOT / "aoe2x" / "js_simulation" / "src" / "placement-table.js"

SIEGE = {"heavy_scorpion", "siege_onager"}
MOBILE = {"arbalester", "hand_cannoneer", "heavy_cav_archer", "imp_elite_skirm"}


def family(label: str) -> str:
    """Which spawn family a recorded matchup label belongs to.

    Mirrors resolveFamily in src/placement.js exactly; the test asserts the two
    agree on every recorded label.
    """
    left, right = re.sub(r"_r\d+$", "", label).split("__vs__")
    ranged = {unit for unit in (left, right) if unit in SIEGE or unit in MOBILE}
    if len(ranged) == 2 or (len(ranged) == 1 and left == right):
        return "rvr"
    if left in MOBILE or right in MOBILE:
        return "kite"
    if left in SIEGE or right in SIEGE:
        return "siege"
    return "waves"


def sort_key(owner: str, cell: tuple[float, float]) -> tuple[float, float]:
    """Deterministic order for cells a single recorded step adds at once.

    Cells added together are interchangeable for reproducing the recorded
    layouts -- any order within one increment yields the same set at every
    recorded size. The order only becomes observable at counts that fall
    between two recorded sizes, so it is fixed here: front rank first, then
    left to right.
    """
    x, y = cell
    return (-y if owner == "2" else y, x)


def main() -> None:
    spawns = json.loads(SPAWNS.read_text())
    families: dict[tuple[str, str], list[frozenset]] = defaultdict(list)
    side_layouts = 0
    for label, sides in spawns.items():
        group = family(label)
        for owner in ("2", "3"):
            points = frozenset(tuple(point) for point in sides[owner])
            families[(owner, group)].append(points)
            side_layouts += 1

    table: dict[str, list[list[float]]] = {}
    exact = 0
    residue: list[dict] = []
    for (owner, group), layouts in sorted(families.items()):
        order: list[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()
        for layout in sorted(layouts, key=len):
            added = sorted(layout - seen, key=lambda c: sort_key(owner, c))
            order.extend(added)
            seen.update(added)
        for layout in layouts:
            if set(order[: len(layout)]) == set(layout):
                exact += 1
            else:
                residue.append({
                    "owner": owner,
                    "family": group,
                    "count": len(layout),
                    "missing": sorted(map(list, set(layout) - set(order[: len(layout)]))),
                    "extra": sorted(map(list, set(order[: len(layout)]) - set(layout))),
                })
        table[f"{owner}@{group}"] = [list(cell) for cell in order]

    print(f"side-layouts {side_layouts}  exact {exact}  residue {len(residue)}")
    for row in residue:
        print("  RESIDUE", row)
    for key, cells in sorted(table.items()):
        print(f"  {key}: {len(cells)} cells")

    body = json.dumps(table, indent=2, sort_keys=True)
    provenance = json.dumps({
        "source": "calibration/fixtures/spawns.json",
        "layouts": len(spawns),
        "sideLayouts": side_layouts,
        "exact": exact,
        "residue": len(residue),
    }, indent=2, sort_keys=True)
    OUTPUT.write_text(
        "// GENERATED by tools/derive_placement.py -- do not edit by hand.\n"
        "//\n"
        "// Ordered spawn cells per family, keyed \"<owner>@<family>\". Take the\n"
        "// first N cells for an N-unit army. The key is (owner, family) and\n"
        "// nothing else: band edge is an output of the fill order, not an input.\n"
        f"export const PLACEMENT_TABLE = Object.freeze({body});\n"
        "\n"
        f"export const PLACEMENT_PROVENANCE = Object.freeze({provenance});\n",
        encoding="utf8",
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the derivation and confirm zero residue**

```bash
cd /d/AI/aoe2_matchup && python aoe2x/js_simulation/tools/derive_placement.py
```

Expected, exactly: `side-layouts 678  exact 678  residue 0`, then eight family lines. Seven of them read `21 cells`; `2@siege` reads `16 cells`.

If the residue is not 0, stop and report BLOCKED with the printed residue rows. Do not add per-layout exceptions, do not special-case a matchup, and do not relax the test — the key has been measured to work, so a residue means something else is wrong and needs diagnosing, not patching.

- [ ] **Step 3: Write the failing placement test**

Create `aoe2x/js_simulation/tests/placement.test.mjs`:

```javascript
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { PLACEMENT_PROVENANCE, PLACEMENT_TABLE } from "../src/placement-table.js";
import { placeArmy, resolveFamily, sideCapacity } from "../src/placement.js";

const spawns = JSON.parse(await readFile(
  new URL("../../../calibration/fixtures/spawns.json", import.meta.url), "utf8"));

const SIEGE = new Set(["heavy_scorpion", "siege_onager"]);
const MOBILE = new Set(["arbalester", "hand_cannoneer", "heavy_cav_archer", "imp_elite_skirm"]);
const classOf = (unit) => (
  SIEGE.has(unit) ? "siege_ranged" : MOBILE.has(unit) ? "mobile_ranged" : "melee");
const key = (points) => points.map(([x, y]) => `${x},${y}`).sort().join(" ");

// The recorded label names both units, so resolveFamily can be driven from the
// archive itself rather than from a second hand-written classification.
function familyOfLabel(label) {
  const [left, right] = label.replace(/_r\d+$/, "").split("__vs__");
  return resolveFamily({ side2Class: classOf(left), side3Class: classOf(right) });
}

test("placeArmy regenerates every recorded side-layout exactly", () => {
  let checked = 0;
  for (const [label, sides] of Object.entries(spawns)) {
    const family = familyOfLabel(label);
    for (const owner of [2, 3]) {
      const points = sides[String(owner)];
      const produced = placeArmy({ owner, count: points.length, family });
      assert.equal(
        key(produced.map(({ x, y }) => [x, y])),
        key(points),
        `${label} side ${owner} (${points.length} units, family ${family})`,
      );
      checked += 1;
    }
  }
  assert.equal(checked, 678, "every recorded side-layout must be checked");
});

test("the derivation left no residue", () => {
  assert.equal(PLACEMENT_PROVENANCE.residue, 0);
  assert.equal(PLACEMENT_PROVENANCE.exact, 678);
  assert.equal(PLACEMENT_PROVENANCE.sideLayouts, 678);
});

test("families are decided by combat class", () => {
  assert.equal(resolveFamily({ side2Class: "melee", side3Class: "melee" }), "waves");
  assert.equal(resolveFamily({ side2Class: "siege_ranged", side3Class: "melee" }), "siege");
  assert.equal(resolveFamily({ side2Class: "melee", side3Class: "siege_ranged" }), "siege");
  assert.equal(resolveFamily({ side2Class: "mobile_ranged", side3Class: "melee" }), "kite");
  assert.equal(resolveFamily({ side2Class: "melee", side3Class: "mobile_ranged" }), "kite");
  assert.equal(resolveFamily({ side2Class: "mobile_ranged", side3Class: "mobile_ranged" }), "rvr");
  assert.equal(resolveFamily({ side2Class: "mobile_ranged", side3Class: "siege_ranged" }), "rvr");
  assert.equal(resolveFamily({ side2Class: "siege_ranged", side3Class: "siege_ranged" }), "rvr");
});

test("every family has a derived sequence and the recorded capacities", () => {
  for (const owner of [2, 3]) {
    for (const family of ["rvr", "kite", "siege", "waves"]) {
      assert.ok(PLACEMENT_TABLE[`${owner}@${family}`], `missing ${owner}@${family}`);
    }
  }
  // Side 2's siege block is the one the archive never grew past 16.
  assert.equal(sideCapacity(2, "siege"), 16);
  assert.equal(sideCapacity(3, "siege"), 21);
  assert.equal(sideCapacity(2, "waves"), 21);
  assert.equal(sideCapacity(3, "kite"), 21);
});

test("positions within one army are distinct", () => {
  for (const owner of [2, 3]) {
    for (const family of ["rvr", "kite", "siege", "waves"]) {
      const cells = placeArmy({ owner, count: sideCapacity(owner, family), family });
      const seen = new Set(cells.map(({ x, y }) => `${x},${y}`));
      assert.equal(seen.size, cells.length, `${owner}@${family} has duplicate cells`);
    }
  }
});

test("a count beyond the derived sequence is rejected", () => {
  assert.throws(
    () => placeArmy({ owner: 2, count: 17, family: "siege" }),
    /only 16 cells/);
  assert.throws(
    () => placeArmy({ owner: 3, count: 22, family: "waves" }),
    /only 21 cells/);
});

test("bad arguments are rejected", () => {
  assert.throws(() => placeArmy({ owner: 1, count: 5, family: "waves" }), /owner must be 2 or 3/);
  assert.throws(() => placeArmy({ owner: 2, count: 0, family: "waves" }), /count must be/);
  assert.throws(() => placeArmy({ owner: 2, count: 5, family: "nope" }), /unknown family nope/);
});
```

- [ ] **Step 4: Run it, verify it fails**

```bash
cd /d/AI/aoe2_matchup && node --test aoe2x/js_simulation/tests/placement.test.mjs
```

Expected: FAIL — `Cannot find module .../src/placement.js`.

- [ ] **Step 5: Write the placement module**

Create `aoe2x/js_simulation/src/placement.js`:

```javascript
// Spawn placement, derived from the recorded tapes and verified against every
// one of them (tests/placement.test.mjs). No fixture is read at runtime.
//
// The only thing that selects a block is (owner, family). Band edge is NOT a
// key: the same family sits at different edges depending on army size, and two
// different families share an edge -- keying on it collides.
import { PLACEMENT_TABLE } from "./placement-table.js";


const FAMILIES = Object.freeze(["rvr", "kite", "siege", "waves"]);
const RANGED = new Set(["mobile_ranged", "siege_ranged"]);


// Which spawn block a pairing uses, from the two units' combat classes. The
// order of these tests is the archive's own: both-ranged wins over one-mobile,
// which wins over one-siege.
export function resolveFamily({ side2Class, side3Class }) {
  const bothRanged = RANGED.has(side2Class) && RANGED.has(side3Class);
  if (bothRanged) return "rvr";
  if (side2Class === "mobile_ranged" || side3Class === "mobile_ranged") return "kite";
  if (side2Class === "siege_ranged" || side3Class === "siege_ranged") return "siege";
  return "waves";
}


function cellsFor(owner, family) {
  if (owner !== 2 && owner !== 3) {
    throw new RangeError(`owner must be 2 or 3, got ${owner}`);
  }
  if (!FAMILIES.includes(family)) {
    throw new RangeError(`unknown family ${family}`);
  }
  return PLACEMENT_TABLE[`${owner}@${family}`];
}


// How many units this side can field in this family. The archive never grew a
// side-2 siege block past 16, so that is the honest ceiling: beyond it there is
// no measured geometry, and inventing some would be exactly the fitting this
// simulator exists to avoid.
export function sideCapacity(owner, family) {
  return cellsFor(owner, family).length;
}


export function placeArmy({ owner, count, family }) {
  const cells = cellsFor(owner, family);
  if (!Number.isSafeInteger(count) || count < 1) {
    throw new RangeError(`count must be a positive integer, got ${count}`);
  }
  if (count > cells.length) {
    throw new RangeError(
      `owner ${owner} family ${family} has only ${cells.length} cells, asked for ${count}`);
  }
  return Object.freeze(cells.slice(0, count).map(
    ([x, y]) => Object.freeze({ x, y })));
}
```

- [ ] **Step 6: Run it, verify it passes**

```bash
cd /d/AI/aoe2_matchup && node --test aoe2x/js_simulation/tests/placement.test.mjs
```

Expected: PASS, seven tests. The first is the gate: 678 recorded side-layouts, all regenerated exactly.

- [ ] **Step 7: Confirm no new suite failures**

```bash
cd /d/AI/aoe2_matchup && node --test aoe2x/js_simulation/tests 2>&1 | grep -E "^# (tests|pass|fail) "
```

Expected: `# fail 31` — unchanged from before this task. The test count rises by 7.

- [ ] **Step 8: Commit**

```bash
cd /d/AI/aoe2_matchup && git add aoe2x/js_simulation/tools/derive_placement.py aoe2x/js_simulation/src/placement-table.js aoe2x/js_simulation/src/placement.js aoe2x/js_simulation/tests/placement.test.mjs && git commit -m "feat(sim): programmatic spawn placement derived from the tapes

Within a family the recorded layouts nest -- the N-unit layout is the first N
cells of a larger one -- so the fill order is recoverable exactly rather than
fitted. derive_placement.py walks each family smallest-first and emits the
ordered cell sequence; placeArmy takes the first N.

The key is (owner, family) and nothing else, measured rather than assumed.
Keying on band edge collides: kite and rvr share side-3 edge 10.5 with
different blocks, and melee-vs-melee and siege-vs-melee share side-2 edge 6.5
with different blocks. Band edge is an output of the fill order -- it moves with
army size inside one family.

Four families from the two units' combat classes: both ranged, one mobile
ranged, one siege, both melee. Gated on regenerating all 678 recorded
side-layouts exactly.

Capacity is what the archive recorded: 21 a side, except a side-2 siege block
which never grew past 16. Beyond that there is no measured geometry.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Unit registry with base costs

The registry is the single place that answers "what units can this viewer run, what class is each, and what does each cost". Base costs come from `ref_units.base_cost_*` in `data/golden/aoe2_reference.db` — the same database the website serves. The civ-adjusted `final_cost_*` column must not be used: it disagrees with the calibrated costs for Berbers Hussar (64 vs 80), Berbers Heavy Camel (116 vs 145) and Slavs Siege Onager (308.5 vs 362.5).

**Files:**
- Create: `aoe2x/js_simulation/tools/export_unit_costs.py`
- Create: `aoe2x/js_simulation/src/unit-registry.js`
- Test: `aoe2x/js_simulation/tests/unit-registry.test.mjs`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `src/unit-registry.js` exporting `UNIT_REGISTRY` — a frozen array of frozen rows `{ slug, label, civ, master, fixture, class, baseCost: { food, wood, gold } }`; `unitBySlug(slug)` → row or `undefined`; `UNIT_SLUGS` — frozen array of the 14 slugs in registry order.

- [ ] **Step 1: Write the cost export tool**

Create `aoe2x/js_simulation/tools/export_unit_costs.py`:

```python
"""Print base costs for the registry's units, straight from the reference DB.

The purchase rule uses dat BASE costs, not the civ-adjusted final costs -- a
Berbers Hussar costs 80 in the rule and 64 after the civ bonus. This prints
both so the registry's committed numbers can be eyeballed against the source.

    python aoe2x/js_simulation/tools/export_unit_costs.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DB = ROOT / "data" / "golden" / "aoe2_reference.db"

UNITS = [
    ("arbalester", "Chinese"),
    ("champion", "Chinese"),
    ("elite_elephant", "Burmese"),
    ("elite_fire_lancer", "Chinese"),
    ("elite_steppe", "Cumans"),
    ("halberdier", "Bulgarians"),
    ("hand_cannoneer", "Bohemians"),
    ("heavy_camel", "Berbers"),
    ("heavy_cav_archer", "Saracens"),
    ("heavy_scorpion", "Japanese"),
    ("hussar", "Berbers"),
    ("imp_elite_skirm", "Chinese"),
    ("paladin", "Spanish"),
    ("siege_onager", "Slavs"),
]

QUERY = """
    SELECT base_cost_food, base_cost_wood, base_cost_gold,
           final_cost_food, final_cost_wood, final_cost_gold
    FROM ref_units
    WHERE unit_slug = ? AND civ_name = ? AND age = 'Imperial'
"""


def main() -> None:
    uri = f"{DB.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        print(f"{'slug':20s} {'civ':12s} {'base F/W/G':>18s} {'weighted':>9s} {'final weighted':>15s}")
        for slug, civ in UNITS:
            rows = connection.execute(QUERY, (slug, civ)).fetchall()
            if len(rows) != 1:
                raise SystemExit(f"expected exactly one {civ} Imperial {slug}, found {len(rows)}")
            bf, bw, bg, ff, fw, fg = (value or 0 for value in rows[0])
            base = bf + bw + 1.5 * bg
            final = ff + fw + 1.5 * fg
            flag = "" if abs(base - final) < 1e-9 else "   <- civ bonus differs"
            print(f"{slug:20s} {civ:12s} {bf:>5}/{bw:>5}/{bg:>5} {base:>9.1f} {final:>15.1f}{flag}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it and confirm the numbers**

```bash
cd /d/AI/aoe2_matchup && python aoe2x/js_simulation/tools/export_unit_costs.py
```

Expected: 14 rows. The `weighted` column must read exactly 92.5, 80.0, 205.0, 112.5, 130.0, 60.0, 120.0, 145.0, 130.0, 187.5, 80.0, 60.0, 172.5, 362.5 in the printed (alphabetical) order. Exactly three rows carry the `<- civ bonus differs` flag: `heavy_camel`, `hussar`, `siege_onager`.

- [ ] **Step 3: Write the failing test**

Create `aoe2x/js_simulation/tests/unit-registry.test.mjs`:

```javascript
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { UNIT_REGISTRY, UNIT_SLUGS, unitBySlug } from "../src/unit-registry.js";

// The cost scalars the calibrated corpus was purchased with.
const CALIBRATED_COST = {
  arbalester: 92.5,
  champion: 80.0,
  elite_elephant: 205.0,
  elite_fire_lancer: 112.5,
  elite_steppe: 130.0,
  halberdier: 60.0,
  hand_cannoneer: 120.0,
  heavy_camel: 145.0,
  heavy_cav_archer: 130.0,
  heavy_scorpion: 187.5,
  hussar: 80.0,
  imp_elite_skirm: 60.0,
  paladin: 172.5,
  siege_onager: 362.5,
};

test("registry holds exactly the fourteen fixtured units", () => {
  assert.equal(UNIT_REGISTRY.length, 14);
  assert.deepEqual([...UNIT_SLUGS].sort(), Object.keys(CALIBRATED_COST).sort());
});

test("base costs reproduce the calibrated cost scalars", () => {
  for (const row of UNIT_REGISTRY) {
    const { food, wood, gold } = row.baseCost;
    assert.equal(food + wood + 1.5 * gold, CALIBRATED_COST[row.slug], row.slug);
  }
});

test("every registry row points at a real mechanics fixture with a matching master", async () => {
  for (const row of UNIT_REGISTRY) {
    const mechanics = JSON.parse(await readFile(
      new URL(`../fixtures/unit_stats/${row.fixture}`, import.meta.url), "utf8"));
    assert.equal(mechanics.unit_master, row.master, `${row.slug} master`);
    assert.equal(mechanics.civilization, row.civ, `${row.slug} civ`);
  }
});

test("exactly four units are mobile ranged", () => {
  const kiters = UNIT_REGISTRY.filter((row) => row.class === "mobile_ranged").map((r) => r.slug);
  assert.deepEqual(kiters.sort(),
    ["arbalester", "hand_cannoneer", "heavy_cav_archer", "imp_elite_skirm"]);
});

test("class matches the fixture's attack range", async () => {
  for (const row of UNIT_REGISTRY) {
    const mechanics = JSON.parse(await readFile(
      new URL(`../fixtures/unit_stats/${row.fixture}`, import.meta.url), "utf8"));
    const ranged = row.class === "mobile_ranged" || row.class === "siege_ranged";
    // Elite Steppe Lancer is a reach fighter at range 1, not a ranged unit.
    const expectRanged = mechanics.attack_range_tiles > 1.0;
    assert.equal(ranged, expectRanged, `${row.slug} range ${mechanics.attack_range_tiles}`);
  }
});

test("unitBySlug finds and misses cleanly", () => {
  assert.equal(unitBySlug("paladin").master, 569);
  assert.equal(unitBySlug("not_a_unit"), undefined);
});
```

- [ ] **Step 4: Run it, verify it fails**

```bash
cd /d/AI/aoe2_matchup && node --test aoe2x/js_simulation/tests/unit-registry.test.mjs
```

Expected: FAIL — `Cannot find module .../src/unit-registry.js`.

- [ ] **Step 5: Write the registry**

Create `aoe2x/js_simulation/src/unit-registry.js`:

```javascript
// The units this simulator can run: one row per tape-measured mechanics
// fixture. `class` drives two things -- which side kites, and how far apart the
// two armies start (see placement.resolveFamily).
//
// baseCost is ref_units.base_cost_* from data/golden/aoe2_reference.db, the
// same database the website serves. It is deliberately the BASE column, not
// final_cost_*: the purchase rule buys at dat base prices, so a Berbers Hussar
// costs 80 here even though the civ bonus makes it 64 in game. Regenerate the
// numbers with tools/export_unit_costs.py.
const ROWS = [
  { slug: "arbalester", label: "Arbalester", civ: "Chinese", master: 492,
    fixture: "arbalester_chinese_imperial.json", class: "mobile_ranged",
    baseCost: { food: 0, wood: 25, gold: 45 } },
  { slug: "champion", label: "Champion", civ: "Chinese", master: 567,
    fixture: "champion_chinese_imperial.json", class: "melee",
    baseCost: { food: 50, wood: 0, gold: 20 } },
  { slug: "elite_elephant", label: "Elite Battle Elephant", civ: "Burmese", master: 1134,
    fixture: "elite_battle_elephant_burmese_imperial.json", class: "melee",
    baseCost: { food: 100, wood: 0, gold: 70 } },
  { slug: "elite_fire_lancer", label: "Elite Fire Lancer", civ: "Chinese", master: 1903,
    fixture: "elite_fire_lancer_chinese_imperial.json", class: "melee",
    baseCost: { food: 0, wood: 45, gold: 45 } },
  { slug: "elite_steppe", label: "Elite Steppe Lancer", civ: "Cumans", master: 1372,
    fixture: "elite_steppe_lancer_cumans_imperial.json", class: "melee",
    baseCost: { food: 70, wood: 0, gold: 40 } },
  { slug: "halberdier", label: "Halberdier", civ: "Bulgarians", master: 359,
    fixture: "halberdier_bulgarians_imperial.json", class: "melee",
    baseCost: { food: 35, wood: 25, gold: 0 } },
  { slug: "hand_cannoneer", label: "Hand Cannoneer", civ: "Bohemians", master: 5,
    fixture: "hand_cannoneer_bohemians_imperial.json", class: "mobile_ranged",
    baseCost: { food: 45, wood: 0, gold: 50 } },
  { slug: "heavy_camel", label: "Heavy Camel Rider", civ: "Berbers", master: 330,
    fixture: "heavy_camel_berbers_imperial.json", class: "melee",
    baseCost: { food: 55, wood: 0, gold: 60 } },
  { slug: "heavy_cav_archer", label: "Heavy Cav Archer", civ: "Saracens", master: 474,
    fixture: "heavy_cav_archer_saracens_imperial.json", class: "mobile_ranged",
    baseCost: { food: 0, wood: 40, gold: 60 } },
  { slug: "heavy_scorpion", label: "Heavy Scorpion", civ: "Japanese", master: 542,
    fixture: "heavy_scorpion_japanese_imperial.json", class: "siege_ranged",
    baseCost: { food: 0, wood: 75, gold: 75 } },
  { slug: "hussar", label: "Hussar", civ: "Berbers", master: 441,
    fixture: "hussar_berbers_imperial.json", class: "melee",
    baseCost: { food: 80, wood: 0, gold: 0 } },
  { slug: "imp_elite_skirm", label: "Elite Skirmisher", civ: "Chinese", master: 6,
    fixture: "elite_skirmisher_chinese_imperial.json", class: "mobile_ranged",
    baseCost: { food: 25, wood: 35, gold: 0 } },
  { slug: "paladin", label: "Paladin", civ: "Spanish", master: 569,
    fixture: "paladin_spanish_imperial.json", class: "melee",
    baseCost: { food: 60, wood: 0, gold: 75 } },
  { slug: "siege_onager", label: "Siege Onager", civ: "Slavs", master: 588,
    fixture: "siege_onager_slavs_imperial.json", class: "siege_ranged",
    baseCost: { food: 0, wood: 160, gold: 135 } },
];

export const UNIT_REGISTRY = Object.freeze(ROWS.map((row) => Object.freeze({
  ...row,
  baseCost: Object.freeze(row.baseCost),
})));

export const UNIT_SLUGS = Object.freeze(UNIT_REGISTRY.map(({ slug }) => slug));

const BY_SLUG = new Map(UNIT_REGISTRY.map((row) => [row.slug, row]));

export function unitBySlug(slug) {
  return BY_SLUG.get(slug);
}
```

- [ ] **Step 6: Run it, verify it passes**

```bash
cd /d/AI/aoe2_matchup && node --test aoe2x/js_simulation/tests/unit-registry.test.mjs
```

Expected: PASS, six tests.

- [ ] **Step 7: Commit**

```bash
cd /d/AI/aoe2_matchup && git add aoe2x/js_simulation/tools/export_unit_costs.py aoe2x/js_simulation/src/unit-registry.js aoe2x/js_simulation/tests/unit-registry.test.mjs && git commit -m "feat(sim): unit registry with base costs and combat class

One row per tape-measured mechanics fixture: slug, label, civ, master, fixture,
class, base cost. Class drives both the kite decision and the starting-distance
band; base cost drives the purchase solver.

Costs are ref_units.base_cost_*, not final_cost_*. The purchase rule buys at dat
base prices, so the civ-adjusted column is wrong for exactly three of the
fourteen: Berbers Hussar 64 vs 80, Berbers Heavy Camel 116 vs 145, Slavs Siege
Onager 308.5 vs 362.5. Gated on reproducing all fourteen calibrated cost
scalars, and on each row's master and civ matching its fixture.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Purchase solver

Derives the default army sizes for a pair. The rule is the one that reproduced the recorded army sizes 101/101: the cheaper side buys `min(21, floor(3000 / c))`, and the other side spends the same weighted budget.

**Files:**
- Create: `aoe2x/js_simulation/src/purchase.js`
- Test: `aoe2x/js_simulation/tests/purchase.test.mjs`

**Interfaces:**
- Consumes: `UNIT_REGISTRY`, `unitBySlug` from Task 3.
- Produces: `src/purchase.js` exporting `weightedCost({ food, wood, gold })` → number; `deriveCounts(slugA, slugB, { budget, cap })` → `{ countA, countB, costA, costB, spendA, spendB }`; `PURCHASE_BUDGET` (3000); `PURCHASE_CAP` (21).

- [ ] **Step 1: Write the failing test**

Create `aoe2x/js_simulation/tests/purchase.test.mjs`:

```javascript
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { deriveCounts, weightedCost } from "../src/purchase.js";

const corpus = JSON.parse(await readFile(
  new URL("../docs/data/standard_units_2026-08-07.json", import.meta.url), "utf8"));

// The corpus labels units by display name; the registry keys by slug.
const SLUG_BY_LABEL = {
  "Arbalester": "arbalester",
  "Champion": "champion",
  "Elite Battle Elephant": "elite_elephant",
  "Elite Fire Lancer": "elite_fire_lancer",
  "Elite Skirmisher": "imp_elite_skirm",
  "Elite Steppe Lancer": "elite_steppe",
  "Halberdier": "halberdier",
  "Hand Cannoneer": "hand_cannoneer",
  "Heavy Camel Rider": "heavy_camel",
  "Heavy Cav Archer": "heavy_cav_archer",
  "Heavy Scorpion": "heavy_scorpion",
  "Hussar": "hussar",
  "Paladin": "paladin",
  "Siege Onager": "siege_onager",
};

test("weightedCost charges gold at 1.5", () => {
  assert.equal(weightedCost({ food: 0, wood: 25, gold: 45 }), 92.5);
  assert.equal(weightedCost({ food: 80, wood: 0, gold: 0 }), 80);
});

test("deriveCounts reproduces every recorded army size", () => {
  assert.equal(corpus.length, 101);
  const wrong = [];
  for (const row of corpus) {
    const slugA = SLUG_BY_LABEL[row.side2.unit];
    const slugB = SLUG_BY_LABEL[row.side3.unit];
    const { countA, countB, costA, costB } = deriveCounts(slugA, slugB);
    if (countA !== row.side2.n || countB !== row.side3.n
        || costA !== row.side2.cost || costB !== row.side3.cost) {
      wrong.push(`${row.matchup}: got ${countA}v${countB} (${costA}/${costB}), `
        + `want ${row.side2.n}v${row.side3.n} (${row.side2.cost}/${row.side3.cost})`);
    }
  }
  assert.deepEqual(wrong, []);
});

test("a mirror matchup buys the cap on both sides", () => {
  const { countA, countB } = deriveCounts("champion", "champion");
  assert.equal(countA, 21);
  assert.equal(countB, 21);
});

test("an unknown slug is rejected", () => {
  assert.throws(() => deriveCounts("paladin", "trebuchet"), /unknown unit trebuchet/);
});
```

- [ ] **Step 2: Run it, verify it fails**

```bash
cd /d/AI/aoe2_matchup && node --test aoe2x/js_simulation/tests/purchase.test.mjs
```

Expected: FAIL — `Cannot find module .../src/purchase.js`.

- [ ] **Step 3: Write the solver**

Create `aoe2x/js_simulation/src/purchase.js`:

```javascript
// How many of each unit an even fight buys.
//
// Measured, not chosen: this rule reproduces the starting counts of all 101
// distinct matchups in the standard-units archive exactly. The cheaper side
// buys as many as a 3000 budget allows, capped at 21; the other side then
// spends that same weighted amount, which is what makes the fight even rather
// than the counts equal.
import { unitBySlug } from "./unit-registry.js";


export const PURCHASE_BUDGET = 3000;
export const PURCHASE_CAP = 21;

const GOLD_WEIGHT = 1.5;


export function weightedCost({ food = 0, wood = 0, gold = 0 } = {}) {
  return food + wood + GOLD_WEIGHT * gold;
}


function costFor(slug) {
  const unit = unitBySlug(slug);
  if (!unit) throw new RangeError(`unknown unit ${slug}`);
  return weightedCost(unit.baseCost);
}


export function deriveCounts(slugA, slugB, {
  budget = PURCHASE_BUDGET,
  cap = PURCHASE_CAP,
} = {}) {
  const costA = costFor(slugA);
  const costB = costFor(slugB);
  const cheaperIsA = costA <= costB;
  const cheapCost = cheaperIsA ? costA : costB;
  const dearCost = cheaperIsA ? costB : costA;

  const cheapCount = Math.min(cap, Math.floor(budget / cheapCost));
  const cheapSpend = cheapCount * cheapCost;
  const dearCount = Math.max(1, Math.floor(cheapSpend / dearCost));

  const countA = cheaperIsA ? cheapCount : dearCount;
  const countB = cheaperIsA ? dearCount : cheapCount;
  return {
    countA,
    countB,
    costA,
    costB,
    spendA: countA * costA,
    spendB: countB * costB,
  };
}
```

- [ ] **Step 4: Run it, verify it passes**

```bash
cd /d/AI/aoe2_matchup && node --test aoe2x/js_simulation/tests/purchase.test.mjs
```

Expected: PASS, four tests. The second one is the gate: 101 matchups, every count and cost exact.

If it fails on ties (two units of equal cost, e.g. Halberdier vs Elite Skirmisher at 60 each), read the failing rows: the tie-break is `costA <= costB`, meaning side 2 is treated as the cheaper side. Both sides buy the cap when costs are equal, so a tie cannot change the counts — a failure there means a cost is wrong in the registry, not the tie-break.

- [ ] **Step 5: Commit**

```bash
cd /d/AI/aoe2_matchup && git add aoe2x/js_simulation/src/purchase.js aoe2x/js_simulation/tests/purchase.test.mjs && git commit -m "feat(sim): purchase solver - derived army sizes from base costs

c = food + wood + 1.5*gold; the cheaper side buys min(21, floor(3000/c)); the
other side spends the same weighted budget. Gated on reproducing the starting
counts and cost scalars of all 101 distinct standard-unit matchups exactly.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Fight composition and the `/api/fight` endpoint

Composes registry + placement + purchase + engine into one request path that reads no tape roster, and returns a playback small enough to send. Today a 15v15 serialises to 101.1 MB, 86.1 MB of which is the mechanics object repeated on every unit of every tick.

**Files:**
- Create: `aoe2x/js_simulation/src/fight.js`
- Modify: `aoe2x/js_simulation/server.mjs:31-52` (routing), `:168-240` (API handlers)
- Test: `aoe2x/js_simulation/tests/fight.test.mjs`

**Interfaces:**
- Consumes: `placeArmy`, `resolveFamily`, `sideCapacity` (Task 2); `unitBySlug`, `UNIT_REGISTRY` (Task 3); `deriveCounts` (Task 4).
- Produces: `src/fight.js` exporting `runFight(root, { side2Slug, n2, side3Slug, n3 })` → frozen slim playback; `FIGHT_SIDE_CAP` (40). **`n2` and `n3` are optional**: when either is omitted, both come from `deriveCounts(side2Slug, side3Slug)` and the chosen values are reported back in `side2.count` / `side3.count`, with `derivedCounts: true`. This keeps the purchase rule in `src/purchase.js` alone — the viewer never recomputes it. Slim playback shape:

```javascript
{
  schemaVersion: 1,
  side2: { slug, label, civ, count, class },
  side3: { slug, label, civ, count, class },
  family: "rvr" | "kite" | "siege" | "waves",
  derivedCounts: boolean,
  kiteOwner: 2 | 3 | null,
  ticks, winnerOwner, winnerHp,
  finalStateHash, eventLogHash,
  unitIndex: { "<referenceId>": { owner, slug, label, maxHp } },
  snapshots: [{ tick, units: [[referenceId, x, y, facing, hp, alive, action,
                               pursuitTargetId, engagedTargetId, attackTargetId], ...],
                events: [...] }]   // movement filtered out
}
```

**The snapshot key names are not free.** `viewer/simulation-review.js:26` requires
every snapshot to be frozen with an integer `tick` equal to its index, a frozen
`units` array and a frozen `events` array, and `map-renderer.js:116` requires the
same plus *deep* freezing. Renaming `tick`/`units`/`events` would throw
`playback requires contiguous immutable snapshots` on boot and break
`cursor.nextEvent()`. The payload saving comes from dropping the mechanics blob
and the unread unit fields, not from shortening key names — so the names stay and
only the per-unit records change shape. The top-level index is called
`unitIndex`, not `units`, to avoid colliding with the snapshot field.

- [ ] **Step 1: Write the failing test**

Create `aoe2x/js_simulation/tests/fight.test.mjs`:

```javascript
import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

import { runFight } from "../src/fight.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = pathToFileURL(path.resolve(here, "..") + "/");

test("a melee fight resolves and reports both sides", async () => {
  const fight = await runFight(root, {
    side2Slug: "champion", n2: 5, side3Slug: "paladin", n3: 3,
  });
  assert.equal(fight.side2.count, 5);
  assert.equal(fight.side3.count, 3);
  assert.equal(fight.side2.label, "Champion");
  assert.equal(fight.kiteOwner, null);
  assert.equal(fight.family, "waves");
  assert.ok(fight.ticks > 0);
  assert.ok(fight.winnerOwner === 2 || fight.winnerOwner === 3);
});

test("exactly one mobile-ranged side sets kiteOwner", async () => {
  const kiting = await runFight(root, {
    side2Slug: "arbalester", n2: 6, side3Slug: "champion", n3: 6,
  });
  assert.equal(kiting.kiteOwner, 2);
  assert.equal(kiting.family, "kite");

  const both = await runFight(root, {
    side2Slug: "arbalester", n2: 6, side3Slug: "imp_elite_skirm", n3: 6,
  });
  assert.equal(both.kiteOwner, null);
  assert.equal(both.family, "rvr");
});

test("snapshots carry no mechanics blob but keep the viewer's contract", async () => {
  const fight = await runFight(root, {
    side2Slug: "champion", n2: 3, side3Slug: "champion", n3: 3,
  });
  const [first] = fight.snapshots;
  // simulation-review.js:26 and map-renderer.js:116 both require exactly this.
  assert.ok(Object.isFrozen(first));
  assert.equal(first.tick, 0);
  assert.ok(Array.isArray(first.units) && Object.isFrozen(first.units));
  assert.ok(Array.isArray(first.events) && Object.isFrozen(first.events));
  assert.equal(first.units.length, 6);
  for (const record of first.units) {
    assert.equal(record.length, 9);
    assert.ok(Object.isFrozen(record));
    assert.equal(typeof record[0], "number");
  }
  assert.equal(JSON.stringify(fight).includes("provenance"), false,
    "mechanics provenance must not be serialised per tick");
});

test("every snapshot tick equals its index", async () => {
  const fight = await runFight(root, {
    side2Slug: "champion", n2: 2, side3Slug: "champion", n3: 2,
  });
  fight.snapshots.forEach((snapshot, index) => {
    assert.equal(snapshot.tick, index);
  });
});

test("max HP is reachable once per unit", async () => {
  const fight = await runFight(root, {
    side2Slug: "champion", n2: 2, side3Slug: "paladin", n3: 2,
  });
  const ids = Object.keys(fight.unitIndex);
  assert.equal(ids.length, 4);
  assert.equal(fight.unitIndex[ids[0]].maxHp > 0, true);
});

test("a 20v20 fight serialises under 10 MB", async () => {
  const fight = await runFight(root, {
    side2Slug: "champion", n2: 20, side3Slug: "paladin", n3: 20,
  });
  const bytes = Buffer.byteLength(JSON.stringify(fight));
  assert.ok(bytes < 10 * 1024 * 1024, `20v20 serialised to ${(bytes / 1048576).toFixed(1)} MB`);
});

test("omitting both counts derives them from the purchase rule", async () => {
  const fight = await runFight(root, { side2Slug: "champion", side3Slug: "siege_onager" });
  assert.equal(fight.derivedCounts, true);
  assert.equal(fight.side2.count, 21);
  assert.equal(fight.side3.count, 8);

  const explicit = await runFight(root, {
    side2Slug: "champion", n2: 21, side3Slug: "siege_onager", n3: 8,
  });
  assert.equal(explicit.derivedCounts, false);
  assert.equal(explicit.finalStateHash, fight.finalStateHash,
    "deriving the counts must produce the same fight as passing them");
});

test("bad input is rejected", async () => {
  await assert.rejects(
    () => runFight(root, { side2Slug: "trebuchet", n2: 5, side3Slug: "champion", n3: 5 }),
    /unknown unit trebuchet/);
  await assert.rejects(
    () => runFight(root, { side2Slug: "champion", n2: 0, side3Slug: "champion", n3: 5 }),
    /count must be an integer/);
  await assert.rejects(
    () => runFight(root, { side2Slug: "champion", n2: 22, side3Slug: "champion", n3: 5 }),
    /count must be an integer/);
});
```

- [ ] **Step 2: Run it, verify it fails**

```bash
cd /d/AI/aoe2_matchup && node --test aoe2x/js_simulation/tests/fight.test.mjs
```

Expected: FAIL — `Cannot find module .../src/fight.js`.

- [ ] **Step 3: Write the fight module**

Create `aoe2x/js_simulation/src/fight.js`:

```javascript
// One fight, composed from the registry and the derived placement. Nothing
// here reads a recorded roster: this is the path a product request takes.
import { readFile } from "node:fs/promises";

import { hashCanonicalJson } from "./canonical-json.js";
import { createUnitState } from "./combat/unit-state.js";
import { createWorld, runWorld } from "./combat/world.js";
import { placeArmy, resolveFamily, sideCapacity } from "./placement.js";
import { deriveCounts } from "./purchase.js";
import { unitBySlug } from "./unit-registry.js";


// Capacity is per (owner, family); this is the largest any of them offers.
export const FIGHT_SIDE_CAP = 21;

const REFERENCE_BASE = { 2: 9000, 3: 9500 };
const MAX_TICKS = 9000;
const mechanicsCache = new Map();


async function loadMechanics(root, unit) {
  if (!mechanicsCache.has(unit.fixture)) {
    mechanicsCache.set(unit.fixture, JSON.parse(await readFile(
      new URL(`fixtures/unit_stats/${unit.fixture}`, root), "utf8")));
  }
  return mechanicsCache.get(unit.fixture);
}


function resolveUnit(slug, count) {
  const unit = unitBySlug(slug);
  if (!unit) throw new RangeError(`unknown unit ${slug}`);
  if (!Number.isSafeInteger(count) || count < 1 || count > FIGHT_SIDE_CAP) {
    throw new RangeError(`count must be an integer 1-${FIGHT_SIDE_CAP}, got ${count}`);
  }
  return unit;
}


// Exactly one mobile-ranged side kites. That is the rule the archive follows in
// all 32 calibrated kiting matchups; siege never kites, and two mobile-ranged
// sides are the unmodelled ranged-vs-ranged case, which runs natively.
function kiteOwnerFor(side2, side3) {
  const two = side2.class === "mobile_ranged";
  const three = side3.class === "mobile_ranged";
  if (two === three) return null;
  return two ? 2 : 3;
}


// Same key names and freezing the viewer's cursor and renderer already demand
// (tick === index, frozen units array, frozen events array). Only the per-unit
// record changes: a positional array instead of an object carrying the whole
// mechanics fixture, which was 85% of the payload.
function slimSnapshot(snapshot) {
  return Object.freeze({
    tick: snapshot.tick,
    units: Object.freeze(snapshot.units.map((unit) => Object.freeze([
      unit.referenceId,
      unit.x,
      unit.y,
      unit.hp,
      unit.alive ? 1 : 0,
      unit.action,
      unit.pursuitTargetId,
      unit.engagedTargetId,
      unit.attackTargetId,
    ]))),
    events: snapshot.events,
  });
}


export async function runFight(root, { side2Slug, n2, side3Slug, n3 }) {
  // Counts are optional: omit either and both come from the purchase rule, so
  // the formula lives in purchase.js and nowhere else.
  const derivedCounts = n2 === undefined || n3 === undefined;
  const derived = derivedCounts ? deriveCounts(side2Slug, side3Slug) : null;
  const count2 = derived ? derived.countA : n2;
  const count3 = derived ? derived.countB : n3;

  const side2 = resolveUnit(side2Slug, count2);
  const side3 = resolveUnit(side3Slug, count3);
  const [mechanics2, mechanics3] = await Promise.all([
    loadMechanics(root, side2),
    loadMechanics(root, side3),
  ]);

  const family = resolveFamily({ side2Class: side2.class, side3Class: side3.class });
  const roster = [
    ...placeArmy({ owner: 2, count: count2, family })
      .map((cell, index) => ({ owner: 2, cell, index, unit: side2, mechanics: mechanics2 })),
    ...placeArmy({ owner: 3, count: count3, family })
      .map((cell, index) => ({ owner: 3, cell, index, unit: side3, mechanics: mechanics3 })),
  ];

  const units = roster.map(({ owner, cell, index, mechanics }, rank) => createUnitState({
    referenceId: REFERENCE_BASE[owner] + index,
    owner,
    x: cell.x,
    y: cell.y,
    facing: 0,
    mechanics,
    acquisitionRank: rank,
    acquisitionCount: roster.length,
  }));

  const kiteOwner = kiteOwnerFor(side2, side3);
  const result = runWorld(createWorld({
    ratio: `${count2}v${count3}`,
    units,
    ...(kiteOwner === null ? {} : { kiteOwner }),
  }), { maxTicks: MAX_TICKS });

  const live = result.world.units.filter(({ alive }) => alive);
  const unitIndex = {};
  for (const { owner, index, unit, mechanics } of roster) {
    unitIndex[REFERENCE_BASE[owner] + index] = Object.freeze({
      owner, slug: unit.slug, label: unit.label, maxHp: mechanics.hp,
    });
  }

  return Object.freeze({
    schemaVersion: 1,
    side2: Object.freeze({
      slug: side2.slug, label: side2.label, civ: side2.civ, count: count2, class: side2.class }),
    side3: Object.freeze({
      slug: side3.slug, label: side3.label, civ: side3.civ, count: count3, class: side3.class }),
    family,
    derivedCounts,
    kiteOwner,
    ticks: result.ticks,
    winnerOwner: live.length ? live[0].owner : null,
    winnerHp: live.reduce((total, unit) => total + unit.hp, 0),
    finalStateHash: hashCanonicalJson({
      tick: result.world.tick, ratio: `${count2}v${count3}`, units: result.world.units }),
    eventLogHash: hashCanonicalJson(result.events),
    unitIndex: Object.freeze(unitIndex),
    snapshots: Object.freeze(result.snapshots.map(slimSnapshot)),
    events: result.events,
  });
}
```

- [ ] **Step 4: Run it, verify it passes**

```bash
cd /d/AI/aoe2_matchup && node --test aoe2x/js_simulation/tests/fight.test.mjs
```

Expected: PASS, seven tests, including the 10 MB budget on 20v20.

- [ ] **Step 5: Add the two endpoints to the server**

In `aoe2x/js_simulation/server.mjs`, add these imports beside the existing ones at the top:

```javascript
import { FIGHT_SIDE_CAP, runFight } from "./src/fight.js";
import { UNIT_REGISTRY } from "./src/unit-registry.js";
```

Add this handler function beside `handleMatchupApi`:

```javascript
function fightSelection(url) {
  const slug2 = url.searchParams.get("side2");
  const slug3 = url.searchParams.get("side3");
  const raw2 = url.searchParams.get("n2");
  const raw3 = url.searchParams.get("n3");
  if (!slug2 || !slug3) return null;
  // Both counts omitted -> derive them from the purchase rule. One without the
  // other is a malformed request, not a half-derived fight.
  if (raw2 === null && raw3 === null) return { side2Slug: slug2, side3Slug: slug3 };
  if (!/^\d{1,2}$/.test(raw2 ?? "") || !/^\d{1,2}$/.test(raw3 ?? "")) return null;
  return { side2Slug: slug2, n2: Number(raw2), side3Slug: slug3, n3: Number(raw3) };
}


async function handleFightApi({ request, response, root, url }) {
  if (url.pathname !== "/api/units" && url.pathname !== "/api/fight") return false;
  if (request.method !== "GET") {
    sendJson(response, 405, { error: "Fight diagnostics are read-only" });
    return true;
  }
  if (url.pathname === "/api/units") {
    sendJson(response, 200, {
      schemaVersion: 1,
      sideCap: FIGHT_SIDE_CAP,
      units: UNIT_REGISTRY.map(({ slug, label, civ, class: unitClass, baseCost }) => ({
        slug, label, civ, class: unitClass, baseCost,
      })),
    });
    return true;
  }
  const selection = fightSelection(url);
  if (!selection) {
    sendJson(response, 400, {
      error: "side2 and side3 must be unit slugs; give both n2 and n3 as integers "
        + `1-${FIGHT_SIDE_CAP}, or neither to derive them`,
    });
    return true;
  }
  try {
    sendJson(response, 200, await runFight(pathToFileURL(path.join(root, "/")), selection));
  } catch (error) {
    sendJson(response, 400, { error: String(error?.message ?? error) });
  }
  return true;
}
```

Register it first in `createMapServer`, before the existing two handlers:

```javascript
      if (await handleFightApi({ request, response, root: resolvedRoot, url })) return;
      if (await handleMatchupApi({ request, response, root: resolvedRoot, url })) return;
      if (await handleChampionApi({ request, response, root: resolvedRoot, url })) return;
```

- [ ] **Step 6: Verify the endpoints by hand**

```bash
cd /d/AI/aoe2_matchup && node aoe2x/js_simulation/server.mjs --port 5011 &
```

Then, in another shell:

```bash
curl -s "http://127.0.0.1:5011/api/units" | head -c 400
```

Expected: JSON with `sideCap: 40` and 14 unit rows.

```bash
curl -s "http://127.0.0.1:5011/api/fight?side2=champion&n2=5&side3=paladin&n3=3" | head -c 300
```

Expected: JSON starting `{"schemaVersion":1,"side2":{"slug":"champion",...`.

```bash
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:5011/api/fight?side2=champion&n2=99&side3=paladin&n3=3"
```

Expected: `400`.

Stop the server before continuing.

- [ ] **Step 7: Run the whole suite**

```bash
cd /d/AI/aoe2_matchup && node --test aoe2x/js_simulation/tests
```

Expected: no new failures. `tests/server.test.mjs` must still pass — the existing endpoints are untouched.

- [ ] **Step 8: Commit**

```bash
cd /d/AI/aoe2_matchup && git add aoe2x/js_simulation/src/fight.js aoe2x/js_simulation/server.mjs aoe2x/js_simulation/tests/fight.test.mjs && git commit -m "feat(sim): /api/fight - any tested pair, any counts, generated spawns

Composes the unit registry, the derived placement and the engine into a request
path that reads no recorded roster. Exactly one mobile-ranged side sets
kiteOwner; bands come from unit class.

Playback is slim: mechanics ship once keyed by unit id instead of on every unit
of every tick, which was 85% of the payload. 15v15 was 101.1 MB, and 20v20 now
has a 10 MB test budget. /api/matchup/* and /api/champion/* are untouched.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Viewer selection controls

Replaces the matchup dropdown with two unit selects and two count inputs, and points the viewer at `/api/fight`. No other UI changes.

**Files:**
- Modify: `aoe2x/js_simulation/viewer/index.html:36-73` (run selector), `:7` (title)
- Modify: `aoe2x/js_simulation/viewer/app.js:135-543`
- Modify: `aoe2x/js_simulation/viewer/simulation-review.js:16-23` (selection), `:124-126` (dedup), `:117`/`:134` (signatures)
- Test: `aoe2x/js_simulation/tests/viewer-selection.test.mjs`

**Interfaces:**
- Consumes: `/api/units` and `/api/fight` from Task 5.
- Produces: no module exports; the viewer's own DOM contract — element ids `side2Select`, `n2Input`, `side3Select`, `n3Input`, `resetCounts`.

- [ ] **Step 1: Replace the run-selector markup**

In `aoe2x/js_simulation/viewer/index.html`, replace the entire `<div class="run-selector">…</div>` block (lines 37–73) with:

```html
        <div class="run-selector">
          <label>
            <span>Side 2</span>
            <select id="side2Select" aria-label="Side 2 unit"></select>
          </label>
          <label>
            <span>Count</span>
            <input id="n2Input" type="number" min="1" max="21" step="1" value="21"
                   inputmode="numeric" aria-label="Side 2 unit count">
          </label>
          <label>
            <span>Side 3</span>
            <select id="side3Select" aria-label="Side 3 unit"></select>
          </label>
          <label>
            <span>Count</span>
            <input id="n3Input" type="number" min="1" max="21" step="1" value="21"
                   inputmode="numeric" aria-label="Side 3 unit count">
          </label>
          <button id="resetCounts" type="button" title="Reset both counts to the derived even-fight purchase">Even fight</button>
        </div>
```

Also change the `<title>` on line 7 from `Golden Arena · Champion Combat Chronograph` to `Golden Arena · Combat Chronograph`, and the `<h1>` subtitle text is left alone.

- [ ] **Step 2: Write the failing test**

Create `aoe2x/js_simulation/tests/viewer-selection.test.mjs`:

```javascript
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const html = await readFile(new URL("../viewer/index.html", import.meta.url), "utf8");
const app = await readFile(new URL("../viewer/app.js", import.meta.url), "utf8");

test("the selector markup carries the four selection controls", () => {
  for (const id of ["side2Select", "n2Input", "side3Select", "n3Input", "resetCounts"]) {
    assert.ok(html.includes(`id="${id}"`), `missing #${id}`);
  }
});

test("the old matchup and ratio controls are gone", () => {
  for (const id of ["matchupSelect", "ratioSelect", "ratioOptions"]) {
    assert.ok(!html.includes(`id="${id}"`), `#${id} should have been removed`);
  }
});

test("the viewer drives the fight endpoint and not the matchup endpoints", () => {
  assert.ok(app.includes("api/fight"), "app.js must call api/fight");
  assert.ok(app.includes("api/units"), "app.js must call api/units");
  assert.ok(!app.includes("api/matchup/"), "app.js must not call api/matchup/*");
  assert.ok(!app.includes("api/champion/result"), "app.js must not call api/champion/result");
});

test("the lab panels are still present", () => {
  for (const id of ["unitTelemetry", "eventTimeline", "runFlagged", "reviewNote",
    "topDownToggle", "gridToggle", "tickReadout", "simWinner"]) {
    assert.ok(html.includes(`id="${id}"`), `lab control #${id} was removed`);
  }
});
```

- [ ] **Step 3: Run it, verify the app.js assertions fail**

```bash
cd /d/AI/aoe2_matchup && node --test aoe2x/js_simulation/tests/viewer-selection.test.mjs
```

Expected: the first two and last tests PASS (Step 1 changed the markup), the third FAILS because `app.js` still calls `api/matchup/`.

- [ ] **Step 4: Rewire app.js to the fight endpoint**

In `aoe2x/js_simulation/viewer/app.js`:

**4a.** In `start()`, drop `api/champion/truth` and `api/champion/mechanics` from the boot `Promise.all` (lines 136–154) and fetch the unit list instead:

```javascript
  const [mapResponse, formationResponse, unitsResponse] = await Promise.all([
    fetch("api/map", { cache: "no-store" }),
    fetch("api/formation", { cache: "no-store" }),
    fetch("api/units", { cache: "no-store" }),
  ]);
  for (const [label, response] of [
    ["Map", mapResponse],
    ["Formation", formationResponse],
    ["Units", unitsResponse],
  ]) {
    if (!response.ok) throw new Error(`${label} API returned ${response.status}`);
  }
  const catalogue = deepFreeze(await unitsResponse.json());
```

**4b.** Replace the source badge and clock lines (161–172) that referenced `truth` and `mechanics`:

```javascript
  byId("sourceBadge").innerHTML = `
    <span class="seal-dot"></span>
    <span><strong>Clean-room engine</strong><small>${catalogue.units.length} measured units · ${fixture.source.filename}</small></span>
  `;
  byId("clockRate").textContent = `${TICKS_PER_SECOND} Hz`;
```

**4c.** Replace the champion-ratio boot block (lines 180–190) with unit-select population and a default selection:

```javascript
  function populateUnitSelects() {
    for (const [id, fallback] of [["side2Select", "champion"], ["side3Select", "paladin"]]) {
      const select = byId(id);
      select.replaceChildren(...catalogue.units.map(({ slug, label, civ }) => {
        const option = document.createElement("option");
        option.value = slug;
        option.textContent = `${label} (${civ})`;
        return option;
      }));
      select.value = fallback;
    }
  }
  populateUnitSelects();

  function currentSelection() {
    return {
      side2Slug: byId("side2Select").value,
      n2: Number(byId("n2Input").value),
      side3Slug: byId("side3Select").value,
      n3: Number(byId("n3Input").value),
    };
  }

  // Boot with no counts: the server derives the even-fight purchase and the
  // inputs are filled in from what it chose.
  let selected = {
    side2Slug: byId("side2Select").value,
    side3Slug: byId("side3Select").value,
  };
```

**4d.** Replace the body of `loadSimulation` (lines 240–278). The endpoint, the ledger fields and the snapshot source all change; the transport-button enable/disable and the feedback call stay:

```javascript
  async function loadSimulation(nextSelection) {
    const serial = requestSerial += 1;
    setPlaying(false);
    selected = nextSelection;
    byId("playbackMode").textContent = "loading trace";
    byId("mapStatus").innerHTML =
      `<span class="status-light is-loading"></span>Running ${selected.n2}v${selected.n3}…`;
    for (const control of ["playPause", "resetPlayback", "stepTick", "nextEvent"]) {
      byId(control).disabled = true;
    }
    // Counts are omitted entirely when the caller wants the derived purchase;
    // the server sends back what it chose and the inputs are synced from it.
    const counts = selected.n2 === undefined || selected.n3 === undefined
      ? "" : `&n2=${selected.n2}&n3=${selected.n3}`;
    const endpoint = `api/fight?side2=${encodeURIComponent(selected.side2Slug)}`
      + `&side3=${encodeURIComponent(selected.side3Slug)}${counts}`;
    const response = await fetch(endpoint, { cache: "no-store" });
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.error ?? `Fight API returned ${response.status}`);
    }
    const result = deepFreeze(await response.json());
    if (serial !== requestSerial) return;
    activeResult = result;
    // Whatever the server ran is what the inputs show, derived or not.
    selected = { ...selected, n2: result.side2.count, n3: result.side3.count };
    byId("n2Input").value = String(result.side2.count);
    byId("n3Input").value = String(result.side3.count);
    cursor = createPlaybackCursor({ snapshots: result.snapshots, onSnapshot: present });
    byId("simWinner").textContent = result.winnerOwner === null
      ? "—" : `Player ${result.winnerOwner}`;
    byId("simWinnerHp").textContent = `${result.winnerHp} HP`;
    byId("tapeWinner").textContent = "—";
    byId("tapeWinnerHp").textContent = "generated formation";
    byId("player2Name").textContent = result.side2.label;
    byId("player3Name").textContent = result.side3.label;
    byId("player2Count").textContent = String(result.side2.count);
    byId("player3Count").textContent = String(result.side3.count);
    byId("ledgerNumber").textContent = `${result.side2.count}V${result.side3.count}`;
    byId("playPause").textContent = "Play";
    byId("playbackMode").textContent = "paused";
    for (const control of ["playPause", "resetPlayback", "stepTick", "nextEvent"]) {
      byId(control).disabled = false;
    }
    displayFeedback();
  }
```

**4e.** `renderUnitTelemetry` (lines 78–98) reads `unit.hp`, `unit.mechanics.hp`, `unit.owner`, `unit.referenceId`, `unit.alive` and `unit.action` off snapshot units. Slim snapshots are positional arrays, so rewrite it to unpack them and take max HP from the `units` index:

```javascript
function renderUnitTelemetry(snapshot, index) {
  const rows = snapshot.units.map(([referenceId, , , , hp, alive, action,
    pursuitTargetId, engagedTargetId, attackTargetId]) => {
    const meta = index[referenceId];
    const row = document.createElement("div");
    row.className = `telemetry-row owner-${meta.owner}${alive ? "" : " is-dead"}`;
    const identity = document.createElement("span");
    identity.className = "telemetry-identity";
    identity.textContent = `P${meta.owner} · ${referenceId}`;
    const hpText = document.createElement("span");
    hpText.className = "telemetry-hp";
    hpText.textContent = `${hp}/${meta.maxHp} HP`;
    const meter = document.createElement("i");
    meter.style.setProperty("--hp", `${Math.max(0, hp / meta.maxHp * 100)}%`);
    const state = document.createElement("small");
    state.textContent = `${alive ? action : "dead"} · ${targetLabel(
      { pursuitTargetId, engagedTargetId, attackTargetId })}`;
    row.append(identity, hpText, meter, state);
    return row;
  });
  byId("unitTelemetry").replaceChildren(...rows);
  const live = snapshot.units.filter(([, , , , alive]) => alive).length;
  byId("unitCount").textContent = `${live}/${snapshot.units.length} alive`;
}
```

**4f.** `present(snapshot)` (lines 210–220) passes the snapshot to the renderer and to telemetry. The renderer needs the old shape, so rehydrate there and pass the index to telemetry:

The per-tick record is a 10-element tuple in this exact order — `[referenceId, x, y, facing, hp, alive, action, pursuitTargetId, engagedTargetId, attackTargetId]` — where `alive` is `1` or `0`, not a boolean. `unitIndex[referenceId]` carries `{ owner, slug, label, maxHp, master, collisionRadius, attackRange }`.

`map-renderer.js` reads `unit.facing`, `unit.unitMaster`, `unit.mechanics.collision_size_tiles.x` and `unit.mechanics.attack_range_tiles`, and tests `unit.alive === false` strictly — so `0` must become `false`, not stay `0`, or corpses render as live bodies. Rehydrate all of it here and nowhere else:

```javascript
  function present(snapshot) {
    // map-renderer requires DEEPLY frozen objects in the legacy unit shape, so
    // the slim positional records are rehydrated here and nowhere else. Note
    // alive is 1|0 on the wire and the renderer tests `=== false`.
    renderer.setSimulationSnapshot(Object.freeze({
      tick: snapshot.tick,
      units: Object.freeze(snapshot.units.map(
        ([referenceId, x, y, facing, hp, alive, action]) => {
          const meta = activeResult.unitIndex[referenceId];
          return Object.freeze({
            referenceId, x, y, facing, hp, action,
            alive: alive === 1,
            owner: meta.owner,
            unitMaster: meta.master,
            mechanics: Object.freeze({
              hp: meta.maxHp,
              attack_range_tiles: meta.attackRange,
              collision_size_tiles: Object.freeze({ x: meta.collisionRadius }),
            }),
          });
        })),
      events: snapshot.events,
    }));
    byId("tickReadout").textContent = String(snapshot.tick).padStart(4, "0");
    byId("secondsReadout").textContent = (snapshot.tick / TICKS_PER_SECOND).toFixed(3);
    renderUnitTelemetry(snapshot, activeResult.unitIndex);
    renderTimeline(eventLog, snapshot.tick);
    byId("mapStatus").innerHTML = `<span class="status-light"></span>`
      + `${activeResult.side2.label} ${activeResult.side2.count}`
      + ` vs ${activeResult.side3.label} ${activeResult.side3.count}`;
    if (cursor?.atEnd()) setPlaying(false);
  }
```

`renderTimeline` needs one flat list of events with their ticks, but the payload no longer carries a top-level `events` array — it was dropped because duplicating it doubled the wire size. Build the flat list once per fight instead. Declare `let eventLog = [];` beside `activeResult`, and in `loadSimulation`, right after `activeResult = result;`, add:

```javascript
    // The wire carries events per snapshot (movement filtered out); the
    // timeline wants one flat list, so flatten it once rather than per frame.
    eventLog = result.snapshots.flatMap(({ events }) => events);
```

**4g.** Replace the matchup/ratio/repeat event wiring (lines 298–388) with the four controls plus the even-fight button:

```javascript
  // Changing a unit re-derives the counts -- a new pair gets the even-fight
  // purchase, which is what the recorded fights were bought at. Typing a count
  // sends both counts explicitly. Either way the server decides and the inputs
  // are synced from its answer, so the purchase rule lives only in purchase.js.
  function loadDerived() {
    return loadSimulation({
      side2Slug: byId("side2Select").value,
      side3Slug: byId("side3Select").value,
    });
  }
  for (const id of ["side2Select", "side3Select"]) {
    byId(id).addEventListener("change", () => { loadDerived().catch(showError); });
  }
  for (const id of ["n2Input", "n3Input"]) {
    byId(id).addEventListener("change", () => {
      loadSimulation(currentSelection()).catch(showError);
    });
  }
  byId("resetCounts").addEventListener("click", () => { loadDerived().catch(showError); });
```

**4h.** Delete the now-unused `matchupList`, `populateMatchups`, `ratiosFor`, `ratioAllowed`, `repopulateRatios` functions and the `CHAMPION_RATIO_OPTIONS` constant, and both `history.replaceState` calls. The import block from `./simulation-review.js` (lines 8–14) drops `RATIO_PATTERN`, `parseReviewSelection` and `selectionUrl` — all three were only used by the deleted ratio validation — leaving:

```javascript
import {
  createPlaybackCursor,
  createReviewFeedback,
  downloadJsonDocument,
} from "./simulation-review.js";
```

Change the boot tail (lines 530–531) to:

```javascript
  await loadSimulation(selected);
```

**4i.** `createReviewFeedback` keys rows by `{ratio, repeat}`, and `selection()` in `simulation-review.js:16` validates `ratio` against `/^[1-9]\d?v[1-9]\d?$/`. A key like `champion-21vpaladin-21` throws `ratio must look like 6v3`, and keying on counts alone would silently merge notes written about different unit pairs. So `selection()` gains an optional `pair`.

In `aoe2x/js_simulation/viewer/simulation-review.js`, add the pattern beside `RATIO_PATTERN`:

```javascript
// Optional matchup identity for a review row. Rows written before free unit
// selection have no pair; omitting the field entirely keeps them readable and
// keeps the stored shape unchanged for them.
export const PAIR_PATTERN = /^[a-z_]+-vs-[a-z_]+$/;
```

Replace `selection()` (lines 16–23) with:

```javascript
function selection({ ratio, repeat, pair }) {
  if (typeof ratio !== "string" || !RATIO_PATTERN.test(ratio)) {
    throw new TypeError("ratio must look like 6v3");
  }
  if (!Number.isInteger(repeat) || repeat < 1 || repeat > 3) {
    throw new TypeError("tape repeat must be 1, 2, or 3");
  }
  if (pair === undefined) return { ratio, repeat };
  if (typeof pair !== "string" || !PAIR_PATTERN.test(pair)) {
    throw new TypeError("pair must look like champion-vs-paladin");
  }
  return { pair, ratio, repeat };
}
```

And widen the dedup filter in `set()` (lines 124–126) so a row is only replaced by one with the same pair:

```javascript
    runs = runs.filter((candidate) => (
      candidate.ratio !== ratio || candidate.repeat !== repeat
      || (candidate.pair ?? undefined) !== pair
    ));
```

`set()`'s signature becomes `set({ ratio, repeat, pair, flagged, note = "" })` and `flag()` becomes `flag({ ratio, repeat, pair, note = "" })`, each forwarding `pair` through. Because `pair` is omitted from the returned row when undefined, the four `assert.deepEqual` assertions in `tests/viewer-simulation.test.mjs` (lines 58–67) keep passing untouched.

Then in `app.js`, give `displayFeedback` and `saveFeedback` a shared key helper and use it in place of `selected`:

```javascript
  function feedbackKey() {
    return {
      pair: `${selected.side2Slug}-vs-${selected.side3Slug}`,
      ratio: `${selected.n2}v${selected.n3}`,
      repeat: 1,
    };
  }
```

`saveFeedback` becomes:

```javascript
  function saveFeedback() {
    feedback.set({
      ...feedbackKey(),
      flagged: byId("runFlagged").checked,
      note: byId("reviewNote").value,
    });
  }
```

and `displayFeedback`'s first line becomes `const row = feedback.get(feedbackKey());`.

**4j.** Add a regression test for the widened selection. Append to `aoe2x/js_simulation/tests/viewer-selection.test.mjs`:

```javascript
import { createReviewFeedback } from "../viewer/simulation-review.js";

function memoryStorage() {
  const map = new Map();
  return {
    getItem: (key) => map.get(key) ?? null,
    setItem: (key, value) => { map.set(key, value); },
  };
}

test("review rows for different unit pairs at the same counts do not collide", () => {
  const feedback = createReviewFeedback({ storage: memoryStorage() });
  feedback.flag({ pair: "champion-vs-paladin", ratio: "5v3", repeat: 1, note: "a" });
  feedback.flag({ pair: "arbalester-vs-champion", ratio: "5v3", repeat: 1, note: "b" });
  assert.equal(feedback.get({ pair: "champion-vs-paladin", ratio: "5v3", repeat: 1 }).note, "a");
  assert.equal(feedback.get({ pair: "arbalester-vs-champion", ratio: "5v3", repeat: 1 }).note, "b");
});

test("a malformed pair is rejected", () => {
  const feedback = createReviewFeedback({ storage: memoryStorage() });
  assert.throws(
    () => feedback.flag({ pair: "Champion vs Paladin", ratio: "5v3", repeat: 1, note: "" }),
    /pair/i);
});
```

- [ ] **Step 5: Run the viewer tests, verify they pass**

```bash
cd /d/AI/aoe2_matchup && node --test aoe2x/js_simulation/tests/viewer-selection.test.mjs aoe2x/js_simulation/tests/viewer-simulation.test.mjs
```

Expected: PASS — six tests in `viewer-selection`, and `viewer-simulation` unchanged and still green (the optional `pair` field is omitted from rows that do not set it, so its `deepEqual` assertions are unaffected).

- [ ] **Step 6: Verify in the browser**

```bash
cd /d/AI/aoe2_matchup && node aoe2x/js_simulation/server.mjs --port 5011 &
```

Open `http://127.0.0.1:5011/` and confirm, in order:

1. Both unit dropdowns list 14 units with civ names; boot runs Champion vs Paladin with the count inputs filled in from the derived purchase (21 and 13).
2. Changing Side 3 to `Arbalester (Chinese)` re-runs, the counts re-derive, and the two armies visibly start further apart.
3. Typing 20 into both count inputs completes and plays without the tab stalling.
4. Pressing "Even fight" after that restores the derived counts.
5. Selecting Champion vs Siege Onager derives 21 and 8.
6. `+1 tick`, `Next event`, `Reset`, the top-down toggle and the event tape all still work.
7. The browser console shows no errors.

Stop the server.

- [ ] **Step 7: Run the whole suite**

```bash
cd /d/AI/aoe2_matchup && node --test aoe2x/js_simulation/tests
```

Expected: no new failures. `tests/viewer-simulation.test.mjs` exercises `matchup-playback.js` directly, not the viewer, so it is unaffected.

- [ ] **Step 8: Commit**

```bash
cd /d/AI/aoe2_matchup && git add aoe2x/js_simulation/viewer/index.html aoe2x/js_simulation/viewer/app.js aoe2x/js_simulation/viewer/simulation-review.js aoe2x/js_simulation/tests/viewer-selection.test.mjs && git commit -m "feat(viewer): free unit and count selection over /api/fight

The matchup dropdown and ratio combobox become two unit selects and two count
inputs; an even-fight button fills in the derived purchase. The viewer now
drives /api/fight only, so no recorded roster reaches the screen.

Telemetry and the renderer read the slim snapshot form, taking max HP from the
per-fight unit index instead of a mechanics blob on every tick. Review rows gain
an optional pair field so notes about different unit pairs at the same counts no
longer collide; rows without one keep their existing shape. Transport, event
tape, map toggles and the review panel are otherwise unchanged.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Self-review notes

Spec coverage, section by section:

| Spec section | Task |
|---|---|
| `src/placement.js` | 2 |
| `src/unit-registry.js` + cost export | 3 |
| `src/purchase.js` | 4 |
| `src/fight.js` and `/api/fight` | 5 |
| Slim playback format | 5 |
| Pinned configuration | 1 |
| UI delta | 6 |
| Gate 1 — placement reproduces the archive | 2, Step 6 |
| Gate 2 — purchase reproduces the corpus | 4, Step 4 |
| Gate 3 — costs reproduce the corpus | 3, Step 6 |
| Gate 5 — no engine drift | 1, Step 7 |
| Gate 6 — payload budget | 5, Step 4 |
| Gate 7 — suite green | 1, 5, 6 |

Gate 4 in the spec ("fixture regeneration is additive-only") no longer applies: Task 3 keeps base costs in the registry rather than writing them into the mechanics fixtures, so the calibrated fixtures are never rewritten. That is a strictly smaller change than the spec described and removes the only step that could have disturbed calibrated inputs. The spec's `src/unit-registry.js` table already listed `baseCost` as a registry field, so no requirement is lost.

The spec's `tapeReference` field is deliberately not implemented in Task 5. It is display-only sugar, the ledger reads dashes without it exactly as it does for synthetic ratios today, and leaving it out keeps `calibration/fixtures/` off the request path entirely. It can be added later without touching any other component.

Three contracts in the existing viewer were checked against the source rather than assumed, and each one changed the plan:

- `viewer/simulation-review.js:26` and `viewer/map-renderer.js:116` both require snapshots frozen with `tick === index`, a frozen `units` array and a frozen `events` array. The slim format keeps those three key names and only reshapes the per-unit record; renaming them would have thrown on boot.
- `map-renderer.js` requires *deep* freezing, so `present()` rehydrates the positional records into frozen objects before handing them to the renderer, and nowhere else.
- `simulation-review.js:16` validates `ratio` against `/^[1-9]\d?v[1-9]\d?$/`, so the review panel cannot key rows on a unit pair without the optional `pair` field added in Task 6, Step 4i.

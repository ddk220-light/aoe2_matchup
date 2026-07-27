# sim_v2 — position-aware battle sim + matchup categorization for unit-analysis videos

This directory holds the **finalized method** for turning one subject unit into a
segmented unit-analysis video: run every matchup through the position-aware "V2"
battle sim, categorize each outcome, and pick the fights to showcase. The pilot
subject is the Elite Temple Guard (ETG, Muisca); the pipeline is parameterized so
any unit can be run.

Three things were finalized (2026-07-06) and now live in code:

1. **How to run the V2 simulation** — `sim_v2_model.js` + `headless_sim.js` + `run_pool_v2.js`
2. **How to categorize the outcomes** — [`aoe2x/analysis/story_rules_v2.py`](../../../aoe2x/analysis/story_rules_v2.py)
3. **How to identify the showcase matchups** — `story_rules_v2.pick_showcase` (driven from the same module)

The one-command driver that ties it together is `build_v2_categorization.py`.

---

## TL;DR — build the categorization for a unit

```bash
# From the repo root, with a Python that has aoe2x + numpy, and node on PATH.
python apps/video/sim_v2/build_v2_categorization.py \
    Muisca elite_temple_guard_muisca \
    --overrides apps/video/sim_v2/overrides/elite_temple_guard_muisca.json \
    --matchup-db C:/AI/matchup_baseline_177723.db \
    --jobs 4
```

Outputs land in `--workdir` (default `apps/video/sim_v2/_work/<slug>/`):

| File | What it is |
|---|---|
| `categorized.md` | Human-readable segmentation report (showcase picks, coin-flip odds, full table) |
| `categorized.json` | Machine-readable rows + showcase, for downstream tooling |
| `storyboard.json` | Bridge that feeds the recorder (`auto/run_unit_analysis_video.py`) |

The finalized ETG result is preserved (tracked) at
[`results/elite_temple_guard_muisca.md`](results/elite_temple_guard_muisca.md).

---

## The three stages (`--stage extract | simulate | categorize | all`)

```
extract   (Python)   pool + arena counts + combat dicts   -> pool_meta.json, combat_dicts_all.json
   |
simulate  (Node)     V2 sim, subject vs every opponent     -> v2_slice_*.json
   |
categorize(Python)   rules + showcase + reports            -> categorized.{md,json}, storyboard.json
```

### 1. `extract`
Builds the opponent pool from [`aoe2x/analysis/opponent_pool.py`](../../../aoe2x/analysis/opponent_pool.py)
(validated uniques + generic staples), applies the per-subject `remove`/`add`
overrides, computes **arena counts** (`equal_resource_counts`, budget 3000, cap 21 —
so the cheaper unit is capped at 21 and the pricier is rescaled to the same spend;
e.g. ETG vs Huskarl → 13 v 21), and writes each unit's combat dict (exactly what
`/api/ref/combat-unit` serves). With `--matchup-db` it also records the shipped-DB
row per matchup for side-by-side comparison.

### 2. `simulate`
`run_pool_v2.js` runs the V2 model for the subject (team 1) vs each opponent (team 2)
at the arena counts. **5 seeds; +10 more if `|mean margin S| < 33`** (so contested
matchups get 15 seeds, decided ones stay cheap). `--jobs N` splits the pool across N
Node processes. Same seed → identical fight (deterministic); the seeded jitter/churn
terms are the per-seed variance source. Each fight returns per-army surviving-HP%,
a margin `S = subjectHP% − oppHP%`, and a winner.

**The V2 model** (`sim_v2_model.js`) is the shipped webapp sim
([`apps/website/static/js/simulate.js`](../../../apps/website/static/js/simulate.js))
loaded headless via `headless_sim.js`, with a frozen physics-fix package applied as
env knobs — it is **not a fork**, so it tracks the shipped combat code. The knobs
(game-true collision radius, melee arrival wind-up, retarget cooldown, crowd churn,
compact-block spawn) were calibrated against 20 per-unit in-game decodes of ETG vs
Huskarl. Full rationale + the 11/12-fight validation:
[`docs/superpowers/specs/2026-07-06-etg-v2-sim-calibration.md`](../../../docs/superpowers/specs/2026-07-06-etg-v2-sim-calibration.md).
The knobs and their reasons are also documented inline at the top of `sim_v2_model.js`.

> **Time cap:** `sim_v2_model.js` pins `MAXS=180` so no caller can accidentally
> shorten a fight (a positional-argv collision once truncated fights into fake
> stalemates — see the header comment in `sim_v2_model.js`).

### 3. `categorize`
Applies [`aoe2x/analysis/story_rules_v2.py`](../../../aoe2x/analysis/story_rules_v2.py)
(pure rules, no I/O) to every V2 result, then selects the showcase fights.

**Outcome** (winner must keep army HP; the coin-flip band absorbs the middle):
- **Win** = subject win-rate ≥ 80% and the subject keeps > 5% army HP
- **Loss** = subject win-rate ≤ 20% and the opponent keeps > 5% army HP
- **Coin-flip** = the rest (contested win-rate, or the winner too thin — this is
  where a genuinely bimodal matchup like ETG-vs-Huskarl lands)

**Expected vs unexpected** — who is *favored* decides, by this cascade:
1. only the subject has a usable damage bonus → subject favored
2. only the opponent has a bonus vs the subject → opponent favored
3. both have a bonus → "both" (always unexpected)
4. neither → the normal-counter class decides (`infantry↩{cav,inf}`,
   `ranged↩{inf,ranged}`, `cav↩{ranged,cav}`)

Then: win + subject/neither = **expected win**; win + opp/both = **unexpected win**;
loss + opp/neither = **expected loss**; loss + subject/both = **unexpected loss**.

Two quirks are baked in: **melee gating** (a melee subject's bonus is ignored vs a
ranged/kiting opponent it can never catch) and the **skirmisher/spearman override**
(they're weak vs infantry, but a *mounted* skirmisher faster than the subject kites
and counts as a normal ranged unit). A damage bonus must be **> 1** to count.

**Showcase** = up to 5 per category: wins → the **most expensive** opponents;
losses → the **cheapest** the subject loses to; coin-flips → **none** (listed at the
end with win/loss odds). The per-subject `exclude_showcase` list drops units that
should never appear on screen.

---

## Per-subject overrides

The **method** is generic; the **curation** for a given subject is data. See
[`overrides/elite_temple_guard_muisca.json`](overrides/elite_temple_guard_muisca.json).
Keys:

| Key | Effect |
|---|---|
| `remove` | Drop these `Civ/slug` from the pool before simulating |
| `add` | Add these to the pool (simulated by the batch) |
| `extra_results` | Splice in matchups simmed **separately** (their combat dict is still built) — used for the ETG's Vietnamese Battle Elephant + Champi, which were run as one-off 15-seed sims |
| `ingame_outcome` | Force a matchup's outcome (`win`/`loss`/`coinflip`) — for units the V2 model gets wrong, validated in-game (the ETG's Arambai) |
| `exclude_showcase` | Never show these on screen (the ETG's Genitour) |

---

## Feeding the recorder

`categorize` emits `storyboard.json` in the schema
[`auto/run_unit_analysis_video.py`](../auto/run_unit_analysis_video.py) consumes, so
the finalized categorization drives the fight recording + stitch directly. The V2
categories map onto the recorder's four filmed categories + listed "even":

| V2 category | Recorder category |
|---|---|
| expected_win | expected_win (filmed) |
| unexpected_win | unexpected_win (filmed) |
| unexpected_loss | unexpected_counter (filmed) |
| expected_loss | expected_counter (filmed) |
| coin_flip | even (listed, not filmed) |

To build the video from the storyboard (on the Windows box with the game + golden rig):

```bash
# copy the storyboard where the recorder expects it, then:
python -m auto.run_unit_analysis_video \
    apps/video/media/units/<slug>/storyboard.json --out <dir> --dry-run   # plan
python -m auto.run_unit_analysis_video \
    apps/video/media/units/<slug>/storyboard.json --out <dir>             # record + stitch
```

See [`../RUNBOOK.md`](../RUNBOOK.md) for the recording rig itself (scenario build,
gRPC HP overlay, compose, chapters).

> The earlier DB/local-sim categorization path
> ([`aoe2x/analysis/unit_video_story.py`](../../../aoe2x/analysis/unit_video_story.py),
> rules in `story_rules.py`) predates the V2 model and uses a different scheme
> (E-prior / RPS priors). The V2 pipeline here is the finalized approach; the older
> path is kept for reference / the shipped-DB comparison.

---

## Full end-to-end process to build a unit-analysis video

1. **Pick the subject** (civ + slug). Create/curate `overrides/<slug>.json`.
2. **`extract`** — pool, arena counts, combat dicts. Sanity-check counts (e.g. the
   Huskarl 13 v 21).
3. **`simulate`** — the V2 batch. Contested matchups auto-escalate to 15 seeds.
4. **`categorize`** — read `categorized.md`; confirm the segmentation looks right.
   Validate any suspicious high-stakes matchup **in-game** (5 runs) and, if the V2
   model is wrong, pin it via `ingame_outcome`.
5. **Record + stitch** — feed `storyboard.json` to `auto.run_unit_analysis_video`
   on the game box (golden recording rig → per-fight clips → intro/banner/ranked
   cards → concat → YouTube chapters).
6. **Preserve** the `categorized.md`/`.json` under `results/<slug>.*`.

---

## File map

| File | Role |
|---|---|
| `build_v2_categorization.py` | Driver: extract → simulate → categorize; CLI |
| `sim_v2_model.js` | The frozen V2 model (env knobs + `require("./headless_sim")`) |
| `headless_sim.js` | Loads the webapp `simulate.js` headless in a vm sandbox; `runFight()` |
| `run_pool_v2.js` | Batch runner: subject vs pool, 5→+10 seed escalation |
| `overrides/<slug>.json` | Per-subject curation (add/remove/extra/in-game/exclude) |
| `results/<slug>.{md,json}` | Preserved finalized categorization deliverables |
| (`aoe2x/analysis/story_rules_v2.py`) | Pure categorization + showcase rules (importable) |

## ETG result (finalized)

23 expected win · 0 unexpected win · 7 coin-flip · 2 unexpected loss · 44 expected loss.
Showcase picks and the full 76-opponent table:
[`results/elite_temple_guard_muisca.md`](results/elite_temple_guard_muisca.md).


## Update 2026-07-26 (champi run — the golden workflow)

- **Categorization rule**: user-declared WIN CONDITIONS (per-line pool-percentile
  thresholds, `win_conditions/<slug>.json` + `--win-conditions`) replace the
  favored() cascade as the standard. See `../UNIT_VIDEO_WALKTHROUGH.md` Phase 1.
- **Physics knobs added to the frozen model** (`sim_v2_model.js`, tape-validated):
  `TRAMPLE_CONE=60` (conical blast, front arc only, CONE_SLUGS in headless_sim) and
  `KITE_CATCH=1.15` (three-condition flee gate: kiter faster AND chaser >=1.15
  tiles/s absolute AND kiter can't hurt the chaser). Full rationale in the model file.
- **Shipped-engine fix inherited at load**: simulate.js getDamageAgainst now resists
  an attack with the armor of the ATTACK'S class (thrown-melee units vs melee armor).
- **Pins retired**: `ingame_outcome`/`ingame_wr`/`ingame_hp` overrides are stopgaps;
  the champi run ended with zero pins — the engine earns every taped result natively.
- `--workdir` must be ABSOLUTE when running `--stage simulate` (node cwd is sim_v2/).

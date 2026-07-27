# Simulation V2 — change list & full-rerun protocol

**Status: 2026-07-26.** This document is the single source of truth for every
deliberate divergence between the **V2 simulation engine** (this package) and
the engines that produced ALL data currently served by the site. Nothing in
this package is consumed by the webapp; the production engines and every
committed DB stay exactly as they are until the full re-run described in §7.

Provenance: the engine files here are a verbatim snapshot of the
`aoe2_ai_for_simulation` branch at `e716414` (2026-07-26). That branch is the
canonical development home; this package exists so a build machine can pull
`staging` and run the new engine without touching production code paths.

---

## 0. The three engines, and what V2 is

| Engine | File | Produces | V2 status |
|---|---|---|---|
| Frontend canvas | `apps/website/static/js/simulate.js` | Interactive Battle Sim page (client-side only) | **Base of V2.** Three fixes written on the branch (§1), NOT yet live on staging/prod |
| Position-based 2D batch | `aoe2x/sim/simulation_real.py` | ALL matchup data: `derived_data.db`, `pool_scores.db`, `civ_power_units/*` | **Unchanged.** Carries bug §1.1; port target for the full rerun |
| Abstract tick | `aoe2x/sim/simulation.py` | `/api/matchup-sims` overlay | **Unchanged.** Carries bug §1.1; cannot represent kiting/envelopment (positionless) — role to be decided at rerun |

**V2** = the real `simulate.js` + a frozen set of load-time source transforms
(`sim_v2_model.js` → `headless_sim.js`). No fork: the transforms patch the
shipped code at load, so V2 stays in lockstep with the browser engine. Every
knob, its calibrated value, and its validation record is in the header
comments of `sim_v2_model.js` — that file is the executable spec.

V2 was validated fight-by-fight against **in-game ground truth**: ~50
recorded arena fights (ddkMatchupAI patrol rig, 16×16 map, equal-resource
counts, 5 runs per contested matchup), including a 13-anchor regression sweep
re-run after every calibration change. The recording rig, tapes index, and
per-fight results live on the `aoe2_ai_for_simulation` branch
(`apps/video/UNIT_VIDEO_WALKTHROUGH.md`, `apps/video/sim_v2/results/`).

---

## 1. Genuine engine BUGS (exist in shipped engines today)

These are not model choices — they are defects. They must be fixed in **all
three** engines at rerun time.

### 1.1 Ranged melee-class attacks resolved against PIERCE armor ⚠ widest ripple

Every engine picks the resisting armor from *delivery* (`isRanged → pierce
armor`). The game resolves by the **attack's damage class**: a ranged unit
whose base attack is class 4 (melee) and has no class-3 entry is resisted by
**melee** armor. Rule: `armor class = ranged && attacks["3"] ? 3 : 4`.

- **Fixed** in `simulate.js` on the branch (commit `e9a5b8b`, incl. the
  damage-formula panel) — that fix is in `engine_base/simulate.js` here.
- **NOT fixed** in `simulation_real.py` (~line 590) and `simulation.py`.
  Fixing `simulation_real.py` bumps `aoe2x/sim/sim_version.py` → auto-stales
  all ~500k matchup rows (this is the designed mechanism, not a side effect).

**Affected units** (ranged, class-4-only base attack — from the current dat):
Gbeto, Mameluke, Throwing Axeman, Chakram Thrower (elites incl.);
Mangonel / Onager / Siege Onager; Bombard Cannon, Houfnice, Heavy Rocket
Cart; Trebuchet variants (Traction / Mounted); ships (Fire Ship line,
Dromon, Cannon Galleon line, Catapult Galleon, Lou Chuan).
Every matchup **involving any of these, on either side**, is suspect in
current rankings — the error roughly halved thrown-melee damage into
high-pierce-armor targets (Gbeto vs Champi: 6/hit shipped vs 11/hit real;
in-game 12 Gbeto beat 21 Champi 5/5 while the shipped sim had Champi winning).

### 1.2 Temple Guard attack-speed ramp is monotonic; the game uses a decaying 5s window

Real mechanic: reload = `max(min, base − ramp × hits_in_last_5s)` — walking
between targets lets the ramp decay. Shipped engines accumulate forever.
Fixed in branch `simulate.js`; verify/port in both Python engines.
**Affected units:** Elite Temple Guard (Muisca) only (`attack_speed_ramp > 0`).

### 1.3 Trample (blast) reach measured from a point, not the body hull

Blast emanates from the trampler's **body**: reach = attacker.radius +
trample_radius + enemy.radius (edge-to-edge). Point-based measurement drops
the attacker's own radius, so a packed ring around an elephant sits just out
of reach (~1 unit/swing hit vs the game's ~4-6). Fixed in branch
`simulate.js`; verify/port in both Python engines.
**Affected units** (any trample stat > 0): War Elephant, Battle Elephant
(+Elite), Siege Elephant, Elite Cataphract (Logistica), Druzhina infantry
(Slavs Champion/Halberdier), Winged Hussar, War Chariot, Elite Ratha (melee),
Elite Urumi Swordsman, Ibirapema Warrior (+Elite).

---

## 2. The V2 physics package (model corrections, calibrated vs tapes)

Applied as transforms in `headless_sim.js`, configured/frozen in
`sim_v2_model.js` (authoritative rationale + calibration numbers there).
Summary, in the order they were established:

| Knob | Value | What it fixes | Blast radius of the change |
|---|---|---|---|
| `RTRUE` | 1 | Collision radius = the game's `outline_size` (~0.2t) instead of the render formula (2.3× too fat) — unjams melee traffic | ALL melee fights |
| `ADELAY/AJIT` | 0.4/0.8 | Melee arrival wind-up (ship struck the instant in range) | All melee |
| `RETARGET/JITTER` | 1.5/0.8 | Additive cooldown on target switch — reproduces the death-reshuffle stall where coin-flip basins bifurcate | All melee |
| `CHURN/CROWDN` | 2.25/6 | Crowd interference per swing, decays in mop-up | All melee, esp. ramping/massed fights |
| `BLOCK/GAP/BSP` | 1/160/30 | Compact block spawns (arena-like) instead of full-height lines that forbid envelopment | All fights |
| `ENVELOP` | 1 | Max simultaneous attackers per target = ring capacity; overflow spills to flanks/rear. Without it, win-rate wrongly moved with army size at fixed ratio | All melee-vs-melee; biggest for outnumbered high-HP units (Warrior Priest, White Feather Guard pins became native results) |
| `KITE` | 1 | Wall-slide kiting: pinned kiter slides along the arena boundary — a faster ranged unit can actually use its speed edge | All fast ranged kiters (Guecha, Genitour, cav-archer lines, mounted skirms) |
| `KITE_CATCH` | 1.15 t/s | Three-condition interception gate on fleeing: deny kite only if (kiter faster) AND (chaser ≥1.15 tiles/s ABSOLUTE) AND (kiter damage/hit ≤ max(3, 5% chaser HP)) | Ranged-vs-fast-melee: Xianbei Raider caught by Champi; Gbeto/Mameluke/Blackwood still win their races (all 5/5-tape-confirmed) |
| `TRAMPLE_K` | 1.5 | Packing compensation for blast radius (V2 arena packs ~1.5× looser than the game blob) | Trample units (§1.3 list) |
| `GRAZE_K` | 1.5 | Same compensation for the projectile miss-graze test (was dead under RTRUE) | Arambai (full-damage graze), any miss-graze unit |
| `TRAMPLE_CONE` | 60° | Conical blast: Ibirapema's dat `blast_attack_level=162` is a cone; splash lands only in the front arc for `CONE_SLUGS` | Ibirapema Warrior (+Elite) only |
| `MAXS/SEEDS/RAMP` | 180/8/window | Time-cap + seed-count pins; RAMP=window is §1.2 | harness safety |

**Rejected hypotheses (do not re-chase):** speed-RATIO kite gate (inverted
vs tapes — Guecha/ETG ratio 1.10 kites fine, Champi/Xianbei 1.27 fails);
global `TRAMPLE_K` reduction (0.75 fixes Ibirapema but flips War Elephant to
a false win — cone vs true-360 are different regimes).

---

## 3. Data-layer gaps to close at productionization

1. **No blast-shape column.** The ref schema / `ability_registry.py` cannot
   express "conical blast", so `config_combat.py` models Ibirapema as 360°
   trample and V2 hardcodes `CONE_SLUGS` in `headless_sim.js`. Proper fix:
   registry param (e.g. `blast_shape`) + config value + one handler per
   engine (runbooks §3 checklist).
2. **Positionless engines can't express V2.** Kiting, envelopment, cone arcs,
   and wall-slide need positions. `simulation_real.py` (2D) can absorb the
   ports; `simulation.py` (abstract) cannot — it already overrates melee vs
   mobile ranged. Decide its role at rerun (keep for the overlay with a
   documented caveat, or re-point the overlay at V2-derived data).
3. **Single-column seating** in `simulation_real.py` (each army spawns as one
   vertical column → no envelopment, 0% trample splash) is the batch-engine
   analogue of `BLOCK/ENVELOP` and needs the equivalent treatment at port
   time.

---

## 4. Manual/pinned data still in play (all on the branch, none served live)

"Pins" are per-subject `ingame_outcome` overrides in
`apps/video/sim_v2/overrides/*.json` — documented stopgaps where the sim
disagreed with tapes. Current state:

- `elite_temple_guard_muisca.json` — **0 pins** (ENVELOP made the last two,
  Warrior Priest + White Feather Guard, native). Carries two `extra_results`
  rows simmed out-of-batch (Burmese Battle Elephant swap, Champi cross-ref).
- `elite_champi_warrior.json` — **0 pins** (engine reproduces all tapes
  natively; `ingame_wr`/`ingame_hp` display overrides retired).
- `elite_guecha_warrior_muisca.json` — **9 stale pins** (elephants, Centurion,
  Cataphract, Boyar, Ratha, Heavy Camel, Steppe Lancer, Ballista Elephant),
  set before ENVELOP/KITE_CATCH existed. Re-derive, expect most to go native.
- `elite_blackwood_archer_tupi.json` — **3 stale pins** (2 elephants, Chu Ko
  Nu win). Same: re-derive after the rerun.
- `elite_kona_mapuche.json` — 0 pins.

After the full rerun, **every pin must be re-derived and ideally deleted**
(the standing rule: fix the engine, never hand-set outcomes).

---

## 5. Adjacent (non-engine) changes that also move rankings

- **Win-conditions categorization** (`aoe2x/analysis/story_rules_v2.py` +
  `apps/video/sim_v2/win_conditions/`): expected/unexpected labels now come
  from user-declared per-line percentile thresholds, not the old favored()
  cascade. Branch-only; affects video categorization, not site data.
- **Pool-percentile fix for two-unique lines** (`aoe2x/advisor/best_units.py`,
  Kamayuk/Champi on one line): **already LIVE** on staging (`9bc7a56`).
- **Investment-cost columns + regenerated golden DBs** (branch `7d94c3f`):
  the branch's `aoe2_reference.db` is built from game build **180059** and
  carries the Mayans archer-cost patch; staging's DBs are pre-patch. The
  Mayans decision (accept patch → regen `.golden/baseline.json` + full
  re-sim) is an open task and should be BUNDLED with the rerun so the 500k
  sims run once, on the new build's data.

---

## 6. Affected-units index (for reviewing the rerun's ranking diffs)

| Change | Directly affected | Expect ranking movement in |
|---|---|---|
| §1.1 thrower/melee-class armor | 19 units (Gbeto, Mameluke, Throwing Axeman, Chakram, mangonel line, bombard/rocket/trebuchet variants, warships) | Any matchup vs high-PA / low-MA units (infantry with shields, huskarl-likes, rams) |
| §1.2 ramp window | Elite Temple Guard | ETG vs everything (weaker vs mobile/reshuffling fights) |
| §1.3 + TRAMPLE_K trample reach | 12 trample units | Trampler vs massed melee (stronger); swarm counters (weaker) |
| TRAMPLE_CONE | Ibirapema only | Ibirapema vs surrounding swarms (much weaker than 360° model) |
| KITE + KITE_CATCH | All ranged kiters; fast melee chasers (≥1.15 t/s: most cavalry, eagles, Champi-class infantry) | Ranged-vs-melee across the board, both directions |
| ENVELOP + RTRUE + churn/wind-ups | Everything melee | High-HP outnumbered units up; swarm-inflated "wins" down; more honest coin-flips |
| §5 Mayans patch (if accepted) | Mayans archer lines | Mayans archer matchups + cost-based counts |

---

## 7. Full-rerun protocol (the big-PC run)

Ordered; each step's own checklist is in `docs/architecture/runbooks.md`.

1. **Decide Mayans patch** (open task) — if accepted, refresh
   `data/inputs/` extraction + regen reference/main DBs first so everything
   below runs on one game build.
2. **Port §1 fixes** into `simulation_real.py` + `simulation.py` (+ any §3
   items being productionized, e.g. blast shape). `sim_version` bumps
   automatically → all matchup rows stale, as designed.
3. **Port §2 physics** into `simulation_real.py` (or stand up a V2-JS batch
   driver at scale — decide by throughput on the build machine; this package
   is the reference implementation either way). Validate the port against
   the 13-anchor tape sweep BEFORE the batch run.
4. **Re-sim** the full matchup baseline (`rebuild_matchup_baseline.py`,
   external `D:/AI/matchup_baseline_<build>.db` — never committed).
5. **Re-derive**: `derive_unit_rankings.py`, `derive_pool_scores.py`,
   `best_units.py` exports → `derived_data.db`, `pool_scores.db`,
   `civ_power_units/<build>.json`.
6. **Regenerate golden baseline**: `python .golden/capture_baseline.py`;
   `pytest` clean.
7. **Ship the UI engine**: merge the three `simulate.js` fixes (already
   written on the branch) so the interactive page agrees with the data.
8. Commit DBs + JSON on `staging`, smoke-test staging URL, then promote to
   `main` (fast-forward only, with explicit user approval).

Until all of the above happens together: **production engines, DBs, and the
live Battle Sim stay frozen** — a partial ship would make the site disagree
with itself.

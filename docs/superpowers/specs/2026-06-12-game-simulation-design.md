# Game Simulation Engine Viewer — Design

*2026-06-12 · branch `game_simulation` · approved by ddk220 in-session*

## Goal

Recreate AoE2:DE engine behavior in the browser, starting from the smallest
complete economic loop: the **4_lumber** scenario (3 villagers + TC + 1 tree;
TC trains a 4th villager rallied to the same tree; tree is fully exhausted).
The simulation runs from **replay commands only** and is verified against the
game's **real internal state** captured via the CadeRemote gRPC spectator API.

This is the first slice of a long-term project: a browser game engine that can
re-play `.aoe2record` files by *simulating* the game rather than interpolating
heuristics (what `aoe2x/replay` does today).

## Source artifacts (this scenario)

| Artifact | Path | Role |
|---|---|---|
| Replay | `C:\Users\ddk22\Games\Age of Empires 2 DE\76561198053842894\savegame\rec.aoe2record` (2026-06-12 12:40) | Sim input: commands |
| gRPC capture | `D:\AI\aoe2_matchup\lab\captures\4_lumber.frames.bin` (13.4 MB, game build 178524) | Ground truth |
| Probe output | `D:\AI\aoe2_matchup\lab\captures\4_lumber_probe.json` | First decode, kept for reference |

Replay commands (mgz, game-sim time):
`t=7.0 ORDER vills [3652,3654,3656] -> tree 3662` ·
`t=8.6 GATHER_POINT TC 3641 -> tree 3662` ·
`t=10.3 DE_QUEUE villager @ TC` · `t=115.0 RESIGN`.

Ground truth extracted from the capture (entity ids match mgz instance ids):

- Tree 3662: GAIA, master 348, pos (16.5, 74.5), starts at **100.0 wood**,
  **20 HP**; HP hits 0 at t≈14 (felling), wood hits 0 at **t=102**, entity
  removed at t=103.
- Villagers 3652/3654/3656 (master 293, 25 HP) walk at **0.8 tiles/s**, gather
  **≈0.391 wood/s** each, carry caps at **10.0**.
- 11 deposits at the TC: t≈43, 49, 50, 68, 77, 82, 84, 101 (10.0 each) and
  partial final loads 6.72 / 7.94 / 5.64 at t≈106–108. Total ≈ **100.3**.
- 4th villager eid 4236 (master 123) spawns **t=35.26** = queue t 10.27 +
  **25.0 s** train time; auto-tasks to the rally tree; deposits at 68 and 101.
- Starting stockpile per in-game UI: **150 wood** (PlayerAttributes models are
  not materialized by the current decoder — stockpile curve is reconstructed
  as `150 + Σ deposits`, which is sufficient).

## Architecture

**Approach:** one pure-JavaScript engine module consumed by both the browser
viewer and a headless Node verifier. Flask serves static files + scenario
data; no coupling to `apps/website`.

```
apps/engine_viewer/
  server.py                  # Flask, default port 5003
  tools/extract_commands.py  # mgz: .aoe2record -> data/<scen>/commands.json
  tools/extract_truth.py     # gRPC frames.bin -> data/<scen>/truth.json
  data/4_lumber/commands.json  # committed
  data/4_lumber/truth.json     # committed
  public/
    index.html               # viewer shell
    constants.js             # game constants + provenance comments
    engine.js                # deterministic tick engine (NO DOM imports)
    render.js                # isometric canvas renderer + sprites
    app.js                   # wiring: load, tick loop, controls, verify overlay
    assets/                  # sprites borrowed/copied from aoe2x/replay assets
  verify/verify.mjs          # node harness: engine vs truth -> scorecard
```

## Engine model (`engine.js`)

- Fixed **20 ticks/s** deterministic loop; `GameState` = entities map, player
  stockpiles, pending commands, event log.
- Entity task state machines:
  `idle → moving(target) → felling(tree) → gathering(tree) →
  returning(dropsite) → deposit → moving(tree) → …`
  TC: production queue (train timer → spawn adjacent tile nearest rally →
  auto-task to rally target).
- Commands consumed at their replay timestamps: ORDER (gather task),
  GATHER_POINT (rally), DE_QUEUE (train villager), RESIGN (end).
- Mechanics v1: straight-line movement at 0.8 tiles/s (no obstacles on this
  map between tree and TC); tree felling phase (20 HP, rate calibrated so a
  solo villager fells in ≈4.4 s); parallel gathering 0.39 wood/s per villager;
  carry cap 10 → auto-return; deposit adds to stockpile + event; tree empty →
  gatherers keep partial loads, deposit, go idle; tree entity removed.
- Output: per-tick queryable state (for renderer) + event log
  `[(t, kind, data)]` with kinds `spawn`, `deposit`, `tree_felled`,
  `tree_empty`, `end`.
- `constants.js` documents each value's source: dat-known (villager speed,
  gather rate, carry, train time) vs capture-measured (felling duration,
  deposit radius).

## Viewer (`public/`)

Isometric canvas (same 2:1 diamond projection as the replay SPA), sprites for
villager / TC / tree / scout copied from `aoe2x/replay/public/assets` (any
missing sprite gets a procedural placeholder first, generated art later).
Carry state shown as a small log icon on the villager. HUD: wood counter, game
clock, play/pause, speeds 1/2/4/8×, timeline scrub. **Verify overlay**: truth
deposit markers vs sim deposit markers on the timeline, wood-over-time chart
(sim line vs truth line), scorecard table.

## Verification (acceptance criteria)

`node verify/verify.mjs` runs the engine headless against `truth.json`:

| Check | Tolerance |
|---|---|
| 4th villager spawn time | ± 0.5 s |
| Each of the 11 deposit events (time, amount) | ± 1.5 s, amount ± 0.5 |
| Tree-empty time | ± 3 s |
| Total wood delivered | within 1 of 100.3 |
| Final villager count | exactly 4 |

Exit code non-zero on any failure; same scorecard rendered in the viewer.

## Error handling

- Extractors hard-fail if the record/capture lack the expected entities.
- Engine logs-and-skips unknown command types (future replays will have many).
- Server 404s unknown scenarios and lists available ones.

## Out of scope (v1)

Pathfinding/obstacles, other resource types, farms, fog, multiple players,
combat. The task-state-machine design is the extension point for all of these.

## Risks

- gRPC decoder is patch-sensitive (entity-band heuristics) — capture was made
  on build 178524 and decoded cleanly (16 re-anchor resyncs, all benign).
- mgz fork pin must keep parsing current-build SP records (verified today).

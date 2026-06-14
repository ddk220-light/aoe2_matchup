# engine_viewer — browser re-simulation of AoE2 replays

Recreates AoE2:DE engine behavior in the browser from replay commands alone,
verified against the game's real internal state (CadeRemote gRPC capture).
Flat 2D grid view: diamond tiles, square units, 1-tile resources, footprint
buildings. Orientation matches the production replay SPA.

- Run: `python apps/engine_viewer/server.py` → http://127.0.0.1:5003/
  (default scenario `camp300`; `?scenario=<name>` to switch)
- Verify vs ground truth: `node apps/engine_viewer/verify/verify.mjs <scenario>`
- Rebake data: `tools/extract_commands.py <scenario>` (replay) /
  `tools/extract_truth.py <scenario>` (gRPC capture)
- Design: [docs/superpowers/specs/2026-06-12-game-simulation-design.md](../../docs/superpowers/specs/2026-06-12-game-simulation-design.md)

## Scenarios

| Scenario | What it exercises | Verified |
|---|---|---|
| `camp300` (current) | Build a lumber camp (3 villagers), auto-gather a 40-tree forest, train 4 villagers, two drop sites (TC + camp), nearest-dropsite deposits, tree retargeting — goal 300 wood | v2 engine, 12/12 |
| `4_lumber` (v1) | One tree, 3 villagers + 1 trained, single drop site | v1 engine, pinned at commit `4da872d` (16/16) |

The live engine (`public/engine.js`) is calibrated to `camp300`. `4_lumber`
remains loadable as the v1 milestone; its exact v1 deposit numbers were a
property of the v1 single-tree engine (see git history) and are not reproduced
by the unified v2 engine.

## camp300 verification snapshot (2026-06-12, capture build 178524)

```
PASS  lumber camp constructed       done 44.1s
PASS  trained villagers = 4
PASS  spawn #1..#4 ±1s              every ~25s, max delta 0.04s
PASS  wood collected ±15            truth 297.05  sim 310.0  (+4.4%)
PASS  collected @40/80/120/160/200s sim curve tracks truth within 10
ALL 12 PASSED
```

The headline metric is **wood collected over time**. The sim lands at 310 vs
the real 297 (+4.4%) — within the "closely, not 100%" target: the last seconds
before RESIGN deposit in-transit loads, and the sim's villagers finish slightly
more synchronized than the real (desynced) ones, so a load or two extra clears.
The collection *curve* matches the real game almost exactly (e.g. @120s: 90 vs
90, @160s: 180 vs 180).

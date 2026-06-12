# engine_viewer — browser re-simulation of AoE2 replays (4_lumber slice)

Recreates AoE2:DE engine behavior in the browser from replay commands alone,
verified against the game's real internal state (CadeRemote gRPC capture).

- Run: `python apps/engine_viewer/server.py` → http://127.0.0.1:5003/
- Verify vs ground truth: `node apps/engine_viewer/verify/verify.mjs`
- Rebake data: `tools/extract_commands.py` (replay) / `tools/extract_truth.py` (gRPC capture)
- Design: [docs/superpowers/specs/2026-06-12-game-simulation-design.md](../../docs/superpowers/specs/2026-06-12-game-simulation-design.md)

## Verification snapshot (2026-06-12, capture build 178524)

```
PASS  4th villager spawn ±0.5s        truth 35.26  sim 35.25
PASS  8 full-load deposits ±1.5s      max delta 0.85 s
PASS  3 post-depletion partials ±4s   amounts within 0.23
PASS  tree empty ±3s                  truth 101.97  sim 101.05
PASS  total wood ±1                   truth 100.3   sim 100.00
PASS  final villager count = 4
ALL 16 PASSED
```

The wider window on the final partial deposits exists because the real engine
auto-retargets lumberjacks to neighboring trees after depletion before they
head home (visible in the capture); v1 does not model retargeting.

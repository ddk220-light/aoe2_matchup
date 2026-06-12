# engine_viewer — browser re-simulation of AoE2 replays (4_lumber slice)

Recreates AoE2:DE engine behavior in the browser from replay commands alone,
verified against the game's real internal state (CadeRemote gRPC capture).

- Run: `python apps/engine_viewer/server.py` → http://127.0.0.1:5003/
- Verify vs ground truth: `node apps/engine_viewer/verify/verify.mjs`
- Rebake data: `tools/extract_commands.py` (replay) / `tools/extract_truth.py` (gRPC capture)
- Design: [docs/superpowers/specs/2026-06-12-game-simulation-design.md](../../docs/superpowers/specs/2026-06-12-game-simulation-design.md)

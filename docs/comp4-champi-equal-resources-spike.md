# Four Champi civilizations: fractional-HP spike

The owner approved six Armenian bowmen against the eight Inca Champi: five at 50 HP and one at 30 HP. The other three pairs each use eight Champi against seven bowmen at 50 HP. This document describes the **first recorded test**, which completed successfully on September 13, 2026 PDT (game build 180059).

## Preserved Golden

The corrected owner scenario is saved byte-for-byte in [comp4_goldens/comp_4_no_buffer.aoe2scenario](../apps/video/templates/comp4_goldens/comp_4_no_buffer.aoe2scenario). Its [manifest](../apps/video/templates/comp4_goldens/manifest.json) records SHA-256 `c38252f1f99a156ae97247b685268e804c9b7e4395491b06b84b1f34b4723753`, pair ownership, colors, camera and invariants.

The source file in the owner's scenario folder was not changed. The generated game-folder copy is named **Comp4_Champi_Equal_Resources.aoe2scenario**. All retained slots preserve the Golden's exact coordinates, rotations and object IDs. Terrain, player civilizations and colors, diplomacy, starting ages, embedded AI and the eight corrected patrols remain unchanged. P5–P8 are all Armenian and red. There is no buffer army.

See [the original scenario analysis](comp-4-no-buffer-scenario-analysis.md) for the full map and patrol inventory. This template is separate from the existing P2-versus-P3 production Goldens.

## Approved balancing rule

Costs come from the same isolated installed-DAT extraction and technology effects used by the corrected recording cost audit. The generator verifies the extraction hashes against `data/recording-costs.json`. Food, wood and gold each have weight one; these units are produced singly.

| Champi civilization | Cost per Champi | Champi count | Opponent count | Opponent opening HP |
|---|---:|---:|---:|---|
| Incas | 35 food + 25 gold = 60 | 8 | 6 | 5 × 50 + 30 = **280** |
| Mapuche | 50 food + 25 gold = 75 | 8 | 7 | 7 × 50 = **350** |
| Muisca | 50 food + 25 gold = 75 | 8 | 7 | 7 × 50 = **350** |
| Tupi | 50 food + 25 gold = 75 | 8 | 7 | 7 × 50 = **350** |

Armenian Composite Bowmen cost 35 wood + 45 gold = 80. The most expensive Champi variant sets the integer baseline: eight Champi cost 600, so `floor(600 / 80) = 7` opponents. The Inca cost ratio is `60 / 75 = 0.8`; applying it to this **rounded reference baseline** gives `7 × 0.8 = 5.6` opponents' HP. Five full bowmen plus one at 60% HP produce exactly 280 HP, 20% below 350.

This is the owner's reference-based HP handicap, not exact equality of purchase resources. Strict unrounded purchasing would give a different comparison. A partly injured bowman still has its full attack while alive; HP equivalence does not imply proportional damage output. The ordinary 5,000-resource ceiling does not bind these small armies.

A 20-damage effect targets only the final retained P5 bowman and executes before the original camera/patrol effects. It changes **current HP**, not maximum HP. No attack, armor or other unit attributes are modified.

## First recorded result

The saved gRPC timeline confirms the complete approved opening at **1.008 game seconds**, before the first combat damage. All subject armies still have their full HP: Incas 520, Mapuche 640, Muisca 520, Tupi 520. Opponent totals are 280/350/350/350.

| Pair | Winner | Champi survivors | Remaining HP | Share of starting Champi HP | Final enemy elimination, game seconds |
|---|---|---:|---:|---:|---:|
| Incas vs Armenians | Incas | 6 / 8 | 326 | 62.7% | 14.998 |
| Mapuche vs Armenians | Mapuche | 6 / 8 | 328 | 51.3% | 19.432 |
| Muisca vs Armenians | Muisca | 4 / 8 | 92 | 17.7% | 27.852 |
| Tupi vs Armenians | Tupi | 5 / 8 | 197 | 37.9% | 20.626 |

The recorder tracks explicit pairs 1↔5, 2↔6, 3↔7 and 4↔8. It stops after all four pairs have a stable four-game-second elimination. P1 revealers and invisible support objects do not count as fighters. This is one observed battle per pair, not a simulation or a repeated-trial ranking.

The initial automatic check incorrectly required stream master 1802. The actual stream retains the **placed ID 1800**, while its bowmen start at 50 HP. The correct 20-point injury is recorded at 1.008 seconds. The check was repaired to validate the authored master IDs and exact expected opening HP. The original status rejection is retained, with a separate hash-bound validation receipt. A later diagnostic restart was unnecessary; it is not used for these results or the review recording.

## Reproduce and inspect

From the repository root, with the video venv and audited extraction available:

```powershell
$env:PYTHONPATH='apps/video;.'
$env:PYTHONIOENCODING='utf-8'
& apps/video/.venv/Scripts/python.exe apps/video/build_comp4_scenario.py --output data/local/new-comp4/Comp4_Champi_Equal_Resources.aoe2scenario
& apps/video/.venv/Scripts/python.exe -m unittest apps/video/tests/test_comp4_balance.py
```

The generator refuses to overwrite an existing output or an altered Golden. It emits the scenario and a companion JSON with cost-effect evidence, extraction hashes, slot IDs, counts and HP allocations. Copy only the generated scenario into the game's scenario folder, load it in the editor, then arm the recorder before clicking Test:

```powershell
& apps/video/.venv/Scripts/python.exe apps/video/capture_comp4_spike.py --out data/local/new-comp4/capture-01 --seconds 180
```

FFmpeg must be on PATH; recording uses the existing desktop video and loopback-audio backend. The gRPC mTLS files must be installed as described in [the gRPC README](../aoe2x/grpc/README.md). The capture helper performs no UI input. Keep the game visible, inspect `status.json` for ARMED, then start through the UI. Do not use the legacy two-owner `.END` or decoder for this layout.

Local evidence from this spike:

- `data/local/comp4-champi-spike/Comp4_Champi_Equal_Resources.aoe2scenario` and companion JSON: generated input and cost plan.
- `data/local/comp4-champi-spike/capture-01/raw.mp4`: original uninterrupted screen recording with game audio.
- `data/local/comp4-champi-spike/Champi_Four_Civilizations_Test.mp4`: review clip from that original capture, starting at the first visible game frame (raw time 28.916667 seconds), with the editor/loading lead-in removed. The clip passed a full FFmpeg decode. It is a test capture; a desktop notification remains in the lower-right margin.
- `data/local/comp4-champi-spike/capture-01/frames.bin`: complete length-prefixed protobuf sequences.
- `capture-01/timeline.jsonl`: per-frame, per-owner, per-unit HP and identities.
- `capture-01/sequence-times.jsonl`: stream timestamps and wall-clock arrival times.
- `data/local/comp4-champi-spike/validation.json`: the verified pre-combat state, pair results and original media/data hashes.
- `data/local/comp4-champi-spike/tests.log`: five passing balance and structural-preservation checks.

The capture's initial stream master is an identity field, not sufficient proof of the displayed Elite upgrade label. This spike preserves the owner's placed unit type and verifies its HP; a production generalization should also validate resolved runtime combat attributes. Existing cross-pair alliances and any shared team bonuses are preserved, as requested. No four-panel production overlay, automatic full roster or YouTube upload is added by this spike.

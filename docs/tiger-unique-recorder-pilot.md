# Tiger Cavalry unique-unit recorder pilot

Approved scope: exclude Gurjara Camel Scout and both Winged Hussars from the
proposed unique-unit roster. Run only the first five opponents for review before
recording the remainder. Preserve the goldens exactly, including their full
Player 4 screen; the suggestion to reduce it to five was withdrawn.

Player 2 is always Wei Elite Tiger Cavalry. Player 3 is the opponent and Player 1
inherits Player 3's civilization for music. Melee damage does not make a thrown
weapon a melee unit: Throwing Axemen, Gbeto, and Mamelukes use the ranged golden
with its Player 4 screen on the opponent's side.

The repeatable queue is `aoe2lab.recorder.first-five.toml`:

| Order | Opponent | Tiger count | Opponent count | Golden |
|---|---|---:|---:|---|
| 1 | Armenian Elite Composite Bowman | 15 | 27 | melee_vs_ranged |
| 2 | Armenian Warrior Priest | 17 | 27 | melee_vs_melee |
| 3 | Aztec Elite Jaguar Warrior | 17 | 27 | melee_vs_melee |
| 4 | Bengali Elite Ratha (melee) | 23 | 27 | melee_vs_melee |
| 5 | Bengali Elite Ratha (ranged) | 23 | 27 | melee_vs_ranged |

Counts use the existing equal-resource purchase rule with cap 27. The ranged
golden contains nine Player 4 scout-line objects; their positions, civilization,
starting age, and diplomacy are preserved. The melee golden has no Player 4 units.

Run with `scripts/aoe2lab.ps1 batch aoe2lab.recorder.first-five.toml --phase recorder`.
Each completed run retains its raw MOV, gRPC frames, metadata, scenario, and HP
data in a structured folder, plus a battle-start-clipped MP4 for phone review.
Repeating the queue validates and reuses completed bundles.

Composite Bowman, Jaguar Warrior, and Mameluke metadata live in a separate
recording registry because they do not yet have calibrated simulator fixtures.
Their costs come from the local reference database and object IDs from the
scenario parser. A simulation request for these units fails explicitly.

Offline validation generated all five scenarios and checked roster positions,
golden camera, Player 4, AI, diplomacy, triggers, and spectator civilization.
Planner regressions cover all three melee-damage ranged units and preserve P2.

## Completed pilot, 2026-09-07

The five-job recorder batch completed with no failures, one capture per matchup.
All five structured bundles passed checksum validation. Outputs are under
`aoe2x/js_simulation/calibration/lab/runs/tiger_unique_*/live/run_001/`.

| Order | Battle clip seconds | Winner |
|---|---:|---|
| 1 | 24.957 | Composite Bowman (P3) |
| 2 | 38.205 | Warrior Priest (P3) |
| 3 | 30.315 | Jaguar Warrior (P3) |
| 4 | 38.895 | Tiger Cavalry (P2) |
| 5 | 46.016 | Tiger Cavalry (P2) |

Validation: four Node planner tests and eighteen recorder/workflow tests passed.
The raw recordings and gRPC streams remain expanded and unchanged; phone-review
clips trim both audio and video to the first detected in-game frame. The user
subsequently approved the full campaign; see `all-unique-unit-recording-campaign.md`.

All five numbered MP4 clips were successfully Taildropped to the user's iPhone;
the final transfer completed at 10:03:39 local time on 2026-09-07.

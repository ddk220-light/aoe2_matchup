# Recovering a completed fight without a rerun

Two recordings flagged as failures on 2026-09-15 were complete:

| Recording | Opening counts | Result | Terminal stream time |
|---|---|---|---:|
| Persian Savar vs Tatar Flaming Camel | 24 vs 27 | Mutual elimination, both 0 HP | 10.450 s |
| Bulgarian Cavalier vs Tatar Flaming Camel | From saved plan | Mutual elimination, both 0 HP | 12.304 s |

The last camel explosion eliminates the remaining cavalry. The saved videos
show the game-end dialog and the gRPC stream confirms both armies at zero.
The spectator's "You are victorious" banner does **not** identify a winning
combat army. These outcomes must be displayed as draws.

## Why the recorder rejected them

The live decoder waits four seconds of simulation time after an army reaches
zero, to allow units that spawn after death to appear. The game-end dialog
freezes the clock before that grace expires, so no live `.END` is written.
The old whole-second HP sidecar also misses the final fractional-second
explosion. Its last sampled row can incorrectly show survivors.

## Safe recovery

`aoe2x/lab/capture_recovery.py` is called by capture validation only when the
raw video, frames, metadata and HP sidecar exist, but the end marker does not.
It requires:

1. Exact planned starting counts in the decoded full-resolution stream.
2. Both armies at zero HP, confirmed by at least three observations spanning
   at least 250 ms of simulation time at the end of the stream.
3. A recorded game-end dialog at two points in the saved video.

Recovery retains the old HP sidecar, reconstructs all HP rows from individual
stream updates, and writes a distinctly labeled recovery receipt with source
hashes. It does not invent a live completion time. Scenario validation, bundle
hash checks and battle-video export still run normally. Failed diagnostics
are retained. Video alignment remains a separate measured rendering step.

This path deliberately rejects unfinished fights, mismatched starting armies,
temporary zero states followed by replacement units, and insufficient terminal
observations. Its regression tests are in
`aoe2x/lab/tests/test_capture_recovery.py`.

Inspection artifacts and successive explosion frames are under
`data/local/knight-comparison-recovery/`. Original attempts remain in their
AoE2 Lab run directories. No game replay was needed.

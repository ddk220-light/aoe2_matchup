# All unique land units: reusable roster and recording campaign

Goal: preserve raw gameplay recordings and gRPC frame streams for every approved
opponent of Wei Elite Tiger Cavalry, for future overlays and comparison against
simulation. Keep files in structured local folders; do not zip, remove raw data,
or Taildrop videos during this campaign.

`data/unique-unit-roster.json` is the reusable, machine-readable roster for AoE2
Lab / a future Unity Lab integration. It includes 74 entries in civilization-name
order, counting selectable Ratha and War Chariot modes separately. Tiger Cavalry
remains in the reusable roster but is excluded from its own opponent queue.
The approved scope excludes Camel Scout, both Winged Hussars, ships, heroes, and
ordinary regional lines. Team-shared unique units remain included.

`aoe2lab.recorder.all-unique.toml` contains 73 matchups and reuses the five pilot
job IDs, leaving 68 new recordings. Player 2 is always Wei Elite Tiger Cavalry;
Player 3 is the opponent, and Player 1 inherits Player 3's civilization for music.
Counts follow the existing equal-resource rule with a 27-unit cap. All golden
scenarios, including the full Player 4 screen in ranged battles, remain unchanged.
Throwing Axemen, Gbeto, and Mamelukes count as ranged units.

## Operation

Run from the repository root using the video Python environment:

```powershell
apps/video/.venv/Scripts/python.exe -u -m aoe2x.lab.recording_campaign aoe2lab.recorder.all-unique.toml --reports aoe2x/js_simulation/calibration/lab/campaigns/tiger-all-unique
```

The runner is serial and resumable. Completed bundles are checksum-verified and
reused. It writes status after each result and reports after matches 10, 20, 30,
40, 50, 60, 70 and the final remainder. Failures produce immediate reports, retain
diagnostics, and three consecutive failures stop the runner. A process lock
prevents duplicate campaign runners. A `STOP` file in the report folder requests
a stop between matchups. Remove that stop request before deliberately resuming.

Reports are under `aoe2x/js_simulation/calibration/lab/campaigns/tiger-all-unique/`.
The Codex heartbeat named "Tiger Cavalry recorder progress" checks every five
minutes and reports new milestones, actionable failures, and completion here.
It stays quiet between changes and sends no videos.

Each run under `aoe2x/js_simulation/calibration/lab/runs/<job>/live/run_001/`
contains raw MOV video, gRPC `.frames.bin`, metadata, decoded HP, saved scenario,
logs, checksummed inventory, and a battle-start MP4. The inventory records the
timeline offsets needed for overlays. Reports certify automated capture checks;
they do not establish visual quality or simulation accuracy. Recording-only units
remain separate from the calibrated JavaScript simulator roster.

Special cases retain review notes in the roster: Missionary conversions change
ownership; Flaming Camel suicide damage may cause simultaneous elimination.
These cases must not be treated as validated elimination-only simulation matches
when capture validation reports an exception.

Prelaunch checks generated and validated all 73 scenarios, including camera,
positions, AI, diplomacy, Player 4, and spectator civilization. Twenty Python
tests and four Node planner tests passed. The initial detached launch exposed a
legacy Windows code-page failure; the runner now sets UTF-8 explicitly.

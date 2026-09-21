# Four knight-line civilizations

Owner request September 15, 2026: individual standard-Golden game captures for
Frankish Paladin, Teutonic Paladin, Lithuanian Paladin with four relics, and
Persian Savar versus the approved unique-unit roster. Raw battle videos and full
gRPC frames only; overlays and publishing are a later stage.

## Armies and conditions

- Franks, Teutons and Lithuanians: 74 opponents each.
- Persians: 73 opponents; exclude Savar versus itself. Total: 295.
- All subjects cost 60 food + 75 gold per physical unit and use one population.
  The three new Paladin identities were independently audited against the same
  installed-DAT cost effects as the existing catalog. Old catalog entries were
  preserved, and the prior catalogs were snapshotted before additions.
- Use [the approved geometric formula](BALANCE_POLICY.md), cap 27. The owner
  removed the former 5,000-resource ceiling. For example, 27 Paladins face 15
  Houfnice, 17 Mounted Trebuchets or 20 Elite War Elephants.
- P2 is the featured cavalry, P3 the opponent. Preserve Golden positions,
  full starting HP, P1 civilization=P3, and the authored nine-Hussar buffer in
  melee/ranged battles. These are separate games, not a four-civ allied map.

## Lithuanian four-relic spike

The original pilot set native resource 7 to four, but game telemetry still
showed 11 damage against the Composite Bowman's 5 melee armor: 16 total attack.
That pilot is excluded from the campaign, even though file/count validation
passed. Its original media and diagnostics remain available as rejected evidence.

The owner approved a direct attack trigger. `apply_lithuanian_relics` in
`apps/video/build_run.py` appends one enabled, non-looping Modify Attribute
effect: source player 2, unit master 569, attack attribute 9, attack class 4,
operation ADD, quantity 4. It modifies all P2 Paladins' melee attack; no other
owner/unit class, resource, research, armor or movement changes. No actual relic
objects or relic-counter effects are combined with this method.

The new plan records `lithuanianRelics: 4` and
`lithuanianRelicMode: attack_trigger_v1`, affecting its plan hash. Lithuanian jobs
use the `_attack4` suffix, distinct from the rejected resource-counter pilot.
Scenario validation checks the exact effect fields and all original Golden
mechanics. Simulation is rejected for this modifier until an exact fixture is
provided; these requests use the real game recorder.

The corrected Armenian pilot verified 180 starting HP per Lithuanian Paladin,
61 nonlethal 15-HP drops on Composite Bowmen, and one aggregate 30-HP drop
consistent with two hits in a frame. This confirms 20 total attack, compared
with 16 in the unboosted pilot. Other pilot opening HP was 192 Franks, 180
Teutons, 165 Savar. Frankish/Teutonic damage to these bowmen was 13 per hit;
Savar dealt 17 including its own anti-archer bonus.

Evidence: `data/local/paladin-line-comparison/attack4-validation.json` and
`pilot-stats-qa.json`, with source frame hashes. The four valid pilot recordings
are reused. The three non-Lithuanian pilots retain their original, nonbinding
5,000-budget metadata and hashes; their counts equal the new uncapped formula.

## Capture and storage

Work folder: `data/local/paladin-line-comparison`.

```powershell
$env:PYTHONPATH='apps/video;.'
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONUTF8='1'
apps/video/.venv/Scripts/python.exe apps/video/run_champi_comparison_capture.py --work data/local/paladin-line-comparison
```

Only one hidden recorder worker may run. Inspect `worker.json`, `worker.log`,
`worker.err.log` and `capture/status.json` before resuming. The runner reuses only
verified jobs present in the current manifest; rejected/superseded pilot IDs do
not count. Opponents are ordered by civilization, with subjects interleaved.
Existing capture checks and ten-match reports run automatically.

The worker archives verified captures to `D:/AoE2 Renders/paladin-line-{franks,
teutons,lithuanians,persians}`. Each folder holds named MP4/frames pairs and the
small `run.json` reconstruction index. SHA-256 verification precedes pruning
local media duplicates. Original metadata and catalog provenance stay local.
See [compact storage](COMPACT_STORAGE.md).

`PAUSE` in the work folder requests a boundary stop; the worker also checks the
8-GiB local-space reserve and existing thermal guard. GPU temperature is readable;
CPU sensor data was unavailable/stale at startup, so CPU thermal monitoring is
not verified. The previously paused scheduled automation remains paused; this
campaign runs through its own background worker.

`prepare_paladin_comparison.py` prepares a new campaign and refuses accidental
replacement. Its explicit `--refresh-preflight` was used once for the owner's
no-ceiling revision before starting the main worker. Do not run it or change
catalogs while this campaign is capturing.

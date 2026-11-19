# Norse standard-unit recordings

Prepared by apps/video/prepare_norse_standard_capture.py. Work directory:
data/local/norse-standard-capture. This is a new raw game capture campaign;
no prior capture is replaced. No simulator, render or upload is requested.

Three subjects: Danish Elite Jomsviking, Saxon Elite Hearth Troop, Varangian
Elite Jarl. Fourteen opponents, five separately launched battles each: 210 total.
Each repeat has its own r1-r5 job ID, raw recording, frames and statistics.
The first pilot is one of those five recordings, not an extra throwaway match.

## Reference opponents

| Civilization | Opponents |
| --- | --- |
| Spanish | Champion, Paladin, Hussar, Elite Skirmisher |
| Chinese | Cavalier |
| Saracens | Arbalester, Heavy Cavalry Archer, Hand Cannoneer |
| Turks | Heavy Camel Rider |
| Cumans | Elite Steppe Lancer |
| Bengalis | Elite Battle Elephant, Elite Elephant Archer, Heavy Scorpion |
| Incas | Elite Champi Warrior |

Selection uses the installed DAT and shipped civilization tech trees. Few
civilizations are preferred, but ordinary combat stats take priority. Spanish
Hand Cannoneers and Saracen Camels are deliberately avoided because of their
combat bonuses. Arbalester is the interpretation of "war blaster"; Elite Champi
Warrior is included separately from Champion.

Regional lines have no entirely generic fully upgraded provider. The exceptions
are explicitly recorded in opponents.json: Cuman speed; Bengali Paiks, elephant
resistance and unavailable Thumb Ring; Inca Fabric Shields and food discount.
These are representative available variants, not bonus-free laboratory units.
All available Post-Imperial technologies apply. Initial game HP/counts are gated.
Chinese replace the original Spanish Cavalier selection: Spanish Cavaliers
automatically became Paladins in Post-Imperial captures (180 opening HP rather
than 140). Existing frozen records are historical evidence, not silently changed
plans. The detailed-winter correction is documented in
[DETAILED_STANDARD_CAPTURE.md](DETAILED_STANDARD_CAPTURE.md#chinese-cavalier-correction).

## Balance and scenery

Use approved weighted geometric counts: food 1, wood 0.9, gold 1.1, full discounts,
one comparison population per physical unit, 27 cheaper units, no resource cap.
Ranged versus melee uses 5-10 Spanish Hussars, scaled to actual fielded weighted
ranged-army cost. Jarl is ranged. Installed DAT costs include maximum Saxon
Hearth Troop discount. Requested and planned counts are preserved per job.

Winter Scenic is copied into each family's own Golden geometry, leaving armies,
AI, diplomacy, camera and patrols intact. The combat lane and an extra boundary
row remain flat; no blocking scenery intrudes. Scenery and audit hashes are in
plan identity. Changed files fail preflight; simulation refuses these visual
variants instead of silently simulating a different map. Goldens are unchanged.

## Start/resume

Run from the repository root in PowerShell:

    $env:PYTHONUTF8='1'
    $env:PYTHONPATH='apps/video;.'
    & apps/video/.venv/Scripts/python.exe apps/video/run_knight_expansion.py --work data/local/norse-standard-capture

Prepare once only. Never regenerate frozen catalogs or plans while capturing.
Before startup, open Scenario Editor and set its Load Scenario search filter
to "Matchup Run". A leftover biome/civilization filter hides the staged file.
The queue lock and recorder mutex prevent duplicate workers. Check process
liveness and existing queue status before resuming. Existing verified jobs are
reused; only pending jobs run. Use the active campaign's PAUSE file for a safe
boundary pause. The queue PAUSE file also blocks the next campaign. Thermal
checks run every 15 minutes; storage below the local reserve stops new battles.
CPU temperature must be reported unavailable if its sensor is stale.

Keep local raw videos, frames, recording metadata, results, frozen catalogs,
plans, scenario files and audits. Future overlay or representative-run selection
can reuse them. Do not discard four repeats after choosing a representative.
Run bundles are under aoe2x/js_simulation/calibration/lab/runs/norse_std_*/live/run_001.
No scheduled task or external-drive move is part of this request.

## Network delivery and Jarl without Hussars (October 1, 2026)

The original 210 captures completed. The owner subsequently requested copies to
`\\100.123.128.35\AoE2-Incoming`, plus a Jarl comparison without a frontline.
Keep the original captures intact. `prepare_jarl_no_hussar.py` freezes only the
40 changed trials (eight melee opponents, five repeats). It checks the installed
DAT and frozen catalogs, then asserts both armies and their balance values match
the original plans. The 30 ranged/ranged trials already had no buffer and are
reused, explicitly identified in `data/local/jarl-standard-without-hussar/selection.json`.
They are not additional independent samples.

New no-buffer trials use the previously audited winter `ranged_vs_ranged` Golden
derivative, including its correct diplomacy and patrols; never remove only P4's
units from the mixed-family template. Preflight confirms zero P4 units. Resume:

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONPATH='apps/video;.'
apps/video/.venv/Scripts/python.exe -u apps/video/run_knight_expansion.py --work data/local/jarl-standard-without-hussar
```

`copy_norse_standard_to_share.py --follow` copies complete sets to these folders,
each containing `Standard_Units_Winter_5_Repeats`:

- `Elite_Jomsviking`
- `Elite_Hearth_Troop`
- `Elite_Jarl_with_Hussar`
- `Elite_Jarl_without_Hussar`

Each set has 70 named MP4/frame pairs with `_r01` through `_r05`, a `run.json`
with per-trial plans, results, clock alignment and checksums, and a small metadata
folder with frozen catalogs, manifests and winter scenery/audits. `with_Hussar`
describes the original mixed-matchup policy; ranged/ranged trials had no buffer
in either set. The copy worker waits for the new 40-trial campaign to finish
before delivering the complete combined 70-trial no-frontline set.

The worker uses a lock, claims only a new destination folder, preserves existing
files on conflicts, verifies source/destination SHA-256, and keeps a durable
receipt at `data/local/norse-standard-delivery/status.json`. All local sources
remain; no deletion is authorized by this copy tool. The share must retain at
least 4 GiB free. No recurring automation is created. Start or resume the finite
copy worker with the same environment as above:

```powershell
apps/video/.venv/Scripts/python.exe -u apps/video/copy_norse_standard_to_share.py --follow
```

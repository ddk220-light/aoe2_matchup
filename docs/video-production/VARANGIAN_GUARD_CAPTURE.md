# Elite Varangian Guard capture

Approved September 22, 2026: capture Byzantines, Danes, Saxons, Varangians,
then Vikings, separately against the unchanged 77-unit unique-unit roster.
These five regional subjects are not added to the opponent roster: 385 battles.
All five are melee for scenario selection, including Varangians with Gothikon.

Installed master 2704 has a base cost of 65 food + 45 gold. Saxons receive the
foot-soldier discount: 5% per controlled Town Center/Castle, capped at 20%.
At the approved maximum, Saxons cost 52 food + 36 gold (91.6 weighted resources);
the other four civilizations cost 65 food + 45 gold (114.5 weighted resources).
The [official Saxon description](https://www.ageofempires.com/news/saxons-civilization-deep-dive/)
explicitly includes Barracks Varangian Guards. Installed English help 120209
specifies the percentage and cap.
The preparation checks the installed DAT and extraction hashes, civilization
availability, every opponent cost, and all generated plans before capture.
Golden Post-Imperial settings supply each civilization's available technologies.
Pilot opening HP is 80, except Vikings at 96; each recorded pilot is reused.

Use the existing weighted geometric count policy: 27 cheaper physical units,
food 1, wood 0.9, gold 1.1, full discounts, one population per physical unit,
no resource ceiling. Ranged opponents receive 5–10 extra Hussars according to
their actual fielded weighted army cost. The first Armenian matchup is 25 Saxon
Guards versus 27 Composite Bowmen; the other four Guard civilizations field 23.
Six Hussars support the bowmen in either case.

## September 27 Saxon correction

The original pricing code incorrectly restricted this bonus to Hearth Troops.
All 77 saved Saxon plans and recording receipts used the undiscounted price;
all 77 army-count pairs change with the correction, including six buffer changes.
This is not a DAT update: the installed DAT hash still matches the original audit.
The other four Guard campaigns and Saxon Mounted Crossbowmen need no retakes for
this error. The Hearth Troop discount was already applied correctly.

Preserve the old frozen campaign and archived recordings as historical evidence.
`apps/video/prepare_saxon_guard_cost_retakes.py` writes the count-by-count audit
to `data/local/saxon-guard-cost-audit/REPORT.md`. With `--prepare`, it corrects
only the live Saxon Guard cost entry and freezes 77 isolated replacement jobs in
`data/local/saxon-guard-cost-retakes`. It compares opponent prices and Golden
identities to the old plans before authorizing any retake; it does not reprepare
the old five-civilization queue. Run the new queue with:

```powershell
$env:PYTHONPATH='apps/video;.'
$env:PYTHONUTF8='1'
apps/video/.venv/Scripts/python.exe apps/video/prepare_saxon_guard_cost_retakes.py --prepare
apps/video/.venv/Scripts/python.exe -u apps/video/run_knight_expansion.py --work data/local/saxon-guard-cost-retakes
```

New captures stay local, retaining battle MP4s, frames and reconstruction metadata.
No old recordings or external files are deleted or overwritten.

## Original five-civilization preparation

Prepare once, then start or resume the queue:

```powershell
$env:PYTHONPATH='apps/video;.'
$env:PYTHONUTF8='1'
apps/video/.venv/Scripts/python.exe apps/video/prepare_varangian_guard_capture.py
apps/video/.venv/Scripts/python.exe -u apps/video/run_knight_expansion.py --work data/local/varangian-guard-capture
```

Do not reprepare an existing queue. `queue.lock` prevents duplicate supervisors;
the recording mutex serializes game control. Each civilization uses the existing
pilot gate, ten-match reports, disk checks and 15-minute thermal safeguards.
Current state is in `data/local/varangian-guard-capture/status.json`, followed
by each civilization's `supervisor.json`, `pilot-validation.json` and
`capture/status.json`. Logs are `worker-output.log` and `worker-error.log`.

This queue omits `archiveRoot` and retains raw captures locally; there is ample
local room and recording need not depend on a removable drive. Preserve battle
MP4s, frames and metadata for later compact transfer under
[the retention rules](RECORDING_RETENTION.md). No overlays, simulator runs,
uploads, or scheduled task are started. Previous captures are untouched.

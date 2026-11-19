# Mounted Crossbowman follow-on queue

## September 23: four additional variants

After the original eight completed, the user authorized Britons, Celts,
Bohemians and Burgundians, in that order. Britons and Celts use Heavy Mounted
Crossbowman (2701); Bohemians and Burgundians use Mounted Crossbowman (2700).
All four cost 40 wood + 65 gold (107.5 weighted resources). These are distinct
combat variants, not repeats of the completed sets. Vikings are excluded.
Spanish reuse Saxon results.

Prepare once with `prepare_mounted_crossbow_capture.py --additional --activate`
and run `run_knight_expansion.py --work data/local/mounted-crossbow-expansion`.
The original queue and frozen plans remain intact. The additional queue has
308 captures, the same 77 opponents, unchanged count/support rules and pilot
gates. Preparation requires all original 616 results to be verified.

The existing regional copy and move workers automatically include this queue
when its `queue.json` exists. Restart them once if they already finished the
original 1,001 recordings. They skip their completed receipts, copy each new
complete civilization to `D:/AoE2 Renders/mounted-crossbow-<civ>`, and reclaim
local media only after verification. Capture proceeds on the next civilization
in parallel. No hourly scheduled check-in is enabled.

The user then authorized Italians as the fifth additional set: standard Mounted
Crossbowman (2700), 65 HP, 40 wood + 65 gold. Start
`run_italian_mounted_crossbow_after_expansion.py` with the video virtual
environment. Its exclusive `italian-handoff.lock` prevents duplicate handoffs.
It waits for all four current campaigns and pending exports to verify, acquires
the released capture queue lock, then appends only Italians' 77 frozen plans.
It resumes the established runner, which skips all four completed sets.
The combined expansion total becomes 385. `italian-handoff-status.json` records
the waiting/preparation/capture state. Archive workers discover the appended
campaign through the queue; the controller restarts them only if their lock is
free and the enlarged collection is unfinished. Final regional archive total:
1,386 pairs. All previous plans and external archives remain intact.

Approved September 22, 2026: after all 385 Varangian Guard captures verify,
record the eight variants below in this order against the same 77 unique-unit
opponents. This adds 616 battles. Keep all raw videos, binary frames and rebuild
metadata on the PC. No external drive, overlays, simulator runs or uploads.

| Civilization | Highest available version | Imperial cost | Weighted cost | Pilot HP |
|---|---|---|---:|---:|
| Danes | Heavy Mounted Crossbowman | 40W + 65G | 107.5 | 75 |
| Saxons | Heavy Mounted Crossbowman | 40W + 65G | 107.5 | 75 |
| Varangians | Heavy Mounted Crossbowman | 40W + 65G | 107.5 | 85 |
| Franks | Heavy Mounted Crossbowman | 40W + 39G | 78.9 | 66 |
| Portuguese | Mounted Crossbowman | 40W + 52G | 93.2 | 65 |
| Sicilians | Heavy Mounted Crossbowman | 40W + 65G | 107.5 | 75 |
| Poles | Heavy Mounted Crossbowman | 40W + 65G | 107.5 | 75 |
| Teutons | Heavy Mounted Crossbowman | 40W + 65G | 107.5 | 75 |

Installed DAT masters are 2700 and 2701. Portuguese lack the Heavy upgrade;
Franks' unique technology reduces gold by 40%; Portuguese reduce gold by 20%.
Saxons' Hearth Troop discount does not apply. Costs and available versions are
verified against `data/local/dat-release-audit/installed` and its source hashes.
All eight are ranged, and receive the existing scaled Hussar support only
against melee opponents. Preserve all Golden templates. Post-Imperial game
research supplies available combat technologies; the pilot verifies counts/HP.

The current [balance policy](BALANCE_POLICY.md) remains unchanged: food 1,
wood 0.9, gold 1.1, full discounts, 27 cheaper units, rounded geometric counts,
one comparison population per physical unit and no resource ceiling.

## Prepare and start

```powershell
$env:PYTHONPATH='apps/video;.'
$env:PYTHONUTF8='1'
apps/video/.venv/Scripts/python.exe apps/video/prepare_mounted_crossbow_capture.py
apps/video/.venv/Scripts/python.exe -u apps/video/run_mounted_crossbow_after_guards.py
```

The first command only audits and saves `follow-on-request.json` and
`release-cost-audit.json` in `data/local/mounted-crossbow-capture`. It does not
change active catalogs. The handoff waits for the Guard queue's COMPLETE state,
385 verified results and all five exact manifest/result sets, then waits for its
queue lock to release. Only then does it run preparation with `--activate` and
the existing `run_knight_expansion.py --work data/local/mounted-crossbow-capture`.

One handoff owns `handoff.lock`. Its state is `handoff-status.json`; the queue
records `status.json`. Each civilization records `pilot-validation.json`,
`supervisor.json`, `capture/status.json`, and worker logs. Never run activation
while Guards are active or recreate a frozen queue. Reuse valid captures and
pilots. The preparation validates every job ID as well as costs/counts; this
includes punctuation in Ratha opponent names.

The hourly app monitor checks both queues and the handoff, worker liveness,
advancing files, exports, disk reserve and existing thermal guards. It can
repair/resume authorized work without duplicate game drivers. Respect later
user pauses; report unavailable CPU temperature honestly. Keep at least 8 GiB
local reserve, stop new battles at a safe boundary if necessary, and never
delete raw sources or depend on the disconnected archive disk. Follow
[recording retention](RECORDING_RETENTION.md) for any later authorized transfer.
Notify on meaningful progress, completion or actionable failures; once both
queues finish, report final counts and pause the hourly monitor.

## September 23: authorized external copies

The user reconnected SAFEHOUSE and authorized archiving completed Guard and
mounted crossbow sets. This supersedes the earlier local-only restriction;
capture continues locally until each complete civilization set verifies. Run
`apps/video/copy_regional_capture_archives.py` with the video virtual environment
and `PYTHONPATH=apps/video;.`. A single lock prevents duplicate copy workers.
The worker waits for each civilization's exact 77 verified results with no
pending exports, then retains named battle MP4s, binary frames, and `run.json`
under `D:/AoE2 Renders/varangian-guard-<civ>` or `mounted-crossbow-<civ>`.

Verify SAFEHOUSE's Buffalo physical serial `00000107000079B6` and volume serial
`5EA9EEEF`; preserve 4 GiB external free space. The worker checks volume identity,
source and destination checksums, and refuses conflicts or unowned folders.
The copy worker never removes local sources or replaces existing external files. Progress,
ownership receipts, logs and the lock are in
`data/local/storage-audit/regional-copy`. If the drive disconnects, copying stops
without altering sources; local capture may continue while storage is safe.
The user subsequently stopped the hourly scheduled check-ins and explicitly
requested moving completed sets to free the PC. The hourly automation is PAUSED;
the recording, copy and cleanup workers continue independently.

Run `apps/video/move_verified_regional_sources.py` alongside the copy worker.
It waits for the whole 77-match civilization to finish and for its external
archive to be marked complete. It verifies the archive index, video/frame
checksums, and unchanged local inputs before deleting individual local raw MOV,
clean MP4, frames and rebuildable HP JSON files. It never deletes recursively or
modifies the external archive. Small local provenance and `archived.json` links
remain; use `apps/video/materialize_compact_recording.py` to rebuild inputs from
the external `run.json` without replaying the game.

Cleanup has its own `move.lock`, `move-status.json`, and `move-*.log` files under
`data/local/storage-audit/regional-copy`. Each deleted file has a durable receipt.
Copy receipts describe source retention at copy time; the later move receipt is
authoritative for whether local media has been reclaimed. Both workers stop on
drive identity errors or thermal pauses and preserve anything not yet verified.
The final Teutonic set is automatically copied and reclaimed after capture and
exports finish. Existing external contents and active recordings are untouched.

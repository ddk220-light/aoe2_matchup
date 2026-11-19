# Detailed winter standard-unit trials

The approved batch uses **Winter Campaign Study - Detailed Battlefield**, the
reviewed campaign-inspired snow, broken-road, glade and mountain scenery. It is
new requested footage; previous winter and unique-unit captures remain valid and
untouched. No overlays, simulator runs or YouTube uploads belong to this queue.

## Sequence and counts

| Order | Subject | Civilization | Recordings |
|---|---|---|---:|
| 1 | Elite Jomsviking | Danes | 100 |
| 2 | Elite Hearth Troop | Saxons | 100 |
| 3 | Elite Jarl | Varangians | 110 |
| 4–7 | Elite Varangian Guard | Danes, Saxons, Varangians, Vikings | 400 |
| 8–11 | Heavy Mounted Crossbowman | Danes, Saxons, Varangians, Franks | 440 |
| | Total | 11 variants | **1,150** |

The unchanged 14 standard opponents are documented in
[NORSE_STANDARD_CAPTURE.md](NORSE_STANDARD_CAPTURE.md). They include eight melee
and six ranged units. Each applicable condition gets five separate game trials.
Mixed melee/ranged fights get both scaled Hussars and no buffer. Same-type fights
have one no-buffer set, since there is no different buffer condition to measure.
Guards are melee; Jarl and Mounted Crossbowmen are ranged.

Army counts use the approved weighted geometric policy: F=1, W=0.9, G=1.1,
full civilization discounts, one comparison population per physical unit,
27 cheaper units and no resource ceiling. The existing planner owns rounding.
Mixed buffered fights use 5–10 Spanish Hussars from the actual fielded ranged
army cost. Removing the buffer does not change either main army's count.
Saxon Guard costs are 52F+36G after the maximum 20% discount. Frank Mounted
Crossbowmen cost 40W+39G; the other three cost 40W+65G.

## Frozen inputs and safe resumption

Preparation: `apps/video/prepare_detailed_standard_capture.py`. It refuses to
overwrite an existing work directory. Do not rerun preparation to resume captures.
Plans validate installed-DAT costs against the current recording catalogs, freeze
the map and catalogs, and preflight all used scenario families/buffer orientations.
The no-buffer mixed matchup uses the no-P4 ranged-vs-ranged Golden derivative,
including its original diplomacy and patrols. Scenery preserves Golden gameplay
configuration, keeps the lane flat, adds no tree coordinates, and freezes animals.

Group work directories: `data/local/detailed-standard-norse`,
`data/local/detailed-standard-guards`, `data/local/detailed-standard-mounted`.
The combined queue is `data/local/detailed-standard-capture/queue.json` and points
to their eleven frozen campaigns in order. Every job ID begins `dstd_` and contains
subject, opponent index, buffer setting and iteration. The first actual trial is
the retained HP/count pilot, never a sixth recording.

Before starting, check process command lines and the queue lock; do not duplicate
workers. Set the editor's Load Scenario search to `Matchup Run`, then leave the
game to the recorder.

The main-menu scenario picker and the in-editor Load Scenario dialog have
separate search state. After reopening the game, set the filter inside the
editor's own Menu > Load Scenario dialog and return to the editor. Setting only
the main-menu picker can leave the staged scenario hidden from the recorder.

From the repository PowerShell:

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONPATH='apps/video;.'
& apps/video/.venv/Scripts/python.exe -u apps/video/run_knight_expansion.py --work data/local/detailed-standard-capture
```

Use `Start-Process -WindowStyle Hidden` with separate output/error logs for a
background launch. Existing workers enforce capture mutexes, initial HP/count
checks, elimination checks, source checksums and export checks, plus thermal and
local-disk safeguards. CPU temperature may be unavailable; never report a stale
reading as current. A parent `PAUSE` stops between units; the active campaign's
`PAUSE` stops at a battle boundary. Preserve completed trials when resuming.

## Completed-unit delivery and disk space

The finite copy worker watches only this queue. It copies a unit only after all
100/110 captures verify, with no pending exports. The next unit can record while
the completed one copies. It uses no recurring scheduled task.

```powershell
& apps/video/.venv/Scripts/python.exe -u apps/video/copy_norse_standard_to_share.py --queue data/local/detailed-standard-capture/queue.json --work data/local/detailed-standard-delivery --run-name Standard_Units_Detailed_Winter_5_Repeats --retire-untrimmed --follow
```

Destination:
`\\100.123.128.35\AoE2-Incoming\<unit_civ>\Standard_Units_Detailed_Winter_5_Repeats`.
Each clean MP4/frame pair includes `_with_hussars_r01` or `_no_buffer_r01` through
`r05`. `run.json` retains plans, clocks, recording metadata and trial conditions.
The metadata folder retains frozen catalogs, source map/derivatives, manifests,
cost/preflight evidence and this guide. Dragonstar can rebuild overlays and choose
representative trials without another game run.

Receipts: `data/local/detailed-standard-delivery/status.json`. New folders must be
owned by a durable receipt before use; conflicting existing contents are never
overwritten. File sizes and SHA-256 verify before publication. If the share fails,
the copy worker stops and all local clean sources remain.

The explicit `--retire-untrimmed` option removes only redundant local MOV files
after the entire unit's archive is complete. It verifies both local and remote
battle/frame pairs and local clock metadata first, checks the exact resolved MOV
path, and writes a per-file removal receipt. Local clean MP4s, frames and metadata
remain. No remote content is deleted. This follows
[RECORDING_RETENTION.md](RECORDING_RETENTION.md).

The initial forecast samples all 210 preceding standard recordings and reserves
50% size headroom. Keeping every untrimmed MOV would exceed local space; retaining
the clean sources plus one active unit fits. Capture stops below its 8 GiB local
reserve; copy stops below 4 GiB destination reserve. See
`data/local/detailed-standard-capture/storage-forecast.json` for measured inputs.

## Chinese Cavalier correction

The original detailed batch completed 1,150 trials. Its 80 Spanish Cavalier
trials all opened with 180 HP per opposing unit: Post-Imperial automatically
upgraded them to Paladins. Chinese fully upgraded Cavaliers open with 140 HP
and retain the Cavalier unit. Both cost 60 food + 75 gold, so original army
counts and buffers stay unchanged. Only these 80 trials require correction.

`prepare_detailed_cavalier_retakes.py` audited the original opening HP, bound
each existing archive index to its verified delivery checksum, and prepared
`data/local/detailed-standard-cavalier-retakes`. Preparation preserves the
original plans and asserts matching army counts, costs, buffers and scenery.
Do not prepare this work again or resume the completed original delivery worker.

Run the finite correction controller from the repository root:

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONPATH='apps/video;.'
apps/video/.venv/Scripts/python.exe -u apps/video/run_detailed_cavalier_retakes.py
```

Order: Jomsviking (5), Hearth Troop (5), Jarl (10), four Guard variants (20),
four Mounted Crossbow variants (40). Each unit's corrections are captured and
published before the next unit starts. Its first actual trial is retained as
the pilot; `pilot-opponent-expectations.json` requires Chinese and 140 opening
HP. Every replacement trial also passes the opening-HP check before delivery.

Replacement stays inside that unit's existing
`Standard_Units_Detailed_Winter_5_Repeats` folder. New named Chinese Cavalier
MP4/frame pairs are copied and SHA-256 verified first. The controller replaces
only the mapped rows in `run.json`, preserving other trials, and verifies its
published checksum. Only then does it remove the explicitly superseded Spanish
Cavalier pairs, checking each exact path, size and SHA-256 and recording removal
receipts. No unrelated archive files are deleted. Original local captures remain.

Correction status and receipts are in each campaign's
`replacement-status.json`; the previous and prepared indexes remain locally as
`previous-run.json` and `prepared-run.json`. The archive's `corrections` entry and
`metadata/cavalier-correction` retain provenance and reconstruction inputs. The
old delivery receipt is historical; the correction receipt binds the new index.
Changed destination indexes fail closed rather than overwriting another user's
changes. Resume this same controller after checking liveness and locks.

Earlier scenic-winter recordings are separate historical sets and are not
silently overwritten by these detailed-winter replacements.

# Nine-variant heavy cavalry capture

Approved after the Turkish camel baseline on 2026-09-20. Record only: preserve
clean gameplay, binary frames and reconstruction metadata; no simulation,
overlay rendering or publishing is authorized by this capture request.

Order: Spanish Paladin, Burgundian Paladin, Celt Paladin, Khmer Cavalier,
Berber Cavalier, Malay Cavalier, Wei Heavy Hei Guang, Wu Heavy Hei Guang,
Shu Heavy Hei Guang. Each faces the same frozen 74-opponent camel baseline list:
666 battles total. Steppe Lancers remain a separate future comparison.

Use `prepare_knight_expansion.py` once, then `run_knight_expansion.py` to start
or resume. Both run under `apps/video/.venv/Scripts/python.exe`, with
`PYTHONPATH=apps/video;.` and `PYTHONUTF8=1`. The game must already be in the
Scenario Editor. Follow the [operations guide](OPERATIONS_AND_RECOVERY.md).

Preparation checks the installed DAT hash, cost extraction hash, scenario IDs,
per-unit purchases, and every canonical plan. Costs are 60 food/75 gold for
Paladins and standard Cavaliers, 48/60 for Berbers, and 65/65 for Heavy Hei Guang.
The comparison discounts Berber food savings at half effectiveness and gold
savings in full, as specified by [the balance policy](BALANCE_POLICY.md).
Use a cap of 27, one comparison population per physical unit, and no resource cap.
Post-Imperial scenario settings supply each civilization's available upgrades;
missing upgrades must not be granted artificially. Existing Golden templates,
buffer rules, spectator civilization and battle framing remain unchanged.

The queue and frozen evidence live in `data/local/knight-expansion`. Each
variant's first Armenian Composite Bowman recording is an HP/count pilot.
The existing supervisor gates the remaining 73 captures on its verification,
checks thermal/disk state every 15 minutes and writes ten-match checkpoints.
Individual failures remain visible; a pilot or system/UI fault stops the queue.

`status.json` identifies the current variant; `<variant>/capture/status.json`
provides exact completed/failed counts. Per-variant logs and frozen plans remain
alongside it. A root `PAUSE` takes effect before the next variant. For a pause
after the current battle, also create `PAUSE` in the current variant directory
(or its `pilot-phase` directory during the pilot).

After each variant, the proven compact archiver copies and SHA-verifies each
verified battle MP4 and frames pair into `data/local/AoE2 Renders`, one folder
per variant. Its `run.json` preserves timing, identities, original recording
checksums, plans and outcomes. Only after verification does it remove redundant
source media, including the untrimmed MOV. Small source metadata remains.
This local staging destination can later be transferred to the external drive;
that drive was disconnected when this queue was prepared.

Use `materialize_compact_recording.py` to restore disposable overlay inputs.
Never rerun preparation, overwrite old comparison captures, or interpret an
archived source path's missing MOV as a failed battle. Resume filters verified
jobs from durable capture status before interacting with the game.

# Eight-civilization camel capture

## Turkish baseline extension (2026-09-20)

The original 591 captures are complete and preserved. A separate 74-match
Turkish Heavy Camel campaign uses the same frozen opponents and count policy,
with no additions to the opponent roster. Its work directory is
`data/local/camel-baseline`. Run `prepare_camel_baseline.py` once, then launch
`run_camel_comparison_capture.py --work data/local/camel-baseline`.
The first Composite Bowman capture gates the full campaign on verified counts
and 140 starting HP per camel. Catalog changes are additive; the original frozen
catalogs, plans and results remain intact. Use the baseline work directory when
resuming, not the original eight-civilization launcher.

`report_camel_baseline.py` writes `BASELINE_COMPARISON.md` and
`baseline-comparison.json` as new captures verify. For future video callouts:

- Turks loses, variant wins: highlight improvement over the baseline.
- Turks wins, variant loses: highlight worse performance than the baseline.
- Both win: ordinary win, no special advantage callout.
- Both lose: no outcome flip. HP can remain secondary context.
- Any draw: label separately, never silently convert it into a loss.
- Missing/unverified baseline: pending, never infer an outcome.

Retain per-match counts and winner HP with both source results. These are observed
outcome changes in individual battles, not statistical claims about win rates.
This phase records raw gameplay and frames only; no overlay render or upload.

The owner authorized raw game recordings and gRPC frames for Hindustanis,
Gurjaras, Berbers, Byzantines, Ethiopians, Saracens, Khitans and Malians.
Hindustanis use Imperial Camel Riders; the other seven use Heavy Camel Riders.
This phase does not render overlays, run the combat simulator, or publish videos.

The frozen manifest contains 591 battles: seven groups of 74 and 73 for
Hindustanis, omitting the identical Imperial Camel self-match. Opponents follow
the approved unique-unit roster in civilization/name order. All eight subjects
face each opponent before proceeding to the next opponent.

Use the current [balance policy](BALANCE_POLICY.md): geometric comparison cost,
one comparison population per physical unit, 27-unit cap, no resource ceiling.
Shared camel food discounts are half-effective and gold discounts fully effective.
The normal Golden scenarios retain their authored Hussar buffer for ranged/melee
matchups. Player 2 is the camel; spectator Player 1 uses Player 3's civilization.
Post-Imperial game technologies supply the combat bonuses without custom camel
stat triggers. Installed DAT and extraction hashes were checked before adding the
seven identities to the purchase/balance catalogs.

## Start or resume

Preparation is already complete. Do not regenerate catalogs while recording.
The game must be open in the Scenario Editor on the capture desktop.

```powershell
$env:PYTHONPATH='apps/video;.'
$env:PYTHONUTF8='1'
apps/video/.venv/Scripts/python.exe -u apps/video/run_camel_comparison_capture.py
```

The supervisor first records all eight subjects against Composite Bowmen. It
checks verified bundles, planned initial counts and observed opening HP against
the reference stats before resuming the full manifest. Verified pilots count
toward the full run and are not recorded twice. The standard capture supervisor
checks disk and thermal state and writes durable ten-match checkpoints. GPU
temperature is available; the existing CPU sensor remains unavailable/stale.

## Evidence and controls

- `data/local/camel-comparison/manifest.json`: frozen requests.
- `plans/`, `preflight.json`, `frozen-catalogs/`, `subject-stats.json`: plan audit.
- `supervisor.json`: pilot/full-capture/completion or error state.
- `pilot-phase/capture/status.json`: first eight captures.
- `pilot-validation.json`: observed opening HP/count checks.
- `capture/status.json`: combined full campaign progress after the pilot.
- `RESULTS.md`, `results.json`: eight-column results with winners, remaining HP
  and both unit counts, refreshed during the full capture pass.
- `worker-output.log`, `worker-error.log`: detached worker logs.
- `aoe2x/js_simulation/calibration/lab/runs/camel_<civ>_unique_*/live/run_001/`:
  raw media, `frames.bin`, clean `battle.mp4`, source scenario, checksums, and
  timing metadata. Retain these for future comparison layouts.

The new files stay on C: because D: has only about 5.6 GiB free. At launch C:
had about 285 GiB free. The first two complete bundles used about 206–224 MiB
each; long fights can require more. The supervisor stops at its local reserve.
Do not add this campaign to the older D:-archiving maintenance adapters.

### Saracen pilot correction

All eight pilots completed with verified recording bundles. The initial HP gate
stopped because the reference DB expected 175 HP for Saracens. The installed DAT
has Heavy Camel base HP 120, civilization tech 312 multiplying HP by 1.25, and
Bloodlines tech 435 adding 20 HP. Each of the 23 recorded Saracen camels reports
170 current and maximum HP at the first game frame: `120 * 1.25 + 20`.
The reference calculation instead corresponds to `(120 + 20) * 1.25`.
`capture-hp-expectations.json` records the correction and source frame hash;
`saracen-opening-entity-check.json` preserves the initial entity evidence.
The runner accepts this reviewed value only for the matching pilot evidence.
Original reference stats, raw footage, plans and unit counts are unchanged.

For a soft pause create `PAUSE` in the active work directory: `pilot-phase/`
during pilots or `camel-comparison/` during the full phase. Check actual worker
and active report before restarting. See [operations](OPERATIONS_AND_RECOVERY.md).

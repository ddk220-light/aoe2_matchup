# Inca Slinger standard-opponent extension

Authorized October 3, 2026. Finish the current Arena/Donut recording and verified
Dragonstar copies before starting these six sets, in this order:

1. Danish Elite Jomsviking.
2. Saxon Elite Hearth Troop.
3. Varangian Elite Jarl.
4. Varangian Elite Varangian Guard.
5. Viking Elite Varangian Guard.
6. Danish Heavy Mounted Crossbowman.

Each subject faces the fully upgraded Inca Slinger in five real Arena games.
For the four melee subjects, record another five on Donut only if the **Slinger**
loses at least three of the five Arena games. Count native game winners, not the
ranking draw threshold. Never test ranged/ranged on Donut, so Jarl and Mounted
Crossbowmen use Arena only. This is 30 new Arena recordings and zero to 20
conditional Donut recordings. All existing cells remain intact.

## Inputs and counts

The installed DAT checksum must agree with its extraction. The October 3 DAT
defines Slinger 185 as 50 food + 25 wood before discounts. Incas' maximum food
discount produces **35 food + 25 wood**, with weighted cost **57.5**. Audit this
and all six subjects against the installed cost effects before freezing plans.
Register the missing Inca Slinger balance identity before planning: installed
tech trees make Slinger 185 available to Incas and Mapuche, and its DAT population
is one. Add only this identity; preserve every existing price and catalog entry.

Use the current [balance policy](BALANCE_POLICY.md): food 1, wood 0.9, gold 1.1;
all actual discounts fully effective; one comparison population per physical
unit; 27 cheaper units and the geometric count for the expensive army; no
resource ceiling. No Hussars or other buffer units. Switching maps must retain
identical army counts.

Reuse the approved detailed-winter Arena and flat Winter Donut scenery from
[the Arena/Donut batch](ARENA_DONUT_CAPTURE.md). The original quiet AI discovers
Slingers correctly, but its 293-ms firing window is invalid for this unit.
New Slinger Donut captures require the animation-timing correction below;
preserve the old frozen templates and recordings.

On Arena, the subject is P2 and Slinger P3. On Donut, Slinger moves to P2 and the
melee subject P3. `subjectOwner` and `rangedOwner` record this distinction;
conditional selection uses Slinger losses, not subject losses.

## Finite handoff and resume

`apps/video/run_inca_slinger_after_arena_donut.py` waits for all preceding
captures, exports and copy receipts, then for both predecessor locks to release.
It prepares once with `prepare_inca_slinger_standard.py`, freezes all Arena and
candidate Donut plans, and starts the existing capture controller and copy
worker. The first Arena trial is the pilot and counts toward the five. Check
both armies' opening HP; normal scenario validation checks identities/counts.
The queue activates only necessary deferred Donut cells and reuses completed
Arena recordings on its second pass.

Use the video venv, `PYTHONUTF8=1` and `PYTHONPATH=apps/video;.`:

```text
apps/video/.venv/Scripts/python.exe -u apps/video/run_inca_slinger_after_arena_donut.py
```

Work and progress are under `data/local/inca-slinger-standard`, including
`handoff-status.json`, `queue.json`, `status.json`, campaign `capture/status.json`
and `delivery/status.json`. Resume existing work; do not reprepare or restart
verified games. Locks prevent duplicate controllers. Respect thermal pauses,
8-GiB local reserve and 4-GiB share reserve. This is a finite process, not a new
scheduled task. No overlays, simulator runs or uploads are launched.

## Delivery

Append to each subject's existing
`\\100.123.128.35\AoE2-Incoming\<subject>\Standard_Units_Detailed_Winter_5_Repeats`.
Keep named clean MP4s, matching frames and complete `run.json` reconstruction
metadata. Donut names end ` - Donut`. `_inca_slinger_metadata` carries the frozen
inputs, cost audit, counts, eligibility/decision and pilot records without
changing the previous `_arena_donut_metadata`.

Bind the completed previous index SHA-256 before copying. Verify each new file's
size and SHA-256 before extending that index. Refuse conflicts; preserve local
sources on any failure. This batch does not delete local or external media.
See [recording retention](RECORDING_RETENTION.md).

## Slinger firing correction (October 8, 2026)

The legacy extracted `attack_delay` divides DAT `frame_delay` by 60. That is
not an animation release time. For installed build 185872, Inca Slinger 185
uses attack graphic 7641, 30 frames, **0.056847997 seconds per frame**, and
releases on frame 14: **0.795871958 seconds**. The historical 233-ms estimate
(14/60) led to a 293-ms AI window. In recorded trial
`dcc6_elite_varangian_guard_varangians_imp_slinger_incas_r6`, Slingers repeatedly
switched to walking after about 676 ms, at animation frame 11, before release.

`apps/video/donut_ai_timing.py` reads the installed graphic timing and sets
Slinger's firing window to `ceil(releaseSeconds * 1000) + 60`: **856 ms** for
this build. Both volley-to-movement transitions also require that minimum
volley dwell. Other units' minimum dwell stays zero and their existing timing
remains unchanged. Do not infer that their legacy timing values are validated
by this Slinger correction.

Preserve the absolute jump targets in AI rules 0–77: add conditions/actions
inside existing rules, not new rules in the core. Apply type-specific timing
overrides **before** the `gWset=2` latch, or the override cannot execute.
`quiet_ai()` applies this correction when generating new templates. Previously
frozen templates are never edited in place.

The finite probe prepared by `prepare_slinger_timing_probe.py` lives in
`data/local/slinger-donut-timing`. It captures one additional trial of 27 red
Inca Slingers versus 19 blue Varangian Guards, using the same positions,
counts, scenery, upgrades and opponent AI as r06. Compare actual attack-frame
completion and damage in the recorded stream, rather than treating a changed
winner as proof that timing is fixed. Keep the original trials; do not launch
a blanket retake campaign from this probe.

Recorded validation: `slinger_timing_varangian_guard_donut_r7` had **zero**
premature walk interruptions (r06: **424**). It reached the release frame in
369 closed attack animations (r06: 26). Slingers won with 15 survivors and
423/945 HP (**44.76%**); in r06, Guards won with 93.68% HP. These are individual
recordings, not a statistical estimate. The timing decision rests on animation
completion; the outcome illustrates why the correction matters.

`apps/video/audit_slinger_release.py` reproduces the animation comparison from
two recording bundles. The compact receipt is
`data/local/slinger-donut-timing/timing-comparison.json`, also carried in the
probe's copied eligibility metadata. r07 is an additional corrected trial,
not an overwrite of r01–r06.

### Approved five-trial corrected sets

The user subsequently requested five corrected trials and checking whether
other subjects need them. Both **Varangian Guards (Varangians)** and **Hearth
Troops (Saxons)** beat Slingers in 5/5 Arena trials, so both qualify. Jomsvikings
caused 0/5 Slinger Arena losses and Viking Guards 2/5, below the selected 3/5
trigger. Jarl and Mounted Crossbowmen remain ranged/ranged Arena-only tests.

`prepare_slinger_donut_corrections.py` freezes **nine new recordings** under
`data/local/slinger-donut-corrections`: four Guards (r08–r11), reusing the
verified corrected Guard r07, followed by five Hearth Troops (r06–r10).
The already tested 856-ms AI, army counts, positions and scenery are reused.
Subject armies remain blue, Slingers red. No Arena games are repeated.

Resume with `run_knight_expansion.py --work data/local/slinger-donut-corrections`.
Copy with `copy_arena_donut_to_share.py --work data/local/slinger-donut-corrections
--follow`. Each set appends to its existing subject folder. Newly recorded
filenames include `Firing Timing Corrected`; the previously copied Guard r07
keeps its original filename. All have matching frame streams and reconstruction
metadata. The `_slinger_five_corrected_metadata` directory includes
`eligibility.json` with explicit `correctedTrialSets`: use those five job IDs
per matchup for analysis, replacing the listed `supersededForAnalysisJobIds`.
Historical recordings remain available and must not be mixed into the corrected
five-trial comparison.

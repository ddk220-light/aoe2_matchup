# Four-relic Elite Leitis corrections

The user explicitly confirmed the eight Elite Leitis corrections after the
Cavalier pass ended: four Paladin variants, then four Cavalier variants.
Keep the Champi comparison unchanged. The unrelated Bulgarian Cavalier versus
Flaming Camel missing-END failure remains outside this retake request.

## Confirmed defect and bounded correction

The original Frankish Paladin versus Elite Leitis recording contains 250
nonlethal P2 HP drops of exactly 18. Four-relic Elite Leitis should deal 22:
16 base attack, +2 available blacksmith attack, +4 relic attack; melee armor
does not reduce Leitis damage. Evidence and frame hash:
`data/local/leitis-four-relic-retakes/baseline-damage.json`.
The static unit database already includes the four relic bonuses, so its
displayed 22 did not prove the game was applying those bonuses.

Lithuanian **Paladin subjects already have their own verified +4 trigger**.
Preserve it when their Leitis opponents also get +4; never double the P2 bonus.
The eight retakes add only `scenario.opponentLithuanianRelics: 4`, represented
by a single enabled, non-looping attack-class-4 ADD-4 effect targeting P3 master
1236. All costs, counts, HP, formation, diplomacy, camera and Golden files stay
unchanged. Distinct job IDs and changed plan hashes prevent baseline reuse.

Preparation is complete:

- `data/local/paladin-leitis-four-relics`: four Paladin subjects.
- `data/local/cavalier-leitis-four-relics`: four Cavalier subjects.
- `data/local/leitis-four-relic-retakes/queue.json`: order, baseline IDs and validation.

Six targeted tests pass in `aoe2x/lab/tests/test_paladin_relics.py`, including both
owners at once, tampered quantities, invalid targets and plan-hash separation.
Every generated scenario passed the ordinary Golden validation too.

## Deferred execution

1. Let `data/local/cavalier-comparison` finish. Check its current worker identity,
   `capture/status.json`, per-pass status and logs. The pass ended at 295/296 and
   the user subsequently authorized these retakes. Require no active competing
   recorder before launching any correction. Respect user/thermal
   pauses and the current resource guard. Never start a competing game driver.
2. Run the first Paladin correction as a one-row pilot manifest, with reports
   under `paladin-leitis-four-relics/capture/pass-pilot`. Use the existing
   `python -m aoe2x.lab.recording_campaign PILOT.json --reports REPORT_DIR`.
3. Validate that pilot's `runDirectory` with:

   ```powershell
   apps/video/.venv/Scripts/python.exe apps/video/validate_leitis_relic_damage.py --run RUN_DIRECTORY --output data/local/leitis-four-relic-retakes/live-damage-validation.json
   ```

   Require at least ten nonlethal 22-HP drops and no incompatible damage. If it
   fails, investigate before accepting/continuing the retakes. The old recording
   is retained as the 18-HP control.
4. Resume the remaining Paladin jobs using
   `apps/video/run_champi_comparison_capture.py --work data/local/paladin-leitis-four-relics`.
   The runner discovers and reuses the verified `pass-pilot/status.json`.
5. After Paladins finish, use the same runner with
   `--work data/local/cavalier-leitis-four-relics`.
6. Archive after each correction campaign with
   `apps/video/archive_leitis_relic_retakes.py paladin` or `cavalier`.
   These use separate `D:/AoE2 Renders/{paladin,cavalier}-leitis-four-relics-CIV`
   directories, retaining MP4, frames, reconstruction metadata and checksums.
   Do not replace any baseline archive or Champi file.
7. Write a local before/after report for all eight: subject, unchanged counts,
   previous/new winner and surviving HP percentage, with links and frame hashes.
   Report completion and pause the follow-up monitor. No rendering or upload is
   required by this correction request.

These modifiers remain recording-only; the simulation planner rejects them
until a matching fixture implements the same conditions.

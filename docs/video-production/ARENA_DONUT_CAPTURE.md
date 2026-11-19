# Arena and Donut captures

Approved October 3, 2026. Arena is the ordinary detailed-winter Golden layout;
Donut is the approved flat winter layout with a central rock and quiet kiting AI.
**No buffer units in new recordings.** Historical with-Hussar footage is retained
as an earlier condition, never treated as a no-buffer baseline.

Counts remain unchanged: weighted per-physical-unit cost is food + 0.9 wood +
1.1 gold, with all actual civilization discounts fully applied. The cheaper unit
gets 27; the expensive unit gets `27 * sqrt(cheap / expensive)`, rounded to the
nearest integer, halves up, minimum one. There is no resource ceiling. Comparison
population is one per physical unit. See [balance policy](BALANCE_POLICY.md).

## Current finite batch

- Reuse 420 existing no-buffer Arena trials across six subjects: Danish
  Jomsviking, Saxon Hearth Troop, Varangian Jarl, Varangian and Viking Guards,
  and Danish Heavy Mounted Crossbowmen. Their indexes include Chinese Cavalier
  corrections. The other Guard/Mounted variants were removed by the user.
- Jomsviking, Hearth Troop and those two Guards: Donut versus Arbalester,
  Heavy Cavalry Archer and Elite Elephant Archer only when the ranged army lost
  at least three of the five Arena trials. `--trigger any-loss` is an alternative
  only if explicitly selected before freezing the queue. In-game winners, not
  the ranking's under-10%-HP draw convention, determine this capture decision.
- Jarl retains the explicitly requested Donut comparisons against every melee
  standard opponent, regardless of Arena outcome. Danish Mounted Crossbowmen
  use individual Arena loss checks: Donut only against melee opponents that
  beat them in at least three of five trials. Never ranged versus ranged.
- Add Chinese Halberdier (359, 35F + 25W) and Chinese Elite Fire Lancer
  (1903, 45W + 45G) on Arena against all six subjects. Both are melee; Fire
  Lancer's one-time projectile does not turn it into a ranged kiting unit.
  Jarl also faces both on Donut. Danish Mounted Crossbowmen first record their
  five Arena trials per opponent, then activate only necessary frozen Donut
  plans. Publication waits for this decision and all selected trials.
- Five separately recorded games per new condition: 195 new captures, plus
  zero, five or ten conditional Chinese-opponent Donut trials. The initial
  430-trial scope and unused plans are retained as history, not recaptured.
  No overlays, uploads or numerical simulator runs.

Prepare once with `apps/video/prepare_arena_donut_capture.py`. It reads the
current share indexes, audits installed DAT costs, freezes the approved Donut
template and catalogs, compares actual counts to reused Arena counts, and
validates generated scenarios. Its `eligibility.json` explains every decision.

Resume with the video venv Python and `PYTHONPATH=apps/video;.`:

```text
apps/video/run_knight_expansion.py --work data/local/arena-donut-standard
apps/video/copy_arena_donut_to_share.py --follow
```

The recorder's mutex prevents concurrent game workers. Existing thermal and
8-GiB local storage guards stop new battles at a safe boundary. The copy worker
requires 4 GiB free on the approved share. Resume pending jobs only; preserve
verified captures and frozen inputs. No scheduled monitor is created by this
workflow. A `PAUSE` file in the queue stops at a campaign boundary; the active
campaign's `PAUSE` stops at a battle boundary.

## Donut ownership and AI

October 8 exception: the user explicitly requested Saracen Arbalester kiting
Varangian Jarl on Donut. Only this pairing may use
`scenario.donutExperiment: arbalester_kites_jarl_v1`, with Arbalester P2 and
Jarl P3/subjectOwner 3. Both keep their actual ranged classifications and
unchanged geometric counts. Other ranged/ranged Donut tests remain rejected.
`apps/video/prepare_jarl_kiting_followup.py` prepares this single trial and one
Heavy Camel correction. Their separate frozen template adds a one-time P3
patrol at game second 1, selecting the entire P3 army by unit type, toward (11, 5).
`build_run` retargets that PATROL filter to the actual opponent. Fixed template
references are ineffective because army replacement allocates new references.
This addresses passive rear camels (two waited 25.52/30 seconds in r06); verify
actual movement from frames before accepting the correction. No scenery,
formations, stats or old recordings are changed. The two new pairs append to
the existing Jarl share folder; the correction uses r07 and Arbalester r01.

Donut always assigns P2 to the ranged army and P3 to the melee army. Therefore
a melee subject moves to P3; this is recorded as `subjectOwner` in each trial and
archive row. Do not infer the test subject from P2 when reporting results.
Army counts are unchanged by this orientation swap. The spectator camera,
player configuration and trigger structure are validated against the frozen
Donut template, separately from the canonical Arena Golden identity. In new
plans, **the subject is blue and the opponent is red**: set
`scenario.subjectOwner` to the same 2 or 3 as the trial's `subjectOwner`.
The planner derives `colorPolicy: subject_blue_opponent_red_v1` and zero-based
scenario `playerColors` (blue 0, red 1), including them in the plan hash.
Generation receives `subject_owner` and sets only the two fighting colors.
The validator permits exactly those planned colors while preserving all other
player configuration, AI, camera, formation and trigger checks. Its
`playerRuntimeConfigurationMatchesGolden` flag is false if colors changed;
`playerRuntimeConfigurationMatchesPlan` and `playerColorsMatchPlan` must be true.

This fixes future generation; it does not rewrite the Golden or reviewed Donut
template, existing plans, recordings, or share indexes. Historical requests with
no `scenario.subjectOwner` retain their original hashes and template colors for
resume/reuse. Do not regenerate them merely to apply this policy. The October 3
audit of the 205 Arena/Donut extension trials and 40 Slinger trials found all 90
Arena trials blue/red and 155 Donut trials with inherited red/cyan colors.
The audit is `data/local/player-color-audit/audit.json`. The user approved the
code fix but explicitly withheld recording until further instructions.

The quiet production AI preserves its absolute core rule numbers. Its discovery
searches explicitly include Elite Jarl 2709, whose DAT class is Cavalry rather
than Cavalry Archer. New Jarl/Mounted Crossbow release-time entries use installed
DAT attack delays + 60 ms, matching the existing table's release margin. No chat
or taunts are added. The full AI and template hashes travel with the archive.

## Delivery and reconstruction

Each completed subject's new trials append to its **existing** folder:
`\\100.123.128.35\AoE2-Incoming\<subject>\Standard_Units_Detailed_Winter_5_Repeats`.
Donut video and frame stems end in ` - Donut`. New Arena opponents use the
existing `_no_buffer_r01` naming convention. Each clean MP4 has matching frames;
`run.json` carries the plan, outcome, video/frame alignment, owner mapping and
checksums. `_arena_donut_metadata` carries the frozen template, AI, catalogs,
selection, conditional decisions and preparation metadata. See
[retention](RECORDING_RETENTION.md).

The copy worker binds and backs up the previous index before writing, refuses
conflicting media, checks SHA-256 on source and destination, and extends only
the authorized index after every new pair verifies. Partial publication has a
durable pending checksum. All original rows and all local base recordings stay
intact. A disconnected share preserves local sources; never format disks or
delete unrelated destination content.

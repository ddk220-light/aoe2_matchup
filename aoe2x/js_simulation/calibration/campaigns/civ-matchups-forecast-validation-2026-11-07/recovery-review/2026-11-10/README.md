# Review of the 36 unfinished forecast contexts

Reviewed November 10, 2026, at 5:28 a.m. PST (America/Los_Angeles), from research checkpoint `7d53deb5df104989a9b2856f43832a492c09d44a`.

All 36 contexts have been reviewed. **None is promoted to a completed frozen-engine result.** They affect 220 displayed cells. This review adds no simulation, replay, winner, draw, correction, or website change. The completed total remains 39,112 of 39,148; recurring tasks and workers remain stopped.

## What is blocking them

| Observed problem | Contexts | Displayed cells | Meaning |
| --- | ---: | ---: | --- |
| Different-engine results | 19 | 194 | Three saved seeds agree, but belong to another physics version. |
| Fixed-position pursuit stalls | 8 | 13 | Units retain HP and positions while pursuit/reservation retries continue. |
| Movement without combat | 6 | 10 | Units move or retarget for long periods without further damage. |
| Idle at patrol endpoints | 2 | 2 | All movement, combat and target state stops while ticks advance. |
| Collision exception | 1 | 1 | The movement solver rejects an invalid ranged-crowd reservation geometry. |
| **Total** | **36** | **220** | **17 native failure cases plus 19 cross-engine projections.** |

These are observed failure families, not proof that every member has the same root cause. The snapshots omit some instantaneous order, reservation and collision state. Survivor advantage does not establish a native winner or a legitimate draw.

## Findings that affect recovery decisions

1. **The saved evidence is intact.** Verified 67 closed attempt timelines, one additional unclosed diagnostic timeline, 13 completed native seed records in their original separate ledgers, and all 57 referenced alternate-engine seed records. All alternate records match their saved hashes, owner-oriented profile order, counts, scenario, event hash and final-state hash. The 62 runtime files and 81 input files match the base manifest with the approved v3 source overrides. No completed seed needs a repeatability rerun.
2. **One old stall is quarantined, not fully exhausted in the journal.** Armenian Champion / Tupi Slinger has three closed watchdog attempts (180/600/1800 seconds). Its fourth archived diagnostic timeline contains 26 snapshots, 24 with fixed core state, but no corresponding closed attempt entry. Preserve it as unfinished; do not invent a fourth timeout or resume the old campaign automatically. The other 16 native failure contexts each have four closed normal attempts; the collision exception failed early rather than timing out.
3. **Four seed-0 records pass today's numeric single-seed screen in isolation.** Armenian Champion / Tupi Slinger, Aztec Elite Skirmisher / Hun Elite Tarkan, Lithuanian Elite Skirmisher / Gurjara Heavy Camel Rider, and Muisca Elite Guecha Warrior / Viking Champion agree with the original forecast and retain at least 25% of the winner's starting HP. However, their recorded multi-seed work already includes later failures. Retroactively discarding those failures would conceal known evidence. Keep the recorded protocol and held status; this review does not apply a new stopping rule after seeing the outcomes.
4. **The Chu Ko Nu / Mounted Trebuchet case really needs its mixed-result treatment.** Native seeds 0–6 are saved; the initial winners vary, and seeds 7–9 remain missing. A majority among the seven completed seeds cannot finish the required ten-seed set. The other saved native seeds also remain protected in their original ledgers. Older diagnosis text asking for an independent replay is historical; the current no-replay instruction supersedes it.
5. **The largest coverage opportunity is concentrated.** Three Scorpion-versus-Heavy-Scorpion mechanics contexts account for 161 of the 220 affected cells (73.2%). One context alone accounts for 147 cells across 7 × 21 civilization variants. Their alternate-engine evidence is useful for investigating recovery, but is not an automatic frozen-engine correction. Table names below use actual frozen mechanics upgrades; a role key containing `heavy_scorpion`, `champion`, or `paladin` does not guarantee that civilization actually fields that upgrade.

## Recommended recovery work, before any new simulation

- **Trace the concrete collision failure first.** Chinese Heavy Scorpion / Polish Heavy Mounted Crossbowman repeatedly throws the same error: references 9000/9011 have separation 0.02350274216190229 against reservation extent 0.025. The stack reaches `validateStartingGeometry` from `resolveMovementProposals` during combat. “Starting overlap” means the start of that movement solve, not necessarily the initial spawn. Inspect how ranged-crowd reservation extents change across movement steps; do not remove the assertion or loosen geometry to force a result.
- **Investigate the 14 pursuit cases as two related families.** Eight become stationary; six keep moving. Start with attack-range/contact-surface agreement and terminal route reachability near forest boundaries, then examine reservation and target-selection cycles. Three Elite Skirmisher / Mapuche Elite Kona cases independently show one skirmisher versus 18 Kona, unchanged HP and continuing movement. That repeated pattern makes them useful comparative diagnostics, without proving one shared defect. Minimum-range behavior also deserves separate attention for Mounted Trebuchets.
- **Investigate patrol continuation separately.** Danish Elite Jomsviking / Muisca Elite Guecha Warrior and Muisca Elite Guecha Warrior / Viking Champion end at (2,13) and (13,2), with no targets or changing event counters. The frozen code preserves scenario patrol orders during combat, but these snapshots do not expose enough order state to prove the reacquisition failure. Compare endpoint/reacquisition behavior to an actual game capture before changing it.
- **Audit the existing candidate changes for the 19 projected contexts.** Nine use `collision-repair-v2`; seven use its static-memo/event-stream candidate; two use a patrol candidate; one uses a terminal-goal candidate explicitly marked as lacking independent forest-pocket game-fidelity validation. Prioritize the three Scorpion contexts for coverage benefit. Verify reusable mechanics and game fidelity before selecting a recovery engine; do not copy results into the frozen ledger or reverse owner orientation.

Any physics repair would need a separately versioned research dataset and explicit recovery scope. Any future execution plan must identify only missing eligible seeds, preserve all completed seeds and failures, keep the 1/3/10 distinct-seed rule, and exclude new same-seed replay. This review does not authorize a retry, engine change, recurring task, build or deployment. Longer watchdogs alone are not justified by the repeated no-combat suffixes.

## Every native failure case

Counts preserve owner order. `Saved` lists completed native seeds in the original ledger. For a case without seed 0, only seed 0 is presently known to be required; escalation to three or ten seeds depends on actual results.

| Matchup (owner 2 / owner 3) | Counts | Cells | Finding | Saved | Known missing | Source |
| --- | --- | ---: | --- | --- | --- | --- |
| Armenians Champion / Tupi Slinger | 27 / 27 | 1 | Fixed-position pursuit stall | 0 | 1, 2 | [Diagnosis](../../../civ-matchups-mismatch-validation-2026-11-05/diagnostics/mv_5e1e0d268234acff1d6e9008/REVIEW.json) |
| Aztecs Elite Skirmisher / Huns Elite Tarkan | 27 / 18 | 1 | Moving without combat | 0 | 1, 2 | [Diagnosis](../../../civ-matchups-mismatch-validation-2026-11-05/diagnostics/mv_306dd795e5f68374d24e2a99/REVIEW.json) |
| Bohemians Elite Hussite Wagon / Khitans Mounted Trebuchet | 27 / 19 | 1 | Fixed-position pursuit stall | 0 | 1, 2 | [Diagnosis](../../diagnostics/fv_c553e033f98149a99dc0ffcf/REVIEW.json) |
| Burgundians Elite Skirmisher / Mapuche Elite Kona | 27 / 19 | 3 | Moving without combat | None | 0 | [Diagnosis](../../diagnostics/fv_02521b013b039fe6f65c73ca/REVIEW.json) |
| Burmese Elite Skirmisher / Mapuche Elite Kona | 27 / 19 | 1 | Moving without combat | None | 0 | [Diagnosis](../../diagnostics/fv_687be822b7c8f4102aabb93f/REVIEW.json) |
| Italians Elite Skirmisher / Byzantines Hussar | 27 / 23 | 1 | Fixed-position pursuit stall | None | 0 | [Diagnosis](../../diagnostics/fv_5bc5ce13eed6d3668dda1e1c/REVIEW.json) |
| Chinese Elite Chu Ko Nu / Khitans Mounted Trebuchet | 27 / 12 | 1 | Moving without combat | 0, 1, 2, 3, 4, 5, 6 | 7, 8, 9 | [Diagnosis](../../../civ-matchups-mismatch-validation-2026-11-05/diagnostics/mv_9bc2d959cf36c2b00f7ffa75/REVIEW.json) |
| Chinese Heavy Scorpion / Poles Heavy Mounted Crossbowman | 23 / 27 | 1 | Collision exception | None | 0 | [Diagnosis](../../diagnostics/fv_d94fee4147c5053486b13687/REVIEW.json) |
| Muisca Elite Guecha Warrior / Turks Cavalier | 27 / 24 | 6 | Fixed-position pursuit stall | None | 0 | [Diagnosis](../../diagnostics/fv_91e08f7a4d9e62083a18bf56/REVIEW.json) |
| Cumans Elite Skirmisher / Malay Light Cavalry | 27 / 23 | 3 | Moving without combat | None | 0 | [Diagnosis](../../diagnostics/fv_0466e97c7d116241411573cc/REVIEW.json) |
| Danes Elite Jomsviking / Muisca Elite Guecha Warrior | 27 / 23 | 1 | Idle at patrol endpoints | None | 0 | [Diagnosis](../../diagnostics/fv_9c07f592c61760a424b461f4/REVIEW.json) |
| Lithuanians Elite Skirmisher / Gurjaras Heavy Camel Rider | 27 / 20 | 1 | Fixed-position pursuit stall | 0 | 1, 2 | [Diagnosis](../../../civ-matchups-mismatch-validation-2026-11-05/diagnostics/mv_e50435eb3040ac8928d195ee/REVIEW.json) |
| Incas Elite Skirmisher / Poles Cavalier | 27 / 19 | 1 | Fixed-position pursuit stall | None | 0 | [Diagnosis](../../diagnostics/fv_5c08b7d3266df27dbb057abc/REVIEW.json) |
| Malay Light Cavalry / Khitans Elite Skirmisher | 23 / 27 | 1 | Fixed-position pursuit stall | None | 0 | [Diagnosis](../../diagnostics/fv_e0d18588ecc82161d1d74801/REVIEW.json) |
| Sicilians Elite Skirmisher / Mapuche Elite Kona | 27 / 19 | 1 | Moving without combat | None | 0 | [Diagnosis](../../diagnostics/fv_5184d46798ee328659752ef9/REVIEW.json) |
| Muisca Elite Guecha Warrior / Vikings Champion | 22 / 27 | 1 | Idle at patrol endpoints | 0, 1 | 2 | [Diagnosis](../../../civ-matchups-mismatch-validation-2026-11-05/diagnostics/mv_c72552550f46f7a6f193d254/REVIEW.json) |
| Vikings Light Cavalry / Sicilians Elite Skirmisher | 23 / 27 | 1 | Fixed-position pursuit stall | None | 0 | [Diagnosis](../../diagnostics/fv_c250a7a42ac0230166abf1ef/REVIEW.json) |

## Every cross-engine projection

All 19 have matching source records for seeds 0, 1 and 2, with the same winner across those three source-engine seeds. This is evidence under the named alternate engine only. Representative civilization names below stand for all equivalent variants retained in `review.json`; displayed-cell counts are not additional independent simulations.

| Representative matchup (owner 2 / owner 3) | Counts | Cells | Source engine | Context ID |
| --- | --- | ---: | --- | --- |
| Armenians Elite Skirmisher / Mapuche Elite Kona | 27 / 19 | 9 | Terminal-goal candidate | `fv_04a3f08c5a3fa3034378a198` |
| Armenians Elite Skirmisher / Romans Legionary | 27 / 24 | 9 | Collision repair v2 | `fv_71d0522368d57b17cda930b0` |
| Aztecs Scorpion / Bengalis Heavy Scorpion | 27 / 27 | 147 | Collision repair v2 | `fv_37b43676bb78ced1fe641bc3` |
| Aztecs Scorpion / Sicilians Heavy Scorpion | 27 / 27 | 7 | Collision repair v2 | `fv_619a0158d08d5a52d810f89b` |
| Aztecs Scorpion / Teutons Heavy Scorpion | 27 / 27 | 7 | Collision repair v2 | `fv_e36a7533a2a0741ec941016e` |
| Gurjaras Hussar / Aztecs Elite Skirmisher | 26 / 27 | 1 | Static-memo/event-stream candidate | `fv_f0e4d7e8b033beefa6874f36` |
| Aztecs Elite Skirmisher / Lithuanians Winged Hussar | 27 / 23 | 1 | Static-memo/event-stream candidate | `fv_3d49be4da9ee956cb3e6056d` |
| Mapuche Elite Skirmisher / Bengalis Elite Battle Elephant | 27 / 15 | 1 | Static-memo/event-stream candidate | `fv_f5850787e7ae715b63a708a1` |
| Byzantines Paladin / Berbers Elite Genitour | 19 / 27 | 1 | Collision repair v2 | `fv_21eb354e22caaa7f2a074bf4` |
| Byzantines Elite Skirmisher / Muisca Elite Champi Warrior | 27 / 20 | 1 | Collision repair v2 | `fv_3e1220e3db7412a4b8634b61` |
| Tatars Hussar / Byzantines Elite Skirmisher | 20 / 27 | 1 | Static-memo/event-stream candidate | `fv_007891ccda2fa93dc61b788f` |
| Varangians Hussar / Byzantines Elite Skirmisher | 20 / 27 | 1 | Static-memo/event-stream candidate | `fv_b30b96ecb6c90027fd60113c` |
| Mapuche Elite Skirmisher / Byzantines Paladin | 27 / 17 | 1 | Collision repair v2 | `fv_bf684744ac30842aeffe756a` |
| Mapuche Elite Skirmisher / Celts Paladin | 27 / 17 | 1 | Collision repair v2 | `fv_d53cd4049fe33c499b053ce6` |
| Ethiopians Two-Handed Swordsman / Muisca Elite Guecha Warrior | 27 / 22 | 2 | Patrol candidate | `fv_b2b173f00d003f46c6598750` |
| Mapuche Elite Skirmisher / Franks Paladin | 27 / 17 | 1 | Collision repair v2 | `fv_d97574f407d4ec3a45421837` |
| Muisca Elite Guecha Warrior / Khitans Champion | 22 / 27 | 1 | Patrol candidate | `fv_90220f5280e3489aa2b36516` |
| Tatars Hussar / Saxons Elite Skirmisher | 20 / 27 | 1 | Static-memo/event-stream candidate | `fv_80a16d8f1e9a54a526a13d1f` |
| Varangians Hussar / Saxons Elite Skirmisher | 20 / 27 | 1 | Static-memo/event-stream candidate | `fv_c0d48f6e0c08f7d9f31102d1` |

## Sources and reproduction

- [Machine-readable full review](review.json): every physical context, original forecast evidence, aliases, source hashes, original native seed references, alternate-engine seed records, and recomputed saved-timeline statistics.
- [All 36 cases as CSV](cases.csv): matchups, counts, category, completed/missing seed status, finding and next action.
- [Read-only review script](review.py): reads saved files only; never imports the simulation engine or launches a worker. Run with `--output <new-directory>` to avoid overwriting a review.
- [Original unfinished-context inventory](../../closeout/2026-11-10/remaining-contexts.jsonl.gz).
- [Completed coverage analysis](../../closeout/2026-11-10/README.md) and [immutable reviewed snapshot 070](../../correction-snapshots/070/summary.json).

Code inspection references: `src/combat/collision.js:175–196, 663–685` (movement-step geometry validation), `src/combat/pair-interactions.js:170–190` (ranged-crowd reservation priority), and `src/combat/world.js:2228–2238` (scenario patrol preservation), under `aoe2x/js_simulation/`. These establish the code paths to investigate, not a proven root cause from incomplete snapshots.

Historical ledgers, projections, forecasts, pair reviews, source hashes, physics and milestone cursor are unchanged. Review artifacts are committed locally; the previous owner's one-time publication of checkpoint `7d53deb5d` remains separate. The general pre-push guard stays installed.

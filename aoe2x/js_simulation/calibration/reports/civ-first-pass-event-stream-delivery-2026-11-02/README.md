# First-pass delivery: event-memory recovery and phase036 audit

The frozen prediction-first-pass-v2 model, original physical contexts and all historical simulation manifests/journals remain unchanged. This update addresses two failed recovery seeds; it does not expand forecasts or start a second validation pass.

## Recovery diagnosis and implementation

The static-memo Kona attempt failed from a3-GiB heap limit at tick196284 after6,971.6wall seconds. It streamed its final hash but still retained every event object. Two other static-memo seeds completed; that partial set cannot support a table projection. Do not restart it blindly.

The Mapuche Skirmisher/Bengali Elephant seed1 exhausted7200wall seconds at3,887game seconds. A bounded150-game-second diagnostic shows a lone16HP skirmisher firing from a forest pocket while elephant HP decreases slowly. It is an ongoing fight, not a proved stalemate or a draw. These diagnostic artifacts are pushed on the parallel branch at39389d32.

The separate worktree `/workspace/aoe2_civ_event_stream`, branch `simulations/civ-matchups-event-stream-2026-11-02`, hashes each tick's events immediately and retains no historical event objects. It preserves the exact canonical byte sequence and keeps full combat calculations unchanged. The existing static collision memoization remains. Six focused tests, a million-event32-MiB heap stress, five saved-output parity probes and a separate progress-worker control passed. Nine existing world-tick failures match the frozen baseline exactly; the full suite is not represented as passing. Source and detailed reports were published at8a99ac7c.

The two-worker runner is `aoe2x/js_simulation/node/civ-matchups/recover-event-stream-first-pass.mjs`; campaign `calibration/campaigns/civ-matchups-event-stream-first-pass-2026-11-02`; manifest hash `4a5d7e75aa1592b954486f34b34be4f15c3b11e9cff17153ec5622f51ec613d6`; log `/workspace/aoe2_civ_event_stream_recovery.log`. Check state, journals, lock and PID before resuming. It recomputes all required seeds for the two failed pairs, writes diagnostic HP/position/event-count/memory progress every30wall seconds, and performs an exact replay review per complete pair. It imports no old outcomes. Observed initial worker heaps were approximately70MiB. Diagnose failures before retries.

## First-pass export

`build_civ_first_pass_delivery.py` now defaults `--event-stream-recovery` to that campaign. Native observations stay in `event-stream-candidate-evidence-ledger.jsonl.gz`, separate from V2, patrol and static-memo evidence. Only a complete reviewed seed set can contribute a `predicted_unvalidated` projection into the frozen V3 table. Source/target physics, hashes, original context, exact replay references and fidelity limitations remain explicit. Partial static-memo and event-stream results contribute nothing. Seven delivery tests pass; the completed patrol loader still validates its two reviews.

## Phase036 coverage

The full-grid preview reconciles555 variants,1540 civilization pairs,151223 cells and68916 profile pairs, including unresolved rows. It contains9281 observed,9585 inferred,45 equivalent,47596 flagged predictions (including two completed patrol projections), and2409 gaps. This is not completion.

`phase036-classification-transitions.json` explains why the gap count grew: the normal evidence rebuild returned1672 previously inferred rows to unresolved;473 other formerly inferred rows are now flagged predictions under the existing frozen policy. New measurements covered224 previous gaps and32 existing predictions. No rules were retrained or expanded to reverse these changes. Previously unsupported conclusions are not promoted merely to reduce the queue.

Only the preview summary and file hashes are published; full preview tables remain disposable local outputs reproducible from immutable phase036 sources. The final complete bundle must be published after zero gaps and all required reviews, without starting exhaustive forecast validation or modifying the web app.

## Phase037 reviewed checkpoint

Phase 037 passed all 256 pairs and 796 valid seeds, with zero missing seeds and an exact replay. The read-only `phase037-check.json` verifies all 62 frozen runtime files, inventory hashes and 31,353 unique valid pilot/adaptive journal records at its snapshot. Phase 038 continues through the existing supervisor.

The original parallel recovery has now stopped safely as blocked after its final 7,200-wall-second patrol timeout. Its nine complete repaired-V2 pairs passed exact replay review; the other four missing seeds are not measurements. The separate completed patrol candidate covers two of those pairs only as provisional projections. The event-memory campaign is still recomputing the remaining Kona/Elephant pairs and contributes nothing until each complete seed set passes review.

`preview-phase037/summary.json` reconciles 555 variants, 1,540 civilization pairs, 151,223 displayed cells and 68,916 profile pairs: 9,537 observed, 10,173 inferred, 45 equivalent, 47,203 flagged predictions and 1,958 unresolved gaps. The predictions include nine repaired-V2 and two patrol-candidate projections. All measurements stay in their own physics ledgers. This is a progress preview, not a completed or fully validated dataset. Its summary and file hashes are published; full disposable preview tables remain local until the final complete bundle is built.

## Phase 038 and newly reviewed recovery

Phase 038 completed 256 planned pairs with 808 valid seeds, one blocked pair and two explicitly missing V3 seeds. Its exact replay passed. The new blocked pair is Gurjara Hussar versus Aztec Imperial Elite Skirmisher, `cm_8b6d8cf86a0ecd56ddc35bc2`: seeds 0 and 2 completed combat but failed final event hashing with `RangeError: Invalid string length`. Its separately frozen recovery uses the already-tested byte-identical event-memory runtime; no physics change was needed. Worktree `/workspace/aoe2_civ_phase038_stream`, branch `simulations/civ-matchups-phase038-stream-2026-11-02`, script `node/civ-matchups/recover-phase038-stream-first-pass.mjs`, campaign `civ-matchups-phase038-stream-first-pass-2026-11-02`, hash `cfd424a435a2fadbb7b0b09feb1c28e09b9989f50a0139b58c75e0128e6ff7b9`. It recomputes the full pair; no V3 outcomes are copied.

The original event-memory campaign finished all three Elephant seeds and its exact review. Seed 1 completed after 5,137 wall seconds / 5,255.53 game seconds, with nine elephants surviving; the earlier watchdog was not a result. Kona seed 0 still timed out after 7,200 wall seconds, with one 23-HP skirmisher and 18 Kona. It remains missing. That frozen campaign is now blocked with five saved seeds and one reviewed pair; do not restart it blindly.

The phase-038 full-grid preview adds only the completed Elephant projection. It reconciles 555 variants, 1,540 civilization pairs, 151,223 cells and 68,916 profiles: 9,792 observed, 10,535 inferred, 45 equivalent, 46,908 flagged predictions and 1,636 unresolved gaps. Its 12 repaired projections consist of nine V2, two patrol-candidate and one event-memory result, all linked to separate physics ledgers. The main campaign is still running; no completion is claimed.

## Minimal terminal-goal candidate

Read `civ-subcell-route-2026-11-02/REVIEW.md` on branch `simulations/civ-matchups-subcell-route-2026-11-02`, source commit `e379ad20`. Terminal waypoint smoothing could clear a pursuit route up to 0.1875 tiles before its final physical attack-stop goal. The minimal candidate retains that goal until reached. Only `chase-path.js` changes relative to the event-memory candidate; collision checks, stop/attack extents, damage, raster resolution and termination remain unchanged. Two broader prototypes were tested, archived and not adopted. No no-route cache or BFS experiment was adopted.

The candidate passes 25 routing tests; its nine world-tick failures match the baseline exactly, with no new failures. Bounded controls preserve winners but can change ticks/hashes. Independent game-fidelity validation stays open. The source commit and diagnostics are not campaign measurements.

Fresh Kona seeds run in `/workspace/aoe2_civ_subcell_route`, script `node/civ-matchups/recover-terminal-goal-first-pass.mjs`, campaign `civ-matchups-terminal-goal-first-pass-2026-11-02`, hash `ad724f10cc4d74e11d53e43ebd4e6860a29c247fa6c4b21161f080afff63c2aa`; log `/workspace/aoe2_civ_terminal_goal_recovery.log`. The campaign owns all native seeds and exactly replays seed 0. Only a complete reviewed set can contribute an unvalidated cross-engine projection.

Builder v6 accepts additional separately frozen campaigns with the identical event-memory runtime via `--extra-event-stream-recovery`, and the terminal candidate via `--terminal-goal-recovery`. It keeps each source campaign hash and rejects duplicate provenance or conflicting complete candidate contexts/outcomes. Terminal observations have their own `terminal-goal-candidate-evidence-ledger.jsonl.gz`. Nine delivery tests pass, including missing-seed, wrong-physics, reversed-context and cross-campaign conflict checks. Existing forecasts and physics journals stay unchanged.

## Kona terminal-goal review completed

The targeted terminal-goal campaign completed all three fresh seeds at ticks 1785, 2159 and 1742, with Mapuche winning each. Its independent exact replay of seed 0 passed, including final-state/event-log parity with the diagnostic v3 control. Final review documentation is pushed at `4bfe02ed`. The completed runner must not be restarted.

The refreshed builder-v6 phase-038 preview contains 9,792 observed, 10,535 inferred, 45 equivalent, 46,909 flagged predictions and 1,635 unresolved gaps. The 13 repaired projections include the one completed terminal-goal pair, whose three native records stay in their own ledger. Phase-038 stream recovery is still running and contributes nothing until its own complete review. No first-pass completion is claimed.

## All targeted inventories through phase 038 accounted for

The phase-038 hashing recovery also completed: three Hussar wins and its independent exact replay passed. Final review documentation is pushed at `6109d06a`. No recovery runner remains active, and all completed inventories must stay stopped. The main phase-039 runner is still live.

The refreshed phase-038 preview now has 46,910 flagged predictions and 1,634 unresolved gaps, with the observed/inferred/equivalent counts unchanged. All 14 previously blocked profile pairs have explicit projections linked to completed reviewed inventories, including two separate event-memory inventories sharing an identical runtime. This does not complete ordinary remaining simulation gaps or validate the forecasts. Full tables remain disposable previews until the final zero-gap bundle is published.

## Phase 039 reviewed checkpoint and new hashing inventory

Phase 039 completed 256 planned pairs with 829 valid V3 seeds, two blocked pairs and two explicitly missing seeds. Its exact replay passed. The final attempts for Tatar Hussar versus Byzantine and Saxon Imperial Elite Skirmishers both completed combat but failed canonical event hashing with `RangeError: Invalid string length`. These failures remain recorded as failures. The main runner has moved on to phase 040.

The new `/workspace/aoe2_civ_phase039_stream` worktree, branch `simulations/civ-matchups-phase039-stream-2026-11-02`, freezes only those two pairs in `civ-matchups-phase039-stream-first-pass-2026-11-02`, hash `d83d5a04d09eed2222a3c1905734711570d0ef82cd29642472429ed239b8a27e`. Source commit `952f8596`; script `node/civ-matchups/recover-phase039-stream-first-pass.mjs`; log `/workspace/aoe2_civ_phase039_stream.log`. All 62 runtime hashes exactly match the already-completed phase-038 recovery. Two workers recompute full native seed sets in parallel and independently replay each complete pair. The new source is already pushed; no prior runner was restarted or V3 result copied.

The builder-v6 default now includes this additional event-memory inventory. Nine delivery tests pass. Its partial or unreviewed records contribute nothing. The phase-039 full-grid preview reconciles 555 variants, 1,540 civilization pairs, 151,223 cells and 68,916 profiles: 10,046 observed, 10,624 inferred, 45 equivalent, 46,770 flagged predictions and 1,431 unresolved gaps. It still includes only the 14 previously completed repaired projections. Neither the new recovery nor the main first pass is declared complete.

## Phase-039 recovery completed; exhausted phase-040 seed recovered separately

Both phase-039 hashing inventories completed all six fresh seeds and passed their independent exact replay reviews. Native seed ticks were 2052, 126234 and 1988 for both pairs; all were Tatar Hussar wins. Final native checkpoint `be86df35` and review documentation `662ce5b1` are pushed on the phase-039 stream branch. That runner is stopped and must not be restarted.

The phase-039 preview now has 46,772 flagged predictions, 1,429 unresolved gaps and 16 reviewed repaired projections. Observed, inferred and equivalent counts remain 10,046, 10,624 and 45. All previously reviewed blockers are accounted for without promoting old V3 errors into measurements.

While phase 040 continues, Aztec Imperial Elite Skirmisher versus Lithuanian Hussar `cm_313d7b3bb1a75fbc0a90e70f` seed 0 exhausted all four V3 retries at the same final event-hash error. It is an ordinary hard gap, not a prediction-validation sample. The separately frozen `civ-matchups-phase040-early-stream-first-pass-2026-11-02` inventory binds the exact exhausted failure line/hash and phase-040 plan before recomputing the complete native seed set. This does not wait for unrelated phase-040 work or alter its journals. An initial watchdog cannot authorize this inventory.

Worktree `/workspace/aoe2_civ_phase040_early_stream`, branch `simulations/civ-matchups-phase040-early-stream-2026-11-02`, script `node/civ-matchups/recover-phase040-early-stream-first-pass.mjs`, hash `29ac37c8445fe6972199a79c641cadfc2e260665b5c8ef01cfe5600de5fc5921`, source `c9dc0b57`, log `/workspace/aoe2_civ_phase040_early_stream.log`. All runtime files are byte-identical to the completed event-memory campaigns; no physics, forecast or scoring change is introduced. This inventory contributes no table projection until its full seed set and exact replay pass.

Builder v6 now checks early-inventory source plans, original campaign/inventory hashes, exact job contexts and the specific exhausted hashing-error records. Missing/changed source records, unknown jobs, initial attempts and watchdogs are rejected. Ten delivery tests pass. The native ledgers, cross-engine flags and fidelity limits remain unchanged.

## Exhausted phase-040 recovery completed

The early phase-040 inventory completed all three fresh seeds as Lithuanian Hussar wins at ticks 123929, 1588 and 1673; its independent exact replay of seed 1 passed. All source-plan, inventory, exhausted-error and runtime hashes passed validation. The final native checkpoint is `b715013b`, with completed review documentation at `ffee4401`. Do not restart this completed runner.

The refreshed phase-039 preview now contains 46,773 flagged predictions and 1,428 unresolved profile pairs. The 17 reviewed repaired projections include this source-phase-040 result only as an explicit cross-engine forecast. Its native observations stay in the separate event-memory ledger. Existing V3 observations, inferences, contexts, failure journals and frozen forecast rules are unchanged. Main phase 040 still has active normal retries and is not complete; no new recovery runner is active.

## Phases 040 and 041 reviewed; remaining phase-040 recoveries started

Phase 040 reviewed 256 planned pairs and 799 valid V3 seeds, with three blocked pairs / four missing seeds and a passed exact replay. The Aztec Skirmisher/Lithuanian Hussar gap already has a completed separate recovery. The other two Varangian Hussar/Byzantine and Saxon Skirmisher seed-1 failures exhausted all retries at final canonical event hashing; no failure is counted as a result.

Phase 041 passed all 256 pairs, 908 valid seeds, zero missing seeds and its exact replay, with no new blockers. The main runner continues phase 042. The phase-041 full-grid preview reconciles 555 variants, 1,540 civilization pairs, 151,223 cells and 68,916 profiles: 10,555 observed, 10,668 inferred, 45 equivalent, 46,592 flagged predictions and 1,056 unresolved gaps. It includes 17 already reviewed repaired projections; the two newly running pairs contribute nothing yet.

The remaining phase-040 recovery runs in `/workspace/aoe2_civ_phase040_stream`, branch `simulations/civ-matchups-phase040-stream-2026-11-02`, script `node/civ-matchups/recover-phase040-stream-first-pass.mjs`, campaign `civ-matchups-phase040-stream-first-pass-2026-11-02`, hash `ece39b03b9185b0eb166507ccaada6f299b064203b9f6110a247ae52d9e0bb71`, source `1ba4bb48`, log `/workspace/aoe2_civ_phase040_stream.log`. Two workers recompute complete native seed sets in parallel and perform independent exact replay reviews. All 62 runtime files exactly match the completed phase-039 memory-safe runtime; no physics or forecast model changes are introduced.

The builder's default additional event-memory inventories include this new frozen campaign. Ten delivery tests pass. A separate audit compared every listed recovery job's profile order, counts, weighted costs, scenario, family and policy against the frozen main inventory. Source journals, raw failures, original contexts, source/rule hashes and native physics ledgers remain preserved. This is a progress preview, not a completed first pass.

## All recoveries through source phase 040 completed

The remaining phase-040 inventory completed all six fresh seeds, with both independent exact replay reviews passing. Both Varangian Hussar pairs won at ticks 2052, 124076 and 1988. Final native checkpoint `df71b217` and review documentation `1cea1cca` are pushed. The completed runner must stay stopped; no recovery runner is active.

The refreshed phase-041 preview has 46,594 flagged predictions, 1,054 unresolved profile pairs and 19 completed repaired projections. Those keys exactly match all 19 currently recorded blocked source pairs. Observed/inferred/equivalent counts remain 10,555 / 10,668 / 45. Supporting native measurements stay in their separate physics ledgers, and no V3 failed or missing seed is promoted into a measurement. Full coverage and orientation checks pass, while remaining ordinary gaps await main phase 042 and subsequent phases. The first pass is still in progress.

## Phase 042 passed; phase 043 running

Phase 042 passed all 256 pairs, 824 valid seed records, zero missing seeds and its independent exact replay. No new failure or recovery inventory was introduced. The main runner continues phase 043 through its existing supervisor.

The full-grid phase-042 preview reconciles 555 variants, 1,540 civilization pairs, 151,223 cells and 68,916 profiles: 10,811 observed, 10,872 inferred, 45 equivalent, 46,406 flagged predictions and 782 unresolved gaps. The 19 completed repaired projections still account for all recorded source blockers, with native observations and fidelity limits preserved separately. No recovery runner is active. This remains an in-progress provisional preview; no first-pass completion or forecast validation is claimed.

## Phase 043 passed; phase 044 running

Phase 043 passed all 256 pairs, 824 valid seed records, zero missing seeds and its independent exact replay. It introduced no new errors or recovery inventory. The existing main runner and supervisor continue phase 044.

The phase-043 full-grid preview reconciles 555 variants, 1,540 civilization pairs, 151,223 cells and 68,916 profile pairs: 11,067 observed, 10,962 inferred, 45 equivalent, 46,251 flagged predictions and 591 unresolved gaps. All 19 previously blocked source pairs retain complete reviewed recovery support only as explicit cross-engine projections. Native physics ledgers, source/rule hashes, original contexts, failure records and fidelity limitations are preserved. No recovery is active. The first pass remains in progress.

## Phase 044 passed; phase 045 running

Phase 044 passed all 256 pairs, 831 valid seed records, zero missing seeds and its independent exact replay. It introduced no new errors or recovery inventory. The existing main runner and supervisor continue phase 045 without a restart.

The phase-044 full-grid preview reconciles 555 variants, 1,540 civilization pairs, 151,223 cells and 68,916 profile pairs: 11,323 observed, 11,034 inferred, 45 equivalent, 46,150 flagged predictions and 364 unresolved gaps. Its 19 reviewed repaired projections account for all recorded source blockers. Native physics ledgers, original contexts, source/rule hashes, failed examples, low-support flags and remaining validation work are preserved. No recovery is active. This remains an in-progress provisional preview; the remaining ordinary gaps still require simulation and review.

## Phase 045 passed; phase 046 running

Phase 045 passed all 256 pairs, 803 valid seed records, zero missing seeds and its independent exact replay. It introduced no new errors or recovery inventory. The main runner and existing supervisor continue phase 046 without a restart.

The phase-045 full-grid preview reconciles 555 variants, 1,540 civilization pairs, 151,223 cells and 68,916 profile pairs: 11,579 observed, 11,155 inferred, 45 equivalent, 45,993 flagged predictions and 144 unresolved gaps. The 19 reviewed repaired projections account for all recorded source blockers, preserving separate native physics ledgers and explicit fidelity limitations. Phase 046 includes all 144 current ordinary gaps plus the existing sample scaled down to 21 prediction checks. It is not a sampling-only second pass. Forecast rules, physical contexts, failures and validation flags remain unchanged; no recovery is active and completion is not yet claimed.

## Phase 046 passed; phase 047 running

Phase 046 passed all 165 planned pairs, 516 valid seed records, zero missing seeds and its independent exact replay. The frozen evidence rebuild left 24 ordinary direct gaps; phase 047 is simulating those with four existing prediction checks. No forecast rule was expanded and no new blocker or recovery inventory was introduced.

The phase-046 full-grid preview reconciles 555 variants, 1,540 civilization pairs, 151,223 cells and 68,916 profile pairs: 11,744 observed, 11,192 inferred, 45 equivalent, 45,911 flagged predictions and 24 unresolved gaps. All 46 phase reviews and required seed sets passed source accounting. The 31 historical missing V3 seeds remain explicitly missing in their original journals; their 19 source pairs have complete reviewed recovery support only as flagged cross-engine projections. Native physics and game-fidelity limitations remain separate. This is still an in-progress provisional preview.

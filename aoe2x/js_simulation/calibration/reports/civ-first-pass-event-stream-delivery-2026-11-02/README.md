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

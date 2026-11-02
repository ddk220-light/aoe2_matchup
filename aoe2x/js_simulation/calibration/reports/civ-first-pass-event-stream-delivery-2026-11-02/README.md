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

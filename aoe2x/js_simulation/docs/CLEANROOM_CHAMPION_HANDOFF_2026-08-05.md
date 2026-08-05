# Clean-room Champion simulator handoff — 2026-08-05

## Resume point

- Repository: `D:\AI\aoe2_matchup`
- Feature branch: `codex/cleanroom-champion-sim`
- Pushed implementation checkpoint: `320a440f` (`feat(sim): complete clean-room Champion simulator`)
- Current clean validation worktree:
  `D:\AI\aoe2_matchup\.worktrees\cleanroom-champion-validation`
- The original implementation worktree is no longer registered with Git. A
  plain residual directory with that name remains because Windows denied
  removal of `.pytest-tmp-task12-review`; it must not be used as a worktree.
- Production was not changed. Do not merge or push to `main` without a new,
  explicit user approval.

The clean-room engine, all five Champion ratio gates, the reproducible
comparison report, and the browser viewer are implemented and pushed. Desktop
browser validation has covered loading, selection/URL persistence, playback,
stepping, next-event navigation, and feedback persistence. A JSON-download
race found during that pass was repaired with a mounted temporary anchor and
deferred object-URL cleanup. Final mobile, console, all-ratio, download, and
Tailnet checks remain before the final milestone.

## Absolute evidence boundary

For this clean-room Champion phase, use only:

`aoe2x/js_simulation/calibration/source/aoe2_golden_basics_championvschampion_2026-08-04.zip`

Required SHA-256:

`33F4051CB1BE014CDF1D3813E7AB74EF619B468CB6196B5E92E7482508AA1BDE`

The ignored ZIP exists in the main project directory as well as the temporary
worktree at handoff time. The main-project copy was reverified with the exact
hash above, so removing the worktree will not destroy the authorized source.
Never substitute or inspect another tape archive for this work.

Runtime provenance additionally locks:

- `champion_basics.json` byte SHA-256:
  `5D40A39D...831E` (full value is enforced in source and reported output)
- Champion mechanics fixture byte SHA-256:
  `06CDE4E9...6595`
- installed DAT SHA-256:
  `CE3530DF36CF0B333A9751CB0FF94460FE904F811FEECEC8AE9794701622B4CF`
- reference database SHA-256:
  `51D602640E4C1A75F35286AA499821338B0EEE5DBA97E12A12D39E058CB11087`

The mechanics fixture was not re-extracted during the reporting phase; its
previous reproducible extraction and exact byte/source locks are enforced.

## What was built

### Map and scenario foundation

- Exact golden 16x16 map fixture and counterclockwise viewer transform.
- Literal Gaia objects and locked Panda Rock position.
- Exact 21v21 formation fixture from the latest golden scenario.
- Exact ratio rosters and starts for `1v1`, `2v1`, `2v3`, `5v3`, and `6v3`.
- Champion unit state is locked to master 567, 70 HP, sourced mechanics, and
  the scenario's literal placement/facing data.

### Deterministic combat engine

- Provisional 60 Hz integer tick clock. This is an explicit hypothesis based
  on all 15 recordings, not a published AoE2 engine constant.
- Frozen start-of-tick decisions and immutable snapshots/events.
- Sourced movement speed, body radius, reload, damage, armor, and sight.
- Equal-mass, nonpenetrating collision projection with bounds and static
  circular obstacles.
- Configuration-space local avoidance routes to legal target contact circles.
  Route side is chosen geometrically; scenario facing is used only for a truly
  symmetric first-choice tie. There is no global clockwise rule.
- Signed-gap collision convergence preserves an already tolerated numerical
  contact deficit without increasing epsilon or the 256-sweep safety cap.

### Target and engagement state machine

The old overloaded `targetId` was removed from unit state and split into:

1. `pursuitTargetId` — persistent movement intent, invalidated only after the
   pursuit target dies.
2. `engagedTargetId` — selected only from resolved physical enemy contact.
3. `attackTargetId` — captured when a swing starts and immutable through that
   swing's release or cancellation.

Tick phase order is:

`pursuit validation/acquisition -> movement -> collision -> engagement -> attack -> damage`

Physical contact never recomputes movement during the same tick. Simultaneous
contacts are ranked by swept time of impact, final surface gap, then reference
ID. Same-tick death cleans live engagements to the corpse, while a previously
captured non-ready swing remains observable until next-tick cancellation.

This separation was required by the authorized tapes: several units initially
move toward one opponent but first attack a different physically encountered
opponent. Generic live-target switching was tested and rejected.

### Acceptance report and verifier

- Generator: `tools/run_champion_suite.mjs`
- Shared comparison/verified playback boundary:
  `src/champion-comparison.js`
- Generated outputs:
  - `calibration/reports/champion_simulation_results.json`
  - `calibration/reports/champion_simulation_results.md`

The report validates exact fixture/source identities, recomputes tape HP%,
preserves all three tape-repeat diagnostics for every ratio, verifies every
14-damage hit, target/liveness lifecycle, terminal validity, non-overlap,
deterministic hashes, and exact median winner HP/HP%.

The source scan is deliberately described as a heuristic lint, not proof. Its
allowances are exact path/category/token/context fingerprints with expected
counts, so additional matches do not inherit a blanket exemption.

The playback serializer requires a supported ratio, authorized identities,
deeply frozen nonempty snapshots/events, strict run validity, terminal-state
agreement, and recomputed canonical final-state/event hashes.

### Browser viewer

The existing golden-map viewer now also provides:

- read-only no-store APIs:
  - `/api/champion/truth`
  - `/api/champion/mechanics`
  - `/api/champion/result?ratio=<ratio>&repeat=<1..3>`
- ratio/repeat URL state;
- play, pause, reset, one-tick, and next-event controls;
- explicit return to the locked 21v21 formation;
- tick/seconds, outcome, unit HP/action/target telemetry, and event timeline;
- exact 0.2-tile body circles and 0.4-tile melee contact/reach rings;
- separate pursuit, engagement, and captured-swing target lines;
- local suspicious-run flag and note per ratio/repeat;
- local feedback clear and JSON export;
- mounted-anchor JSON export with deferred object-URL cleanup so the browser
  cannot cancel the download before consuming the blob URL;
- mobile-responsive field-instrument/chronograph styling;
- no seed control and no browser-side simulation stepping.

Raw source archives and fixtures remain outside the server's public surface.

## Exact ratio results

| Ratio | Tape winner HP | Tape winner HP% | Sim winner HP | Sim winner HP% | Winner | Survivors | Damage events |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1v1 | 14 | 20% | 14 | 20% | owner 2 | 1 | 9 |
| 2v1 | 112 | 80% | 112 | 80% | owner 2 | 2 | 7 |
| 2v3 | 126 | 60% | 126 | 60% | owner 3 | 2 | 16 |
| 5v3 | 252 | 72% | 252 | 72% | owner 2 | 4 | 22 |
| 6v3 | 336 | 80% | 336 | 80% | owner 2 | 6 | 21 |

All five winner-HP and winner-HP-percentage deltas are zero. Reversed unit
arrays produce identical final-state and event-log hashes. The 5v3 and 6v3
gates additionally require per-snapshot non-overlap; 6v3 requires every
visible living attacker to have explainable progress/state rather than idle
overflow.

## Verification completed

- Complete JavaScript suite after the JSON export repair: **137/137 passed**.
- Task 13 focused server/renderer/viewer suite: **18/18 passed**.
- Task 12 focused Python provenance/reproducibility suite: **20/20 passed**.
- Modified JavaScript syntax checks passed.
- `git diff --check` passed except expected Windows line-ending/global-ignore
  warnings.
- Last generated report hashes before the viewer-only change:
  - JSON: `DA510EC1064FA48E8AA0D1138CD2E53754FD618EDDCB8BFE7B9C4FBCD5872C4C`
  - Markdown: `A27CF71CD6A079C71D96461E81BB112D75FCBA84EC0F2B1F848739D57BC40BCC`

Review loops were completed for Tasks 1–12. Task 13 passed automated tests and
self-review. Its manual browser pass is partially complete as recorded below.

## Browser validation state

Validated in the in-app browser at the local server:

- rendered desktop layout and exact golden-map scene;
- ratio switching (`1v1` to `6v3`) and repeat switching (`1` to `3`);
- URL selection persistence across reload;
- play/pause, one-tick, and next-event advancement;
- local flag and note persistence across reload;
- exact `6v3` simulation total of 336 winner HP.

The original JSON export click exposed a real browser race: it revoked its blob
URL immediately after clicking an unattached anchor. The repaired helper now
mounts the hidden anchor, clicks and removes it, then schedules URL revocation.
`tests/viewer-simulation.test.mjs` locks this operation order. The browser must
be restarted against the current validation worktree and the actual download
event rechecked before declaring the viewer complete.

The local server previously listening on port 5011 was launched from the
unregistered residual implementation directory and therefore serves the
checkpoint, not this follow-up. Resolve the exact owning process for port 5011,
stop only that process, and relaunch from the validation worktree. The existing
Tailscale mount is expected to remain:

`https://dragonstar.tail82a190.ts.net/golden-map`

## Important rejected approaches

Do not reintroduce any of these:

- arbitrary post-swing waits or movement pauses;
- speed, collision-radius, overlap, compression, damage, HP, or reload fitting;
- forced clockwise pursuit or owner/reference direction rules;
- ratio- or formation-specific combat branches;
- RNG added solely to reproduce tape winner variation;
- generic live target switching on body obstruction;
- recomputing movement after selecting a physical engagement;
- raising the collision sweep cap to conceal non-convergence;
- aiming an avoidance route at target center instead of the legal contact ring;
- treating 10 Hz recorder samples as exact internal movement/contact ticks.

## Next actions

1. Confirm `codex/cleanroom-champion-sim` is clean and synchronized with its
   remote tracking branch.
2. Confirm the ignored authorized ZIP in the validation worktree and verify its
   SHA-256.
3. Replace the exact port-5011 server process with one started from
   `aoe2x/js_simulation` in the validation worktree.
4. Continue the in-app browser pass on the actual rendered page:
   - all five ratios;
   - repeats 1–3;
   - play/pause/reset/+1/next-event;
   - target lines, body/reach rings, HP/actions, timeline;
   - formation return, pan/zoom, golden map/Gaia/Panda Rock;
   - URL state across refresh;
   - local flag/note persistence and JSON feedback download;
   - mobile viewport and zero console errors.
5. Confirm or repair the existing Tailscale serve route for the local port and
   provide the phone-accessible Tailnet URL.
6. Run a fresh reviewer pass over Task 13 plus any visual fixes.
7. Re-run the complete JS suite after visual fixes.
8. Update this handoff with final evidence and create the final milestone
   commit. Push only the feature branch unless the user separately approves a
   production/main action.

Suggested local checks:

```powershell
cd D:\AI\aoe2_matchup\aoe2x\js_simulation
Get-FileHash -Algorithm SHA256 calibration\source\aoe2_golden_basics_championvschampion_2026-08-04.zip
node --test tests
node server.mjs --host 127.0.0.1 --port 5011
```

The remaining browser/Tailnet checks are intentionally pending at this resume
point; do not describe the viewer as fully visually validated until they pass.

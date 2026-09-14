# Recorder roster simulation coverage

The recorder accepts a broader unit roster than the V3 engine originally registered. A recording can therefore succeed even when its unit has no simulation profile. On this branch, 24 of the 73 requested opponents were recording-only. The DB/DAT mechanics exporter and its runtime configuration were also absent from the branch; they have been restored from repository history.

## Repairs

- Added the 24 missing Imperial profiles and a generated supplemental unit registry.
- Restored the shared exporter and added `aoe2x/js_simulation/tools/export_roster_mechanics.py`. It resolves canonical roster labels against reference DB selectors, uses the matching game DAT, updates the supplemental registry, and exits unsuccessfully if any export fails.
- Missionary and Flaming Camel are absent from the website's reference selection table. Their profiles use explicit DAT masters and the shared UnitAnalyzer instead of substituting another unit.
- Corrected unsigned attack/armor multiplier decoding in UnitAnalyzer. The previous signed decode made Flaming Camel's Siege Engineers building bonus negative.
- Added the needed runtime handling for bonus-damage resistance, rechargeable melee/projectile shields, Monaspa group attack, flat trample, forward-line damage and suicide attacks. Added regression cases for the recorder roster and the newly supported mechanics.
- Regenerated both Ratha modes and Shrivamsha Rider to include missing defensive effects.

## Preflight and scope

Run from the repository root:

```powershell
node aoe2x/js_simulation/tools/preflight_recorder_roster.mjs .tools/recorder-roster-preflight.json
node --test aoe2x/js_simulation/tests/recorder-roster-mechanics.test.mjs aoe2x/js_simulation/tests/unique-special-effects.test.mjs aoe2x/js_simulation/tests/aoe2lab-worker.test.mjs
```

Verified on 2026-09-07: 74/74 canonical entries (Tiger plus 73 opponents) have source-backed profiles and load their Golden scenario inputs. All 28 focused tests pass. Every roster entry also runs a short combat smoke test. All 74 static overlay panels render with installed civilization artwork.

This does not mean every profile is empirically calibrated. The recorder uses the Golden patrol scenario with scripted kiting disabled; it does not need measured kite-cadence tapes. Missionary has no damaging attack, but the completed Golden recording confirmed that it automatically converts enemy units. The earlier assumption that this patrol scenario required no conversion behavior was incorrect. V3 conversion is not implemented, and Missionary is explicitly held as unsupported rather than assigned an accuracy verdict. Specialized mechanics still need evaluation against the real gRPC recordings.

A broader legacy test attempt encountered pre-existing missing calibration archives/tools and incomplete test sources; it was stopped after the relevant focused checks completed. It is not reported as a passing full test suite.

## Continuous outputs

`aoe2x/lab/postprocess_campaign.py` has separate, bounded overlay and simulation lanes. It consumes only verified raw bundles, retains five deterministic seed playbacks per saved plan, and writes a local HTML/JSON report. The default comparison uses winner agreement and signed remaining HP: positive for Tiger, negative for its opponent. MATCH requires 5/5 winner agreement and an absolute mean HP delta of at most 10 percentage points. This threshold is a reporting convention, not an accuracy guarantee.

The worker runs the complete roster preflight and focused tests before launching jobs. Source changes stop further scheduling; rerunning uses the new source fingerprint and invalidates old results. Seed cache provenance includes the saved plan hash. Raw recordings and gRPC files remain intact.

Local output directory: `aoe2x/js_simulation/calibration/lab/campaigns/tiger-all-unique-postprocess`. Overlay videos are next to their raw bundle under `unit-hp-overlay/battle-with-unit-hp.mp4`.

HP alignment is inferred from visible in-game health bars matched to recorded per-unit HP states; ambiguous fits fail for review. The first Composite Bowman clip's automatic estimate was within one frame of its independently measured manual alignment. Existing verified alignment is preserved. Encodes use temporary output names before replacing the completed overlay file.

Missionary recording recovery: converted entities were counted in both their old and new armies, preventing live end detection. The live and offline gRPC decoders now transfer army membership on ownership changes. Four dynamic-army regression tests pass. All 73 raw captures subsequently verified successfully.


## Parallel comparison scheduler (2026-09-07)

The campaign now accepts `--simulation-workers` (default 6, range 1–16). Each worker owns one matchup and runs its five seeds serially; there are at most six independent Node processes plus one overlay lane. No recording is running. Startup repeats 74-profile preflight and 28 mechanics/worker tests. Two scheduler/filter tests also pass.

The serial worker drained its active matchup. All 135 completed seeds were reused after verifying the simulation and overlay function ASTs, engine, fixtures, overlay and Node worker hashes were unchanged. The local `parallel-scheduler-migration.json` records the old/new scheduling revisions and file hashes. Results were not recomputed or changed by the scheduler migration. The repaired Missionary overlay was merged from its hash-verified media receipt; Missionary simulation remains explicitly unsupported because V3 lacks conversion.

`failures-over20.md` and `.json` refresh alongside the main report: they include completed comparisons with any wrong seed winner or absolute mean signed HP delta strictly greater than 20 percentage points. The original main report still uses its stricter 10-point MATCH classification.

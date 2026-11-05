# Simulation corrections for legacy/current advisor disagreements

The owner authorized fresh simulations for the complete old/new mismatch list,
followed by corrections to the current advisor data. Presentation and the
recommendation formula remain unchanged. Old winners do not automatically win a
disagreement: current frozen battle setups are simulated and reviewed first.

The complete identity-aligned inventory has 18,298 displayed cells across 10,227
distinct physical setups. It covers winner reversals, decisive/close differences,
legacy direction conflicts, concrete composition-coverage disagreements, and raw
yardstick-margin disagreements. Aggregate rank changes and recommendations that
changed solely because of the new weighting formula are excluded.

Inventory, source hashes and ongoing native records are on branch
`simulations/civ-matchups-mismatch-validation-2026-11-05` under
`aoe2x/js_simulation/calibration/campaigns/civ-matchups-mismatch-validation-2026-11-05`.
The complete CSV is under the corresponding `calibration/reports/` directory.

Four workers validate only this inventory. Complete original V3 observations get
a fresh exact replay and source review. Other contexts get seeds 0..2, extending
through seed 9 for mixed initial winners, plus an independent exact replay.
Gameplay, physical orientations, counts and scenarios stay frozen. The isolated
execution change streams every canonical event without retaining the complete
event history. Five focused tests and eight exact original/saved/stream controls
passed. No physics repair or forecast retraining is included.

The first released checkpoint independently verifies 17 physical setups. It
replaces 16 forecasts and one inference with complete measured evidence. These
cover 27 displayed cells; 16 outcomes change. Original predictions, rules,
sourceContext, low-support flags and values remain in each evidence record's
`originalEvidence` and `mismatchValidation` provenance. Current display flags
advance only after the reviewed seed set. All remaining guesses are preserved.

Snapshot: `data/validation/civ-matchups-legacy-mismatch-2026-11-05/checkpoint-001`.
Original database SHA-256:
`93e5732f5e1afd08a9be5b292506edb2f4ee41c2be4352a8bc4128184a05ebb8`.
The import maps a measured winner's profile hash to each displayed cell; it
never reverses a physical battle context. Original first-pass files/journals and
ranking scores are unchanged. Partial seed sets, diagnostics and timeouts cannot
replace table data. The full targeted validation campaign remains in progress.

Validation includes four import contracts covering reversed physical contexts,
preserved original forecasts, complete seeds, unchanged unrelated cells and
SQLite integrity, and preventing later snapshots from removing released
corrections, plus the existing complete-grid/orientation/API contracts.
The same exported advisor component feeds desktop, mobile and the Flask API.

The 195 public feature export checks passed; civilization, ranking and simulator
projections are byte-identical to the preceding release. Desktop and mobile
data-selection checks passed. The existing strict mobile menu/smooth-scroll
offset test is sensitive to the animated header's intermediate height on both
old and new datasets; no product presentation changes are included here.

## Cumulative checkpoint 002

The cumulative snapshot now independently verifies 255 physical contexts:
230 former forecasts and 25 former inferences have complete native seed sets
and exact replay reviews. This covers 426 displayed cells and changes 161
winner/close outcomes. Snapshot 001 and all its released corrections remain
preserved. The new serving database SHA-256 is
`b6f0c8d25dd01075dca6e63383173f8ef610dcf4c3e1af60b2ff5df82cbbf3ad`.

Ten correction/advisor tests and all 195 export checks passed. Public
civilization, ranking and simulator projections remain byte-identical. The
stalled Armenian Champion / Tupi slinger context contributes no correction;
its existing evidence and cells remain byte-identical to the immutable baseline.
See the operations document for the diagnosed unfinished quarantine and the
versioned rolling scheduler, which keeps the four-worker limit and all frozen
battle inputs while allowing unrelated contexts to continue across audit phases.

## Cumulative checkpoint 003

The independently verified cumulative snapshot covers 481 physical contexts:
403 fresh measured seed sets and 78 exact checks of existing native observations.
It reviews 1,283 displayed cells, replaces forecasts/inferences with measurements
in 638 cells, and changes 228 winner/close outcomes. Earlier released corrections
remain included. The serving database SHA-256 is
`5cedcc046177238c419af20b82aba8beb29b2ccb54fb71d7eec7ad3ddd11df81`.

Ten correction/advisor tests and all 195 export checks passed. Civilization,
ranking and simulator projections remain byte-identical. The quarantined context
still contributes no correction; its existing evidence and cells are unchanged.

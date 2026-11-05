# Matchup correction checkpoint 012

This cumulative update independently reviews 2,184 physical contexts under the frozen V3 gameplay: 2,028 fresh complete seed sets and 156 exact checks of existing native observations. It covers 4,432 displayed cells, adds measured evidence to 3,242 cells, and changes 502 winner/close outcomes. All earlier released corrections remain included.

The independently verified snapshot is `data/validation/civ-matchups-legacy-mismatch-2026-11-05/checkpoint-012`, sourced from validation commit `ec05a75b8ce39fa1ea549af247307ea5b35e6b99`. The serving database SHA-256 is `a99de1c2e435836c486f26c4530d6cc245a9c0774f953308b318302198b76c95`.

Ten correction/advisor tests and all 195 public export checks passed. Civilization, ranking and simulator projections are byte-identical to the previous release. UI and recommendation formulas are unchanged. Unfinished contexts (evidence IDs 702, 5982 and 22530) retain their original evidence and cells and contribute no correction.

The full validation campaign remains in progress. Partial seed sets, watchdogs and diagnostics are not measurements. Staging CI, exact preview checks, main CI and production verification remain required release gates.

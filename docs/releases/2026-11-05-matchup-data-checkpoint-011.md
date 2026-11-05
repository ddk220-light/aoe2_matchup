# Matchup correction checkpoint 011

This cumulative update independently reviews 2,087 physical contexts under the frozen V3 gameplay: 1,931 fresh complete seed sets and 156 exact checks of existing native observations. It covers 4,272 displayed cells, adds measured evidence to 3,082 cells, and changes 477 winner/close outcomes. All earlier released corrections remain included.

The independently verified snapshot is `data/validation/civ-matchups-legacy-mismatch-2026-11-05/checkpoint-011`, sourced from validation commit `5973c289ab2b174e084328ed37fa141e3b30b3bb`. The serving database SHA-256 is `e1bbff5a49cbad736623e40ec5e6b4bfabf462d1100969bc7f1976e1508254f9`.

Ten correction/advisor tests and all 195 public export checks passed. Civilization, ranking and simulator projections are byte-identical to the previous release. UI and recommendation formulas are unchanged. Unfinished contexts (evidence IDs 702, 5982 and 22530) retain their original evidence and cells and contribute no correction.

The full validation campaign remains in progress. Partial seed sets, watchdogs and diagnostics are not measurements. Staging CI, exact preview checks, main CI and production verification remain required release gates.

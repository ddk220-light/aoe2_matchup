# Matchup correction checkpoint 013

This cumulative update independently reviews 2,305 physical contexts under the frozen V3 gameplay: 2,149 fresh complete seed sets and 156 exact checks of existing native observations. It covers 4,628 displayed cells, adds measured evidence to 3,438 cells, and changes 524 winner/close outcomes. All earlier released corrections remain included.

The independently verified snapshot is `data/validation/civ-matchups-legacy-mismatch-2026-11-05/checkpoint-013`, sourced from validation commit `200d7dcd5f3fb8466c9d484d099f0e8cbe568b70`. The serving database SHA-256 is `2ea93603cf9b4e69ee6572c36938a0e49c63bca7a6384c0a2409d7d762325c1e`.

The formerly pending context `mv_369c6ecf6845478794dfc78d` now has all three valid seeds and a passed independent exact replay. Its slow seed completed normally in 2,946.99 wall seconds, after 202.23 game seconds. Evidence 22530 is now observed and retains its original inference, whose winner was confirmed. Unresolved contexts (evidence IDs 702 and 5982) remain unchanged and contribute no correction.

Ten correction/advisor tests and all 195 public export checks passed. Civilization, ranking and simulator projections are byte-identical to the previous release. UI and recommendation formulas are unchanged.

The full validation campaign remains in progress. Partial seed sets, watchdogs and diagnostics are not measurements. Staging CI, exact preview checks, main CI and production verification remain required release gates.

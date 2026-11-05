# Matchup correction checkpoint 010

This cumulative update independently reviews 1,859 physical contexts under the frozen V3 gameplay: 1,703 fresh complete seed sets and 156 exact checks of existing native observations. It covers 3,938 displayed cells, adds measured evidence to 2,748 cells, and changes 429 winner/close outcomes. All earlier released corrections remain included.

The independently verified snapshot is `data/validation/civ-matchups-legacy-mismatch-2026-11-05/checkpoint-010`, sourced from validation commit `02a27e5b08f0ad04005bf6986daac829cb4b0fbb`. The serving database SHA-256 is `1beb3eff6a04022e8fc8967efab978a6aae8452d2bdcfb87bdfb7cab7971d9a1`.

Ten correction/advisor tests and all 195 public export checks passed. Civilization, ranking and simulator projections are byte-identical to the previous release. UI and recommendation formulas are unchanged. The quarantined Armenian Champion / Tupi slinger context retains its original evidence and cells and contributes no correction.

The full validation campaign remains in progress. Partial seed sets, watchdogs and diagnostics are not measurements. Staging CI, exact preview checks, main CI and production verification remain required release gates.

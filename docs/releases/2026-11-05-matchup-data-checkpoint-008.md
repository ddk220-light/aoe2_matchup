# Matchup correction checkpoint 008

This cumulative update independently reviews 1,627 physical contexts under the frozen V3 gameplay: 1,471 fresh complete seed sets and 156 exact checks of existing native observations. It covers 3,545 displayed cells, adds measured evidence to 2,355 cells, and changes 375 winner/close outcomes. All earlier released corrections remain included.

The independently verified snapshot is `data/validation/civ-matchups-legacy-mismatch-2026-11-05/checkpoint-008`, sourced from validation commit `0cf0a042a60c050ee3677ade4592024b6a521311`. The serving database SHA-256 is `12688f6f068fc3f7ae5f5272559f899db9c71e115e9a53bebbbc0c7661603fdb`.

Ten correction/advisor tests and all 195 public export checks passed. Civilization, ranking and simulator projections are byte-identical to the previous release. UI and recommendation formulas are unchanged. The quarantined context and the active slow context (evidence IDs 702 and 35992) retain their original evidence and cells and contribute no correction.

The full validation campaign remains in progress. Partial seed sets, watchdogs and diagnostics are not measurements. Staging CI, exact preview checks, main CI and production verification remain required release gates.

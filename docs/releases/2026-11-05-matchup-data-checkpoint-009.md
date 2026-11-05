# Matchup correction checkpoint 009

This cumulative update independently reviews 1,713 physical contexts under the frozen V3 gameplay: 1,557 fresh complete seed sets and 156 exact checks of existing native observations. It covers 3,669 displayed cells, adds measured evidence to 2,479 cells, and changes 395 winner/close outcomes. All earlier released corrections remain included.

The independently verified snapshot is `data/validation/civ-matchups-legacy-mismatch-2026-11-05/checkpoint-009`, sourced from validation commit `5c89450ba699de83062e18e35a696ba5727dad8d`. The serving database SHA-256 is `165b4c55efefb95cf99f55ed6e44fec83d2f25335fd5cb1866de6c41bf67ce71`.

The formerly pending context `mv_2108fd04f6ba5704fcf5e1bb` now has all three valid seeds and a passed independent exact replay. Its slow seed completed normally in 2,650.86 wall seconds, after 202.23 game seconds; its earlier watchdogs remain failed attempts. Evidence 35992 is now observed, retains its original prediction and confirms the original winner. The quarantined context, evidence 702, remains unchanged and contributes no correction.

Ten correction/advisor tests and all 195 public export checks passed. Civilization, ranking and simulator projections are byte-identical to the previous release. UI and recommendation formulas are unchanged.

The full validation campaign remains in progress. Partial seed sets, watchdogs and diagnostics are not measurements. Staging CI, exact preview checks, main CI and production verification remain required release gates.

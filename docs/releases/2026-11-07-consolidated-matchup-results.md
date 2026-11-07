# Consolidated matchup results

The owner approved this production update on 2026-11-07 after reviewing the
legacy/current mismatch analysis. This is the single consolidated release;
the scheduled validation monitor remains paused.

The serving database now contains all **10,222 complete seed/replay reviews**
from the frozen 10,227-context inventory. Applying their exact physical
contexts also updates aliases elsewhere in the full grid: **37,546 displayed
cells** have reviewed evidence and **1,499 displayed outcomes** differ from
the immutable comparison baseline. The selected mismatch inventory itself
contains 18,293 reviewed displayed cells and 1,164 changed context
classifications (842 opposite winners and 322 mixed/close results).

The cumulative snapshot is retained at
`data/validation/civ-matchups-legacy-mismatch-2026-11-05/consolidated-2026-11-07/`.
Its original manifest and file hashes are unchanged. The native source is
`e6b6326de5675b4a804b906e30fa98c755584e74`; the independently checked research
bundle and analysis are published at
[`1a669f22601ce2118a8d8033330224f3326f2d2f`](https://github.com/ddk220-light/aoe2_matchup/commit/1a669f22601ce2118a8d8033330224f3326f2d2f).

The five simulator-blocked cases retain their original evidence, flags and
failures. The owner separately supplied these winners, all of which already
match their saved table outcomes:

- Armenian Champion over Tupi Imperial Slinger, 27/27.
- Hunnic Elite Tarkan over Aztec Elite Skirmisher, 18/27.
- Khitan Mounted Trebuchet over Chinese Elite Chu Ko Nu, 12/27.
- Viking Champion over Muisca Elite Guecha Warrior, 27/22.
- Gurjara Heavy Camel over Lithuanian Elite Skirmisher, 20/27.

The exact declarations and original physical order are preserved in
`data/validation/civ-matchups-legacy-mismatch-2026-11-05/user-confirmations/2026-11-07-five-blocked-winners.json`.
They are not relabeled as simulator measurements, and the native snapshot's
`complete: false` remains accurate. No engine retries, physics changes,
forecast retraining or additional validation campaign is included.

The import starts from immutable baseline SHA-256
`93e5732f5e1afd08a9be5b292506edb2f4ee41c2be4352a8bc4128184a05ebb8`.
The resulting serving database SHA-256 is
`36626bc0f74242de5482d98362695cec15226eb87cba8767371841a62bd231d5`.
Original predictions, rule/source hashes, source contexts and low-support flags
remain reconstructible through the evidence provenance.

All 555 variants, 1,540 civilization pairs, 151,223 displayed cells and 68,916
profile contexts remain covered. The presentation, recommendation formula,
ranking scores, civilization data and simulator physics are unchanged.
Forecasts and observations continue to display identically as requested.

Release gates are the correction/advisor tests, full-grid/context audit,
feature export checks, packaged backend and Astro build, exact-commit staging
CI and preview checks, followed by the authorized main push and production
verification. Production checks must confirm the cumulative review count,
representative changed outcomes, the five owner-supplied winners, versioned
advisor files and the normal site/API routes.

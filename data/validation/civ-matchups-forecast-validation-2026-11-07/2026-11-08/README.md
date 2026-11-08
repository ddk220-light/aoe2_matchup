# Forecast review snapshot released once on 2026-11-08

The owner explicitly requested a one-time website update with the latest completed research data. The authorization is preserved in `authorization.json`; recurring research checks remain data-only.

This unchanged snapshot contains 11,478 complete reviewed physical contexts: 6,415 single-seed confirmations and 5,063 multi-seed validations. There are 2,758 changed winner/close classifications and 8,720 retained forecasts. Its native source is [52e495a2](https://github.com/ddk220-light/aoe2_matchup/commit/52e495a2cc8b33dbcaac489dd4db6c49059e170f), and the independent research export is checkpoint 029 on `simulations/civ-forecast-validation-2026-11-07`.

The [full frozen list](https://github.com/ddk220-light/aoe2_matchup/blob/52e495a2cc8b33dbcaac489dd4db6c49059e170f/aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07/all-forecast-contexts.jsonl.gz) contains 39,148 contexts. The 27,670 remaining contexts, including held, exhausted and partial cases, are not measurements in this release. The confidence-ordered inventory and agreement-dependent stopping do not estimate unbiased global forecast accuracy.

The base is production commit `c907cc23668611851a2112911893929c3b905696`, DB SHA-256 `36626bc0f74242de5482d98362695cec15226eb87cba8767371841a62bd231d5`. It already includes the prior 10,222 mismatch reviews. The import preserves those reviews and all unreviewed evidence byte-for-byte, plus original predictions, flags, rule/source hashes and physical contexts. New replay evidence remains explicitly not required/not performed/exact=null; 651 historical replay checks remain unchanged. No battles were rerun for import or verification.

`independent-verification.json` binds the research snapshot and its source journal. `release-audit.json` checks every serving evidence row and displayed cell against the baseline. The serving DB now has 15,503 reviewed forecast cells, including 3,526 changed displayed outcomes. The 555 variants, 151,223 cells and 68,916 evidence rows are unchanged in coverage.

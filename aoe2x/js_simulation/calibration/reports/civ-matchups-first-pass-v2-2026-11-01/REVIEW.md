# First-pass predictions without a coverage ceiling

The user requested as much clearly flagged prediction coverage as the available evidence can support, rather than stopping at 75–80%. This separately versioned policy predicts **49,814 of the 51,805 unresolved phase-027 profile pairs (96.16%)**: 49,813 winner forecasts and one predicted close/uncertain result. **1,991 pairs remain unresolved**, including 13 blocked pairs. These predictions expand to **67,738 civilization cells**. They are not validated results.

The complete exported table still contains all **555 variants, 1,540 civilization pairs, 151,223 displayed cells and 68,916 distinct profile pairs**. Existing measured results, legitimate close results, exact-equivalence rows and validated direct-root inferences are preserved. Every guessed row has `evidenceType: predicted_unvalidated`, `verified: false`, `needsValidation: true`, its support tier, source outcome, rule hash and source hashes. Predicted close outcomes do not acquire a fabricated winner when display direction is reversed.

There is no percentage quota in the selector. The policy retains stronger forecasts, adds a weak directional lean when both frozen models favor the same winner over their other classes, and uses two opponent-specific methods to resolve some disagreements:

- **Shared opponents C:** use only completed, decisive, observed A–C and B–C fights. C must belong to A's or B's unit line. At least two common profiles, a median signed HP-margin gap of at least 0.10, and at least two-thirds directional agreement support a forecast. The HP margins are predictive features, not proof that matchups are transitive.
- **Observed fights against the exact opponent:** look for substitutions in the same unit line, class, mode, effect configuration and charge behavior, preserving the scenario, the fixed opponent's physical side and army count. The substituted army count may differ by at most one. Up to five nearest anchors must agree, with at least two anchors and RMS log-feature distance at most 0.15 across HP, speed, reload, range, exact static damage in both directions, accuracy and collision size. A target fight cannot become its own anchor.

If observed witness methods disagree, they do not resolve a model disagreement. A predicted close result requires both models to favor the close class. Inferred and guessed rows never enter the witness ledger. The frozen `observed-witness-anchors.jsonl.gz` records the direct source runs and contexts; hashes tie it to the frozen source matrix and seed ledger. Source rankings from the old engine remain features only.

Coverage comes with a visible accuracy tradeoff. Screening on completed phases 025–027 produced:

| Support tier | Remaining predicted pairs | Checked fights | Correct | Wrong or close called decisive |
|---|---:|---:|---:|---:|
| Stronger existing support | 26,981 | 388 | 387 | 1 |
| Previous broader model agreement | 11,888 | 183 | 165 | 18 |
| Weak directional agreement | 10,030 | 151 | 89 | 62 |
| Opponent-specific forecast | 914 | 17 | 14 | 3 |
| Both models predict close | 1 | 0 | 0 | 0 |

Overall, 655/739 screened forecasts were correct: 45 picked the wrong winner and 39 called a close fight decisive. **The weakest tier was correct on only 89/151 screened fights (58.9%).** Those 10,030 forecasts are low-support leans, not trustworthy measured wins. The sample was selected by the earlier simulation policy and is not a random accuracy estimate for all remaining pairs. No screening recount is presented as independent prospective validation of this revised policy. Phase 029 is its first untouched prospective phase.

The 32-per-phase validation sample remains separate from the deferred forecasts. Remaining phase slots focus on genuinely unresolved pairs, including existing refinement probes. A new failure is archived with its context and marks the precise forecast stratum contested; related guesses remain visibly unvalidated while tests and narrow revisions receive higher priority. Completed observed fights always replace their earlier guesses. The old v1 policy and its predictions are preserved.

This is a provisional frozen-V3 table. It does not mix V2 replay outcomes into V3 measurements or certify V2 compatibility. Engine mechanics, seed counts, historical journals, scoring and the web app remain unchanged. V2 repair/replay work continues separately.

# Conservative review of unexpected results

For the complete reproducible calculation, source roster, commands, examples,
and output schema, start with [Recorded rankings and the three top-25 lists](RECORDED_RANKING.md).

The September 21, 2026 instruction is to retain real surprises without tuning
the report to match expectations. An overall rank is not a prediction for every
opponent. Khitan combat regeneration versus another civilization's Bloodlines
is a meaningful tradeoff, not a reason to discard a Khitan win.

## What changes

Unexpected-result candidates still include a lower-ranked clear win when the
higher-ranked variant loses or draws, or when both win and the lower-ranked
variant keeps strictly more than 10 percentage points extra starting-army HP.
They now also include two clear losses when the lower-ranked variant leaves
strictly more than 10 percentage points less opponent HP. This measures net
depletion of the opponent's starting army, not cumulative damage dealt; healing
and differing opponent counts can affect the measurement. Do not mistake the
surviving opponent's HP for the defeated tested unit's own HP. Lower-ranked
draws still do not qualify. Exactly 10 percentage points does not qualify.
The existing under-10-percent draw rule, scores and rarity bonuses are unchanged.

Keep candidates by default. Dismiss an individual comparison from strategic
highlights only when the available evidence shows an obvious anomaly: matched
counts and relevant defenses, equal or weaker offense, and no compensating
ability or matchup-specific advantage. Review the actual opponent's armor and
damage classes, the authored buffer, and recorded counts. Do not discard a
result merely because its explanation is uncertain or its winner ranks lower.

For example, the Turkish Bolas Rider win over Malians has matched formations,
counts and HP; Malians deal at least as much damage, and Turks have no relevant
unique ability. This comparison is dismissed as inconclusive. It is not relabeled
as a loss, and one recording cannot prove randomness. A Turkish comparison with
Khitans has a real starting-HP tradeoff and remains an observed exception.

## Evidence and reproducibility

`report_knight_line_rankings.py` retains all candidates in `rankExceptions` and
the conservative presentation in `reviewedRankExceptions`. `upsets.json` remains
a wins-only compatibility export. `unexpected-performance.json` includes the
retained wins and losses. Dismissed comparisons remain in `ranking.json` and
`exception-review.json` with their reasons.

## Three editorial top-25 summaries

The overall ranking remains in `RANKING.md`. `HIGHLIGHTS.md` contains the three
requested summary views, without separate labels for better wins and defeats:

1. **Upward surprises:** one tested variant against one opponent, ordered by the
   number of distinct higher-ranked variants it outperformed on that opponent.
2. **Downward surprises:** the inverse of those exact comparisons, ordered by the
   number of distinct lower-ranked variants that outperformed it.
3. **Rare wins:** one variant's clear win against one opponent where a majority
   of other variants lost, ordered by the count of those other losses. Overall
   rank is irrelevant. Draws stay separate and are not losses for this measure.

A jump means one distinct peer, not ordinal rank distance or multiple tests of
the same peer. Compare all higher-ranked variants, not just the adjacent one.
Tie rows use civilization and then opponent alphabetically; alphabetic order
does not imply a stronger result. Apply the top-25 limit after grouping and
sorting. Dismissed comparisons are omitted symmetrically from the first two
views, while raw rare-win outcomes and ranking scores remain unchanged.
Do not pad a list with nonqualifying results when fewer than 25 exist.
`highlight-summary.json` retains the complete lists as well as their top 25;
`highlight-sources.json` contains projected evidence for an inline report.

Per-pair decisions live in `apps/video/ranking_reviews/<line>.json` with status
`retain` or `dismiss_obvious`, a rationale, evidence, and a capture fingerprint.
The fingerprint binds counts, outcomes, HP, rules, Golden, game version and ranks.
The manifest also records the reference database hash. A stale or missing review
retains the comparison without claiming its cause is understood.

Reference primary-hit calculations are explanatory checks, not simulated battle
predictions. They do not isolate pathing, focus fire, splash, charge, or healing
timing. Say when a relevant ability offers a plausible mechanism; do not claim
it proved the cause of a single observed win. Preserve raw captures and the full
unadjusted outcome matrix throughout.

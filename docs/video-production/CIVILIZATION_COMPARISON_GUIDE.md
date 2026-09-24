# Civilization comparison and highlight-selection handoff

Give this file to the person or agent analyzing a new unit family across
civilizations. It defines the overall ranking and the three lists used to select
interesting video chapters, using recorded results without starting new battles.
Rules checked against the reporting implementation on September 23, 2026.

The owner originally requested top 10, then expanded the display to **top 25**
and reduced the performance-gap threshold to **strictly more than 10 percentage
points**. These are the defaults. To make a top-10 presentation, take the first
10 rows of each final sorted list; do not change the ranking, thresholds,
comparison roster, or rarity denominator. Preserve the complete lists.

## Start here

1. Identify the intended unit family, civilization variants, common opponents,
   and capture rules. Select authoritative recordings using evidence, never
   whichever recording produces the most favorable result.
2. Validate the saved inputs and results. Reuse compatible recordings. A changed
   policy label, missing media, or disconnected disk does not justify a rerun.
3. Classify all results using the close-finish draw rule, then rank the full
   comparison roster. Calculate the three highlight lists from that fixed ranking.
4. Apply conservative, documented review to individual unexpected comparisons.
   Reviews affect editorial highlights only, not scores or recorded outcomes.
5. Deliver the ranking, three lists, complete evidence, and source limitations.

For the detailed historical specification and file schema, use
[RECORDED_RANKING.md](RECORDED_RANKING.md). For new capture rules, use
[BALANCE_POLICY.md](BALANCE_POLICY.md). For anomaly decisions, use
[RANKING_REVIEW.md](RANKING_REVIEW.md). For reuse and storage, use the
[minimal retake audit](KNIGHT_MINIMAL_RETAKE_AUDIT.md) and
[retention guide](RECORDING_RETENTION.md).

## 1. Define a comparable benchmark before scoring

One observation is **one civilization's unit variant versus one opponent**.
Comparing two variants means comparing their separate battles against that same
opponent; it does not mean the variants fought each other.

Save the following with the benchmark:

| Definition | Required decision |
|---|---|
| Identity | Stable family ID, variant keys/labels, exact upgraded unit and mode |
| Roster | Every intended variant, optional generic baseline, explicit opponent slugs |
| Sources | Authoritative archive indexes and explicit per-cell correction precedence |
| Rules | Saved game/data version, count/cost policy, cap, upgrade/relic assumptions, Golden and buffer rules |
| Exclusions | Opponent slugs and reasons; missing cells listed separately |
| Reproduction | Code revision, input-index hashes, review/reference-data hashes, report settings |

Include only the approved variants. Two civilizations with identical relevant
stats, abilities, costs, counts and scenario conditions may share one representative
if that is the chosen roster; record the equivalence instead of inventing another
battle. Adding duplicates as extra variants changes rarity and jump counts.
Adding a baseline also changes those denominators, so include it before scoring.

Use the same **explicit set of M opponents for every one of N variants**. Exclude
Flaming Camel, Missionary and War Chariot barrage mode from these rankings;
War Chariot focused-fire mode remains eligible. Keep excluded captures intact.
If a self-match was intentionally omitted, omit that opponent for every variant
in the shared benchmark and state why. Historical camel and knight reports have
70 shared opponents; **70 is not a quota for a new roster**.

An accidental missing or incompatible cell is a completeness problem. Do not
silently drop it and call the smaller intersection a final report. A preliminary
intersection may be useful, but label it incomplete and list what is missing.

### Source evidence and reuse

Read compact archives' `run.json` files. The required fields and nesting are
listed in [the input contract](RECORDED_RANKING.md#fields-consumed-from-runjson).
Use completed, verified battles. An interrupted capture, timeout awaiting review,
or pending result is missing evidence, not an automatic draw or loss.
Retain the job ID, frozen plan, actual starting counts, winner owner, winner HP,
starting HP denominator, normalized HP, game version, Golden hash, buffer count,
relic settings and authoritative source for every cell. Player 2 is the tested
unit; player 3 is the opponent. Player 4 support is excluded from main-army HP.

Check unique opponent identities within a source, known winner owners, finite
nonnegative HP, captured counts against the plan, and HP arithmetic against the
saved totals. Select corrections explicitly by opponent identity. An override
replaces one cell; it is not another trial to average. If multiple runs exist,
do not select the best result or average them without a separately agreed design.

Metadata can support ranking even when its MP4 or frames are unavailable.
Mark those cells `metadataOnly`; they cannot supply new overlays or video clips.
Preserve named raw MP4s, frames and reconstruction metadata wherever available.
Routine reporting need not rehash every large media file: use verified transfer
receipts and hash the small source indexes. Inspect frames/video for a specific
unresolved result, not as a blanket repeat of capture QA.

### Latest counts versus historical counts

New capture plans use `geometric_full_discount_weighted_resources_v3`:

```text
C = finalFood + 0.9 * finalWood + 1.1 * finalGold
cheaperCount = 27
expensiveCount = max(1, floor(27 * sqrt(cheaperC / expensiveC) + 0.5))
```

Costs are discounted purchase prices **per physical unit**, with full discount
effectiveness. Split batch purchases first. Every physical unit counts as one
comparison population; there is no resource ceiling. This is geometric cost
balance, not equal spending. Preserve the frozen effective cost and its evidence,
including any maximum conditional civilization discount used.

In mixed ranged/melee battles, calculate support after rounding main-army counts:

```text
T = actual fielded rangedCount * rangedC
Hussars = floor(clamp(5 + (T - 1000) / 1800, 5, 10) + 0.5)
```

There is no buffer in ranged/ranged or melee/melee battles. Support does not count
toward T or the main-army cap. Jarl is ranged for these scenarios. Full details,
exceptions and historical formulas are in [BALANCE_POLICY.md](BALANCE_POLICY.md).

Validate historical battles against their **saved inputs and actual conditions**.
Do not reprice old recordings from today's catalog. Reuse requires demonstrated
equivalence to the chosen benchmark; a version name alone neither proves nor
disproves compatibility. See the minimal retake audit before proposing recaptures.

For v3, different variants can legitimately have different opponent counts and
different Hussar counts. Validate each buffer against its own fielded ranged cost;
do not require identical support counts across all civilizations. The same rule
must apply consistently. Differences in game balance, upgrades, template behavior
or relic assumptions need explicit compatibility evidence. Intended civilization
bonuses are the variable being tested, not a reason to reject the comparison.

## 2. Classify outcomes and calculate overall rank

Let `P = 100 * surviving main-army HP / that army's own starting HP`.
For a tested-unit win, this is its own HP percentage. For a defeat, it is the
opponent's remaining HP percentage. Do not divide by the other army's HP or
interpret a defeated army's zero HP as a close finish.

Preserve the game's raw outcome. For ranking, treat a result as a draw when there
is no winner, or when the surviving side has **P < 10%**, whichever side won.
Exactly 10% remains a win/loss. Classify using full precision before rounding
display values. A draw is a presentation rule, not a measured win probability.

Classify the whole matrix before calculating rarity. For a clear win, let
`Lother` be the number of other variants with a clear loss to the same opponent.
Draws are not losses here. Let `h = min(P, 100) / 100` for scoring only.

```text
clear win:  points = 2 + h + Lother / (N - 1)
clear loss: points = -h
draw:       points = 0.5
totalPoints = sum(points over the M shared opponents)
displayScore = 100 * totalPoints / (4 * M)
```

Every opponent has equal weight. A win always scores more than a draw, and a
draw more than a loss. Overall rank uses the sum, not a rule that always puts any
extra win ahead of every possible HP/rarity difference. `displayScore` can be
negative and is not a win percentage. Retain uncapped P for evidence and HP-gap
comparisons; cap only the scoring term, including conversion cases above 100%.

Sort by descending total points, then stable variant key for display. Assign
competition ranks: `1 + count(other.points > own.points + 1e-9)`. Equal scores
share ranks (1, 1, 3). Do not compare tied ranks as higher/lower.

Show rank, variant, points/score, W/L/D, mean remaining HP across clear wins,
rare-win count and sole-win count. A sole win means no other clear winner;
the other variants may include draws. Mean winning HP is absent when there are
no clear wins. Keep raw outcomes and both kinds of close-finish reclassification.

## 3. Detect better performances against higher-ranked variants

Fix the overall ranks first. For each opponent, compare every lower-ranked variant
against **every strictly higher-ranked variant**, not just the adjacent rank.

| Lower-ranked result | Higher-ranked result | Qualifies when |
|---|---|---|
| Clear win | Loss or draw | Always |
| Clear win | Clear win | Lower retains more than 10 percentage points extra own HP |
| Clear loss | Clear loss | Lower leaves more than 10 percentage points less enemy HP |
| Draw | Anything | Never |
| Clear loss | Win or draw | Never |

For two wins, gap is `lowerOwnHP - higherOwnHP`. For two losses, gap is
`higherEnemyHP - lowerEnemyHP`. Use normalized starting-army percentages, not
absolute HP or relative percentage improvement. Require `gap > 10` and exclude
values within `1e-9` of 10, matching the implementation. Exactly 10 is excluded.

Example: lower-ranked A wins with 42%, while higher-ranked B wins with 29%:
13 percentage points qualifies. If both lose and A leaves the enemy at 21%
while B leaves it at 34%, the same 13-point advantage qualifies. A win against
B's draw also qualifies; A's draw against B's loss does not.

The defeat comparison measures **net depletion** of the opponent's starting army,
not cumulative damage dealt. Healing and differing army sizes matter. Preserve
W/L/D and HP ownership in the evidence, but combine qualifying cases in the
presentation rather than splitting the lists into win and defeat categories.

### Conservative review before selecting highlights

Keep unexpected comparisons by default, including plausible ability tradeoffs
such as Khitan regeneration versus Bloodlines. Do not remove a result merely
because its cause is uncertain or it conflicts with the overall ranking.

Dismiss only an individually documented obvious anomaly with no relevant stat,
ability, count or matchup advantage. Save the rationale, evidence and fingerprint
using [the review policy](RANKING_REVIEW.md). Missing/stale reviews retain the
comparison. A dismissal removes that pair from strategic highlights only; it
does not alter raw results, points, rarity or overall ranks. Do not claim one
recording proves randomness. Recheck review fingerprints when the roster changes.

## 4. Construct the three top-25 lists

Keep one retained edge `(lower variant, higher variant, opponent)` per qualifying
comparison. Deduplicate peers. A row in each list is **one variant against one
opponent**, not a civilization's total across all its matches.

| List | Grouping and ordering |
|---|---|
| Upward surprises | Group by lower variant + opponent; count distinct higher-ranked peers outperformed; descending count |
| Downward surprises | Invert those same edges; group by higher variant + opponent; count distinct lower-ranked peers that outperformed it; descending count |
| Rare wins | Independently select clear wins where `otherLosses > (N - 1) / 2`; descending other-loss count |

A jump means one distinct peer, not the ordinal distance between ranks. Rank 8
outperforming rank 1 is one jump. Outperforming ranks 1, 3 and 4 on the same
opponent is three jumps. Equal jump counts are real ties: display them by variant
label, opponent label, then opponent slug alphabetically. List peers by rank/key.
Apply the same alphabetical tie order to rare wins; neither HP nor overall rank
breaks a rarity tie. Truncate only after grouping and sorting. Never pad a list.

With nine variants, a rare win needs at least five of the other eight to lose.
Draws stay separate. A sole win surrounded by draws need not qualify for this
majority-loss list. The ranking's rarity bonus has no majority threshold: any
other clear losses contribute. Editorial dismissals do not affect rare wins.

Save the complete lists plus top-25 slices. A requested top 10 is simply
`allUpward[:10]`, `allDownward[:10]`, `allRareWins[:10]`. The full upward/downward
lists describe the same edges; their displayed slices need not mirror each other.

## 5. Run existing reports or adapt to a new family

The current [reporter](../../apps/video/report_knight_line_rankings.py) supports
`--line camel` and `--line knight` only. It has historical v1/v2 count validation,
fixed roster/completeness guards and equal-buffer checks. **Adding a new folder
to the source manifest alone is not enough to support a new v3 family.** Do not
use `--line mounted-crossbow` or simply whitelist v3 and claim it is validated.

For the existing benchmark, from the repository root:

```powershell
$env:PYTHONPATH='apps/video;.'
apps/video/.venv/Scripts/python.exe apps/video/report_knight_line_rankings.py --line camel --archive-root 'D:/AoE2 Renders' --require-current-all
apps/video/.venv/Scripts/python.exe apps/video/report_knight_line_rankings.py --line knight --archive-root 'E:/AoE2 Renders/knight-line-canonical' --require-current-all
```

Substitute the actual archive locations and Python executable on another system.
Drive letters are examples, not disk identity. The reporter needs Python 3.10+,
versioned source/review manifests, the tracked reference database, and archive
indexes. It needs no game, media encoder, network credentials or API key. Run
without Python `-O`, since existing validation uses assertions. See
[reproduction requirements](RECORDED_RANKING.md#1-recreate-the-reports).

When implementing support for another family:

1. Version its explicit roster and source selection, following
   [ranking_sources.json](../../apps/video/ranking_sources.json). Keep its exact
   expected opponent set, capture rules, exclusions and baseline alongside it.
   Extend CLI selection and use a separate output directory for the new family.
2. Adapt loading/completeness checks to that declared roster. Require all N
   variants and exact M opponent identities, not the historical 9/17/70 counts.
   Verify frozen v3 weighted costs, counts and per-cell scaled buffers. Replace
   the historical identical-buffer check for this policy; do not bypass checks.
3. Reuse `ranking_outcome`, `match_score`, `ranking_exceptions`,
   `review_ranking_exceptions` and `performance_highlights` from the reporter.
   The normalized `series[key].rows[opponentSlug]` and ranking schema are described
   in [RECORDED_RANKING.md](RECORDED_RANKING.md) and produced by `main()`.
   Adapt the loader, not the approved analytical formulas.
4. Record new-family review evidence independently. Do not copy camel judgments
   to different units. Retain candidates without a valid current review.
   Extend fingerprints if additional capture conditions are relevant.
5. Update generated labels and provenance to describe the actual policy and
   roster, including `highlight_sources()`; it currently contains historical
   benchmark wording. Preserve the existing output contract below.
6. Add focused adapter checks for roster completeness and legitimate variable
   buffers, then run the existing scoring tests. Validate analytical invariants
   below. No recapture is required to adapt or validate a report generator.

This guide documents that extension; it does not claim it has been implemented.

## 6. Deliver a reproducible result and choose chapters

Keep `RANKING.md` for the overall table, `HIGHLIGHTS.md` for the three lists,
`ranking.json` for complete per-cell evidence, and `highlight-summary.json` for
the full and truncated lists. Also retain `unexpected-performance.json` and
`exception-review.json` so every inclusion/dismissal is traceable. The complete
[output contract](RECORDED_RANKING.md#8-output-files-and-tracing-a-row) includes
source hashes and compatibility exports. Preserve a report snapshot before
changing the roster or rules; generated reports normally replace local outputs.

Check these invariants before delivery:

- Each variant has M results and W + L + D = M; no missing approved cells.
- Point components sum to total points; score normalization uses the same M.
- The complete upward/downward edge sets match, as do their summed jump counts.
- Every rare row is a clear win with a majority of other variants losing;
  other wins + draws + losses = N - 1.
- Top lists equal the requested leading slices; ties and threshold boundaries
  follow the rules above. Source and review hashes match the selected evidence.

The existing focused tests run without the game:

```powershell
$env:PYTHONPATH='apps/video;.'
apps/video/.venv/Scripts/python.exe -m pytest apps/video/tests/test_recorded_line_ranking.py -q -p no:cacheprovider
```

For chapter selection, start with the overall ranking, then use upward surprises
to show a lower-ranked variant's niche, downward surprises to show a leader's
weakness, and rare wins to show difficult opponents. Deduplicate opponent chapters
that appear in several lists. These lists guide the edit; they do not add another
score bonus or require new captures.

If a generic baseline is included, retain a separate W/L/D comparison: a variant
winning where the baseline loses is different from winning an already favorable
matchup. Keep draws visible. Do not add a baseline bonus to the ranking.
The overlay's per-opponent best-winner tally is also separate: it highlights
winning HP on that matchup, not the overall ranking or the three lists. Use the
[comparison overlay guide](CHAMPI_COMPARISON_OVERLAY.md) for presentation.

State limitations plainly: single recorded battles, any missing footage, and
unexplained mechanisms. Do not describe observed outcomes as win probabilities.
Never launch captures, renders, uploads or archive cleanup just to produce these
reports. If a necessary input is missing, identify that input and the smallest
remedy first; preserve all existing recordings.

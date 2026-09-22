# Recorded-unit rankings and the three top-25 lists

This is the reproducible specification for the overall ranking and the three
editorial lists used to choose comparison-video chapters. It records the approved
rules as of **September 21, 2026**: top 25, an HP advantage strictly greater than
10 percentage points, and finishes below 10% surviving HP treated as draws.

Start here when handing the analysis to another person or agent. The executable
implementation is [report_knight_line_rankings.py](../../apps/video/report_knight_line_rankings.py),
the versioned input roster is [ranking_sources.json](../../apps/video/ranking_sources.json),
and the focused checks are [test_recorded_line_ranking.py](../../apps/video/tests/test_recorded_line_ranking.py).
The report reads captured game results; it does not run the simulation engine or
start new recordings, overlays, renders, or uploads.

## Contents

1. [Recreate the reports](#1-recreate-the-reports)
2. [Inputs, rosters, and comparable battles](#2-inputs-rosters-and-comparable-battles)
3. [HP and adjusted outcomes](#3-hp-and-adjusted-outcomes)
4. [Overall ranking](#4-overall-ranking)
5. [Which performances qualify](#5-which-performances-qualify)
6. [Conservative review](#6-conservative-review)
7. [Build and order the three lists](#7-build-and-order-the-three-lists)
8. [Output files and tracing a row](#8-output-files-and-tracing-a-row)
9. [Validation, changes, and interpretation](#9-validation-changes-and-interpretation)

## 1. Recreate the reports

Use the same Git revision and the same archive indexes to reproduce a historical
result. Checkout `codex/video-recorder-v3`, or the specific recorded commit when
reproducing an older report. Do not switch the checkout of a running recorder;
use a separate checkout for historical analysis.

Required inputs:

- Python 3.10 or newer. The reporting script uses only the standard library;
  pytest is needed only for its tests. The recording PC already has
  `apps/video/.venv/Scripts/python.exe`.
- This script, `ranking_sources.json`, and any
  `apps/video/ranking_reviews/<line>.json` from the same revision.
- `data/golden/aoe2_reference.db` from that revision. It is tracked in Git and
  authenticates the reference data used by the saved camel reviews.
- Each required archive folder's `run.json`. Keep the named battle MP4 and frame
  file too for replay, inspection, and future overlays. They are not read by this
  metadata-only calculation.

Local capture queues, intro profiles, OAuth tokens, API keys, the installed game,
and FFmpeg are **not required to regenerate these reports**. The source roster
is versioned so it no longer depends on the recording PC's ignored queue files
or on later edits to an intro's civilization columns.

Run from the repository root on the recording PC:

```powershell
$env:PYTHONPATH='apps/video;.'
apps/video/.venv/Scripts/python.exe apps/video/report_knight_line_rankings.py --line camel --archive-root 'D:/AoE2 Renders' --require-current-all
```

After the [minimal knight corrections](KNIGHT_MINIMAL_RETAKE_AUDIT.md) are archived
and the retained Cavalier result indexes are built:

```powershell
$env:PYTHONPATH='apps/video;.'
apps/video/.venv/Scripts/python.exe apps/video/report_knight_line_rankings.py --line knight --archive-root 'D:/AoE2 Renders' --archive-root data/local/knight-reused-indexes --require-current-all
```

On another machine, substitute its Python executable and actual archive path.
Multiple archive locations are supported by repeating `--archive-root`. For
each required folder, the first root containing its `run.json` wins. Avoid two
different versions of the same folder in those roots: the tool does not choose
the newest file or reconcile conflicting copies. Specify the intended source
first and check the output's source hashes.

The command writes to `data/local/camel-line-ranking/` or
`data/local/knight-line-ranking/` inside the checkout, replacing previous generated
reports there. Save an existing report snapshot elsewhere locally if comparing
methodology revisions. It reads external archives without changing them.
The output directory is ignored by Git; the code, roster, review decisions, and
this specification are committed, while the raw evidence stays in the archives.

Use `--require-current-all` for the final result. Without it the script can make
a preliminary report from accessible variants and their comparable intersection;
its ranks, denominators, rarity, and review fingerprints can differ. A missing
variant is not assigned losses. Do not publish that preliminary result as the
complete benchmark. Python must run without `-O` or `PYTHONOPTIMIZE`, because
input and completeness checks use assertions.

Disk safety applies even when locating the inputs: never format, initialize,
erase, or repartition a drive, or suggest doing so. Never delete or overwrite
existing external contents. If a drive is unavailable, preserve all sources and
ask the owner to reconnect it. See [recording retention](RECORDING_RETENTION.md).

## 2. Inputs, rosters, and comparable battles

### Unit of observation

One cell is **one tested variant against one opponent in one recorded battle**.
The tested unit is owner/player 2; the opponent is owner/player 3. Distinct modes,
such as War Chariot focused fire and barrage, have distinct opponent slugs.
Comparing two camels' performances against the same opponent is not a direct
battle between those camels and is not an average of repeated trials.

### Required source sets

The exact folder names, stable keys, labels, and correction precedence are in
[ranking_sources.json](../../apps/video/ranking_sources.json). Do not infer the
roster from whatever folders happen to be connected.

| Line | Variants | Sources | Final shared opponents |
|---|---|---|---:|
| Camels | Hindustanis, Gurjaras, Berbers, Byzantines, Ethiopians, Saracens, Khitans, Malians, Turks | Nine `camel-comparison-*` folders; Hindustanis use Imperial Camel Rider, the others Heavy Camel Rider | 70 |
| Knights: expansion | Spanish, Burgundian, Celtic Paladins; Khmer, Berber, Malay Cavaliers; Wei, Wu, Shu Heavy Hei Guang Cavalry | Nine `knight-expansion-*` folders, each followed by its `knight-v2-leitis4-*` correction | 70 |
| Knights: completed replacements | Frank, Teutonic, four-relic Lithuanian Paladins; Persian Savar; Bulgarian Cavalier | Five completed `knight-v2-*` folders | 70 |
| Knights: reused originals | Polish, Burmese, Sicilian Cavaliers | Three `knight-reused-cavalier-*` result indexes, each followed by its two-cell `knight-count-fix-cavalier-*` archive | 70 |

The knight ranking combines all **17** variants. A compatibility key remains
`paladin-persians`; its label is Persian Savar and its archive is
`knight-v2-savar-persians`. Stable keys, not display names, identify comparisons.

An override is loaded after the base source and replaces the same opponent slug
in memory. It does not rewrite the base archive or add another battle to the
average. The approved nine correction archives contain the four-relic Elite
Leitis cell only. In a final knight report, all nine overrides are mandatory even
though the manifest field is named `optionalOverrides`. Inspect a new correction
index before adding it; later-source precedence applies to every matching slug
in that index. `variants[key].rows[slug].archive` identifies the authoritative
source, and `sources` includes both original and correction index hashes.

### Fields consumed from `run.json`

Each index has a `matchups` array. For each matchup the calculation uses:

| Field | Purpose |
|---|---|
| `jobId` | Identity of the selected recording |
| `plan.side3.slug`, `label`, `civ` | Opponent identity and display text |
| `plan.side2.count`, `plan.side3.count` | Intended starting counts |
| `plan.side2.comparison.comparisonCost`, likewise `side3` | Frozen comparison prices for independently checking counts |
| `plan.balance.cap`, `comparisonPolicy` | Count cap and formula version |
| `plan.scenario.opponentLithuanianRelics` | Opponent relic setting, default 0 |
| `capture.capture.winnerOwner` | Recorded winner: 2, 3, or null |
| `capture.capture.winnerHp`, `winnerStartingHp` | Surviving army's final HP and starting HP denominator |
| `capture.capture.winnerRemainingHpPercent`, `signedRemainingHpPercent` | Saved normalized result and signed cross-check |
| `capture.capture.startCounts`, `gameVersion` | Actual captured counts and game version |
| `capture.scenario.sourceGoldenSha256`, `player4Count` | Template identity and authored support-unit count |

`files` retains relative paths, byte sizes, and SHA-256 checksums for the named
battle MP4 and frames. The reporting script trusts the archive's captured result
after the metadata checks below; it does not independently rediscover the winner
from the video or hash every large media file on each invocation. Copy and
media-integrity verification are separate steps in the retention workflow.

The three reused Cavalier indexes are explicitly metadata-only: original plans,
capture results and metadata hashes were recovered from `retained-source-versions`,
including their existing four-relic Leitis fixes. Their original MP4/frame files
were not located on the connected disks. This does not require another battle
for ranking, but it does limit replay and overlay rebuilding. Each affected row
keeps `metadataOnly: true`; the report states this limitation. See the
[recovery command and audit](KNIGHT_MINIMAL_RETAKE_AUDIT.md).

### Counts and comparability

The benchmark uses `geometric_shared_discount_unit_count_v2`:

```text
shared-unit comparisonFood = finalFood + 0.5 * max(0, baseFood - finalFood)
shared-unit comparisonWood = finalWood + 0.5 * max(0, baseWood - finalWood)
shared-unit comparisonGold = finalGold
comparisonCost = comparisonFood + comparisonWood + comparisonGold
```

For a civilization-exclusive unit use its actual final purchase total. Prices
are per physical unit after splitting batch purchases. This halves positive
food/wood discounts for shared units, not the value of all food/wood; gold
discounts remain fully effective. Classification follows availability, not the
production building. See the complete [balance policy](BALANCE_POLICY.md).

Given frozen tested cost `A`, opponent cost `B`, and cap `K = 27`:

```text
roundUpHalf(x) = max(1, floor(x + 0.5))
if A <= B: counts = [K, roundUpHalf(K * sqrt(A / B))]
else:      counts = [roundUpHalf(K * sqrt(B / A)), K]
```

Equal costs give 27 each. Every physical unit counts as one comparison population;
there is no 5,000-resource ceiling. The reporter consumes the frozen comparison
costs, rather than recomputing discounts from today's DAT/catalog. Reduced game
population, supporting villagers, and additive population prices are not inputs.
Support units retain the Golden template's authored rules and are not extra
tested-unit slots. HP comes from the recorded side-2/side-3 result, rather than
adding player 4 to it.

For each source, the script rejects duplicate opponent slugs, invalid owners,
non-finite/negative HP, actual counts unequal to planned counts, inconsistent
HP arithmetic, or inconsistent signed HP. Its arithmetic check is
`math.isclose(..., abs_tol=1e-7)` with Python's default relative tolerance of
`1e-9`. A recorded draw's expected normalized and signed HP is zero.

It then builds the union of available opponent slugs and includes a slug only
when every included variant has that opponent, a recognized v1/v2 policy, actual counts matching
the formula, and matching `gameVersion`, opponent relic setting, Golden hash,
and buffer count across variants. Expected unit stats can differ by civilization;
these checks do not establish that every possible in-game mechanic was measured.

V1 and v2 share comparison-price rules in these captures. An old policy label
alone is not a reason to recapture: reuse it when its actual starting counts
match the current formula. Preserve its original policy label. The audited older
eight knight variants differed in only 16 of 591 count pairs, against Blackwood
Archers and Karambit Warriors; the other 575 did not need a count-driven rerun.

Exclude these three opponents from **all ranking metrics and all three lists**:

- `flaming_camel_tatars`: Flaming Camel.
- `missionary_spanish`: Missionary.
- `war_chariot_shu_barrage`: War Chariot barrage mode.

War Chariot focused fire stays included. Missing self-matches are excluded for
everyone: `imperial_camel_rider_hindustanis` for camels and `savar_persians` for
knights. The approved 74-opponent roster therefore produces 70 shared opponents.
The strict mode checks both that number and the exact excluded slug set, plus
all 9 or 17 variants. An unexpected incompatibility must not silently shorten a
final benchmark. Excluded raw recordings remain archived.

## 3. HP and adjusted outcomes

Let `P` be the surviving army's remaining HP as a percentage of **that army's own
starting HP**:

```text
P = 100 * winnerHp / winnerStartingHp
```

For a tested-unit win it is own HP; for a tested-unit loss it is enemy HP. Do not
divide a losing battle's surviving enemy HP by the tested army's starting HP.
The signed cross-check is `+P` for owner 2, `-P` for owner 3, and 0 for a draw.

Keep two outcomes:

- `recordedOutcome`: W for owner 2, L for owner 3, D for no winner.
- `outcome`: ranking interpretation after applying the close-finish rule.

| Recorded result | Surviving army's HP | Ranking outcome |
|---|---:|---|
| W or L | Strictly below 10% | D |
| W or L | Exactly 10% or greater | Preserve W or L |
| D | No winner | D |

This rule tests the surviving side, not the eliminated side's zero HP. It is a
chosen near-tie convention, not an estimated probability of winning a rematch.
Classify all cells before scoring or comparing them. Do not round displayed HP
to one decimal place first. `9.999999%` is a draw; `10.0%` is not.

For score calculations only, `h = min(P, 100) / 100`. Raw HP remains uncapped in
the evidence, averages, and performance-gap comparisons. This protects scores
from conversion cases exceeding the original HP pool without hiding the result.

## 4. Overall ranking

Let `N` be the number of included variants and `M` their common opponent count.
For a given winning cell, let `Lother` count other variants whose **adjusted**
outcome on that opponent is L. Draws are not losses for this count.

```text
rarityBonus = Lother / (N - 1)        # only awarded to W

W: points = 2 + h + rarityBonus
L: points = -h                       # h belongs to the surviving opponent
D: points = 0.5                      # no HP or rarity bonus

totalPoints = sum(points over all M opponents)
displayScore = 100 * totalPoints / (M * 4)
             = 25 * mean(points)
```

Every win earns more than any draw, and every draw more than any loss. Higher HP
improves a win; lower enemy HP improves a loss. The aggregate is a weighted sum,
not a lexicographic sort by win count. Its theoretical score range is -25 to 100;
the score is not a win percentage. All opponents receive equal weight.

Example with nine camels: a 40%-HP win when five of the other eight lose earns
`2 + 0.40 + 5/8 = 3.025`. A loss leaving 35% enemy HP earns `-0.35`. Either a
recorded draw or a sub-10%-HP finish earns `0.5`.

Sort by total points descending, then stable variant key. The reported rank is
`1 + count(other.totalPoints > own.totalPoints + 1e-9)`, allowing competition
ties such as 1, 1, 3. Do not compare equal-ranked variants in the surprise lists.
The alphabetic order of tied rows is not a substantive advantage.

The ranking also exposes:

- W/L/D counts after adjustment and separate counts of raw wins/losses converted
  to draws.
- Mean raw surviving HP across clear wins only; `null`/`n/a` if there are none.
- `minorityWins`: clear wins with `Lother > (N-1)/2`.
- `soleWins`: clear wins where nobody else clearly won; others may have drawn.
- Win, draw, signed HP, and rarity point components, which sum to total points.

Sensitivity recomputes scores for win weights 1, 2, 3 crossed with rarity weights
0.5, 1, 2. HP weight remains 1 and draws remain 0.5. The nine combinations provide
each variant's rank range; they test the scoring choice, not game randomness.
Their display denominator is `M * (winWeight + 1 + rarityWeight)`. The top-25
lists use the approved default ranking, not whichever sensitivity is convenient.

## 5. Which performances qualify

Fix the overall ranking first. For each opponent, compare a lower-ranked variant
`low` with **every** strictly higher-ranked variant `high` on that same opponent.
One of the following must hold:

| `low` outcome | `high` outcome | Qualifying condition |
|---|---|---|
| W | L or D | Always qualifies; no extra HP-gap requirement |
| W | W | `low own HP% - high own HP% > 10` |
| L | L | `high enemy HP% - low enemy HP% > 10` |
| D | Any | Does not qualify |
| L | W or D | Does not qualify |

The two HP comparisons use **percentage points**, not relative percentages.
For example, 32% versus 20% on two wins is a 12-point advantage and qualifies;
19% versus 10% is a 9-point advantage and does not. On two losses, leaving 30%
enemy HP versus 45% is a 15-point advantage and qualifies.

Exactly a 10-point gap does not qualify. The code checks `gap > 10` and excludes
values `math.isclose(gap, 10, rel_tol=0, abs_tol=1e-9)`, avoiding floating-point
noise at the boundary. Use full-precision raw percentages, never rounded display
values. This is separate from the **below 10% surviving HP** draw threshold.
The historical 15-point gap and top-10 display limit are superseded.

For two losses, lower enemy HP measures better **net HP depletion**. It does not
mean the tested unit won or prove it dealt more cumulative damage: healing and
different opponent counts affect that interpretation. Outcomes, HP ownership,
and gap types remain explicit in the JSON even though the editorial tables
combine them under better performance.

A higher-ranked draw counts as a non-win for an outcome reversal only. It stays
a draw for scoring, rarity bonuses, and the rare-win list. A lower-ranked draw
never counts as a winning surprise.

## 6. Conservative review

See [RANKING_REVIEW.md](RANKING_REVIEW.md) for the full policy and
[the camel decisions](../../apps/video/ranking_reviews/camel.json) for saved cases.
Keep unexpected results by default, including relevant tradeoffs such as Khitan
combat regeneration versus Bloodlines. Do not discard a result just because a
lower-ranked unit performed better, or because the mechanism is uncertain.

An individual comparison can be dismissed from strategic highlights only when
documented evidence supports an obvious anomaly with no relevant stat, ability,
or count advantage. Inspect the actual counts, defenses, attack/armor classes,
buffer and opponent interactions. For example, the saved Turks-versus-Malians
Bolas comparison is dismissed as inconclusive; it is not relabeled a loss or
claimed to prove randomness. Turks-versus-Khitans can have a real starting-HP
tradeoff and stays eligible.

The review key is `opponentSlug|lowerVariantKey|higherVariantKey`. Each decision
has `status` (`retain` or `dismiss_obvious`), nonempty `rationale`, nonempty
`evidence`, and a `fingerprint`. `exception_review_fingerprint()` hashes Python
`json.dumps(payload, sort_keys=True)` in UTF-8 with SHA-256. The payload contains
the review key, both overall ranks, and each cell's:

```text
jobId, recordedOutcome, outcome, winnerHpPercent, counts, policy,
gameVersion, opponentRelics, golden, bufferCount
```

Use the function to generate fingerprints; do not hand-construct hashes. The
manifest's `referenceDatabaseSha256` must match the tracked reference database.
A changed database disables those saved reviews. Missing or stale pair reviews
retain the comparison and mark it unreviewed. Archive-drive letters and the
display limit are not part of a pair fingerprint, so relocating identical
evidence does not invalidate it. The HP-gap threshold is also not a fingerprint
field; changing it discovers more/fewer candidates without automatically
revoking a still-valid judgment on unchanged evidence.

Review is pairwise: dismissing one higher-ranked comparator does not remove
other qualifying comparators for the same variant/opponent. Raw candidates,
retained comparisons, dismissed comparisons with reasons, and unreviewed cases
are all retained in output. Dismissals **never change raw outcomes, points,
overall rank, rarity bonuses, or the third list of rare wins**.

## 7. Build and order the three lists

Create one deduplicated edge `(lower variant, higher variant, opponent)` for
each qualifying comparison retained after review. The same peer counts once,
even if duplicate evidence or more than one criterion describes it.

### List 1: upward surprises

Group edges by `(lower variant, opponent)`. Count distinct higher-ranked peers
outperformed; that is the row's `jumpCount`. A rank-8 variant outperforming rank 1
on one opponent makes **one jump**, not seven. Outperforming ranks 1, 3, and 4 on
that opponent makes three jumps. This is not the total number of different
opponents a civilization beats across its campaign.

Sort by `jumpCount` descending, then variant display label, opponent label, and
opponent slug alphabetically. Peers within a row sort by overall rank, then
stable key. Keep the first 25 rows after grouping and sorting.

### List 2: downward surprises

Invert the exact same retained edges and group by `(higher variant, opponent)`.
Count distinct lower-ranked peers that outperformed that variant, sort with the
same rule, and keep the first 25. No separate performance detector is used for
this list. The complete upward and downward lists must describe the identical
set of edges, including symmetric removal of dismissed comparisons.

The displayed top-25 slices need not be mirror images because they group and
truncate differently. Equal jump counts are real ties; alphabetical display
order resolves where the top-25 cut falls without inventing a superiority claim.

### List 3: rare wins

Start from the adjusted outcome matrix, independently of ranks and mechanics
review. Each row is one variant's **clear win** on one opponent. Count all other
variants' clear losses, draws, and wins separately. Qualify only when:

```text
otherLosses > (N - 1) / 2
```

With nine camels, at least five of the other eight must lose. With 17 knight
variants, at least nine of the other 16 must lose. Draws are never losses here.
Sort by `otherLosses` descending, then variant label, opponent label, and slug
alphabetically. Keep up to 25. Neither overall rank nor HP breaks a rarity tie.

`soleWinner` means `otherWins == 0`, not necessarily that everybody else lost.
A clear win with seven losses and one draw is a sole win, but receives `7/8`
rarity bonus rather than `8/8`. This list has a majority-loss admission threshold;
the overall ranking's rarity bonus can reward a win against fewer other losses.

Do not pad any list if fewer than 25 qualify. The complete lists remain saved,
so the presentation limit does not discard evidence.

## 8. Output files and tracing a row

All files below are regenerated in `data/local/<line>-line-ranking/`:

| File | Contents |
|---|---|
| `RANKING.md` | Overall ranking, score, W/L/D, HP, rare/sole wins, sensitivity, sources |
| `HIGHLIGHTS.md` | The three editorial top-25 lists and their rules |
| `ranking.json` | Complete per-cell evidence, source hashes, exclusions, missing variants, scores, sensitivity, candidates, reviewed exceptions, and highlights |
| `highlight-summary.json` | `topUpward`, `topDownward`, `topRareWins`, plus untruncated `allUpward`, `allDownward`, `allRareWins` |
| `unexpected-performance.json` | Retained comparisons, rule, and dismissed pairs |
| `exception-review.json` | `retained`, `inconclusive`, and `unreviewed` review results |
| `upsets.json` | Legacy compatibility export containing retained W cases only; omits improved defeats |
| `highlight-sources.json` | Projected tables and provenance for chat source displays |

Manually saved `validation.json`, `sources.json`, or dated snapshots are optional
audit artifacts, not inputs to or required outputs of the generator.

Trace a table row as follows:

1. Find it in `highlight-summary.json` using its variant key and opponent slug.
2. Inspect its peer keys. Look up both cells in
   `ranking.json -> variants[key].rows[opponentSlug]` for recorded/adjusted
   outcomes, HP, counts, rules, points, job ID, and authoritative archive path.
3. For the comparison criterion and exact gap, read `rankExceptions` and
   `reviewedRankExceptions`. Internal fields `higherRankedNonWinners`,
   `higherRankedHpWins`, and `higherRankedHpLosses` correspond to the three
   eligibility rows above. `lowerRankedWinner` is a compatibility field and is
   null for an improved defeat; use `lowerRankedVariant` for the general key.
4. Inspect `inconclusiveRankComparisons` or `unreviewedRankComparisons` to see
   why a particular peer was excluded or retained without a current judgment.
5. Open the named archive's `run.json`, find `jobId`, then resolve the file paths
   under that archive directory to replay the battle or inspect frames.

`sources` stores the SHA-256 of every loaded `run.json`. `reproduction` also
stores the report script hash, source-manifest hash/path, review-manifest hash
(or null), and whether that manifest passed the database gate. A true
`reviewManifestApplied` does not mean every pair review was current; inspect
the per-pair review results. Keep the Git commit alongside a saved report.
Generated timestamps, absolute source paths, and code/provenance hashes may
change on regeneration; the analytical fields should match for unchanged inputs
and rules.

## 9. Validation, changes, and interpretation

Run the focused tests without touching the game:

```powershell
$env:PYTHONPATH='apps/video;.'
apps/video/.venv/Scripts/python.exe -m pytest apps/video/tests/test_recorded_line_ranking.py -q -p no:cacheprovider
```

They cover both draw boundaries, scoring order, draws in reversals, rank ties,
strict HP gaps on wins and losses, subtraction direction, percentage points,
review fingerprints, stale-review retention, unchanged score inputs, deduped
peer counts, inverse lists, rare-win treatment of draws, limits, and portable
roster loading without local capture queues.

For a final generated report check:

- No missing variants; exactly 70 comparable opponents and the four intended
  exclusions. Camels contribute 630 scored cells; knights contribute 1,190.
- Each variant's W + L + D equals 70. Point components sum to total points and
  `score100` equals `25 * totalPoints / 70` at the default weights.
- The full upward and downward lists contain identical edge sets. Their sums of
  `jumpCount` agree. Every displayed row occurs in its complete list and the
  top arrays equal its first 25 rows.
- Every rare row is a clear win, its peer counts sum to `N-1`, and its loss count
  exceeds half of `N-1`. Do not force 25 rare rows when only 21 qualify.
- Any dismissed comparison has valid current evidence, never merely an
  inconvenient outcome. Inspect the saved `run.json` hashes when comparing
  outputs from different disks or dates.

As a historical checkpoint, the completed camel report after the top-25/10-point
change had 9 variants, 70 opponents, 103 full upward rows, 142 full downward rows,
171 retained pair comparisons, 6 dismissed pairs, and 21 qualifying rare wins.
It displayed 25, 25, and 21 entries. Those are audit observations for those exact
archives and reviews, not hard-coded quotas for future results.

To change a benchmark, preserve the original captures and report snapshot first.
Version the source roster and rules explicitly. A new roster can change ranks,
rarity denominators, exception eligibility, and review fingerprints even when
individual battle results do not change. If the opponent roster grows, update
the strict completeness guard deliberately rather than dropping
`--require-current-all`. New overlays do not require recalculating battle results.

For future video structure, the overall ranking gives the benchmark order; the
first two lists suggest matchups where that order is least descriptive, and the
third emphasizes difficult opponents only a few variants beat. The lists are
descriptive chapter-selection aids, not independent score bonuses. Avoid counting
the same pair twice just because it appears in both directions. A single battle
does not establish repeatability or prove a proposed mechanical explanation.

Related workflow: [main production runbook](../VIDEO_PRODUCTION_RUNBOOK.md),
[camel capture and baseline](CAMEL_COMPARISON_CAPTURE.md),
[knight expansion](KNIGHT_EXPANSION_CAPTURE.md),
[current-policy knight recapture](KNIGHT_V2_RECAPTURE.md),
[balance policy](BALANCE_POLICY.md), [review policy](RANKING_REVIEW.md), and
[archive/rebuild retention](RECORDING_RETENTION.md).

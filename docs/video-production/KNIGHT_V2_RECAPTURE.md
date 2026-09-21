# Comparable knight-line re-recording

Final reporting is specified in [Recorded rankings and the three top-25 lists](RECORDED_RANKING.md),
including exact scoring, HP thresholds, review decisions, and reproduction commands.

Approved September 21, 2026 to replace the historical count policy for ranking,
while preserving all original recordings and archives.

The queue records Franks, Teutons and four-relic Lithuanian Paladins; Persian
Savar; and Bulgarian, Polish, Burmese and Sicilian Cavaliers. Each faces the
same frozen 74-opponent roster as the completed nine-variant knight expansion.
Savar versus itself remains omitted: 591 captures across these eight variants.

Every plan uses `geometric_shared_discount_unit_count_v2`: one comparison
population per physical unit, cheaper side capped at 27, square-root cost ratio,
shared-unit food/wood discounts half-effective and gold discounts fully
effective, without the old 5,000-resource ceiling. Golden files are unchanged.
Lithuanian Paladins receive the approved +4 melee attack trigger.

Opponent Elite Leitis receive the previously approved +4 relic attack too.
The nine expansion campaigns had inherited a baseline roster lacking this
setting. Nine isolated retakes correct only those cells; the other 657 expansion
captures remain authoritative. The original expansion plans are not edited.
Total queue: **600 new recordings**, no rendering or publishing.

Preparation: `apps/video/prepare_knight_v2_recapture.py`. It checks installed DAT
and cost-extraction hashes, uses existing audited identities without rewriting
catalogs, freezes all plans and catalogs, and refuses existing destinations.
Work: `data/local/knight-v2-recapture`. After preparation, start or resume with:

```powershell
$env:PYTHONPATH='apps/video;.'
$env:PYTHONUTF8='1'
apps/video/.venv/Scripts/python.exe -u apps/video/run_knight_expansion.py --work data/local/knight-v2-recapture
```

Each full variant passes its first capture's HP/count pilot. The existing
recorder mutex prevents concurrent game control; exports run separately.
Thermal checks remain at 15 minutes. Archive identity and a 4 GiB reserve are
checked throughout each capture pass; a failure requests a stop at a battle
boundary, preserving sources. SAFEHOUSE is Buffalo serial `00000107000079B6`,
volume serial `1588195055`, currently D:. Never format or change disk layout.

Completed variants compact to new `D:/AoE2 Renders/knight-v2-*` folders with
named battle videos, binary frames and `run.json` reconstruction metadata.
Local media is retired only after verified copies and durable receipts. Existing
external files and the historical archives must never be overwritten or removed.

After all captures and archives finish, combine the eight new archives with the
nine expansion archives, applying `knight-v2-leitis4-*` as explicit overrides.
Rank all 17 variants on the 70 shared opponents (Savar self-match, Flaming Camel,
Missionary and War Chariot barrage mode excluded for everyone). War Chariot
focused-fire mode remains included. The user requested these ranking exclusions
on September 21, 2026; this does not change the capture queue. Preserve the full
74-opponent raw outcome tables for all other
variants. The ranking request values wins first, then HP margin and rare wins;
record its exact formula and per-match scores with the final report.

For ranking only, classify a finish as a draw if the surviving side has strictly
less than 10% of its starting army HP, regardless of which side won in game.
Exactly 10% remains a win/loss. Give every draw 0.5 points, without HP or rarity
bonuses; wins score 2 plus surviving HP fraction plus the fraction of other
variants that lost, and losses score minus the opponent's surviving HP fraction.
Recompute rarity after this classification; draws do not count as losses for
the score's rarity bonus. In the separate unexpected-win report, a clear win
by a lower-ranked variant qualifies when a higher-ranked variant lost or drew.
Keep L/D labels visible; this exception rule does not alter ranking points.
Lower-ranked draws never qualify as wins. Preserve original outcomes and HP.
Also flag an unexpected HP advantage when both variants clearly win the same
opponent and the lower-ranked variant retains strictly more than 10 percentage
points extra HP, each normalized to its own starting army HP. Exactly 10 points
does not qualify. Keep these comparisons separate from outcome reversals and
do not add them to the ranking score or rarity bonus.

Keep anomaly review conservative. Retain unexpected wins and HP margins by
default, especially genuine tradeoffs such as Khitan combat regeneration versus
Bloodlines. Do not require every surprise to have a proven causal explanation.
Dismiss only an obvious matchup-specific anomaly where the lower-ranked variant
has no relevant stat, ability or count advantage, and record why. An unexplained
result is not proof of randomness. Dismissals affect strategic highlights only;
do not rewrite recorded wins/losses, score points or rarity bonuses.
`apps/video/ranking_reviews/<line>.json` stores individual decisions bound to the
actual capture evidence. Missing or stale reviews retain the comparison. See
[ranking review policy](RANKING_REVIEW.md).

The September 21 editorial update also includes losses with strictly over
10 percentage points less enemy HP remaining. Keep `RANKING.md` focused on the
overall ranking; deliver `HIGHLIGHTS.md` with top-25 upward surprises, top-25
downward surprises and top-25 rare wins as defined in the ranking review policy.

The old-policy ranking sources are on the disconnected older archive disk.
They are unnecessary for this new capture queue and must not be substituted
for current-policy outcomes. Existing preliminary analysis lives in
`data/local/knight-line-ranking`; rebuild it once all 17 current-policy sets exist.

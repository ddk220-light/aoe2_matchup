"""Rank recorded knight- or camel-line outcomes without modifying archives.

Run with one or more --archive-root arguments when disks are connected.
Keeps per-match evidence, missing variants, exclusions, and weight sensitivity.
Methodology and reproduction: docs/video-production/RECORDED_RANKING.md.
"""
import argparse
import copy
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

REPO = Path(__file__).resolve().parents[2]
SOURCE_MANIFEST = REPO / "apps/video/ranking_sources.json"
# These battles remain in the archives but are outside the user's ranking scope.
RANKING_EXCLUSIONS = {
    "flaming_camel_tatars": "Flaming Camel",
    "missionary_spanish": "Missionary",
    "war_chariot_shu_barrage": "War Chariot (Barrage)",
}
DRAW_THRESHOLD_HP_PERCENT = 10.0
DRAW_POINTS = 0.5
# This is a between-battles HP gap, distinct from the surviving-army draw cutoff.
UNEXPECTED_WIN_HP_GAP_PP = 10.0
HIGHLIGHT_LIMIT = 25
EXCEPTION_FIELDS = ("higherRankedNonWinners", "higherRankedHpWins", "higherRankedHpLosses")
COUNT_POLICIES = {"geometric_shared_discount_v1", "geometric_shared_discount_unit_count_v2"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def ranking_outcome(winner_owner, winner_hp_percent):
    """Classify the surviving army, not the eliminated side's zero HP.

    The threshold is strict: a finish at exactly 10% remains a win or loss.
    This changes ranking interpretation only; raw capture outcomes are retained.
    """
    if winner_owner is None or winner_hp_percent < DRAW_THRESHOLD_HP_PERCENT:
        return "D"
    return "W" if winner_owner == 2 else "L"


def match_score(row, win_weight=2, rare_weight=1):
    """Score an adjusted outcome; hpFraction is the capped survivor fraction.

    Rarity uses clear losses among all other variants, never draws or ranks.
    Highlight selection and mechanics reviews must not feed back into this score.
    """
    if row["outcome"] == "D":
        return DRAW_POINTS
    if row["outcome"] == "W":
        return win_weight + row["hpFraction"] + rare_weight * row["rarityBonus"]
    return -row["hpFraction"]


def expected_counts(plan):
    """Check v2 counts using frozen comparison costs, not today's game catalog.

    Population is one per physical unit. Round halves upward, not Python's
    ties-to-even round(); the cheaper side fills the saved cap (27 here).
    """
    a, b = (plan[s]["comparison"]["comparisonCost"] for s in ("side2", "side3"))
    cap = plan["balance"]["cap"]
    rounded = lambda x: max(1, math.floor(x + .5))
    return [cap, rounded(cap * math.sqrt(a / b))] if a <= b else [rounded(cap * math.sqrt(b / a)), cap]


def counts_match_current_policy(policy, captured, expected):
    """Reuse equivalent battles; an old policy label alone does not require a rerun.

    V1 and v2 share comparison-price rules. V1 can differ only through population
    weighting/counts here; require the actual army counts to match the v2 formula.
    Golden, game version, relics, and buffer checks remain separate and mandatory.
    """
    return policy in COUNT_POLICIES and captured == expected


def source_specs(line):
    """Load the versioned roster, independent of local queues and intro edits.

    Knight corrections are already merged into the canonical variant indexes.
    Historical manifests may still list correction folders in precedence order.
    """
    manifest = read(SOURCE_MANIFEST)
    if manifest["schemaVersion"] != 1:
        raise ValueError("Unsupported ranking source manifest version")
    return manifest[line]


def ranking_exceptions(ranking, series, opponents):
    """Find better outcomes, healthier wins, and more effective defeats.

    This is a descriptive view of the finished ranking, never a score input.
    Higher-ranked draws qualify as non-wins here, but remain draws in scoring.
    Equal-outcome HP margins must exceed 10 percentage points. On a defeat,
    less opponent HP is better: reverse the subtraction, and never describe
    the survivor's HP as the defeated variant's own HP. Remaining HP measures
    net depletion, not cumulative damage when healing is involved.
    Lower-ranked draws and rank ties do not qualify.
    """
    exceptions = []
    for slug in opponents:
        for variant in ranking:
            row = series[variant["key"]]["rows"][slug]
            if row["outcome"] not in ("W", "L"):
                continue
            higher = [v for v in ranking if v["rank"] < variant["rank"]]
            non_winners, hp_wins, hp_losses = [], [], []
            for v in higher:
                other = series[v["key"]]["rows"][slug]
                comparison = dict(key=v["key"], label=v["label"], rank=v["rank"],
                                  outcome=other["outcome"], recordedOutcome=other["recordedOutcome"],
                                  survivingHpPercent=other["winnerHpPercent"])
                if row["outcome"] == "W" and other["outcome"] in ("L", "D"):
                    non_winners.append(comparison)
                elif row["outcome"] == other["outcome"] == "W":
                    gap = row["winnerHpPercent"] - other["winnerHpPercent"]
                    if gap > UNEXPECTED_WIN_HP_GAP_PP and not math.isclose(
                            gap, UNEXPECTED_WIN_HP_GAP_PP, rel_tol=0, abs_tol=1e-9):
                        hp_wins.append(dict(**comparison, hpGapPercentagePoints=gap))
                elif row["outcome"] == other["outcome"] == "L":
                    gap = other["winnerHpPercent"] - row["winnerHpPercent"]
                    if gap > UNEXPECTED_WIN_HP_GAP_PP and not math.isclose(
                            gap, UNEXPECTED_WIN_HP_GAP_PP, rel_tol=0, abs_tol=1e-9):
                        hp_losses.append(dict(**comparison, hpGapPercentagePoints=gap))
            if non_winners or hp_wins or hp_losses:
                exceptions.append(dict(
                    opponentSlug=slug, opponent=row["opponent"],
                    opponentCivilization=row["opponentCivilization"],
                    lowerRankedVariant=variant["key"],
                    lowerRankedWinner=variant["key"] if row["outcome"] == "W" else None,
                    label=variant["label"], outcome=row["outcome"],
                    hpOwner="own" if row["outcome"] == "W" else "opponent",
                    rank=variant["rank"], winnerHpPercent=row["winnerHpPercent"],
                    higherRankedNonWinners=non_winners,
                    higherRankedHpWins=hp_wins, higherRankedHpLosses=hp_losses))
    return exceptions


def exception_review_key(exception, comparison):
    lower = exception.get("lowerRankedVariant") or exception["lowerRankedWinner"]
    return "|".join((exception["opponentSlug"], lower, comparison["key"]))


def exception_review_fingerprint(exception, comparison, series):
    """Bind a mechanics judgment to its actual captures, counts and outcomes."""
    fields = ("jobId", "recordedOutcome", "outcome", "winnerHpPercent", "counts",
              "policy", "gameVersion", "opponentRelics", "golden", "bufferCount")
    slug = exception["opponentSlug"]
    payload = {"key": exception_review_key(exception, comparison),
               "lowerRank": exception["rank"], "higherRank": comparison["rank"]}
    lower = exception.get("lowerRankedVariant") or exception["lowerRankedWinner"]
    for name, key in (("lower", lower), ("higher", comparison["key"])):
        row = series[key]["rows"][slug]
        payload[name] = {f: row.get(f) for f in fields}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def review_ranking_exceptions(exceptions, series, review=None):
    """Dismiss only documented obvious anomalies, without retuning outcomes.

    The default is to retain an unexpected result. Missing explanations, stale
    reviews, or tradeoffs involving relevant unique abilities do not suppress it.
    A specific obvious anomaly can be hidden from highlights, never from scores.
    """
    decisions = (review or {}).get("decisions", {})
    retained, inconclusive, unreviewed = [], [], []
    for exception in exceptions:
        kept = copy.deepcopy(exception)
        for field in EXCEPTION_FIELDS:
            kept[field] = []
        for field in EXCEPTION_FIELDS:
            for comparison in exception.get(field, []):
                key = exception_review_key(exception, comparison)
                decision = decisions.get(key, {})
                current = exception_review_fingerprint(exception, comparison, series)
                valid = (decision.get("fingerprint") == current
                         and decision.get("status") in ("retain", "dismiss_obvious")
                         and bool(decision.get("rationale")) and bool(decision.get("evidence")))
                record = dict(key=key, opponentSlug=exception["opponentSlug"],
                              opponent=exception["opponent"], lowerRankedWinner=exception["lowerRankedWinner"],
                              lowerRankedVariant=exception.get("lowerRankedVariant") or exception["lowerRankedWinner"],
                              lowerLabel=exception["label"], higherRankedVariant=comparison["key"],
                              higherLabel=comparison["label"], comparisonKind=field,
                              fingerprint=current)
                if not valid:
                    unreviewed.append(dict(**record, reason="Retained: no current documented obvious anomaly"))
                    kept[field].append(copy.deepcopy(comparison))
                elif decision["status"] == "dismiss_obvious":
                    inconclusive.append(dict(**record, rationale=decision["rationale"], evidence=decision["evidence"]))
                else:
                    kept[field].append(dict(**comparison, mechanicsRationale=decision["rationale"],
                                            mechanicsEvidence=decision["evidence"]))
        if any(kept[field] for field in EXCEPTION_FIELDS):
            retained.append(kept)
    return dict(retained=retained, inconclusive=inconclusive, unreviewed=unreviewed)


def performance_highlights(ranking, series, opponents, exceptions, limit=HIGHLIGHT_LIMIT):
    """Three editorial lists, never inputs to the overall ranking.

    A row is one variant against one opponent, not a direct camel-vs-camel
    fight. A jump counts a distinct peer outperformed, not ordinal distance.
    The downward list is the exact inverse of the retained upward comparisons.
    """
    variants = {v["key"]: v for v in ranking}
    upward, downward = {}, {}
    for e in exceptions:
        lower = e.get("lowerRankedVariant") or e["lowerRankedWinner"]
        slug = e["opponentSlug"]
        for field in EXCEPTION_FIELDS:
            for peer in e.get(field, []):
                higher = peer["key"]
                # Dedupe peers even if several criteria describe the same pair.
                upward.setdefault((lower, slug), {})[higher] = peer
                downward.setdefault((higher, slug), {})[lower] = dict(
                    key=lower, label=e["label"], rank=e["rank"])

    def summarize(groups):
        rows = []
        for (key, slug), peers in groups.items():
            v, battle = variants[key], series[key]["rows"][slug]
            rows.append(dict(key=key, label=v["label"], rank=v["rank"],
                             opponentSlug=slug, opponent=battle["opponent"],
                             opponentCivilization=battle["opponentCivilization"],
                             jumpCount=len(peers),
                             peers=sorted(peers.values(), key=lambda p: (p["rank"], p["key"]))))
        # Equal jump counts are genuine ties; alphabetic order is only display order.
        rows.sort(key=lambda r: (-r["jumpCount"], r["label"], r["opponent"], r["opponentSlug"]))
        return rows

    up, down = summarize(upward), summarize(downward)
    rare = []
    n = len(ranking)
    for v in ranking:
        for slug in opponents:
            battle = series[v["key"]]["rows"][slug]
            if battle["outcome"] != "W":
                continue
            peers = [dict(key=o["key"], label=o["label"], rank=o["rank"],
                          outcome=series[o["key"]]["rows"][slug]["outcome"])
                     for o in ranking if o["key"] != v["key"]]
            losses = sum(p["outcome"] == "L" for p in peers)
            if losses <= (n - 1) / 2:
                continue
            draws = sum(p["outcome"] == "D" for p in peers)
            wins = sum(p["outcome"] == "W" for p in peers)
            rare.append(dict(key=v["key"], label=v["label"], rank=v["rank"],
                             opponentSlug=slug, opponent=battle["opponent"],
                             opponentCivilization=battle["opponentCivilization"],
                             otherLosses=losses, otherDraws=draws, otherWins=wins,
                             soleWinner=wins == 0, winnerHpPercent=battle["winnerHpPercent"], peers=peers))
    rare.sort(key=lambda r: (-r["otherLosses"], r["label"], r["opponent"], r["opponentSlug"]))
    return dict(
        limit=limit,
        rowDefinition="One variant against one opponent. Compare every strictly higher/lower rank, not only adjacent ranks.",
        ordering="Jump count descending; ties use civilization then opponent alphabetically. A jump is one distinct peer outperformed, not rank-position distance.",
        rarityRule="Clear win while a majority of other variants lose; order by number of other losses. Draws stay separate and do not count as losses. Overall rank is irrelevant.",
        topUpward=up[:limit], topDownward=down[:limit], topRareWins=rare[:limit],
        allUpward=up, allDownward=down, allRareWins=rare)


def highlight_markdown(highlights, line):
    lines = [f"# Recorded {line}-line highlights", "",
             "[Overall ranking](RANKING.md) remains separate. These three lists select opponent-specific material for the video without changing that ranking.", "",
             highlights["rowDefinition"], "", highlights["ordering"], "",
             f"Better performance includes a clear win against a loss/draw, over {UNEXPECTED_WIN_HP_GAP_PP:g} percentage points more own HP when both win, or over {UNEXPECTED_WIN_HP_GAP_PP:g} points less enemy HP when both lose. The latter measures net HP depletion, not cumulative damage. Exactly {UNEXPECTED_WIN_HP_GAP_PP:g} does not qualify. Lower-ranked draws do not qualify. Obvious anomalies already dismissed by the conservative review remain excluded.", ""]
    for heading, key, peer_heading in (
            (f'Top {highlights["limit"]} upward surprises', "topUpward", "Higher-ranked variants outperformed"),
            (f'Top {highlights["limit"]} downward surprises', "topDownward", "Lower-ranked variants that outperformed it")):
        lines += ["", "## " + heading, "", f"| Camel / unit variant | Opponent | Jumps | {peer_heading} |", "|---|---|---:|---|"]
        for row in highlights[key]:
            peers = "; ".join(f'#{p["rank"]} {p["label"]}' for p in row["peers"])
            lines.append(f'| #{row["rank"]} {row["label"]} | {row["opponent"]} | {row["jumpCount"]} | {peers} |')
    lines += ["", f'## Top {highlights["limit"]} rare wins', "", highlights["rarityRule"], "",
              f'{len(highlights["topRareWins"])} shown from {len(highlights["allRareWins"])} qualifying rare wins; do not fill unused slots with non-rare wins.', "",
              "| Camel / unit variant | Opponent | Other losses | Other draws | Other wins | Winning HP |", "|---|---|---:|---:|---:|---:|"]
    for row in highlights["topRareWins"]:
        lines.append(f'| {row["label"]} | {row["opponent"]} | {row["otherLosses"]} | {row["otherDraws"]} | {row["otherWins"]} | {row["winnerHpPercent"]:.1f}% |')
    lines += ["", "Each result is one recorded battle, not an estimated win probability. Tables combine the forms of better performance; full classifications, HP, peer comparisons and review reasons remain in `ranking.json`, `unexpected-performance.json` and `exception-review.json`."]
    return lines


def highlight_sources(result):
    """Safe, portable provenance and projected tables for the chat receipts."""
    common = dict(label="Recorded matchup archives",
                  files=[dict(label=Path(s["path"]).parent.name + "/run.json") for s in result["sources"]],
                  executedAt=result["createdAt"],
                  filters=[f'{result["opponentsPerVariant"]} common opponents per variant.',
                           "Current one-population-per-unit geometric cost policy.",
                           "Flaming Camel, Missionary, War Chariot barrage and unavailable self-match opponents excluded."],
                  caveats=["One recorded battle per cell does not establish repeatability.",
                           "Exception lists do not change overall ranking scores.",
                           "HP percentages use each surviving army's own starting HP. Lower enemy HP after a loss measures net depletion, not cumulative damage."])
    items = []
    h = result["highlights"]
    for key, title in (("topUpward", f'Top {h["limit"]} upward surprises'), ("topDownward", f'Top {h["limit"]} downward surprises'), ("topRareWins", f'Top {h["limit"]} rare wins')):
        source = copy.deepcopy(common)
        source["metricDefinitions"] = [dict(label="Selection", definition=h["rowDefinition"]),
            dict(label="Ordering", definition=h["rarityRule"] if key == "topRareWins" else h["ordering"])]
        if key != "topRareWins":
            source["metricDefinitions"].append(dict(label="Better performance", definition=result["rankingExceptionRule"]))
            source["caveats"].append(result["mechanicsReviewRule"])
        rows = []
        for row in h[key]:
            entry = dict(variant=row["label"], opponent=row["opponent"], overallRank=row["rank"])
            if key == "topRareWins":
                entry.update({k: row[k] for k in ("otherLosses", "otherDraws", "otherWins", "winnerHpPercent")})
            else:
                entry.update(jumps=row["jumpCount"], comparators="; ".join(f'#{p["rank"]} {p["label"]}' for p in row["peers"]))
            rows.append(entry)
        columns = [dict(field="variant", label="Variant"), dict(field="opponent", label="Opponent"), dict(field="overallRank", label="Overall rank")]
        columns += ([dict(field=k, label=label) for k, label in (("otherLosses", "Other losses"), ("otherDraws", "Other draws"), ("otherWins", "Other wins"), ("winnerHpPercent", "Winning HP (%)"))] if key == "topRareWins" else [dict(field="jumps", label="Distinct variants outperformed / underperformed"), dict(field="comparators", label="Compared variants")])
        item_id = {"topUpward": "upward-surprises", "topDownward": "downward-surprises", "topRareWins": "rare-wins"}[key]
        items.append(dict(id=item_id, title=title, queries=[dict(id=item_id + "-recorded-battles", source=source, rows=rows, columns=columns)]))
    return dict(schemaVersion=1, items=items)


def main(roots, require_current_all=False, line="knight"):
    """Read archives, establish a common benchmark, then score and select.

    Only local reports are written. Source archives and recorded outcomes stay
    intact; filtering, draw classification, and review decisions are separate.
    Use require_current_all for a final report so partial data cannot silently
    become the final ranking. Input assertions require Python without -O.
    """
    out = REPO / f"data/local/{line}-line-ranking"
    out.mkdir(parents=True, exist_ok=True)
    specs = source_specs(line)
    sources, missing, series = [], [], {}
    for spec in specs:
        folders = spec["folders"] + (spec.get("optionalOverrides", []) if require_current_all else [])
        paths = [next((root / f / "run.json" for root in roots if (root / f / "run.json").is_file()), None)
                 for f in folders]
        if not require_current_all:
            for folder in spec.get("optionalOverrides", []):
                override = next((root / folder / "run.json" for root in roots if (root / folder / "run.json").is_file()), None)
                if override is not None:
                    paths.append(override)
        if any(p is None for p in paths):
            missing.append(dict(**spec, missingFolders=[f for f, p in zip(folders, paths) if p is None]))
            continue
        rows = {}
        for path in paths:
            sources.append(dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            seen = set()
            for raw in read(path)["matchups"]:
                plan = raw["plan"]
                slug = plan["side3"]["slug"]
                assert slug not in seen, (path, slug)
                seen.add(slug)
                cap = raw["capture"]["capture"]
                owner = cap["winnerOwner"]
                assert owner in (None, 2, 3)
                hp = cap["winnerRemainingHpPercent"]
                assert math.isfinite(hp) and hp >= 0
                assert cap["startCounts"] == [plan[s]["count"] for s in ("side2", "side3")]
                expected_hp = 0 if owner is None else cap["winnerHp"] / cap["winnerStartingHp"] * 100
                assert math.isclose(hp, expected_hp, abs_tol=1e-7)
                expected_signed = hp if owner == 2 else -hp if owner == 3 else 0
                assert math.isclose(expected_signed, cap["signedRemainingHpPercent"], abs_tol=1e-7)
                # Later explicit correction sources replace only matching slugs.
                # Keep the authoritative per-cell path, as well as all source hashes.
                rows[slug] = dict(jobId=raw["jobId"], archive=str(path),
                    sourceKind=raw.get("sourceKind", "compact_recording_archive"),
                    metadataOnly=raw.get("metadataOnly", False),
                    opponent=plan["side3"]["label"], opponentCivilization=plan["side3"]["civ"],
                    recordedOutcome="W" if owner == 2 else "L" if owner == 3 else "D",
                    outcome=ranking_outcome(owner, hp),
                    closeFinishDraw=owner is not None and hp < DRAW_THRESHOLD_HP_PERCENT,
                    winnerHpPercent=hp, hpFraction=min(hp, 100) / 100,
                    hpCappedForScoring=hp > 100, counts=cap["startCounts"],
                    currentPolicyCounts=expected_counts(plan),
                    policy=plan["balance"]["comparisonPolicy"], gameVersion=cap["gameVersion"],
                    opponentRelics=plan["scenario"].get("opponentLithuanianRelics", 0),
                    golden=raw["capture"]["scenario"]["sourceGoldenSha256"],
                    bufferCount=raw["capture"]["scenario"].get("player4Count", 0))
        series[spec["key"]] = dict(label=spec["label"], rows=rows)

    assert len(series) > 1, "At least two complete variants are required"
    all_opponents = set.union(*(set(v["rows"]) for v in series.values()))
    included, excluded = [], []
    for slug in sorted(all_opponents):
        rows = [v["rows"].get(slug) for v in series.values()]
        reasons = []
        if slug in RANKING_EXCLUSIONS:
            reasons.append(f"{RANKING_EXCLUSIONS[slug]} excluded from rankings at the user's request")
        if any(r is None for r in rows):
            reasons.append("Not recorded for every included variant (including omitted self-match)")
        else:
            if any(not counts_match_current_policy(r["policy"], r["counts"], r["currentPolicyCounts"]) for r in rows):
                reasons.append("Recorded policy or counts are incompatible with the current one-pop-per-unit benchmark")
            for field in ("gameVersion", "opponentRelics", "golden", "bufferCount"):
                if len({r[field] for r in rows}) > 1:
                    reasons.append("Different " + field)
        if reasons:
            excluded.append(dict(opponent=slug, reasons=reasons))
        else:
            included.append(slug)
    assert included, "No comparable opponents"
    if require_current_all:
        total = 9 if line == "camel" else 17
        omitted_self = "imperial_camel_rider_hindustanis" if line == "camel" else "savar_persians"
        assert len(series) == total and not missing, f"All {total} current-policy archives are required"
        expected_opponents = 73 - len(RANKING_EXCLUSIONS)
        assert len(included) == expected_opponents, f"Expected exactly {expected_opponents} shared opponents after self-match and requested exclusions"
        assert {e["opponent"] for e in excluded} == {omitted_self, *RANKING_EXCLUSIONS}, excluded
    # Classify every variant first, then compute rarity on that adjusted matrix.
    # A higher-ranked draw qualifies for an outcome reversal below, but never
    # counts as a loss for this scoring bonus or the rare-win top-25 list.
    n = len(series)
    for slug in included:
        outcomes = Counter(v["rows"][slug]["outcome"] for v in series.values())
        for v in series.values():
            row = v["rows"][slug]
            lost_others = outcomes["L"] - (row["outcome"] == "L")
            row.update(otherLosses=lost_others,
                       rarityBonus=lost_others / (n - 1) if row["outcome"] == "W" else 0,
                       minorityWin=row["outcome"] == "W" and lost_others > (n - 1) / 2,
                       soleWin=row["outcome"] == "W" and outcomes["W"] == 1)
            row["points"] = match_score(row)

    def summarize(win_weight=2, rare_weight=1):
        table = []
        for key, v in series.items():
            rows = [v["rows"][s] for s in included]
            wins = [r for r in rows if r["outcome"] == "W"]
            draws = sum(r["outcome"] == "D" for r in rows)
            hp_component = sum(r["hpFraction"] * (1 if r["outcome"] == "W" else -1 if r["outcome"] == "L" else 0) for r in rows)
            rare_component = sum(r["rarityBonus"] for r in rows)
            points = sum(match_score(r, win_weight, rare_weight) for r in rows)
            table.append(dict(key=key, label=v["label"], wins=len(wins),
                losses=sum(r["outcome"] == "L" for r in rows), draws=draws,
                winsReclassifiedAsDraws=sum(r["closeFinishDraw"] and r["recordedOutcome"] == "W" for r in rows),
                lossesReclassifiedAsDraws=sum(r["closeFinishDraw"] and r["recordedOutcome"] == "L" for r in rows),
                total=len(rows), points=points, score100=100 * points / (len(rows) * (win_weight + 1 + rare_weight)),
                averageWinningHpPercent=mean(r["winnerHpPercent"] for r in wins) if wins else None,
                minorityWins=sum(r["minorityWin"] for r in rows), soleWins=sum(r["soleWin"] for r in rows),
                winPoints=win_weight * len(wins), drawPoints=DRAW_POINTS * draws,
                hpPoints=hp_component, rarityPoints=rare_weight * rare_component))
        table.sort(key=lambda v: (-v["points"], v["key"]))
        for v in table:
            v["rank"] = 1 + sum(x["points"] > v["points"] + 1e-9 for x in table)
        return table

    ranking = summarize()
    sensitivity = [dict(winWeight=w, rarityWeight=r, ranking=summarize(w, r))
                   for w in (1, 2, 3) for r in (.5, 1, 2)]
    for row in ranking:
        ranks = [next(v["rank"] for v in s["ranking"] if v["key"] == row["key"]) for s in sensitivity]
        row["weightSensitivityRankRange"] = [min(ranks), max(ranks)]
    result = dict(createdAt=datetime.now(timezone.utc).isoformat(),
        reproduction=dict(
            reportScriptSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            sourceManifestPath=str(SOURCE_MANIFEST),
            sourceManifestSha256=hashlib.sha256(SOURCE_MANIFEST.read_bytes()).hexdigest()),
        scope=f"All currently accessible recorded {line}-line variants; missing archives are not treated as losses",
        availableVariants=len(series), plannedVariants=len(specs), opponentsPerVariant=len(included),
        scoring=dict(win="2 + min(own HP remaining %, 100)/100 + other losses/(variants-1)",
                     loss="-min(opponent HP remaining %, 100)/100", draw=DRAW_POINTS,
                     drawThresholdHpPercent=DRAW_THRESHOLD_HP_PERCENT,
                     drawRule="Surviving side has strictly less than 10% of its starting army HP; exactly 10% remains a win/loss. Actual recorded draws also score as draws.",
                     rarityRule="Use ranking outcomes after the close-finish draw rule; draws are neither wins nor losses and receive no HP or rarity bonus.",
                     aggregate="Sum match points; display score = 25 * mean match points",
                     explanation="Winning is primary; preserve HP on wins, minimize opponent HP on defeats, reward wins that other variants lose."),
        caveats=["Single recorded battle per cell; these ranks describe this benchmark, not estimated win probabilities.",
                 "HP is normalized to the winning side's starting HP. Defeat HP belongs to the opponent.",
                 "A recorded win or loss with under 10% HP left on the surviving side is treated as a ranking draw. Original outcomes and HP remain in the evidence.",
                 f"{', '.join(RANKING_EXCLUSIONS.values())} are excluded from rankings at the user's request; all recorded outcomes are preserved.",
                 "Same opponent set is used for every ranked variant; unmatched rules/counts are excluded."],
        missingVariants=missing, excludedOpponents=excluded, includedOpponents=included,
        sources=sources, ranking=ranking, sensitivity=sensitivity, variants=series,
        rankingExceptionRule=f"Compare a lower-ranked variant with every strictly higher-ranked variant against the same opponent. Include a clear win versus a loss or draw; two clear wins with strictly more than {UNEXPECTED_WIN_HP_GAP_PP:g} percentage points extra own HP; or two clear losses with strictly more than {UNEXPECTED_WIN_HP_GAP_PP:g} percentage points less opponent HP remaining. Normalize each HP pool to its own starting HP. Exactly {UNEXPECTED_WIN_HP_GAP_PP:g} points does not qualify. Lower-ranked draws do not qualify. These descriptive comparisons never change ranking scores or rarity bonuses.",
        rankingExceptionHpGapThresholdPercentagePoints=UNEXPECTED_WIN_HP_GAP_PP,
        rankExceptions=ranking_exceptions(ranking, series, included))
    if any(row["metadataOnly"] for variant in series.values() for row in variant["rows"].values()):
        result["caveats"].append("Some unchanged Cavalier results are recovered from retained capture metadata. Their outcomes and count checks are available, but the original video/frame files have not been located on the connected disks; no replacement battle is inferred or required for ranking.")
    review_path = REPO / f"apps/video/ranking_reviews/{line}.json"
    mechanics_review = read(review_path) if review_path.exists() else None
    result["reproduction"]["reviewManifestSha256"] = (
        hashlib.sha256(review_path.read_bytes()).hexdigest() if review_path.exists() else None)
    # A changed reference database requires reviewing the reasoning again.
    if mechanics_review and mechanics_review.get("referenceDatabaseSha256"):
        database = REPO / "data/golden/aoe2_reference.db"
        if hashlib.sha256(database.read_bytes()).hexdigest() != mechanics_review["referenceDatabaseSha256"]:
            mechanics_review = None
    result["reproduction"]["reviewManifestApplied"] = mechanics_review is not None
    reviewed = review_ranking_exceptions(result["rankExceptions"], series, mechanics_review)
    result.update(reviewedRankExceptions=reviewed["retained"],
                  inconclusiveRankComparisons=reviewed["inconclusive"],
                  unreviewedRankComparisons=reviewed["unreviewed"],
                  mechanicsReviewRule="Retain unexpected results by default, including unique-ability and stat tradeoffs. Dismiss only documented obvious anomalies where the lower-ranked variant has no relevant advantage; lack of an explanation alone is insufficient. Dismissals affect strategic highlights only, not raw outcomes, HP, scores or rarity bonuses. Never declare randomness proven from one recording.")
    if line == "camel" and "turks" in series:
        baseline = series["turks"]["rows"]
        result["baselineComparison"] = {
            key: {
                "winsWhereBaselineLoses": [s for s in included if v["rows"][s]["outcome"] == "W" and baseline[s]["outcome"] == "L"],
                "lossesWhereBaselineWins": [s for s in included if v["rows"][s]["outcome"] == "L" and baseline[s]["outcome"] == "W"],
                "otherDifferences": [s for s in included if v["rows"][s]["outcome"] != baseline[s]["outcome"] and "D" in (v["rows"][s]["outcome"], baseline[s]["outcome"])],
            } for key, v in series.items()
        }
    result["highlights"] = performance_highlights(ranking, series, included, reviewed["retained"])
    (out / "ranking.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (out / "highlight-summary.json").write_text(json.dumps(result["highlights"], indent=2) + "\n", encoding="utf-8")
    (out / "highlight-sources.json").write_text(json.dumps(highlight_sources(result), indent=2) + "\n", encoding="utf-8")
    # Preserve the old wins-only export for consumers that use it as a win list.
    (out / "upsets.json").write_text(json.dumps([e for e in result["reviewedRankExceptions"] if e["outcome"] == "W"], indent=2) + "\n", encoding="utf-8")
    (out / "unexpected-performance.json").write_text(json.dumps(dict(
        rule=result["rankingExceptionRule"], cases=result["reviewedRankExceptions"],
        dismissed=result["inconclusiveRankComparisons"]), indent=2) + "\n", encoding="utf-8")
    (out / "exception-review.json").write_text(json.dumps(reviewed, indent=2) + "\n", encoding="utf-8")
    lines = [f"# Recorded {line}-line ranking", "", f"{len(series)} of {len(specs)} variants available; {len(included)} common comparable opponents each.", "",
             f"{', '.join(RANKING_EXCLUSIONS.values())} are excluded from all ranking metrics. War Chariot (Focus Fire) remains included. A variant's omitted self-match is excluded for every variant. The archived recordings and complete raw outcome tables are unchanged.", "",
             f"Win: 2 + surviving HP fraction + fraction of other variants that lost. Loss: minus opponent surviving HP fraction. Draw: {DRAW_POINTS} points. Score: 25 times average match points. Maximum: 100; losses can produce a negative score.", "",
             "If the surviving army has strictly less than 10% of its starting HP, treat the result as a draw regardless of which side survived. Exactly 10% stays a win/loss. Draws receive no HP or rarity bonus and do not count as losses when evaluating another variant's rare win.", "",
             "| Rank | Variant | W-L-D | Score | Mean HP in wins | Wins when most others lose | Sole wins |",
             "|---:|---|---:|---:|---:|---:|---:|"]
    for v in ranking:
        hp = f'{v["averageWinningHpPercent"]:.1f}%' if v["averageWinningHpPercent"] is not None else "n/a"
        lines.append(f'| {v["rank"]} | {v["label"]} | {v["wins"]}-{v["losses"]}-{v["draws"]} | {v["score100"]:.1f} | {hp} | {v["minorityWins"]} | {v["soleWins"]} |')
    lines += ["", "## Interpretation and source limits", "", *["- " + c for c in result["caveats"]]]
    lines += ["", "Wins when most others lose counts victories where more than half of the other variants lost; draws are not losses. Sole wins means no other variant won.", "",
              "## Weight sensitivity", "",
              "Recomputed with win weights 1, 2 and 3, and rarity weights 0.5, 1 and 2; HP weight stays at 1 and draws stay at 0.5 points. These nine combinations test scoring choices, not game randomness.", ""]
    for v in ranking:
        lo, hi = v["weightSensitivityRankRange"]
        lines.append(f'- {v["label"]}: rank {lo}' + (f' to {hi}.' if hi != lo else '.'))
    if missing:
        lines += ["", "Unavailable archived variants: " + "; ".join(v["label"] for v in missing) + "."]
    reproduction = ["", "## Reproduction", "", "`apps/video/report_knight_line_rankings.py` reads compact archive `run.json` metadata; `ranking.json` retains every cell, source hash, exact calculation and sensitivity run.", "", "Source indexes:", "", *["- " + s["path"] for s in sources], "", "Rerun: `python apps/video/report_knight_line_rankings.py --line " + line + " --archive-root <archive-directory> --require-current-all`."]
    lines += ["", f"Three editorial top-{HIGHLIGHT_LIMIT} lists: [Performance highlights](HIGHLIGHTS.md)."]
    (out / "RANKING.md").write_text("\n".join(lines + reproduction) + "\n", encoding="utf-8")
    (out / "HIGHLIGHTS.md").write_text("\n".join(highlight_markdown(result["highlights"], line) + reproduction) + "\n", encoding="utf-8")
    (out / "STALE.json").unlink(missing_ok=True)
    print(json.dumps({k:result[k] for k in ("availableVariants", "plannedVariants", "opponentsPerVariant", "excludedOpponents", "ranking")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", action="append", type=Path)
    parser.add_argument("--line", choices=("knight", "camel"), default="knight")
    parser.add_argument("--require-current-all", action="store_true", help="Require every current-policy variant and the full shared opponent set; knight rankings also require four-relic Leitis corrections")
    args = parser.parse_args()
    default_root = Path("E:/AoE2 Renders/knight-line-canonical" if args.line == "knight" else "D:/AoE2 Renders")
    main(args.archive_root or [default_root], args.require_current_all, args.line)

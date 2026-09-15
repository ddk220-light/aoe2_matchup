"""Compare independent old/new captures, including cross-civilization patterns."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/local/champi-geometric-comparison"
CIVS = ["Incas", "Mapuche", "Muisca", "Tupi"]


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def save(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_suffix(".partial.json")
    temp.write_text(json.dumps(v, indent=2) + "\n", encoding="utf-8")
    temp.replace(p)


def outcome(c):
    # Recorded ownership, never infer the winner from a positive HP remainder.
    return (
        "win" if c["winnerOwner"] == 2 else "loss" if c["winnerOwner"] == 3 else "other"
    )


def compare(baseline, new_capture, new_plan):
    old = baseline["capture"]
    old_result = outcome(old)
    new_result = outcome(new_capture) if new_capture else None
    new_counts = [new_plan[s]["count"] for s in ("side2", "side3")]
    if new_capture and new_capture["startCounts"] != new_counts:
        raise ValueError("Capture starting counts differ from approved plan")
    return dict(
        jobId=baseline["newJobId"],
        oldJobId=baseline["oldJobId"],
        civ=new_plan["side2"]["civ"],
        opponent=new_plan["side3"]["slug"],
        opponentLabel=new_plan["side3"]["civ"] + " " + new_plan["side3"]["label"],
        oldCounts=old["startCounts"],
        newCounts=new_counts,
        countsChanged=old["startCounts"] != new_counts,
        oldResult=old_result,
        newResult=new_result,
        flipped=None if new_result is None else old_result != new_result,
        oldWinnerHpPercent=old["winnerRemainingHpPercent"],
        newWinnerHpPercent=(
            new_capture["winnerRemainingHpPercent"] if new_capture else None
        ),
        oldSurvivors=old["survivors"],
        newSurvivors=new_capture["survivors"] if new_capture else None,
        comparison=[new_plan[s]["comparison"] for s in ("side2", "side3")],
    )


def group_pattern(rows):
    by = {r["civ"]: r for r in rows}
    old = [c for c in CIVS if by[c]["oldResult"] == "win"]
    complete = all(by[c]["newResult"] is not None for c in CIVS)
    new = [c for c in CIVS if by[c]["newResult"] == "win"] if complete else None
    contrasts = []
    if complete:
        for c in CIVS[1:]:
            before = [by[x]["oldResult"] for x in ("Incas", c)]
            after = [by[x]["newResult"] for x in ("Incas", c)]
            contrasts.append(
                dict(
                    otherCiv=c,
                    before=before,
                    after=after,
                    changed=before != after,
                    incaOnlyWinLost=before == ["win", "loss"] and after != before,
                    incaOnlyWinGained=after == ["win", "loss"] and before != after,
                )
            )
    return dict(
        opponent=rows[0]["opponent"],
        opponentLabel=rows[0]["opponentLabel"],
        oldWinningCivs=old,
        newWinningCivs=new,
        complete=complete,
        patternChanged=None if not complete else old != new,
        allWinsToAllLosses=complete and len(old) == 4 and not new,
        incaSoleWinLost=complete and old == ["Incas"] and "Incas" not in new,
        contrasts=contrasts,
    )


def main():
    baseline = read(OUT / "baseline.json")["jobs"]
    status = (
        read(OUT / "capture/status.json")
        if (OUT / "capture/status.json").exists()
        else {}
    )
    verified = {
        r["jobId"]: r for r in status.get("results", []) if r["status"] == "verified"
    }
    rows = []
    for b in baseline:
        p = read(OUT / "plans" / f"{b['newJobId']}.json")
        row = verified.get(b["newJobId"])
        capture = (
            read(Path(row["runDirectory"]) / "manifest.json")["capture"]
            if row
            else None
        )
        rows.append(compare(b, capture, p))
    groups = [
        group_pattern([r for r in rows if r["opponent"] == slug])
        for slug in dict.fromkeys(r["opponent"] for r in rows)
    ]
    summary = dict(
        completed=len(verified),
        total=len(rows),
        flips=sum(r["flipped"] is True for r in rows),
        unchangedCountFlips=sum(
            r["flipped"] is True and not r["countsChanged"] for r in rows
        ),
        completedOpponentGroups=sum(g["complete"] for g in groups),
        changedPatterns=sum(g["patternChanged"] is True for g in groups),
        allWinsToAllLosses=sum(g["allWinsToAllLosses"] for g in groups),
        incaSoleWinLost=sum(g["incaSoleWinLost"] for g in groups),
    )
    save(OUT / "comparison.json", dict(summary=summary, jobs=rows, opponents=groups))
    lines = [
        "# Champi: original versus geometric benchmark",
        "",
        f"Completed {summary['completed']}/{summary['total']}; winner changes: {summary['flips']}; completed opponent groups: {summary['completedOpponentGroups']}/74.",
        "",
        "Each result is one recorded battle. Differences with identical counts are rerun variation, not a count-policy effect; differences with changed counts are observed changes, not isolated causal proof. No engine simulations are included. HP is the winner’s remaining army HP divided by its starting total.",
        "",
        "## Changes across civilizations",
        "",
        "| Opponent | Previous Champi winners | New Champi winners | All wins to losses | Incas sole win lost |",
        "|---|---|---|---|---|",
    ]
    for g in groups:
        lines.append(
            f"| {g['opponentLabel']} | {', '.join(g['oldWinningCivs']) or 'None'} | {('Pending' if g['newWinningCivs'] is None else ', '.join(g['newWinningCivs']) or 'None')} | {g['allWinsToAllLosses']} | {g['incaSoleWinLost']} |"
        )
    lines += [
        "",
        "## Individual recordings",
        "",
        "Counts are Champi : opponent. A flip means the Champi result changed.",
        "",
        "| Civ | Opponent | Old counts | New counts | Old result | New result | Flip | Old winner HP | New winner HP |",
        "|---|---|---:|---:|---|---|---|---:|---:|",
    ]
    for r in rows:
        hp = (
            "Pending"
            if r["newWinnerHpPercent"] is None
            else f"{r['newWinnerHpPercent']:.1f}%"
        )
        lines.append(
            f"| {r['civ']} | {r['opponentLabel']} | {r['oldCounts'][0]} : {r['oldCounts'][1]} | {r['newCounts'][0]} : {r['newCounts'][1]} | {r['oldResult']} | {r['newResult'] or 'Pending'} | {r['flipped']} | {r['oldWinnerHpPercent']:.1f}% | {hp} |"
        )
    (OUT / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()

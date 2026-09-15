"""Create a separate 296-game benchmark campaign, freezing the old results."""

import copy
import hashlib
import json
from pathlib import Path
from aoe2x.lab.config import load_config
from aoe2x.lab.cli import _load_batch
from aoe2x.lab.planner import plan_matchup
from aoe2x.lab.costs import validate_plan_costs

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "data/local/champi-standard-comparison"
OUT = ROOT / "data/local/champi-geometric-comparison"


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def save(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(v, indent=2) + "\n"
    if p.exists() and p.read_text() != text:
        raise ValueError(f"Refusing to rewrite frozen campaign evidence: {p}")
    p.write_text(text, encoding="utf-8")


def main():
    old = read(OLD / "manifest.json")["matchups"]
    baseline = {
        r["jobId"]: r
        for r in read(OLD / "capture/status.json")["results"]
        if r["status"] == "verified"
    }
    assert len(old) == len(baseline) == 296
    rows = []
    snapshots = []
    for row in old:
        new = copy.deepcopy(row)
        new["id"] = row["id"].replace("champi_standard_", "champi_geometric_")
        new["balance"]["mode"] = "geometric_shared_discount"
        rows.append(new)
        run = Path(baseline[row["id"]]["runDirectory"])
        plan = read(run.parents[1] / "plan.json")
        capture = read(run / "manifest.json")["capture"]
        assert capture["startCounts"] == [plan[s]["count"] for s in ("side2", "side3")]
        snapshots.append(
            dict(
                oldJobId=row["id"],
                newJobId=new["id"],
                plan=plan,
                capture=capture,
                oldRunDirectory=str(run),
                oldManifestSha256=hashlib.sha256(
                    (run / "manifest.json").read_bytes()
                ).hexdigest(),
            )
        )
    # Four civilizations per opponent: the cross-civ comparison fills continuously.
    civs = ["Incas", "Mapuche", "Muisca", "Tupi"]
    opponent_order = {r["side3"]: i for i, r in enumerate(old) if r["civ2"] == "Incas"}
    rows.sort(key=lambda r: (opponent_order[r["side3"]], civs.index(r["civ2"])))
    save(OUT / "manifest.json", dict(schemaVersion=1, matchups=rows))
    save(OUT / "baseline.json", dict(source=str(OLD), jobs=snapshots))
    _, requests = _load_batch(OUT / "manifest.json")
    cfg = load_config()
    evidence = []
    for request in requests:
        plan = plan_matchup(cfg, request)
        validate_plan_costs(plan)
        save(OUT / "plans" / f"{plan['jobId']}.json", plan)
        base = next(b for b in snapshots if b["newJobId"] == plan["jobId"])
        assert plan["scenario"] == base["plan"]["scenario"]
        evidence.append(
            dict(
                jobId=plan["jobId"],
                civ=plan["side2"]["civ"],
                opponent=plan["side3"]["slug"],
                oldCounts=base["capture"]["startCounts"],
                newCounts=[plan[s]["count"] for s in ("side2", "side3")],
                comparison=[plan[s]["comparison"] for s in ("side2", "side3")],
            )
        )
    save(
        OUT / "preflight.json",
        dict(
            state="PASSED",
            total=len(evidence),
            jobs=evidence,
            policy="Geometric mean; half food/wood discounts for shared units; full gold discounts; nearest integer halves up; full HP; original Golden/P4 conditions preserved.",
        ),
    )
    print(
        json.dumps(
            {
                "prepared": len(evidence),
                "changedCounts": sum(
                    r["oldCounts"] != r["newCounts"] for r in evidence
                ),
                "monaspa": [r for r in evidence if "monaspa" in r["opponent"]],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

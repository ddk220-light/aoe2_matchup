"""``status``: progress, rate, ETA and blocked contexts of a run, read from its records only."""
from __future__ import annotations

import statistics
from datetime import datetime
from pathlib import Path

from aoe2x.matchups import journal as J


def _ts(text: str | None):
    if not text:
        return None
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


def report(records: Path) -> dict:
    R = Path(records)
    state = J.read_json(R / "state.json", {}) or {}
    runs = J.read_journal(R / "runs.jsonl") if (R / "runs.jsonl").exists() else []
    attempts = J.read_journal(R / "attempts.jsonl") if (R / "attempts.jsonl").exists() else []
    sessions = J.read_journal(R / "sessions.jsonl") if (R / "sessions.jsonl").exists() else []
    lock = J.RunnerLock(R / ".runner.lock")
    owner = lock.read()
    alive = lock.owner_alive(owner)
    walls = [r["wallSeconds"] for r in runs]
    contexts = state.get("contexts") or {}
    per_context = {}
    for r in runs:
        per_context[r["matchupId"]] = per_context.get(r["matchupId"], 0) + 1
    reviewed = contexts.get("reviewed") or 0
    seeds_per_context = (sum(per_context.values()) / len(per_context)) if per_context else None
    # rate: seeds finished per wall-clock hour while a runner was running (session windows)
    starts = [_ts(s["at"]) for s in sessions if s.get("event") == "start"]
    finished = sorted(t for t in (_ts(r.get("finishedAt")) for r in runs) if t)
    active_seconds, counted = 0.0, 0
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else None
        inside = [t for t in finished if t >= start and (end is None or t < end)]
        if inside:
            active_seconds += inside[-1] - start
            counted += len(inside)
    rate = counted / active_seconds * 3600 if active_seconds > 60 else None
    remaining = contexts.get("remaining")
    workers = state.get("workers") or 1
    est_seeds = remaining * seeds_per_context if remaining is not None and seeds_per_context else None
    eta = {}
    if est_seeds is not None:
        if rate:
            eta["fromObservedRateHours"] = round(est_seeds / rate, 2)
        if walls:
            eta["fromMeanWallHours"] = round(est_seeds * statistics.fmean(walls) / workers / 3600, 2)
    blocked = {}
    for a in attempts:
        if a.get("unblocked"):
            blocked.pop(a["matchupId"], None)
            continue
        b = blocked.setdefault(a["matchupId"], {"jobId": a["matchupId"], "attempts": [], "exhausted": False})
        b["attempts"].append({k: a.get(k) for k in ("seed", "attempt", "limitSeconds", "wallSeconds", "watchdog",
                                                    "exhausted", "lastProgress")} |
                             {"error": (a.get("error") or {}).get("name")})
        b["exhausted"] = b["exhausted"] or bool(a.get("exhausted"))
    reviewed_ids = {x.stem for x in (R / "pair-reviews").glob("*.json")} if (R / "pair-reviews").exists() else set()
    supervisor = J.read_json(R / "supervisor.json")
    return {
        "records": str(R), "runId": state.get("runId"), "status": state.get("status"),
        "runnerAlive": alive, "runnerPid": owner.get("pid") if alive and owner else None,
        "staleLock": bool(owner) and not alive,
        "updatedAt": state.get("updatedAt"), "engineId": state.get("engineId"), "nodeVersion": state.get("nodeVersion"),
        "samplingPolicy": state.get("samplingPolicy"), "workers": state.get("workers"),
        "contexts": contexts, "seedsSaved": len(runs), "failedAttempts": len(attempts),
        "evidenceLevels": state.get("evidenceLevels"), "outcomes": state.get("outcomes"),
        "seedsPerReviewedContext": round(seeds_per_context, 3) if seeds_per_context else None,
        "wallSeconds": {"sum": round(sum(walls), 1), "mean": round(statistics.fmean(walls), 2),
                        "median": round(statistics.median(walls), 2), "max": round(max(walls), 1)} if walls else None,
        "seedsPerHour": round(rate, 1) if rate else None,
        "estimatedRemainingSeeds": round(est_seeds) if est_seeds is not None else None, "eta": eta or None,
        "blocked": [b for b in blocked.values() if b["exhausted"]],
        "retrying": [b for b in blocked.values() if not b["exhausted"] and b["jobId"] not in reviewed_ids],
        "recoveredAfterTimeouts": sum(1 for b in blocked.values() if not b["exhausted"] and b["jobId"] in reviewed_ids),
        "active": state.get("active"), "sessions": sum(s.get("event") == "start" for s in sessions),
        "supervisor": {k: supervisor.get(k) for k in ("status", "pid", "heartbeatAt", "restarts", "lastExit")}
        if supervisor else None,
        "reviewedContexts": reviewed,
    }


def render(r: dict) -> str:
    c = r["contexts"] or {}
    lines = [f"run {r['runId']}  status {r['status']}  runner {'alive pid ' + str(r['runnerPid']) if r['runnerAlive'] else 'not running'}"
             + ("  (stale lock: clear with `unlock`)" if r["staleLock"] else ""),
             f"records {r['records']}  engine {r['engineId']}  node {r['nodeVersion']}  policy {r['samplingPolicy']}  workers {r['workers']}",
             f"contexts {c.get('complete', 0)}/{c.get('total', 0)} complete ({c.get('reviewed', 0)} run, {c.get('reused', 0)} reused), "
             f"{c.get('blocked', 0)} blocked, {c.get('remaining', 0)} remaining, {c.get('active', 0)} active",
             f"seeds saved {r['seedsSaved']}  failed attempts {r['failedAttempts']}  seeds/context {r['seedsPerReviewedContext']}",
             f"outcomes {r['outcomes']}  evidence {r['evidenceLevels']}"]
    if r["wallSeconds"]:
        w = r["wallSeconds"]
        lines.append(f"wall per seed: mean {w['mean']} s, median {w['median']} s, max {w['max']} s; "
                     f"rate {r['seedsPerHour']} seeds/h")
    if r["eta"]:
        lines.append(f"ETA ~{r['estimatedRemainingSeeds']} seeds: " +
                     ", ".join(f"{k} {v} h" for k, v in r["eta"].items()))
    for b in r["blocked"]:
        last = b["attempts"][-1]
        lines.append(f"BLOCKED {b['jobId']} seed {last['seed']}: {len(b['attempts'])} attempts, last "
                     f"{'watchdog' if last['watchdog'] else last['error']} at {last['limitSeconds']} s, "
                     f"lastProgress {last['lastProgress']}")
    if r["recoveredAfterTimeouts"]:
        lines.append(f"{r['recoveredAfterTimeouts']} context(s) finished after failed attempts")
    for b in r["retrying"]:
        lines.append(f"retrying {b['jobId']}: {len(b['attempts'])} failed attempt(s) so far")
    if r["supervisor"]:
        s = r["supervisor"]
        lines.append(f"supervisor {s['status']} pid {s['pid']} heartbeat {s['heartbeatAt']} restarts {s['restarts']}")
    return "\n".join(lines)

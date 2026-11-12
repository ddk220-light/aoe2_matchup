"""``run``: execute a run config's inventory on its pinned engine, resumably.

Generalises the 2026 runners (RB = ``origin/simulations/civ-forecast-recovery-2026-11-10``,
``CM`` = ``aoe2x/js_simulation/node/civ-matchups``): ``CM/run-forecast-validation.mjs``
(locks, ``runs.jsonl``/``attempts.jsonl`` journals, watchdog escalation, pair
reviews, phase reviews, ``state.json``), ``CM/run-mismatch-validation.mjs`` and
``CM/run-adaptive.mjs`` (3 -> 10 sampling), ``CM/rolling-validation-queue.mjs``
(keep every worker busy across phase boundaries). Everything that was a
hard-coded campaign constant comes from the run config; there are no git
commits, pushes, approval files or amendment files.

Process layout::

    python -m aoe2x.matchups run <config>          (this module; holds <records>/.runner.lock)
      └─ node run-battles.mjs --serve              (one attempt per request; BattleWorkerPool)
           └─ battle-worker.mjs x N                (pinned engine, tick cap lifted)

Records (``<records>`` = ``output.records``, outside the repo by default)::

    inventory/jobs.jsonl.gz       contexts (the ``inventory`` command; built here if missing)
    runs.jsonl                    one line per completed seed (fsynced before anything else)
    attempts.jsonl                one line per failed attempt (timeout / crash / error)
    pair-reviews/<jobId>.json     one review per finished context
    reviews/NNN.json              phase reviews (``execution.phaseContexts`` contexts each)
    reuse.json                    contexts not run because the baseline index has their result
    state.json                    counts and status (atomic rewrite)
    sessions.jsonl                one line per runner start / end
    progress/                     diagnostic snapshots (never results)
    logs/runner.log               Node stderr and runner events

Safety rules kept from 2026: a completed seed is never re-run and a duplicate
seed line is an integrity error; a timeout or crash is never a result; a seed
gets one attempt per ``engine.wallTimeoutSteps`` step and after the last one
its context is ``blocked`` (kept in ``state.json`` and ``status``, never
retried unless ``run --retry-blocked`` is given); the runner refuses changed
engine files, an unverified Node version (per policy) and experiment variables.
Work order is the inventory order (sorted ``pairKey``) and every decision is a
pure function of the journals, so a run killed at any point and restarted
finishes with exactly the journal an uninterrupted run would have written
(apart from timestamps and wall times).
"""
from __future__ import annotations

import gzip
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from collections import Counter
from pathlib import Path

from aoe2x.matchups import journal as J
from aoe2x.matchups.canonical import digest, sha256_bytes
from aoe2x.matchups.sampling import MULTI, SINGLE, Policy, winner_hp_fraction

REVIEW_SCHEMA = "aoe2-matchup-review/v1"
STATE_SCHEMA = "aoe2-matchup-run-state/v1"
VOLATILE = ("startedAt", "finishedAt", "wallSeconds", "attempt", "limitSeconds")
EXIT_DONE, EXIT_FAILED, EXIT_INTEGRITY, EXIT_LOCKED, EXIT_STOPPED = 0, 1, 2, 75, 143
PYTHON_WATCHDOG_GRACE = 120.0  # seconds beyond the Node watchdog before the backend is presumed hung


class RunError(RuntimeError):
    exit_code = EXIT_INTEGRITY


# ------------------------------------------------------------------ backends

class NodeBackend:
    """``node run-battles.mjs --serve``: one attempt per request, replies on a queue."""

    def __init__(self, *, engine_dir: Path, node: str, workers: int, node_policy: str, environment: dict,
                 max_old_space_mb: int | None, log_path: Path):
        self.args = dict(engine_dir=engine_dir, node=node, workers=workers, node_policy=node_policy,
                         environment=environment, max_old_space_mb=max_old_space_mb)
        self.log_path = Path(log_path)
        self.replies: queue.Queue = queue.Queue()
        self.proc = None
        self.hello = None

    def start(self, timeout: float = 120.0) -> dict:
        from aoe2x.matchups.paths import NODE_DIR
        a = self.args
        cmd = [a["node"]]
        if a["max_old_space_mb"]:
            cmd.append(f"--max-old-space-size={a['max_old_space_mb']}")
        cmd += [str(NODE_DIR / "run-battles.mjs"), "--serve", "--engine", str(a["engine_dir"]),
                "--workers", str(a["workers"]), "--node-policy", a["node_policy"],
                "--environment", json.dumps(a["environment"])]
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log = open(self.log_path, "ab")
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOE2X_EXP_")}
        env.update(a["environment"])
        self.replies = queue.Queue()
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._log, env=env,
                                     bufsize=0)
        threading.Thread(target=self._read, args=(self.proc, self.replies), daemon=True).start()
        try:
            first = self.replies.get(timeout=timeout)
        except queue.Empty:
            self.stop()
            raise RunError(f"Node backend did not start within {timeout:.0f}s (see {self.log_path})")
        if "hello" not in first:
            self.stop()
            raise RunError(f"Node backend refused to start: {first} (see {self.log_path})")
        self.hello = first["hello"]
        return self.hello

    @staticmethod
    def _read(proc, replies):
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                replies.put(json.loads(line))
            except ValueError:
                replies.put({"fatal": f"unparsable backend line {line[:200]!r}"})
        replies.put({"backendExit": proc.wait()})

    def submit(self, request: dict) -> None:
        self.proc.stdin.write((json.dumps(request, separators=(",", ":")) + "\n").encode())
        self.proc.stdin.flush()

    def get(self, timeout: float):
        try:
            return self.replies.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self) -> None:
        if not self.proc:
            return
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self.proc = None
        self._log.close()

    def kill(self) -> None:
        if self.proc:
            self.proc.kill()
            self.proc.wait()
            self.proc = None
            self._log.close()


# ------------------------------------------------------------------ the run

def payload(job: dict, seed: int, variants: dict, scenarios, battle: dict) -> dict:
    """``payload(job, seed)`` of RB ``CM/forecast-validation-lib.mjs``, battle flags from the config."""
    teams = []
    for i, key in enumerate(job["teamKeys"]):
        v = variants[key]
        if v["profileHash"] != job["profileHashes"][i]:
            raise RunError(f"{job['id']}: {key} does not have profile {job['profileHashes'][i]}")
        teams.append({"mechanics": v["mechanics"], "count": job["counts"][i]})
    scenario_hash, scenario = scenarios.resolve(job["family"], job["engineFamily"])
    if scenario_hash != job["scenarioHash"]:
        raise RunError(f"{job['id']}: scenario {scenario_hash} is not the job's {job['scenarioHash']}")
    return {"jobId": job["id"], "seed": seed, "teams": teams, "scenario": scenario,
            "disableAiOrders": battle["disableAiOrders"], "disableKiting": battle["disableKiting"],
            "preserveOwnerOrientation": battle["preserveOwnerOrientation"], "retainSnapshots": False}


def content(row: dict) -> dict:
    """A journal row without the fields that depend on timing (for comparisons and exports)."""
    return {k: v for k, v in row.items() if k not in VOLATILE}


def load_index(ref: dict) -> list[dict]:
    from aoe2x.matchups.config import ConfigError, resolve_path
    from aoe2x.matchups.paths import REPO_ROOT
    path = resolve_path(ref["index"], REPO_ROOT)
    if not path.exists():
        raise ConfigError(f"result index {path} is missing; build it with `python -m aoe2x.matchups import-results`")
    raw = path.read_bytes()
    if sha256_bytes(raw) != ref["sha256"]:
        raise ConfigError(f"{path} has sha256 {sha256_bytes(raw)}, config expects {ref['sha256']}")
    return [json.loads(line) for line in gzip.decompress(raw).decode().splitlines() if line.strip()]


def load_priors(ref: dict) -> dict:
    from aoe2x.matchups.config import ConfigError, resolve_path
    from aoe2x.matchups.paths import REPO_ROOT
    path = resolve_path(ref["file"], REPO_ROOT)
    raw = path.read_bytes()
    if sha256_bytes(raw) != ref["sha256"]:
        raise ConfigError(f"{path} has sha256 {sha256_bytes(raw)}, config expects {ref['sha256']}")
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
    out = {}
    for line in raw.decode().splitlines():
        if line.strip():
            r = json.loads(line)
            out[r.get("contextHash") or r["pairKey"]] = {"outcomes": list(r["outcomes"]), "source": r.get("source")}
    return out


class Run:
    """All inputs of one run, resolved and verified (no records touched)."""

    def __init__(self, cfg: dict, *, records: Path | None = None, force: bool = False):
        from aoe2x.matchups import config as C
        from aoe2x.matchups.bundle import Scenarios
        from aoe2x.matchups.cli import load_inputs
        self.cfg = cfg
        self.records = Path(records) if records else C.records_dir(cfg)
        self.run_hash = C.run_hash(cfg)
        self.config_hash = C.config_hash(cfg)
        self.policy = Policy(cfg["sampling"])
        self.sampling_hash = digest(cfg["sampling"])
        self.inputs = load_inputs(cfg)
        self.engine = self.inputs["engine"]
        self.variants = {v["key"]: v for v in self.inputs["bundle"]["variants"]}
        self.scenarios = Scenarios(self.inputs["scenarioSet"])
        self.steps = list(cfg["engine"]["wallTimeoutSteps"])
        self.force = force or bool(cfg["selection"].get("rerunReusable"))
        self.jobs = None
        self.index_sha256 = None
        self.reusable, self.index_by_context = {}, {}
        ref = cfg["selection"].get("baselineResults")
        if ref:
            self.index_sha256 = ref["sha256"]
            for row in load_index(ref):
                if row.get("context") is not None and row.get("evidenceType") != "identity":
                    self.index_by_context[row["contextHash"]] = row
                if row.get("reusable") and row.get("resultKey"):
                    self.reusable[row["resultKey"]] = row
        source = cfg["sampling"]["forecastSource"]
        self.priors_file = load_priors(cfg["sampling"]["priors"]) if source == "priors-file" else {}

    def prepare(self, build: bool = True) -> "Run":
        """Load (and, under the runner lock, build if missing) the inventory jobs."""
        if self.jobs is None:
            self.jobs, self.inventory_sha256 = self._inventory(build)
            self.by_id = {j["id"]: j for j in self.jobs}
            if len(self.by_id) != len(self.jobs):
                raise RunError("duplicate job ids in the inventory")
        return self

    def _inventory(self, build: bool) -> tuple[list, str]:
        from aoe2x.matchups import inventory as I
        from aoe2x.matchups.cli import _header
        directory = self.records / "inventory"
        header = _header(self.cfg, self.inputs)
        summary_path, jobs_path = directory / "inventory-summary.json", directory / "jobs.jsonl.gz"
        if not jobs_path.exists():
            if not build:
                raise RunError(f"{jobs_path} is missing; run `python -m aoe2x.matchups inventory <config>`")
            result = I.build(self.cfg, self.inputs["bundle"], self.inputs["scenarioSet"], self.inputs["orientation"],
                             self.inputs["setupHash"])
            I.write(result, directory, header)
        summary = json.loads(summary_path.read_text())
        for field in ("bundleHash", "setupHash", "selectionHash", "orientationTableHash", "scenarioSetHash", "engineId"):
            if summary.get(field) != header[field]:
                raise RunError(f"{directory} was built for a different {field} "
                               f"({summary.get(field)} vs {header[field]}); rebuild it with `inventory {self.cfg['runId']}`")
        raw = jobs_path.read_bytes()
        if sha256_bytes(raw) != summary["files"]["jobs.jsonl.gz"]["sha256"]:
            raise RunError(f"{jobs_path} does not match inventory-summary.json")
        jobs = [json.loads(line) for line in gzip.decompress(raw).decode().splitlines() if line.strip()]
        for j in jobs:
            if j.get("resultKey") != digest({"contextHash": j["contextHash"], "setupHash": self.inputs["setupHash"]}):
                raise RunError(f"{j['id']}: resultKey does not match the setup")
        return jobs, sha256_bytes(raw)

    def prior(self, job: dict):
        """Prior outcomes for the one-seed shortcut, or None (never a guess)."""
        source = self.cfg["sampling"]["forecastSource"]
        if source == "baseline-outcome":
            row = self.index_by_context.get(job["contextHash"])
            if row and row.get("outcome") in ("a_win", "b_win", "close_uncertain"):
                return [row["outcome"]], f"baseline:{row.get('source')}"
        elif source == "priors-file":
            hit = self.priors_file.get(job["contextHash"]) or self.priors_file.get(job["pairKey"])
            if hit and hit["outcomes"]:
                return hit["outcomes"], hit["source"] or "priors-file"
        return None, None

    def payload(self, job: dict, seed: int) -> dict:
        return payload(job, seed, self.variants, self.scenarios, self.cfg["battle"])


class Runner:
    def __init__(self, run: Run, *, backend_factory=None, workers: int | None = None, node: str | None = None,
                 retry_blocked: bool = False, log=None, max_backend_restarts: int = 20):
        self.run = run
        self.cfg = run.cfg
        self.R = run.records
        self.workers = workers or self.cfg["execution"]["workers"]
        self.node = node
        self.retry_blocked = retry_blocked
        self.backend_factory = backend_factory or self._node_backend
        self.log = log or (lambda msg: print(msg, file=sys.stderr, flush=True))
        self.max_backend_restarts = max_backend_restarts
        self.stopping = False
        self.stop_reason = None
        self.session_seeds = 0
        self.backend = None
        self.node_version = None

    # ---------------------------------------------------------------- setup
    def _node_backend(self):
        from aoe2x.matchups.engine import engine_dir, find_node
        e = self.cfg["engine"]
        return NodeBackend(engine_dir=engine_dir(e["id"]), node=find_node(self.node), workers=self.workers,
                           node_policy=e["nodeVersionPolicy"], environment=e["environment"],
                           max_old_space_mb=self.cfg["execution"]["maxOldSpaceMb"],
                           log_path=self.R / "logs" / "runner.log")

    def _load_records(self) -> None:
        R, run = self.R, self.run
        self.repair = J.repair_journal(R / "runs.jsonl")
        if self.repair["repaired"]:
            self.log(f"journal repaired: {self.repair['reason']}, dropped {self.repair['droppedBytes']} bytes")
        attempts_repair = J.repair_journal(R / "attempts.jsonl")
        self.rows: dict[str, list] = {}
        seen = set()
        for r in J.read_journal(R / "runs.jsonl"):
            if r.get("campaignHash") != run.run_hash:
                raise RunError(f"runs.jsonl has a line of another run ({r.get('campaignHash')}); "
                               f"this config is {run.run_hash}. Use a new records directory.")
            job = run.by_id.get(r["matchupId"])
            if job is None:
                raise RunError(f"runs.jsonl names unknown context {r['matchupId']}")
            for f in ("pairKey", "contextHash", "profileHashes", "counts", "scenarioHash"):
                if r[f] != job[f]:
                    raise RunError(f"runs.jsonl {r['matchupId']} seed {r['seed']}: {f} differs from the inventory")
            if r["outcome"] not in ("win", "loss", "draw") or not r.get("finalStateHash") or not r.get("eventLogHash"):
                raise RunError(f"runs.jsonl {r['matchupId']} seed {r['seed']}: not a completed result")
            key = (r["matchupId"], r["seed"])
            if key in seen:
                raise RunError(f"duplicate seed line {key}")
            seen.add(key)
            self.rows.setdefault(r["matchupId"], []).append(r)
        self.saved = len(seen)
        # attempts: failures per (context, seed) since the last unblock of the context
        self.failures: Counter = Counter()
        self.blocked: dict[str, dict] = {}
        self.attempt_lines = 0
        for a in J.read_journal(R / "attempts.jsonl"):
            self.attempt_lines += 1
            if a.get("campaignHash") != run.run_hash:
                raise RunError("attempts.jsonl has a line of another run")
            jid = a["matchupId"]
            if a.get("unblocked"):
                for k in [k for k in self.failures if k[0] == jid]:
                    del self.failures[k]
                self.blocked.pop(jid, None)
                continue
            self.failures[(jid, a["seed"])] += 1
            if a.get("exhausted"):
                self.blocked[jid] = {"jobId": jid, "seed": a["seed"], "attempts": self.failures[(jid, a["seed"])],
                                     "lastError": a.get("error"), "lastProgress": a.get("lastProgress"),
                                     "watchdog": a.get("watchdog"), "at": a.get("finishedAt")}
        self.attempts = J.Journal(R / "attempts.jsonl")
        if attempts_repair["repaired"]:
            self.log(f"attempts log repaired: {attempts_repair['reason']}")
        if self.retry_blocked and self.blocked:
            for jid in sorted(self.blocked):
                self.attempts.append({"campaignHash": run.run_hash, "matchupId": jid, "unblocked": True, "at": J.now(),
                                      "reason": "run --retry-blocked"})
                for k in [k for k in self.failures if k[0] == jid]:
                    del self.failures[k]
            self.log(f"retrying {len(self.blocked)} blocked context(s)")
            self.blocked = {}
        # reviews
        (R / "pair-reviews").mkdir(parents=True, exist_ok=True)
        self.reviews: dict[str, dict] = {}
        for path in sorted((R / "pair-reviews").glob("*.json")):
            review = json.loads(path.read_text())
            body = {k: v for k, v in review.items() if k != "reviewHash"}
            if digest(body) != review.get("reviewHash") or review.get("campaignHash") != run.run_hash:
                raise RunError(f"{path}: review hash or run differs")
            job = run.by_id.get(review["jobId"])
            rows = self.rows.get(review["jobId"], [])
            if job is None or sorted(r["seed"] for r in rows) != sorted(s["seed"] for s in review["seedResults"]):
                raise RunError(f"{path}: review does not match the journal")
            self.reviews[review["jobId"]] = review
        # reuse
        self.reused: dict[str, dict] = {}
        if run.reusable and not run.force:
            for j in run.jobs:
                hit = run.reusable.get(j["resultKey"])
                if hit is not None and j["id"] not in self.reviews and j["id"] not in self.rows:
                    self.reused[j["id"]] = hit
        J.write_json_atomic(R / "reuse.json", {
            "schema": "aoe2-matchup-reuse/v1", "runHash": run.run_hash, "resultIndexSha256": run.index_sha256,
            "forced": run.force, "reusableInIndex": len(run.reusable), "reused": len(self.reused),
            "contexts": [[jid, run.by_id[jid]["resultKey"], hit["outcome"], hit.get("source")]
                         for jid, hit in sorted(self.reused.items())]}, indent=None)

    # -------------------------------------------------------------- reviews
    def _review(self, job: dict) -> dict:
        run = self.run
        rows = sorted(self.rows.get(job["id"], []), key=lambda r: r["seed"])
        prior, prior_source = run.prior(job)
        decision = run.policy.decision(job, rows, prior)
        if decision["requiredSeeds"]:
            raise RunError(f"{job['id']}: review of an incomplete seed set")
        outcome = run.policy.outcome(job, rows, prior)
        context = {"profiles": job["profileHashes"], "counts": job["counts"], "scenarioHash": job["scenarioHash"],
                   "family": job["family"], "engineFamily": job["engineFamily"],
                   "weightedCosts": job["weightedCosts"], "policy": job["policy"]}
        if digest(context) != job["contextHash"]:
            raise RunError(f"{job['id']}: context hash")
        body = {
            "schema": REVIEW_SCHEMA, "campaignHash": run.run_hash, "runId": self.cfg["runId"], "jobId": job["id"],
            "reviewedAt": J.now(), "status": "passed", "context": context, "contextHash": job["contextHash"],
            "pairKey": job["pairKey"], "resultKey": job["resultKey"], "setupHash": run.inputs["setupHash"],
            "physicsVersion": run.engine["physicsVersion"], "executionVersion": run.engine["executionVersion"],
            "engineId": run.engine["engineId"],
            "validationMode": "single_seed_forecast_screen" if decision["evidenceLevel"] == SINGLE else "fresh_seed_set",
            "samplingPolicy": run.policy.name, "samplingPolicyHash": run.sampling_hash,
            "evidenceLevel": decision["evidenceLevel"], "samplingDecision": decision,
            "seedCount": len(rows), "requiredSeeds": [],
            "seedResults": [{"seed": r["seed"], "winnerOwner": r["winnerOwner"], "ticks": r["ticks"],
                             "finalStateHash": r["finalStateHash"], "eventLogHash": r["eventLogHash"],
                             "winnerHpFraction": winner_hp_fraction(r), "recordHash": digest(r)} for r in rows],
            "exactReplay": {"required": False, "performed": False, "exact": None,
                            "reason": "distinct seeds only (sampling policy v3 rule)"},
            "outcome": outcome, "priorOutcomes": prior, "priorSource": prior_source,
            "changed": None if prior is None else any(p != outcome for p in prior),
            "displayedCells": job["displayedCells"],
        }
        return {**body, "reviewHash": digest(body)}

    def _finish(self, job: dict) -> None:
        review = self._review(job)
        J.write_json_atomic(self.R / "pair-reviews" / f"{job['id']}.json", review)
        self.reviews[job["id"]] = review
        self._phase_check(job["id"])

    def _phase_check(self, jid: str | None = None) -> None:
        size = self.cfg["execution"]["phaseContexts"]
        indexes = range(len(self.order) // size + 1) if jid is None else [self.position[jid] // size]
        for p in indexes:
            batch = self.order[p * size:(p + 1) * size]
            if not batch:
                continue
            path = self.R / "reviews" / f"{p + 1:03d}.json"
            if path.exists() or not all(j in self.reviews or j in self.reused or j in self.blocked for j in batch):
                continue
            reviewed = [j for j in batch if j in self.reviews]
            report = {"phase": f"{p + 1:03d}", "campaignHash": self.run.run_hash, "reviewedAt": J.now(),
                      "plannedJobs": len(batch), "reviewedJobs": len(reviewed),
                      "reusedJobs": sum(j in self.reused for j in batch),
                      "singleSeedConfirmations": sum(self.reviews[j]["evidenceLevel"] == SINGLE for j in reviewed),
                      "multiSeedValidations": sum(self.reviews[j]["evidenceLevel"] == MULTI for j in reviewed),
                      "blockedJobs": [j for j in batch if j in self.blocked],
                      "reviewHashes": [{"jobId": j, "reviewHash": self.reviews[j]["reviewHash"]} for j in reviewed],
                      "status": "complete_with_blocked" if any(j in self.blocked for j in batch) else "passed"}
            J.write_json_atomic(path, report)

    # ---------------------------------------------------------------- state
    def _state(self, status: str) -> None:
        total = len(self.run.jobs)
        done = len(self.reviews) + len(self.reused)
        levels = Counter(r["evidenceLevel"] for r in self.reviews.values())
        outcomes = Counter(r["outcome"] for r in self.reviews.values())
        state = {
            "schema": STATE_SCHEMA, "runId": self.cfg["runId"], "campaignHash": self.run.run_hash,
            "configHash": self.run.config_hash, "status": status,
            "pid": os.getpid() if status in ("running", "stopping") else None,
            "startedAt": self.started_at, "updatedAt": J.now(),
            "engineId": self.run.engine["engineId"], "nodeVersion": self.node_version, "workers": self.workers,
            "samplingPolicy": self.run.policy.name, "inventorySha256": self.run.inventory_sha256,
            "resultIndexSha256": self.run.index_sha256, "forcedRerun": self.run.force,
            "contexts": {"total": total, "complete": done, "reviewed": len(self.reviews), "reused": len(self.reused),
                         "blocked": len(self.blocked), "remaining": total - done - len(self.blocked),
                         "active": len({v["jobId"] for v in self.inflight.values()})},
            "seeds": {"saved": self.saved, "savedThisSession": self.session_seeds,
                      "failedAttempts": self.attempt_lines},
            "evidenceLevels": dict(sorted(levels.items())), "outcomes": dict(sorted(outcomes.items())),
            "blockedJobs": sorted(self.blocked),
            "active": sorted(({k: v[k] for k in ("jobId", "seed", "attempt", "limitSeconds", "startedAt")}
                              for v in self.inflight.values()), key=lambda a: (a["jobId"], a["seed"])),
            "journalRepair": self.repair if self.repair.get("repaired") else None,
            "stopReason": self.stop_reason,
        }
        J.write_json_atomic(self.R / "state.json", state)
        self._last_state = time.monotonic()

    # ------------------------------------------------------------- dispatch
    def _needed(self, jid: str) -> list[int]:
        job = self.run.by_id[jid]
        rows = self.rows.get(jid, [])
        prior, _ = self.run.prior(job)
        return self.run.policy.dispatchable(job, rows, prior)

    def _settled(self, jid: str) -> bool:
        return jid in self.reviews or jid in self.reused or jid in self.blocked

    def _try_finish(self, jid: str) -> None:
        if self._settled(jid) or any(v["jobId"] == jid for v in self.inflight.values()):
            return
        job = self.run.by_id[jid]
        prior, _ = self.run.prior(job)
        if self.run.policy.complete(job, self.rows.get(jid, []), prior):
            self._finish(job)

    def _submit(self, jid: str, seed: int) -> None:
        n = self.failures[(jid, seed)]
        limit = self.run.steps[n]
        key = f"{jid}:{seed}:{n + 1}"
        mode = self.cfg["execution"].get("diagnostics", "after-first-timeout")
        diag = None
        if mode == "always" or (mode == "after-first-timeout" and n > 0):
            diag = str(self.R / "progress" / f"{jid}-{seed}-a{n + 1}-{int(time.time() * 1000)}.jsonl")
            (self.R / "progress").mkdir(parents=True, exist_ok=True)
        request = {"key": key, "payload": self.run.payload(self.run.by_id[jid], seed), "limitSeconds": limit}
        if diag:
            request["diagnosticProgressPath"] = diag
        self.inflight[key] = {"jobId": jid, "seed": seed, "attempt": n + 1, "limitSeconds": limit,
                              "startedAt": J.now(), "deadline": time.monotonic() + limit + PYTHON_WATCHDOG_GRACE,
                              "progressPath": diag}
        self.backend.submit(request)

    def _dispatch(self) -> None:
        while not self.stopping and len(self.inflight) < self.workers:
            busy = {(v["jobId"], v["seed"]) for v in self.inflight.values()}
            pick = None
            for jid in list(self.open):
                if self._settled(jid):
                    self.open.remove(jid)
                    continue
                seeds = [s for s in self._needed(jid) if (jid, s) not in busy]
                if seeds:
                    pick = (jid, seeds[0])
                    break
                if not any(v["jobId"] == jid for v in self.inflight.values()):
                    self._try_finish(jid)
                    if self._settled(jid):
                        self.open.remove(jid)
            if pick is None:
                while self.cursor < len(self.order) and self._settled(self.order[self.cursor]):
                    self.cursor += 1
                if self.cursor >= len(self.order):
                    return
                jid = self.order[self.cursor]
                self.cursor += 1
                self.open.append(jid)
                self._try_finish(jid)  # complete from the journal already (killed before its review)
                continue
            self._submit(*pick)

    # -------------------------------------------------------------- results
    def _record(self, info: dict, reply: dict) -> None:
        run, job = self.run, self.run.by_id[info["jobId"]]
        r = reply["result"]
        start, rem = r["startingHpByOwner"], r["remainingByOwner"]
        row = {
            "campaignHash": run.run_hash, "runId": self.cfg["runId"], "matchupId": job["id"], "pairKey": job["pairKey"],
            "contextHash": job["contextHash"], "resultKey": job["resultKey"],
            "physicsVersion": run.engine["physicsVersion"], "executionVersion": run.engine["executionVersion"],
            "engineId": run.engine["engineId"], "nodeVersion": self.node_version, "seed": info["seed"],
            "startedAt": reply.get("startedAt") or info["startedAt"], "finishedAt": J.now(),
            "wallSeconds": reply["wallSeconds"], "attempt": info["attempt"], "limitSeconds": info["limitSeconds"],
            "purpose": "fresh_measurement", "samplingPolicy": run.policy.name, "samplingPolicyHash": run.sampling_hash,
            "counts": job["counts"], "unitCount": job["counts"][0], "opponentCount": job["counts"][1],
            "profileHashes": job["profileHashes"], "scenarioHash": job["scenarioHash"],
            "outcome": "draw" if r["outcome"] == "draw" else ("win" if r["winnerOwner"] == 2 else "loss"),
            "winnerOwner": r["winnerOwner"],
            "unitStartingHp": start["2"], "opponentStartingHp": start["3"],
            "unitRemainingHp": (rem.get("2") or {}).get("hp", 0), "opponentRemainingHp": (rem.get("3") or {}).get("hp", 0),
            "unitSurvivors": (rem.get("2") or {}).get("units", 0), "opponentSurvivors": (rem.get("3") or {}).get("units", 0),
            "ticks": r["ticks"], "simulationSeconds": r["ticks"] / 60,
            "finalStateHash": r["finalStateHash"], "eventLogHash": r["eventLogHash"],
        }
        if any(x["seed"] == row["seed"] for x in self.rows.get(job["id"], [])):
            raise RunError(f"never rerun a completed seed: {job['id']} seed {row['seed']}")
        self.journal.append(row)  # fsynced before any state that depends on it
        self.rows.setdefault(job["id"], []).append(row)
        self.saved += 1
        self.session_seeds += 1

    def _failure(self, info: dict, reply: dict) -> None:
        jid, seed = info["jobId"], info["seed"]
        self.failures[(jid, seed)] += 1
        exhausted = self.failures[(jid, seed)] >= len(self.run.steps)
        row = {"campaignHash": self.run.run_hash, "matchupId": jid, "contextHash": self.run.by_id[jid]["contextHash"],
               "seed": seed, "purpose": "fresh_measurement", "attempt": info["attempt"],
               "startedAt": reply.get("startedAt") or info["startedAt"], "finishedAt": J.now(),
               "wallSeconds": reply.get("wallSeconds"), "limitSeconds": info["limitSeconds"],
               "watchdog": reply.get("watchdog", False), "error": reply.get("error"),
               "unfinishedOutcome": reply.get("unfinishedOutcome"), "lastProgress": reply.get("lastProgress"),
               "exhausted": exhausted, "progressPath": info.get("progressPath"), "nodeVersion": self.node_version}
        self.attempts.append(row)
        self.attempt_lines += 1
        self.log(json.dumps({"attemptFailed": {k: row[k] for k in ("matchupId", "seed", "attempt", "limitSeconds",
                                                                    "watchdog", "exhausted")}}))
        if exhausted:
            self.blocked[jid] = {"jobId": jid, "seed": seed, "attempts": self.failures[(jid, seed)],
                                 "lastError": row["error"], "lastProgress": row["lastProgress"],
                                 "watchdog": row["watchdog"], "at": row["finishedAt"]}
            self._phase_check(jid)

    def _abandon_inflight(self, error: dict) -> None:
        for key, info in sorted(self.inflight.items()):
            self._failure(info, {"error": error, "watchdog": False})
        self.inflight.clear()

    # ----------------------------------------------------------------- main
    def _signal(self, signum, _frame):
        self.stopping = True
        self.stop_reason = signal.Signals(signum).name

    def execute(self) -> int:
        R = self.R
        R.mkdir(parents=True, exist_ok=True)
        stop_file = R / "STOP"
        if stop_file.exists():
            self.log(f"{stop_file} exists: remove it to run")
            return EXIT_STOPPED
        lock = J.RunnerLock(R / ".runner.lock", {"runHash": self.run.run_hash, "runId": self.cfg["runId"],
                                                  "command": " ".join(sys.argv)})
        try:
            lock.acquire()
        except J.LockBusy as busy:
            self.log(str(busy))
            return EXIT_LOCKED
        if lock.cleared:
            self.log(f"cleared stale lock of dead process {lock.cleared.get('pid')}")
        old_handlers = {s: signal.signal(s, self._signal) for s in (signal.SIGTERM, signal.SIGINT)}
        self.inflight: dict[str, dict] = {}
        self.started_at = J.now()
        sessions = J.Journal(R / "sessions.jsonl")
        try:
            self.run.prepare(build=True)
            self._load_records()
            self.journal = J.Journal(R / "runs.jsonl")
            self.order = [j["id"] for j in self.run.jobs]
            self.position = {jid: i for i, jid in enumerate(self.order)}
            self.open: list[str] = []
            self.cursor = 0
            self._phase_check()
            self.backend = self.backend_factory()
            hello = self.backend.start()
            self.node_version = (hello.get("node") or {}).get("version")
            if hello.get("engineId") != self.run.engine["engineId"] or \
                    hello.get("filesDigest") not in (None, self.run.engine["filesDigest"]):
                raise RunError(f"backend runs engine {hello.get('engineId')}, config wants {self.run.engine['engineId']}")
            sessions.append({"event": "start", "pid": os.getpid(), "at": self.started_at, "node": hello.get("node"),
                             "workers": self.workers, "savedSeeds": self.saved, "reviewed": len(self.reviews),
                             "reused": len(self.reused), "blocked": len(self.blocked),
                             "journalRepair": self.repair if self.repair.get("repaired") else None,
                             "staleLockCleared": lock.cleared})
            self._state("running")
            restarts = 0
            self._dispatch()
            while self.inflight and not self.stopping:
                if stop_file.exists():
                    self.stopping, self.stop_reason = True, "STOP file"
                    break
                reply = self.backend.get(timeout=1.0)
                if reply is None:
                    late = [k for k, v in self.inflight.items() if time.monotonic() > v["deadline"]]
                    if late:
                        self.log(f"backend unresponsive for {late}; restarting it")
                        self.backend.kill()
                        self._abandon_inflight({"name": "BackendHang", "message": "no reply within watchdog + grace"})
                        restarts += 1
                        self._restart_backend(restarts)
                    elif time.monotonic() - self._last_state > 10:
                        self._state("running")
                    if not self.inflight:
                        self._dispatch()
                    continue
                if "backendExit" in reply or "fatal" in reply:
                    self.log(f"backend failure: {reply}")
                    self.backend.kill()
                    self._abandon_inflight({"name": "BackendExit", "message": json.dumps(reply)[:500]})
                    restarts += 1
                    self._restart_backend(restarts)
                    self._dispatch()
                    continue
                info = self.inflight.pop(reply["key"], None)
                if info is None:
                    continue  # reply for an attempt abandoned before a backend restart
                if reply.get("ok"):
                    self._record(info, reply)
                else:
                    self._failure(info, reply)
                self._try_finish(info["jobId"])
                self._dispatch()
                self._state("running")
            # loop ended: everything settled, or stopping
            remaining = [j for j in self.order if not self._settled(j)]
            if self.stopping:
                status, code = "interrupted", EXIT_STOPPED
            elif remaining:
                raise RunError(f"{len(remaining)} contexts neither finished nor blocked (scheduler error)")
            else:
                status, code = ("complete_with_blocked" if self.blocked else "complete"), EXIT_DONE
            if self.backend:
                self.backend.stop() if not self.stopping else self.backend.kill()
            self.inflight.clear()
            self._state(status)
            sessions.append({"event": "end", "pid": os.getpid(), "at": J.now(), "status": status,
                             "savedThisSession": self.session_seeds, "reason": self.stop_reason})
            self.log(json.dumps({"status": status, "reviewed": len(self.reviews), "reused": len(self.reused),
                                 "blocked": sorted(self.blocked), "savedThisSession": self.session_seeds}))
            return code
        except RunError as error:
            self.log(f"run error: {error}")
            if self.backend:
                self.backend.kill()
            try:
                self.inflight = {}
                self._state("failed")
            except Exception:  # noqa: BLE001 - state is best effort here
                pass
            sessions.append({"event": "end", "pid": os.getpid(), "at": J.now(), "status": "failed",
                             "error": str(error)})
            return error.exit_code
        except Exception as error:  # noqa: BLE001 - any other failure: record it, let the supervisor restart
            import traceback
            self.log("runner crashed:\n" + traceback.format_exc())
            if self.backend:
                self.backend.kill()
            try:
                self.inflight = {}
                self._state("failed")
            except Exception:  # noqa: BLE001
                pass
            sessions.append({"event": "end", "pid": os.getpid(), "at": J.now(), "status": "crashed",
                             "error": repr(error)})
            return EXIT_FAILED
        finally:
            for s, h in old_handlers.items():
                signal.signal(s, h)
            sessions.close()
            lock.release()

    def _restart_backend(self, restarts: int) -> None:
        if restarts > self.max_backend_restarts:
            err = RunError(f"backend restarted {restarts} times this session; giving up")
            err.exit_code = EXIT_FAILED
            raise err
        time.sleep(min(30, 2 ** min(restarts, 5)))
        self.backend = self.backend_factory()
        hello = self.backend.start()
        self.node_version = (hello.get("node") or {}).get("version")


def run_config(cfg: dict, *, records: Path | None = None, force: bool = False, **kwargs) -> int:
    try:
        run = Run(cfg, records=records, force=force)
    except RunError as error:
        print(f"run error: {error}", file=sys.stderr)
        return error.exit_code
    return Runner(run, **kwargs).execute()

"""``archive``: the essential records of a run (or of the 2026 campaigns) as one deterministic tarball.

Classes (``docs/matchups/RECORDS_TRIAGE.md``):

ESSENTIAL   needed to redo an analysis or prove provenance, and not cheaply
            regenerable (seed journals, failed attempts, pair reviews,
            diagnoses, owner declarations/approvals, final exports, frozen
            definitions, the forecast record, the inference table);
DERIVABLE   can be regenerated from the essential set + bundle + engine
            (phase reviews, intermediate cumulative exports, inventories,
            audits, copies of the serving DB);
DISPOSABLE  diagnostics snapshots and status reports with no unique result
            content, superseded intermediate model outputs.

The archive holds the ESSENTIAL files plus a few small DERIVABLE inputs that
the importers read directly (``archived`` in the rules). Determinism: members
in sorted path order, mtime 0, uid/gid 0, no user names, mode 0644, gzip mtime
0, and a ``MANIFEST.json`` first member listing every member's path, class,
kind, size and sha256 (plus the source: records directory or RB commit). The
same inputs give the same bytes. A sidecar ``<out>.manifest.json`` repeats the
manifest with the archive's own sha256.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import subprocess
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

from aoe2x.matchups.paths import REPO_ROOT

ARCHIVE_SCHEMA = "aoe2-matchup-records-archive/v1"
ESSENTIAL, DERIVABLE, DISPOSABLE = "ESSENTIAL", "DERIVABLE", "DISPOSABLE"

# --------------------------------------------------------------- run records
# (pattern on the path inside <records>, kind, class, archived)
RUN_RULES = [
    (r"^manifest\.json$", "manifest (freeze)", ESSENTIAL, True),
    (r"^config\.json$", "run config", ESSENTIAL, True),
    (r"^inventory/inventory-summary\.json$", "inventory summary", ESSENTIAL, True),
    (r"^inventory/.*", "inventory jobs", DERIVABLE, False),
    (r"^runs\.jsonl$", "seed journal", ESSENTIAL, True),
    (r"^attempts\.jsonl$", "failed attempts", ESSENTIAL, True),
    (r"^sessions\.jsonl$", "runner sessions", ESSENTIAL, True),
    (r"^pair-reviews/[^/]+\.json$", "pair reviews", ESSENTIAL, True),
    (r"^reviews/[^/]+\.json$", "phase reviews", DERIVABLE, True),
    (r"^reuse\.json$", "reuse list", DERIVABLE, True),
    (r"^state\.json$", "state", DERIVABLE, True),
    (r"^export/.*", "export snapshot", ESSENTIAL, True),
    (r"^progress/.*", "diagnostic progress", DISPOSABLE, False),
    (r"^logs/.*", "logs", DISPOSABLE, False),
    (r"^(supervisor\.json|STOP|\.runner\.lock|\.supervisor\.lock)$", "control files", DISPOSABLE, False),
]

# ---------------------------------------------------------------- 2026 (RB)
C = "aoe2x/js_simulation/calibration/campaigns/"
R = "aoe2x/js_simulation/calibration/reports/"
CAMPAIGNS = {
    "pilot": C + "civ-matchups-campaign-2026-10-31/pilot/",
    "adaptive": C + "civ-matchups-campaign-2026-10-31/adaptive/",
    "adaptive-plan": C + "civ-matchups-campaign-2026-10-31/",
    "mismatch": C + "civ-matchups-mismatch-validation-2026-11-05/",
    "forecast": C + "civ-matchups-forecast-validation-2026-11-07/",
    "recovery": C + "civ-matchups-forecast-recovery-2026-11-10/",
    "inference": C + "civ-matchups-inference-phase1-2026-10-31/",
    "adaptive-rule": C + "civ-matchups-adaptive-rule-v1-2026-11-01/",
    "prediction-v1": C + "civ-matchups-prediction-first-pass-v1-2026-11-01/",
    "prediction-v2": C + "civ-matchups-prediction-first-pass-v2-2026-11-01/",
    "first-pass": R + "civ-matchups-first-pass-provisional-2026-11-02/",
    "ranking-definition": C + "unit-rankings-path-recovery-2026-10-29/",
    "ranking-runs": C + "unit-rankings-consolidated-2026-10-29/",
}
# The last reviewed-only export of each campaign (what the 2026 result index was imported from).
FINAL_SNAPSHOTS = {"forecast": "correction-snapshots/070/", "mismatch": "correction-snapshots/review-ready-2026-11-07/",
                   "recovery": "correction-snapshots/002/"}
# (pattern on the path inside the campaign dir, kind, class, archived); first match wins.
RB_RULES = [
    (r"(^|/)progress(/|\.json$)", "progress diagnostics", DISPOSABLE, False),
    (r"^monitor-reports/", "monitor reports", DISPOSABLE, False),
    (r"(^|/)(runs\.jsonl(\.gz)?|runs/[^/]+\.jsonl|additional-recorded-runs\.jsonl)$", "seed journals", ESSENTIAL, True),
    (r"(^|/)attempts\.jsonl?(\.gz)?$", "failed attempts", ESSENTIAL, True),
    (r"(^|/)pair-reviews/", "pair reviews", ESSENTIAL, True),
    (r"(^|/)diagnostics?/|^recovery-review/|^diagnosis/", "diagnoses", ESSENTIAL, True),
    (r"^correction-snapshots/", "intermediate correction snapshots", DERIVABLE, False),
    (r"^(predictions|estimates|refinement)/", "selector predictions/estimates/refinement", DISPOSABLE, False),
    (r"^(reviews|phases)/|PHASE_.*\.md$|^checks/", "phase reviews", DERIVABLE, False),
    (r"^(user-reviews|website-releases|cost-holds/.*(authorization|hold|verification|receipt|monitor)[^/]*\.json"
     r"|closeout/.*(README\.md|analysis\.json|authorization\.json|monitor-pause\.json))", "owner declarations, approvals, releases",
     ESSENTIAL, True),
    (r"(^|/)(manifest\.json|launch-approval\.json|sampling-policy-v\d\.json|queue-controls\.json|control-events\.jsonl"
     r"|state\.json|completion\.json|summary\.json|summary\.csv|ceiling-parity\.json|undecided\.json"
     r"|revisions\.json|generator-source\.py|witness-source\.py|monitor-reporting\.json|website-release-status\.json"
     r"|inventory-summary\.json|README\.md|RESULTS\.md|CAMPAIGN_PLAN\.md|review\.(json|md)|rule-validation\.json"
     r"|tradeoff-validation\.json|\.gitignore|latest-inference|exporter-checks.*)$", "manifests, policies, state, docs",
     ESSENTIAL, True),
    (r"^(all-forecast-contexts|held-contexts|inventory)\.jsonl\.gz$", "inventories read by the importers", DERIVABLE, True),
    (r"(^|/)(jobs|expected-native-records|mismatches|yardstick-comparison)\.jsonl\.gz$", "inventories/job lists",
     DERIVABLE, False),
    (r"^(original-evidence\.jsonl\.gz|sources/)", "copies of serving-DB evidence / baseline DB", DERIVABLE, False),
    (r"^closeout/|^cost-holds/|^policy-transitions/", "closeout indexes, audits, pre-amendment journal copies",
     DERIVABLE, False),
    (r"\.jsonl\.gz$|\.json$|\.py$|\.mjs$", "campaign tables and helpers", ESSENTIAL, True),
]
# Whole-campaign overrides: (campaign, class, archived, kind) applied before RB_RULES when matched.
CAMPAIGN_OVERRIDES = {
    "prediction-v1": ("forecast record v1 (superseded by v2; nothing published depends on it)", DISPOSABLE, False),
    "prediction-v2": ("forecast record v2 (original predictions; not regenerable)", ESSENTIAL, True),
    "inference": ("rule-inference table (source of the 10,193 inferred results)", ESSENTIAL, True),
    "first-pass": ("first-pass delivery (import-results input)", ESSENTIAL, True),
    "adaptive-rule": ("adaptive selector baselines", DERIVABLE, False),
}
RANKING_FILES = {"ranking-definition": {"manifest.json"},
                 "ranking-runs": {"runs.jsonl", "additional-recorded-runs.jsonl", "manifest.json"}}


def classify_run(path: str) -> tuple[str, str, bool]:
    for pattern, kind, cls, archived in RUN_RULES:
        if re.search(pattern, path):
            return kind, cls, archived
    return "other", DISPOSABLE, False


def campaign_of(path: str):
    best = None
    for name, prefix in CAMPAIGNS.items():
        if path.startswith(prefix) and (best is None or len(prefix) > len(CAMPAIGNS[best])):
            best = name
    return best


def classify_rb(path: str):
    """(campaign, inner path, kind, class, archived) or None when the file is not a matchup record."""
    camp = campaign_of(path)
    if camp is None:
        return None
    inner = path[len(CAMPAIGNS[camp]):]
    if camp == "adaptive-plan" and "/" in inner:
        return None  # pilot/ and adaptive/ have their own prefixes
    if camp in RANKING_FILES:
        if inner not in RANKING_FILES[camp]:
            return None
        return camp, inner, ("frozen ranking definition" if camp == "ranking-definition"
                             else "ranking-era seed journals"), ESSENTIAL, True
    if camp in CAMPAIGN_OVERRIDES:
        kind, cls, archived = CAMPAIGN_OVERRIDES[camp]
        return camp, inner, kind, cls, archived
    if inner.startswith(FINAL_SNAPSHOTS.get(camp, "\0")):
        return camp, inner, "final correction snapshot", ESSENTIAL, True
    for pattern, kind, cls, archived in RB_RULES:
        if re.search(pattern, inner):
            return camp, inner, kind, cls, archived
    return camp, inner, "other", DISPOSABLE, False


def rb_tree(ref: str) -> list[tuple[str, str, int]]:
    out = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-tree", "-r", "-l", ref], check=True,
                         capture_output=True).stdout.decode()
    rows = []
    for line in out.splitlines():
        meta, path = line.split("\t", 1)
        _, typ, obj, size = meta.split()
        if typ == "blob":
            rows.append((path, obj, int(size)))
    return rows


def triage_rb(ref: str) -> dict:
    """Counts and bytes per (campaign, kind, class) on RB."""
    table = defaultdict(lambda: {"files": 0, "bytes": 0})
    totals = Counter()
    for path, _, size in rb_tree(ref):
        c = classify_rb(path)
        if c is None:
            continue
        camp, _, kind, cls, archived = c
        t = table[(camp, kind, cls, archived)]
        t["files"] += 1
        t["bytes"] += size
        totals[cls] += size
        totals["archived" if archived else "notArchived"] += size
    rows = [{"campaign": k[0], "kind": k[1], "class": k[2], "archived": k[3], **v}
            for k, v in sorted(table.items(), key=lambda kv: (kv[0][0], -kv[1]["bytes"]))]
    return {"rows": rows, "totals": dict(totals)}


# ------------------------------------------------------------------- writing

def _cat_file(objects: list[str]):
    """Yield blob contents for git object ids, in order (one ``git cat-file --batch`` process)."""
    proc = subprocess.Popen(["git", "-C", str(REPO_ROOT), "cat-file", "--batch"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE)
    import threading

    def feed():
        for o in objects:
            proc.stdin.write((o + "\n").encode())
        proc.stdin.close()
    threading.Thread(target=feed, daemon=True).start()
    for _ in objects:
        header = proc.stdout.readline().split()
        size = int(header[2])
        data = proc.stdout.read(size)
        proc.stdout.read(1)
        yield data
    proc.wait()


def _member(name: str, size: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size, info.mtime, info.mode, info.uid, info.gid, info.uname, info.gname = size, 0, 0o644, 0, 0, "", ""
    return info


def write_tar(out: Path, entries, manifest: dict) -> dict:
    """``entries()``: a callable yielding (archive path, bytes, meta) in sorted order; called twice (pass 1
    hashes for the manifest, pass 2 writes), so nothing large is held in memory."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    listed = [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), **meta}
              for name, data, meta in entries()]
    by_kind = Counter()
    for x in listed:
        by_kind[x["kind"]] += x["bytes"]
    manifest = {**manifest, "schema": ARCHIVE_SCHEMA, "files": listed,
                "totals": {"files": len(listed), "bytes": sum(x["bytes"] for x in listed),
                           "byClass": dict(sorted(Counter(x["class"] for x in listed).items())),
                           "bytesByKind": dict(sorted(by_kind.items()))}}
    mbytes = (json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode()
    tmp = out.with_name(out.name + ".part")
    with open(tmp, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0, filename="") as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tar:
            tar.addfile(_member("MANIFEST.json", len(mbytes)), io.BytesIO(mbytes))
            for (name, data, _), want in zip(entries(), listed):
                if name != want["path"] or hashlib.sha256(data).hexdigest() != want["sha256"]:
                    raise RuntimeError(f"{name} changed between the two archive passes")
                tar.addfile(_member(name, len(data)), io.BytesIO(data))
    tmp.replace(out)
    h = hashlib.sha256()
    with open(out, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    side = {k: v for k, v in manifest.items() if k != "files"} | {
        "archive": {"file": out.name, "bytes": out.stat().st_size, "sha256": h.hexdigest()}, "files": listed}
    out.with_name(out.name + ".manifest.json").write_text(json.dumps(side, indent=1, sort_keys=True) + "\n")
    return side


def archive_run(records: Path, out: Path, config_path: Path | None = None) -> dict:
    records = Path(records)
    files = sorted(p for p in records.rglob("*") if p.is_file())
    exhausted_progress = set()
    attempts = records / "attempts.jsonl"
    if attempts.exists():
        for line in attempts.read_text().splitlines():
            try:
                a = json.loads(line)
            except ValueError:
                continue
            if a.get("exhausted") and a.get("progressPath"):
                exhausted_progress.add(Path(a["progressPath"]).name)
    entries, skipped = [], Counter()
    for p in files:
        rel = p.relative_to(records).as_posix()
        kind, cls, archived = classify_run(rel)
        if rel.startswith("progress/") and p.name in exhausted_progress:
            kind, cls, archived = "diagnostic progress of an exhausted attempt", ESSENTIAL, True
        if rel.endswith((".part", ".tmp", ".building")):
            archived = False
        if not archived:
            skipped[f"{cls}:{kind}"] += p.stat().st_size
            continue
        entries.append((rel, p, {"kind": kind, "class": cls}))
    if config_path:
        entries.append(("config.json", Path(config_path), {"kind": "run config", "class": ESSENTIAL}))
    entries.sort(key=lambda e: e[0])
    state = {}
    if (records / "state.json").exists():
        state = json.loads((records / "state.json").read_text())
    return write_tar(out, lambda: ((n, p.read_bytes(), m) for n, p, m in entries), {"source": {"kind": "run-records", "runHash": state.get("runHash"),
                                               "runId": state.get("runId")},
                                    "skippedBytes": dict(sorted(skipped.items()))})


def archive_rb(ref: str, commit: str, out: Path, with_index: Path | None = None) -> dict:
    chosen = []
    skipped = Counter()
    for path, obj, size in rb_tree(ref):
        c = classify_rb(path)
        if c is None:
            continue
        camp, inner, kind, cls, archived = c
        if archived:
            chosen.append((path, obj, {"kind": kind, "class": cls, "campaign": camp}))
        else:
            skipped[f"{cls}:{kind}"] += size
    chosen.sort(key=lambda e: e[0])

    def entries():
        for (path, _, meta), data in zip(chosen, _cat_file([o for _, o, _ in chosen])):
            yield "rb/" + path, data, meta
        if with_index is not None:
            raw = Path(with_index).read_bytes()
            yield ("derived/result-index.jsonl.gz", raw,
                   {"kind": "2026 result index (import-results)", "class": DERIVABLE, "campaign": "index"})
    return write_tar(out, entries, {"source": {"kind": "research-branch", "ref": ref, "commit": commit},
                                      "skippedBytes": dict(sorted(skipped.items()))})

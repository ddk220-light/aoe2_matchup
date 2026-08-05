"""run_golden_overnight.py — drive the whole golden-set job unattended.

Phases, in order, each resumable:
  1. wait until the game rig is idle (no other record_golden process)
  2. record every matchup in the list that has no decoded output yet
  3. flag ODD fights by objective criteria and record 2 extra runs of each
  4. regenerate GROUND_TRUTH.md over everything
  5. zip the decoded package + report and Taildrop it to the target machine

Phase 2 is derived from what is ON DISK, not from a cursor, so this can be re-run
after any interruption and it picks up exactly what is missing.

  python run_golden_overnight.py <out_dir> <matchups.json> [--drop-to dragonstar]
"""
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

REPORTER = HERE / "golden_report.py"
TAILSCALE = r"C:\Program Files\Tailscale\tailscale.exe"

# No cap. A cap silently decides which rows end up trustworthy, and the choice of which
# ones to drop is not the runner's to make (user, 2026-07-30).
MAX_EXTRA_FIGHTS = 10 ** 9
REPEATS_PER_ODD = 2
# THE RULE: a fight whose winner keeps under 44% of its starting hp pool is close enough
# that one run cannot be trusted, so it is recorded 3 more times — INLINE, right after
# the fight, unit by unit, rather than deferred to a chase phase (user, 2026-07-30).
CLOSE_WIN_HP_FRAC = 0.44
REPEATS_PER_CLOSE_WIN = 3

# Ship a snapshot every N fights so the calibration machine can work while the rig is
# still recording, instead of idling for the whole batch.
DROP_EVERY = 10
# Snapshots are CUMULATIVE (everything decoded so far), not deltas. A delta scheme
# needs every drop to arrive or the receiver has a silent gap; a cumulative snapshot
# is self-sufficient, and at ~280 KB/fight the largest is still only ~30 MB.


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def rig_busy():
    """Is another record_golden run holding the game?"""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Select-Object -ExpandProperty CommandLine"],
            capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return False
    mine = str(os.getpid())
    return any("record_golden.py" in l and mine not in l for l in out.splitlines())


def decoded_tags(out):
    """Base matchup tags that already have a decoded summary (repeats stripped)."""
    tags = set()
    counts = Counter()
    for p in (Path(out) / "decoded").glob("*.summary.json"):
        t = p.name[: -len(".summary.json")]
        counts[t.split("_r")[0] if "_r" in t else t] += 1
        tags.add(t)
    return tags, counts


def oddness(summary, meta):
    """Why this fight deserves a second look. Empty list = unremarkable.

    These are ARTIFACT smells, not 'surprising matchups' — a lopsided result between
    mismatched units is expected and is not flagged. What is flagged is a fight whose
    shape suggests the rig, not the game, decided it.
    """
    reasons = []
    s2, s3 = summary["sides"]["side2"], summary["sides"]["side3"]
    dur = meta.get("duration_s") or 0
    if summary["outcome"] in ("timeout", "both_wiped"):
        reasons.append(f"indeterminate outcome ({summary['outcome']})")
    win, lose = (s2, s3) if summary["outcome"] == "side2" else (s3, s2)
    if summary["outcome"] in ("side2", "side3"):
        if win["survivors"] == win["start_count"]:
            reasons.append("winner took zero casualties (shutout)")
        if lose["hits_landed"] == 0:
            reasons.append("loser never landed a hit")
        # a narrow win: the winner is barely standing, so the result is fragile
        frac = _hp_frac(win)
        if frac is not None and frac < CLOSE_WIN_HP_FRAC:
            reasons.append(f"close win — winner kept {frac*100:.0f}% hp")
    if dur and dur < 12:
        reasons.append(f"very short fight ({dur:.0f}s)")
    if dur and dur > 170:
        reasons.append(f"ran to the time cap ({dur:.0f}s)")
    return reasons


def _hp_frac(side):
    """Fraction of its starting hp pool a side still holds, or None if unknown
    (fights decoded before hp_start was recorded)."""
    start = side.get("hp_start")
    if not start:
        return None
    return (side.get("hp_remaining") or 0.0) / start


def repeats_for(reasons):
    return (REPEATS_PER_CLOSE_WIN if any(r.startswith("close win") for r in reasons)
            else REPEATS_PER_ODD)


def build_and_drop(out, drop_to, label, regen_report=True, files=None):
    """Zip the decoded set (+ report) and Taildrop it. `files` limits it to a delta.
    Returns the zip path, or None on failure."""
    dec = Path(out) / "decoded"
    md = Path(out) / "GROUND_TRUTH.md"
    if regen_report and files is None:
        subprocess.run([sys.executable, str(REPORTER), str(dec), "--md", str(md)],
                       capture_output=True)
    tag = Path(out).name
    zip_path = Path(out).parent / f"aoe2_golden_{tag}_{label}.zip"
    stage = Path(out).parent / f"_stage_{label}"
    if files is None:
        copy_in = (f"Copy-Item -Recurse '{dec}' (Join-Path '{stage}' 'decoded')\n"
                   f"if (Test-Path '{md}') {{ Copy-Item '{md}' '{stage}' }}\n"
                   f"if (Test-Path '{Path(out) / 'record.log'}') "
                   f"{{ Copy-Item '{Path(out) / 'record.log'}' '{stage}' }}")
    else:
        # The file list goes in a FILE, never inlined into the command. Inlining ~380
        # paths blew the Windows command-length limit ("filename or extension is too
        # long"), every delta failed, and because a failed drop never marks its files as
        # sent, each retry got larger and failed harder.
        listfile = Path(out).parent / f"_files_{label}.txt"
        listfile.write_text("\n".join(str(p) for p in files), encoding="utf-8")
        copy_in = (f"New-Item -ItemType Directory -Force "
                   f"(Join-Path '{stage}' 'decoded') | Out-Null\n"
                   f"Get-Content -LiteralPath '{listfile}' | "
                   f"Copy-Item -Destination (Join-Path '{stage}' 'decoded')")
    ps = f"""
$ErrorActionPreference='Stop'
if (Test-Path '{stage}') {{ Remove-Item -Recurse -Force '{stage}' }}
New-Item -ItemType Directory -Force '{stage}' | Out-Null
{copy_in}
if (Test-Path '{zip_path}') {{ Remove-Item -Force '{zip_path}' }}
Compress-Archive -Path (Join-Path '{stage}' '*') -DestinationPath '{zip_path}'
Remove-Item -Recurse -Force '{stage}'
(Get-Item '{zip_path}').Length
"""
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True)
    if not zip_path.exists():
        log(f"drop {label}: FAILED to build zip — {r.stderr.strip()[:200]}")
        return None
    size_mb = zip_path.stat().st_size / 1e6
    if drop_to:
        rc = subprocess.run([TAILSCALE, "file", "cp", str(zip_path), f"{drop_to}:"],
                            capture_output=True, text=True)
        if rc.returncode == 0:
            log(f"drop {label}: Taildropped {size_mb:.1f} MB to {drop_to}")
        else:
            log(f"drop {label}: Taildrop FAILED rc={rc.returncode} "
                f"{rc.stdout.strip()[:150]} {rc.stderr.strip()[:150]}")
    else:
        log(f"drop {label}: built {zip_path} ({size_mb:.1f} MB), no target")
    try:
        zip_path.unlink()          # the receiver has it; don't hoard snapshots locally
    except OSError:
        pass
    return zip_path


def make_dropper(out, drop_to, delta=False):
    """on_fight hook: ship every DROP_EVERY successful fights.

    delta=False ships a CUMULATIVE snapshot — self-sufficient, so a lost drop cannot
    leave the receiver with a gap. Fine for ~90 fights (largest zip ~20 MB).
    delta=True ships only files not yet sent. Needed at ~520 fights, where the decoded
    set reaches ~150 MB and re-zipping all of it 50+ times would burn real CPU during
    recording. The FINAL drop is cumulative either way, so any delta lost in transit is
    still delivered at the end.
    """
    # What has already been shipped is PERSISTED, so a restart resumes the delta stream
    # instead of trying to re-send the entire decoded set as one oversized drop.
    manifest = Path(out) / ".sent_files.json"
    try:
        prev = json.loads(manifest.read_text())
    except Exception:
        prev = {"sent": [], "seq": 0}
    state = {"n": 0, "sent": set(prev.get("sent", [])), "seq": prev.get("seq", 0)}

    def save():
        try:
            manifest.write_text(json.dumps({"sent": sorted(state["sent"]),
                                            "seq": state["seq"]}))
        except OSError:
            pass

    def hook(tag, status):
        if status != "ok":
            return
        state["n"] += 1
        if state["n"] % DROP_EVERY:
            return
        if not delta:
            done, _ = decoded_tags(out)
            build_and_drop(out, drop_to, f"partial_{len(done):03d}")
            return
        dec = Path(out) / "decoded"
        new = [p for p in sorted(dec.glob("*")) if p.name not in state["sent"]]
        if not new:
            return
        state["seq"] += 1
        if build_and_drop(out, drop_to, f"delta_{state['seq']:03d}", files=new):
            state["sent"].update(p.name for p in new)
            save()
    return hook


def make_followup(out):
    """THE close-win rule, applied inline: read back the fight just decoded and ask for
    REPEATS_PER_CLOSE_WIN more runs if the winner kept under CLOSE_WIN_HP_FRAC of its
    starting hp. Returns 0 for anything else."""
    dec = Path(out) / "decoded"

    def hook(tag, status):
        p = dec / f"{tag}.summary.json"
        if status != "ok" or not p.exists():
            return 0
        try:
            s = json.load(open(p))
        except Exception:
            return 0
        if s.get("outcome") not in ("side2", "side3"):
            return 0
        frac = _hp_frac(s["sides"][s["outcome"]])
        if frac is not None and frac < CLOSE_WIN_HP_FRAC:
            log(f"    close win ({frac*100:.0f}% kept) -> {REPEATS_PER_CLOSE_WIN} repeats")
            return REPEATS_PER_CLOSE_WIN
        return 0
    return hook


def phase_record(out, pairs, on_fight=None):
    from record_golden import record_many
    done, counts = decoded_tags(out)
    todo = [((m["civ1"], m["slug1"]), (m["civ2"], m["slug2"])) for m in pairs
            if f"{m['slug1']}__vs__{m['slug2']}" not in done]
    log(f"phase 2: {len(done)} already decoded, {len(todo)} to record")
    if not todo:
        return []
    return record_many(out, todo, tag_offset=counts, on_fight=on_fight,
                       followup=make_followup(out))


def phase_chase(out, pairs, on_fight=None):
    from record_golden import record_many
    by_tag = {f"{m['slug1']}__vs__{m['slug2']}": m for m in pairs}
    odd = []
    for p in sorted((Path(out) / "decoded").glob("*.summary.json")):
        tag = p.name[: -len(".summary.json")]
        if "_r" in tag:                      # already a repeat
            continue
        m = by_tag.get(tag)
        if not m:
            continue
        try:
            summary = json.load(open(p))
            meta = json.load(open(str(p).replace(".summary.", ".meta.")))
        except Exception:
            continue
        why = oddness(summary, meta)
        if why:
            win = summary["sides"].get(summary["outcome"])
            frac = _hp_frac(win) if win else None
            odd.append((tag, m, why, frac))

    log(f"phase 3: {len(odd)} odd fights flagged")
    for tag, _, why, frac in odd:
        kept = f"{frac*100:.0f}%" if frac is not None else "n/a"
        log(f"    ODD [{kept:>4} kept] {tag}: {'; '.join(why)}")
    if not odd:
        return []

    _, counts = decoded_tags(out)
    wanted = sum(repeats_for(w) for _, _, w, _f in odd)
    log(f"phase 3: {wanted} repeats wanted (close wins get {REPEATS_PER_CLOSE_WIN}, "
        f"other flags {REPEATS_PER_ODD}); budget {MAX_EXTRA_FIGHTS}")
    extra, budget = [], MAX_EXTRA_FIGHTS
    for tag, m, why, _f in odd:
        for _ in range(repeats_for(why)):
            if budget <= 0:
                break
            extra.append(((m["civ1"], m["slug1"]), (m["civ2"], m["slug2"])))
            budget -= 1
    if wanted > MAX_EXTRA_FIGHTS:
        log(f"    NOTE: extra-fight budget ({MAX_EXTRA_FIGHTS}) reached — "
            f"{wanted - MAX_EXTRA_FIGHTS} planned repeats skipped")
    log(f"phase 3: recording {len(extra)} extra fights")
    return record_many(out, extra, tag_offset=counts, on_fight=on_fight)


def phase_package(out, drop_to):
    log("phase 4: regenerating the report over everything")
    log("phase 5: building + dropping the FINAL snapshot")
    build_and_drop(out, drop_to, f"FINAL_{time.strftime('%Y-%m-%d')}")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    out, listfile = Path(argv[0]), Path(argv[1])
    drop_to = None
    if "--drop-to" in argv:
        drop_to = argv[argv.index("--drop-to") + 1]
    pairs = json.loads(listfile.read_text())

    log(f"golden overnight: {len(pairs)} matchups, out={out}, drop_to={drop_to}")
    waited = 0
    while rig_busy():
        if waited == 0:
            log("phase 1: another record_golden run holds the game — waiting")
        time.sleep(30)
        waited += 30
        if waited > 3 * 3600:
            log("phase 1: gave up waiting after 3h")
            return 1
    log(f"phase 1: rig idle (waited {waited}s)")

    # >90 fights => delta drops (see make_dropper)
    dropper = make_dropper(out, drop_to, delta=len(pairs) > 150)

    r1 = phase_record(out, pairs, on_fight=dropper)
    bad = [(t, s) for t, s in r1 if s != "ok"]
    log(f"phase 2 complete: {len(r1)} recorded, {len(bad)} not ok")
    for t, s in bad:
        log(f"    !! {t}: {s}")

    # one retry sweep for anything that failed to record at all — a transient nav
    # hiccup should not leave a permanent hole in the set
    if bad:
        log("phase 2b: retrying failed matchups once")
        r1b = phase_record(out, pairs, on_fight=dropper)
        for t, s in r1b:
            if s != "ok":
                log(f"    !! still failing {t}: {s}")

    r2 = phase_chase(out, pairs, on_fight=dropper)
    log(f"phase 3 complete: {len(r2)} extra fights")

    phase_package(out, drop_to)

    done, counts = decoded_tags(out)
    log(f"ALL DONE: {len(done)} decoded fight files, "
        f"{len([t for t in done if '_r' not in t])} distinct matchups")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main(sys.argv[1:]))

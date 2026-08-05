"""basics_championpluspaladin -- controlled unit-count-ratio benchmark for rebuilding
the sim engine from scratch.

Unlike the golden set (equal resources, up to 21 per side), this is FIXED exact
counts on both sides -- 1v1, 2v1, 2v3, 5v3, 6v3 -- for three unit pairings:
champion vs champion, paladin vs paladin, champion vs paladin. All Chinese Champion /
Spanish Paladin, same civs used throughout this project's golden set. Same
melee-vs-melee template (NoneAi both sides), video off. 3 runs per config, fixed --
no close-win escalation (this data is for isolating count-ratio dynamics, not
settling coin-flip outcomes).

  python record_basics.py <out_dir> <phase>      # phase in champion / paladin / cross / all
"""
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

CHAMPION = ("Chinese", "champion")
PALADIN = ("Spanish", "paladin")
RATIOS = [(1, 1), (2, 1), (2, 3), (5, 3), (6, 3)]
RUNS_PER_CONFIG = 3

PHASES = {
    "champion": ("champion_vs_champion", CHAMPION, CHAMPION),
    "paladin": ("paladin_vs_paladin", PALADIN, PALADIN),
    "cross": ("champion_vs_paladin", CHAMPION, PALADIN),
}


def build_jobs(label, side1, side2):
    jobs = []
    for n1, n2 in RATIOS:
        tag = f"{label}__{n1}v{n2}"
        for _ in range(RUNS_PER_CONFIG):
            jobs.append((tag, side1, side2, n1, n2))
    return jobs


def record_phase(out, phase_key):
    from record_golden import DECODER, KEEP_VIDEO, _positions_frozen, _check_army, _drop_decoded
    from auto.orchestrate_matchup import run_matchup, return_to_editor
    from auto import grpc_capture
    from auto.config import GRPC_PYTHON
    from build_golden_v2 import build_v2_from_sides as build_golden_from_sides
    import subprocess

    if not grpc_capture.available():
        print(f"FATAL: gRPC capture unavailable (AOE2_GRPC_PYTHON -> {GRPC_PYTHON})")
        return 2
    subprocess.run(["taskkill", "/f", "/im", "TextInputHost.exe"], capture_output=True)

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    label, side1, side2 = PHASES[phase_key]
    queue = build_jobs(label, side1, side2)

    from collections import Counter
    seen_tags = Counter()
    results = []
    loaded = None
    retried = set()
    i = 0
    while i < len(queue):
        base_tag, (c1, s1), (c2, s2), n1, n2 = queue[i]
        i += 1
        seen_tags[base_tag] += 1
        tag = base_tag if seen_tags[base_tag] == 1 else f"{base_tag}_r{seen_tags[base_tag]}"
        pair_key = (base_tag, n1, n2)

        print(f"\n===== {i}/{len(queue)}  {c1}/{s1} x{n1}  vs  {c2}/{s2} x{n2}  [{tag}] =====",
              flush=True)
        t_start = time.time()
        try:
            run_matchup(c1, s1, c2, s2,
                        name=f"{tag}.mp4", raw_copy_to=str(out),
                        fixed_counts=(n1, n2),
                        live_overlay=False, compose=False,
                        build_fn=build_golden_from_sides,
                        restart=False, dismiss_after=False,
                        logfile=str(out / "record.log"))
            loaded = pair_key
            status = None
        except Exception as e:
            print(f"[record] FAILED {tag}: {e!r}", flush=True)
            try:
                return_to_editor(str(out / "recover.log"))
            except Exception:
                pass
            loaded = None
            status = "record-failed"

        if status is None:
            raws = sorted(out.rglob("*.frames.bin"), key=lambda p: p.stat().st_mtime)
            if not raws or raws[-1].stat().st_mtime < t_start:
                print(f"[record] NO FRESH CAPTURE for {tag} — skipping decode", flush=True)
                status = "no-capture"
            else:
                pfx = str(raws[-1])[: -len(".frames.bin")]
                print(f"[decode] {pfx}", flush=True)
                rc = subprocess.run([sys.executable, str(DECODER), pfx,
                                     "--out", str(out / "decoded"), "--name", tag])
                status = "ok" if rc.returncode == 0 else "decode-failed"

                if status == "ok" and _positions_frozen(out, tag):
                    print(f"[record] {tag}: POSITIONS FROZEN — restarting the game", flush=True)
                    try:
                        from auto.restart_game import restart_and_enter_editor
                        ok = restart_and_enter_editor(logfile=str(out / "record.log"))
                        print(f"[record] game restart {'ok' if ok else 'FAILED'}", flush=True)
                    except Exception as e:
                        print(f"[record] game restart errored: {e!r}", flush=True)
                    loaded = None

                if status == "ok":
                    bad = _check_army(out, tag, [n1, n2])
                    if bad:
                        print(f"[record] WRONG ARMY for {tag}: got {bad} — discarding", flush=True)
                        _drop_decoded(out, tag)
                        seen_tags[base_tag] -= 1
                        status = "wrong-army"
                        loaded = None
                        if base_tag not in retried:
                            retried.add(base_tag)
                            queue.insert(i, (base_tag, (c1, s1), (c2, s2), n1, n2))
                            print(f"[record] {tag}: re-queued", flush=True)

                if rc.returncode == 0 and not KEEP_VIDEO:
                    for mov in Path(pfx).parent.glob(Path(pfx).name + ".mov"):
                        try:
                            mov.unlink()
                        except OSError:
                            pass

        results.append((tag, status))

        if loaded is not None and (i >= len(queue) or (queue[i][0], queue[i][3], queue[i][4]) != loaded):
            return_to_editor(str(out / "record.log"))
            loaded = None

    return results


if __name__ == "__main__":
    out_dir = sys.argv[1]
    phase = sys.argv[2] if len(sys.argv) > 2 else "all"
    phases = list(PHASES) if phase == "all" else [phase]
    all_results = []
    for p in phases:
        res = record_phase(out_dir, p)
        if isinstance(res, int):
            raise SystemExit(res)
        all_results.extend(res)
    print("\n===== DONE =====")
    for tag, st in all_results:
        print(f"  {'OK ' if st == 'ok' else '!! '} {tag}: {st}")

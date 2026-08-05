"""record_golden.py — record matchups for the SIMULATION-CALIBRATION golden set.

Unlike record_fights.py (which films analysis videos), this records for DATA only:
compose is off, so each fight costs a navigate + the fight itself, and what we keep
is the raw gRPC capture. Every fight is then decoded by aoe2x/grpc/decode_fight.py
into the full per-unit / per-hit ground-truth record.

Fight settings are the project's standard arena, unchanged: equal resources
(food 1.0 / wood 1.0 / gold 1.5, budget 3000), 21 units max per side, the golden
engagement templates (ddkMatchupAI patrol + NoneAi), no repeats.

  python record_golden.py <out_dir> <civ>/<slug> vs <civ>/<slug> [more pairs...]
  python record_golden.py <out_dir> --list matchups.json

Game must be open in the Scenario Editor, frontmost. Run with apps/video/.venv.
"""
import os
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))              # apps/video on path

DECODER = REPO / "aoe2x" / "grpc" / "decode_fight.py"
# set AOE2_GOLDEN_KEEP_VIDEO=1 to keep the .mov (eyeballing a suspicious fight)
KEEP_VIDEO = os.environ.get("AOE2_GOLDEN_KEEP_VIDEO", "").lower() in ("1", "true", "yes")
# Repeat a matchup by restarting it from the in-game menu instead of navigating again.
# OFF by default: on 2026-07-30 the menu's Restart was found and clicked, the confirm was
# answered, and the scenario still did not reload — the capture's game clock ran straight
# on from the previous fight (481 s of stream inside a 275 s recording) and the "repeat"
# decoded as the LEFTOVER 5 Paladins of the fight before it, with no enemy. It would have
# gone into the golden set as a real row. Set AOE2_GOLDEN_RESTART=1 to try it again;
# _check_army below is what makes that safe to attempt.
USE_RESTART = os.environ.get("AOE2_GOLDEN_RESTART", "").lower() in ("1", "true", "yes")


def parse_pairs(argv):
    """['A/a', 'vs', 'B/b', 'C/c', 'vs', 'D/d'] -> [((A,a),(B,b)), ((C,c),(D,d))]"""
    toks = [t for t in argv if t.lower() != "vs"]
    if len(toks) % 2:
        raise SystemExit("matchups must come in pairs")
    out = []
    for i in range(0, len(toks), 2):
        c1, s1 = toks[i].split("/", 1)
        c2, s2 = toks[i + 1].split("/", 1)
        out.append(((c1, s1), (c2, s2)))
    return out


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    out = Path(argv[0])
    if argv[1] == "--list":
        pairs = [((m["civ1"], m["slug1"]), (m["civ2"], m["slug2"]))
                 for m in json.loads(Path(argv[2]).read_text())]
    else:
        pairs = parse_pairs(argv[1:])
    results = record_many(out, pairs)
    print("\n===== DONE =====")
    for tag, st in results:
        print(f"  {'OK ' if st == 'ok' else '!! '} {tag}: {st}")
    return 0 if all(s == "ok" for _, s in results) else 1


def record_many(out, pairs, tag_offset=None, on_fight=None, followup=None):
    """Record + decode each (side1, side2) pair. Returns [(tag, status)].

    `tag_offset` seeds the repeat counter, so a caller adding MORE runs of a matchup
    already recorded in this directory continues the _r2/_r3 numbering instead of
    overwriting it.

    `on_fight(tag, status)` is called after each fight, for incremental shipping. It is
    wrapped in try/except: a failing hook must never cost us a recording session.

    `followup(tag, status)` returns how many EXTRA runs of the matchup just recorded to
    queue immediately after it. Repeats are appended right behind the fight that earned
    them, so each matchup is fully resolved before moving on. A repeat never earns
    further repeats — otherwise a genuinely coin-flip matchup would recurse forever.
    """
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    from auto.orchestrate_matchup import run_matchup, return_to_editor
    from auto.pure import equal_resource_counts
    from auto import grpc_capture
    from auto.config import GRPC_PYTHON, GRPC_LOGGER
    from build_golden_v2 import build_v2_from_sides as build_golden_from_sides

    # HARD FAIL, never a warning. For a VIDEO the gRPC stream is optional garnish (the
    # overlay falls back to the OCR readout), so orchestrate_matchup only logs and
    # carries on. For the golden set the stream IS the deliverable: without it a run
    # completes, looks healthy, and yields nothing. Caught 2026-07-29, when GRPC_PYTHON
    # defaulted to a .venv inside a git WORKTREE that has no venv of its own.
    if not grpc_capture.available():
        print("FATAL: gRPC capture unavailable — every fight would record zero data.\n"
              f"  AOE2_GRPC_PYTHON -> {GRPC_PYTHON}\n"
              f"  AOE2_GRPC_LOGGER -> {GRPC_LOGGER}\n"
              "  Set AOE2_GRPC_PYTHON to a python with grpcio (the main checkout's "
              "apps/video/.venv) and re-run.")
        return 2

    # The on-screen keyboard host steals foreground and eats injected keys (2026-07-20).
    subprocess.run(["taskkill", "/f", "/im", "TextInputHost.exe"], capture_output=True)

    results = []
    seen_tags = Counter(tag_offset or {})
    queue = [(p, False) for p in pairs]        # (pair, is_repeat)
    loaded = None      # matchup currently loaded in the game (None = back in the editor)
    retried = set()    # base tags already given a second chance after a wrong-army fight
    i = 0
    while i < len(queue):
        pair, is_repeat = queue[i]
        ((c1, s1), (c2, s2)) = pair
        i += 1
        base_tag = f"{s1}__vs__{s2}"
        tag = base_tag
        # Repeats of the SAME matchup get _r2, _r3 ... so they don't overwrite each
        # other's decoded output (the golden set is one run per matchup, but repeats are
        # how a surprising result gets checked for noise).
        seen_tags[base_tag] += 1
        if seen_tags[base_tag] > 1:
            tag = f"{base_tag}_r{seen_tags[base_tag]}"
        n1, n2 = equal_resource_counts(c1, s1, c2, s2, unit_cap=21)
        # Restarting is legal exactly when the scenario sitting in the game IS this
        # matchup — i.e. the previous fight was the same pair and we deliberately left it
        # loaded. Everything else takes the full build -> stage -> Load -> Test path.
        reuse = USE_RESTART and (loaded == pair)
        print(f"\n===== {i}/{len(queue)}  {c1}/{s1} x{n1}  vs  {c2}/{s2} x{n2}"
              f"{'  [repeat]' if is_repeat else ''}{'  [restart]' if reuse else ''} =====",
              flush=True)
        t_start = time.time()
        try:
            run_matchup(c1, s1, c2, s2,
                        name=f"{tag}.mp4", raw_copy_to=str(out),
                        mode="resources", unit_cap=21,
                        live_overlay=False, compose=False,
                        build_fn=build_golden_from_sides,
                        restart=reuse, dismiss_after=False,
                        logfile=str(out / "record.log"))
            loaded = pair
            status = None                      # decided below
        except Exception as e:
            print(f"[record] FAILED {tag}: {e!r}", flush=True)
            # Includes a Restart that never found its menu entry. Backing out to the
            # editor makes the next attempt take the full navigate path, which works from
            # a cold start — so a restart that goes wrong costs one fight, not the batch.
            try:
                return_to_editor(str(out / "recover.log"))
            except Exception:
                pass
            loaded = None
            status = "record-failed"

        if status is None:
            # archive_raw drops the capture in a "raw recordings/" SUBFOLDER of
            # raw_copy_to, not at its root — glob recursively or every decode silently
            # reports no-capture.
            raws = sorted(out.rglob("*.frames.bin"), key=lambda p: p.stat().st_mtime)
            # The capture must post-date THIS fight's start. Without that check a fight
            # whose recording silently failed would decode the PREVIOUS fight's capture
            # and file it under this matchup's name — a wrong row in the golden set, which
            # is far worse than a missing one. Over 91 unattended fights this will happen.
            if not raws or raws[-1].stat().st_mtime < t_start:
                print(f"[record] NO FRESH CAPTURE for {tag} — skipping decode", flush=True)
                status = "no-capture"
            else:
                pfx = str(raws[-1])[: -len(".frames.bin")]
                print(f"[decode] {pfx}", flush=True)
                rc = subprocess.run([sys.executable, str(DECODER), pfx,
                                     "--out", str(out / "decoded"), "--name", tag])
                status = "ok" if rc.returncode == 0 else "decode-failed"

                # A frozen position channel means the game session has gone stale. Every
                # further fight would record the same way -- valid-looking, spatially
                # useless -- so restart the game and carry on rather than burn the batch.
                # The tape itself is KEPT: its damage/hp are still good.
                if status == "ok" and _positions_frozen(out, tag):
                    print(f"[record] {tag}: POSITIONS FROZEN — restarting the game",
                          flush=True)
                    try:
                        from auto.restart_game import restart_and_enter_editor
                        ok = restart_and_enter_editor(logfile=str(out / "record.log"))
                        print(f"[record] game restart {'ok' if ok else 'FAILED'}",
                              flush=True)
                    except Exception as e:
                        print(f"[record] game restart errored: {e!r}", flush=True)
                    loaded = None

                if status == "ok":
                    bad = _check_army(out, tag, [n1, n2])
                    if bad:
                        print(f"[record] WRONG ARMY for {tag}: got {bad} — discarding",
                              flush=True)
                        _drop_decoded(out, tag)
                        seen_tags[base_tag] -= 1     # free the tag for the retry
                        status = "wrong-army"
                        loaded = None                # never restart off a suspect state
                        if base_tag not in retried:
                            retried.add(base_tag)
                            queue.insert(i, (pair, is_repeat))
                            print(f"[record] {tag}: re-queued once via full navigate",
                                  flush=True)

                # The screen recording is a by-product we never look at here: ~200 MB per
                # fight, ~24 GB across the 91-matchup batch. The gRPC stream is the artefact.
                if rc.returncode == 0 and not KEEP_VIDEO:
                    for mov in Path(pfx).parent.glob(Path(pfx).name + ".mov"):
                        try:
                            mov.unlink()
                        except OSError:
                            pass

        results.append((tag, status))
        _notify(on_fight, tag, status)

        # inline repeats: a close result is re-recorded immediately, so the matchup is
        # settled before we move on. Repeats never earn repeats of their own.
        if followup and status == "ok" and not is_repeat:
            try:
                n_more = int(followup(tag, status) or 0)
            except Exception as e:
                print(f"[record] followup hook failed for {tag}: {e!r}", flush=True)
                n_more = 0
            if n_more > 0:
                print(f"[record] {tag}: queueing {n_more} repeat(s)", flush=True)
                for k in range(n_more):
                    queue.insert(i + k, (pair, True))

        # Hold the scenario loaded ONLY while the next fight is the same matchup. Decided
        # here, after followup has queued its repeats — deciding it before the fight would
        # miss exactly the repeats this is meant to accelerate.
        if loaded is not None and (i >= len(queue) or queue[i][0] != loaded):
            return_to_editor(str(out / "record.log"))
            loaded = None

    return results


def _check_army(out, tag, want):
    """Did the decoded fight actually field the armies we asked for?

    The decoder records the segment's starting counts, so this is a direct check that the
    capture is the fight we think it is — not the tail of the previous one, not a reload
    that half-populated. Compared order-independently because P2/P3 assignment depends on
    the template. Returns None if it looks right, else a description of what arrived.

    Worth the six lines: a fight that records the wrong army still decodes cleanly and
    still looks like a valid row. There is no way to spot it downstream."""
    meta = Path(out) / "decoded" / f"{tag}.meta.json"
    if not meta.exists():
        return "no meta"
    try:
        got = list(json.loads(meta.read_text()).get("segment_start_counts") or [])
    except (OSError, ValueError) as e:
        return f"unreadable meta ({e})"
    return None if sorted(got) == sorted(want) else f"{got}, expected {sorted(want)}"


def _positions_frozen(out, tag):
    """Did this fight record every unit standing on its spawn tile? decode_fight sets the
    flag; a missing flag means an older decoder, so treat it as fine rather than restart
    the game on no evidence."""
    meta = Path(out) / "decoded" / f"{tag}.meta.json"
    try:
        return bool(json.loads(meta.read_text()).get("positions_frozen"))
    except (OSError, ValueError):
        return False


def _drop_decoded(out, tag):
    """Remove a bad fight's decoded output so a later pass re-records it."""
    for p in (Path(out) / "decoded").glob(f"{tag}.*"):
        try:
            p.unlink()
        except OSError:
            pass


def _notify(cb, tag, status):
    if not cb:
        return
    try:
        cb(tag, status)
    except Exception as e:                 # a shipping hiccup must not stop recording
        print(f"[record] on_fight hook failed for {tag}: {e!r}", flush=True)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main(sys.argv[1:]))

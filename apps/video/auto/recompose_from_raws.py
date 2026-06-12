"""recompose_from_raws.py — re-render matchup clips from their ARCHIVED raw recordings with
the CURRENT overlay/compose code (no game needed). Use after overlay/timing tweaks, or to
render a `run_guecha_sweep --record-only` sweep.

For each opponent whose raw exists: detect game-start, build (and SAVE next to the clip) the
OCR readout sidecar, then compose the final clip — overwriting it. The saved sidecar +
game-start let later re-renders skip the slow OCR pass (pass --reuse-ocr).

The compose is pure CPU (OCR + one ffmpeg encode), so it parallelizes cleanly: --jobs 3
renders three clips at once (each worker loads its own OCR model, ~200MB RAM apiece).

  python -m auto.recompose_from_raws                 # all matchups that have a raw
  python -m auto.recompose_from_raws --only Aztecs   # one (smoke test)
  python -m auto.recompose_from_raws --reuse-ocr     # reuse saved sidecars (fast)
  python -m auto.recompose_from_raws --jobs 3        # parallel render
  python -m auto.recompose_from_raws --opponent "Muisca:elite_temple_guard_muisca" \
      --out "D:/videos/temple_guard_sweep"           # a different fixed side
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
SB = HERE.parent
sys.path.insert(0, str(SB))

from auto import platform_io                                       # noqa: E402
from auto.run_guecha_sweep import unique_units, matchup_name, GUECHA, NAVAL, OUT_DIR  # noqa: E402
from auto.orchestrate_matchup import equal_resource_counts, resolve_side  # noqa: E402
from auto.record_until_end import (                                # noqa: E402
    select_sidecar, detect_game_start, PATROL_LEAD, log)


def recompose_one(fixed, civ, slug, nm, out_dir, mode, unit_cap, reuse_ocr, logf):
    """Render ONE matchup clip from its archived raw. `fixed` = (civ, slug, label) of the
    constant side. Top-level (picklable) so --jobs can fan it out across processes."""
    from overlay.overlay_data import get_unit_card
    from overlay.compose import make_live_overlay_video, _duration
    out_dir = Path(out_dir)
    name = matchup_name(civ, nm, fixed=fixed)
    raw = out_dir / "raw recordings" / (Path(name).stem + ".mov")
    if not raw.exists():
        log(f"[skip] no raw for {nm} ({civ})", logf)
        return False
    clip = out_dir / name
    ocr_path = out_dir / (Path(name).stem + ".ocr.hp.json")
    counts = (equal_resource_counts(fixed[0], fixed[1], civ, slug, unit_cap)
              if mode == "resources" else (unit_cap, unit_cap))

    # Game-time zero = the load->game pixel transition (frame-accurate, no OCR); the
    # clip starts a fixed PATROL_LEAD after that anchor. Sidecar preference: sane gRPC
    # redecode (exact game data, archived next to the raw by a record-only sweep —
    # zero OCR) > OCR readout (+HP merge).
    v0 = detect_game_start(str(raw))
    grpc_sc = str(raw.with_suffix("")) + ".hp.json"
    if (Path(str(raw.with_suffix("")) + ".frames.bin")).exists():
        # archived sidecars may predate the delta-decoder fix / the game-sim->video
        # clock conversion — rebuild from the raw stream once (the rebuilt sidecar
        # carries clock="video" and is reused on later passes)
        try:
            with open(grpc_sc) as f:
                old = json.load(f)
        except Exception:
            old = {}
        if old.get("clock") != "video":
            from auto import grpc_capture
            grpc_capture.write_sidecar(str(raw.with_suffix("")),
                                       old.get("recorder_start_epoch", 0.0), logfile=logf)
    oc, src = select_sidecar(
        str(raw), v0, grpc_sc if Path(grpc_sc).exists() else None,
        fixed[0], fixed[1], civ, slug, counts, str(ocr_path),
        str(clip), reuse_ocr=reuse_ocr, logfile=logf)
    if not oc:
        log(f"[skip] no usable timeline for {nm} ({civ})", logf)
        return False
    try:
        with open(oc) as f:
            gs = json.load(f).get("video_game_start_s")
    except Exception:
        gs = None
    lead_in = (gs if gs is not None else (v0 if v0 is not None else 6.0)) + PATROL_LEAD

    u1 = get_unit_card(fixed[0], fixed[1])
    u2 = get_unit_card(civ, slug)
    make_live_overlay_video(u1, u2, str(clip), str(raw), oc, lead_in=lead_in,
                            counts=counts, size=(platform_io.OUT_W, platform_io.OUT_H))
    log(f"[recompose] {nm} ({civ})  lead_in={lead_in:.1f}  -> {clip.name} "
        f"({_duration(clip):.1f}s)", logf)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--only", default=None)
    ap.add_argument("--start", type=int, default=0, help="start at opponent index (for parallel slices)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--opponent", default=None, metavar="CIV:slug",
                    help="the FIXED side of the sweep (default: the Guecha)")
    ap.add_argument("--mode", choices=["resources", "count"], default="resources")
    ap.add_argument("--unit-cap", type=int, default=30)
    ap.add_argument("--reuse-ocr", action="store_true")
    ap.add_argument("--jobs", type=int, default=1,
                    help="parallel render processes (3 is a good default on 8+ cores)")
    a = ap.parse_args()
    out_dir = Path(a.out)
    logf = str(out_dir / "_recompose.log")
    open(logf, "a").close()

    if a.opponent:
        oc, os_ = a.opponent.split(":", 1)
        fixed = resolve_side(oc, os_)            # -> (civ, unit_key, label)
        fixed = (oc, os_, fixed[2])
    else:
        fixed = GUECHA

    opp = [(c, s, n) for c, s, n in unique_units() if s != fixed[1] and s not in NAVAL]
    if a.only:
        opp = [o for o in opp if o[0].lower() == a.only.lower()]
    if a.start:
        opp = opp[a.start:]
    if a.limit:
        opp = opp[:a.limit]

    log(f"=== RECOMPOSE {len(opp)} clips (PATROL_LEAD={PATROL_LEAD}, "
        f"reuse_ocr={a.reuse_ocr}, jobs={a.jobs}) ===", logf)
    t0 = time.time()
    done = 0
    if a.jobs > 1:
        with ProcessPoolExecutor(max_workers=a.jobs) as ex:
            futs = {ex.submit(recompose_one, fixed, civ, slug, nm, str(out_dir),
                              a.mode, a.unit_cap, a.reuse_ocr, logf): (civ, nm)
                    for civ, slug, nm in opp}
            for i, f in enumerate(as_completed(futs), 1):
                civ, nm = futs[f]
                try:
                    done += bool(f.result())
                    log(f"[{i}/{len(opp)}] {nm} ({civ}) finished  "
                        f"(elapsed {int(time.time()-t0)}s)", logf)
                except Exception as e:
                    log(f"[{i}/{len(opp)}] FAILED {nm}: {type(e).__name__}: {e}", logf)
    else:
        for i, (civ, slug, nm) in enumerate(opp):
            log(f"[{i+1}/{len(opp)}] {nm} ({civ})  (elapsed {int(time.time()-t0)}s)", logf)
            try:
                if recompose_one(fixed, civ, slug, nm, str(out_dir),
                                 a.mode, a.unit_cap, a.reuse_ocr, logf):
                    done += 1
            except Exception as e:
                log(f"[{i+1}/{len(opp)}] FAILED {nm}: {type(e).__name__}: {e}", logf)
    log(f"=== RECOMPOSE DONE: {done}/{len(opp)} in {int(time.time()-t0)}s ===", logf)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()

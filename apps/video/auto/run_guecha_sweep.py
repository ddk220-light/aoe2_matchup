"""run_guecha_sweep.py — batch end-to-end: Muisca Elite Guecha Warrior vs EVERY unique
unit, each rendered as a ~20s live-overlay clip (detail cards over the battle + top
draining HP bar + captured audio), then stitched into one compilation.

  python -m auto.run_guecha_sweep                 # full sweep (resumes; skips done clips)
  python -m auto.run_guecha_sweep --only Aztecs   # one matchup (smoke test)
  python -m auto.run_guecha_sweep --limit 3       # first 3 opponents
  python -m auto.run_guecha_sweep --stitch-only    # just re-join existing clips

Resumable: a matchup whose final mp4 already exists in the out dir is skipped. Each run
is isolated — a failure is logged and the sweep continues to the next matchup. All RAW
recordings are archived (out/raw recordings/) and the audio is captured with the video.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SB = HERE.parent
sys.path.insert(0, str(SB))

from auto import input_driver as ui, platform_io          # noqa: E402
from auto.orchestrate_matchup import run_matchup, return_to_editor, bring_game_to_front  # noqa: E402
from auto.record_until_end import log                     # noqa: E402

from auto.config import GUECHA_OUT as OUT_DIR                       # noqa: E402

GUECHA = ("Muisca", "elite_guecha_warrior_muisca", "Elite Guecha Warrior")
NAVAL = {"elite_turtle_ship_koreans", "elite_caravel_portuguese"}
COMPILATION = "Elite Guecha Warrior vs All Unique Units.mp4"


def unique_units():
    """EVERY validated unique unit — a civ with several uniques fields them ALL
    (Wei: Xianbei Raider AND Tiger Cavalry; Tatars: Keshik AND Flaming Camel...).
    Source: the same validated enumeration unique_units.json is generated from, so
    the sweep and the json list can't drift apart. (This used to reduce to one unit
    per civ, which silently made every civ's second unique unsweepable.)"""
    from auto.build_unique_list import enumerate_uniques
    return [(u["civ"], u["slug"], u["name"]) for u in enumerate_uniques()[0]]


def _safe(s: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", s).strip()


def matchup_name(opp_civ, opp_name, fixed=GUECHA) -> str:
    return _safe(f"{fixed[2]} vs {opp_name} ({fixed[0]} vs {opp_civ})") + ".mp4"


def opponents(include_naval=False):
    out = []
    for civ, slug, nm in unique_units():
        if slug == GUECHA[1]:
            continue
        if slug in NAVAL and not include_naval:
            continue
        out.append((civ, slug, nm))
    return out


def stitch(out_dir: Path, clips: list[Path], logfile=None) -> Path | None:
    """Join the per-matchup clips into the compilation + write the matching YouTube
    chapter markers (cumulative start time per matchup, labeled by the opponent)."""
    clips = [c for c in clips if c and Path(c).exists()]
    if not clips:
        log("[stitch] no clips to join", logfile)
        return None
    from overlay.compose import concat_videos, _duration
    from auto.batch_matchups import write_chapters, _civ_adj
    dest = out_dir / COMPILATION
    log(f"[stitch] joining {len(clips)} clips -> {dest}", logfile)
    concat_videos([str(c) for c in clips], dest)
    log(f"[stitch] DONE -> {dest} ({dest.stat().st_size // 1048576} MB)", logfile)
    # chapter label = the OPPONENT in clip order; clip names are
    # "<fixed> vs <opponent name> (<fixed civ> vs <opp civ>).mp4"
    entries = []
    for c in clips:
        m = re.match(r".+ vs (.+) \((.+) vs (.+)\)$", Path(c).stem)
        label = f"{_civ_adj(m.group(3))} {m.group(1)}" if m else Path(c).stem
        entries.append((label, _duration(c)))
    ch = write_chapters(entries, out_dir / (Path(COMPILATION).stem + " chapters.txt"))
    log(f"[stitch] chapters -> {ch}", logfile)
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--only", default=None, help="run only this opponent civ (smoke test)")
    ap.add_argument("--limit", type=int, default=0, help="only the first N opponents")
    ap.add_argument("--start", type=int, default=0, help="start at opponent index")
    ap.add_argument("--include-naval", action="store_true")
    ap.add_argument("--mode", choices=["resources", "count"], default="resources")
    ap.add_argument("--unit-cap", type=int, default=30)
    ap.add_argument("--cap", type=int, default=150, help="per-fight watch cap (s)")
    ap.add_argument("--no-stitch", action="store_true")
    ap.add_argument("--stitch-only", action="store_true")
    ap.add_argument("--record-only", action="store_true",
                    help="record + archive raws only (no compose); render afterwards "
                         "with `python -m auto.recompose_from_raws --jobs 3`. Roughly "
                         "halves sweep wall-clock: the game runs are wait-bound, the "
                         "compose is CPU-bound, and they no longer alternate.")
    ap.add_argument("--force", action="store_true", help="re-run even if the clip exists")
    a = ap.parse_args()

    out_dir = Path(a.out); out_dir.mkdir(parents=True, exist_ok=True)
    logf = str(out_dir / "_sweep.log")
    open(logf, "a").close()

    opp = opponents(a.include_naval)
    if a.only:
        opp = [o for o in opp if o[0].lower() == a.only.lower()]
    if a.start:
        opp = opp[a.start:]
    if a.limit:
        opp = opp[:a.limit]

    # in clip order = matchup order (so the compilation reads alphabetically by civ)
    expected_clips = [out_dir / matchup_name(c, nm) for c, s, nm in opp]

    if a.stitch_only:
        stitch(out_dir, expected_clips, logf)
        return

    log(f"=== GUECHA SWEEP: {len(opp)} matchups, mode={a.mode}, cap={a.cap}s -> {out_dir} ===", logf)
    if not platform_io.recorder_available():
        log(f"ERROR: recorder unavailable — {platform_io.recorder_hint()}", logf)
        sys.exit(2)
    # confirm the game is reachable before committing to a long unattended sweep
    st = bring_game_to_front(logf)
    log(f"[preflight] game screen: {st}", logf)
    if st not in ("editor", "main_menu", "load_dialog", "in_game", "end_screen"):
        log("ERROR: AoE2:DE not detected in a known screen. Open it in the Scenario "
            "Editor (or its Load page), frontmost, and retry.", logf)
        sys.exit(2)

    done, failed = [], []
    t0 = time.time()
    for i, (civ, slug, nm) in enumerate(opp):
        name = matchup_name(civ, nm)
        # record-only counts a matchup done when its RAW exists; normal mode, the clip
        dest = (out_dir / "raw recordings" / (Path(name).stem + ".mov")
                if a.record_only else out_dir / name)
        tag = f"[{i+1}/{len(opp)}] {nm} ({civ})"
        if dest.exists() and not a.force:
            log(f"{tag}: already done -> skip", logf)
            done.append(dest)
            continue
        log(f"{tag}: START  (elapsed {int(time.time()-t0)}s)", logf)
        try:
            final = run_matchup(
                GUECHA[0], GUECHA[1], civ, slug,
                name=name, copy_to=str(out_dir), raw_copy_to=str(out_dir),
                cap=a.cap, mode=a.mode, unit_cap=a.unit_cap, live_overlay=True,
                compose=not a.record_only, logfile=logf)
            done.append(Path(final))
            log(f"{tag}: OK -> {final}", logf)
        except Exception as e:
            failed.append((civ, nm, str(e)))
            log(f"{tag}: FAILED -> {e}", logf)
            try:
                return_to_editor(logf)         # recover so the next matchup can start clean
            except Exception:
                pass
            time.sleep(2.0)

    log(f"=== SWEEP COMPLETE: {len(done)} ok, {len(failed)} failed, "
        f"{int(time.time()-t0)}s ===", logf)
    for civ, nm, err in failed:
        log(f"  FAILED {nm} ({civ}): {err}", logf)

    if a.record_only:
        log(f"[record-only] raws archived. Render them with:\n"
            f"  python -m auto.recompose_from_raws --out \"{out_dir}\" --jobs 3\n"
            f"then stitch with:  python -m auto.run_guecha_sweep --out \"{out_dir}\" "
            f"--stitch-only", logf)
        return

    if not a.no_stitch:
        # stitch in matchup order, including any previously-completed clips
        stitch(out_dir, expected_clips, logf)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()

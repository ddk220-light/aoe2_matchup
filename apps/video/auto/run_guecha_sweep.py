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
from auto.chapters import write_chapters, _civ_adj         # noqa: E402
from auto.orchestrate_matchup import run_matchup, return_to_editor, bring_game_to_front  # noqa: E402
from auto.queue_runner import run_matchup_queue, _load_manifest  # noqa: E402
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


def _chapter_label(civ, opp_name) -> str:
    """Chapter label for a matchup = '<civ adjective> <opponent unit>'."""
    return f"{_civ_adj(civ)} {opp_name}"


def stitch(out_dir: Path, expected: list[Path], logfile=None) -> Path | None:
    """Join the per-matchup clips into the compilation + write the matching YouTube
    chapter markers (cumulative start time per matchup, labeled by the opponent).

    Labels come from manifest.json (written per clip by the queue runner) — the clip
    `label` and `path`, in manifest order. Falls back to filename parsing for any
    manifest-less clip (e.g. a stitch-only run over a folder recorded elsewhere)."""
    from overlay.compose import concat_videos, _duration
    manifest = _load_manifest(out_dir)

    pairs = []            # (label, clip_path) in order
    if manifest["clips"]:
        for c in manifest["clips"]:
            if c.get("status") == "done" and c.get("path") and Path(c["path"]).exists():
                label = c.get("label") or Path(c["path"]).stem
                pairs.append((label, c["path"]))
    else:
        for c in expected:
            if c and Path(c).exists():
                m = re.match(r".+ vs (.+) \((.+) vs (.+)\)$", Path(c).stem)
                label = f"{_civ_adj(m.group(3))} {m.group(1)}" if m else Path(c).stem
                pairs.append((label, str(c)))

    if not pairs:
        log("[stitch] no clips to join", logfile)
        return None
    dest = out_dir / COMPILATION
    log(f"[stitch] joining {len(pairs)} clips -> {dest}", logfile)
    concat_videos([p for _, p in pairs], dest)
    log(f"[stitch] DONE -> {dest} ({dest.stat().st_size // 1048576} MB)", logfile)
    entries = [(lbl, _duration(p)) for lbl, p in pairs]
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

    # ---- BUILD THE QUEUE -------------------------------------------------
    # Each spec carries name (stem)/label/category so the manifest — not filenames —
    # drives stitch + chapters. matchup_name() keeps the ".mp4" for the on-disk clip;
    # the queue runner's resume-skip checks out_dir/{name}.mp4, so name = the stem.
    specs = []
    for civ, slug, nm in opp:
        stem = Path(matchup_name(civ, nm)).stem
        specs.append(dict(civ1=GUECHA[0], slug1=GUECHA[1], civ2=civ, slug2=slug,
                          name=stem, label=_chapter_label(civ, nm),
                          category="matchup", opp_name=nm))

    # --force: drop prior done clips so they re-record (delete the mp4 the queue checks).
    if a.force:
        for s in specs:
            clip = out_dir / f"{s['name']}.mp4"
            if clip.exists():
                clip.unlink()
    # record-only resume: the queue skips on {name}.mp4, but record-only produces a raw
    # .mov and no .mp4 — so pre-skip specs whose RAW already exists (mirrors the old
    # per-mode skip target).
    if a.record_only and not a.force:
        keep = []
        for s in specs:
            raw = out_dir / "raw recordings" / f"{s['name']}.mov"
            if raw.exists():
                log(f"{s['label']}: raw already done -> skip", logf)
            else:
                keep.append(s)
        specs = keep

    t0 = time.time()

    def run_one(spec, _out_dir):
        log(f"{spec['label']}: START  (elapsed {int(time.time()-t0)}s)", logf)
        final = run_matchup(
            GUECHA[0], GUECHA[1], spec["civ2"], spec["slug2"],
            name=f"{spec['name']}.mp4", copy_to=str(out_dir), raw_copy_to=str(out_dir),
            cap=a.cap, mode=a.mode, unit_cap=a.unit_cap, live_overlay=True,
            compose=not a.record_only, logfile=logf)
        log(f"{spec['label']}: OK -> {final}", logf)
        return Path(final)

    res = run_matchup_queue(specs, out_dir, run_one=run_one,
                            on_recover=lambda: (return_to_editor(logf), time.sleep(2.0)))

    log(f"=== SWEEP COMPLETE: {len(res.done) + len(res.skipped)} ok, "
        f"{len(res.failed)} failed, {int(time.time()-t0)}s ===", logf)
    for s in res.failed:
        log(f"  FAILED {s.get('opp_name', s['name'])} ({s['civ2']})", logf)

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

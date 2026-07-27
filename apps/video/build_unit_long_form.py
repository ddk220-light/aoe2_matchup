"""build_unit_long_form.py — assemble the long-form unit-analysis video for ANY subject.

Generalization of build_etg_long_form.py (kept for history): same parchment card
family, same brief, but everything derives from the categorization JSON instead of
hand-coded clip names / copy / coin-flip odds. Plus the voice-line intro the ETG
one-off predates: the civ's military attack barks play over the animated hero card.

    python build_unit_long_form.py --subject "Incas:elite_champi_warrior" \
        --cat sim_v2/_work/elite_champi_warrior/categorized.json \
        --clips-dir "C:/Users/ddk22/Videos/aoe2_matchups/champi_sweep" \
        --out "C:/Users/ddk22/Videos/aoe2_matchups/champi_sweep/Elite Champi Warrior - Counters and Matchups.mp4"

Expects fight clips named `<category>_<rank>_<oppslug>.mp4` in --clips-dir — exactly
what `sim_v2/record_fights.py <civ> <slug> <category> <dir> <opps...>` produces when
invoked once per category with the filmed picks in order.

Brief rules (user, 2026-07-19):
- category order: expected_win -> expected_loss -> unexpected_win -> unexpected_loss
  (surprises last), then the coin-flip odds card, then the outro.
- EMPTY categories say NOTHING (no card, no chapter).
- ranking card only when a category has >= 4 rows (fewer = all were on camera).
- coin-flip: no fights, one odds card (odds = sim win-rate, subject : opponent).
Run with the MAIN checkout's apps/video/.venv python and AOE2_MEDIA_DIR set (voices
+ attack gifs); the script refuses to run silently degraded.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from overlay.intro_card import make_unit_intro_video, make_outro_thanks_video
from overlay.category_card import (make_category_explanation_card,
                                   make_category_ranking_card,
                                   make_coinflip_odds_card)
from overlay.compose import (_card_segment, concat_videos, _duration, _ffmpeg, _run,
                             _x264, _AAC, voice_track)
from overlay.assets import AssetResolver
from auto.chapters import write_chapters

SIZE = (2560, 1440)

# --- durations (seconds) — per the ETG brief ---------------------------------
INTRO_S = 3.5
EXPLAIN_S = 5.0
RANK_S = 8.0
COINFLIP_S = 6.0
OUTRO_S = 6.0

CATEGORY_ORDER = ("expected_win", "expected_loss", "unexpected_win", "unexpected_loss")

TITLES = {
    "expected_win": "Expected Wins",
    "expected_loss": "Expected Losses",
    "unexpected_win": "Unexpected Wins",
    "unexpected_loss": "Unexpected Losses",
}
TITLES_SINGULAR = {
    "expected_win": "Expected Win",
    "expected_loss": "Expected Loss",
    "unexpected_win": "Unexpected Win",
    "unexpected_loss": "Unexpected Loss",
}


def _copy_for(cat: str, short: str, n: int) -> str:
    """Explanation-card copy, derived from the category + counts (no hand-writing)."""
    return {
        "expected_win": (f"On paper, the {short} holds the edge in these fights — "
                         f"and the field agrees. {n} matchups tested, {n} wins."),
        "expected_loss": (f"These units hold the advantage over the {short}. "
                          f"It loses — as expected. {n} matchups, {n} losses."),
        "unexpected_win": (f"On paper, these units beat the {short}. "
                           f"On the field, it beats them."),
        "unexpected_loss": (f"On paper, the {short} has the advantage here. "
                            f"It loses anyway."),
    }[cat]


def _log(msg):
    print(f"[build] {msg}", flush=True)


def _wrap_hero_video(src_mp4: Path, out_mp4: Path, audio_wav: Path | None) -> Path:
    """Normalize an animated hero card (1920x1080@30, silent) to the fight clips'
    2560x1440 / 60fps / h264 / AAC format, with the voice track (or silence)."""
    if audio_wav is not None:
        a_in = ["-i", str(audio_wav)]
    else:
        a_in = ["-f", "lavfi", "-t", f"{_duration(src_mp4):.3f}",
                "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
    _run([_ffmpeg(), "-y", "-i", str(src_mp4), *a_in,
          "-vf", f"scale={SIZE[0]}:{SIZE[1]}:flags=lanczos,fps=60",
          "-map", "0:v", "-map", "1:a", "-shortest",
          *_x264(), *_AAC, "-movflags", "+faststart", str(out_mp4)])
    return out_mp4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", required=True, metavar="Civ:slug")
    ap.add_argument("--cat", required=True, help="categorized.json (rows + filmed)")
    ap.add_argument("--clips-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--work-dir", default=None)
    ap.add_argument("--skip-coinflip", action="store_true",
                    help="omit the Too Close To Call odds card (user 2026-07-26: "
                         "the toss-up list doesn't add much value)")
    a = ap.parse_args()

    civ, slug = a.subject.split(":", 1)
    clips_dir = Path(a.clips_dir)
    out_mp4 = Path(a.out)
    work = Path(a.work_dir) if a.work_dir else out_mp4.parent / "_build_work"
    work.mkdir(parents=True, exist_ok=True)

    d = json.loads(Path(a.cat).read_text(encoding="utf-8"))
    subj = d["subject"]
    assert (subj["civ"], subj["slug"]) == (civ, slug), \
        f"--subject {civ}:{slug} does not match {a.cat} ({subj['civ']}:{subj['slug']})"
    short = subj["name"].replace("Elite ", "")

    assets = AssetResolver()
    if assets.root is None:
        sys.exit("AOE2_MEDIA_DIR is not set — voices/gifs would silently degrade. "
                 "Set it to <main checkout>/apps/video/media and re-run.")
    voices = assets.voice_lines(civ)
    _log(f"media root ok; {len(voices)} voice lines for {civ}")

    rows_by_cat: dict[str, list[dict]] = {}
    for r in d["rows"]:
        rows_by_cat.setdefault(r["category"], []).append(r)
    filmed = {k: [tuple(p) for p in v] for k, v in d["filmed"].items()}
    coinflip_rows = rows_by_cat.get("coin_flip", [])
    n_total = len(d["rows"])

    # rows within a category, ordered for the ranking card: wins most-expensive
    # first, losses cheapest first (same rule the filmed picks use)
    def cat_rows(cat):
        rows = rows_by_cat.get(cat, [])
        rev = "win" in cat
        return sorted(rows, key=lambda r: (r.get("cost") or 0) * (-1 if rev else 1))

    active = [c for c in CATEGORY_ORDER if rows_by_cat.get(c)]
    _log("counts: " + " ".join(f"{c}={len(rows_by_cat.get(c, []))}" for c in
                               (*CATEGORY_ORDER, "coin_flip")) + f" total={n_total}")

    chapters: list[tuple[str, list[Path]]] = []
    seg_i = [0]

    def next_seg(prefix: str) -> Path:
        seg_i[0] += 1
        return work / f"seg_{seg_i[0]:03d}_{prefix}.mp4"

    def png_segment(png: Path, seconds: float, out: Path) -> Path:
        return _card_segment(png, seconds, out, SIZE, card_width_frac=1.0)

    # combat dicts for the intro stat card: the categorization's own workdir copy
    # (falls back to intro_card's module default when absent)
    cd_json = Path(a.cat).parent / "combat_dicts_all.json"
    intro_kw = {"json_path": cd_json} if cd_json.exists() else {}

    # ---- 1. Intro (voice barks over the animated hero card) -------------------
    _log("rendering intro (animated hero card + voice lines)...")
    raw_intro = next_seg("intro_raw")
    make_unit_intro_video(civ, slug, raw_intro, duration_s=INTRO_S, **intro_kw)
    track, n_used = (voice_track(voices, INTRO_S, work / "intro_voice.wav")
                     if voices else (None, 0))
    intro_seg = _wrap_hero_video(raw_intro, next_seg("intro"), track)
    chapters.append(("Intro", [intro_seg]))
    _log(f"intro ok ({_duration(intro_seg):.2f}s, voice lines={n_used})")

    # ---- 2. Category sections -------------------------------------------------
    for idx, cat in enumerate(active, start=1):
        rows = cat_rows(cat)
        title = TITLES[cat]
        _log(f"rendering {title} ({len(rows)} rows, step {idx}/{len(active)})...")
        expl_png = work / f"card_expl_{cat}.png"
        img = make_category_explanation_card(
            title, _copy_for(cat, short, len(rows)), idx, len(active), cat)
        img.convert("RGB").save(expl_png)
        chapters.append((title, [png_segment(expl_png, EXPLAIN_S, next_seg(f"expl_{cat}"))]))

        by_key = {(r["civ"], r["slug"]): r for r in rows}
        for rank, oppkey in enumerate(filmed.get(cat, []), start=1):
            row = by_key[tuple(oppkey)]
            clip = clips_dir / f"{cat}_{rank}_{row['slug']}.mp4"
            assert clip.exists(), f"missing fight clip: {clip}"
            chapters.append((f"{TITLES_SINGULAR[cat]} — {row['name']} ({row['civ']})", [clip]))
            _log(f"fight clip ok: {clip.name} ({_duration(clip):.2f}s)")

        if len(rows) >= 4:
            rank_png = work / f"card_rank_{cat}.png"
            img = make_category_ranking_card(title, rows, filmed.get(cat, []), cat,
                                             subject_short=subj["name"])
            img.convert("RGB").save(rank_png)
            chapters.append((f"{title} — full ranking",
                             [png_segment(rank_png, RANK_S, next_seg(f"rank_{cat}"))]))
        else:
            _log(f"{title}: {len(rows)} rows < 4 — no ranking card")

    # ---- 3. Coin-flips close ---------------------------------------------------
    if a.skip_coinflip:
        _log("coin-flip card skipped (--skip-coinflip)")
        coinflip_rows = []
    if coinflip_rows:
        _log(f"rendering coin-flip odds card ({len(coinflip_rows)} rows)...")
        disp = []
        for r in sorted(coinflip_rows, key=lambda r: -(r.get("wr") or 0.5)):
            wr = r.get("wr")
            odds = (f"{round(wr * 100)} : {round((1 - wr) * 100)}"
                    if wr is not None else "50 : 50")
            disp.append(dict(name=r["name"], civ=r["civ"], odds=odds))
        img = make_coinflip_odds_card(
            "Too Close To Call", disp,
            "These could go either way — full numbers at AOE2MATCHUP.COM.",
            category_key="coin_flip")
        png = work / "card_coinflip.png"
        img.convert("RGB").save(png)
        chapters.append(("Too Close To Call",
                         [png_segment(png, COINFLIP_S, next_seg("coinflip"))]))
    else:
        _log("no coin-flips — card skipped")

    # ---- 4. Outro --------------------------------------------------------------
    _log("rendering outro thanks...")
    raw_outro = next_seg("outro_raw")
    make_outro_thanks_video(civ, slug, raw_outro, duration_s=OUTRO_S)
    outro_seg = _wrap_hero_video(raw_outro, next_seg("outro"), None)
    chapters.append(("Thanks + aoe2matchup.com", [outro_seg]))

    # ---- concat + chapters -----------------------------------------------------
    all_segs = [s for _, segs in chapters for s in segs]
    _log(f"concatenating {len(all_segs)} segments -> {out_mp4}")
    concat_videos(all_segs, out_mp4)

    chap_entries = [(label, sum(_duration(s) for s in segs)) for label, segs in chapters]
    chapters_txt = out_mp4.with_suffix(".chapters.txt")
    write_chapters(chap_entries, chapters_txt)

    _log(f"DONE: {out_mp4} ({_duration(out_mp4):.2f}s total)")
    for label, dur in chap_entries:
        _log(f"  {label}: {dur:.2f}s")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()

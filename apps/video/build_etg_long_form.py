"""build_etg_long_form.py — one-off assembly script for the final Elite Temple
Guard (Muisca) long-form unit-analysis video.

Hand-builds the segment list in the brief's exact order (intro -> expected
wins -> expected losses -> unexpected losses -> coin-flip close -> outro
thanks) and stitches it directly with the low-level primitives
(overlay.compose._card_segment / concat_videos / _duration,
auto.chapters.write_chapters) rather than going through
auto.run_unit_analysis_video.build_plan (whose CATEGORY_ORDER and
empty-category skip don't match this brief) or auto.stitch_analysis.
stitch_analysis_video (built for the older non-parchment card family).

EMPTY-CATEGORY RULE (user rule 2026-07-19): a category with zero filmed/ranked
matchups says NOTHING in the finished video — no explanation card, no ranking
card, no chapter, not even a placeholder. Elite Temple Guard's "Unexpected
Wins" category has 0 rows (`unexp_win_rows` below, computed from the results
JSON same as every other category), so its entire segment is omitted from the
`chapters` list this script builds. `overlay.category_card.make_zero_category_card`
(the old "NONE" zero-state card) is intentionally left UNCALLED here — it
stays defined in category_card.py for a future storyboard that wants to
explicitly call out an empty category rather than silently skip it.

All cards render via the new parchment card family:
  overlay.intro_card.make_unit_intro_video          — animated hero intro
  overlay.intro_card.make_outro_thanks_video         — animated closing "thank you"
  overlay.category_card.make_category_explanation_card
  overlay.category_card.make_category_ranking_card
  overlay.category_card.make_coinflip_odds_card

Progress markers on the explanation cards read "i / 3" (Expected Wins 1/3,
Expected Losses 2/3, Unexpected Losses 3/3) — 3, not 4, because the skipped
Unexpected Wins category no longer counts as a storyboard step. The coin-flip
close and the outro carry no progress marker (neither did before).

Every segment is normalized to 2560x1440 @ 60fps h264/yuv420p + AAC 48k
stereo — the recorded fight clips' native format — so concat_videos'
stream-copy-first path has the best chance of joining without a re-encode
(it falls back to a filter_complex re-encode automatically if params drift).

Run: python build_etg_long_form.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from overlay.intro_card import make_unit_intro_video, make_outro_thanks_video
from overlay.category_card import (make_category_explanation_card,
                                   make_category_ranking_card,
                                   make_coinflip_odds_card)
from overlay.compose import _card_segment, concat_videos, _duration, _ffmpeg, _run, _x264, _AAC
from auto.chapters import write_chapters

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_JSON = Path(__file__).parent / "sim_v2" / "results" / "elite_temple_guard_muisca.json"
CLIPS_DIR = Path(r"C:\Users\ddk22\Videos\aoe2_matchups\etg_sweep_v2")
OUT_DIR = CLIPS_DIR
OUT_MP4 = OUT_DIR / "Elite Temple Guard - Counters and Matchups.mp4"
WORK_DIR = OUT_DIR / "_build_work"

SIZE = (2560, 1440)
SUBJECT_SHORT = "Elite Temple Guard"

# --- durations (seconds) — per brief -----------------------------------------
INTRO_S = 3.5
EXPLAIN_S = 5.0
RANK_S = 8.0
COINFLIP_S = 6.0
OUTRO_S = 6.0


def _log(msg):
    print(f"[build] {msg}", flush=True)


def _wrap_intro_video(src_mp4: Path, out_mp4: Path) -> Path:
    """Normalize an animated hero card's raw output (1920x1080, 30fps, no audio —
    shared by make_unit_intro_video and make_outro_thanks_video) to the common
    2560x1440 / 60fps / h264 / yuv420p / AAC-48k-stereo segment format."""
    _run([_ffmpeg(), "-y", "-i", str(src_mp4),
          "-f", "lavfi", "-t", f"{_duration(src_mp4):.3f}",
          "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
          "-vf", f"scale={SIZE[0]}:{SIZE[1]}:flags=lanczos,fps=60",
          "-map", "0:v", "-map", "1:a",
          *_x264(), *_AAC, "-movflags", "+faststart", str(out_mp4)])
    return out_mp4


def _png_segment(png: Path, seconds: float, out: Path) -> Path:
    """Full-bleed 1920x1080 parchment card -> 2560x1440 held segment (same
    aspect ratio, so card_width_frac=1.0 fills the frame exactly, no bars)."""
    return _card_segment(png, seconds, out, SIZE, card_width_frac=1.0)


def main():
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    d = json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
    subj = d["subject"]
    civ, slug = subj["civ"], subj["slug"]

    rows_by_cat: dict[str, list[dict]] = {}
    for r in d["rows"]:
        rows_by_cat.setdefault(r["category"], []).append(r)
    filmed = {k: [tuple(p) for p in v] for k, v in d["filmed"].items()}

    exp_win_rows = sorted(rows_by_cat.get("expected_win", []), key=lambda r: -(r.get("cost") or 0))
    exp_loss_rows = sorted(rows_by_cat.get("expected_loss", []), key=lambda r: (r.get("cost") or 0))
    unexp_win_rows = rows_by_cat.get("unexpected_win", [])
    unexp_loss_rows = rows_by_cat.get("unexpected_loss", [])
    coinflip_rows = rows_by_cat.get("coin_flip", [])

    n_expected_win = len(exp_win_rows)
    n_expected_loss = len(exp_loss_rows)
    n_total_matchups = len(d["rows"])

    _log(f"counts: expected_win={n_expected_win} unexpected_win={len(unexp_win_rows)} "
        f"coin_flip={len(coinflip_rows)} unexpected_loss={len(unexp_loss_rows)} "
        f"expected_loss={n_expected_loss} total={n_total_matchups}")

    chapters: list[tuple[str, list[Path]]] = []
    seg_i = [0]

    def next_seg(prefix: str) -> Path:
        seg_i[0] += 1
        return WORK_DIR / f"seg_{seg_i[0]:03d}_{prefix}.mp4"

    # ---- 1. Intro -------------------------------------------------------------
    _log("rendering intro (animated hero card)...")
    raw_intro = next_seg("intro_raw")
    make_unit_intro_video(civ, slug, raw_intro, duration_s=INTRO_S)
    intro_seg = _wrap_intro_video(raw_intro, next_seg("intro"))
    chapters.append(("Intro", [intro_seg]))
    _log(f"intro ok ({_duration(intro_seg):.2f}s)")

    # ---- 2. Expected Wins -------------------------------------------------------
    _log("rendering Expected Wins explanation card...")
    expl_png = WORK_DIR / "card_expl_expected_win.png"
    img = make_category_explanation_card(
        "Expected Wins",
        "The Temple Guard has a damage bonus against these units — and it shows. "
        "23 matchups tested. Every one a convincing win.",
        1, 3, "expected_win")
    img.convert("RGB").save(expl_png)
    seg = _png_segment(expl_png, EXPLAIN_S, next_seg("expl_expected_win"))
    chapters.append(("Expected Wins", [seg]))

    for rank, oppkey in enumerate(filmed["expected_win"], start=1):
        row = next(r for r in exp_win_rows if (r["civ"], r["slug"]) == oppkey)
        clip_name = {
            ("Burmese", "elite_elephant"): "expected_win_1_elite_elephant.mp4",
            ("Romans", "elite_centurion_romans"): "expected_win_2_elite_centurion_romans.mp4",
            ("Wu", "jian_swordsman_wu"): "expected_win_3_jian_swordsman_wu.mp4",
        }[oppkey]
        clip = CLIPS_DIR / clip_name
        assert clip.exists(), f"missing fight clip: {clip}"
        chap_label = f"Expected Win — {row['name']} ({row['civ']})"
        chapters.append((chap_label, [clip]))
        _log(f"fight clip ok: {clip_name} ({_duration(clip):.2f}s)")

    _log("rendering Expected Wins ranking card...")
    rank_png = WORK_DIR / "card_rank_expected_win.png"
    img = make_category_ranking_card("Expected Wins", exp_win_rows, filmed["expected_win"],
                                     "expected_win", subject_short=SUBJECT_SHORT)
    img.convert("RGB").save(rank_png)
    seg = _png_segment(rank_png, RANK_S, next_seg("rank_expected_win"))
    chapters.append(("Expected Wins — full ranking", [seg]))

    # ---- 3. Expected Losses -----------------------------------------------------
    _log("rendering Expected Losses explanation card...")
    expl_png = WORK_DIR / "card_expl_expected_loss.png"
    img = make_category_explanation_card(
        "Expected Losses",
        "These units carry a bonus against the Temple Guard. It loses — and cheaply: "
        "even 40-resource units wipe it out.",
        2, 3, "expected_loss")
    img.convert("RGB").save(expl_png)
    seg = _png_segment(expl_png, EXPLAIN_S, next_seg("expl_expected_loss"))
    chapters.append(("Expected Losses", [seg]))

    for rank, oppkey in enumerate(filmed["expected_loss"], start=1):
        row = next(r for r in exp_loss_rows if (r["civ"], r["slug"]) == oppkey)
        clip_name = {
            ("Malay", "elite_karambit_warrior_malay"): "expected_counter_1_elite_karambit_warrior_malay.mp4",
            ("Tupi", "elite_blackwood_archer_tupi"): "expected_counter_2_elite_blackwood_archer_tupi.mp4",
            ("Incas", "elite_champi_warrior"): "expected_counter_3_elite_champi_warrior.mp4",
        }[oppkey]
        clip = CLIPS_DIR / clip_name
        assert clip.exists(), f"missing fight clip: {clip}"
        chap_label = f"Expected Loss — {row['name']} ({row['civ']})"
        chapters.append((chap_label, [clip]))
        _log(f"fight clip ok: {clip_name} ({_duration(clip):.2f}s)")

    _log("rendering Expected Losses ranking card...")
    rank_png = WORK_DIR / "card_rank_expected_loss.png"
    img = make_category_ranking_card("Expected Losses", exp_loss_rows, filmed["expected_loss"],
                                     "expected_loss", subject_short=SUBJECT_SHORT)
    img.convert("RGB").save(rank_png)
    seg = _png_segment(rank_png, RANK_S, next_seg("rank_expected_loss"))
    chapters.append(("Expected Losses — full ranking", [seg]))

    # ---- 4. Unexpected Wins — EMPTY CATEGORY, SILENTLY SKIPPED --------------------
    # unexp_win_rows is [] for Elite Temple Guard (0 upsets in its favor). Per the
    # empty-category rule (module docstring), a category with no rows gets no card
    # and no chapter at all — not even the old "NONE" zero-state card. If a future
    # run of this script ever has non-zero unexp_win_rows, add an explanation+fights
    # +ranking block here mirroring the Expected Wins / Expected Losses sections
    # above (and bump every "i / N" progress marker in this file back up).
    if unexp_win_rows:
        raise NotImplementedError(
            "unexp_win_rows is non-empty — the empty-category skip no longer applies; "
            "this section needs a real explanation/fights/ranking block (see comment).")
    _log("skipping Unexpected Wins: 0 matchups — empty categories are silently skipped")

    # ---- 5. Unexpected Losses -----------------------------------------------------
    _log("rendering Unexpected Losses explanation card...")
    expl_png = WORK_DIR / "card_expl_unexpected_loss.png"
    img = make_category_explanation_card(
        "Unexpected Losses",
        "On paper, the Temple Guard has the advantage in both of these fights. "
        "It loses anyway.",
        3, 3, "unexpected_loss")
    img.convert("RGB").save(expl_png)
    seg = _png_segment(expl_png, EXPLAIN_S, next_seg("expl_unexpected_loss"))
    chapters.append(("Unexpected Losses", [seg]))

    unexp_loss_by_key = {(r["civ"], r["slug"]): r for r in unexp_loss_rows}
    for oppkey, clip_name in (
        (("Byzantines", "elite_cataphract_byzantines"),
         "unexpected_counter_1_elite_cataphract_byzantines.mp4"),
        (("Persians", "elite_war_elephant_persians"),
         "unexpected_counter_2_elite_war_elephant_persians.mp4"),
    ):
        row = unexp_loss_by_key[oppkey]
        clip = CLIPS_DIR / clip_name
        assert clip.exists(), f"missing fight clip: {clip}"
        chap_label = f"Unexpected Loss — {row['name']} ({row['civ']})"
        chapters.append((chap_label, [clip]))
        _log(f"fight clip ok: {clip_name} ({_duration(clip):.2f}s)")
    # NO ranking card (2 units < 4 — addendum rule)

    # ---- 6. Coin-flips close -----------------------------------------------------
    _log("rendering coin-flip odds card...")
    coinflip_png = WORK_DIR / "card_coinflip.png"
    coinflip_display = [
        dict(name="Elite Konnik", civ="Bulgarians", odds="67 : 33"),
        dict(name="Condottiero", civ="Italians", odds="47 : 53"),
        dict(name="Elite Huskarl", civ="Goths", odds="40 : 60"),
    ]
    img = make_coinflip_odds_card(
        "Too Close To Call", coinflip_display,
        "These could go either way — full numbers at AOE2MATCHUP.COM.",
        category_key="coin_flip")
    img.convert("RGB").save(coinflip_png)
    seg = _png_segment(coinflip_png, COINFLIP_S, next_seg("coinflip"))
    chapters.append(("Too Close To Call", [seg]))

    # ---- 7. Outro — animated "thank you" close (NEW final segment) ----------------
    _log("rendering outro thanks (animated hero card)...")
    raw_outro = next_seg("outro_raw")
    make_outro_thanks_video(civ, slug, raw_outro, duration_s=OUTRO_S)
    outro_seg = _wrap_intro_video(raw_outro, next_seg("outro"))
    chapters.append(("Thanks + aoe2matchup.com", [outro_seg]))
    _log(f"outro ok ({_duration(outro_seg):.2f}s)")

    # ---- concat + chapters --------------------------------------------------
    all_segs = [s for _, segs in chapters for s in segs]
    _log(f"concatenating {len(all_segs)} segments -> {OUT_MP4}")
    concat_videos(all_segs, OUT_MP4)

    chap_entries = [(label, sum(_duration(s) for s in segs)) for label, segs in chapters]
    chapters_txt = OUT_MP4.with_suffix(".chapters.txt")
    write_chapters(chap_entries, chapters_txt)

    _log(f"DONE: {OUT_MP4} ({_duration(OUT_MP4):.2f}s total)")
    _log(f"chapters: {chapters_txt}")
    for label, dur in chap_entries:
        _log(f"  {label}: {dur:.2f}s")


if __name__ == "__main__":
    main()

"""
video_extract.py — read survivor counts off a battle video with OCR.

This is the REAL-GAME results path: the scenario shows a live count readout
(count_units_into_variable -> display_instructions) in a known screen region;
we sample frames, crop the two number regions, OCR them, and rebuild the
survivor timeline as a results.MatchResult — the same shape extract_sim_results
returns, so the overlay renderer is source-agnostic.

OCR engine: rapidocr-onnxruntime (pip-only, no admin, CPU, offline).

No real footage yet, so `make_mock_readout_video()` synthesizes a clip that
mimics the game's readout (a top banner with both counts changing over time),
letting us validate the OCR + parsing end-to-end now. When real footage exists,
just tune the two ROIs to where the game draws the numbers.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from overlay.results import MatchResult
from overlay.readout import parse_counts as _parse_counts

# Cross-platform font dir for the mock-video generator (cosmetic only).
_FONTS = next((Path(p) for p in (
    "/System/Library/Fonts/Supplemental", "/Library/Fonts",
    "C:/Windows/Fonts", "/usr/share/fonts/truetype") if Path(p).exists()),
    Path("."))

# The REAL in-game readout (from make_scenario's display_instructions) is ONE
# centered line: "Unit A: N  VS  Unit B: M". We crop this band, OCR it raw
# (rapidocr handles the light-text-on-field directly — NO dark-panel preprocess),
# split on "VS", and take the first integer on each side. Verified on Mac DE.
READOUT_BAND = (0.28, 0.13, 0.74, 0.22)   # fractional x0,y0,x1,y1
# Legacy two-panel ROIs — used ONLY by the synthetic mock readout video below.
ROI_LEFT = (0.255, 0.035, 0.455, 0.150)
ROI_RIGHT = (0.545, 0.035, 0.745, 0.150)


@lru_cache(maxsize=1)
def _ocr():
    from rapidocr_onnxruntime import RapidOCR
    return RapidOCR()


@lru_cache(maxsize=8)
def _font(name, size):
    try:
        return ImageFont.truetype(str(_FONTS / name), size)
    except OSError:
        return ImageFont.load_default()


def _preprocess(crop_rgb: np.ndarray) -> np.ndarray:
    """High-contrast black-digits-on-white for the OCR model.

    The readout is light digits on a dark panel; threshold + invert so digits
    are dark on white (what text OCR models expect), then upscale 3x.
    """
    gray = np.dot(crop_rgb[..., :3].astype(np.float32), [0.299, 0.587, 0.114])
    binar = np.where(gray > 110, 0, 255).astype(np.uint8)  # bright->black, dark->white
    im = Image.fromarray(binar).convert("RGB")
    return np.array(im.resize((im.width * 3, im.height * 3), Image.LANCZOS))


def _read_int(crop_rgb: np.ndarray) -> int | None:
    """OCR a small crop and return the first integer found (None if unreadable)."""
    res, _ = _ocr()(_preprocess(crop_rgb))
    if not res:
        return None
    text = " ".join(line[1] for line in res)
    m = re.findall(r"\d+", text)
    return int(m[0]) if m else None


def _clean_monotonic(series: list[int], cap: int | None = None) -> list[int]:
    """Survivor counts only ever DECREASE and never exceed the starting count `cap`.

    Robust to SINGLE-FRAME OCR errors in BOTH directions: a digit split ('4' OCR'd as
    '4 4' => 44), a stray/dropped digit, or a low misread (27 read as 2). Pipeline:
      1. clamp to [0, cap]   (counts can't exceed the start; kills impossible highs)
      2. first-sample repair (counts only ever DECREASE, so the first sample must be
         the series max; a low FIRST misread ('30' read as '3') would otherwise be
         propagated over EVERYTHING by the forward-min — lift it to max(first 3))
      3. median-of-3 filter  (a lone outlier high or low is replaced by its neighbours)
      4. forward min          (enforce non-increasing on what remains)
    The OLD backward-max step is gone — it propagated a single HIGH misread backward
    across the whole series (e.g. one '44' frame poisoned every earlier count)."""
    if not series:
        return series
    s = [max(0, min(v, cap) if cap is not None else max(0, v)) for v in series]
    n = len(s)
    m = list(s)
    m[0] = max(s[:3])                                     # repair a low first misread
    for i in range(1, n - 1):
        m[i] = sorted((s[i - 1], s[i], s[i + 1]))[1]     # median of 3
    for i in range(1, n):
        m[i] = min(m[i], m[i - 1])                        # non-increasing
    return m


def _crop(frame_rgb: np.ndarray, roi) -> np.ndarray:
    h, w = frame_rgb.shape[:2]
    x0, y0, x1, y1 = roi
    return frame_rgb[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]


# Every recording shares one deterministic visual structure (same template, same
# navigation): editor (~32 mean luma) -> Test-click flash -> dark LOADING screen
# (~22) -> the bright arena appears (~120-140) the instant the scenario starts.
# That load->game luma jump IS game-time zero, and it's detectable frame-accurately
# from pixel statistics alone — no OCR. Measured identical across all archived raws.
_GAME_LUMA = 90.0          # in-game frames measure ~120-140; menu/load ~22-33; flash <70
_DARK_LUMA = 50.0          # the load screen / menu band


def _luma_at(cap, t: float):
    import cv2
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000.0)
    ok, fr = cap.read()
    if not ok:
        return None
    small = cv2.resize(fr, (160, 90))
    return float(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).mean())


def find_game_start(video_path, t_from=1.0, t_to=25.0, coarse=0.5):
    """FRAME-ACCURATE game-start (the first in-game frame) from the load->game luma
    jump. Coarse 0.5s scan brackets the first bright frame that FOLLOWS a dark one
    (debounced against the Test-click flash by requiring the next sample bright too),
    then a frame-step scan inside the bracket pins it. Returns seconds, or None
    (caller falls back to the OCR readout scan)."""
    import cv2
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
        seen_dark, bracket = False, None
        t = t_from
        while t <= t_to:
            m = _luma_at(cap, t)
            if m is None:
                return None
            if m < _DARK_LUMA:
                seen_dark = True
            elif m >= _GAME_LUMA and seen_dark:
                nxt = _luma_at(cap, t + coarse)
                if nxt is not None and nxt >= _GAME_LUMA:   # debounce the click flash
                    bracket = t
                    break
            t += coarse
        if bracket is None:
            return None
        # frame-step refine inside (bracket - coarse, bracket]: ONE seek, then decode
        # sequentially (per-frame seeks on long-GOP H.264 are what made this slow)
        cap.set(cv2.CAP_PROP_POS_MSEC, max(t_from, bracket - coarse) * 1000.0)
        base_t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        for i in range(int(fps * (coarse + 0.2)) + 2):
            ok, fr = cap.read()
            if not ok:
                break
            t = base_t + i / fps
            small = cv2.resize(fr, (160, 90))
            if float(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).mean()) >= _GAME_LUMA:
                return round(t, 3)
            if t > bracket + 0.1:
                break
        return round(bracket, 3)
    finally:
        cap.release()


def extract_video_results(video_path, *, band=READOUT_BAND, sample_hz=2.0,
                          civ1="", slug1="", civ2="", slug2="",
                          start1=None, start2=None, t_from=0.0, t_to=None) -> MatchResult:
    """OCR a recording's centered 'Unit A: N  VS  Unit B: M' readout into a MatchResult.

    Samples [`t_from`, `t_to`] (whole clip if t_to is None), keeps only frames where BOTH
    counts parse (so pre-fight menu/countdown frames are skipped), re-bases the timeline to
    the first readable frame, clamps counts to monotonic-decrease, and records the absolute
    fight window (fight_start_s/fight_end_s). Bounding the scan to the known fight window
    avoids OCR-ing the (slow, useless) menu/load/post-result frames; once one side reads 0
    for a few consecutive samples the battle is over and the scan stops early (the readout
    keeps displaying through the long WINS hold — no point OCR-ing that tail).
    """
    import cv2
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    duration = (cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) / fps
    end = duration if t_to is None else min(duration, t_to)

    samples = []  # (abs_t, raw_s1, raw_s2)
    t = max(0.0, t_from)
    step = 1.0 / sample_hz
    started, gap, wiped = False, 0, 0
    max_gap = max(2, int(round(4.0 * sample_hz)))   # stop ~4s after the readout disappears
    while t <= end + 1e-6:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ok, frame = cap.read()
        if not ok:
            break
        crop = _crop(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), band)
        res, _ = _ocr()(crop)        # rapidocr on the raw color crop (no preprocess)
        counts = _parse_counts(" ".join(line[1] for line in res)) if res else None
        if counts:
            samples.append((round(t, 2), counts[0], counts[1]))
            started, gap = True, 0
            # an army at 0 = battle over; require 3 consecutive zero-reads (misread guard)
            wiped = wiped + 1 if min(counts) == 0 else 0
            if wiped >= 3:
                break
        elif started:               # readout gone -> the fight's over; don't OCR the tail
            gap += 1
            if gap >= max_gap:
                break
        t += step
    cap.release()

    if not samples:
        raise RuntimeError("OCR produced no readable readout — check the band/footage.")

    # domain cleanup: survivor counts only ever decrease and never exceed the start count
    s1 = _clean_monotonic([s[1] for s in samples], cap=start1)
    s2 = _clean_monotonic([s[2] for s in samples], cap=start2)
    st1 = start1 if start1 is not None else max(s1)
    st2 = start2 if start2 is not None else max(s2)
    t0 = samples[0][0]
    timeline = [{"t": round(ts - t0, 2), "s1": a, "s2": b,
                 "hp1": (a / st1 if st1 else 0.0), "hp2": (b / st2 if st2 else 0.0)}
                for (ts, _, _), a, b in zip(samples, s1, s2)]

    surv1, surv2 = s1[-1], s2[-1]
    winner = 1 if surv1 > surv2 else (2 if surv2 > surv1 else 0)
    return MatchResult(
        civ1=civ1, slug1=slug1, civ2=civ2, slug2=slug2,
        start1=st1, start2=st2, winner=winner, survivors1=surv1, survivors2=surv2,
        hp1_pct=(surv1 / st1 if st1 else 0.0), hp2_pct=(surv2 / st2 if st2 else 0.0),
        duration_s=round(timeline[-1]["t"], 2), end_reason="ocr_video",
        engine="video_ocr", timeline=timeline,
        fight_start_s=t0, fight_end_s=samples[-1][0])


def read_winner_text(video_path, ts, band=(0.10, 0.18, 0.90, 0.52)):
    """OCR the centre band at the given video times; return the first text containing
    'wins' (the scenario's '<unit> WINS!' hold — the game's own verdict), else None.
    Lowercased with spaces stripped."""
    import cv2
    cap = cv2.VideoCapture(str(video_path))
    try:
        for t in ts:
            cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000.0)
            ok, fr = cap.read()
            if not ok:
                continue
            crop = _crop(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB), band)
            res, _ = _ocr()(crop)
            txt = "".join(line[1] for line in res).lower().replace(" ", "") if res else ""
            if "wins" in txt:
                return txt
    finally:
        cap.release()
    return None


# --------------------------------------------------------------------------- #
# Mock readout video (stand-in for the real game's on-screen count display)
# --------------------------------------------------------------------------- #
def _mock_frame(s1, s2, name1, name2, t, size) -> Image.Image:
    W, H = size
    img = Image.new("RGB", (W, H), (51, 64, 28))  # field
    d = ImageDraw.Draw(img)
    # Single centered readout line matching the real game's display_instructions,
    # positioned inside READOUT_BAND (~y 0.13-0.22) so extract_video_results reads it.
    lbl = _font("georgiab.ttf", 30)
    line = f"{name1}: {s1}   VS   {name2}: {s2}"
    d.text((W * 0.5, H * 0.175), line, font=lbl, fill=(232, 224, 196), anchor="mm")
    return img


def make_mock_readout_video(result: MatchResult, out_path, name1, name2,
                            size=(1280, 720)) -> Path:
    """Render a clip whose top banner shows the live counts from `result.timeline`."""
    import cv2
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tl = result.timeline
    fps = max(1.0, len(tl) / max(1.0, result.duration_s))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(str(out_path), fourcc, fps, size)
    for row in tl:
        frame = _mock_frame(row["s1"], row["s2"], name1, name2, row["t"], size)
        bgr = cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR)
        vw.write(bgr)
    vw.release()
    return out_path


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # scenario_builder/
    from overlay.results import extract_sim_results
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # 1. ground-truth timeline from the sim
    truth = extract_sim_results("Wu", "elite_fire_archer_wu", "Wu", "jian_swordsman_wu")
    s = Path(__file__).parent / "samples"
    mock = make_mock_readout_video(truth, s / "_mock_readout.mp4",
                                   "Elite Fire Archer", "Jian Swordsman")
    print("mock readout video:", mock)

    # 2. OCR it back
    got = extract_video_results(mock, start1=truth.start1, start2=truth.start2)
    print(f"OCR result: winner=team{got.winner}  survivors {got.survivors1}-{got.survivors2}  "
          f"samples={len(got.timeline)}")

    # 3. accuracy vs ground truth, compared by NEAREST TIMESTAMP (the two
    #    timelines sample at slightly different rates, so index-compare is wrong)
    def truth_at(t):
        best = min(truth.timeline, key=lambda r: abs(r["t"] - t))
        return best["s1"], best["s2"]
    n = len(got.timeline)
    exact = 0
    mism = []
    for r in got.timeline:
        ts1, ts2 = truth_at(r["t"])
        if r["s1"] == ts1 and r["s2"] == ts2:
            exact += 1
        else:
            mism.append((r["t"], (ts1, ts2), (r["s1"], r["s2"])))
    print(f"exact count matches: {exact}/{n}  ({100*exact/max(1,n):.0f}%)")
    if mism:
        print("mismatches (t, truth, ocr):")
        for m in mism[:10]:
            print("  ", m)

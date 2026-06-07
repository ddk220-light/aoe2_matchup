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

from results import MatchResult

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


def _parse_counts(text: str):
    """Parse 'Unit A: N  VS  Unit B: M' -> (N, M); None if it doesn't match."""
    parts = re.split(r"\bvs\b", text, flags=re.IGNORECASE)
    if len(parts) != 2:
        return None
    left = re.findall(r"\d+", parts[0])
    right = re.findall(r"\d+", parts[1])
    if not left or not right:
        return None
    return int(left[0]), int(right[0])


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


def _clean_monotonic(series: list[int]) -> list[int]:
    """Survivors can only decrease. Lift too-low misreads to >= the next value
    (backward max), then clamp any upward blips (forward min). Removes the gross
    OCR errors (e.g. 27 read as 2) using the domain constraint."""
    if not series:
        return series
    s = list(series)
    for i in range(len(s) - 2, -1, -1):       # backward: fix too-low reads
        s[i] = max(s[i], s[i + 1])
    for i in range(1, len(s)):                 # forward: no increases allowed
        s[i] = min(s[i], s[i - 1])
    return s


def _crop(frame_rgb: np.ndarray, roi) -> np.ndarray:
    h, w = frame_rgb.shape[:2]
    x0, y0, x1, y1 = roi
    return frame_rgb[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]


def extract_video_results(video_path, *, band=READOUT_BAND, sample_hz=2.0,
                          civ1="", slug1="", civ2="", slug2="",
                          start1=None, start2=None) -> MatchResult:
    """OCR a recording's centered 'Unit A: N  VS  Unit B: M' readout into a MatchResult.

    Samples the whole clip, keeps only frames where BOTH counts parse (so pre-fight
    menu/countdown frames are skipped), re-bases the timeline to the first readable
    frame, clamps counts to monotonic-decrease, and records the absolute fight window
    (fight_start_s/fight_end_s) so the caller can trim the source clip to the fight.
    """
    import cv2
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    duration = (cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) / fps

    samples = []  # (abs_t, raw_s1, raw_s2)
    t = 0.0
    step = 1.0 / sample_hz
    while t <= duration + 1e-6:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ok, frame = cap.read()
        if not ok:
            break
        crop = _crop(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), band)
        res, _ = _ocr()(crop)        # rapidocr on the raw color crop (no preprocess)
        if res:
            counts = _parse_counts(" ".join(line[1] for line in res))
            if counts:
                samples.append((round(t, 2), counts[0], counts[1]))
        t += step
    cap.release()

    if not samples:
        raise RuntimeError("OCR produced no readable readout — check the band/footage.")

    # domain cleanup: survivor counts only ever decrease
    s1 = _clean_monotonic([s[1] for s in samples])
    s2 = _clean_monotonic([s[2] for s in samples])
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
    sys.path.insert(0, str(Path(__file__).parent))
    from results import extract_sim_results
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

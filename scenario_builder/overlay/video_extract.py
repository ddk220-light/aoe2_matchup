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

_FONTS = Path("C:/Windows/Fonts")

# Fractional ROIs (x0,y0,x1,y1) of the frame where each side's number sits.
# These are the MOCK layout; tune to the real game's readout location later.
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


def extract_video_results(video_path, *, roi_left=ROI_LEFT, roi_right=ROI_RIGHT,
                          sample_hz=2.0, civ1="", slug1="", civ2="", slug2="",
                          start1=None, start2=None) -> MatchResult:
    """OCR a battle video's count readout into a MatchResult (timeline + final)."""
    import cv2
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    duration = n_frames / fps if n_frames else 0.0

    timeline, last1, last2 = [], None, None
    t = 0.0
    step = 1.0 / sample_hz
    while t <= duration + 1e-6:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ok, frame = cap.read()
        if not ok:
            break
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        s1 = _read_int(_crop(rgb, roi_left))
        s2 = _read_int(_crop(rgb, roi_right))
        # hold last good reading if a frame is unreadable (OCR hiccup)
        s1 = s1 if s1 is not None else last1
        s2 = s2 if s2 is not None else last2
        if s1 is not None and s2 is not None:
            timeline.append({"t": round(t, 2), "s1": s1, "s2": s2,
                             "hp1": None, "hp2": None})
            last1, last2 = s1, s2
        t += step
    cap.release()

    if not timeline:
        raise RuntimeError("OCR produced no readable samples — check ROIs.")

    # domain cleanup: survivor counts only ever decrease
    s1_clean = _clean_monotonic([r["s1"] for r in timeline])
    s2_clean = _clean_monotonic([r["s2"] for r in timeline])
    for r, a, b in zip(timeline, s1_clean, s2_clean):
        r["s1"], r["s2"] = a, b

    final = timeline[-1]
    surv1, surv2 = final["s1"], final["s2"]
    winner = 1 if surv1 > surv2 else (2 if surv2 > surv1 else 0)
    return MatchResult(
        civ1=civ1, slug1=slug1, civ2=civ2, slug2=slug2,
        start1=start1 if start1 is not None else timeline[0]["s1"],
        start2=start2 if start2 is not None else timeline[0]["s2"],
        winner=winner, survivors1=surv1, survivors2=surv2,
        hp1_pct=1.0 if surv1 else 0.0, hp2_pct=1.0 if surv2 else 0.0,
        duration_s=round(final["t"], 2), end_reason="ocr_video",
        engine="video_ocr", timeline=timeline)


# --------------------------------------------------------------------------- #
# Mock readout video (stand-in for the real game's on-screen count display)
# --------------------------------------------------------------------------- #
def _mock_frame(s1, s2, name1, name2, t, size) -> Image.Image:
    W, H = size
    img = Image.new("RGB", (W, H), (51, 64, 28))  # field
    d = ImageDraw.Draw(img)
    # top banner
    d.rectangle([0, 0, W, int(H * 0.17)], fill=(18, 14, 9))
    lbl = _font("georgiab.ttf", 26)
    num = _font("arialbd.ttf", 54)
    d.text((W * 0.18, H * 0.045), name1, font=lbl, fill=(201, 168, 76), anchor="ma")
    d.text((W * 0.82, H * 0.045), name2, font=lbl, fill=(201, 168, 76), anchor="ma")
    # numbers centered inside the ROIs
    d.text((W * 0.355, H * 0.093), str(s1), font=num, fill=(255, 255, 255), anchor="mm")
    d.text((W * 0.645, H * 0.093), str(s2), font=num, fill=(255, 255, 255), anchor="mm")
    d.text((W * 0.5, H * 0.075), "VS", font=lbl, fill=(201, 168, 76), anchor="mm")
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

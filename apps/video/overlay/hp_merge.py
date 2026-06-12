"""hp_merge.py — fuse the two HP-sidecar sources into one timeline that has BOTH
frame-exact sync and true HP.

  * The OCR readout sidecar (built from the footage) is frame-exact — its counts step
    the moment a unit dies on screen — but it has no real HP (hp == count, so the bar
    shows "survivors remaining", and a side with 5 half-dead survivors reads 17% healthy).
  * The gRPC sidecar has TRUE aggregate army HP per second, but its clock is wall-clock
    estimated against the recorder start, so it can sit a few seconds off the video.

merge_sidecars() solves the clock offset by sliding the gRPC count series against the
OCR count series (both record the same deaths) and keeping the offset that minimizes the
disagreement; the merged rows then carry the OCR clock + OCR counts with the gRPC HP
sampled at the corrected time. A QUALITY GATE refuses to merge when the two series don't
actually agree (the gRPC decode is known to desync mid-battle on some game versions) —
callers fall back to the OCR-only sidecar.
"""
from __future__ import annotations

import json
from pathlib import Path

# the merged HP only beats count-as-hp if the two series genuinely line up:
# at the best offset the counts must agree within ~MAX_RMSE units per side on average
MAX_RMSE = 2.0


def grpc_sane(d: dict, counts) -> bool:
    """Is a gRPC-redecode sidecar structurally trustworthy enough to drive the overlay
    WITHOUT the (slow) OCR cross-check? Requirements:
      * enough rows to be a timeline;
      * the starting army sizes match the scenario EXACTLY (a desynced decode landing
        on both exact counts by chance is implausible);
      * counts (which can never rise) show at most a couple of transient decode dips;
      * the fight resolves (one side reaches 0) or the timeline is long (a cap fight).
    """
    rows = d.get("rows") or []
    if len(rows) < 5:
        return False
    c0 = (int(rows[0]["side1"]["count"]), int(rows[0]["side2"]["count"]))
    if tuple(counts) != c0:
        return False
    dips = 0
    for side in ("side1", "side2"):
        seq = [int(r[side]["count"]) for r in rows]
        dips += sum(1 for a, b in zip(seq, seq[1:]) if b > a)
    if dips > 2:
        return False
    last = rows[-1]
    end_min = min(int(last["side1"]["count"]), int(last["side2"]["count"]))
    return end_min == 0 or rows[-1]["game_s"] - rows[0]["game_s"] >= 30


def _count_at(rows, t, side):
    """Stepped count at game-second `t` (counts hold their value between samples)."""
    if t <= rows[0]["game_s"]:
        return int(rows[0][side]["count"])
    for a, b in zip(rows, rows[1:]):
        if a["game_s"] <= t < b["game_s"]:
            return int(a[side]["count"])
    return int(rows[-1][side]["count"])


def _hp_at(rows, t, side):
    """Linear-interpolated HP at game-second `t`."""
    if t <= rows[0]["game_s"]:
        return float(rows[0][side]["hp"])
    for a, b in zip(rows, rows[1:]):
        if a["game_s"] <= t <= b["game_s"]:
            span = max(1e-6, b["game_s"] - a["game_s"])
            f = (t - a["game_s"]) / span
            return float(a[side]["hp"]) + f * (float(b[side]["hp"]) - float(a[side]["hp"]))
    return float(rows[-1][side]["hp"])


def align_offset(ocr_rows, grpc_rows, d0=0.0, span=8.0, step=0.25):
    """Find delta so that grpc time (t + delta) lines up with ocr time t, by minimizing
    the squared count disagreement over the OCR samples. Returns (delta, rmse_per_side)."""
    best_d, best_score = d0, float("inf")
    n_steps = int(round(2 * span / step)) + 1
    for i in range(n_steps):
        d = d0 - span + i * step
        total, n = 0.0, 0
        for r in ocr_rows:
            t = r["game_s"]
            g1 = _count_at(grpc_rows, t + d, "side1")
            g2 = _count_at(grpc_rows, t + d, "side2")
            total += (int(r["side1"]["count"]) - g1) ** 2 + (int(r["side2"]["count"]) - g2) ** 2
            n += 1
        if n and total / n < best_score:
            best_score, best_d = total / n, d
    rmse = (best_score / 2) ** 0.5 if best_score != float("inf") else float("inf")
    return best_d, rmse


def merge_rows(ocr_rows, grpc_rows, delta):
    """OCR clock + OCR counts, gRPC true HP sampled at (t + delta)."""
    return [{"game_s": r["game_s"],
             "side1": {"count": int(r["side1"]["count"]),
                       "hp": round(_hp_at(grpc_rows, r["game_s"] + delta, "side1"), 1)},
             "side2": {"count": int(r["side2"]["count"]),
                       "hp": round(_hp_at(grpc_rows, r["game_s"] + delta, "side2"), 1)}}
            for r in ocr_rows]


def merge_sidecars(ocr_path, grpc_path, out_path, logfn=print):
    """Write the merged sidecar to `out_path` and return it, or None when the gRPC data
    is missing/too short/disagrees with the footage (quality gate)."""
    try:
        ocr = json.loads(Path(ocr_path).read_text())
        grpc = json.loads(Path(grpc_path).read_text())
    except (OSError, ValueError):
        return None
    ocr_rows, grpc_rows = ocr.get("rows") or [], grpc.get("rows") or []
    if len(ocr_rows) < 3 or len(grpc_rows) < 3:
        return None
    # repair gRPC decode dropouts before using its HP (clean_rows mutates a copy)
    from overlay.overlay_hp import clean_rows
    grpc_rows = clean_rows(json.loads(json.dumps(grpc_rows)))
    # initial guess: both sidecars estimate where game-time 0 sits in the video
    d0 = 0.0
    if ocr.get("video_game_start_s") is not None and grpc.get("video_game_start_s") is not None:
        d0 = float(ocr["video_game_start_s"]) - float(grpc["video_game_start_s"])
    delta, rmse = align_offset(ocr_rows, grpc_rows, d0=d0)
    if rmse > MAX_RMSE:
        logfn(f"[hp-merge] gRPC counts disagree with footage (rmse {rmse:.1f} > "
              f"{MAX_RMSE}) — keeping the OCR-only sidecar")
        return None
    merged = {"video_game_start_s": ocr["video_game_start_s"],
              "rows": merge_rows(ocr_rows, grpc_rows, delta),
              "source": "ocr_counts+grpc_hp", "grpc_offset_s": round(delta, 2),
              "align_rmse": round(rmse, 2)}
    with open(out_path, "w") as f:
        json.dump(merged, f)
    logfn(f"[hp-merge] merged sidecar -> {out_path} (offset {delta:+.2f}s, rmse {rmse:.2f})")
    return str(out_path)

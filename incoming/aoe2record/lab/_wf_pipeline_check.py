"""_wf_pipeline_check.py — end-to-end regression checks on redecode_hp.py outputs.

Validates:
  1. %TEMP%\\wf_gt\\gt.hp_log.jsonl (ground-truth fight): start counts 24/30,
     side1 zero time (stream clock + /1.7 video clock vs [15,18]), side2 end
     (count>=15, hp>0), per-side monotonic non-increasing with <=2 single-step dips.
  2. C:\\dev\\aoe2grpc\\run1.hp_log.jsonl: 23v30, side1 zero near t=21, side2 ~25u.
  3. repo gate: scenario_builder.overlay.hp_merge.grpc_sane({"rows": gt_rows}, (24,30)).
"""
import json
import os
import sys

GAME_SPEED = 1.7

def load(p):
    rows = []
    with open(p) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def zero_time(rows, side):
    for r in rows:
        if r[side]["count"] == 0:
            return r["game_s"]
    return None

def dips(rows):
    out = {}
    for side in ("side1", "side2"):
        seq = [r[side]["count"] for r in rows]
        d = [(i, a, b) for i, (a, b) in enumerate(zip(seq, seq[1:])) if b > a]
        out[side] = d
    return out

res = {}

# --- 1. ground truth ---
gt_path = os.path.join(os.environ["TEMP"], "wf_gt", "gt.hp_log.jsonl")
gt = load(gt_path)
gt_start = (gt[0]["side1"]["count"], gt[0]["side2"]["count"])
gt_zero_stream = zero_time(gt, "side1")
gt_zero_video = round(gt_zero_stream / GAME_SPEED, 2) if gt_zero_stream is not None else None
gt_last = gt[-1]
gt_dips = dips(gt)
gt_dip_n = sum(len(v) for v in gt_dips.values())
res["gt"] = {
    "rows": len(gt),
    "start": gt_start,
    "start_ok": gt_start == (24, 30),
    "side1_zero_stream_s": gt_zero_stream,
    "side1_zero_video_s": gt_zero_video,
    "zero_in_15_18_video": gt_zero_video is not None and 15.0 <= gt_zero_video <= 18.0,
    "side2_end": (gt_last["side2"]["count"], gt_last["side2"]["hp"]),
    "side2_end_ok": gt_last["side2"]["count"] >= 15 and gt_last["side2"]["hp"] > 0,
    "dips": {k: v for k, v in gt_dips.items()},
    "dips_ok": gt_dip_n <= 2 and all(b - a == 1 for _, a, b in
                                     gt_dips["side1"] + gt_dips["side2"]),
}

# --- 2. run1 ---
r1 = load(r"C:\dev\aoe2\aoe2record\lab\run1.hp_log.jsonl")
r1_start = (r1[0]["side1"]["count"], r1[0]["side2"]["count"])
r1_zero = zero_time(r1, "side1")
r1_last = r1[-1]
r1_dips = dips(r1)
res["run1"] = {
    "rows": len(r1),
    "start": r1_start,
    "start_ok": r1_start == (23, 30),
    "side1_zero_s": r1_zero,
    "zero_near_21": r1_zero is not None and abs(r1_zero - 21) <= 3,
    "side2_end": (r1_last["side2"]["count"], r1_last["side2"]["hp"]),
    "side2_end_ok": 20 <= r1_last["side2"]["count"] <= 30,
    "dip_count": sum(len(v) for v in r1_dips.values()),
}

# --- 3. repo gate ---
sys.path.insert(0, r"C:\dev\aoe2\aoe2-unit-analyzer\scenario_builder")
from overlay.hp_merge import grpc_sane  # noqa: E402
res["grpc_sane_gt"] = grpc_sane({"rows": gt}, (24, 30))
res["grpc_sane_gt_wrongcounts"] = grpc_sane({"rows": gt}, (23, 30))  # sanity: must be False
res["grpc_sane_run1"] = grpc_sane({"rows": r1}, (23, 30))

res["all_ok"] = (res["gt"]["start_ok"] and res["gt"]["zero_in_15_18_video"]
                 and res["gt"]["side2_end_ok"] and res["gt"]["dips_ok"]
                 and res["run1"]["start_ok"] and res["run1"]["zero_near_21"]
                 and res["run1"]["side2_end_ok"]
                 and res["grpc_sane_gt"] is True
                 and res["grpc_sane_gt_wrongcounts"] is False)

print(json.dumps(res, indent=1))

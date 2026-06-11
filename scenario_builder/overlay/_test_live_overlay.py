"""Validate the NEW 20s live-overlay pipeline on an EXISTING raw recording.
No game needed — uses the consistency-1 Temple Guard vs Jaguar raw + sidecar."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SB = HERE.parent
sys.path.insert(0, str(SB))

from overlay.overlay_data import get_unit_card
from overlay.compose import make_live_overlay_video, _duration

RAW = r"C:\Users\ddk22\Videos\aoe2_matchups\raw recordings\Elite Temple Guard vs Jaguar Warrior (consistency 1).mov"
SC = r"C:\Users\ddk22\Videos\aoe2_matchups\Elite Temple Guard vs Jaguar Warrior (consistency 1).hp.json"
OUT = r"C:\Users\ddk22\Videos\aoe2_matchups\_LIVE_OVERLAY_TEST.mp4"

u1 = get_unit_card("Muisca", "elite_temple_guard_muisca")
u2 = get_unit_card("Aztecs", "elite_jaguar_warrior_aztecs")

# lead-in: prefer the frame-accurate game-start detection used by the real pipeline
lead_in = None
try:
    from auto.record_until_end import detect_game_start, PATROL_LEAD
    gs = detect_game_start(RAW)
    if gs is not None:
        lead_in = gs + PATROL_LEAD
        print(f"[test] detected game-start={gs:.1f}s -> lead_in={lead_in:.1f}s")
except Exception as e:
    print(f"[test] detect_game_start unavailable ({type(e).__name__}: {e})")
if lead_in is None:
    import json
    vstart = json.load(open(SC))["video_game_start_s"]
    lead_in = vstart + 2.0
    print(f"[test] fallback lead_in = vstart+2 = {lead_in:.1f}s")

print(f"[test] raw duration = {_duration(RAW):.1f}s")
out = make_live_overlay_video(u1, u2, OUT, RAW, SC, lead_in=lead_in,
                              counts=(23, 30), size=(2560, 1440))
print("WROTE", out, f"({Path(out).stat().st_size//1024} KB, {_duration(out):.1f}s)")

"""Replay a recorded frames.bin through grpc_hp_log.LiveEnd to validate the live
fight-end tailer offline. Expected on the golden Jaguar dump: .END written with
end_stream_s ~= 28.8 (side1 wiped), winner=2."""
import json
import os
import struct
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import cade_api_pb2 as pb            # noqa: E402
import grpc_hp_log as G              # noqa: E402

SRC = sys.argv[1]
OUT = os.path.join(os.environ.get("TEMP", "."), "replay_live")
for ext in (".END", ".live_seed.bin"):
    try:
        os.remove(OUT + ext)
    except OSError:
        pass

live = G.LiveEnd(OUT)
t0 = time.time()
nf = 0
with open(SRC + ".frames.bin", "rb") as f:
    while not live.done:
        hdr = f.read(4)
        if len(hdr) < 4:
            break
        ln = struct.unpack("<I", hdr)[0]
        buf = f.read(ln)
        if len(buf) < ln:
            break
        sq = pb.FrameSequence()
        sq.ParseFromString(buf)
        for fr in sq.frame:
            nf += 1
            live.feed(fr)
            if live.done:
                break
print(f"frames fed: {nf}   decode wall time: {time.time() - t0:.1f}s   "
      f"live_ok={live.ok}  done={live.done}")
if os.path.exists(OUT + ".END"):
    with open(OUT + ".END") as f:
        print("END:", json.load(f))
else:
    print("NO .END written")

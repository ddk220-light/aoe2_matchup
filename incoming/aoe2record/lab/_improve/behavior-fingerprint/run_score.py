"""Trigger the resident driver and wait for the result (max 360s).
Usage: python run_score.py [exec_script_path]"""
import os, time, sys
WORK = r"C:\dev\aoe2\aoe2record\lab\_improve\behavior-fingerprint"
RESULT = os.path.join(WORK, "result.txt")
GO = os.path.join(WORK, "go.txt")
if os.path.exists(RESULT):
    os.remove(RESULT)
with open(GO, "w") as f:
    f.write(sys.argv[1] if len(sys.argv) > 1 else "")
t0 = time.time()
while time.time() - t0 < 360:
    if os.path.exists(RESULT):
        time.sleep(0.3)
        print(open(RESULT).read())
        sys.exit(0)
    time.sleep(1)
print("TIMEOUT waiting for driver result")
sys.exit(1)

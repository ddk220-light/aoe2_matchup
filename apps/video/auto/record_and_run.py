"""record_and_run.py — run a matchup batch while screen-recording the ENTIRE automation
(navigation, menus, the fight, compose) to one file, so the session can be reviewed
against the timestamped logs to find slow spots / improvements.

The session capture is a LIGHT gdigrab encode (low fps/res, CPU + libx264 ultrafast) so it
doesn't contend with the automation's own ddagrab + h264_nvenc fight recorder — different
capture API and encoder, so the two run side by side without stealing the GPU capture.

  python -m auto.record_and_run <session.mp4> -- <batch_matchups args...>
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SB = HERE.parent
sys.path.insert(0, str(SB))

from auto import platform_io   # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("usage: python -m auto.record_and_run <session.mp4> -- <batch args...>")
        sys.exit(2)
    session_out = sys.argv[1]
    rest = sys.argv[2:]
    if rest and rest[0] == "--":
        rest = rest[1:]

    ff = platform_io._win_ffmpeg() or "ffmpeg"
    # session-capture safety cap: long batches outrun a short -t and silently lose
    # footage; default 4h, override with AOE2_SESSION_CAP (seconds)
    sess_cap = os.environ.get("AOE2_SESSION_CAP", "14400")
    sess = subprocess.Popen(
        [ff, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "gdigrab", "-framerate", "15", "-i", "desktop",
         "-vf", "scale=1280:-2", "-c:v", "libx264", "-preset", "ultrafast",
         "-pix_fmt", "yuv420p", "-t", sess_cap, str(session_out)],
        stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    print(f"[session] recording whole run -> {session_out}", flush=True)
    time.sleep(1.0)

    code = 0
    sys.argv = ["batch_matchups"] + rest
    try:
        from auto import batch_matchups
        batch_matchups.main()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 0
    except Exception as e:
        print(f"[session] batch error: {e}", flush=True)
        code = 1
    finally:
        try:
            sess.communicate(b"q", timeout=25)      # graceful finalize
        except Exception:
            sess.kill()
        sz = Path(session_out).stat().st_size // 1024 if Path(session_out).exists() else 0
        print(f"[session] stopped -> {session_out} ({sz} KB)", flush=True)
    sys.exit(code)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()

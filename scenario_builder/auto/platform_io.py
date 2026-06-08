"""platform_io.py — OS-specific primitives for the matchup automation.

Everything else in `auto/` (find_text/detect_* logic, navigation, the watch loop) and
the whole `overlay/` + `build_run.py` side is cross-platform Python. Only a handful of
primitives differ per OS, and they all live here:

    grab()                full-screen screenshot (PIL.Image)
    SCALE                 screenshot-pixels per click-point (Retina Mac = 2; Windows usually 1)
    move / mouse_down / mouse_up / key / type_text   low-level input injection
    activate_game()       bring AoE2:DE frontmost (keep clicks/captures on it)
    bring_to_front()      launch/raise AoE2:DE and wait a moment
    input_available()     can we inject input? (Mac: Accessibility grant; Windows: yes)
    SCENARIO_DIR          the game's scenario folder (where staged scenarios go)
    recorder_start/stop   screen+audio recorder -> .mov/.mp4

The backend is auto-selected from the OS; force it with env AOE2_OS=mac|windows.

WINDOWS BACKEND IS A DRAFT to adjust on a Windows box (see README_WINDOWS.md):
  pip install pydirectinput mss pygetwindow pywin32      (Pillow already required)
  + ffmpeg on PATH (gdigrab for capture). Set AOE2_SCENARIO_DIR and, if clicks land
  off, AOE2_SCALE, for your machine/display.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_OS = os.environ.get("AOE2_OS", "").lower() or ("windows" if sys.platform.startswith("win") else "mac")
IS_WINDOWS = _OS == "windows"
IS_MAC = _OS == "mac"

# AoE2:DE identifiers
AOE2_BUNDLE = "com.feralinteractive.ageofempires2"          # macOS bundle id (Feral port)
AOE2_WIN_TITLE = os.environ.get("AOE2_WIN_TITLE", "Age of Empires II: Definitive Edition")

# Working-temp dir for recordings / intermediate clips. macOS keeps /tmp (what the
# pipeline has always used); Windows has no /tmp, so use the OS temp dir (%TEMP%).
TMP_DIR = tempfile.gettempdir() if IS_WINDOWS else "/tmp"

# Screenshot-pixels per logical click-point. macOS Retina screencapture is 2x the
# point grid cliclick uses. On Windows, PIL ImageGrab pixels usually match the input
# coordinate space (DPI-aware) -> 1; override with AOE2_SCALE if clicks land off.
SCALE = float(os.environ.get("AOE2_SCALE", "2" if IS_MAC else "1"))


# --------------------------------------------------------------------------- #
# macOS backend (the current, verified implementation — unchanged behavior)
# --------------------------------------------------------------------------- #
_CLICLICK = "/opt/homebrew/bin/cliclick"


def _mac_grab():
    from PIL import Image
    fd, path = tempfile.mkstemp(suffix=".png"); os.close(fd)
    try:
        subprocess.run(["screencapture", "-x", "-t", "png", path], check=True, capture_output=True)
        return Image.open(path).convert("RGB")
    finally:
        try: os.unlink(path)
        except OSError: pass


def _mac_run(*args):
    subprocess.run([_CLICLICK, *args], check=True, capture_output=True)


def _mac_input_available():
    out = subprocess.run([_CLICLICK, "-V"], capture_output=True, text=True)
    return "accessibility privileges not enabled" not in (out.stdout + out.stderr).lower()


def _mac_activate():
    subprocess.run(["osascript", "-e", f'tell application id "{AOE2_BUNDLE}" to activate'],
                   capture_output=True)


def _mac_front():
    subprocess.run(["open", "-b", AOE2_BUNDLE], capture_output=True)


_MAC_SCEN_DIR = Path(
    "/Users/deepak/Library/Application Support/Feral Interactive/Age Of Empires II/"
    "VFS/User/Games/Age of Empires 2 DE/76561198053842894/resources/_common/scenario")


def _mac_recorder_start(out_mov, cap, fps, w, h):
    rec = Path(__file__).resolve().parent.parent / "recorder" / "sck_record"
    if not rec.exists():
        raise FileNotFoundError(f"recorder not built at {rec} (run recorder/build.sh)")
    return subprocess.Popen([str(rec), str(out_mov), str(cap), str(fps), str(w), str(h)],
                            stderr=subprocess.DEVNULL)


def _mac_recorder_stop(proc, out_mov, timeout=20):
    import signal
    if proc.poll() is None:
        proc.send_signal(signal.SIGINT)            # graceful: finalize the .mov
        try: proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired: proc.kill()


# --------------------------------------------------------------------------- #
# Windows backend (DRAFT — adjust + test on a Windows machine)
# --------------------------------------------------------------------------- #
def _win_grab():
    # mss is faster, but Pillow's ImageGrab needs no extra dep and is fine here.
    from PIL import ImageGrab
    return ImageGrab.grab().convert("RGB")          # primary monitor, physical pixels


def _win_input():
    import pydirectinput                            # DirectInput-compatible (works in games)
    pydirectinput.PAUSE = 0                         # we sequence our own settle/hold
    pydirectinput.FAILSAFE = False
    return pydirectinput


def _win_move(x, y):
    _win_input().moveTo(int(x), int(y))


def _win_mouse_down(x, y):
    pdi = _win_input(); pdi.moveTo(int(x), int(y)); pdi.mouseDown()


def _win_mouse_up(x, y):
    _win_input().mouseUp()


def _win_key(chord):
    # chord like "cmd+a" on mac -> map cmd->ctrl on windows; "delete"->"backspace"
    pdi = _win_input()
    keys = [("ctrl" if k == "cmd" else "backspace" if k == "delete" else k)
            for k in chord.lower().split("+")]
    if len(keys) == 1:
        pdi.press(keys[0])
    else:
        for k in keys: pdi.keyDown(k)
        for k in reversed(keys): pdi.keyUp(k)


def _win_type(text):
    _win_input().typewrite(text, interval=0.02)


def _win_activate():
    try:
        import pygetwindow as gw
        wins = gw.getWindowsWithTitle(AOE2_WIN_TITLE)
        if wins:
            w = wins[0]
            if w.isMinimized: w.restore()
            w.activate()
    except Exception:
        pass


def _win_front():
    _win_activate()                                 # launch is manual on Windows (Steam)


_WIN_SCEN_DIR = Path(os.environ.get(
    "AOE2_SCENARIO_DIR",
    str(Path(os.environ.get("USERPROFILE", "C:/Users/Default")) /
        "Games" / "Age of Empires 2 DE" / "<STEAMID>" / "resources" / "_common" / "scenario")))


def _win_recorder_start(out_mov, cap, fps, w, h):
    """ffmpeg gdigrab desktop capture. Audio (system) needs a loopback dshow device —
    set AOE2_AUDIO_DEVICE (e.g. 'Stereo Mix (Realtek)' or a VB-CABLE) or leave unset
    for video-only. Captures the primary desktop (AoE2 fullscreen)."""
    import shutil
    ff = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [ff, "-y", "-f", "gdigrab", "-framerate", str(fps), "-i", "desktop"]
    audio = os.environ.get("AOE2_AUDIO_DEVICE")
    if audio:
        cmd += ["-f", "dshow", "-i", f"audio={audio}"]
    cmd += ["-t", str(cap), "-vf", f"scale={w}:{h}", "-c:v", "libx264",
            "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(fps)]
    if audio:
        cmd += ["-c:a", "aac", "-ar", "48000", "-ac", "2"]
    cmd += [str(out_mov)]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)


def _win_recorder_stop(proc, out_mov, timeout=20):
    if proc.poll() is None:
        try:
            proc.communicate(b"q", timeout=timeout)  # 'q' on ffmpeg stdin = graceful finalize
        except Exception:
            proc.kill()


# --------------------------------------------------------------------------- #
# Public API — dispatches to the selected backend
# --------------------------------------------------------------------------- #
def grab():                       return _win_grab() if IS_WINDOWS else _mac_grab()
def input_available():            return True if IS_WINDOWS else _mac_input_available()
def activate_game():              (_win_activate if IS_WINDOWS else _mac_activate)()
def bring_to_front():             (_win_front if IS_WINDOWS else _mac_front)()
def move(x, y):                   (_win_move(x, y) if IS_WINDOWS else _mac_run(f"m:{int(x)},{int(y)}"))
def mouse_down(x, y):             (_win_mouse_down(x, y) if IS_WINDOWS else _mac_run(f"dd:{int(x)},{int(y)}"))
def mouse_up(x, y):               (_win_mouse_up(x, y) if IS_WINDOWS else _mac_run(f"du:{int(x)},{int(y)}"))
def type_text(text):             (_win_type(text) if IS_WINDOWS else _mac_run(f"t:{text}"))
def key(chord):                   (_win_key(chord) if IS_WINDOWS else _mac_run(*[f"kd:{k}" for k in chord.split('+')]))


def scenario_dir() -> Path:
    return _WIN_SCEN_DIR if IS_WINDOWS else _MAC_SCEN_DIR


def recorder_available() -> bool:
    """Is the screen recorder present? (Windows: ffmpeg on PATH; macOS: the built SCK binary.)"""
    if IS_WINDOWS:
        import shutil
        return shutil.which("ffmpeg") is not None
    return (Path(__file__).resolve().parent.parent / "recorder" / "sck_record").exists()


def recorder_hint() -> str:
    return ("ffmpeg not on PATH (needed for gdigrab capture)" if IS_WINDOWS
            else "recorder not built — run recorder/build.sh")


def recorder_start(out_mov, cap=240, fps=60, w=1920, h=1248):
    return (_win_recorder_start if IS_WINDOWS else _mac_recorder_start)(out_mov, cap, fps, w, h)


def recorder_stop(proc, out_mov, timeout=20):
    (_win_recorder_stop if IS_WINDOWS else _mac_recorder_stop)(proc, out_mov, timeout)

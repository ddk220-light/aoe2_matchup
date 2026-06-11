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

# Make this process DPI-aware on Windows so PIL screenshots (physical pixels) and
# pydirectinput coordinates live in ONE coordinate space — clicks then land correctly at
# any display scaling and SCALE can stay 1. No-op if it fails (old Windows / already set).
if IS_WINDOWS:
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)   # per-monitor DPI aware
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()        # system DPI aware (older)
    except Exception:
        pass

def _primary_display_size():
    """Physical primary-monitor size in px (the process is DPI-aware, set above)."""
    if IS_WINDOWS:
        try:
            import ctypes
            u = ctypes.windll.user32
            return int(u.GetSystemMetrics(0)), int(u.GetSystemMetrics(1))  # SM_CXSCREEN/CYSCREEN
        except Exception:
            pass
    return 1920, 1248


# Output/canvas frame size for the recorder + compose. On Windows default to the NATIVE
# primary-display resolution so the capture AND the final video stay full-res ("highest
# resolution possible"); macOS keeps the 1920x1248 game-window size. Override per machine
# with AOE2_OUT_W / AOE2_OUT_H.
_DW, _DH = _primary_display_size()
OUT_W = int(os.environ.get("AOE2_OUT_W", str(_DW if IS_WINDOWS else 1920)))
OUT_H = int(os.environ.get("AOE2_OUT_H", str(_DH if IS_WINDOWS else 1248)))


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
    # legacy backend, frozen — the pipeline is Windows-only now
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


def _win_ffmpeg() -> str | None:
    """Locate ffmpeg (shared logic in overlay.ffutil — PATH, then the WinGet location)."""
    from overlay.ffutil import find_ffmpeg
    return find_ffmpeg()


def _win_scenario_dir() -> Path:
    """The AoE2:DE scenario folder. AOE2_SCENARIO_DIR overrides; otherwise auto-detect
    <profile>\\Games\\Age of Empires 2 DE\\<steamid>\\resources\\_common\\scenario by
    scanning for the numeric steam-id profile that actually has a scenario folder
    (preferring a real long steam id and the most-recently-used one)."""
    env = os.environ.get("AOE2_SCENARIO_DIR")
    if env:
        return Path(env)
    base = Path(os.environ.get("USERPROFILE", "C:/Users/Default")) / "Games" / "Age of Empires 2 DE"
    if base.is_dir():
        cands = []
        for d in base.iterdir():
            if d.is_dir() and d.name.isdigit():
                s = d / "resources" / "_common" / "scenario"
                if s.is_dir():
                    cands.append((len(d.name) >= 6, s.stat().st_mtime, s))
        if cands:                                  # real steam id first, then most recent
            cands.sort(key=lambda t: (t[0], t[1]), reverse=True)
            return cands[0][2]
    return base / "<STEAMID>" / "resources" / "_common" / "scenario"


_FF_CAPS: dict | None = None


def _win_ff_caps(ff: str) -> dict:
    """Probe (once) whether this ffmpeg build has the GPU capture path: the ddagrab
    source filter and the h264_nvenc encoder. nvenc can still fail at RUNTIME on a
    non-NVIDIA box even when the encoder is compiled in — the start-probe in
    _win_recorder_start catches that and falls back."""
    global _FF_CAPS
    if _FF_CAPS is None:
        def _grep(args, needle):
            try:
                p = subprocess.run([ff, "-hide_banner", *args],
                                   capture_output=True, text=True, timeout=20)
                return needle in (p.stdout + p.stderr)
            except Exception:
                return False
        _FF_CAPS = {"ddagrab": _grep(["-filters"], "ddagrab"),
                    "nvenc": _grep(["-encoders"], "h264_nvenc")}
    return _FF_CAPS


_AUDIO_OK: dict = {}


def _win_audio_ok(ff: str, device: str) -> bool:
    """Is `device` an existing dshow audio device? Probed once per device name from
    ffmpeg's device list, so a missing loopback filter degrades the run to video-only
    instead of killing the whole capture (audio+video share one ffmpeg process)."""
    if device not in _AUDIO_OK:
        try:
            p = subprocess.run([ff, "-hide_banner", "-list_devices", "true",
                                "-f", "dshow", "-i", "dummy"],
                               capture_output=True, text=True, timeout=20)
            _AUDIO_OK[device] = device.lower() in (p.stdout + p.stderr).lower()
        except Exception:
            _AUDIO_OK[device] = False
    return _AUDIO_OK[device]


def _win_recorder_cmd(ff, out_mov, cap, fps, audio, mode: str) -> list:
    """Build the capture command for one of three tiers:
      "nv_zero"  ddagrab -> hwmap(cuda) -> scale_cuda(nv12) -> h264_nvenc — frames stay
                 ON the GPU end to end. The old hwdownload path round-tripped every
                 native-res frame over PCIe (~840 MB/s at 1440p60); when that stalled,
                 Desktop Duplication repeated frames — the recurring 0.2-0.5s hitches
                 baked into the raws (most visible once the ramp speeds the fight up).
      "nv_dl"    ddagrab -> hwdownload -> h264_nvenc (the previous default; fallback
                 when the CUDA interop isn't available).
      "cpu"      gdigrab + libx264 ultrafast, the portable last resort.
    Audio (optional) is a dshow loopback device."""
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error"]
    if audio:
        cmd += ["-f", "dshow", "-i", f"audio={audio}"]
    pixfmt = ["-pix_fmt", "yuv420p"]
    # p1/ull = nvenc's cheapest mode: the encoder shares the GPU with the game, and
    # encoder cost directly becomes dropped capture frames when the GPU is saturated.
    nvenc = ["-c:v", "h264_nvenc", "-preset", "p1", "-tune", "ull", "-cq", "19"]
    if mode == "nv_zero":
        # the documented ddagrab zero-copy form: D3D11 frames hand straight to nvenc.
        # MEASURED WORSE here (18 hitches vs 4-8): nvenc ingesting native-res BGRA
        # costs more GPU than the hwdownload path on this box — kept as an opt-in
        # experiment (AOE2_CAPTURE_MODE=zero), not a default.
        cmd += ["-filter_complex",
                f"ddagrab=output_idx=0:framerate={fps}[v]",
                "-map", "[v]"]
        venc = nvenc
        pixfmt = []                            # nvenc converts on the GPU
    elif mode == "nv_dl":
        cmd += ["-filter_complex",
                f"ddagrab=output_idx=0:framerate={fps},hwdownload,format=bgra[v]",
                "-map", "[v]"]
        venc = nvenc
    else:
        cmd += ["-f", "gdigrab", "-framerate", str(fps), "-i", "desktop",
                "-map", f"{1 if audio else 0}:v"]
        venc = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "21"]
    if audio:
        cmd += ["-map", "0:a"]
    cmd += ["-t", str(cap), *venc, *pixfmt, "-r", str(fps)]
    if audio:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
    return cmd + [str(out_mov)]


def _win_recorder_start(out_mov, cap, fps, w, h):
    """Start the desktop capture, FAIL-FAST and self-healing:
      * ffmpeg's stderr goes to <out>.ffmpeg.log (not DEVNULL) so a dead recorder is
        diagnosable instead of silently producing an empty file 3 minutes later.
      * the configured audio device is probed first; missing -> video-only + warning
        (audio and video share one process, so a bad device used to kill BOTH).
      * the GPU path (ddagrab+h264_nvenc) is probed and, if it dies within the start
        window (e.g. nvenc present but no NVIDIA GPU), gdigrab+libx264 is tried next.
    Raises RuntimeError with the log tail if no capture config survives."""
    ff = _win_ffmpeg()
    if not ff:
        raise FileNotFoundError(recorder_hint())
    audio = os.environ.get("AOE2_AUDIO_DEVICE", "virtual-audio-capturer")
    if audio and not _win_audio_ok(ff, audio):
        print(f"[rec] WARNING: dshow audio device {audio!r} not found — recording "
              "video-only (set AOE2_AUDIO_DEVICE, or '' to silence this)", flush=True)
        audio = ""
    caps = _win_ff_caps(ff)
    attempts = []
    if caps["ddagrab"] and caps["nvenc"]:
        if os.environ.get("AOE2_CAPTURE_MODE", "").lower() == "zero":
            attempts.append(("ddagrab+cuda zero-copy", "nv_zero"))
        attempts.append(("ddagrab+h264_nvenc", "nv_dl"))
    attempts.append(("gdigrab+libx264", "cpu"))
    log_path = str(out_mov) + ".ffmpeg.log"
    for name, mode in attempts:
        cmd = _win_recorder_cmd(ff, out_mov, cap, fps, audio, mode)
        with open(log_path, "a") as errf:
            errf.write(f"--- attempt: {name} ---\n{' '.join(cmd)}\n")
            errf.flush()
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=errf)
        time.sleep(1.5)                      # start-probe: catch an instant death NOW
        ok = proc.poll() is None
        if ok:
            # a HANGING pipeline stays alive but never writes a frame (seen with the
            # ddagrab->CUDA hwmap on some setups) — require actual output bytes too
            deadline = time.time() + 3.5
            while time.time() < deadline:
                try:
                    if os.path.getsize(out_mov) > 0:
                        break
                except OSError:
                    pass
                time.sleep(0.4)
            else:
                ok = False
                try:
                    proc.kill()
                except Exception:
                    pass
        if ok:
            proc.stderr_log = log_path
            return proc
        print(f"[rec] {name} failed at start "
              f"({'no output' if proc.returncode is None else f'exit {proc.returncode}'})"
              f" — see {log_path}", flush=True)
    tail = ""
    try:
        tail = Path(log_path).read_text(errors="replace")[-800:]
    except OSError:
        pass
    raise RuntimeError(f"screen recorder failed to start (all configs). "
                       f"ffmpeg log {log_path}:\n{tail}")


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
    # re-resolve on Windows so a late AOE2_SCENARIO_DIR (set after import) still applies
    return _win_scenario_dir() if IS_WINDOWS else _MAC_SCEN_DIR


def recorder_available() -> bool:
    """Is the screen recorder present? (Windows: ffmpeg on PATH or WinGet; macOS: the
    built SCK binary.)"""
    if IS_WINDOWS:
        return _win_ffmpeg() is not None
    return (Path(__file__).resolve().parent.parent / "recorder" / "sck_record").exists()


def recorder_hint() -> str:
    return ("ffmpeg not found (needed for gdigrab capture) — "
            "`winget install Gyan.FFmpeg`" if IS_WINDOWS
            else "recorder not built — run recorder/build.sh")


def recorder_start(out_mov, cap=240, fps=60, w=1920, h=1248):
    return (_win_recorder_start if IS_WINDOWS else _mac_recorder_start)(out_mov, cap, fps, w, h)


def recorder_stop(proc, out_mov, timeout=20):
    (_win_recorder_stop if IS_WINDOWS else _mac_recorder_stop)(proc, out_mov, timeout)

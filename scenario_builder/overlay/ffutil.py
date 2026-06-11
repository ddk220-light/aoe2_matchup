"""ffutil.py — locate ffmpeg/ffprobe. The ONE place the discovery logic lives
(compose and platform_io both use it): PATH first, else the WinGet install location
(PATH edits don't reach an already-running shell, so a fresh
`winget install Gyan.FFmpeg` works without restarting the terminal).
"""
from __future__ import annotations

import glob
import os
import shutil


def find_ffmpeg() -> str | None:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    hits = glob.glob(os.path.expandvars(
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\**\ffmpeg.exe"),
        recursive=True)
    return hits[0] if hits else None


def find_ffprobe() -> str | None:
    exe = shutil.which("ffprobe")
    if exe:
        return exe
    ff = find_ffmpeg()                      # ffprobe sits beside ffmpeg
    if not ff:
        return None
    head, tail = os.path.split(ff)
    cand = os.path.join(head, tail.replace("ffmpeg", "ffprobe"))
    return cand if os.path.exists(cand) else None

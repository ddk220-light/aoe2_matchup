"""chapters.py — YouTube chapter markers + civ-adjective helper for the joined
compilation videos.

Game-free (no OCR / window / ffmpeg). Moved out of batch_matchups.py so both the
batch runner and the guecha sweep (and any manifest-driven stitcher) share one
copy. batch_matchups re-imports these for back-compat.

  write_chapters(entries, out_txt)  — entries = [(label, clip_duration_seconds), ...]
  _civ_adj(civ)                     — 'Armenians' -> 'Armenian', 'Chinese' -> 'Chinese'
"""
from __future__ import annotations

from pathlib import Path

# civs whose adjective is NOT just "drop the trailing s"
_CIV_ADJ_KEEP = {"Chinese", "Vietnamese", "Burmese", "Portuguese"}


def _civ_adj(civ: str) -> str:
    """'Armenians' -> 'Armenian', 'Aztecs' -> 'Aztec', 'Chinese' -> 'Chinese'."""
    if civ in _CIV_ADJ_KEEP:
        return civ
    return civ[:-1] if civ.endswith("s") else civ


def write_chapters(entries, out_txt) -> Path:
    """Write YouTube chapter markers (cumulative start times) for the joined video.
    entries = [(label, clip_duration_seconds), ...]."""
    lines, t = [], 0.0
    for label, dur in entries:
        s = int(t)
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        ts = f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"
        lines.append(f"{ts} - {label}")
        t += dur
    Path(out_txt).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return Path(out_txt)

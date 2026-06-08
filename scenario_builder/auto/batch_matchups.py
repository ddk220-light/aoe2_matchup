"""batch_matchups.py — run several matchup videos back-to-back, hands-off.

Chains orchestrate_matchup.run_matchup over a list of matchups. After each fight
the end-of-game banner is dismissed back to the Scenario Editor
(return_to_editor), so the next run starts clean; each run rebuilds its scenario
from the golden template, stages it as the SOLE file in the game folder (removing
the previous one), records the fight, and composes a recap video.

  python -m auto.batch_matchups \
      --copy-to "/Volumes/Orchid/AOEII_videos/3kResMatchUpVideos" \
      --matchup "Muisca:elite_temple_guard_muisca:Aztecs:elite_jaguar_warrior_aztecs:Elite Temple Guard vs Jaguar Warrior (Muisca vs Aztecs)" \
      --matchup "Muisca:elite_temple_guard_muisca:Vikings:elite_berserk_vikings:Elite Temple Guard vs Berserk (Muisca vs Vikings)"

Prereqs: same as orchestrate_matchup — a Terminal with Accessibility + Screen
Recording, AoE2:DE open frontmost in the Scenario Editor. Don't touch the
mouse/keyboard or switch apps while it runs.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SB = HERE.parent
sys.path.insert(0, str(SB))
sys.path.insert(0, str(SB / "overlay"))

from auto import input_driver as ui                    # noqa: E402
from auto.orchestrate_matchup import run_matchup        # noqa: E402
from auto.record_until_end import log                   # noqa: E402


def _parse_matchup(s: str) -> dict:
    """'CIV1:slug1:CIV2:slug2:Display Name' -> dict."""
    civ1, slug1, civ2, slug2, name = s.split(":", 4)
    return dict(civ1=civ1.strip(), slug1=slug1.strip(),
                civ2=civ2.strip(), slug2=slug2.strip(), name=name.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--matchup", action="append", required=True, type=_parse_matchup,
                    help="CIV1:slug1:CIV2:slug2:Display Name  (repeatable)")
    ap.add_argument("--copy-to", default=None)
    ap.add_argument("--cap", type=int, default=240)
    ap.add_argument("--log", default="/tmp/auto_matchup.log")
    a = ap.parse_args()
    open(a.log, "w").close()
    n = len(a.matchup)
    log(f"=== BATCH of {n} matchup(s) (template-based, no OCR) ===", a.log)

    if not ui.accessibility_ok():
        log("ERROR: Accessibility not granted — scripted clicks will fail.", a.log)
        sys.exit(2)

    results = []
    for i, m in enumerate(a.matchup, 1):
        log(f"===== [{i}/{n}] {m['name']} =====", a.log)
        try:
            final = run_matchup(
                m["civ1"], m["slug1"], m["civ2"], m["slug2"],
                name=f"{m['name']}.mp4", copy_to=a.copy_to, cap=a.cap,
                out_mov=f"/tmp/auto_fight_{i}.mov", final=f"/tmp/auto_matchup_{i}.mp4",
                dismiss_after=True, logfile=a.log)
            log(f"[{i}/{n}] DONE -> {final}", a.log)
            results.append((m["name"], str(final)))
        except Exception as e:
            log(f"[{i}/{n}] FAILED: {e}", a.log)
            results.append((m["name"], f"FAILED: {e}"))

    log("=== BATCH COMPLETE ===", a.log)
    for nm, r in results:
        log(f"  {nm}  ->  {r}", a.log)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()

"""batch_matchups.py — run a queue of matchup videos back-to-back, hands-off.

Chains orchestrate_matchup.run_matchup over a list of matchups. After each fight
the end-of-game banner is dismissed back to the Scenario Editor, so the next run
starts clean; each run rebuilds its scenario from the golden template, stages it
as the SOLE file in the game folder (removing the previous one), records the
fight, and composes a recap video (intro stat card -> real fight + audio ->
"Battle Complete" card; no OCR / survivor counts).

ROBUSTNESS:
  * PRE-FLIGHT — every matchup's units are resolved and the environment is checked
    BEFORE the game is touched, so a typo in matchup #5 aborts immediately instead
    of wasting four runs. `--dry-run` runs only this and prints the plan.
  * ISOLATION — a failing matchup is logged and SKIPPED; the batch continues. The
    recorder is always stopped and the game always dismissed back to the editor.

  python -m auto.batch_matchups \
      --matchup "Muisca:elite_temple_guard_muisca:Aztecs:elite_jaguar_warrior_aztecs:Elite Temple Guard vs Jaguar Warrior (Muisca vs Aztecs)" \
      --matchup "Muisca:elite_temple_guard_muisca:Vikings:elite_berserk_vikings:Elite Temple Guard vs Berserk (Muisca vs Vikings)"

Each --matchup is  CIV1:slug1:CIV2:slug2:Display Name  (the display name becomes
the output filename and the on-screen title; civs are title-case, slugs are the
reference-DB unit slugs). Repeat --matchup for as many fights as you want.

PREREQS: a Terminal with BOTH Accessibility and Screen Recording (System Settings
-> Privacy & Security); AoE2:DE open frontmost in the Scenario Editor. Don't touch
the mouse/keyboard or switch apps while it runs (the recorder captures the screen).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SB = HERE.parent
sys.path.insert(0, str(SB))
sys.path.insert(0, str(SB / "overlay"))

from auto import input_driver as ui                          # noqa: E402
from auto.orchestrate_matchup import run_matchup, resolve_side, RUN_DIR  # noqa: E402
from auto.record_until_end import log, RECORDER              # noqa: E402
from build_run import TEMPLATE, unit_const                   # noqa: E402

DEFAULT_COPY_TO = "/Volumes/Orchid/AOEII_videos/3kResMatchUpVideos"


def _parse_matchup(s: str) -> dict:
    """'CIV1:slug1:CIV2:slug2:Display Name' -> dict (name may contain ':')."""
    parts = s.split(":", 4)
    if len(parts) != 5:
        raise argparse.ArgumentTypeError(
            f"matchup must be CIV1:slug1:CIV2:slug2:Name — got {s!r}")
    civ1, slug1, civ2, slug2, name = (p.strip() for p in parts)
    return dict(civ1=civ1, slug1=slug1, civ2=civ2, slug2=slug2, name=name)


def preflight(matchups, copy_to, logfile=None):
    """Validate the whole batch before touching the game. Returns (errors, plan).
    `plan` is a list of (name, label1, label2) for the ones that resolve."""
    errors, plan = [], []
    # environment
    if not TEMPLATE.exists():
        errors.append(f"golden template missing: {TEMPLATE}")
    if not RECORDER.exists():
        errors.append(f"recorder not built: {RECORDER} (run recorder/build.sh)")
    if copy_to:
        cp = Path(copy_to)
        if not cp.exists() and not cp.parent.exists():
            errors.append(f"--copy-to not reachable: {copy_to} (is the volume mounted?)")
    # every matchup's units must resolve from the reference DB + unit dataset
    for i, m in enumerate(matchups, 1):
        labels = []
        for civ, slug in ((m["civ1"], m["slug1"]), (m["civ2"], m["slug2"])):
            try:
                civ_, key, label = resolve_side(civ, slug)   # card data (reference DB)
                unit_const(key)                              # scenario unit id (unit dataset)
                labels.append(label)
            except Exception as e:
                labels.append(None)
                errors.append(f"matchup {i} [{m['name']}]: cannot resolve {civ}/{slug} — {e}")
        if all(labels):
            plan.append((m["name"], labels[0], labels[1]))
    return errors, plan


def main():
    ap = argparse.ArgumentParser(description="Chain matchup videos back-to-back.")
    ap.add_argument("--matchup", action="append", required=True, type=_parse_matchup,
                    metavar="CIV1:slug1:CIV2:slug2:Name", help="repeatable")
    ap.add_argument("--copy-to", default=DEFAULT_COPY_TO,
                    help=f"output folder (default: {DEFAULT_COPY_TO})")
    ap.add_argument("--cap", type=int, default=240, help="per-fight recording safety cap (s)")
    ap.add_argument("--log", default="/tmp/auto_matchup.log")
    ap.add_argument("--dry-run", action="store_true",
                    help="validate matchups + environment and print the plan, then exit")
    a = ap.parse_args()
    open(a.log, "w").close()
    n = len(a.matchup)

    # ---- PRE-FLIGHT ------------------------------------------------------
    errors, plan = preflight(a.matchup, a.copy_to, a.log)
    log(f"=== BATCH of {n} matchup(s); {len(plan)} valid ===", a.log)
    for i, (name, l1, l2) in enumerate(plan, 1):
        log(f"  [{i}] {l1}  vs  {l2}   ->  {name}.mp4", a.log)
    if errors:
        for e in errors:
            log(f"  PRE-FLIGHT ERROR: {e}", a.log)
        log("Aborting — fix the matchups/environment above and re-run.", a.log)
        sys.exit(1)
    if not ui.accessibility_ok():
        log("PRE-FLIGHT ERROR: Accessibility not granted to this terminal — scripted "
            "clicks will fail. System Settings -> Privacy & Security -> Accessibility.", a.log)
        sys.exit(2)
    if a.dry_run:
        log("--dry-run: validation passed; not running.", a.log)
        return

    # ---- RUN -------------------------------------------------------------
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
            results.append((m["name"], "OK", str(final)))
        except Exception as e:
            log(f"[{i}/{n}] FAILED: {e}", a.log)
            results.append((m["name"], "FAILED", str(e)))

    # ---- SUMMARY ---------------------------------------------------------
    ok = sum(1 for _, s, _ in results if s == "OK")
    log(f"=== BATCH COMPLETE — {ok}/{n} succeeded ===", a.log)
    for name, status, detail in results:
        log(f"  [{status}] {name}  ->  {detail}", a.log)
    sys.exit(0 if ok == n else 1)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()

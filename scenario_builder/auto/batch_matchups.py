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
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SB = HERE.parent
sys.path.insert(0, str(SB))
sys.path.insert(0, str(SB / "overlay"))

from auto import input_driver as ui, platform_io             # noqa: E402
from auto.orchestrate_matchup import (                       # noqa: E402
    run_matchup, resolve_side, equal_resource_counts, RUN_DIR)
from auto.record_until_end import log                        # noqa: E402
from build_run import TEMPLATE, unit_const                   # noqa: E402

DEFAULT_COPY_TO = "/Volumes/Orchid/AOEII_videos/3kResMatchUpVideos"
TMP = platform_io.TMP_DIR                          # /tmp on mac, %TEMP% on windows


def _parse_matchup(s: str) -> dict:
    """'CIV1:slug1:CIV2:slug2:Display Name' -> dict (name may contain ':')."""
    parts = s.split(":", 4)
    if len(parts) != 5:
        raise argparse.ArgumentTypeError(
            f"matchup must be CIV1:slug1:CIV2:slug2:Name — got {s!r}")
    civ1, slug1, civ2, slug2, name = (p.strip() for p in parts)
    return dict(civ1=civ1, slug1=slug1, civ2=civ2, slug2=slug2, name=name)


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
    Path(out_txt).write_text("\n".join(lines) + "\n")
    return Path(out_txt)


def _slice_1based(spec: str, n: int):
    """'A:B' 1-based inclusive -> (lo, hi) python indices. 'A:'/':B'/'' tolerated."""
    if not spec:
        return 0, n
    a, _, b = spec.partition(":")
    lo = int(a) if a.strip() else 1
    hi = int(b) if b.strip() else n
    return max(0, lo - 1), hi


def matchups_from_list(list_path, slice_spec, opponent):
    """Build 'opponent vs each list entry' matchups from a unique_units.json list.
    `opponent` = 'CIV:slug' (the fixed side, e.g. Muisca:elite_temple_guard_muisca)."""
    entries = json.loads(Path(list_path).read_text())
    lo, hi = _slice_1based(slice_spec, len(entries))
    entries = entries[lo:hi]
    opp_civ, opp_slug = opponent.split(":", 1)
    opp_label = resolve_side(opp_civ, opp_slug)[2]
    out = []
    for e in entries:
        name = f"{opp_label} vs {e['name']} ({opp_civ} vs {e['civ']})"
        out.append(dict(civ1=opp_civ, slug1=opp_slug,
                        civ2=e["civ"], slug2=e["slug"], name=name))
    return out


def preflight(matchups, copy_to, mode="count", unit_cap=30, logfile=None):
    """Validate the whole batch before touching the game. Returns (errors, plan).
    `plan` is a list of (name, label1, label2, n1, n2) for the ones that resolve."""
    errors, plan = [], []
    # environment
    if not TEMPLATE.exists():
        errors.append(f"golden template missing: {TEMPLATE}")
    if not platform_io.recorder_available():
        errors.append(platform_io.recorder_hint())
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
            if mode == "resources":
                n1, n2 = equal_resource_counts(m["civ1"], m["slug1"],
                                               m["civ2"], m["slug2"], unit_cap)
            else:
                n1 = n2 = unit_cap
            plan.append((m["name"], labels[0], labels[1], n1, n2))
    return errors, plan


def main():
    ap = argparse.ArgumentParser(description="Chain matchup videos back-to-back.")
    ap.add_argument("--matchup", action="append", default=[], type=_parse_matchup,
                    metavar="CIV1:slug1:CIV2:slug2:Name", help="explicit matchup (repeatable)")
    ap.add_argument("--list", dest="list_path",
                    help="JSON unique-units list to run against --opponent (auto/unique_units.json)")
    ap.add_argument("--slice", help="1-based inclusive range into --list, e.g. 1:5")
    ap.add_argument("--opponent", metavar="CIV:slug",
                    help="fixed side for --list mode (e.g. Muisca:elite_temple_guard_muisca)")
    ap.add_argument("--join", metavar="NAME.mp4",
                    help="also concatenate every clip into ONE video with this filename")
    ap.add_argument("--resources", action="store_true",
                    help="equal-RESOURCE fight: cheaper unit capped at --unit-cap, "
                         "pricier unit count matched to the same total cost (f+w+g)")
    ap.add_argument("--unit-cap", type=int, default=30,
                    help="max units for the cheaper side (default 30)")
    ap.add_argument("--copy-to", default=DEFAULT_COPY_TO,
                    help=f"output folder (default: {DEFAULT_COPY_TO})")
    ap.add_argument("--cap", type=int, default=240, help="per-fight recording safety cap (s)")
    ap.add_argument("--log", default=str(Path(TMP) / "auto_matchup.log"))
    ap.add_argument("--dry-run", action="store_true",
                    help="validate matchups + environment and print the plan, then exit")
    a = ap.parse_args()
    open(a.log, "w").close()
    mode = "resources" if a.resources else "count"

    # ---- BUILD THE QUEUE -------------------------------------------------
    matchups = list(a.matchup)
    if a.list_path:
        if not a.opponent:
            log("ERROR: --list requires --opponent CIV:slug", a.log); sys.exit(2)
        matchups += matchups_from_list(a.list_path, a.slice, a.opponent)
    if not matchups:
        log("ERROR: no matchups — give --matchup or --list + --opponent.", a.log); sys.exit(2)
    n = len(matchups)

    # ---- PRE-FLIGHT ------------------------------------------------------
    errors, plan = preflight(matchups, a.copy_to, mode, a.unit_cap, a.log)
    log(f"=== BATCH of {n} matchup(s); {len(plan)} valid  [{mode}] ===", a.log)
    for i, (name, l1, l2, n1, n2) in enumerate(plan, 1):
        log(f"  [{i}] {l1} x{n1}  vs  {l2} x{n2}   ->  {name}.mp4", a.log)
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
        if a.join:
            log(f"--join: the {len(plan)} clips would be concatenated into {a.join}", a.log)
        log("--dry-run: validation passed; not running.", a.log)
        return

    # ---- RUN -------------------------------------------------------------
    # In --join mode the individual clips are NOT copied out — only the joined video
    # is the deliverable (kept in /tmp so we can concatenate them at the end).
    join_mode = bool(a.join)
    per_run_copy_to = None if join_mode else a.copy_to
    results, clips, chapters = [], [], []
    for i, m in enumerate(matchups, 1):
        log(f"===== [{i}/{n}] {m['name']} =====", a.log)
        try:
            final = run_matchup(
                m["civ1"], m["slug1"], m["civ2"], m["slug2"],
                name=f"{m['name']}.mp4", copy_to=per_run_copy_to,
                raw_copy_to=a.copy_to, cap=a.cap,    # archive the raw for EVERY run
                mode=mode, unit_cap=a.unit_cap,
                out_mov=str(Path(TMP) / f"auto_fight_{i}.mov"),
                final=str(Path(TMP) / f"auto_matchup_{i}.mp4"),
                dismiss_after=True, logfile=a.log)
            log(f"[{i}/{n}] DONE -> {final}", a.log)
            results.append((m["name"], "OK", str(final)))
            clips.append(str(final))
            # chapter label = the opponent unit (the varying side), e.g. "Aztec Jaguar Warrior"
            label = f"{_civ_adj(m['civ2'])} {resolve_side(m['civ2'], m['slug2'])[2].replace('Elite ', '')}"
            chapters.append((label, str(final)))
        except Exception as e:
            log(f"[{i}/{n}] FAILED: {e}", a.log)
            results.append((m["name"], "FAILED", str(e)))

    # ---- JOIN (one combined video) + CHAPTERS ---------------------------
    if join_mode and clips:
        from compose import concat_videos, _duration
        log(f"[join] concatenating {len(clips)} clip(s) -> {a.join} ...", a.log)
        joined = concat_videos(clips, str(Path(TMP) / "joined_matchups.mp4"))
        Path(a.copy_to).mkdir(parents=True, exist_ok=True)
        dest = Path(a.copy_to) / a.join
        shutil.copy2(joined, dest)
        log(f"[join] -> {dest} ({Path(dest).stat().st_size // 1024} KB)", a.log)
        # YouTube chapters .txt (cumulative start time per matchup)
        ch_entries = [(lbl, _duration(clip)) for lbl, clip in chapters]
        ch_path = write_chapters(ch_entries, Path(a.copy_to) / f"{Path(a.join).stem} chapters.txt")
        log(f"[chapters] -> {ch_path}", a.log)

    # ---- SUMMARY ---------------------------------------------------------
    ok = sum(1 for _, s, _ in results if s == "OK")
    log(f"=== BATCH COMPLETE — {ok}/{n} succeeded ===", a.log)
    for name, status, detail in results:
        log(f"  [{status}] {name}  ->  {detail}", a.log)
    if join_mode and clips:
        log(f"  JOINED -> {Path(a.copy_to) / a.join}", a.log)
    sys.exit(0 if ok == n else 1)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()

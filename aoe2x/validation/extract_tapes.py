"""Extract the in-game tape corpus into a self-contained fixture.

Ground truth for engine fidelity is ~40 recorded arena fights (ddkMatchupAI
patrol rig, 16x16 map, equal-resource counts, 5 runs per contested matchup).
Those recordings live on the `aoe2_ai_for_simulation` branch under
apps/video/sim_v2/. This script pulls them out via `git show` and writes a
committed fixture so the validation rig is self-contained — no branch checkout,
no network, reproducible on any machine with the repo.

Field semantics in the source files (verified 2026-07-27):
  * `outcome`      -- TAPE TRUTH (what the recording showed), from the
                      subject's perspective: "win" | "loss".
  * `wr`, `*_hp`   -- the V2 JS engine's ANSWER for that row. Kept so the
                      fixture also records where that engine disagreed.
  * `n_subject`/`n_opp` -- the exact arena counts the fight was recorded at.

A row counts as tape-verified when `ingame` is true, or when the subject's
overrides file pins an `ingame_outcome` for that opponent.

    python -m aoe2x.validation.extract_tapes            # writes tape_corpus.json
    python -m aoe2x.validation.extract_tapes --check    # verify, don't write
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

BRANCH = "origin/aoe2_ai_for_simulation"
SRC_DIR = "apps/video/sim_v2"
OUT = Path(__file__).resolve().parent / "tape_corpus.json"

SUBJECTS = [
    "elite_blackwood_archer_tupi",
    "elite_champi_warrior",
    "elite_guecha_warrior_muisca",
    "elite_ibirapema_warrior_tupi",
    "elite_kona_mapuche",
    "elite_temple_guard_muisca",
    "imp_slinger",
]


def _git_show(path: str):
    """Return parsed JSON at `path` on BRANCH, or None if absent."""
    try:
        raw = subprocess.run(
            ["git", "show", f"{BRANCH}:{path}"],
            capture_output=True, check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return None
    return json.loads(raw.decode("utf-8"))


def _split_key(key: str):
    """'Civ/slug' -> ('Civ', 'slug')."""
    civ, _, slug = key.partition("/")
    return civ, slug


def collect():
    corpus, missing = [], []
    for subj_slug in SUBJECTS:
        res = _git_show(f"{SRC_DIR}/results/{subj_slug}.json")
        if res is None:
            missing.append(subj_slug)
            continue
        subject = res["subject"]
        ovr = _git_show(f"{SRC_DIR}/overrides/{subj_slug}.json") or {}
        pins = ovr.get("ingame_outcome", {}) or {}

        # Index the sim rows so override-only pins can still find their counts.
        by_opp = {(r["civ"], r["slug"]): r for r in res.get("rows", [])}

        keys = {k for k, r in by_opp.items() if r.get("ingame")}
        keys |= {_split_key(k) for k in pins}

        for civ, slug in sorted(keys):
            row = by_opp.get((civ, slug))
            if row is None:
                # Pinned opponent that never made it into the sim table; we have
                # the outcome but not the counts, so it cannot be simulated.
                missing.append(f"{subj_slug} vs {civ}/{slug} (no counts)")
                continue
            tape = pins.get(f"{civ}/{slug}") or row.get("outcome")
            if tape not in ("win", "loss"):
                missing.append(f"{subj_slug} vs {civ}/{slug} (outcome={tape!r})")
                continue
            corpus.append({
                "subject_civ": subject["civ"],
                "subject_slug": subject["slug"],
                "subject_name": subject["name"],
                "opp_civ": civ,
                "opp_slug": slug,
                "opp_name": row.get("name"),
                "n_subject": row["n_subject"],
                "n_opp": row["n_opp"],
                # ground truth
                "tape_outcome": tape,
                # what the V2 JS engine said, for reference/comparison only
                "v2_wr": row.get("wr"),
                "v2_subject_hp": row.get("subject_hp"),
                "v2_opp_hp": row.get("opp_hp"),
                "v2_agrees": (tape == "win") == (row.get("wr", 0) >= 0.5),
            })
    return corpus, missing


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report what would be extracted; do not write")
    a = ap.parse_args()

    corpus, missing = collect()
    if not corpus:
        sys.exit(f"no tape rows extracted — is {BRANCH} fetched?")

    by_subj: dict[str, int] = {}
    for r in corpus:
        by_subj[r["subject_slug"]] = by_subj.get(r["subject_slug"], 0) + 1

    print(f"tape rows: {len(corpus)}")
    for s, n in sorted(by_subj.items()):
        print(f"  {s:<34} {n:3d}")
    disagree = [r for r in corpus if not r["v2_agrees"]]
    print(f"V2 JS engine disagrees with tape on {len(disagree)}/{len(corpus)} rows")
    if missing:
        print(f"skipped {len(missing)}:")
        for m in missing[:10]:
            print(f"  - {m}")

    if a.check:
        return
    OUT.write_text(json.dumps({
        "_comment": "In-game tape corpus. Ground truth = tape_outcome. "
                    "Extracted by aoe2x/validation/extract_tapes.py from "
                    f"{BRANCH}:{SRC_DIR}. Do not hand-edit.",
        "source_branch": BRANCH,
        "rows": corpus,
    }, indent=1), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

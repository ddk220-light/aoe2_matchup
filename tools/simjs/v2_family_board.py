"""Per-FAMILY tape-vs-engine board, and an old-corpus / v2-corpus truth diff.

Why a family board
------------------
``aoe2x.calibration.score`` scores one RECORDING at a time, which is the right
unit for a metric gate and the wrong unit for the question "does the engine
pick the same side the game does?". A single recording's winner is one sample
of a stochastic fight: a family with 12 recordings and a 9/12 split is not
telling you the engine is wrong when it loses 3 of them -- it is telling you
the true win-share is ~75%. Comparing a 20-seed engine distribution against a
one-shot tape, recording by recording, cannot see that. This tool aggregates
BOTH sides of the comparison up to the matchup (family) level, where the two
are actually commensurable:

    tape win-share   = fights this slug won / recordings in the family
    engine win-share = seeds this slug won / (recordings x seeds)

and reports the HP-remaining and duration errors alongside, so a family that
picks the right winner for the wrong reason is still visible.

Duration
--------
A truth card's ``duration_s`` is the RECORDER SEGMENT length, not the fight's:
the capture keeps running after the last unit falls. Comparing a sim's
``duration_s`` (which ends at the wipe) against it therefore always reports the
sim as "too fast". This tool takes the tape's ACTUAL WIPE -- the timestamp of
the last damage event in the tape's own stream -- and reports both, because the
gap between them is itself worth seeing.

Corpus split
------------
Fights are split by the manifest's ``drop`` field. ``--drop-substr`` selects
the "new" corpus (default ``melee_v2``); everything else in the same matchup is
the "old" corpus, which is what the ``OLD vs NEW`` section diffs.

Usage::

    python tools/simjs/v2_family_board.py --sim-runs-dir calibration/runs/v2-melee
    python tools/simjs/v2_family_board.py --sim-runs-dir <dir> --json board.json
"""
from __future__ import annotations

import argparse
import gzip
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from aoe2x.calibration.paths import workspace_paths  # noqa: E402

PATHS = workspace_paths()
CALIB = PATHS.fixtures_dir
TAPES = PATHS.tapes_dir


def load_manifest():
    return json.loads((CALIB / "manifest.json").read_text(encoding="utf-8"))["fights"]


def load_dicts():
    return json.loads((CALIB / "combat_dicts.json").read_text(encoding="utf-8"))


def _outcome_rank(side):
    """(survivors, hp) -- higher is better. Same ordering the scorer uses."""
    return (side.get("survivors") or 0, side.get("hp_remaining") or 0)


def _winner(sides):
    """Owner key of the better-off side, or None on an exact tie."""
    ranked = sorted(sides.items(), key=lambda kv: _outcome_rank(kv[1]), reverse=True)
    if len(ranked) < 2:
        return None
    if _outcome_rank(ranked[0][1]) == _outcome_rank(ranked[1][1]):
        return None
    return ranked[0][0]


def tape_wipe_s(tag: str) -> float | None:
    """Timestamp of the tape's last damage event -- when the fighting stopped.

    Read off the recording's own ``.damage.jsonl.gz``; ``None`` if the tape is
    not on disk. This is deliberately NOT the truth card's ``duration_s`` (see
    the module docstring).
    """
    p = TAPES / tag / f"{tag}.damage.jsonl.gz"
    if not p.exists():
        return None
    last = None
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            last = row.get("t", last)
    return last


def collect(sim_runs_dir: Path, seeds, drop_substr: str):
    """One row per fight: tape outcome, per-seed engine outcomes, HP, duration."""
    dicts = load_dicts()
    rows = []
    for fight in load_manifest():
        run_id = fight["run_id"]
        truth_p = CALIB / "truth" / f"{run_id}.json"
        if not truth_p.exists():
            continue
        truth = json.loads(truth_p.read_text(encoding="utf-8"))
        # Truth cards key sides "side<owner>"; sim runs key the bare owner.
        tape_sides = {k.replace("side", ""): v for k, v in truth["sides"].items()}

        raws = []
        for s in seeds:
            p = sim_runs_dir / run_id / f"seed-{s}.json"
            if p.exists():
                raws.append(json.loads(p.read_text(encoding="utf-8")))

        # owner key -> slug, and each side's total army HP, from the manifest
        # side blocks (NOT from side ORDER -- the tag's word order does not
        # decide which manifest side is which owner).
        slug_of, army_of, count_of = {}, {}, {}
        for side in (fight["side1"], fight["side2"]):
            key = str(side["owner"])
            slug_of[key] = side["slug"]
            count_of[key] = side["count"]
            cd = dicts.get(f"{side['civ']}|{side['slug']}")
            army_of[key] = float(cd["hp"]) * side["count"] if cd else None

        tape_win = _winner(tape_sides)
        rows.append({
            "tag": fight["tag"],
            "run_id": run_id,
            "matchup": fight["matchup"],
            "is_new": drop_substr in (fight.get("drop") or ""),
            "slug_of": slug_of,
            "count_of": count_of,
            "army_of": army_of,
            "tape_winner": tape_win,
            "tape_winner_slug": slug_of.get(tape_win) if tape_win else None,
            "tape_hp": {k: (v.get("hp_remaining") or 0.0) for k, v in tape_sides.items()},
            "tape_survivors": {k: (v.get("survivors") or 0) for k, v in tape_sides.items()},
            "tape_card_duration": truth.get("duration_s"),
            "seed_winners": [_winner(r["sides"]) for r in raws],
            "sim_hp": {
                k: statistics.median([r["sides"][k]["hp_remaining"] for r in raws
                                      if k in r["sides"]])
                for k in tape_sides if any(k in r["sides"] for r in raws)
            } if raws else {},
            "sim_duration": statistics.median([r["duration_s"] for r in raws]) if raws else None,
            "n_seeds": len(raws),
        })
    return rows


def _pct(hp, army):
    return None if not army else 100.0 * hp / army


def family_board(rows, *, want_new=True):
    """Aggregate fight rows into one entry per matchup."""
    fams = defaultdict(list)
    for r in rows:
        if r["is_new"] == want_new:
            fams[r["matchup"]].append(r)

    out = []
    for matchup, frs in sorted(fams.items()):
        keys = sorted(frs[0]["slug_of"])
        slugs = {k: frs[0]["slug_of"][k] for k in keys}
        n = len(frs)

        tape_wins = {k: sum(1 for r in frs if r["tape_winner"] == k) for k in keys}
        seed_wins = {k: 0 for k in keys}
        n_seeds_total = 0
        for r in frs:
            for w in r["seed_winners"]:
                n_seeds_total += 1
                if w in seed_wins:
                    seed_wins[w] += 1

        per_side = {}
        for k in keys:
            tape_pcts, sim_pcts, errs = [], [], []
            for r in frs:
                army = r["army_of"].get(k)
                tp = _pct(r["tape_hp"].get(k, 0.0), army)
                sp = _pct(r["sim_hp"].get(k), army) if k in r["sim_hp"] else None
                if tp is not None:
                    tape_pcts.append(tp)
                if sp is not None:
                    sim_pcts.append(sp)
                if tp is not None and sp is not None:
                    errs.append(sp - tp)
            per_side[k] = {
                "slug": slugs[k],
                "count": frs[0]["count_of"][k],
                "tape_hp_pct": statistics.mean(tape_pcts) if tape_pcts else None,
                "sim_hp_pct": statistics.mean(sim_pcts) if sim_pcts else None,
                "hp_err_pts": statistics.mean(errs) if errs else None,
                "hp_abs_err_pts": statistics.mean(abs(e) for e in errs) if errs else None,
            }

        wipes = [w for w in (r.get("tape_wipe") for r in frs) if w]
        card_durs = [r["tape_card_duration"] for r in frs if r["tape_card_duration"]]
        sim_durs = [r["sim_duration"] for r in frs if r["sim_duration"]]

        out.append({
            "matchup": matchup,
            "n_recordings": n,
            "n_seeds": n_seeds_total,
            "keys": keys,
            "slugs": slugs,
            "tape_wins": tape_wins,
            "tape_share": {k: tape_wins[k] / n for k in keys},
            "seed_wins": seed_wins,
            "engine_share": {k: (seed_wins[k] / n_seeds_total if n_seeds_total else None)
                             for k in keys},
            "sides": per_side,
            "tape_wipe_s": statistics.mean(wipes) if wipes else None,
            "tape_card_s": statistics.mean(card_durs) if card_durs else None,
            "sim_s": statistics.mean(sim_durs) if sim_durs else None,
            "tags": sorted(r["tag"] for r in frs),
        })
    return out


def print_board(board, title):
    print(f"\n{'=' * 118}\n{title}\n{'=' * 118}")
    hdr = (f"{'family':38s} {'n':>3s}  {'side':>14s} {'tapeW':>7s} {'engW':>7s} "
           f"{'tapeHP%':>8s} {'simHP%':>8s} {'dHP':>7s}   {'wipe_s':>7s} {'sim_s':>7s}")
    print(hdr)
    print("-" * 118)
    for f in board:
        for i, k in enumerate(f["keys"]):
            s = f["sides"][k]
            lead = f["matchup"][:38] if i == 0 else ""
            nrec = str(f["n_recordings"]) if i == 0 else ""
            wipe = f"{f['tape_wipe_s']:.1f}" if i == 0 and f["tape_wipe_s"] else ""
            sims = f"{f['sim_s']:.1f}" if i == 0 and f["sim_s"] else ""
            tw = f"{100 * f['tape_share'][k]:5.0f}%"
            ew = (f"{100 * f['engine_share'][k]:5.0f}%"
                  if f["engine_share"][k] is not None else "    -")
            th = f"{s['tape_hp_pct']:7.1f}" if s["tape_hp_pct"] is not None else "      -"
            sh = f"{s['sim_hp_pct']:7.1f}" if s["sim_hp_pct"] is not None else "      -"
            dh = f"{s['hp_err_pts']:+6.1f}" if s["hp_err_pts"] is not None else "     -"
            flag = ""
            if i == 0:
                ts = f["tape_share"]
                es = f["engine_share"]
                tw_k = max(ts, key=lambda x: ts[x])
                ew_k = max(es, key=lambda x: (es[x] or 0))
                if ts[tw_k] > 0.5 and (es[ew_k] or 0) > 0.5 and tw_k != ew_k:
                    flag = "  <== WINNER FLIP"
            print(f"{lead:38s} {nrec:>3s}  {s['slug'][:14]:>14s} {tw:>7s} {ew:>7s} "
                  f"{th:>8s} {sh:>8s} {dh:>7s}   {wipe:>7s} {sims:>7s}{flag}")
        print("-" * 118)


def print_old_vs_new(rows):
    """Family-level truth diff: the OLD corpus's winner/share vs the NEW one's.

    A winner match is NOT on its own proof the old capture was sound. A family
    can name the same victor in both corpora and still disagree about how close
    the fight was, and the margin is what every HP-remaining constant is fitted
    against. So the diff carries the WINNING SIDE's mean HP-remaining (% of its
    army's max) from each corpus, and calls out a family whose margin moved a
    lot even though the winner did not -- plus the families whose v2 margin is
    thin enough that a single old recording could have landed either way.
    """
    old = defaultdict(list)
    new = defaultdict(list)
    for r in rows:
        (new if r["is_new"] else old)[r["matchup"]].append(r)

    both = sorted(set(old) & set(new))
    only_old = sorted(set(old) - set(new))
    print(f"\n{'=' * 118}\nOLD vs NEW TRUTH (tape only -- no engine involved)\n{'=' * 118}")
    print(f"{'family':34s} {'oldn':>4s} {'old winner':>15s} {'shr':>5s} {'HP%':>5s}  "
          f"{'newn':>4s} {'new winner':>15s} {'shr':>5s} {'HP%':>5s}  verdict")
    print("-" * 118)

    def side_share(frs):
        keys = sorted(frs[0]["slug_of"])
        wins = {k: sum(1 for r in frs if r["tape_winner"] == k) for k in keys}
        best = max(keys, key=lambda k: wins[k])
        # Winner-side HP margin, averaged over the recordings this side won.
        won = [r for r in frs if r["tape_winner"] == best]
        pcts = [p for p in (_pct(r["tape_hp"].get(best, 0.0), r["army_of"].get(best))
                            for r in won) if p is not None]
        margin = statistics.mean(pcts) if pcts else None
        return frs[0]["slug_of"][best], wins[best] / len(frs), best, margin

    thin = []
    for m in both:
        os_, osh, okey, omg = side_share(old[m])
        ns_, nsh, nkey, nmg = side_share(new[m])
        if okey != nkey:
            verdict = "*** MISCAPTURED -- winner flipped"
        elif abs(osh - nsh) >= 0.34:
            verdict = "shape shifted (winner held, share moved >=34pts)"
        elif omg is not None and nmg is not None and abs(omg - nmg) >= 15.0:
            verdict = f"margin moved {omg - nmg:+.0f}pts (winner held)"
        else:
            verdict = "agrees"
        # A family the v2 corpus shows as a coin-flip is one the old corpus's
        # single recording could not have pinned down either way.
        if nmg is not None and (nmg < 20.0 or nsh <= 0.75) and len(old[m]) <= 2 and okey == nkey:
            thin.append((m, len(old[m]), ns_, nsh, nmg))
        om = f"{omg:4.0f}" if omg is not None else "   -"
        nm = f"{nmg:4.0f}" if nmg is not None else "   -"
        print(f"{m[:34]:34s} {len(old[m]):4d} {os_[:15]:>15s} {100 * osh:4.0f}% {om:>5s}  "
              f"{len(new[m]):4d} {ns_[:15]:>15s} {100 * nsh:4.0f}% {nm:>5s}  {verdict}")

    if thin:
        print(f"\nUNDER-SAMPLED IN THE OLD CORPUS ({len(thin)}): v2 shows these as close "
              f"fights, old corpus has <=2 recordings --\nthe old winner agreeing is luck, "
              f"not confirmation. Weight them by the v2 share, not the old one:")
        for m, n_old, slug, sh, mg in thin:
            print(f"  {m[:44]:44s} old n={n_old}  v2: {slug} {100 * sh:.0f}% at {mg:.0f}% HP")
    if only_old:
        print(f"\nfamilies in the OLD corpus with NO v2 re-recording ({len(only_old)}):")
        for m in only_old:
            os_, osh, _, _ = side_share(old[m])
            print(f"  {m[:44]:44s} n={len(old[m]):2d}  {os_} {100 * osh:.0f}%")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sim-runs-dir", type=Path, default=PATHS.runs_dir / "v2-melee")
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--drop-substr", default="melee_v2",
                    help="manifest `drop` substring identifying the NEW corpus")
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--no-wipe", action="store_true",
                    help="skip reading tape damage streams for actual-wipe times")
    args = ap.parse_args()

    seeds = list(range(1, args.seeds + 1))
    rows = collect(args.sim_runs_dir, seeds, args.drop_substr)
    if not args.no_wipe:
        for r in rows:
            r["tape_wipe"] = tape_wipe_s(r["tag"])

    new_board = family_board(rows, want_new=True)
    print_board(new_board, f"V2 FAMILY BOARD -- tape vs engine ({args.sim_runs_dir})")
    print_old_vs_new(rows)

    if args.json:
        args.json.write_text(json.dumps(
            {"new_board": new_board, "fights": rows}, indent=2, default=str) + "\n",
            encoding="utf-8")
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()

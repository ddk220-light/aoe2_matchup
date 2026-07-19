"""build_reel.py — cut a vertical (9:16) ~15s short-form reel for one subject unit.

A post-process on already-recorded fights (no game needed): pick the two most
compelling matchups, then intro -> fight A -> fight B -> CTA via reel_compose.

Selection is driven by the V2 categorization JSON (apps/video/sim_v2/results/<subj>.json)
and favours the SURPRISING content (see select_reel_matchups). Each fight needs its raw
`.mov` + `.hp.json` on disk (clean gameplay for the middle band).

    # auto (needs categorization JSON + a dir of raws):
    python -m auto.build_reel --subject "Muisca:elite_temple_guard_muisca" \
        --cat apps/video/sim_v2/results/elite_temple_guard_muisca.json \
        --raws-dir "C:/Users/ddk22/Videos/aoe2_matchups/etg_v2/raw recordings" \
        --out "C:/Users/ddk22/Videos/aoe2_matchups/etg_v2/elite_temple_guard_muisca_reel.mp4"

    # manual (hand-picked fights; verdict = category name or win/loss). Unique-unit slugs
    # carry the civ suffix; standard-unit slugs are the plain name (e.g. champion):
    python -m auto.build_reel --subject "Mapuche:elite_bolas_rider_mapuche" \
        --fight "<raw.mov>||loss|Byzantines:elite_cataphract_byzantines" \
        --fight "<raw.mov>||win|Mongols:elite_mangudai_mongols" \
        --out "<out.mp4>"

Auto mode is the intended path once a subject has BOTH a categorization JSON and its
raws on disk; manual mode is for hand-curated reels / validating without categorization.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SB = HERE.parent
sys.path.insert(0, str(SB))

# start the clip this many seconds after game-time zero (matches record_until_end.PATROL_LEAD)
PATROL_LEAD = 1.3


def select_reel_matchups(cat: dict, cap: int = 2):
    """Pick up to `cap` (verdict_kind, row) matchups from a V2 categorization dict,
    favouring surprising content: one unexpected win + one unexpected loss; else the
    unit's range (expected win + expected loss); a lone surprise is paired with the
    opposite-valence expected pick. 'top' = the first showcase pick (already ordered by
    the long-form pipeline: wins most-expensive, losses cheapest).

    `showcase[kind]` entries are [civ, slug] pairs; each is joined to the full `rows`
    entry (for name/metadata). Also accepts dict rows directly (hand-built/tests)."""
    show = cat.get("showcase") or {}
    by_key = {(r.get("civ"), r.get("slug")): r for r in (cat.get("rows") or [])}

    def top(kind):
        picks = show.get(kind) or []
        if not picks:
            return None
        first = picks[0]
        if isinstance(first, (list, tuple)):            # [civ, slug] -> full row
            civ, slug = first[0], first[1]
            row = by_key.get((civ, slug)) or {"civ": civ, "slug": slug, "name": slug}
        else:
            row = first                                 # already a row dict
        return (kind, row)

    picks = [p for p in (top("unexpected_win"), top("unexpected_loss")) if p]
    if not picks:
        picks = [p for p in (top("expected_win"), top("expected_loss")) if p]
    elif len(picks) == 1:
        only = picks[0][0]
        mate = top("expected_loss") if "win" in only else top("expected_win")
        if mate:
            picks.append(mate)
    return picks[:cap]


def _outcome(sidecar) -> tuple | None:
    """(subject_wins, subj_survivors, opp_survivors) from the last sidecar row (side1 =
    subject in the sweep sidecars). None if unreadable or a draw."""
    try:
        r = (json.load(open(sidecar)).get("rows")) or []
    except Exception:
        return None
    if not r:
        return None
    s1, s2 = int(r[-1]["side1"]["count"]), int(r[-1]["side2"]["count"])
    if s1 > 0 and s2 <= 0:
        return (True, s1, s2)
    if s2 > 0 and s1 <= 0:
        return (False, s1, s2)
    return None


def _footage_verdict(favored, subj_wins) -> str:
    """verdict_kind from who was FAVORED (sim) + who actually WON (footage). Keeps the
    chip truthful to the clip even when the sim's category disagrees with the recording."""
    if favored == "subject":
        return "expected_win" if subj_wins else "unexpected_loss"
    if favored in ("opponent", "both"):
        return "unexpected_win" if subj_wins else "expected_loss"
    return "win" if subj_wins else "loss"                    # 'neither' — no strong prior


def select_from_footage(cat: dict, resolve, cap: int = 2):
    """Footage-truthful selection: for each showcase candidate, resolve its recording,
    read the REAL outcome, and re-derive the verdict. Same preference as the sim-only rule
    (unexpected win + unexpected loss, one of each valence, else the unit's range), but a
    matchup only counts as an 'unexpected win' if it actually WON on tape. `resolve(row)`
    returns a sidecar path (or None if no footage). Returns [(verdict_kind, row)]."""
    by_key = {(r.get("civ"), r.get("slug")): r for r in (cat.get("rows") or [])}
    seen, cands = set(), []
    for pairs in (cat.get("showcase") or {}).values():
        for civ, slug in pairs:
            if (civ, slug) in seen:
                continue
            seen.add((civ, slug))
            row = by_key.get((civ, slug))
            if not row:
                continue
            sc = resolve(row)
            oc = _outcome(sc) if sc else None
            if oc is None:
                continue
            subj_wins, s1, s2 = oc
            kind = _footage_verdict(row.get("favored"), subj_wins)
            margin = s1 if subj_wins else s2                 # dominance for ranking
            cands.append((kind, row, margin))

    def top(kind):
        c = sorted((x for x in cands if x[0] == kind), key=lambda x: x[2], reverse=True)
        return (c[0][0], c[0][1]) if c else None

    picks = [p for p in (top("unexpected_win"), top("unexpected_loss")) if p]
    if not picks:
        picks = [p for p in (top("expected_win"), top("expected_loss")) if p]
    elif len(picks) == 1:
        only = picks[0][0]
        mate = (top("expected_loss") or top("loss")) if "win" in only \
            else (top("expected_win") or top("win"))
        if mate:
            picks.append(mate)
    return picks[:cap]


def _sidecar_for(raw: Path) -> Path | None:
    for cand in (raw.with_suffix(".hp.json"),
                 Path(str(raw.with_suffix("")) + ".grpc.hp.json"),
                 Path(str(raw.with_suffix("")) + ".ocr.hp.json")):
        if cand.exists():
            return cand
    return None


def _lead_in(sidecar: Path) -> float:
    try:
        gs = json.load(open(sidecar)).get("video_game_start_s")
    except Exception:
        gs = None
    return (gs if gs is not None else 6.0) + PATROL_LEAD


def _why(subj_name, opp_name, verdict_kind):
    win = "win" in verdict_kind
    if verdict_kind == "unexpected_loss":
        return f"{subj_name} should win this — but the {opp_name} over-performs."
    if verdict_kind == "unexpected_win":
        return f"{subj_name} isn't favoured, yet it beats the {opp_name}."
    if win:
        return f"{subj_name} shreds the {opp_name}."
    return f"The {opp_name} overwhelms {subj_name}."


def _find_raw(raws_dir: Path, opp_slug: str, opp_name: str) -> Path | None:
    """Best-effort: a .mov in raws_dir whose name contains the opponent slug/name."""
    if not raws_dir or not raws_dir.exists():
        return None
    needles = [opp_slug.lower(), opp_name.lower(), opp_name.lower().replace("elite ", "")]
    for mov in sorted(raws_dir.glob("*.mov")):
        low = mov.stem.lower()
        if any(nd and nd in low for nd in needles):
            return mov
    return None


def main():
    from overlay.overlay_data import get_unit_card
    from overlay import reel_compose

    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", required=True, metavar="Civ:slug")
    ap.add_argument("--cat", default=None, help="V2 categorization JSON (auto mode)")
    ap.add_argument("--raws-dir", default=None, help="dir of raw .mov + .hp.json (auto mode)")
    ap.add_argument("--fight", action="append", default=[],
                    metavar="raw|sidecar|verdict|OppCiv:oppslug",
                    help="manual fight (repeatable); sidecar '' = derive from raw")
    ap.add_argument("--out", required=True)
    ap.add_argument("--work-dir", default=None)
    a = ap.parse_args()

    sciv, sslug = a.subject.split(":", 1)
    scard = get_unit_card(sciv, sslug)
    subject = {"name": scard["name"], "civ": sciv, "slug": sslug, "icon": scard["icon"]}

    fights = []
    if a.fight:
        for spec in a.fight:
            raw_s, side_s, verdict, opp = spec.split("|")
            oc, oslug = opp.split(":", 1)
            raw = Path(raw_s)
            sidecar = Path(side_s) if side_s else _sidecar_for(raw)
            if sidecar is None or not sidecar.exists():
                sys.exit(f"no sidecar for {raw}")
            ocard = get_unit_card(oc, oslug)
            fights.append({
                "raw": str(raw), "sidecar": str(sidecar),
                "u1": scard, "u2": ocard, "subj_slug": sslug,
                "verdict_kind": verdict, "why": _why(scard["name"], ocard["name"], verdict),
                "lead_in": _lead_in(sidecar),
            })
    elif a.cat:
        cat = json.load(open(a.cat))
        raws_dir = Path(a.raws_dir) if a.raws_dir else None
        cache = {}                                          # (civ,slug) -> (raw, sidecar)

        def resolve(row):
            key = (row["civ"], row["slug"])
            if key not in cache:
                raw = _find_raw(raws_dir, row["slug"], row["name"]) if raws_dir else None
                sc = _sidecar_for(raw) if raw else None
                cache[key] = (raw, sc) if (raw and sc) else (None, None)
            return cache[key][1]

        # footage-truthful when raws are present; sim-only picks otherwise (no build)
        picks = select_from_footage(cat, resolve) if raws_dir else select_reel_matchups(cat)
        for kind, row in picks:
            raw, sidecar = cache.get((row["civ"], row["slug"]), (None, None))
            if raw is None or sidecar is None:
                print(f"[skip] no footage for {row['name']} ({kind})")
                continue
            ocard = get_unit_card(row["civ"], row["slug"])
            fights.append({
                "raw": str(raw), "sidecar": str(sidecar),
                "u1": scard, "u2": ocard, "subj_slug": sslug,
                "verdict_kind": kind, "why": _why(scard["name"], ocard["name"], kind),
                "lead_in": _lead_in(sidecar),
            })
            print(f"[pick] {kind:16} {row['name']}  <- {Path(raw).name}")
    else:
        sys.exit("pass --cat (+--raws-dir) for auto mode, or one or more --fight for manual")

    if not fights:
        sys.exit("no usable fights resolved")
    out = reel_compose.build_reel_video(subject, fights, a.out, work_dir=a.work_dir)
    from overlay.compose import _duration
    print(f"WROTE {out}  ({_duration(out):.1f}s, {out.stat().st_size // 1024} KB, "
          f"{len(fights)} fights)")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()

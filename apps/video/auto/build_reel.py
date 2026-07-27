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


def _subject_first_sidecar(sidecar: Path, n_subject, n_opp, work: Path) -> Path:
    """Return a sidecar whose side1 is the SUBJECT.

    RAW gRPC sidecars are in PLAYER (P2/P3) order, which is opponent-first whenever the
    builder put the opponent in the P2 slot — record_until_end corrects this for the
    finished clip, but the archived raw keeps the original order. Reading it as-is
    reports the wrong winner AND labels the HP band backwards (2026-07-24: the ETG's
    Blackwood Archer fight, a 0-survivor loss, was published as an 'unexpected WIN').

    Detect it the same way record_until_end does — row 0 matching the REVERSED start
    counts — and write a corrected copy. The normalized sidecar sitting next to the
    finished clip is NOT a substitute: its video_game_start_s is aligned to the trimmed
    clip, not to the raw .mov this reel cuts from.
    """
    d = json.load(open(sidecar))
    rows = d.get("rows") or []
    if not rows or n_subject is None or n_opp is None or int(n_subject) == int(n_opp):
        return sidecar
    c0 = (int(rows[0]["side1"]["count"]), int(rows[0]["side2"]["count"]))
    if c0 != (int(n_opp), int(n_subject)):
        return sidecar
    for r in rows:
        r["side1"], r["side2"] = r["side2"], r["side1"]
    work.mkdir(parents=True, exist_ok=True)
    out = work / (Path(sidecar).name.replace(".hp.json", "") + ".subjfirst.hp.json")
    out.write_text(json.dumps(d))
    print(f"[sidecar] {Path(sidecar).name}: raw was opponent-first "
          f"({c0[0]}v{c0[1]}) — swapped to subject-first")
    return out


def select_one_per_category(cat: dict, resolve, order=None):
    """One matchup per category, in narrative order — the per-category short. Uses the
    showcase pick already chosen by the long-form pipeline (wins: most expensive; losses:
    cheapest) so the short agrees with the YouTube cut, and skips categories with no
    footage on disk."""
    order = order or ("expected_win", "unexpected_win", "coin_flip",
                      "unexpected_loss", "expected_loss")
    by_key = {(r.get("civ"), r.get("slug")): r for r in (cat.get("rows") or [])}
    show = cat.get("showcase") or {}
    picks = []
    for kind in order:
        for pair in (show.get(kind) or []):
            civ, slug = (pair[0], pair[1]) if isinstance(pair, (list, tuple)) else \
                (pair.get("civ"), pair.get("slug"))
            row = by_key.get((civ, slug))
            if row is None or resolve(row) is None:
                continue
            picks.append((kind, row))
            break
    return picks


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


def _attack_gif_for(slug: str, name: str = "") -> Path | None:
    """The unit's attack gif for the top band: local media first (full slug, then the
    civ-suffix-stripped form), else fetched once from the public bucket mirror
    (aoe2matchup.com/assets/gifs/<slug>.gif) and cached under the media root. The
    bucket keys derive from DISPLAY names, so those are tried too (the project's
    staple slug 'elite_elephant' lives in the bucket as 'elite_battle_elephant').
    Returns None when nothing resolves — the caller falls back to the static icon."""
    from overlay.assets import AssetResolver
    res = AssetResolver()
    cands = [slug]
    stripped = slug.rsplit("_", 1)[0]
    if stripped != slug:
        cands.append(stripped)
    if name:
        from_name = name.lower().replace(" ", "_").replace("-", "_")
        if from_name not in cands:
            cands.append(from_name)
    for s in cands:
        p = res.attack_gif(s)
        if p is not None:
            return p
    if res.root is None:
        return None
    import urllib.request
    for s in cands:
        dest = res.root / "gifs" / f"{s}.gif"
        if dest.exists():
            return dest
        try:
            req = urllib.request.Request(f"https://aoe2matchup.com/assets/gifs/{s}.gif")
            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read()
            if data[:4] == b"GIF8":                 # not an error page
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                print(f"[gif] fetched {s}.gif from the bucket -> {dest}")
                return dest
        except Exception:
            continue
    return None


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
    ap.add_argument("--per-category", action="store_true",
                    help="one fight per category in narrative order (not the 2-pick reel)")
    ap.add_argument("--pacing", choices=("reel", "long"), default="reel",
                    help="'long' = each fight at its YouTube-cut length, no extra speed-up")
    a = ap.parse_args()

    sciv, sslug = a.subject.split(":", 1)
    scard = get_unit_card(sciv, sslug)
    scard = {**scard, "gif": _attack_gif_for(sslug, scard.get("name", ""))}
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

        # combat dicts (for the stats/TTK panel): next to the categorization JSON, or
        # in the matching sim workdir when --cat points at results/<subject>.json
        cd_path = Path(a.cat).parent / "combat_dicts_all.json"
        if not cd_path.exists():
            cd_path = (Path(a.cat).parent.parent / "_work" / Path(a.cat).stem
                       / "combat_dicts_all.json")
        combat = json.load(open(cd_path)) if cd_path.exists() else {}
        if not combat:
            print(f"[panel] no combat_dicts_all.json near {a.cat} — stats panel skipped")

        sc_work = Path(a.work_dir or Path(a.out).parent) / "_reel_sidecars"

        def resolve(row):
            key = (row["civ"], row["slug"])
            if key not in cache:
                raw = _find_raw(raws_dir, row["slug"], row["name"]) if raws_dir else None
                sc = _sidecar_for(raw) if raw else None
                if raw and sc:
                    sc = _subject_first_sidecar(sc, row.get("n_subject"),
                                                row.get("n_opp"), sc_work)
                cache[key] = (raw, sc) if (raw and sc) else (None, None)
            return cache[key][1]

        if a.per_category:
            picks = select_one_per_category(cat, resolve)
        elif raws_dir:
            picks = select_from_footage(cat, resolve)   # footage-truthful
        else:
            picks = select_reel_matchups(cat)           # sim-only (no build)
        for kind, row in picks:
            raw, sidecar = cache.get((row["civ"], row["slug"]), (None, None))
            if raw is None or sidecar is None:
                print(f"[skip] no footage for {row['name']} ({kind})")
                continue
            ocard = get_unit_card(row["civ"], row["slug"])
            ocard = {**ocard, "gif": _attack_gif_for(row["slug"], row.get("name", ""))}
            cd1 = combat.get(f"{sciv}/{sslug}")
            cd2 = combat.get(f"{row['civ']}/{row['slug']}")
            panel = None
            if cd1 and cd2 and row.get("n_subject") and row.get("n_opp"):
                panel = {"hero": {"name": scard["name"], "cd": cd1, "slug": sslug},
                         "opp": {"name": ocard["name"], "cd": cd2, "slug": row["slug"]},
                         "n1": row["n_subject"], "n2": row["n_opp"]}
            fights.append({
                "raw": str(raw), "sidecar": str(sidecar),
                "u1": scard, "u2": ocard, "subj_slug": sslug,
                "verdict_kind": kind, "why": _why(scard["name"], ocard["name"], kind),
                "lead_in": _lead_in(sidecar), "panel": panel,
            })
            print(f"[pick] {kind:16} {row['name']}  <- {Path(raw).name}"
                  + ("" if panel else "  (no stats panel)"))
    else:
        sys.exit("pass --cat (+--raws-dir) for auto mode, or one or more --fight for manual")

    if not fights:
        sys.exit("no usable fights resolved")
    from overlay.assets import AssetResolver
    voices = AssetResolver().voice_lines(sciv)
    n_matchups = len((cat.get("all_results") or cat.get("rows") or [])) if a.cat else 0
    out = reel_compose.build_reel_video(subject, fights, a.out, work_dir=a.work_dir,
                                        pacing=a.pacing, voices=voices,
                                        n_matchups=n_matchups)
    from overlay.compose import _duration
    print(f"WROTE {out}  ({_duration(out):.1f}s, {out.stat().st_size // 1024} KB, "
          f"{len(fights)} fights)")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()

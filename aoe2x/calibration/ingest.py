"""Ingest the locked FINAL standard-unit archive into the local workspace.

The archive supplies decoded fight streams and ``ROSTER.txt``. This module
resolves each unit to its civilization and slug, validates observed spawn HP
and derivable hit damage, stages streams under ``calibration/tapes``, and
writes project-local fixtures under ``calibration/fixtures``.

Recording IDs remain distinct, while ``matchup`` uses the roster authority's
side order so reverse-direction recordings group into one unordered matchup.
Content hashes make re-ingestion idempotent. No production simulator module
imports this calibration-only pipeline.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
import re
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

from aoe2x.calibration.paths import CalibrationPaths, workspace_paths
from aoe2x.paths import GOLDEN_DIR

logger = logging.getLogger(__name__)

REFERENCE_DB_PATH = GOLDEN_DIR / "aoe2_reference.db"

_HP_TOLERANCE = 1e-6
_ATTACK_TOLERANCE = 1e-6

# ref_units columns needed to validate a resolved (civ, slug): HP, the raw
# attack/armor class maps used by the attack cross-check, and every combat
# property that would make the simple additive attack/armor-class formula
# below wrong (percentage reductions, armor-ignoring, execution damage,
# etc.) — presence of any of these marks the attack cross-check "ambiguous".
_REF_UNIT_COLUMNS = [
    "final_hp",
    "final_attack",
    "final_attacks_json",
    "final_armors_json",
    "ignores_melee_armor",
    "ignores_pierce_armor",
    "bonus_damage_reduction",
    "miss_damage_percent",
    "armor_strip_per_hit",
    "charge_ignores_armor",
    "damage_reflect_percent",
    "execute_damage_per_step",
    "dodge_shield_max",
    "pass_through_percent",
    "splash_radius",
    "is_siege_projectile",
    "trample_percent",
    "trample_radius",
    "trample_flat_damage",
]

_COMPLICATING_ATTACK_FIELDS = (
    "ignores_melee_armor",
    "ignores_pierce_armor",
    "bonus_damage_reduction",
    "miss_damage_percent",
    "armor_strip_per_hit",
    "charge_ignores_armor",
    "damage_reflect_percent",
    "execute_damage_per_step",
    "dodge_shield_max",
    "pass_through_percent",
    # splash_radius: a genuine area-of-effect projectile blast (siege
    # units), where even the "closest" recorded hit is a distance-falloff
    # value the additive class formula can't approximate (observed on
    # Aztecs Siege Onager: formula predicts ~72-73, tape modal is 1 — most
    # recorded hits are blast-edge splash onto bystanders).
    "splash_radius",
    "is_siege_projectile",
    # trample_percent/trample_radius/trample_flat_damage: whether the tape's
    # modal hit damage lands on the primary-hit value or the trample-splash
    # value is a function of formation density, not something derivable
    # here — it depends on how packed the victims are when the trampler
    # swings. Elite Battle Elephant vs a spread-out Hand Cannoneer line
    # (spike fight) happened to have the primary hit as the mode; Elite
    # Battle Elephant vs a packed Heavy Camel Rider formation
    # (heavy_camel__vs__elite_elephant) had the SPLASH fraction as the mode
    # (observed modal=3.75 == 0.25 * final_attack=15, i.e. trample_percent).
    # Comparing that splash value against the primary-hit formula is
    # apples-to-oranges, so any non-zero trample field skips the check
    # entirely rather than risk trusting a coincidence that doesn't
    # generalize.
    "trample_percent",
    "trample_radius",
    "trample_flat_damage",
)


class IngestFailures(RuntimeError):
    """Raised by `ingest_zip` when one or more fights in a drop couldn't be
    (fully) ingested: either processing failures (civ resolution, HP/attack
    cross-validation, I/O) or run_id/content conflicts (see below). The
    manifest is still saved with everything that DID succeed — per-fight
    isolation means one bad recording in a batch never blocks the rest.
    Callers (and the `python -m aoe2x.calibration.ingest` CLI) must treat
    this as "partially done, needs attention" and never swallow it silently.
    """

    def __init__(
        self,
        message: str,
        successes: list[str],
        failures: list[tuple[str, str]],
        conflicts: list[tuple[str, str]] | None = None,
    ):
        super().__init__(message)
        self.successes = successes  # run_ids that succeeded (or were already-ingested no-ops)
        self.failures = failures  # (tag, error message) for fights that raised during processing
        self.conflicts = conflicts or []  # (run_id, message) for true tag collisions (composition also differs) —
        # a same-run_id/different-content/SAME-composition case is a reused-tag repeat, not a conflict: it gets
        # auto-assigned a new <matchup>_rN run_id and ingested normally instead of landing here.


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_matchups(matchups_path: Path) -> list[dict[str, Any]]:
    return json.loads(matchups_path.read_text(encoding="utf-8"))


def _load_roster_authority(extracted_root: Path) -> list[dict[str, Any]]:
    """Build the 91-pair civ/slug authority from FINAL's own ROSTER.txt."""
    roster_files = sorted(extracted_root.rglob("ROSTER.txt"))
    if len(roster_files) != 1:
        raise ValueError(
            f"expected exactly one ROSTER.txt, found {len(roster_files)}: "
            f"{[str(path) for path in roster_files]}"
        )
    units: list[dict[str, str]] = []
    pattern = re.compile(
        r"^\s{2}(.+?)\s{2,}([^/\s]+)/([^\s]+)\s{2,}(?:melee|ranged|siege)\s*$"
    )
    for line in roster_files[0].read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            label, civ, slug = match.groups()
            units.append({"label": label.strip(), "civ": civ, "slug": slug})
    if len(units) < 2:
        raise ValueError(f"ROSTER.txt contained only {len(units)} parseable units")
    if len({unit["label"] for unit in units}) != len(units):
        raise ValueError("ROSTER.txt contains duplicate unit labels")
    if len({unit["slug"] for unit in units}) != len(units):
        raise ValueError("ROSTER.txt contains duplicate unit slugs")
    return [
        {
            "civ1": first["civ"],
            "slug1": first["slug"],
            "label1": first["label"],
            "civ2": second["civ"],
            "slug2": second["slug"],
            "label2": second["label"],
        }
        for first, second in combinations(units, 2)
    ]


def _find_decoded_dir(extracted_root: Path) -> Path:
    """Return the sole decoded-tape directory in an extracted drop.

    Early drops stored it directly at ``decoded/``; consolidated drops use
    ``standard_units/decoded/``. Requiring metadata prevents an unrelated
    empty directory from being selected and turns an unsupported archive
    layout into a hard failure instead of a silent zero-fight ingest.
    """
    candidates = sorted(
        path
        for path in extracted_root.rglob("decoded")
        if path.is_dir() and any(path.glob("*.meta.json"))
    )
    if len(candidates) != 1:
        raise ValueError(
            f"ingest_zip: expected exactly one decoded directory containing "
            f"*.meta.json under {extracted_root}, found {len(candidates)}"
        )
    return candidates[0]


_RUN_SUFFIX_RE = re.compile(r"_r\d+$")


def _matchup_for_tag(tag: str) -> str:
    """The matchup identity a tag belongs to: the tag with any trailing
    `_r2`/`_r3`/`_rN` repeat-recording suffix stripped. A tag with no such
    suffix IS its own matchup (first/only recording so far)."""
    return _RUN_SUFFIX_RE.sub("", tag)


def _same_matchup_composition(existing_entry: dict[str, Any], new_composition: dict[str, dict[str, int]]) -> bool:
    """True if `new_composition` (a fresh meta.json's `composition`) names
    the same two units as `existing_entry`'s `side1`/`side2`, ignoring
    owner numbers and counts. Used to tell a genuine repeat recording
    (recorder reused a tag instead of adding its own `_rN` suffix) apart
    from an actual mix-up (same tag string, a completely different fight —
    which must never be auto-merged)."""
    existing_names = {existing_entry["side1"]["unit_name"], existing_entry["side2"]["unit_name"]}
    new_names = {name for side_units in new_composition.values() for name in side_units}
    return existing_names == new_names


def _find_by_content_in_matchup(
    matchup: str, content_hash: str, fights_by_run_id: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    """An existing entry anywhere in `matchup`'s family (base tag or any
    `_rN` repeat) whose content_hash already matches, if any.

    Needed because a reused-tag repeat gets stored under a REASSIGNED
    run_id (not the raw tag) — so a later redelivery of that exact content
    (e.g. the same drop ingested twice) must be recognized as a no-op by
    searching the whole matchup family, not just the literal `run_id ==
    tag` slot (which still holds the OLDER recording and would otherwise
    look like yet another new repeat every time, minting an unbounded
    string of identical `_rN` duplicates).
    """
    for f in fights_by_run_id.values():
        if f.get("matchup") == matchup and f.get("content_hash") == content_hash:
            return f
    return None


def _next_available_run_id(matchup: str, fights_by_run_id: dict[str, dict[str, Any]]) -> str:
    """The next free `<matchup>` / `<matchup>_rN` slot, given the entries
    already recorded for this matchup. Used when the recorder reuses an
    existing tag for a genuine new recording instead of suffixing it
    itself — see ingest_zip's reused-tag handling."""
    numbers = set()
    suffix_re = re.compile(rf"^{re.escape(matchup)}_r(\d+)$")
    for f in fights_by_run_id.values():
        if f.get("matchup") != matchup:
            continue
        if f["run_id"] == matchup:
            numbers.add(1)
        else:
            m = suffix_re.match(f["run_id"])
            if m:
                numbers.add(int(m.group(1)))
    next_n = max(numbers, default=0) + 1
    return matchup if next_n == 1 else f"{matchup}_r{next_n}"


def _fight_content_hash(decoded_dir: Path, tag: str) -> str:
    """A content fingerprint for one fight: sha256 over the raw bytes of its
    damage/units/missiles streams (length-prefixed per file so there's no
    boundary ambiguity). This is what idempotency keys on — NOT the zip's
    hash — because later drops re-deliver earlier fights byte-identically
    inside an archive with a different sha256 (the archive just grew).
    """
    h = hashlib.sha256()
    for suffix in ("damage.jsonl.gz", "units.jsonl.gz", "missiles.jsonl.gz"):
        data = (decoded_dir / f"{tag}.{suffix}").read_bytes()
        h.update(len(data).to_bytes(8, "big"))
        h.update(data)
    return h.hexdigest()


def _owner_from_composition_key(key: str) -> int:
    # meta.json composition keys are the in-game owner numbers, e.g. "side2"
    # means owner==2 — NOT a "first side / second side" label. The real
    # owner number is preserved verbatim in each side's "owner" field.
    if not key.startswith("side") or not key[len("side"):].isdigit():
        raise ValueError(f"ingest_zip: unexpected composition key (expected 'sideN'): {key!r}")
    return int(key[len("side"):])


def _read_jsonl_gz(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _observed_spawn_hp(units_rows: list[dict[str, Any]], owner: int) -> float:
    """Max hp seen for `owner`'s units at the earliest `t` in the tape."""
    owner_rows = [r for r in units_rows if r["owner"] == owner]
    if not owner_rows:
        raise ValueError(f"_observed_spawn_hp: no unit samples for owner={owner}")
    t_min = min(r["t"] for r in owner_rows)
    return max(r["hp"] for r in owner_rows if r["t"] == t_min)


def _modal_hit_damage(damage_rows: list[dict[str, Any]], attacker_owner: int) -> tuple[float | None, str | None]:
    """The tape's modal (most frequent) per-hit damage dealt by `attacker_owner`.

    Returns (value, None) if derivable, or (None, reason) if there are no
    damage samples for this owner at all. A low-share mode (e.g. a
    trampling elephant whose primary-target hits are a plurality, not a
    majority, of all recorded hits) is still returned — empirically this is
    the value that matches the attack/armor-class formula for the "clean"
    (non-splash) hit, which is what we want to cross-check against.
    """
    hits = [r["damage"] for r in damage_rows if r.get("attacker_owner") == attacker_owner]
    if not hits:
        return None, f"no damage events recorded for owner={attacker_owner}"
    value, _n = Counter(hits).most_common(1)[0]
    return value, None


def _class_amount_map(json_text: str | None) -> dict[str, float]:
    if not json_text:
        return {}
    return {str(k): float(v) for k, v in json.loads(json_text).items()}


def _expected_hit_damage(attacker_row: dict[str, Any], target_row: dict[str, Any]) -> float | None:
    """Best-effort single-hit damage estimate from raw attack/armor-class maps.

    Sums, over armor-class ids the attacker has an attack value for AND the
    target has an armor value for (i.e. classes the target is actually a
    member of), (attack - armor). Classes present on only one side don't
    contribute — this matches the Genie engine's combat model, where a
    bonus attack class only lands if the target belongs to that class.
    Returns None if the two sides share no class id at all (nothing to
    compare). Validated against all four known-good spike-fight units
    (Japanese Hand Cannoneer, Burmese Elite Battle Elephant, Chinese
    Arbalester, Cumans Elite Steppe Lancer): this formula reproduces the
    tape's modal hit damage exactly for all four, including the trampling
    Elephant.

    AoE2 has a hard floor of 1 damage per landed hit — when armor >= attack
    the game still deals 1, it never deals 0 or negative. Both engines this
    repo runs enforce that floor (`Math.max(1, baseDmg + bonusDamage +
    executeBonus)` in `apps/website/static/js/engine/battle_unit.js:334-337`;
    `max(1, base_dmg + bonus_damage + execute_bonus)` in
    `aoe2x/sim/simulation_real.py:730`), so the expected value returned here
    must be clamped the same way before comparison — DO NOT remove this
    clamp, it is not an approximation, it is the actual rule.
    """
    attacks = _class_amount_map(attacker_row.get("final_attacks_json"))
    armors = _class_amount_map(target_row.get("final_armors_json"))
    shared = set(attacks) & set(armors)
    if not shared:
        return None
    return max(1.0, sum(attacks[c] - armors[c] for c in shared))


def _has_complicating_attack_properties(row: dict[str, Any]) -> bool:
    return any((row.get(field) or 0) for field in _COMPLICATING_ATTACK_FIELDS)


def _fetch_ref_unit(civ: str, slug: str) -> dict[str, Any] | None:
    conn = sqlite3.connect(str(REFERENCE_DB_PATH))
    try:
        cur = conn.execute(
            f"SELECT {', '.join(_REF_UNIT_COLUMNS)} FROM ref_units "
            "WHERE civ_name = ? AND unit_slug = ? AND age = 'Imperial'",
            (civ, slug),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return dict(zip(_REF_UNIT_COLUMNS, row))


def _slugs_for_unit_name(unit_name: str) -> list[str]:
    """Distinct unit_slug values whose canonical (Imperial-age) ref_units
    unit_name matches `unit_name` exactly.

    Used only as a fallback inside `resolve_civ` when a tape's unit display
    name doesn't match any matchups-authority label verbatim (e.g. the live
    game shows "Heavy Camel Rider" / "Heavy Cavalry Archer" while the
    authority's abbreviated label is "Heavy Camel" / "Heavy Cav Archer").
    This is a deterministic DB cross-reference, not a fuzzy guess.
    """
    conn = sqlite3.connect(str(REFERENCE_DB_PATH))
    try:
        cur = conn.execute(
            "SELECT DISTINCT unit_slug FROM ref_units WHERE unit_name = ? AND age = 'Imperial'",
            (unit_name,),
        )
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def _load_manifest(paths: CalibrationPaths | None = None) -> dict[str, Any]:
    resolved = paths or workspace_paths()
    if resolved.manifest.exists():
        return json.loads(resolved.manifest.read_text(encoding="utf-8"))
    return {"fights": []}


def _save_manifest(
    manifest: dict[str, Any],
    paths: CalibrationPaths | None = None,
) -> None:
    resolved = paths or workspace_paths()
    resolved.manifest.parent.mkdir(parents=True, exist_ok=True)
    resolved.manifest.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def resolve_civ(unit_name: str, matchups: list[dict[str, Any]]) -> tuple[str, str]:
    """Resolve a tape's unit display name to (civ, slug) via the matchups authority.

    Each `matchups_91.json` entry carries {civ1, slug1, label1, civ2, slug2,
    label2} for both sides of a matchup; a unit's display name must map to
    exactly one (civ, slug) pair across the whole authority.

    Tries an exact match against `label1`/`label2` first. If that finds
    nothing, falls back to a `ref_units.unit_name` cross-reference (handles
    the live game showing a fuller name than the authority's abbreviated
    label, e.g. "Heavy Camel Rider" vs "Heavy Camel") — still deterministic,
    still hard-fails if ambiguous. Never guesses.
    """
    found: set[tuple[str, str]] = set()
    for entry in matchups:
        if entry.get("label1") == unit_name:
            found.add((entry["civ1"], entry["slug1"]))
        if entry.get("label2") == unit_name:
            found.add((entry["civ2"], entry["slug2"]))

    if not found:
        fallback_slugs = _slugs_for_unit_name(unit_name)
        for slug in fallback_slugs:
            for entry in matchups:
                if entry.get("slug1") == slug:
                    found.add((entry["civ1"], slug))
                if entry.get("slug2") == slug:
                    found.add((entry["civ2"], slug))
        if found:
            logger.warning(
                "resolve_civ: unit_name=%r not found verbatim in matchups authority labels; "
                "resolved via ref_units.unit_name fallback (slugs=%s) to %s",
                unit_name, fallback_slugs, sorted(found),
            )

    if not found:
        raise ValueError(
            f"resolve_civ: no (civ, slug) found for unit_name={unit_name!r} in matchups "
            f"authority (tried exact label match and ref_units.unit_name fallback)"
        )
    if len(found) > 1:
        raise ValueError(
            f"resolve_civ: ambiguous unit_name={unit_name!r} maps to multiple "
            f"(civ, slug) pairs: {sorted(found)}"
        )
    return next(iter(found))


def _canonical_matchup_for_composition(
    composition: dict[str, dict[str, int]],
    matchups: list[dict[str, Any]],
) -> str:
    """Return the authority-ordered identity for an unordered unit pair."""
    unit_names = [name for side in composition.values() for name in side]
    if len(unit_names) != 2:
        raise ValueError(
            "ingest_zip: expected exactly two unit types while resolving matchup "
            f"identity, got {unit_names!r}"
        )
    slugs = {resolve_civ(name, matchups)[1] for name in unit_names}
    candidates = [
        row for row in matchups if {row["slug1"], row["slug2"]} == slugs
    ]
    if len(candidates) != 1:
        raise ValueError(
            "ingest_zip: expected exactly one authority row for unordered slugs "
            f"{sorted(slugs)!r}, found {len(candidates)}"
        )
    row = candidates[0]
    return f"{row['slug1']}__vs__{row['slug2']}"


def validate_unit(
    civ: str,
    slug: str,
    observed_hp: float,
    *,
    opponent_civ: str | None = None,
    opponent_slug: str | None = None,
    modal_hit_damage: float | None = None,
) -> dict[str, Any]:
    """Cross-validate a resolved (civ, slug) against `ref_units`.

    HP check (always performed): hard-fails (raises ValueError, printing
    both values) if the row is missing or the DB's Imperial-age `final_hp`
    doesn't match the tape's observed spawn HP.

    Attack check (only performed when `opponent_civ`/`opponent_slug`/
    `modal_hit_damage` are all supplied): strengthens the HP check, which
    alone cannot distinguish civs that happen to share identical HP (e.g.
    Bengalis and Burmese both have final_hp=320 for elite_elephant).
    Compares a raw attack/armor-class-map sum against the tape's modal
    observed hit damage. Hard-fails on a clear mismatch; but if the check
    is ambiguous (opponent row missing, either side has combat modifiers
    the simple formula can't model, or no shared attack/armor class ids)
    it is logged and skipped, not failed — the HP check alone stands, with
    a weaker guarantee, exactly as before this check existed.
    """
    row = _fetch_ref_unit(civ, slug)
    if row is None:
        raise ValueError(
            f"validate_unit: no ref_units row for civ_name={civ!r} unit_slug={slug!r} "
            f"age='Imperial' (observed tape hp={observed_hp!r})"
        )

    final_hp = row["final_hp"]
    if final_hp is None or abs(final_hp - observed_hp) > _HP_TOLERANCE:
        raise ValueError(
            f"validate_unit: HP mismatch for civ_name={civ!r} unit_slug={slug!r}: "
            f"ref_units.final_hp={final_hp!r} vs tape observed_hp={observed_hp!r}"
        )

    result: dict[str, Any] = {"hp_ok": True, "attack_check": None}

    if opponent_civ is None or opponent_slug is None or modal_hit_damage is None:
        result["attack_check"] = "skipped: no opponent/modal-damage supplied (weaker guarantee: HP-only)"
        logger.info("validate_unit: civ_name=%r unit_slug=%r — %s", civ, slug, result["attack_check"])
        return result

    opponent_row = _fetch_ref_unit(opponent_civ, opponent_slug)
    if opponent_row is None:
        result["attack_check"] = (
            f"skipped: no ref_units row for opponent civ_name={opponent_civ!r} "
            f"unit_slug={opponent_slug!r} (weaker guarantee: HP-only)"
        )
        logger.warning("validate_unit: civ_name=%r unit_slug=%r — %s", civ, slug, result["attack_check"])
        return result

    if _has_complicating_attack_properties(row) or _has_complicating_attack_properties(opponent_row):
        result["attack_check"] = (
            "skipped: attacker/opponent has combat modifiers the additive attack/armor-class "
            "formula can't model (weaker guarantee: HP-only)"
        )
        logger.info("validate_unit: civ_name=%r unit_slug=%r — %s", civ, slug, result["attack_check"])
        return result

    expected = _expected_hit_damage(row, opponent_row)
    if expected is None:
        result["attack_check"] = "skipped: no shared attack/armor class ids (weaker guarantee: HP-only)"
        logger.info("validate_unit: civ_name=%r unit_slug=%r — %s", civ, slug, result["attack_check"])
        return result

    if abs(expected - modal_hit_damage) > _ATTACK_TOLERANCE:
        raise ValueError(
            f"validate_unit: ATTACK mismatch for civ_name={civ!r} unit_slug={slug!r} vs "
            f"opponent civ_name={opponent_civ!r} unit_slug={opponent_slug!r}: expected per-hit "
            f"damage={expected!r} (sum over shared attack/armor classes) vs tape "
            f"modal_hit_damage={modal_hit_damage!r}"
        )

    result["attack_check"] = f"passed: expected={expected!r} == tape modal_hit_damage={modal_hit_damage!r}"
    logger.info("validate_unit: civ_name=%r unit_slug=%r — %s", civ, slug, result["attack_check"])
    return result


def _process_fight(
    tag: str,
    decoded_dir: Path,
    matchups: list[dict[str, Any]],
    content_hash: str,
    zip_sha256: str,
    zip_path: Path,
    paths: CalibrationPaths,
    matchup: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Resolve, cross-validate, and stage tape files for a single fight.

    `run_id` defaults to the tag itself — the recorder normally gives each
    recording, including repeats, a unique tag (`_r2`/`_r3`/... suffix
    included). It is passed explicitly (and differs from `tag`) only when
    the recorder reused an existing tag for a genuine new recording and
    `ingest_zip` had to assign a fresh `<matchup>_rN` slot itself (see the
    "reused tag" handling there). ``matchup`` is the roster-authority
    identity for the unordered pair, so reverse-direction recordings group
    together. This function raises on any failure; it only touches the
    filesystem (tape copy) after both sides have fully validated, so a
    failing fight never leaves a half-copied tape directory behind (and
    never leaves a manifest entry).
    """
    run_id = run_id if run_id is not None else tag
    meta = json.loads((decoded_dir / f"{tag}.meta.json").read_text(encoding="utf-8"))
    units_rows = _read_jsonl_gz(decoded_dir / f"{tag}.units.jsonl.gz")
    damage_path = decoded_dir / f"{tag}.damage.jsonl.gz"
    damage_rows = _read_jsonl_gz(damage_path) if damage_path.exists() else []

    composition = meta["composition"]
    side_keys = sorted(composition.keys(), key=_owner_from_composition_key)
    if len(side_keys) != 2:
        raise ValueError(
            f"ingest_zip: expected exactly 2 sides in composition for tag={tag!r}, "
            f"got {list(composition)}"
        )

    resolved = []
    for side_key in side_keys:
        owner = _owner_from_composition_key(side_key)
        unit_counts = composition[side_key]
        if len(unit_counts) != 1:
            raise ValueError(
                f"ingest_zip: expected exactly 1 unit type per side for tag={tag!r} "
                f"side={side_key!r}, got {unit_counts}"
            )
        unit_name, count = next(iter(unit_counts.items()))
        civ, slug = resolve_civ(unit_name, matchups)
        observed_hp = _observed_spawn_hp(units_rows, owner)
        resolved.append(
            {"owner": owner, "unit_name": unit_name, "civ": civ, "slug": slug, "count": count, "observed_hp": observed_hp}
        )

    for i, side in enumerate(resolved):
        opponent = resolved[1 - i]
        modal_damage, note = _modal_hit_damage(damage_rows, attacker_owner=side["owner"])
        if modal_damage is None:
            logger.info(
                "tag=%s run_id=%s civ=%s slug=%s: attack cross-check not derivable (%s)",
                tag, run_id, side["civ"], side["slug"], note,
            )
        validate_unit(
            side["civ"],
            side["slug"],
            observed_hp=side["observed_hp"],
            opponent_civ=opponent["civ"],
            opponent_slug=opponent["slug"],
            modal_hit_damage=modal_damage,
        )

    # All validations passed for both sides — now (and only now) stage tape
    # files, so a failed fight never leaves an orphaned/partial tape dir.
    run_dir = paths.tapes_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        for src in decoded_dir.glob(f"{tag}.*"):
            # Rename-on-copy when the run_id was REASSIGNED away from the raw
            # recorded tag (the reused-tag repeat path above). The decoded
            # files are named "<tag>.<stream>", but every downstream reader
            # (extract.build_truth_card, tests/test_calibration_extract.py)
            # addresses them as "<run_id>.<stream>". Copying them under the
            # raw tag name into a `<run_id>/` dir left the streams
            # unreachable, and extract silently emitted an all-zero card
            # instead of failing -- exactly what happened to
            # hand_cannoneer__vs__elite_elephant_r2.
            dest_name = f"{run_id}{src.name[len(tag):]}"
            shutil.copy2(src, run_dir / dest_name)
    except Exception:
        shutil.rmtree(run_dir, ignore_errors=True)
        raise

    return {
        "tag": run_id,  # kept identical to run_id (see module docstring); NOT necessarily the raw recorded tag
        "run_id": run_id,
        "matchup": matchup,
        "content_hash": content_hash,
        "zip_sha256": zip_sha256.upper(),
        "source_archive": zip_path.name,
        "side1": {k: v for k, v in resolved[0].items() if k != "observed_hp"},
        "side2": {k: v for k, v in resolved[1].items() if k != "observed_hp"},
        "duration_s": meta["duration_s"],
        "stream_hz": meta["stream_hz"],
        "ingested_utc": datetime.now(timezone.utc).isoformat(),
    }


def ingest_zip(
    zip_path: str | Path,
    *,
    paths: CalibrationPaths | None = None,
) -> list[str]:
    """Unpack a recorded-fight drop zip and register it in the calibration manifest.

    Extracts the zip to a temp dir, resolves + cross-validates both sides of
    each fight, copies each fight's decoded tape files to
    ``calibration/tapes/<run_id>/`` and writes the derived roster authority
    and manifest under ``calibration/fixtures``. Adds one manifest entry per
    successfully validated fight, keyed by `run_id` (the tag exactly as
    recorded — the recorder already suffixes repeat recordings `_r2`,
    `_r3`, ...). Each entry also carries the roster-authority ``matchup``
    identity so callers can group every direction and repeat of one pair.

    Idempotency keys on each fight's own CONTENT hash (over its raw
    damage/units/missiles bytes), not the zip's hash: later drops are
    cumulative snapshots that re-deliver earlier fights byte-identically
    inside a new archive, and that redelivery must be a silent no-op. If a
    `run_id` already in the manifest shows up again with DIFFERENT content,
    that's either (a) the recorder reusing a tag for a genuine new
    recording — detected by the two sides' unit names still matching the
    existing entry — in which case the new recording is assigned the next
    free `<matchup>_rN` slot and ingested normally (never discarded, never
    overwriting the earlier one), or (b) the composition ALSO differs, a
    real tag collision between two unrelated fights, which is reported
    loudly afterward via `IngestFailures.conflicts` and never guessed at.

    Each fight is processed independently (per-fight isolation): one fight
    failing to resolve/validate does not block the others in the same
    drop. The manifest is saved with everything that succeeded; if any
    fight failed or conflicted, `IngestFailures` is raised afterward (never
    silent) with `.successes` (run_ids), `.failures` (`(tag, message)`
    pairs), and `.conflicts` (`(run_id, message)` pairs).

    Returns the list of run_ids ingested (newly processed, or already
    present with matching content — a cumulative-redelivery no-op).
    """
    zip_path = Path(zip_path)
    resolved_paths = paths or workspace_paths()
    zip_sha256 = _sha256_file(zip_path).upper()

    manifest = _load_manifest(resolved_paths)
    fights_by_run_id: dict[str, dict[str, Any]] = {f["run_id"]: f for f in manifest["fights"]}

    run_ids: list[str] = []
    failures: list[tuple[str, str]] = []
    conflicts: list[tuple[str, str]] = []
    tags: list[str] = []

    with zipfile.ZipFile(zip_path) as zf, tempfile.TemporaryDirectory(prefix="aoe2_calib_") as tmp:
        tmp_path = Path(tmp)
        zf.extractall(tmp_path)

        decoded_dir = _find_decoded_dir(tmp_path)
        meta_files = sorted(decoded_dir.glob("*.meta.json"))
        tags = [p.name[: -len(".meta.json")] for p in meta_files]

        # FINAL carries ROSTER.txt. Supporting an embedded matchups_91.json
        # keeps this parser usable for a structurally equivalent archive,
        # without falling back to any previously generated fixture.
        matchup_files = sorted(tmp_path.rglob("matchups_91.json"))
        if len(matchup_files) == 1:
            matchups_src = matchup_files[0]
            matchups = _load_matchups(matchups_src)
        elif not matchup_files:
            matchups_src = None
            matchups = _load_roster_authority(tmp_path)
            resolved_paths.fixtures_dir.mkdir(parents=True, exist_ok=True)
            resolved_paths.matchups.write_text(
                json.dumps(matchups, indent=2) + "\n",
                encoding="utf-8",
            )
        else:
            raise ValueError(
                f"ingest_zip: found multiple matchups_91.json files: {matchup_files}"
            )

        for tag in tags:
            run_id = tag  # the recorder's tag is normally the unique recording identity
            content_hash = _fight_content_hash(decoded_dir, tag)
            existing = fights_by_run_id.get(run_id)
            new_meta = json.loads((decoded_dir / f"{tag}.meta.json").read_text(encoding="utf-8"))
            matchup = _canonical_matchup_for_composition(new_meta["composition"], matchups)

            if existing is not None and existing.get("content_hash") == content_hash:
                # Cumulative redelivery of an already-ingested fight — no-op.
                run_ids.append(run_id)
                continue

            already_ingested = _find_by_content_in_matchup(matchup, content_hash, fights_by_run_id)
            if already_ingested is not None:
                # This exact content is already in the manifest under a
                # REASSIGNED run_id from an earlier reused-tag repeat (the
                # literal run_id==tag slot holds a different, older
                # recording) — redelivery of it must still be a no-op.
                run_ids.append(already_ingested["run_id"])
                continue

            if existing is not None:
                # Same run_id, different content. Two possibilities: (a) the
                # recorder re-ran this matchup but reused the tag instead of
                # suffixing its own repeat (composition — the two unit names
                # — still matches: a genuine variance sample we must keep,
                # not discard), or (b) an actual conflict (same tag string,
                # different fight entirely) that must never be auto-merged.
                if _same_matchup_composition(existing, new_meta["composition"]):
                    reassigned_run_id = _next_available_run_id(matchup, fights_by_run_id)
                    logger.warning(
                        "ingest_zip: run_id=%r reused for a new recording of the same matchup "
                        "(composition matches, content_hash differs) — recorder didn't suffix "
                        "its own repeat; assigning run_id=%r instead of overwriting the existing "
                        "entry or discarding this one",
                        run_id, reassigned_run_id,
                    )
                    try:
                        entry = _process_fight(
                            tag, decoded_dir, matchups, content_hash, zip_sha256, zip_path,
                            resolved_paths, matchup,
                            run_id=reassigned_run_id,
                        )
                    except Exception as exc:  # noqa: BLE001 - isolate one bad fight
                        logger.error("ingest_zip: fight tag=%r run_id=%r FAILED: %s", tag, reassigned_run_id, exc)
                        failures.append((tag, str(exc)))
                        continue
                    fights_by_run_id[reassigned_run_id] = entry
                    run_ids.append(reassigned_run_id)
                else:
                    msg = (
                        f"run_id={run_id!r} already in manifest with content_hash="
                        f"{existing.get('content_hash')!r}, and this drop's content_hash="
                        f"{content_hash!r} differs too — but the composition ALSO differs "
                        f"(existing: {existing['side1']['unit_name']!r}/{existing['side2']['unit_name']!r}, "
                        f"new: {sorted({n for su in new_meta['composition'].values() for n in su})}) — "
                        f"this looks like a genuine tag collision between two different fights, "
                        f"not a repeat recording; refusing to guess, not ingesting"
                    )
                    logger.error("ingest_zip: CONFLICT %s", msg)
                    conflicts.append((run_id, msg))
                continue

            try:
                entry = _process_fight(
                    tag,
                    decoded_dir,
                    matchups,
                    content_hash,
                    zip_sha256,
                    zip_path,
                    resolved_paths,
                    matchup,
                )
            except Exception as exc:  # noqa: BLE001 - deliberately broad: isolate one bad fight
                logger.error("ingest_zip: fight tag=%r run_id=%r FAILED: %s", tag, run_id, exc)
                failures.append((tag, str(exc)))
                continue

            fights_by_run_id[run_id] = entry
            run_ids.append(run_id)

        # Archive the raw drop and the civ authority alongside the manifest
        # regardless of per-fight failures — the fights that DID succeed are
        # still worth keeping, and the drop itself is unmodified evidence.
        if matchups_src is not None:
            resolved_paths.fixtures_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(matchups_src, resolved_paths.matchups)

    manifest["fights"] = list(fights_by_run_id.values())
    _save_manifest(manifest, resolved_paths)

    if failures or conflicts:
        parts = []
        if failures:
            parts.append(f"{len(failures)} failed: " + "; ".join(f"{t}: {m}" for t, m in failures))
        if conflicts:
            parts.append(f"{len(conflicts)} conflicted: " + "; ".join(f"{r}: {m}" for r, m in conflicts))
        raise IngestFailures(
            f"{len(tags)} fight(s) in {zip_path.name}: {len(run_ids)} OK, " + "; ".join(parts),
            successes=run_ids,
            failures=failures,
            conflicts=conflicts,
        )
    return run_ids


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if len(sys.argv) != 2:
        print("usage: python -m aoe2x.calibration.ingest <drop.zip>")
        sys.exit(2)
    try:
        ids = ingest_zip(sys.argv[1])
        print(f"Ingested {len(ids)} fight(s): {ids}")
    except IngestFailures as exc:
        print(f"Ingested {len(exc.successes)} fight(s) OK: {exc.successes}")
        if exc.failures:
            print(f"FAILED {len(exc.failures)} fight(s):")
            for tag, msg in exc.failures:
                print(f"  - {tag}: {msg}")
        if exc.conflicts:
            print(f"CONFLICTED {len(exc.conflicts)} fight(s) (existing entry NOT overwritten):")
            for run_id, msg in exc.conflicts:
                print(f"  - {run_id}: {msg}")
        sys.exit(1)

"""Ingest recorded-fight "drop" zips into the calibration manifest.

A drop contains one or more decoded fight tapes (10 Hz unit positions, damage
events, ~60 Hz missile positions, in-game commands) plus a `matchups_91.json`
civ authority. This module unpacks a drop, resolves which civilization each
side actually was (tapes only carry unit *names*, not civs), cross-validates
that resolution against the tape's observed spawn HP (and, when derivable,
the tape's observed hit damage), and records everything in
`data/calibration/manifest.json` so downstream calibration stages
(truth-card extraction, engine replay, scoring) never have to re-derive it.

Large decoded tapes and raw drop archives live OUTSIDE the repo under
``D:/AI/aoe2_golden/`` — only the manifest and the `matchups.json` civ
authority are committed.

Two things about how drops actually arrive, learned from real batches:

1. **Drops are cumulative snapshots, not deltas.** A later batch zip
   re-delivers every fight from earlier batches byte-identically (same
   `damage`/`units`/`missiles` streams), packaged under a new `zip_sha256`
   just because the archive grew. Idempotency therefore keys on each
   fight's own *content* (a hash over its raw `damage`/`units`/`missiles`
   bytes), never on the zip's hash — otherwise every cumulative drop would
   re-ingest every earlier fight as "new".
2. **The recorder already gives repeat recordings distinct identities.**
   When the operator re-runs a matchup because a result looked odd, the
   repeat gets an explicit `_r2`/`_r3`/`_rN` tag suffix (e.g.
   `champion__vs__arbalester` and `champion__vs__arbalester_r3` are two
   separate recordings of the same matchup). So the tag itself — suffix
   included — IS the unique recording identity; no synthetic numbering is
   needed. Each fight's manifest entry stores both `run_id` (the tag
   exactly as recorded) and `matchup` (the tag with any trailing `_rN`
   stripped), so downstream scoring can group repeat runs of one matchup —
   that grouping is the only measurement of the real game's own
   run-to-run variance, so repeats are always additive, never merged or
   overwritten. If the same `run_id` ever shows up with DIFFERENT content
   (a recorder bug, not the cumulative-redelivery case), ingestion refuses
   to overwrite the existing entry and reports the conflict loudly instead.

Do not import this module's callers into ``aoe2x/sim/simulation_real.py`` or
``aoe2x/dbgen/config_combat.py`` territory: those files are byte-hashed into
the matchup-row cache key and this pipeline must never touch them.
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
from pathlib import Path
from typing import Any

from aoe2x.paths import GOLDEN_DIR, REPO_ROOT

logger = logging.getLogger(__name__)

# Large decoded tapes + raw drop archives live outside the repo (never committed).
EXTERNAL_ROOT = Path("D:/AI/aoe2_golden")
TAPES_DIR = EXTERNAL_ROOT / "tapes"
DROPS_DIR = EXTERNAL_ROOT / "drops"

# Committed calibration artifacts.
CALIBRATION_DIR = REPO_ROOT / "data" / "calibration"
MANIFEST_PATH = CALIBRATION_DIR / "manifest.json"
MATCHUPS_PATH = CALIBRATION_DIR / "matchups.json"

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
    # NOTE: splash_on_hit_radius/trample_percent are deliberately NOT here —
    # both were empirically verified (Burmese Elite Battle Elephant) to
    # leave the PRIMARY target's hit damage matching the simple formula; the
    # tape's modal damage naturally picks out that primary-hit value.
    # splash_radius is different: it's a genuine area-of-effect projectile
    # blast (siege units), where even the "closest" recorded hit is a
    # distance-falloff value the additive class formula can't approximate
    # (observed on Aztecs Siege Onager: formula predicts ~72-73, tape modal
    # is 1 — most recorded hits are blast-edge splash onto bystanders).
    "splash_radius",
    "is_siege_projectile",
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
        self.conflicts = conflicts or []  # (run_id, message) for same-run_id/different-content clashes


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


_RUN_SUFFIX_RE = re.compile(r"_r\d+$")


def _matchup_for_tag(tag: str) -> str:
    """The matchup identity a tag belongs to: the tag with any trailing
    `_r2`/`_r3`/`_rN` repeat-recording suffix stripped. A tag with no such
    suffix IS its own matchup (first/only recording so far)."""
    return _RUN_SUFFIX_RE.sub("", tag)


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
    """
    attacks = _class_amount_map(attacker_row.get("final_attacks_json"))
    armors = _class_amount_map(target_row.get("final_armors_json"))
    shared = set(attacks) & set(armors)
    if not shared:
        return None
    return sum(attacks[c] - armors[c] for c in shared)


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


def _load_manifest() -> dict[str, Any]:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {"fights": []}


def _save_manifest(manifest: dict[str, Any]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


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
) -> dict[str, Any]:
    """Resolve, cross-validate, and stage tape files for a single fight.

    `run_id` is the tag itself (the recorder already gives each recording,
    including repeats, a unique tag — `_r2`/`_r3`/... suffix included). This
    function raises on any failure; it only touches the filesystem (tape
    copy) after both sides have fully validated, so a failing fight never
    leaves a half-copied tape directory behind (and never leaves a manifest
    entry).
    """
    run_id = tag
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
    run_dir = TAPES_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        for src in decoded_dir.glob(f"{tag}.*"):
            shutil.copy2(src, run_dir / src.name)
    except Exception:
        shutil.rmtree(run_dir, ignore_errors=True)
        raise

    return {
        "tag": tag,
        "run_id": run_id,
        "matchup": _matchup_for_tag(tag),
        "content_hash": content_hash,
        "zip_sha256": zip_sha256,
        "drop": str(DROPS_DIR / zip_path.name),
        "side1": {k: v for k, v in resolved[0].items() if k != "observed_hp"},
        "side2": {k: v for k, v in resolved[1].items() if k != "observed_hp"},
        "duration_s": meta["duration_s"],
        "stream_hz": meta["stream_hz"],
        "ingested_utc": datetime.now(timezone.utc).isoformat(),
    }


def ingest_zip(zip_path: str) -> list[str]:
    """Unpack a recorded-fight drop zip and register it in the calibration manifest.

    Extracts the zip to a temp dir, resolves + cross-validates both sides of
    each fight, copies each fight's decoded tape files to
    ``D:/AI/aoe2_golden/tapes/<run_id>/``, archives the raw zip under
    ``D:/AI/aoe2_golden/drops/``, and copies the drop's `matchups_91.json`
    civ authority into the repo as `data/calibration/matchups.json`. Appends
    one manifest entry per successfully-validated fight to
    `data/calibration/manifest.json`, keyed by `run_id` (the tag exactly as
    recorded — the recorder already suffixes repeat recordings `_r2`,
    `_r3`, ...). Each entry also carries `matchup` (the tag with any
    trailing `_rN` stripped), so callers can group repeat runs of one
    matchup — see the module docstring for why that grouping matters.

    Idempotency keys on each fight's own CONTENT hash (over its raw
    damage/units/missiles bytes), not the zip's hash: later drops are
    cumulative snapshots that re-deliver earlier fights byte-identically
    inside a new archive, and that redelivery must be a silent no-op. If a
    `run_id` already in the manifest shows up again with DIFFERENT content
    (a genuine recorder conflict, not cumulative redelivery), the existing
    entry is left untouched and the conflict is reported loudly afterward
    via `IngestFailures.conflicts` — never silently discarded or overwritten.

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
    zip_sha256 = _sha256_file(zip_path)

    manifest = _load_manifest()
    fights_by_run_id: dict[str, dict[str, Any]] = {f["run_id"]: f for f in manifest["fights"]}

    run_ids: list[str] = []
    failures: list[tuple[str, str]] = []
    conflicts: list[tuple[str, str]] = []
    tags: list[str] = []

    with zipfile.ZipFile(zip_path) as zf, tempfile.TemporaryDirectory(prefix="aoe2_calib_") as tmp:
        tmp_path = Path(tmp)
        zf.extractall(tmp_path)

        decoded_dir = tmp_path / "decoded"
        meta_files = sorted(decoded_dir.glob("*.meta.json"))
        tags = [p.name[: -len(".meta.json")] for p in meta_files]

        # Only the first ("spike") drop actually carries matchups_91.json —
        # it's a static civ authority, not something that changes per batch.
        # Later cumulative drops fall back to the already-committed copy.
        matchups_src = tmp_path / "matchups_91.json"
        if matchups_src.exists():
            matchups = _load_matchups(matchups_src)
        elif MATCHUPS_PATH.exists():
            matchups = _load_matchups(MATCHUPS_PATH)
            matchups_src = None  # nothing fresh in this drop to copy back
        else:
            raise ValueError(
                f"ingest_zip: {zip_path.name} has no matchups_91.json and no prior "
                f"{MATCHUPS_PATH} exists to fall back to — cannot resolve civs for any fight in this drop"
            )

        for tag in tags:
            run_id = tag  # the recorder's tag IS the unique recording identity
            content_hash = _fight_content_hash(decoded_dir, tag)
            existing = fights_by_run_id.get(run_id)

            if existing is not None:
                if existing.get("content_hash") == content_hash:
                    # Cumulative redelivery of an already-ingested fight — no-op.
                    run_ids.append(run_id)
                else:
                    msg = (
                        f"run_id={run_id!r} already in manifest with content_hash="
                        f"{existing.get('content_hash')!r}, but this drop's content_hash="
                        f"{content_hash!r} differs — refusing to overwrite (never seen this "
                        f"recorder produce a genuine same-run_id content change)"
                    )
                    logger.error("ingest_zip: CONFLICT %s", msg)
                    conflicts.append((run_id, msg))
                continue

            try:
                entry = _process_fight(tag, decoded_dir, matchups, content_hash, zip_sha256, zip_path)
            except Exception as exc:  # noqa: BLE001 - deliberately broad: isolate one bad fight
                logger.error("ingest_zip: fight tag=%r run_id=%r FAILED: %s", tag, run_id, exc)
                failures.append((tag, str(exc)))
                continue

            fights_by_run_id[run_id] = entry
            run_ids.append(run_id)

        # Archive the raw drop and the civ authority alongside the manifest
        # regardless of per-fight failures — the fights that DID succeed are
        # still worth keeping, and the drop itself is unmodified evidence.
        DROPS_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(zip_path, DROPS_DIR / zip_path.name)

        if matchups_src is not None:
            CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(matchups_src, MATCHUPS_PATH)

    manifest["fights"] = list(fights_by_run_id.values())
    _save_manifest(manifest)

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

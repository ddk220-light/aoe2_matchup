import json
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ZIP = Path("C:/Users/ddk22/Downloads/aoe2_golden_spike_2026-07-29.zip")
BATCH_017_ZIP = Path("C:/Users/ddk22/Downloads/aoe2_golden_batch91_partial_017.zip")
BATCH_033_ZIP = Path("C:/Users/ddk22/Downloads/aoe2_golden_batch91_partial_033.zip")
MANIFEST = REPO / "data" / "calibration" / "manifest.json"


def test_ingest_spike_zip():
    from aoe2x.calibration.ingest import ingest_zip

    tags = ingest_zip(str(ZIP))
    assert set(tags) == {"hand_cannoneer__vs__elite_elephant", "elite_steppe__vs__arbalester"}
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    fights = {f["tag"]: f for f in m["fights"]}
    hc = fights["hand_cannoneer__vs__elite_elephant"]
    sides = {s["unit_name"]: s for s in (hc["side1"], hc["side2"])}
    assert sides["Hand Cannoneer"]["civ"] == "Japanese"
    assert sides["Hand Cannoneer"]["count"] == 21
    assert sides["Elite Battle Elephant"]["civ"] == "Burmese"
    assert sides["Elite Battle Elephant"]["count"] == 12
    assert abs(hc["duration_s"] - 152.31) < 0.01
    # tag == run_id == matchup for a fight with no repeat-recording suffix.
    assert hc["run_id"] == "hand_cannoneer__vs__elite_elephant"
    assert hc["matchup"] == "hand_cannoneer__vs__elite_elephant"


def test_ingest_is_idempotent():
    from aoe2x.calibration.ingest import ingest_zip

    before = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ingest_zip(str(ZIP))
    after = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert len(before["fights"]) == len(after["fights"])


def test_hp_cross_validation_rejects_wrong_civ():
    from aoe2x.calibration.ingest import validate_unit

    validate_unit("Burmese", "elite_elephant", observed_hp=320.0)  # must not raise
    try:
        validate_unit("Bengalis", "elite_elephant", observed_hp=999.0)
        assert False, "expected a hard failure on HP mismatch"
    except Exception:
        pass


def test_attack_floor_clamps_to_minimum_one_damage():
    """AoE2 always deals >=1 damage per hit, even when armor >= attack (both
    engines this repo runs enforce this: battle_unit.js:334-337's
    `Math.max(1, ...)`, simulation_real.py:730's `max(1, ...)`). Without a
    matching floor, `_expected_hit_damage` predicts <=0 for two REAL fights
    from aoe2_golden_batch91_partial_053.zip and validate_unit hard-fails
    even though the tape's modal_hit_damage of 1.0 is exactly the real
    game's damage floor firing — the data was right, the validator was
    wrong. Constructed so it fails without the `max(1.0, ...)` clamp.
    """
    from aoe2x.calibration.ingest import _expected_hit_damage, validate_unit

    # Chinese Elite Skirmisher's class-3 (Pierce) attack is 7; Burmese Elite
    # Battle Elephant's class-3 armor is 9 -> raw sum 7-9=-2.
    skirm_attacks = {"final_attacks_json": '{"27": 4, "15": 4, "3": 7, "28": 2, "35": 2, "21": 0, "17": 0}'}
    elephant_armors = {"final_armors_json": '{"5": 0, "4": 6, "8": 0, "3": 9, "31": 0}'}
    assert _expected_hit_damage(skirm_attacks, elephant_armors) == 1.0

    # Same skirmisher vs Spanish Paladin's class-3 armor of 7 -> raw sum 7-7=0.
    paladin_armors = {"final_armors_json": '{"4": 5, "8": 0, "3": 7, "31": 0}'}
    assert _expected_hit_damage(skirm_attacks, paladin_armors) == 1.0

    # End-to-end: both real fights must VALIDATE against modal_hit_damage=1.0.
    validate_unit(
        "Chinese", "imp_elite_skirm", observed_hp=35.0,
        opponent_civ="Burmese", opponent_slug="elite_elephant",
        modal_hit_damage=1.0,
    )
    validate_unit(
        "Chinese", "imp_elite_skirm", observed_hp=35.0,
        opponent_civ="Spanish", opponent_slug="paladin",
        modal_hit_damage=1.0,
    )


def test_trample_skips_attack_check_instead_of_hard_failing():
    """Elite Battle Elephant tramples (trample_percent=0.25): when it swings
    into a packed formation, most recorded hits are splash hits on
    secondary victims, not the primary target, so the tape's modal hit
    damage is the SPLASH fraction, not the primary-hit value the additive
    attack/armor-class formula predicts. Real case (from
    aoe2_golden_batch91_partial_103.zip): heavy_camel__vs__elite_elephant,
    Burmese Elite Battle Elephant vs Persians Heavy Camel Rider — the
    formula predicts 15.0 (18 attack - 3 armor for shared class "4", plus 0
    for shared class "31"/"39"), the tape's modal was 3.75 == 0.25 * 15.0
    (exactly the trample fraction). A trampling attacker must skip the
    attack check (HP-only, logged) rather than hard-fail on this
    apples-to-oranges comparison — constructed so it fails without the
    trample fields in _COMPLICATING_ATTACK_FIELDS.
    """
    from aoe2x.calibration.ingest import validate_unit

    validate_unit(
        "Burmese", "elite_elephant", observed_hp=320.0,
        opponent_civ="Persians", opponent_slug="heavy_camel",
        modal_hit_damage=3.75,  # must NOT raise despite the huge mismatch vs the naive formula
    )


def _isolate_calibration_storage(monkeypatch, tmp_path):
    """Redirect ingest.py's manifest/tape/drop storage under tmp_path so a
    test can exercise ingest_zip repeatedly without touching the real
    committed data/calibration/manifest.json or D:/AI/aoe2_golden. The
    reference DB (data/golden/aoe2_reference.db) is intentionally left
    pointing at the real repo copy — these tests validate real civ/HP data.

    Seeds the isolated matchups.json from the real committed copy: only the
    initial spike drop carries its own matchups_91.json (it's a static civ
    authority, not per-batch data), so any test that ingests a batch zip
    directly needs the authority already present, exactly as it would be
    after a real spike-zip ingest.
    """
    import aoe2x.calibration.ingest as ingest_mod

    calibration_dir = tmp_path / "calibration"
    monkeypatch.setattr(ingest_mod, "CALIBRATION_DIR", calibration_dir)
    monkeypatch.setattr(ingest_mod, "MANIFEST_PATH", calibration_dir / "manifest.json")
    monkeypatch.setattr(ingest_mod, "MATCHUPS_PATH", calibration_dir / "matchups.json")
    monkeypatch.setattr(ingest_mod, "TAPES_DIR", tmp_path / "golden" / "tapes")
    monkeypatch.setattr(ingest_mod, "DROPS_DIR", tmp_path / "golden" / "drops")

    calibration_dir.mkdir(parents=True, exist_ok=True)
    real_matchups = REPO / "data" / "calibration" / "matchups.json"
    (calibration_dir / "matchups.json").write_text(real_matchups.read_text(encoding="utf-8"), encoding="utf-8")
    return ingest_mod


def test_cumulative_batch_redelivery_dedups_by_content(tmp_path, monkeypatch):
    """Real batches are cumulative snapshots: aoe2_golden_batch91_partial_033.zip
    re-delivers all 17 fights from partial_017.zip byte-identically, just
    packaged under a new zip_sha256 because the archive grew. Ingesting both
    in order must land 33 manifest entries total, NOT 17 + 33 = 50 — the 17
    repeats must be deduped by content, not treated as new."""
    ingest_mod = _isolate_calibration_storage(monkeypatch, tmp_path)

    ids_017 = ingest_mod.ingest_zip(str(BATCH_017_ZIP))
    assert len(ids_017) == 17

    ids_033 = ingest_mod.ingest_zip(str(BATCH_033_ZIP))
    assert len(ids_033) == 33  # every tag in this drop, 17 of them content-identical no-ops

    manifest = json.loads((tmp_path / "calibration" / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["fights"]) == 33

    run_ids = {f["run_id"] for f in manifest["fights"]}
    assert len(run_ids) == 33  # no duplicates


def test_repeat_recording_shares_matchup_but_has_distinct_run_id(tmp_path, monkeypatch):
    """The recorder gives repeat recordings of one matchup an explicit
    _r2/_r3/_rN tag suffix (e.g. champion__vs__arbalester_r3). Each repeat
    must be its own run_id/manifest entry with genuinely different content,
    while sharing the same `matchup` grouping key as the unsuffixed run —
    that grouping is how the scorer will measure the real game's own
    run-to-run variance."""
    ingest_mod = _isolate_calibration_storage(monkeypatch, tmp_path)

    ingest_mod.ingest_zip(str(BATCH_033_ZIP))
    manifest = json.loads((tmp_path / "calibration" / "manifest.json").read_text(encoding="utf-8"))
    by_run_id = {f["run_id"]: f for f in manifest["fights"]}

    base = by_run_id["champion__vs__arbalester"]
    repeat = by_run_id["champion__vs__arbalester_r3"]
    assert base["matchup"] == "champion__vs__arbalester"
    assert repeat["matchup"] == "champion__vs__arbalester"
    assert base["run_id"] != repeat["run_id"]
    assert base["content_hash"] != repeat["content_hash"]  # genuinely different recordings

    # 4 recordings of this matchup (base + _r2 + _r3 + _r4), all grouped under it.
    same_matchup = [f for f in manifest["fights"] if f["matchup"] == "champion__vs__arbalester"]
    assert len(same_matchup) == 4
    assert {f["run_id"] for f in same_matchup} == {
        "champion__vs__arbalester",
        "champion__vs__arbalester_r2",
        "champion__vs__arbalester_r3",
        "champion__vs__arbalester_r4",
    }


def _make_true_conflict_zip(dst: Path, tag_to_mutate: str) -> Path:
    """Copy ZIP but change one fight's meta.json composition (different unit
    name on one side) AND its units.jsonl.gz raw bytes, so ingest_zip sees
    the same run_id with different content AND a different composition —
    a genuine tag collision between two unrelated fights, never a repeat
    recording. Never read past content_hash for a true conflict (the
    conflict is detected before any parsing), so the mutated bytes don't
    need to remain valid gzip/jsonl.
    """
    with zipfile.ZipFile(ZIP) as zin:
        names = zin.namelist()
        data = {n: zin.read(n) for n in names}

    units_key = f"decoded/{tag_to_mutate}.units.jsonl.gz"
    data[units_key] = data[units_key] + b"\x00mutated-for-conflict-test"

    meta_key = f"decoded/{tag_to_mutate}.meta.json"
    meta = json.loads(data[meta_key])
    side_key = next(iter(meta["composition"]))
    unit_name = next(iter(meta["composition"][side_key]))
    count = meta["composition"][side_key].pop(unit_name)
    meta["composition"][side_key]["Totally Different Unit"] = count
    data[meta_key] = json.dumps(meta).encode("utf-8")

    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for n in names:
            zout.writestr(n, data[n])
    return dst


def test_same_run_id_different_composition_is_conflict_not_overwrite(tmp_path, monkeypatch):
    """If a run_id ever reappears with DIFFERENT content AND a genuinely
    different composition (a real tag collision between two unrelated
    fights, not a repeat recording), ingest_zip must never silently
    discard the existing recording, overwrite it, or guess — it must leave
    the entry untouched and report the conflict loudly (IngestFailures)."""
    ingest_mod = _isolate_calibration_storage(monkeypatch, tmp_path)

    first_ids = ingest_mod.ingest_zip(str(ZIP))
    assert "hand_cannoneer__vs__elite_elephant" in first_ids

    manifest_before = json.loads((tmp_path / "calibration" / "manifest.json").read_text(encoding="utf-8"))
    entry_before = next(
        f for f in manifest_before["fights"] if f["run_id"] == "hand_cannoneer__vs__elite_elephant"
    )

    conflicting_zip = _make_true_conflict_zip(tmp_path / "conflicting.zip", "hand_cannoneer__vs__elite_elephant")

    with pytest.raises(ingest_mod.IngestFailures) as excinfo:
        ingest_mod.ingest_zip(str(conflicting_zip))

    assert len(excinfo.value.conflicts) == 1
    assert excinfo.value.conflicts[0][0] == "hand_cannoneer__vs__elite_elephant"
    # The other fight in this drop is untouched by the conflict and still a no-op success.
    assert "elite_steppe__vs__arbalester" in excinfo.value.successes

    manifest_after = json.loads((tmp_path / "calibration" / "manifest.json").read_text(encoding="utf-8"))
    entry_after = next(
        f for f in manifest_after["fights"] if f["run_id"] == "hand_cannoneer__vs__elite_elephant"
    )
    assert entry_after == entry_before  # existing entry left completely untouched


def _recompressed(raw_gz_bytes: bytes) -> bytes:
    """Decompress+recompress gzip bytes: gzip embeds a fresh timestamp on
    every compress() call, so this produces different raw bytes (a
    different content_hash) while decompressing to byte-identical JSONL
    content. Used to simulate "recorder made a genuinely new recording,
    same matchup, same composition" without needing new real tape data."""
    import gzip as _gzip

    return _gzip.compress(_gzip.decompress(raw_gz_bytes))


def _make_reused_tag_repeat_zip(dst: Path, tag: str) -> Path:
    """Copy ZIP but recompress `tag`'s units/damage/missiles streams (see
    `_recompressed`) so its content_hash differs while meta.json's
    composition — and therefore civ/HP/attack validation — stays
    byte-for-byte the same as the original recording. This mirrors what
    was observed on a real corpus (aoe2_golden_batch91_partial_103.zip):
    hand_cannoneer__vs__elite_elephant recorded twice (152.31s and
    129.79s), same tag both times, same two units both times — the
    recorder reused the tag instead of adding its own _rN suffix.
    """
    with zipfile.ZipFile(ZIP) as zin:
        names = zin.namelist()
        data = {n: zin.read(n) for n in names}
    for suffix in ("units.jsonl.gz", "damage.jsonl.gz", "missiles.jsonl.gz"):
        key = f"decoded/{tag}.{suffix}"
        data[key] = _recompressed(data[key])
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for n in names:
            zout.writestr(n, data[n])
    return dst


def test_reused_tag_repeat_gets_reassigned_run_id_not_discarded(tmp_path, monkeypatch):
    """When the recorder reuses an existing tag for a genuine new recording
    (composition — the two unit names — still matches the existing entry,
    only the content differs), ingest_zip must keep BOTH recordings under
    distinct run_ids (auto-assigning the next free `<matchup>_rN` slot)
    rather than discarding the newer one or raising a conflict — every
    recording is a variance sample worth keeping."""
    ingest_mod = _isolate_calibration_storage(monkeypatch, tmp_path)

    first_ids = ingest_mod.ingest_zip(str(ZIP))
    assert "hand_cannoneer__vs__elite_elephant" in first_ids

    manifest_before = json.loads((tmp_path / "calibration" / "manifest.json").read_text(encoding="utf-8"))
    entry_before = next(
        f for f in manifest_before["fights"] if f["run_id"] == "hand_cannoneer__vs__elite_elephant"
    )

    repeat_zip = _make_reused_tag_repeat_zip(tmp_path / "reused_tag_repeat.zip", "hand_cannoneer__vs__elite_elephant")

    # Must NOT raise: this is a successful ingest, not a failure/conflict.
    # ids returned are the reassigned run_id (NOT the raw tag) for the
    # repeat, plus the other fight in this zip as an untouched no-op.
    second_ids = ingest_mod.ingest_zip(str(repeat_zip))
    assert set(second_ids) == {"hand_cannoneer__vs__elite_elephant_r2", "elite_steppe__vs__arbalester"}

    manifest_after = json.loads((tmp_path / "calibration" / "manifest.json").read_text(encoding="utf-8"))
    by_run_id = {f["run_id"]: f for f in manifest_after["fights"]}
    assert len(manifest_after["fights"]) == 3  # original 2 + the new repeat, nothing dropped

    original = by_run_id["hand_cannoneer__vs__elite_elephant"]
    repeat = by_run_id["hand_cannoneer__vs__elite_elephant_r2"]
    assert original == entry_before  # original entry left completely untouched
    assert repeat["matchup"] == "hand_cannoneer__vs__elite_elephant"
    assert repeat["content_hash"] != original["content_hash"]
    assert repeat["side1"]["unit_name"] == original["side1"]["unit_name"]
    assert repeat["side2"]["unit_name"] == original["side2"]["unit_name"]

    # Both recordings' tape directories must exist on disk — nothing discarded.
    assert (tmp_path / "golden" / "tapes" / "hand_cannoneer__vs__elite_elephant").is_dir()
    repeat_dir = tmp_path / "golden" / "tapes" / "hand_cannoneer__vs__elite_elephant_r2"
    assert repeat_dir.is_dir()

    # ...and the staged files inside must carry the REASSIGNED run_id, not
    # the raw recorded tag. Asserting only that the dir exists is what let
    # the original bug ship: the decoded streams were copied in keeping
    # their `<tag>.*` names, so extract.build_truth_card's
    # `<run_id>.damage.jsonl.gz` lookup missed and it emitted a silent
    # all-zero truth card for this exact fight.
    staged = sorted(p.name for p in repeat_dir.iterdir())
    assert staged, "repeat run's tape dir is empty"
    for name in staged:
        assert name.startswith("hand_cannoneer__vs__elite_elephant_r2."), (
            f"staged tape file {name!r} does not carry the reassigned run_id — "
            f"extract would not find it"
        )
    assert "hand_cannoneer__vs__elite_elephant_r2.damage.jsonl.gz" in staged

    # Re-ingesting the SAME reused-tag-repeat zip again must stay a no-op:
    # the literal run_id==tag slot still holds the OLDER (original)
    # recording, so a naive "does this exact run_id slot's content match"
    # check would wrongly treat this as yet another new repeat and mint an
    # unbounded string of identical _r3, _r4, ... duplicates. It must
    # instead recognize the content already exists (under the reassigned
    # _r2 run_id) and no-op.
    third_ids = ingest_mod.ingest_zip(str(repeat_zip))
    assert set(third_ids) == {"hand_cannoneer__vs__elite_elephant_r2", "elite_steppe__vs__arbalester"}
    manifest_third = json.loads((tmp_path / "calibration" / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest_third["fights"]) == 3  # unchanged — still just original + one repeat

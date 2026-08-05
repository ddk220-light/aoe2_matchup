import importlib.util
import hashlib
import json
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SERVER_MODULE = ROOT / "calibration" / "viewer" / "hc_compare_server.py"


def load_viewer_module():
    if not SERVER_MODULE.exists():
        pytest.fail("HC comparison viewer server has not been implemented")
    spec = importlib.util.spec_from_file_location("hc_compare_server", SERVER_MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_catalog_uses_only_locked_final_tape_and_ranks_the_three_hc_families():
    viewer = load_viewer_module()
    catalog = viewer.build_catalog(ROOT)

    assert catalog["source"]["sha256"] == (
        "31A31FE39C025DDD88EB1F502FD62E0EC48464F4CBB72C1693D5C4FEED0713C9"
    )
    assert [family["id"] for family in catalog["families"]] == [
        "hand_cannoneer__vs__heavy_scorpion",
        "hand_cannoneer__vs__elite_steppe",
        "hand_cannoneer__vs__paladin",
    ]
    assert [family["tape"]["winner_slug"] for family in catalog["families"]] == [
        "heavy_scorpion",
        "elite_steppe",
        "paladin",
    ]
    assert [family["tape"]["winner_hp_pct"] for family in catalog["families"]] == pytest.approx(
        [42.1, 8.0, 17.9], abs=0.1
    )

    for family in catalog["families"]:
        assert family["recordings"]
        for recording in family["recordings"]:
            assert recording["source_archive"] == "aoe2_golden_STANDARD_UNITS_FINAL.zip"
            assert recording["zip_sha256"] == catalog["source"]["sha256"]
            assert len(recording["positions"]["1"]) == recording["teams"][0]["count"]
            assert len(recording["positions"]["2"]) == recording["teams"][1]["count"]


def test_source_verifier_rejects_metadata_that_disagrees_with_archive(monkeypatch):
    viewer = load_viewer_module()
    original_read_json = viewer._read_json

    def tampered_metadata(path):
        if Path(path).name == "source_of_truth.json":
            return {
                "archive": "aoe2_golden_STANDARD_UNITS_FINAL.zip",
                "sha256": "0" * 64,
                "recordings": 339,
            }
        return original_read_json(path)

    monkeypatch.setattr(viewer, "_read_json", tampered_metadata)

    with pytest.raises(RuntimeError, match="archive SHA-256"):
        viewer.verify_source_archive(ROOT)


def test_variant_contract_keeps_hypotheses_isolated_and_exposes_recovery_control():
    viewer = load_viewer_module()
    variants = viewer.variant_specs(ROOT)

    assert list(variants) == ["base", "recovery", "h1", "h2", "h3", "h1_h3"]
    assert variants["base"]["flags"] == {}
    assert variants["recovery"]["flags"] == {"c3": ["postSwingRecovery"]}
    assert variants["h1"]["flags"] == {
        "c3": ["postSwingRecovery", "postSwingPlant", "postSwingCollisionAnchor"]
    }
    assert variants["h2"]["flags"] == {
        "c3": ["postSwingRecovery"],
        "h2": ["laneAwareRangedHandoff"],
    }
    assert variants["h3"]["flags"] == {"c3": ["postSwingRecovery"]}
    assert variants["h3"]["arena"] == "tapebox-obstacle"
    assert variants["h1_h3"]["flags"] == {
        "c3": ["postSwingRecovery", "postSwingPlant", "postSwingCollisionAnchor"]
    }
    assert variants["h1_h3"]["arena"] == "tapebox-obstacle"
    assert variants["h1_h3"]["engine_root"] == variants["h3"]["engine_root"]
    assert variants["h2"]["engine_root"].resolve().is_dir()


def test_http_server_serves_catalog_page_and_variant_modules_without_traversal():
    viewer = load_viewer_module()
    server = viewer.make_server(ROOT, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base}/api/catalog") as response:
            payload = json.load(response)
        assert payload["families"][0]["id"] == "hand_cannoneer__vs__heavy_scorpion"

        with urllib.request.urlopen(f"{base}/") as response:
            html = response.read().decode("utf-8")
        assert "HC FIELD LAB" in html

        with urllib.request.urlopen(f"{base}/bundle/h2/engine/constants.js") as response:
            constants = response.read().decode("utf-8")
        assert "laneAwareRangedHandoff" in constants

        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"{base}/bundle/h2/engine/../../../../AGENTS.md")
        assert exc.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_physics_renderer_uses_exact_collision_radius_and_tile_ruler():
    renderer_path = ROOT / "calibration" / "viewer" / "physics_renderer.js"
    assert renderer_path.exists(), "calibration physics renderer has not been implemented"

    renderer_source = renderer_path.read_text(encoding="utf-8")
    app_source = (ROOT / "calibration" / "viewer" / "app.js").read_text(encoding="utf-8")
    assert "const radius = unit.radius;" in renderer_source
    assert "unit.drawRadius" not in renderer_source
    assert "TILE_SIZE" in renderer_source
    assert "1 tile" in renderer_source
    assert "physics_renderer.js" in app_source
    assert "PhysicsSimRenderer" in app_source

    viewer = load_viewer_module()
    server = viewer.make_server(ROOT, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base}/bundle/h1/physics_renderer.js") as response:
            served_source = response.read().decode("utf-8")
        assert "PhysicsSimRenderer" in served_source
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_variant_smoke_runner_executes_the_three_final_scenarios():
    runner = ROOT / "calibration" / "viewer" / "hc_variant_smoke.mjs"
    if not runner.exists():
        pytest.fail("HC variant smoke runner has not been implemented")
    completed = subprocess.run(
        ["node", str(runner), "--variant", "base", "--seeds", "1"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["source_sha256"] == (
        "31A31FE39C025DDD88EB1F502FD62E0EC48464F4CBB72C1693D5C4FEED0713C9"
    )
    assert [row["matchup"] for row in payload["results"]] == [
        "hand_cannoneer__vs__heavy_scorpion",
        "hand_cannoneer__vs__elite_steppe",
        "hand_cannoneer__vs__paladin",
    ]
    assert all(row["runs"] == 1 for row in payload["results"])


def test_h1_h3_gate_runs_five_seeds_for_every_final_hc_melee_recording():
    runner = ROOT / "calibration" / "viewer" / "hc_variant_smoke.mjs"
    completed = subprocess.run(
        [
            "node",
            str(runner),
            "--variant",
            "h1_h3",
            "--scope",
            "hc-melee",
            "--seeds",
            "5",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["gate_passed"] is True
    assert len(payload["results"]) == 7
    assert sum(row["recordings"] for row in payload["results"]) == 33
    assert all(row["runs"] == row["recordings"] * 5 for row in payload["results"])
    assert all(row["winner_correct"] and row["within_25pct"] for row in payload["results"])

    archive = ROOT / "calibration" / "source" / "aoe2_golden_STANDARD_UNITS_FINAL.zip"
    assert payload["source_sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest().upper()


def test_variant_smoke_runner_can_measure_another_ranged_unit_against_melee():
    runner = ROOT / "calibration" / "viewer" / "hc_variant_smoke.mjs"
    completed = subprocess.run(
        [
            "node",
            str(runner),
            "--variant",
            "base",
            "--scope",
            "other-ranged-melee",
            "--matchup",
            "champion__vs__arbalester",
            "--seeds",
            "1",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["scope"] == "other-ranged-melee"
    assert payload["gate_passed"] is None
    assert len(payload["results"]) == 1

    result = payload["results"][0]
    assert result["matchup"] == "champion__vs__arbalester"
    assert result["focal_slug"] == "arbalester"
    assert result["recordings"] == 8
    assert result["runs"] == 8

"""Local-only Hand Cannoneer hypothesis viewer backed by the locked FINAL tape.

The server deliberately does not import or modify production Flask code. It
serves a small diagnostic UI, builds scenarios from ``calibration/fixtures``,
and exposes isolated engine snapshots from the H1/H2/H3 evidence worktrees.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import statistics
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


LOCKED_ARCHIVE = "aoe2_golden_STANDARD_UNITS_FINAL.zip"
LOCKED_ARCHIVE_SHA256 = "31A31FE39C025DDD88EB1F502FD62E0EC48464F4CBB72C1693D5C4FEED0713C9"
LOCKED_RECORDINGS = 339


TOP_FAMILIES = (
    {
        "id": "hand_cannoneer__vs__heavy_scorpion",
        "label": "Hand Cannoneer vs Heavy Scorpion",
        "rank": 1,
        "baseline": {
            "winner_slug": "hand_cannoneer",
            "winner_label": "Hand Cannoneer",
            "winner_hp_pct": 22.3,
            "signed_gap_pp": 64.4,
            "wrong_winner": True,
            "samples": 25,
        },
    },
    {
        "id": "hand_cannoneer__vs__elite_steppe",
        "label": "Hand Cannoneer vs Elite Steppe Lancer",
        "rank": 2,
        "baseline": {
            "winner_slug": "elite_steppe",
            "winner_label": "Elite Steppe Lancer",
            "winner_hp_pct": 52.4,
            "signed_gap_pp": 44.4,
            "wrong_winner": False,
            "samples": 5,
        },
    },
    {
        "id": "hand_cannoneer__vs__paladin",
        "label": "Hand Cannoneer vs Paladin",
        "rank": 3,
        "baseline": {
            "winner_slug": "paladin",
            "winner_label": "Paladin",
            "winner_hp_pct": 57.5,
            "signed_gap_pp": 39.7,
            "wrong_winner": False,
            "samples": 50,
        },
    },
)


def _read_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def verify_source_archive(repo_root: Path) -> dict:
    """Hash the locked ZIP bytes; never trust fixture metadata as provenance."""
    source_root = Path(repo_root) / "calibration" / "source"
    source = _read_json(source_root / "source_of_truth.json")
    if source.get("archive") != LOCKED_ARCHIVE:
        raise RuntimeError(f"unexpected tape archive: {source.get('archive')!r}")
    archive_path = source_root / LOCKED_ARCHIVE
    digest = hashlib.sha256()
    with archive_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    actual_sha = digest.hexdigest().upper()
    declared_sha = str(source.get("sha256", "")).upper()
    if declared_sha != actual_sha:
        raise RuntimeError(
            f"archive SHA-256 metadata mismatch: declared {declared_sha}, actual {actual_sha}"
        )
    if actual_sha != LOCKED_ARCHIVE_SHA256:
        raise RuntimeError(
            f"archive SHA-256 is not the locked FINAL digest: {actual_sha}"
        )
    if int(source.get("recordings", -1)) != LOCKED_RECORDINGS:
        raise RuntimeError("locked source metadata must declare 339 recordings")
    return {**source, "sha256": actual_sha}


def _winner_for_truth(truth: dict) -> tuple[str | None, str | None, float]:
    living = []
    for side_key, side in truth["sides"].items():
        if float(side["hp_remaining"]) > 0:
            living.append((side_key, side))
    if len(living) != 1:
        return None, None, 0.0
    _, side = living[0]
    return side["slug"], side["unit_name"], float(side["hp_remaining"])


def _tape_recording(fight: dict, truth: dict, positions: dict, dicts: dict) -> dict:
    winner_slug, winner_label, winner_hp = _winner_for_truth(truth)
    winner_hp_pct = 0.0
    if winner_slug:
        winner_side = next(side for side in truth["sides"].values() if side["slug"] == winner_slug)
        combat = dicts[f"{winner_side['civ']}|{winner_slug}"]
        max_hp = float(combat["hp"]) * int(winner_side["start_count"])
        winner_hp_pct = 100.0 * winner_hp / max_hp

    teams = []
    engine_positions = {}
    for engine_team, side_name in enumerate(("side1", "side2"), start=1):
        side = fight[side_name]
        teams.append(
            {
                "civ": side["civ"],
                "slug": side["slug"],
                "label": side["unit_name"],
                "count": int(side["count"]),
                "combat_dict": dicts[f"{side['civ']}|{side['slug']}"],
            }
        )
        engine_positions[str(engine_team)] = positions[fight["tag"]][str(side["owner"])]

    truth_sides = list(truth["sides"].values())
    return {
        "tag": fight["tag"],
        "source_archive": fight["source_archive"],
        "zip_sha256": fight["zip_sha256"],
        "duration_s": float(truth["duration_s"]),
        "teams": teams,
        "positions": engine_positions,
        "tape": {
            "winner_slug": winner_slug,
            "winner_label": winner_label or "Draw",
            "winner_hp_pct": round(winner_hp_pct, 3),
            "side1_hits": int(truth_sides[0]["hits_landed"]),
            "side2_hits": int(truth_sides[1]["hits_landed"]),
            "side1_swings": int(truth_sides[0]["swing_count"]),
            "side2_swings": int(truth_sides[1]["swing_count"]),
        },
    }


def build_catalog(repo_root: Path) -> dict:
    repo_root = Path(repo_root)
    fixture_root = repo_root / "calibration" / "fixtures"
    source = verify_source_archive(repo_root)
    manifest = _read_json(fixture_root / "manifest.json")["fights"]
    if len(manifest) != LOCKED_RECORDINGS:
        raise RuntimeError(f"locked FINAL manifest has {len(manifest)} fights, expected 339")
    if any(
        fight.get("source_archive") != LOCKED_ARCHIVE or
        str(fight.get("zip_sha256", "")).upper() != source["sha256"]
        for fight in manifest
    ):
        raise RuntimeError("fixture manifest contains a non-FINAL tape source")
    positions = _read_json(fixture_root / "spawns.json")
    dicts = _read_json(fixture_root / "combat_dicts.json")
    fights_by_matchup: dict[str, list[dict]] = {}
    for fight in manifest:
        fights_by_matchup.setdefault(fight["matchup"], []).append(fight)

    families = []
    for family_spec in TOP_FAMILIES:
        family_id = family_spec["id"]
        recordings = []
        for fight in fights_by_matchup.get(family_id, []):
            truth = _read_json(fixture_root / "truth" / f"{fight['tag']}.json")
            recordings.append(_tape_recording(fight, truth, positions, dicts))
        if not recordings:
            raise RuntimeError(f"Locked FINAL fixtures contain no recordings for {family_id}")

        winners = Counter(r["tape"]["winner_slug"] for r in recordings if r["tape"]["winner_slug"])
        modal_winner, modal_count = winners.most_common(1)[0]
        winning_runs = [r for r in recordings if r["tape"]["winner_slug"] == modal_winner]
        hp_median = statistics.median(r["tape"]["winner_hp_pct"] for r in winning_runs)
        representative = min(
            winning_runs,
            key=lambda r: (abs(r["tape"]["winner_hp_pct"] - hp_median), r["tag"]),
        )
        modal_label = representative["tape"]["winner_label"]
        families.append(
            {
                **family_spec,
                "tape": {
                    "winner_slug": modal_winner,
                    "winner_label": modal_label,
                    "winner_hp_pct": round(hp_median, 3),
                    "winner_runs": modal_count,
                    "recordings": len(recordings),
                },
                "representative_tag": representative["tag"],
                "recordings": recordings,
            }
        )

    return {
        "source": {
            "archive": source["archive"],
            "sha256": source["sha256"],
            "recordings": source["recordings"],
        },
        "baseline_run": "calibration/runs/standard-units-current-5x-20260803",
        "families": families,
        "variants": {
            key: {
                "label": value["label"],
                "short": value["short"],
                "description": value["description"],
                "flags": value["flags"],
                "arena": value["arena"],
            }
            for key, value in variant_specs(repo_root).items()
        },
    }


def variant_specs(repo_root: Path) -> dict:
    repo_root = Path(repo_root)
    engine_rel = Path("apps") / "website" / "static" / "js" / "engine"
    return {
        "base": {
            "label": "Base — current simulation",
            "short": "BASE",
            "description": "Current engine, no diagnostic HC hypothesis enabled.",
            "engine_root": repo_root / engine_rel,
            "flags": {},
            "arena": "tapebox",
        },
        "recovery": {
            "label": "Recovery — shared control",
            "short": "CTRL",
            "description": "Speed-qualified post-swing recovery used as the common H1/H2/H3 control.",
            "engine_root": repo_root / ".worktrees" / "hc-h1-posthit" / engine_rel,
            "flags": {"c3": ["postSwingRecovery"]},
            "arena": "tapebox",
        },
        "h1": {
            "label": "H1 — post-hit collision anchor",
            "short": "H1",
            "description": "Recovery + 0.7 s plant + allied collision anchoring after a landed melee swing.",
            "engine_root": repo_root / ".worktrees" / "hc-h1-posthit" / engine_rel,
            "flags": {
                "c3": ["postSwingRecovery", "postSwingPlant", "postSwingCollisionAnchor"]
            },
            "arena": "tapebox",
        },
        "h2": {
            "label": "H2 — lane-aware kill handoff",
            "short": "H2",
            "description": "Recovery + lane-aware target acquisition immediately after killing a ranged unit.",
            "engine_root": repo_root / ".worktrees" / "hc-h2-viewer" / engine_rel,
            "flags": {
                "c3": ["postSwingRecovery"],
                "h2": ["laneAwareRangedHandoff"],
            },
            "arena": "tapebox",
        },
        "h3": {
            "label": "H3 — central obstruction",
            "short": "H3",
            "description": "Recovery + the recorded central tree/rock obstruction inside the exact-spawn TapeBox.",
            "engine_root": repo_root / ".worktrees" / "hc-h3-obstacle" / engine_rel,
            "flags": {"c3": ["postSwingRecovery"]},
            "arena": "tapebox-obstacle",
        },
        "h1_h3": {
            "label": "H1 + H3 - planted clockwise kite",
            "short": "H1+H3",
            "description": "H1's planted, collision-anchored melee swing composed with H3's clockwise central-obstacle route.",
            "engine_root": repo_root / ".worktrees" / "hc-h3-obstacle" / engine_rel,
            "flags": {
                "c3": [
                    "postSwingRecovery",
                    "postSwingPlant",
                    "postSwingCollisionAnchor",
                ]
            },
            "arena": "tapebox-obstacle",
        },
    }


def _safe_child(root: Path, relative: str) -> Path | None:
    root = root.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _handler_class(repo_root: Path):
    viewer_root = repo_root / "calibration" / "viewer"
    renderer_path = repo_root / "apps" / "website" / "static" / "js" / "sim_renderer.js"
    physics_renderer_path = viewer_root / "physics_renderer.js"
    variants = variant_specs(repo_root)

    class Handler(BaseHTTPRequestHandler):
        server_version = "HCFieldLab/1.0"

        def log_message(self, _format, *_args):
            return

        def _send_bytes(self, payload: bytes, content_type: str, status: int = 200):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)

        def _send_file(self, path: Path):
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if path.suffix == ".js":
                content_type = "text/javascript; charset=utf-8"
            elif path.suffix == ".html":
                content_type = "text/html; charset=utf-8"
            self._send_bytes(path.read_bytes(), content_type)

        def _not_found(self):
            self._send_bytes(b"not found\n", "text/plain; charset=utf-8", 404)

        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            if path == "/":
                return self._send_file(viewer_root / "index.html")
            if path == "/app.js":
                return self._send_file(viewer_root / "app.js")
            if path == "/api/catalog":
                payload = json.dumps(build_catalog(repo_root), separators=(",", ":")).encode("utf-8")
                return self._send_bytes(payload, "application/json; charset=utf-8")

            parts = path.strip("/").split("/")
            if len(parts) >= 3 and parts[0] == "bundle" and parts[1] in variants:
                variant = variants[parts[1]]
                if parts[2:] == ["sim_renderer.js"]:
                    return self._send_file(renderer_path)
                if parts[2:] == ["physics_renderer.js"]:
                    return self._send_file(physics_renderer_path)
                if len(parts) >= 4 and parts[2] == "engine":
                    relative = "/".join(parts[3:])
                    module = _safe_child(variant["engine_root"], relative)
                    if module and module.suffix == ".js":
                        return self._send_file(module)
            return self._not_found()

    return Handler


def make_server(repo_root: Path, host: str = "127.0.0.1", port: int = 5010):
    repo_root = Path(repo_root).resolve()
    return ThreadingHTTPServer((host, port), _handler_class(repo_root))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=5010, type=int)
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    server = make_server(repo_root, args.host, args.port)
    print(f"HC Field Lab: http://{args.host}:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

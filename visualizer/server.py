#!/usr/bin/env python3
"""
Flask server for AoE2 Replay Visualizer.
Handles file uploads and processes replay files.
"""

import csv
import io
import json
import os
import sys
import tempfile
import zipfile
from collections import defaultdict
from datetime import datetime

import mgz
import mgz.model
import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# AoE2 Companion API settings
AOE2_COMPANION_API = "https://data.aoe2companion.com/api"
AOE2_COMPANION_HEADERS = {"User-Agent": "https://github.com/aoe2record-visualizer"}
REPLAY_DOWNLOAD_URL = "https://aoe.ms/replay"

# Players list file
PLAYERS_CSV_PATH = os.path.join(os.path.dirname(__file__), "players.csv")

app = Flask(__name__, static_folder="public", static_url_path="")


def load_players_from_csv():
    """Load player list from CSV file."""
    players = []
    try:
        with open(PLAYERS_CSV_PATH, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                players.append(
                    {"name": row["name"], "profileId": int(row["profileId"])}
                )
    except FileNotFoundError:
        app.logger.warning(f"Players CSV not found: {PLAYERS_CSV_PATH}")
    return players


CORS(app)

# AoE2 standard player colors
PLAYER_COLORS = {
    0: {"name": "Blue", "hex": "#0042FF"},
    1: {"name": "Red", "hex": "#FF0000"},
    2: {"name": "Green", "hex": "#00FF00"},
    3: {"name": "Yellow", "hex": "#FFFF00"},
    4: {"name": "Cyan", "hex": "#00FFFF"},
    5: {"name": "Purple", "hex": "#FF00FF"},
    6: {"name": "Grey", "hex": "#808080"},
    7: {"name": "Orange", "hex": "#FFA500"},
}

DEATH_THRESHOLD = 5 * 60

# Unit type classification
INFANTRY_UNITS = {
    "militia",
    "manatarms",
    "longswordsman",
    "twohanded swordsman",
    "champion",
    "spearman",
    "pikeman",
    "halberdier",
    "eaglescout",
    "eaglewarrior",
    "eliteeaglewarrior",
    "condottiero",
    "kamayuk",
    "elitekamayuk",
    "shotelwarrior",
    "eliteshotelwarrior",
    "gbeto",
    "elitegbeto",
    "supplywaggon",
    "huskarl",
    "elitehuskarl",
    "teutonic knight",
    "eliteteutonic knight",
    "berserk",
    "eliteberserk",
    "jaguar warrior",
    "elitejaguar warrior",
    "woad raider",
    "elitewoad raider",
    "throwing axeman",
    "elitethrowing axeman",
    "samurai",
    "elitesamurai",
    "urumi swordsman",
    "eliteurumi swordsman",
    "obuch",
    "eliteobuch",
    "serjeant",
    "eliteserjeant",
    "flemish militia",
    "warrior priest",
}

CAVALRY_UNITS = {
    "scoutcavalry",
    "lightcavalry",
    "hussar",
    "wingedhussar",
    "knight",
    "cavalier",
    "paladin",
    "camelrider",
    "heavycamelrider",
    "imperialcamelrider",
    "battleelephant",
    "elitebattleelephant",
    "steppelancer",
    "elitesteppelancer",
    "cataphract",
    "elitecataphract",
    "boyar",
    "eliteboyar",
    "konnik",
    "elitekonnik",
    "leitis",
    "eliteleitis",
    "keshik",
    "elitekeshik",
    "magyar huszar",
    "elitemagyar huszar",
    "tarkan",
    "elitetarkan",
    "war elephant",
    "elitewar elephant",
    "mameluke",
    "elitemameluke",
    "shrivamsha rider",
    "eliteshrivamsha rider",
    "coustillier",
    "elitecoustillier",
    "monaspa",
    "elitemonaspa",
    "savar",
}

ARCHER_UNITS = {
    "archer",
    "crossbowman",
    "arbalester",
    "skirmisher",
    "eliteskirmisher",
    "imperialskirmisher",
    "cavalryarcher",
    "heavycavalryarcher",
    "handcannoneer",
    "slinger",
    "longbowman",
    "elitelongbowman",
    "chukonou",
    "elitechukonou",
    "mangudai",
    "elitemangudai",
    "warwagon",
    "elitewarwagon",
    "plumedarchery",
    "eliteplumedarchery",
    "genitour",
    "elitegenitour",
    "camel archer",
    "elitecamel archer",
    "genoese crossbowman",
    "elitegenoese crossbowman",
    "elephant archer",
    "eliteelephant archer",
    "rattan archer",
    "eliterattan archer",
    "kipchak",
    "elitekipchak",
    "arambai",
    "elitearambai",
    "janissary",
    "elitejanissary",
    "conquistador",
    "eliteconquistador",
    "rattaarcher",
    "eliterattaarcher",
    "chakram thrower",
    "elitechakram thrower",
    "thirisadai",
}

SIEGE_UNITS = {
    "batteringram",
    "cappedram",
    "siegeram",
    "mangonel",
    "onager",
    "siegeonager",
    "scorpion",
    "heavyscorpion",
    "bombardcannon",
    "siegetower",
    "trebuchet",
    "organ gun",
    "eliteorgan gun",
    "houfnice",
}

MONK_UNITS = {
    "monk",
    "missionary",
    "imam",
    "warrior priest",
}

SHIP_UNITS = {
    "galley",
    "war galley",
    "galleon",
    "fire galley",
    "fire ship",
    "fast fire ship",
    "demolition raft",
    "demolition ship",
    "heavy demolition ship",
    "cannon galleon",
    "elite cannon galleon",
    "longboat",
    "elitelongboat",
    "turtle ship",
    "eliteturtle ship",
    "caravel",
    "elitecaravel",
    "dromon",
    "transport ship",
    "fishing ship",
    "trade cog",
}


def classify_unit_type(unit_name):
    """Classify a unit into a category based on its name."""
    name_lower = unit_name.lower().replace("_", " ").replace("-", " ")

    # Check each category
    for infantry in INFANTRY_UNITS:
        if infantry in name_lower:
            return "infantry"

    for cavalry in CAVALRY_UNITS:
        if cavalry in name_lower:
            return "cavalry"

    for archer in ARCHER_UNITS:
        if archer in name_lower:
            return "archer"

    for siege in SIEGE_UNITS:
        if siege in name_lower:
            return "siege"

    for monk in MONK_UNITS:
        if monk in name_lower:
            return "monk"

    for ship in SHIP_UNITS:
        if ship in name_lower:
            return "ship"

    # Special cases
    if "villager" in name_lower:
        return "villager"
    if "scout" in name_lower:
        return "cavalry"  # Scout cavalry
    if "king" in name_lower:
        return "king"

    return "military"  # Default


def load_object_names():
    """Load object ID to name mappings."""
    try:
        import aocref

        aocref_path = os.path.dirname(aocref.__file__)
        dataset_file = os.path.join(aocref_path, "data", "datasets", "100.json")
        with open(dataset_file, "r") as f:
            data = json.load(f)
            return data.get("objects", {})
    except:
        return {}


def process_replay(replay_file):
    """Process a replay file and return JSON data."""

    object_names = load_object_names()

    match = mgz.model.parse_match(replay_file)
    match_duration = match.duration.total_seconds()

    # Build unit owner map
    unit_owner_map = {}
    for player in match.players:
        if player.objects:
            for obj in player.objects:
                unit_owner_map[obj.instance_id] = player.name

    for action in match.actions:
        if not action.player:
            continue
        payload = action.payload or {}
        if "object_ids" in payload:
            for obj_id in payload["object_ids"]:
                if obj_id not in unit_owner_map:
                    unit_owner_map[obj_id] = action.player.name

    # Track actions per unit with first seen time
    unit_actions = defaultdict(list)
    unit_first_seen = {}  # obj_id -> first time seen
    for action in match.actions:
        if not action.player:
            continue
        payload = action.payload or {}
        action_time = action.timestamp.total_seconds()
        if "object_ids" in payload:
            for obj_id in payload["object_ids"]:
                unit_actions[obj_id].append(
                    {
                        "time": action_time,
                        "type": str(action.type).replace("Action.", ""),
                    }
                )
                if obj_id not in unit_first_seen:
                    unit_first_seen[obj_id] = action_time

    # Determine villagers by BUILD actions
    villager_ids = set()
    for obj_id, actions in unit_actions.items():
        if any(a["type"] == "BUILD" for a in actions):
            villager_ids.add(obj_id)

    # Build unit names
    unit_name_map = {}
    unit_counters = defaultdict(lambda: defaultdict(int))

    # Collect training events with more detail
    # Track training queue per player - list of (time, unit_type, used) tuples
    training_queue = defaultdict(list)  # player -> [(time, unit_type, used), ...]
    for action in match.actions:
        if not action.player:
            continue
        action_type = str(action.type).replace("Action.", "")
        if action_type == "DE_QUEUE" and action.payload:
            unit_type_name = action.payload.get("unit", "unit")
            training_queue[action.player.name].append(
                {
                    "time": action.timestamp.total_seconds(),
                    "unit_type": unit_type_name.lower().replace(" ", ""),
                    "used": False,
                }
            )

    # Sort training queues by time
    for player in training_queue:
        training_queue[player].sort(key=lambda x: x["time"])

    # Name starting units (these have obj.name from the replay)
    starting_obj_ids = set()
    for player in match.players:
        if player.objects:
            for obj in player.objects:
                starting_obj_ids.add(obj.instance_id)
                unit_type = obj.name.lower().replace(" ", "") if obj.name else "unit"
                unit_counters[player.name][unit_type] += 1
                count = unit_counters[player.name][unit_type]
                unit_name_map[obj.instance_id] = f"{unit_type}_{player.name}_{count}"

    # Build data structure
    data = {
        "match": {
            "map_name": match.map.name
            if hasattr(match.map, "name")
            else str(match.map),
            "map_size": 220,
            "duration_seconds": match_duration,
            "duration_formatted": str(match.duration).split(".")[0],
        },
        "players": [],
        "starting_units": [],
        "actions": [],
        "walls": [],
        "unit_deaths": {},
    }

    # Add players
    for player in match.players:
        color = PLAYER_COLORS.get(
            player.color_id, {"name": "Unknown", "hex": "#FFFFFF"}
        )
        data["players"].append(
            {
                "name": player.name,
                "color_id": player.color_id,
                "color_hex": color["hex"],
                "color_name": color["name"],
                "civilization": player.civilization
                if hasattr(player, "civilization")
                else "",
            }
        )

    # Add starting units
    for player in match.players:
        if player.objects:
            for obj in player.objects:
                unit_name = unit_name_map.get(
                    obj.instance_id, f"unit_{obj.instance_id}"
                )
                raw_type = obj.name.lower().replace(" ", "") if obj.name else "unit"
                unit_class = classify_unit_type(raw_type)

                start_x, start_y = None, None
                for action in match.actions:
                    if not action.player:
                        continue
                    payload = action.payload or {}
                    if obj.instance_id in payload.get("object_ids", []):
                        if hasattr(action, "position") and action.position:
                            start_x = action.position.x
                            start_y = action.position.y
                            break

                data["starting_units"].append(
                    {
                        "id": unit_name,
                        "instance_id": obj.instance_id,
                        "player": player.name,
                        "type": unit_class,
                        "x": start_x,
                        "y": start_y,
                    }
                )

    # Process actions
    action_id = 0
    for action in match.actions:
        if not action.player:
            continue

        action_id += 1
        action_type = str(action.type).replace("Action.", "")
        payload = action.payload or {}
        pos = action.position if hasattr(action, "position") else None

        unit_ids = payload.get("object_ids", [])
        subject_names = []

        for obj_id in unit_ids:
            if obj_id not in unit_name_map:
                owner = unit_owner_map.get(obj_id, action.player.name)
                first_seen = unit_first_seen.get(
                    obj_id, action.timestamp.total_seconds()
                )

                # Determine unit type
                if obj_id in villager_ids:
                    unit_type = "villager"
                elif obj_id in starting_obj_ids:
                    # This shouldn't happen as starting units are already named
                    unit_type = "unit"
                else:
                    # Find the best matching UNUSED training event for this player
                    # Training takes time, so we look for events where:
                    # queue_time < first_seen (unit was queued before it appeared)
                    # We pick the most recent unused training event before first_seen
                    unit_type = "unit"
                    player_queue = training_queue.get(owner, [])
                    best_match = None
                    best_time = -1
                    for te in player_queue:
                        if te["used"]:
                            continue
                        # Training event must be before unit first appeared
                        if te["time"] < first_seen:
                            # Pick the most recent one (closest to first_seen)
                            if te["time"] > best_time:
                                best_time = te["time"]
                                best_match = te

                    if best_match:
                        unit_type = best_match["unit_type"]
                        best_match["used"] = True

                unit_counters[owner][unit_type] += 1
                count = unit_counters[owner][unit_type]
                unit_name_map[obj_id] = f"{unit_type}_{owner}_{count}"

            subject_names.append(unit_name_map[obj_id])

        target_name = ""
        if action_type == "BUILD":
            building_id = payload.get("building_id", payload.get("building", ""))
            building_type = object_names.get(str(building_id), f"building{building_id}")
            target_name = building_type.lower().replace(" ", "")
        elif action_type == "DE_QUEUE":
            unit_type = payload.get("unit", "unit")
            target_name = unit_type.lower().replace(" ", "")
        elif action_type == "RESEARCH":
            tech = payload.get("technology", payload.get("tech_id", ""))
            target_name = str(tech).lower().replace(" ", "")

        data["actions"].append(
            {
                "id": action_id,
                "time": action.timestamp.total_seconds(),
                "player": action.player.name,
                "type": action_type,
                "subjects": subject_names,
                "target": target_name,
                "x": pos.x if pos else None,
                "y": pos.y if pos else None,
                "amount": payload.get("amount"),
            }
        )

        # Capture wall placements
        if action_type == "WALL":
            wall_type = payload.get("building", "Palisade Wall")
            building_id = payload.get("building_id", 72)
            x_start = pos.x if pos else None
            y_start = pos.y if pos else None
            x_end = payload.get("x_end", x_start)
            y_end = payload.get("y_end", y_start)

            if x_start is not None and y_start is not None:
                data["walls"].append(
                    {
                        "time": action.timestamp.total_seconds(),
                        "player": action.player.name,
                        "type": wall_type.lower().replace(" ", ""),
                        "building_id": building_id,
                        "x_start": x_start,
                        "y_start": y_start,
                        "x_end": x_end,
                        "y_end": y_end,
                    }
                )

    # Calculate unit deaths
    for obj_id, actions in unit_actions.items():
        if not actions:
            continue

        unit_name = unit_name_map.get(obj_id)
        if not unit_name:
            continue

        if obj_id in villager_ids:
            continue

        last_time = actions[-1]["time"]
        if match_duration - last_time > DEATH_THRESHOLD:
            death_time = last_time + DEATH_THRESHOLD
            data["unit_deaths"][unit_name] = death_time

    return data


@app.route("/")
def index():
    return send_from_directory("public", "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory("public", path)


@app.route("/api/upload", methods=["POST"])
def upload_replay():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not file.filename.endswith(".aoe2record"):
        return jsonify(
            {"error": "Invalid file type. Please upload a .aoe2record file"}
        ), 400

    try:
        # Save to temp file since mgz needs a proper file handle
        with tempfile.NamedTemporaryFile(suffix=".aoe2record", delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                data = process_replay(f)
            return jsonify(data)
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to process replay: {str(e)}"}), 500


@app.route("/api/default", methods=["GET"])
def get_default_replay():
    """Return the default replay_data.json if it exists."""
    try:
        with open("replay_data.json", "r") as f:
            return jsonify(json.load(f))
    except FileNotFoundError:
        return jsonify({"error": "No default replay data found"}), 404


@app.route("/api/matches", methods=["GET"])
def get_matches():
    """Fetch recent Land Nomad matches from all players in the CSV."""
    try:
        # Load players from CSV
        players = load_players_from_csv()
        if not players:
            return jsonify({"error": "No players found in players.csv"}), 404

        # Get all profile IDs
        profile_ids = [p["profileId"] for p in players]

        # Fetch matches for all players (API accepts comma-separated profile_ids)
        all_matches = {}
        matches_url = f"{AOE2_COMPANION_API}/matches"

        # Fetch in batches to avoid URL length limits
        batch_size = 10
        for i in range(0, len(profile_ids), batch_size):
            batch_ids = profile_ids[i : i + batch_size]
            matches_resp = requests.get(
                matches_url,
                params={"profile_ids": ",".join(map(str, batch_ids)), "perPage": 50},
                headers=AOE2_COMPANION_HEADERS,
                timeout=30,
            )
            matches_data = matches_resp.json()

            # Deduplicate by match ID and filter for Land Nomad
            for match in matches_data.get("matches", []):
                match_id = match.get("matchId")
                map_name = match.get("mapName", "").lower()

                # Only include Land Nomad maps
                if "land nomad" not in map_name:
                    continue

                if match_id and match_id not in all_matches:
                    all_matches[match_id] = match

        # Sort by start time (newest first) and take top 25
        sorted_matches = sorted(
            all_matches.values(),
            key=lambda x: x.get("started", ""),
            reverse=True,
        )[:25]

        return jsonify(
            {
                "players": players,
                "matches": sorted_matches,
            }
        )

    except requests.RequestException as e:
        return jsonify({"error": f"Failed to fetch matches: {str(e)}"}), 500
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Error: {str(e)}"}), 500


@app.route("/api/matches/<player_name>", methods=["GET"])
def get_matches_for_player(player_name):
    """Fetch recent matches for a specific player from AoE2 Companion API."""
    try:
        # First, search for the player to get their profile ID
        search_url = f"{AOE2_COMPANION_API}/profiles"
        search_resp = requests.get(
            search_url,
            params={"search": player_name},
            headers=AOE2_COMPANION_HEADERS,
            timeout=15,
        )
        search_data = search_resp.json()

        profiles = search_data.get("profiles", [])
        if not profiles:
            return jsonify({"error": f"Player '{player_name}' not found"}), 404

        # Find exact match or use first result
        profile = None
        for p in profiles:
            if p.get("name", "").lower() == player_name.lower():
                profile = p
                break
        if not profile:
            profile = profiles[0]

        profile_id = profile.get("profileId")

        # Fetch recent matches
        matches_url = f"{AOE2_COMPANION_API}/matches"
        matches_resp = requests.get(
            matches_url,
            params={"profile_ids": profile_id, "perPage": 10},
            headers=AOE2_COMPANION_HEADERS,
            timeout=15,
        )
        matches_data = matches_resp.json()

        return jsonify(
            {
                "player": {
                    "profileId": profile_id,
                    "name": profile.get("name"),
                    "country": profile.get("country"),
                    "games": profile.get("games"),
                },
                "matches": matches_data.get("matches", []),
            }
        )

    except requests.RequestException as e:
        return jsonify({"error": f"Failed to fetch matches: {str(e)}"}), 500
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Error: {str(e)}"}), 500


@app.route("/api/load-match", methods=["POST"])
def load_match():
    """Download replay from aoe.ms, unzip, parse, and return replay data."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400

    match_id = data.get("matchId")
    profile_id = data.get("profileId")

    if not match_id or not profile_id:
        return jsonify({"error": "matchId and profileId are required"}), 400

    try:
        # Download replay ZIP from aoe.ms
        download_url = (
            f"{REPLAY_DOWNLOAD_URL}/?gameId={match_id}&profileId={profile_id}"
        )
        app.logger.info(f"Downloading replay from: {download_url}")

        resp = requests.get(
            download_url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=60,
            stream=True,
        )

        if resp.status_code != 200:
            return jsonify(
                {"error": f"Failed to download replay: HTTP {resp.status_code}"}
            ), 500

        # Read ZIP content
        zip_content = resp.content
        app.logger.info(f"Downloaded {len(zip_content)} bytes")

        # Extract .aoe2record from ZIP
        with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
            # Find the .aoe2record file in the ZIP
            record_file = None
            for name in zf.namelist():
                if name.endswith(".aoe2record"):
                    record_file = name
                    break

            if not record_file:
                return jsonify({"error": "No .aoe2record file found in ZIP"}), 500

            app.logger.info(f"Extracting: {record_file}")

            # Extract to temp file and process
            with tempfile.NamedTemporaryFile(suffix=".aoe2record", delete=False) as tmp:
                tmp.write(zf.read(record_file))
                tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                replay_data = process_replay(f)

            # Add match metadata
            replay_data["source"] = {
                "matchId": match_id,
                "profileId": profile_id,
                "downloadUrl": download_url,
            }

            return jsonify(replay_data)
        finally:
            os.unlink(tmp_path)

    except requests.RequestException as e:
        return jsonify({"error": f"Failed to download replay: {str(e)}"}), 500
    except zipfile.BadZipFile:
        return jsonify({"error": "Downloaded file is not a valid ZIP"}), 500
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to process replay: {str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    print("Starting AoE2 Replay Visualizer server...")
    print(f"Open http://localhost:{port} in your browser")
    app.run(debug=debug, host="0.0.0.0", port=port)

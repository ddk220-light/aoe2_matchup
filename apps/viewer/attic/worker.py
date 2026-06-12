"""
Cloudflare Worker for AoE2 Replay Visualizer.
Handles file uploads and processes replay files using mgz.
"""

import io
import json
from collections import defaultdict

import mgz
import mgz.model
from js import Headers, Object, Response

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

MONK_UNITS = {"monk", "missionary", "imam", "warrior priest"}

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

    if "villager" in name_lower:
        return "villager"
    if "scout" in name_lower:
        return "cavalry"
    if "king" in name_lower:
        return "king"

    return "military"


def process_replay(replay_bytes):
    """Process a replay file and return JSON data."""
    replay_file = io.BytesIO(replay_bytes)
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

    # Track actions per unit
    unit_actions = defaultdict(list)
    for action in match.actions:
        if not action.player:
            continue
        payload = action.payload or {}
        if "object_ids" in payload:
            for obj_id in payload["object_ids"]:
                unit_actions[obj_id].append(
                    {
                        "time": action.timestamp.total_seconds(),
                        "type": str(action.type).replace("Action.", ""),
                    }
                )

    # Determine villagers
    villager_ids = set()
    for obj_id, actions in unit_actions.items():
        if any(a["type"] == "BUILD" for a in actions):
            villager_ids.add(obj_id)

    # Build unit names
    unit_name_map = {}
    unit_counters = defaultdict(lambda: defaultdict(int))

    # Training events
    training_events = []
    for action in match.actions:
        if not action.player:
            continue
        action_type = str(action.type).replace("Action.", "")
        if action_type == "DE_QUEUE" and action.payload:
            unit_type_name = action.payload.get("unit", "unit")
            training_events.append(
                {
                    "time": action.timestamp.total_seconds(),
                    "player": action.player.name,
                    "unit_type": unit_type_name.lower().replace(" ", ""),
                }
            )

    # Name starting units
    for player in match.players:
        if player.objects:
            for obj in player.objects:
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

                if obj_id in villager_ids:
                    unit_type = "villager"
                else:
                    first_seen = None
                    for a in unit_actions.get(obj_id, []):
                        first_seen = a["time"]
                        break

                    unit_type = "unit"
                    if first_seen:
                        for te in reversed(training_events):
                            if te["player"] == owner and te["time"] < first_seen:
                                unit_type = te["unit_type"]
                                break

                unit_counters[owner][unit_type] += 1
                count = unit_counters[owner][unit_type]
                unit_name_map[obj_id] = f"{unit_type}_{owner}_{count}"

            subject_names.append(unit_name_map[obj_id])

        target_name = ""
        if action_type == "BUILD":
            building_id = payload.get("building_id", payload.get("building", ""))
            target_name = f"building{building_id}"
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


def json_response(data, status=200):
    """Create a JSON response."""
    headers = Headers.new(
        {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}.items()
    )
    return Response.new(json.dumps(data), status=status, headers=headers)


async def on_fetch(request, env):
    """Handle incoming requests."""
    url = request.url
    method = request.method

    # Handle CORS preflight
    if method == "OPTIONS":
        headers = Headers.new(
            {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            }.items()
        )
        return Response.new("", status=204, headers=headers)

    # Parse URL path
    path = url.split("//")[1].split("/", 1)
    path = "/" + path[1] if len(path) > 1 else "/"

    # Remove query string
    path = path.split("?")[0]

    # API routes
    if path == "/api/upload" and method == "POST":
        try:
            # Get the form data
            form_data = await request.formData()
            file = form_data.get("file")

            if not file:
                return json_response({"error": "No file provided"}, 400)

            # Read file bytes
            file_bytes = await file.arrayBuffer()
            file_bytes = bytes(file_bytes)

            # Process the replay
            data = process_replay(file_bytes)
            return json_response(data)

        except Exception as e:
            return json_response({"error": f"Failed to process replay: {str(e)}"}, 500)

    # Let Cloudflare handle static assets
    return env.ASSETS.fetch(request)

"""Make a geometry-locked winter foundation for visual editing in AoE2.

The Golden remains read-only. Trees are reskinned in place, never scattered.
Only the two deep-forest clearings may lose trees. Final props are placed in
the editor, inside these clearings and away from the unchanged forest edge.
"""
import contextlib
import hashlib
import io
import json
from pathlib import Path

from AoE2ScenarioParser.datasets.other import OtherInfo
from AoE2ScenarioParser.datasets.terrains import TerrainId
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "apps/video/templates/lab_goldens/melee_vs_ranged.aoe2scenario"
OUT = Path(__file__).resolve().parent
TARGET = OUT / "Northern Winter - fixed footprint.aoe2scenario"
TREE_IDS = {item.ID for item in OtherInfo if item.name.startswith("TREE_")}
CLEARINGS = {(2, 3), (3, 3), (2, 4), (3, 4), (11, 12), (12, 12), (11, 13), (12, 13)}


def unit_signature(scenario, players):
    return sorted((player, u.reference_id, u.unit_const, u.x, u.y, u.z,
                   u.rotation, u.garrisoned_in_id)
                  for player in players for u in scenario.unit_manager.units[player])


with contextlib.redirect_stdout(io.StringIO()):
    scene = AoE2DEScenario.from_file(str(SOURCE))
source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
army_before = unit_signature(scene, range(1, 9))
original_trees = {(u.x, u.y): u.unit_const for u in scene.unit_manager.units[0] if u.unit_const in TREE_IDS}
original_heights = [t.elevation for t in scene.map_manager.terrain]
removed = []
for unit in list(scene.unit_manager.units[0]):
    if unit.unit_const not in TREE_IDS:
        continue
    cell = int(unit.x), int(unit.y)
    if cell in CLEARINGS:
        removed.append((unit.x, unit.y))
        scene.unit_manager.remove_unit(unit=unit)
        continue
    x, y = cell
    # Small irregular groups of broadleaf and bare trees break up the conifers.
    if (x <= 6 and 1 <= y <= 2) or (x >= 13 and 8 <= y <= 10):
        unit.unit_const = OtherInfo.TREE_OAK_AUTUMN_SNOW.ID
    elif (x, y) in {(1, 5), (4, 3), (6, 2), (10, 13), (13, 12), (14, 10)}:
        unit.unit_const = OtherInfo.TREE_DEAD.ID
    elif (x * 7 + y * 11) % 11 == 0 and 2 < x + y < 28:
        unit.unit_const = OtherInfo.TREE_PINE_FOREST.ID
    else:
        unit.unit_const = OtherInfo.TREE_SNOW_PINE.ID

for tile in scene.map_manager.terrain:
    cell = tile.x, tile.y
    if (tile.x + .5, tile.y + .5) in original_trees:
        tile.terrain_id = int(TerrainId.UNDERBRUSH_SNOW if (tile.x * 5 + tile.y) % 4 == 0 else TerrainId.SNOW_STRONG)
    else:
        tile.terrain_id = int(TerrainId.SNOW_SOFT)
    if cell in CLEARINGS:
        tile.terrain_id = int(TerrainId.SNOW_LIGHT)

with contextlib.redirect_stdout(io.StringIO()):
    scene.write_to_file(str(TARGET))
    checked = AoE2DEScenario.from_file(str(TARGET))
new_trees = {(u.x, u.y): u.unit_const for u in checked.unit_manager.units[0] if u.unit_const in TREE_IDS}
assert set(new_trees) <= set(original_trees), "A tree was added outside an original coordinate"
assert set(original_trees) - set(new_trees) == set(removed)
assert unit_signature(checked, range(1, 9)) == army_before
assert [t.elevation for t in checked.map_manager.terrain] == original_heights
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash
report = {
    "source": str(SOURCE), "sourceSha256": source_hash,
    "foundation": str(TARGET), "originalTreeCount": len(original_trees),
    "winterTreeCount": len(new_trees), "addedTreeCoordinates": [],
    "removedInteriorTreeCoordinates": removed,
    "combatAndUtilityUnitsUnchanged": True, "elevationsUnchanged": True,
    "note": "Foundation audit before editor detailing. No trees may be added in the editor. Props belong only inside the two enclosed clearings."
}
(OUT / "winter-footprint-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))

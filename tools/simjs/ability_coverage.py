"""Which JS-engine abilities does the golden panel actually exercise?

The parity gate can only catch a regression in a mechanic that some unit in the panel
carries. This cross-references aoe2x/dbgen/ability_registry.py (the single source of truth
for special-ability params) against golden/combat_dicts.json and reports any ability that
no captured unit exercises — i.e. a blind spot in the gate.

    python tools/simjs/ability_coverage.py             # audit the committed golden
    python tools/simjs/ability_coverage.py -v          # also list every carrier
    python tools/simjs/ability_coverage.py <dicts.json>

Exits non-zero if any JS ability is unexercised, so it can be used as a check.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from aoe2x.dbgen.ability_registry import ABILITIES, ENGINE_JS  # noqa: E402

args = [a for a in sys.argv[1:] if a != "-v"]
verbose = "-v" in sys.argv
dicts_path = Path(args[0]) if args else ROOT / "tools/simjs/golden/combat_dicts.json"
dicts = json.loads(dicts_path.read_text())

# A JS ability is one with at least one param that the JS engine implements AND that
# combat_unit_loader emits into the served combat dict (a param the dict never carries
# cannot be exercised by the panel no matter which unit is picked).
js_abilities = {}
for name, ab in ABILITIES.items():
    params = [p for p in ab.params if p.in_combat_dict and ENGINE_JS in ab.param_engines(p)]
    if params:
        js_abilities[name] = params


def active(val, default):
    """True if this param carries a non-neutral value (the unit really has the ability)."""
    if val is None:
        return False
    if isinstance(val, str):
        return val not in ("", "{}", "null")
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != (default if isinstance(default, (int, float)) else 0)
    return bool(val)


exercised, missing = {}, []
for name, params in sorted(js_abilities.items()):
    carriers = [
        key for key, cd in sorted(dicts.items())
        if any(active(cd.get(p.name), p.default) for p in params)
    ]
    (exercised.setdefault(name, carriers) if carriers else missing.append(name))

print(f"combat dicts          : {len(dicts)}  ({dicts_path})")
print(f"JS abilities declared : {len(js_abilities)}")
print(f"  exercised           : {len(exercised)}")
print(f"  NOT exercised       : {len(missing)}")
print()
for name, carriers in sorted(exercised.items()):
    shown = ", ".join(carriers[:3] if not verbose else carriers)
    print(f"  OK   {name:26s} ({len(carriers):2d}) {shown}")
for name in missing:
    print(f"  MISS {name:26s} params={[p.name for p in js_abilities[name]]}")

if missing:
    sys.exit(f"\n{len(missing)} JS ability/abilities unexercised — the parity gate is blind to them.")
print("\nall JS abilities exercised")

"""Spot-check civ_power_units.json against known expectations."""
import json
import sys

with open("civ_power_units.json") as f:
    data = json.load(f)

errors = []

# Check all 50 civs present
if len(data) != 50:
    errors.append(f"Expected 50 civs, got {len(data)}")

# Franks: paladin should be cavalry power unit, strength should be "strong" or "signature"
franks = data.get("Franks", {}).get("imperial", {})
if franks:
    cav = franks["power_units"].get("cavalry")
    if not cav or cav["unit_slug"] != "paladin":
        errors.append(f"Franks cavalry: expected paladin, got {cav}")
    elif cav["strength"] not in ("strong", "signature"):
        errors.append(f"Franks paladin strength: expected strong/signature, got {cav['strength']}")

# Britons: ranged should be a strong/signature unit
britons = data.get("Britons", {}).get("imperial", {})
if britons:
    ranged = britons["power_units"].get("ranged")
    if not ranged or ranged["strength"] not in ("strong", "signature"):
        errors.append(f"Britons ranged: expected strong/signature, got {ranged}")

# Meso civs have no stable line — cavalry=None is expected
MESO_CIVS = {"Aztecs", "Incas", "Mayans"}

# Every civ should have at least ranged and infantry; cavalry for non-Meso
for civ, civ_data in data.items():
    imp = civ_data.get("imperial", {})
    if not imp:
        errors.append(f"{civ}: missing imperial data")
        continue
    pu = imp.get("power_units", {})
    for role in ["ranged", "infantry"]:
        if pu.get(role) is None:
            errors.append(f"{civ}: missing {role} power unit")
    if civ not in MESO_CIVS and pu.get("cavalry") is None:
        errors.append(f"{civ}: missing cavalry power unit")

if errors:
    print("VALIDATION FAILED:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED")
    # Print a few examples
    for civ in ["Franks", "Britons", "Mongols", "Goths", "Spanish"]:
        imp = data[civ]["imperial"]
        profile = imp["strength_profile"]
        sigs = [r for r, s in profile.items() if s == "signature"]
        strongs = [r for r, s in profile.items() if s == "strong"]
        print(f"  {civ}: signature={sigs}, strong={strongs}")

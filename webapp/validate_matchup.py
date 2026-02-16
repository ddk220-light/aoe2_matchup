"""Validate matchup recommendation logic with known matchups."""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from best_units import get_matchup_recommendations

errors = []

# Franks vs Britons: Franks should recommend cavalry (to close on longbows)
result = get_matchup_recommendations("Franks", "Britons")
if "error" in result:
    errors.append(f"Franks vs Britons: {result['error']}")
else:
    comps = result["recommended_compositions"]
    if not comps:
        errors.append("Franks vs Britons: no compositions recommended")
    else:
        print(f"Franks vs Britons:")
        print(f"  Opponent strengths: {result['opponent_strengths']}")
        for c in comps:
            print(f"  Comp #{c['rank']}: {c['gold_unit']['unit_slug']} + {c.get('trash_unit', {}).get('unit_slug', 'none')}")
            print(f"    Scores: {c['scores']}")
            print(f"    Reasoning: {c['reasoning']}")

# Britons vs Franks: Britons should recommend ranged + anti-cav
result2 = get_matchup_recommendations("Britons", "Franks")
if "error" not in result2:
    print(f"\nBritons vs Franks:")
    print(f"  Opponent strengths: {result2['opponent_strengths']}")
    for c in result2["recommended_compositions"]:
        print(f"  Comp #{c['rank']}: {c['gold_unit']['unit_slug']} + {c.get('trash_unit', {}).get('unit_slug', 'none')}")
        print(f"    Reasoning: {c['reasoning']}")

# Goths vs Spanish: test a generic matchup
result3 = get_matchup_recommendations("Goths", "Spanish")
if "error" not in result3:
    print(f"\nGoths vs Spanish:")
    for c in result3["recommended_compositions"]:
        print(f"  Comp #{c['rank']}: {c['gold_unit']['unit_slug']} + {c.get('trash_unit', {}).get('unit_slug', 'none')}")

if errors:
    print(f"\nERRORS: {errors}")
    sys.exit(1)
else:
    print("\nALL MATCHUP CHECKS PASSED")

# Conversational Matchup Advisor — Design Document

**Date:** 2026-02-16
**Status:** Approved

## Problem

The current matchup advisor shows one best unit per role in a grid. It doesn't explain *why* a civ is strong or weak, what strategic options it has, or what makes individual units special. Users can't understand the big picture of a civ's identity.

## Solution

Transform the matchup advisor into a **single-civ conversational analysis** that narrates each unit category's strength, highlights signature units, shows what techs/bonuses make units special (or what's missing), and provides a strategic summary.

## Approach

**Backend analysis + Frontend narrative templates (Approach B)**

- `best_units.py` computes all units per role with scores, missing techs, bonus abilities, and analysis metadata (narrative_key, above_avg_count, etc.)
- Frontend JS uses `narrative_key` to select from template strings, renders unit names as hoverable interactive elements with rich tooltips
- All data pre-computed in `civ_power_units.json` — no extra API calls at render time

---

## Data Model

### Expanded `civ_power_units.json` structure

```json
{
  "Franks": {
    "imperial": {
      "power_units": {
        "cavalry": {
          "narrative_key": "cav_all_strong",
          "above_avg_count": 2,
          "total_count": 2,
          "has_signature": true,
          "best_unit": "paladin",
          "all_units": [
            {
              "unit_slug": "paladin",
              "unit_name": "Paladin",
              "line_slug": "stable",
              "score": 85.3,
              "rank": 3,
              "median_delta": 25.1,
              "strength": "signature",
              "speed": 1.5,
              "missing_techs": [],
              "bonus_abilities": ["Cavalry +20% HP"],
              "special_effects": []
            },
            {
              "unit_slug": "hussar",
              "unit_name": "Hussar",
              "line_slug": "stable",
              "score": 42.1,
              "rank": 28,
              "median_delta": -3.2,
              "strength": "average",
              "speed": 1.5,
              "missing_techs": ["Bloodlines"],
              "bonus_abilities": [],
              "special_effects": []
            }
          ]
        },
        "ranged": { "..." : "same structure" },
        "infantry": { "..." : "same structure" },
        "anti_cavalry": { "..." : "same structure" },
        "trash": { "..." : "same structure" },
        "siege": { "..." : "same structure" }
      },
      "strength_profile": {
        "cavalry": "signature",
        "ranged": "weak",
        "infantry": "average",
        "anti_cavalry": "average",
        "trash": "average",
        "siege": "strong"
      },
      "strategic_summary": {
        "strong_areas": ["cavalry"],
        "weak_areas": ["ranged"],
        "signature_areas": ["cavalry"],
        "summary_key": "one_area_strong",
        "primary_strength": "cavalry"
      }
    }
  }
}
```

### Narrative keys

**Cavalry:**
| Key | Condition |
|-----|-----------|
| `cav_all_strong` | All cav units have median_delta > 0 |
| `cav_one_strong` | Exactly 1 cav unit has median_delta > 0 |
| `cav_strong_slow` | Best cav speed <= 1.35 AND has strong/signature cav |
| `cav_trash_only` | Only scout line (hussar/light_cavalry) is above average |
| `cav_none` | No cav unit has median_delta > 0 |

**Ranged:**
| Key | Condition |
|-----|-----------|
| `ranged_strong` | 2+ above-avg ranged units |
| `ranged_one_strong` | Exactly 1 above-avg ranged unit |
| `ranged_none` | No above-avg ranged |

**Infantry:**
| Key | Condition |
|-----|-----------|
| `inf_strong` | 2+ above-avg infantry units |
| `inf_one_strong` | Exactly 1 above-avg infantry unit |
| `inf_none` | No above-avg infantry |

**Anti-Cavalry (uses `anti_cav_value`, NOT overall effectiveness):**
| Key | Condition |
|-----|-----------|
| `anticav_strong` | Above-avg anti-cav options |
| `anticav_one_strong` | One standout anti-cav unit |
| `anticav_weak` | No above-avg anti-cav |

**Trash:**
| Key | Condition |
|-----|-----------|
| `trash_strong` | Above-avg trash unit |
| `trash_weak` | Below-avg trash |

**Siege:**
| Key | Condition |
|-----|-----------|
| `siege_strong` | Above-avg siege |
| `siege_one_strong` | One standout siege unit |
| `siege_weak` | Below-avg siege |

**Strategic Summary:**
| Key | Condition |
|-----|-----------|
| `multi_flexible` | 3+ roles with strong/signature strength_profile |
| `one_area_strong` | 1-2 roles strong/signature |
| `none_exceptional` | No role is strong or signature |

### Thresholds

- **Above average:** median_delta > 0
- **Slow cavalry:** speed <= 1.35 (Teuton Paladin)
- **Scout line:** unit_slug in ("hussar", "light_cavalry", "winged_hussar")
- **Strength tiers:** signature (rank<=5 AND delta>20), strong (delta>10), average, weak (delta<-10)

---

## Backend Logic (`best_units.py` changes)

### 1. Fetch all units per role (not just LIMIT 1)

Remove `LIMIT 1` from battle_scores query. Sort by median_delta DESC. Store all results in `all_units[]`.

### 2. Compute missing_techs per unit

For each unit line (e.g., stable), build **reference tech set** = the set of standard tech names that appear for ANY civ's version of that unit at that age. Standard means `tech_type='standard'` (excludes civ bonuses and unique techs).

Filter reference set to impactful techs only:
- Blacksmith: Forging, Iron casting, Blast Furnace, Scale/Chain/Plate Barding/Mail Armor, Fletching, Bodkin Arrow, Bracer, Padded/Leather/Ring Archer Armor
- Stable: Bloodlines, Husbandry
- Barracks: Squires, Arson, Gambesons
- Castle: Conscription
- University: Ballistics, Chemistry, Siege Engineers
- Other: Thumb Ring, Parthian Tactics

For each civ's unit: `missing_techs = impactful_reference_techs - civ_techs_applied`

### 3. Extract bonus_abilities per unit

From `ref_techs_applied`:
- Entries where `tech_name` starts with `"C-Bonus"` → strip `"C-Bonus, "` prefix → add to bonus_abilities
- Entries where tech_name contains `"UT"` → add to bonus_abilities

From `ref_special_effects` (where property_value != 0):
- `trample_percent` → "Trample {v}%"
- `ignores_melee_armor` → "Ignores melee armor"
- `ignores_pierce_armor` → "Ignores pierce armor"
- `bleed_dps` → "Bleed {v} dps"
- `dodge_shield_max` → "Dodge shield ({v} charges)"
- `block_first_melee` → "Blocks first melee hit"
- `hp_regen` → "+{v} HP/min regen"
- `charge_attack_melee` → "Charge +{v} melee"
- `attack_bonus_per_kill` → "+{v} attack per kill"
- `bonus_damage_reduction` → "{v}% bonus damage reduction"
- `splash_radius` → "Splash damage ({v} radius)"
- `extra_projectiles` → "+{v} extra projectiles"

### 4. Determine narrative_key per role

Run the condition checks in priority order (first match wins):

**Cavalry example:**
```python
scout_slugs = {"hussar", "light_cavalry", "winged_hussar"}
above_avg = [u for u in all_units if u["median_delta"] > 0]
above_avg_non_scout = [u for u in above_avg if u["unit_slug"] not in scout_slugs]
best = all_units[0] if all_units else None

if not above_avg:
    key = "cav_none"
elif above_avg and not above_avg_non_scout:
    key = "cav_trash_only"
elif best and best["speed"] <= 1.35 and best["median_delta"] > 0:
    key = "cav_strong_slow"
elif len(above_avg) == 1:
    key = "cav_one_strong"
else:
    key = "cav_all_strong"
```

### 5. Compute strategic_summary

```python
strong_roles = [r for r in roles if strength_profile[r] in ("strong", "signature")]
sig_roles = [r for r in roles if strength_profile[r] == "signature"]

if len(strong_roles) >= 3:
    summary_key = "multi_flexible"
elif strong_roles:
    summary_key = "one_area_strong"
    primary_strength = strong_roles[0]
else:
    summary_key = "none_exceptional"
```

---

## Frontend Design

### Page structure (single-civ analysis)

1. **Civ selector** — keep existing 50-civ grid
2. **Analysis container** — appears after selecting a civ:
   - Role sections in order: Cavalry, Ranged, Infantry, Anti-Cavalry, Trash, Siege
   - Each section: narrative paragraph + unit badges row
3. **Strategic summary** — bottom section

### Per-role section

```html
<div class="role-section">
  <h3 class="role-header">Cavalry</h3>
  <p class="role-narrative">
    <!-- Generated from narrative_key + unit names -->
    This civ has good cavalry, and can be a good option for mobility.
  </p>
  <div class="unit-badges">
    <!-- One badge per unit in all_units -->
    <div class="unit-badge signature">
      <img src="icon.svg" />
      <span class="unit-name">Paladin</span>
      <span class="rank-badge">#3</span>
      <!-- Tooltip on hover -->
    </div>
  </div>
</div>
```

### Narrative templates (frontend JS)

```javascript
const NARRATIVES = {
  cavalry: {
    cav_all_strong: "This civ has good cavalry, and can be a good option for mobility.",
    cav_one_strong: "This civ's mobility is centered around {best_unit}.",
    cav_strong_slow: "The cavalry is strong, but lacks mobility.",
    cav_trash_only: "Mobility is only available late game with trash units.",
    cav_none: "Cavalry line is not a strong suite for this civ.",
  },
  ranged: {
    ranged_strong: "This civ has strong ranged options, so pushing a single position can be very effective.",
    ranged_one_strong: "Ranged options are limited, but {best_unit} stands out.",
    ranged_none: "Ranged units are not a strength for this civ.",
  },
  infantry: {
    inf_strong: "This civ has strong infantry that can help push with siege.",
    inf_one_strong: "Infantry options center around {best_unit} for frontline pressure.",
    inf_none: "Infantry is not a strong area for this civ.",
  },
  anti_cavalry: {
    anticav_strong: "Strong anti-cavalry options give this civ tools to shut down enemy cavalry.",
    anticav_one_strong: "{best_unit} provides solid anti-cavalry capability.",
    anticav_weak: "Anti-cavalry is a weakness — be cautious against cavalry-heavy opponents.",
  },
  trash: {
    trash_strong: "Trash units are above average, giving staying power in long games.",
    trash_weak: "Trash units are below average — gold-heavy strategies may be needed.",
  },
  siege: {
    siege_strong: "Strong siege options for pushing fortified positions.",
    siege_one_strong: "{best_unit} is a notable siege option.",
    siege_weak: "Siege is not a strength — consider alternative push strategies.",
  },
};
```

### Hover tooltip

Shows ONLY special info (not basic stats):

```
┌─ Paladin (Franks) ──────────────┐
│ ✦ Cavalry +20% HP (civ bonus)  │
│ ✦ Bearded Axe (unique tech)     │
│                                  │
│ Rank #3 of 50 · +25.1 above avg │
└──────────────────────────────────┘
```

For weak units with missing techs:
```
┌─ Hussar (Franks) ───────────────┐
│ ✗ Missing: Bloodlines            │
│                                  │
│ Rank #28 of 50 · -3.2 vs avg    │
└──────────────────────────────────┘
```

### Signature unit highlighting

- Gold border + subtle glow (`box-shadow: 0 0 12px rgba(255,215,0,0.4)`)
- Star icon next to unit name
- Slightly larger badge than regular units

### Strategic summary section

```
"Franks is strongest in cavalry. Lean into knight rushes and use
cavalry mobility to raid and pressure. Support with siege for
pushing fortified positions."

Strengths: ● Cavalry  ● Siege
Weaknesses: ○ Ranged  ○ Anti-Cavalry
```

Summary templates:
- **multi_flexible:** "This civ is strong across {areas}, so it can pursue flexible strategies and adapt to any opponent."
- **one_area_strong:** "This civ is strongest in {primary_strength}, so it must leverage that advantage. {specific_advice}"
- **none_exceptional:** "This civ doesn't scale exceptionally in late game. Focus on doing early damage and maintaining a lead."

---

## Files Modified

| File | Change |
|------|--------|
| `webapp/best_units.py` | Expand `compute_civ_power_units()` to store all units, missing_techs, bonus_abilities, narrative_keys, strategic_summary |
| `webapp/civ_power_units.json` | Regenerated with expanded structure |
| `webapp/templates/matchup_advisor.html` | Single-civ analysis layout, remove 2-civ comparison |
| `webapp/static/js/matchup.js` | New rendering: narrative sections, unit badges, hover tooltips, strategic summary |
| `webapp/static/css/matchup.css` | Role sections, unit badges, signature highlighting, tooltip styling |
| `webapp/app.py` | No changes needed (endpoint already returns JSON from file) |

## What stays the same

- Scoring formulas/weights (NEVER changed without approval)
- `compute_battle_scores.py` — no changes
- Battle simulation engine — no changes
- Civ selector UI component
- Existing rankings pages and other views

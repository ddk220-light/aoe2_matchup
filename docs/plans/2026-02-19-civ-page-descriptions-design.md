# Civilization Page: Better Descriptions & Score-Based Categorization

**Date:** 2026-02-19

## Overview

Update the `/civilizations` page with:
1. Rich strategic descriptions generated from scoring data
2. Score-based categorization (top 25th percentile per role = "good")
3. Template renaming for clarity

## 1. Template Renaming

| Current | New | Serves |
|---------|-----|--------|
| `civ_detail.html` | `deprecated-civ.html` | `/civilizations/<civ_name>` |
| `matchup_advisor.html` | `civ_detail.html` | `/civilizations` |

Update `app.py` routes to reference the new template names.

## 2. Score-Based Categorization

**Current:** 4 tiers with fixed thresholds on `rank` and `median_delta`:
- signature: rank <= 5 AND median_delta > 20
- strong: median_delta > 10
- weak: median_delta < -10
- average: else

**New:** 3 tiers based on per-role 75th percentile of score:
- **signature**: score >= 75th percentile AND rank <= 5
- **good**: score >= 75th percentile (not signature)
- **average**: score < 75th percentile

Implementation in `best_units.py`:
1. Before classifying, collect all scores per role across all 50 civs
2. Compute 75th percentile threshold per role
3. Replace `_classify_strength(rank, median_delta)` with `_classify_strength(score, rank, role_threshold)`
4. Drop "weak" tier; remove "strong" naming in favor of "good"

## 3. Strategic Description (Rule-Based Paragraph)

Generated in `best_units.py`, stored as `strategic_description` in `civ_power_units.json`.

### Part 1: Primary Playstyle

Based on strongest role(s):

| Strongest Role | Example Language |
|---|---|
| Cavalry (fast) | "excels at mobile cavalry play -- able to raid, flank, and apply pressure across the map with {best_unit}" |
| Cavalry (slow) | "fields powerful but slower cavalry like {best_unit}, favoring head-on engagements over mobility" |
| Ranged | "has strong ranged options for concentrated pushes, with {best_unit} providing range advantage and sustained damage" |
| Infantry | "has strong infantry for frontline pressure, with {best_unit} serving as the backbone of siege-backed pushes" |
| Multiple strong | "is versatile, with strength across {areas} -- allowing flexible strategies" |
| None exceptional | "doesn't have a standout late-game powerhouse -- focus on early aggression" |

### Part 2: Defensive Assessment

Based on anti_cavalry + anti_archer strength:

| Anti-Cav | Anti-Archer | Language |
|---|---|---|
| strong | strong | "Defensively well-rounded, with solid options to shut down both cavalry and ranged threats." |
| strong | weak | "Can hold the line against cavalry, but vulnerable to massed archers." |
| weak | strong | "Good tools against ranged units, but lacks reliable anti-cavalry." |
| weak | weak | "Limited counter options -- must play aggressively and press its advantage." |

### Part 3: Push Strategy

Based on siege data + primary strength:

| Condition | Language |
|---|---|
| Strong infantry + strong ram | "An infantry ram push is the signature play -- use {infantry} as a meatshield to protect rams." |
| Strong ranged + strong treb | "Pushing behind trebuchets maximizes the ranged advantage." |
| Strong bombard cannon | "Bombard Cannons provide long-range siege power for breaking through fortifications." |
| Strong siege generally | "Solid siege options give flexibility in how to close out games." |
| Weak siege | "Siege options are limited -- look to win through open-field engagements." |

### Frontend

Replace the hero section (1-line summary + strength/weakness pills) with the generated paragraph. Keep per-role narratives inside each column.

## Data Flow

```
best_units.py
  -> compute per-role 75th percentile thresholds
  -> classify units as signature/good/average
  -> generate strategic_description paragraph
  -> save to civ_power_units.json

matchup.js (frontend)
  -> read strategic_description from JSON
  -> render in hero section (replacing old summary + pills)
  -> per-role narratives remain unchanged
```

## Files Changed

- `webapp/best_units.py` -- categorization + description generation
- `webapp/static/js/matchup.js` -- hero section rendering
- `webapp/templates/matchup_advisor.html` -- renamed to `civ_detail.html`
- `webapp/templates/civ_detail.html` -- renamed to `deprecated-civ.html`
- `webapp/app.py` -- template references

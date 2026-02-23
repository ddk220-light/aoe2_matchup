# Matchup Advisor Simulation Overlay — Design

**Goal:** Enhance the matchup advisor by running live combat simulations between every unit of two selected civs, showing which opponent units each unit beats as small icons below the percentile bar.

**Architecture:** New on-demand `POST /api/matchup-sims` endpoint runs ~650 simulations server-side (~0.8s). Frontend fetches this in the background after initial percentile comparison loads. Highlighted "exclusive wins" show where one civ's unit beats an opponent that the other civ's equivalent cannot.

---

## API Endpoint

**`POST /api/matchup-sims`**

Request:
```json
{ "civ_left": "Franks", "civ_right": "Saracens", "age": "imperial" }
```

Response — keyed by `{unit_slug}__{civ_name_lower}`:
```json
{
  "results": {
    "paladin__franks": {
      "wins": ["militia_line_saracens", "spear_line_saracens"],
      "highlighted": ["militia_line_saracens"]
    }
  }
}
```

### Win Logic

For each pair (unitA vs unitB):
1. Run `simulate_battle(A, B, fixed_count=30, return_hp=True)` → `hp_pct_A`
2. Run `simulate_battle(A, B, resources=3000, return_hp=True)` → `hp_pct_A`
3. **Win** = A has >10% HP remaining in BOTH modes
4. Otherwise → draw/loss (not shown)

### Highlight Logic (Exclusive Wins)

Per unit line (e.g., knight line):
- For each left-side unit `U_L`, collect its wins
- For each right-side unit `U_R` in the **same line**, collect its wins
- A win by `U_L` over opponent `X` is **highlighted** if no `U_R` in that line also beats `X`
- Meaning: "Frank Paladin beats Militia, but Saracen Cavalier doesn't → highlight Militia"
- Multi-unit lines (unique + generic): compare each unit independently

---

## Frontend Display

Below each unit's strength label, add a "Beats" row of small icons:

```
┌────────────────────────────────────┐
│ 🏰 Paladin              [Franks]  │
│ ████████████████████░░░  82%       │
│ Signature                          │
│ Beats: [icon][icon][icon*][icon]   │  ← NEW
└────────────────────────────────────┘
```

- Icons: 20px (smaller than 28px unit icons)
- Highlighted wins: gold ring/border
- Normal wins: subtle border
- No wins → row hidden
- Loading state: small spinner placeholder

---

## Data Flow

1. User selects two civs → `loadComparison()` fires
2. Fetch **percentile data** (existing `/api/civ-power-units/`) → render cards immediately
3. Fire **background `POST /api/matchup-sims`** → show spinner placeholders
4. Response arrives → populate "Beats" icon rows
5. Age toggle → re-fetch both percentile and sim data

---

## Scope

- **In scope:** New API endpoint, frontend beats row, highlight logic, loading state
- **Out of scope:** Tooltips on icons, click-to-simulate drill-down, caching across page loads

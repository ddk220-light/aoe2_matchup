# Matchup Advisor — Design Document

## Goal

Replace the "Coming Soon" matchup advisor page with a two-civ comparison tool. Users pick two civilizations and see a side-by-side breakdown of each unit line's percentile score, making it immediately clear where each civ is stronger or weaker.

## Architecture

**Frontend-only comparison.** Fetch `/api/civ-power-units/<civ>` for both civs, then render the comparison client-side. No new backend API needed — the existing endpoint already returns percentile, rank, strength tier, and stats per unit line per civ.

**Reuse patterns from Team Analysis and Civ Detail pages** — same civ picker grid, same strength color system, same icon helpers from `constants.js`.

## UI Flow

### Step 1: Civ Selection

Two-panel picker at the top:
- **Left panel** — "Your Civ" (gold accent, `--gold` border)
- **Right panel** — "Opponent" (blue accent, `--team2` border)
- Shared civ grid below both panels
- Click a civ → assigns to whichever side is "active" (left first, then right)
- Click a selected civ → deselects it
- Once both civs are selected, comparison loads automatically (no button needed)

### Step 2: Comparison View

**Age toggle** at the top: Imperial (default) / Castle.

**Four sections** — Cavalry, Ranged, Infantry, Siege — displayed as cards (like team analysis stage cards).

Each section contains **unit line rows**. Each row:

```
  Knight Line
  ┌─────────────────────────────────────────────────────┐
  │ [Emblem] Cavalier         │ [Emblem] Paladin        │
  │ ████████████░░░  72%      │ ██████████████░  92%     │
  │ Strong                    │ Signature                │
  ├───────────────────────────┴─────────────────────────┤
  │               ◄── Opponent leads                    │
  └─────────────────────────────────────────────────────┘
```

- **Percentile bar** (0–100%) colored by strength tier
- **Strength label** below bar (Signature / Strong / Average / Weak / Poor)
- **Unit name** with civ emblem
- **Winner indicator** — subtle arrow or highlight showing which side leads in this line
- **N/A** for lines a civ doesn't have (greyed out, no bar)

### Color Scheme (existing)

| Tier | Background | Text |
|------|-----------|------|
| Signature | `rgba(201, 168, 76, 0.2)` | `var(--gold)` |
| Strong | `rgba(46, 204, 113, 0.15)` | `#2ecc71` |
| Average | `rgba(255, 255, 255, 0.05)` | `var(--text-muted)` |
| Weak | `rgba(230, 126, 34, 0.15)` | `#e67e22` |
| Poor | `rgba(231, 76, 60, 0.15)` | `#e74c3c` |

## Data Source

`/api/civ-power-units/<civ_name>?age=imperial` returns:

```json
{
  "power_units": {
    "cavalry": {
      "knight": [{ "percentile": 72.0, "strength": "strong", "unit_name": "Cavalier", ... }],
      "camel": null,
      ...
    },
    ...
  }
}
```

Key fields per unit entry: `percentile`, `strength`, `unit_name`, `unit_slug`, `rank`, `score`, `stats`, `special_effects`, `missing_techs`.

## Files

| File | Action | Purpose |
|------|--------|---------|
| `webapp/templates/matchup_wip.html` | Replace | Full matchup advisor template |
| `webapp/static/js/matchup_advisor.js` | Create | Comparison logic + rendering |
| `webapp/static/css/matchup_advisor.css` | Create | Comparison-specific styles |
| `webapp/app.py` | Modify | Pass civs list to template |

## Unit Line Definitions

Reuse from civ detail page (`matchup.js`):

- **Cavalry:** light_cav, knight, camel, steppe_lancer, elephant
- **Ranged:** skirmisher, archer, cav_archer, gunpowder, scorpion
- **Infantry:** militia, spear, shock_infantry
- **Siege:** ram, bombard_cannon, trebuchet

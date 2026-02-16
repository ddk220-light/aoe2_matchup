# Team Analysis Expansion Design

Expand team analysis from cavalry-only to all four combat categories (cavalry, infantry, ranged, siege) with tabbed sub-category breakdowns.

## Decisions

- **Same-line only**: Each stage shows units from its own line(s). No cross-line mixing.
- **Tabs within card**: Sub-categories are tabs inside each stage card, not separate cards or expand/collapse.
- **Combined multi-line queries**: Infantry (militia+spear+shock_infantry) and ranged (archer+skirmisher+cav_archer+scorpion+gunpowder) query all their line_slugs together.
- **Approach A**: One API call per tab click. `TEAM_ANALYSIS_STAGES` defines tabs per stage.
- **Siege included**: Even with only 2 score types (anti_building_score, time_to_kill).

## Backend: TEAM_ANALYSIS_STAGES

```python
TEAM_ANALYSIS_STAGES = {
    "cavalry": {
        "line_slugs": ["stable"],
        "tabs": OrderedDict([
            ("overall",        {"score_type": "stable_effectiveness", "label": "Overall"}),
            ("general_combat", {"score_type": "general_combat",       "label": "General Combat"}),
            ("anti_cav",       {"score_type": "anti_cav",             "label": "Anti-Cav"}),
        ])
    },
    "infantry": {
        "line_slugs": ["militia", "spear", "shock_infantry"],
        "tabs": OrderedDict([
            ("overall",        {"score_type": "militia_value",    "label": "Overall"}),
            ("general_combat", {"score_type": "general_combat",   "label": "General Combat"}),
            ("anti_cav",       {"score_type": "anti_cav",         "label": "Anti-Cav"}),
            ("raiding",        {"score_type": "raiding_value",    "label": "Raiding"}),
        ])
    },
    "ranged": {
        "line_slugs": ["archer", "skirmisher", "cav_archer", "scorpion", "gunpowder"],
        "tabs": OrderedDict([
            ("overall",        {"score_type": "ranged_effectiveness", "label": "Overall"}),
            ("general_combat", {"score_type": "general_combat",       "label": "General Combat"}),
            ("anti_archer",    {"score_type": "anti_archer",          "label": "Anti-Archer"}),
            ("mobility",       {"score_type": "mobility_score",       "label": "Mobility"}),
        ])
    },
    "siege": {
        "line_slugs": ["siege"],
        "tabs": OrderedDict([
            ("overall",        {"score_type": "anti_building_score", "label": "Overall"}),
            ("time_to_kill",   {"score_type": "time_to_kill",        "label": "Time to Kill"}),
        ])
    },
}
```

## API Changes

Endpoint: `GET /api/team-analysis?team1=...&team2=...&stage=cavalry&tab=overall&age=Imperial`

New `tab` parameter (default: `"overall"`). Validated against stage's tab keys.

SQL changes: `WHERE line_slug IN (?, ?, ...)` instead of `= ?` for multi-line stages.

Response adds:
- `tab`: active tab key
- `tab_label`: human-readable tab name
- `available_tabs`: list of `{key, label}` for the stage's tab bar

## Frontend

### Stage Cards
On "Analyze", fetch all 4 stages in parallel (overall tab each). Render 4 stage cards top-to-bottom: Cavalry, Infantry, Ranged, Siege.

### Tab Bar
Each stage card has a horizontal tab bar below the header. Tabs sourced from `available_tabs` in API response. Active tab highlighted. Clicking a tab fetches that stage+tab and re-renders the card body.

### Card Body
Same as current: two columns (Team 1 red, Team 2 blue), above-median units sorted by score DESC, footer showing civs with no above-median units.

## Files Changed

| File | Change |
|------|--------|
| `webapp/app.py` | Expand `TEAM_ANALYSIS_STAGES`, update endpoint for `tab` param + multi-line queries |
| `webapp/static/js/team_analysis.js` | Fetch 4 stages, build tab bars, handle tab clicks |
| `webapp/static/css/team_analysis.css` | Tab bar styles |
| Database | No changes needed |

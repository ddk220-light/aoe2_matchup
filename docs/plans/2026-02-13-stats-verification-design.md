# Stats Verification via Parallel Sub-Agents

## Goal
Verify all unique unit stats in our database against the AoE2 Fandom Wiki using massively parallel sub-agents (one per unit).

## Scope
- **Units:** Unique units only (~85 including elite variants)
- **Stats:** All 79 columns in `unit_stats`
- **Source:** `ageofempires.fandom.com/wiki/{Unit_Name}`

## Architecture

```
Phase 1 (Setup)           Phase 2 (Parallel)              Phase 3 (Analysis)
┌──────────────┐     ┌─────────────────────────┐     ┌──────────────────┐
│ DB Query      │     │ Agent: Mangudai          │     │                  │
│ Agent         │     │ Agent: Chu Ko Nu          │     │ Aggregation &    │
│               │────>│ Agent: Longbowman         │────>│ Discrepancy      │
│ Returns list  │     │ Agent: Cataphract          │     │ Report           │
│ of all unique │     │ ... (~85 agents)          │     │                  │
│ unit stats    │     │                           │     │                  │
└──────────────┘     │ Each: fetch wiki > compare │     └──────────────────┘
                     └─────────────────────────────┘
```

### Phase 1: Database Extraction
- 1 agent (general-purpose) queries SQLite DB at `webapp/aoe2_units.db`
- Extracts all unique unit records with full stats (all 79 columns)
- Returns structured list of `{unit_name, slug, stats_dict}`

### Phase 2: Parallel Wiki Verification
- ~85 agents launched simultaneously (general-purpose, haiku model)
- Each agent receives: unit name, our DB stats, wiki URL
- Each agent: fetches wiki page via WebFetch, extracts stats, compares to DB values
- Each returns: `{unit_name, wiki_url, status, discrepancies[], notes}`
- Status values: `match`, `discrepancy`, `fetch_failed`
- Agents run in background (`run_in_background: true`)

### Phase 3: Aggregation
- Read all background agent output files
- Compile final report: matches, discrepancies, fetch failures
- Save to `docs/stats-verification-report.md`

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent model | haiku for Phase 2 | Cheaper, faster for extract-and-compare |
| Background mode | Yes for Phase 2 | Don't block main conversation |
| Wiki URL pattern | `ageofempires.fandom.com/wiki/{Name}` | Standard, spaces to underscores |
| Stats comparison | Numeric tolerance +/-0.01 | Ignore floating point noise |
| Elite handling | Separate agents per variant | Each needs distinct DB comparison |

## Risk Mitigations
- Rate limiting: log failures, retry later
- Wiki format variance: flexible extraction prompt
- Name mismatches: include alternate name patterns (e.g., "Ratha (Melee)" vs "Ratha")
- Unverifiable fields: distinguish "not found on wiki" from "discrepancy"

## Output
Markdown report with:
1. Summary counts (matches, discrepancies, failures)
2. Discrepancy table: unit | field | our_value | wiki_value
3. Missing data: fields not found on wiki
4. Failed fetches: units that couldn't be loaded

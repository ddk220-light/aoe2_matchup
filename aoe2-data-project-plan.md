# AoE2 Game Data Extraction & API Project

## Project Overview

Extract complete unit, technology, civilization, and game mechanics data from Age of Empires II: Definitive Edition's `.dat` files and make it accessible through multiple channels: downloadable JSON files, a REST API, and an MCP (Model Context Protocol) server.

### Goals

1. **Accuracy**: Parse directly from game files to ensure data matches the current game version
2. **Completeness**: Include all unit stats, armor classes, attack bonuses, civ bonuses, and tech effects
3. **Accessibility**: Provide multiple access methods for different use cases
4. **Maintainability**: Automate updates when new game patches are released
5. **Compute-Ready**: Architecture supports future compute workloads (unit simulations, army optimization)

### Scope Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API Authentication | Public (no auth) | Maximize accessibility, reassess if abused |
| Version History | Latest patch only | Simplifies storage and queries |
| Localization | English only | Reduces complexity, expand later if needed |
| Game Content | Ranked civs only | No Return of Rome, focus on competitive play |

---

## Data Sources

### Primary Source: `empires2_x2_p1.dat`

Location: `<AoE2DE Install>/resources/_common/dat/empires2_x2_p1.dat`

This binary file contains all game data and is the authoritative source used by:
- Advanced Genie Editor (the official modding tool)
- aoe2techtree.net (Siege Engineers)
- All data mod creators

### Parsing Library: `genieutils-py`

- **Repository**: https://github.com/SiegeEngineers/genieutils-py
- **PyPI**: `pip install genieutils-py`
- **Maintainer**: Siege Engineers (trusted AoE2 community organization)
- **Supports**: AoE2:DE file versions 7.7+ (GV_C20 and above)

---

## Data Model

### Core Entities

#### 1. Units
```json
{
  "id": 4,
  "name": "Archer",
  "internal_name": "ARCHR",
  "class": 0,
  "hit_points": 30,
  "speed": 0.96,
  "line_of_sight": 6,
  "garrison_capacity": 0,
  "cost": {
    "wood": 25,
    "gold": 45
  },
  "train_time": 35,
  "attacks": [
    {"class": 3, "amount": 4},
    {"class": 27, "amount": 3}
  ],
  "armors": [
    {"class": 3, "amount": 0},
    {"class": 4, "amount": 0},
    {"class": 15, "amount": 0},
    {"class": 27, "amount": 0}
  ],
  "range": 4,
  "accuracy": 80,
  "reload_time": 2.0,
  "projectile_speed": 7.0,
  "created_at_building": 87,
  "upgrade_from": null,
  "upgrade_to": 24
}
```

#### 2. Armor/Attack Classes
```json
{
  "id": 4,
  "name": "Base Pierce",
  "description": "Standard ranged attack class"
}
```

Known classes include:
- 1: Infantry
- 2: Turtle Ships
- 3: Base Pierce
- 4: Base Melee
- 5: War Elephants
- 8: Cavalry
- 11: All Buildings
- 13: Stone Defense
- 15: Archers
- 16: Ships
- 17: Rams
- 19: Trees
- 20: Unique Units
- 21: Siege Weapons
- 22: Standard Buildings
- 23: Walls & Gates
- 24: Gunpowder Units
- 25: Boars
- 26: Monks
- 27: Castles
- 28: Spearmen
- 29: Cavalry Archers
- 30: Eagle Warriors
- 31: Camels
- 34: Condottieri
- 35: Fishing Ships
- 36: Mamelukes
- 37: Heroes (Lancers)
- 38: Hussite Wagons

#### 3. Technologies
```json
{
  "id": 22,
  "name": "Loom",
  "internal_name": "Loom",
  "research_time": 25,
  "cost": {
    "gold": 50
  },
  "researched_at": 109,
  "age": 1,
  "effect_id": 22,
  "effects": [
    {
      "type": "attribute_add",
      "unit_id": 83,
      "attribute": "hit_points",
      "amount": 15
    },
    {
      "type": "attribute_add", 
      "unit_id": 83,
      "attribute": "melee_armor",
      "amount": 1
    },
    {
      "type": "attribute_add",
      "unit_id": 83,
      "attribute": "pierce_armor", 
      "amount": 2
    }
  ]
}
```

#### 4. Civilizations
```json
{
  "id": 1,
  "name": "Britons",
  "team_bonus_effect_id": 446,
  "tech_tree": {
    "units": [4, 24, 492, ...],
    "buildings": [12, 45, 82, ...],
    "technologies": [22, 67, 101, ...]
  },
  "bonuses": [
    {
      "effect_id": 287,
      "description": "Town Centers cost -50% wood in Castle Age",
      "effects": [...]
    }
  ],
  "unique_units": [8, 1155],
  "unique_technologies": [3, 61]
}
```

#### 5. Effects (Civ Bonuses & Tech Effects)
```json
{
  "id": 296,
  "name": "C-Bonus, Gunpowder +25% HP",
  "commands": [
    {
      "type": 5,
      "unit_id": 36,
      "attribute": 0,
      "amount": 1.25
    }
  ]
}
```

Effect command types:
- 0: Set attribute
- 1: Add resource
- 2: Enable/disable unit
- 3: Upgrade unit
- 4: Add attribute
- 5: Multiply attribute
- 101: Set tech cost
- 102: Add tech cost
- 103: Disable tech

---

## Architecture

### High-Level Architecture: Cloudflare + Modal Hybrid

This architecture separates concerns: Cloudflare handles fast API requests at the edge, while Modal handles compute-heavy workloads like unit simulations and army optimization.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Data Extraction Pipeline                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐               │
│  │ empires2_x2  │───▶│ genieutils-  │───▶│ Normalized JSON  │               │
│  │ _p1.dat      │    │ py Parser    │    │ Data Files       │               │
│  └──────────────┘    └──────────────┘    └──────────────────┘               │
│                                                   │                          │
│                                                   ▼                          │
│                                          ┌──────────────────┐               │
│                                          │ Upload to        │               │
│                                          │ Cloudflare D1/R2 │               │
│                                          └──────────────────┘               │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Cloudflare Stack                                │
│                         (API, Storage, Edge Caching)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐               │
│  │ R2 Bucket    │    │ D1 Database  │    │ Workers          │               │
│  │ (JSON files) │    │ (SQLite)     │    │ (API + MCP)      │               │
│  └──────────────┘    └──────────────┘    └──────────────────┘               │
│         │                   │                     │                          │
│         │                   └─────────┬───────────┘                          │
│         │                             │                                      │
│         ▼                             ▼                                      │
│  ┌──────────────┐              ┌──────────────────┐                         │
│  │ Direct       │              │ api.aoe2data.com │                         │
│  │ Download     │              │ mcp.aoe2data.com │                         │
│  │ (CDN cached) │              │                  │                         │
│  └──────────────┘              └──────────────────┘                         │
│                                        │                                     │
└────────────────────────────────────────┼─────────────────────────────────────┘
                                         │
                    ┌────────────────────┴────────────────────┐
                    │ Compute requests (cache miss)           │
                    ▼                                         │
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Modal (Compute)                                 │
│                     (Simulations, Optimization, Batch Jobs)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────────────────────────────────────────────┐              │
│  │                   Serverless Functions                     │              │
│  │                                                            │              │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌────────────┐ │              │
│  │  │ simulate_fight  │  │ optimize_army   │  │ precompute │ │              │
│  │  │ (unit vs unit)  │  │ (budget/enemy)  │  │ _matchups  │ │              │
│  │  └─────────────────┘  └─────────────────┘  └────────────┘ │              │
│  │                                                            │              │
│  └───────────────────────────────────────────────────────────┘              │
│                            │                                                 │
│                            ▼                                                 │
│                   ┌──────────────────┐                                      │
│                   │ Modal Volumes    │                                      │
│                   │ (cached results) │                                      │
│                   └──────────────────┘                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Request Flow

```
User Request
     │
     ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Cloudflare  │────▶│ Check D1    │────▶│ Return      │
│ Worker      │     │ Cache/Data  │ hit │ Response    │
└─────────────┘     └─────────────┘     └─────────────┘
                           │ miss
                           ▼
                    ┌─────────────┐     ┌─────────────┐
                    │ Call Modal  │────▶│ Compute &   │
                    │ Function    │     │ Cache       │
                    └─────────────┘     └─────────────┘
```

### Component Details

#### Cloudflare Stack

| Component | Service | Free Tier | Purpose |
|-----------|---------|-----------|---------|
| JSON Files | R2 | 10GB storage, 10M reads | Direct downloads, full dataset |
| Database | D1 | 5GB, 5M reads/day | Queryable data, cached results |
| REST API | Workers | 100k req/day | `/units`, `/civs`, `/techs` endpoints |
| MCP Server | Workers | Same as API | SSE endpoint for AI/LLM access |

#### Modal Stack

| Component | Free Tier | Purpose |
|-----------|-----------|---------|
| Functions | $30/mo credit | Unit simulations, army optimization |
| Cron Jobs | Included | Nightly matchup precomputation |
| Volumes | Included | Cache computed results |
| GPU (future) | Pay per second | ML-based recommendations |

### Why This Architecture

1. **Edge Performance**: 99% of requests served from Cloudflare edge cache (<50ms globally)
2. **Compute Separation**: Heavy calculations don't block API responses
3. **Cost Efficiency**: Only pay for compute when actually computing
4. **Future-Proof**: Modal supports GPU for future ML workloads
5. **Independent Scaling**: API and compute scale independently

---

## Implementation Plan

### Phase 1: Data Extraction (Week 1-2)

#### 1.1 Core Parser Development

```
aoe2-data/
├── src/
│   ├── parser/
│   │   ├── __init__.py
│   │   ├── dat_parser.py      # Main extraction logic
│   │   ├── unit_extractor.py  # Unit data normalization
│   │   ├── tech_extractor.py  # Technology data normalization
│   │   ├── civ_extractor.py   # Civilization data normalization
│   │   ├── effect_resolver.py # Resolve effect chains
│   │   └── constants.py       # Armor class names, attribute IDs
│   ├── models/
│   │   ├── __init__.py
│   │   ├── unit.py
│   │   ├── technology.py
│   │   ├── civilization.py
│   │   └── effect.py
│   └── export/
│       ├── __init__.py
│       ├── json_exporter.py
│       └── sqlite_exporter.py
├── scripts/
│   ├── extract.py             # Main extraction script
│   └── upload.py              # Upload to Cloudflare
└── output/
    └── [generated files]
```

#### 1.2 Output Files

```
output/
├── metadata.json           # Version info, extraction timestamp
├── units.json              # All units with full stats
├── technologies.json       # All technologies with effects
├── civilizations.json      # All civs with bonuses & tech trees
├── armor_classes.json      # Attack/armor class definitions
├── effects.json            # Raw effect data
└── aoe2.sqlite             # SQLite database with all data
```

### Phase 2: Cloudflare Infrastructure (Week 2-3)

#### 2.1 Project Structure

```
aoe2-api/
├── wrangler.toml           # Cloudflare configuration
├── src/
│   ├── index.ts            # Worker entry point
│   ├── routes/
│   │   ├── units.ts
│   │   ├── technologies.ts
│   │   ├── civilizations.ts
│   │   ├── armor-classes.ts
│   │   └── compute.ts      # Proxy to Modal
│   ├── mcp/
│   │   ├── server.ts       # MCP SSE handler
│   │   └── tools.ts        # MCP tool definitions
│   └── lib/
│       ├── db.ts           # D1 queries
│       └── modal.ts        # Modal API client
├── schema/
│   └── d1-schema.sql       # D1 database schema
└── scripts/
    └── seed-d1.ts          # Populate D1 from JSON
```

#### 2.2 Cloudflare Resources

```toml
# wrangler.toml
name = "aoe2-api"
main = "src/index.ts"
compatibility_date = "2024-01-01"

[[d1_databases]]
binding = "DB"
database_name = "aoe2-data"
database_id = "<generated>"

[[r2_buckets]]
binding = "STORAGE"
bucket_name = "aoe2-files"

[vars]
MODAL_API_URL = "https://your-modal-app.modal.run"
```

#### 2.3 API Endpoints

```
Base URL: https://api.aoe2data.com/v1

# Core Data (served from D1)
GET /units                    # List all units
GET /units/:id                # Get unit by ID
GET /units?name=archer        # Search by name
GET /units?class=cavalry      # Filter by class

GET /technologies             # List all technologies  
GET /technologies/:id         # Get technology by ID

GET /civilizations            # List all civilizations
GET /civilizations/:id        # Get civilization by ID
GET /civilizations/:id/units  # Get civ-specific unit stats
GET /civilizations/:id/techs  # Get civ tech tree

GET /armor-classes            # List attack/armor classes
GET /armor-classes/:id        # Get class details

# Downloads (served from R2)
GET /download/units.json      # Full units JSON
GET /download/all.json        # Complete dataset
GET /download/aoe2.sqlite     # SQLite database

# Compute (proxied to Modal)
POST /compute/simulate        # Simulate unit fight
POST /compute/optimize-army   # Find optimal army
GET  /compute/matchups/:id    # Get precomputed matchups

# Metadata
GET /metadata                 # Version info, last updated
GET /health                   # Health check

# MCP
GET /mcp/sse                  # MCP SSE endpoint
```

### Phase 3: Modal Compute Functions (Week 3-4)

#### 3.1 Project Structure

```
aoe2-compute/
├── modal_app.py            # Modal app definition
├── functions/
│   ├── simulate.py         # Unit fight simulation
│   ├── optimize.py         # Army composition optimizer
│   ├── matchups.py         # Matchup calculations
│   └── precompute.py       # Batch precomputation jobs
├── lib/
│   ├── combat.py           # Combat mechanics
│   ├── units.py            # Unit data access
│   └── civs.py             # Civ bonus application
└── data/
    └── [synced from Cloudflare]
```

#### 3.2 Modal Functions

```python
# modal_app.py
import modal

app = modal.App("aoe2-compute")

# Shared volume for data
volume = modal.Volume.from_name("aoe2-data", create_if_missing=True)

@app.function(volumes={"/data": volume})
def simulate_fight(
    attacker_id: int,
    defender_id: int,
    attacker_civ: str | None = None,
    defender_civ: str | None = None,
    num_attackers: int = 1,
    num_defenders: int = 1,
    iterations: int = 100
) -> dict:
    """
    Simulate fights between units and return statistics.
    
    Returns:
        {
            "attacker_win_rate": 0.73,
            "avg_attacker_remaining_hp": 24.5,
            "avg_defender_remaining_hp": 0,
            "avg_fight_duration": 12.3,
            "cost_efficiency": 1.45
        }
    """
    ...

@app.function(volumes={"/data": volume})
def optimize_army(
    budget: dict,  # {"food": 1000, "wood": 500, "gold": 800}
    enemy_composition: list[dict],  # [{"unit_id": 4, "count": 10}, ...]
    civ: str,
    enemy_civ: str | None = None
) -> dict:
    """
    Find optimal army composition against enemy.
    
    Returns:
        {
            "composition": [{"unit_id": 93, "count": 15}, ...],
            "total_cost": {"food": 980, "gold": 750},
            "expected_win_rate": 0.82,
            "reasoning": "Knights counter archers effectively..."
        }
    """
    ...

@app.function(volumes={"/data": volume})
def get_unit_matchups(unit_id: int, civ: str | None = None) -> dict:
    """
    Get win rates against all other units.
    
    Returns:
        {
            "unit_id": 4,
            "civ": "britons",
            "counters": [
                {"unit_id": 93, "win_rate": 0.15, "cost_efficiency": 0.4},
                ...
            ],
            "countered_by": [
                {"unit_id": 358, "win_rate": 0.85, "cost_efficiency": 2.1},
                ...
            ]
        }
    """
    ...

@app.function(schedule=modal.Cron("0 2 * * *"), volumes={"/data": volume})
def precompute_all_matchups():
    """
    Nightly job to precompute matchup matrix for all unit pairs.
    Results cached in volume and synced to Cloudflare D1.
    """
    ...

# Web endpoint for Cloudflare to call
@app.function()
@modal.web_endpoint(method="POST")
def compute_endpoint(request: dict):
    """HTTP endpoint that Cloudflare Worker calls"""
    action = request.get("action")
    params = request.get("params", {})
    
    if action == "simulate":
        return simulate_fight.remote(**params)
    elif action == "optimize":
        return optimize_army.remote(**params)
    elif action == "matchups":
        return get_unit_matchups.remote(**params)
    else:
        return {"error": "Unknown action"}
```

### Phase 4: MCP Server (Week 4)

#### 4.1 MCP Tools

```typescript
// src/mcp/tools.ts
export const tools = [
  {
    name: "get_unit",
    description: "Get unit statistics by ID or name",
    parameters: {
      unit_id: { type: "number", optional: true },
      name: { type: "string", optional: true },
      civ: { type: "string", optional: true, description: "Apply civ bonuses" }
    }
  },
  {
    name: "get_unit_counters",
    description: "Get units that counter or are countered by the specified unit",
    parameters: {
      unit_id: { type: "number", required: true },
      civ: { type: "string", optional: true }
    }
  },
  {
    name: "compare_units",
    description: "Compare two units side by side with optional civ bonuses",
    parameters: {
      unit_a: { type: "number", required: true },
      unit_b: { type: "number", required: true },
      civ_a: { type: "string", optional: true },
      civ_b: { type: "string", optional: true }
    }
  },
  {
    name: "simulate_fight",
    description: "Simulate a fight between units and get win rates",
    parameters: {
      attacker_id: { type: "number", required: true },
      defender_id: { type: "number", required: true },
      attacker_civ: { type: "string", optional: true },
      defender_civ: { type: "string", optional: true },
      num_attackers: { type: "number", default: 1 },
      num_defenders: { type: "number", default: 1 }
    }
  },
  {
    name: "optimize_army",
    description: "Find the optimal army composition given a budget and enemy",
    parameters: {
      budget_food: { type: "number", required: true },
      budget_wood: { type: "number", default: 0 },
      budget_gold: { type: "number", default: 0 },
      enemy_composition: { type: "string", description: "e.g. '10 archers, 5 knights'" },
      civ: { type: "string", required: true },
      enemy_civ: { type: "string", optional: true }
    }
  },
  {
    name: "get_civilization",
    description: "Get civilization bonuses, tech tree, and unique units",
    parameters: {
      civ: { type: "string", required: true }
    }
  },
  {
    name: "get_technology",
    description: "Get technology details including effects",
    parameters: {
      tech_id: { type: "number", optional: true },
      name: { type: "string", optional: true }
    }
  },
  {
    name: "search",
    description: "Search for units, technologies, or civilizations by name",
    parameters: {
      query: { type: "string", required: true },
      type: { type: "string", enum: ["all", "units", "techs", "civs"], default: "all" }
    }
  }
];
```

### Phase 5: Deployment & Automation (Week 5)

#### 5.1 Deployment Pipeline

```yaml
# .github/workflows/deploy.yml
name: Deploy AoE2 Data

on:
  workflow_dispatch:
    inputs:
      game_version:
        description: 'Game version to extract'
        required: true
  schedule:
    - cron: '0 6 * * 1'  # Weekly check on Mondays

jobs:
  extract:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install genieutils-py
      
      - name: Download game files
        run: |
          # Download from Steam or cached location
          ./scripts/download-dat.sh
      
      - name: Extract data
        run: python scripts/extract.py
      
      - name: Upload to Cloudflare R2
        run: |
          npx wrangler r2 object put aoe2-files/units.json --file=output/units.json
          npx wrangler r2 object put aoe2-files/all.json --file=output/all.json
          # ... other files
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CF_API_TOKEN }}
      
      - name: Seed D1 database
        run: npx wrangler d1 execute aoe2-data --file=output/seed.sql
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CF_API_TOKEN }}
      
      - name: Sync data to Modal
        run: modal volume put aoe2-data output/
        env:
          MODAL_TOKEN_ID: ${{ secrets.MODAL_TOKEN_ID }}
          MODAL_TOKEN_SECRET: ${{ secrets.MODAL_TOKEN_SECRET }}
      
      - name: Trigger Modal precomputation
        run: modal run aoe2-compute::precompute_all_matchups
```

#### 5.2 Domain Setup

```
Domains:
  api.aoe2data.com     → Cloudflare Worker (API)
  mcp.aoe2data.com     → Cloudflare Worker (MCP SSE)
  files.aoe2data.com   → Cloudflare R2 (Downloads)
```

---

## Database Schema (Cloudflare D1)

```sql
-- D1 Schema (SQLite-compatible)

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE units (
    id INTEGER PRIMARY KEY,
    internal_name TEXT,
    name TEXT,
    class INTEGER,
    hit_points REAL,
    speed REAL,
    line_of_sight REAL,
    range REAL,
    min_range REAL,
    reload_time REAL,
    attack_delay REAL,
    accuracy INTEGER,
    projectile_speed REAL,
    train_time REAL,
    cost_food INTEGER DEFAULT 0,
    cost_wood INTEGER DEFAULT 0,
    cost_gold INTEGER DEFAULT 0,
    cost_stone INTEGER DEFAULT 0,
    created_at_building INTEGER,
    age INTEGER,
    raw_data TEXT  -- Full JSON for complex queries
);

CREATE TABLE unit_attacks (
    unit_id INTEGER REFERENCES units(id),
    armor_class_id INTEGER,
    amount REAL,
    PRIMARY KEY (unit_id, armor_class_id)
);

CREATE TABLE unit_armors (
    unit_id INTEGER REFERENCES units(id),
    armor_class_id INTEGER,
    amount REAL,
    PRIMARY KEY (unit_id, armor_class_id)
);

CREATE TABLE technologies (
    id INTEGER PRIMARY KEY,
    internal_name TEXT,
    name TEXT,
    research_time REAL,
    cost_food INTEGER DEFAULT 0,
    cost_wood INTEGER DEFAULT 0,
    cost_gold INTEGER DEFAULT 0,
    cost_stone INTEGER DEFAULT 0,
    researched_at_building INTEGER,
    age INTEGER,
    effect_id INTEGER,
    raw_data TEXT
);

CREATE TABLE civilizations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    team_bonus_effect_id INTEGER,
    raw_data TEXT
);

CREATE TABLE civ_units (
    civ_id INTEGER REFERENCES civilizations(id),
    unit_id INTEGER REFERENCES units(id),
    available INTEGER DEFAULT 1,
    PRIMARY KEY (civ_id, unit_id)
);

CREATE TABLE civ_techs (
    civ_id INTEGER REFERENCES civilizations(id),
    tech_id INTEGER REFERENCES technologies(id),
    available INTEGER DEFAULT 1,
    PRIMARY KEY (civ_id, tech_id)
);

CREATE TABLE civ_bonuses (
    id INTEGER PRIMARY KEY,
    civ_id INTEGER REFERENCES civilizations(id),
    effect_id INTEGER,
    description TEXT
);

CREATE TABLE effects (
    id INTEGER PRIMARY KEY,
    name TEXT,
    commands TEXT  -- JSON array of effect commands
);

CREATE TABLE armor_classes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);

-- Precomputed matchup data (populated by Modal)
CREATE TABLE matchups (
    attacker_id INTEGER,
    defender_id INTEGER,
    attacker_civ_id INTEGER,
    defender_civ_id INTEGER,
    win_rate REAL,
    avg_remaining_hp REAL,
    cost_efficiency REAL,
    computed_at TEXT,
    PRIMARY KEY (attacker_id, defender_id, attacker_civ_id, defender_civ_id)
);

-- Indexes for common queries
CREATE INDEX idx_units_name ON units(name);
CREATE INDEX idx_units_class ON units(class);
CREATE INDEX idx_techs_name ON technologies(name);
CREATE INDEX idx_matchups_attacker ON matchups(attacker_id);
CREATE INDEX idx_matchups_defender ON matchups(defender_id);
```

---

## Cost Estimates

### Free Tier Coverage

| Service | Free Tier | Expected Usage | Covered? |
|---------|-----------|----------------|----------|
| Cloudflare Workers | 100k req/day | ~10-50k req/day | ✅ |
| Cloudflare D1 | 5M reads/day, 5GB | ~1M reads/day, <100MB | ✅ |
| Cloudflare R2 | 10GB, 10M reads/mo | <1GB, ~100k reads/mo | ✅ |
| Modal | $30/mo credit | ~$5-15/mo compute | ✅ |

### If Traffic Grows

| Tier | Workers | D1 | Modal | Est. Total |
|------|---------|----|----|------------|
| Free | 100k/day | 5M reads | $30 credit | $0 |
| Light | $5/mo | $5/mo | $30 credit | ~$10/mo |
| Medium | $25/mo | $25/mo | $50/mo | ~$100/mo |

---

## Future Compute Capabilities

### Phase 1: Basic Simulations (Week 3-4)
- 1v1 unit fight simulation
- Win rate calculations
- Cost efficiency metrics

### Phase 2: Army Optimization (Week 5-6)
- Multi-unit composition analysis
- Budget-constrained optimization
- Counter-composition suggestions

### Phase 3: Advanced Analysis (Future)
- Full army battle simulations (with micro patterns)
- Build order optimization
- Map-specific recommendations
- ML-based meta predictions (requires GPU)

### Compute Function Examples

```python
# Example: What beats 10 crossbows as Franks?
optimize_army(
    budget={"food": 600, "gold": 400},
    enemy_composition=[{"unit_id": 24, "count": 10}],  # Crossbows
    civ="franks",
    enemy_civ="britons"
)
# Returns: {"composition": [{"unit_id": 38, "count": 8}], ...}  # Knights

# Example: Simulate 20 knights vs 40 pikes
simulate_fight(
    attacker_id=38,
    defender_id=358,
    num_attackers=20,
    num_defenders=40,
    iterations=1000
)
# Returns: {"attacker_win_rate": 0.12, "cost_efficiency": 0.45, ...}
```

---

## Development Milestones

| Milestone | Deliverable | Timeline |
|-----------|-------------|----------|
| M1 | Core parser extracts all unit data | Week 1 |
| M2 | Full data extraction (units, techs, civs, effects) | Week 2 |
| M3 | Cloudflare D1 schema + R2 upload scripts | Week 2 |
| M4 | REST API deployed (core endpoints) | Week 3 |
| M5 | Modal compute functions (simulate, optimize) | Week 3-4 |
| M6 | MCP server with all tools | Week 4 |
| M7 | Precomputation pipeline (nightly matchups) | Week 5 |
| M8 | GitHub Actions deployment automation | Week 5 |
| M9 | Documentation and examples | Week 6 |
| M10 | Public launch | Week 6 |

---

## Repository Structure

```
aoe2-data/
├── README.md
├── LICENSE (MIT)
│
├── extractor/                    # Python data extraction
│   ├── pyproject.toml
│   ├── src/
│   │   ├── parser/
│   │   ├── models/
│   │   └── export/
│   └── scripts/
│       ├── extract.py
│       └── upload.py
│
├── api/                          # Cloudflare Worker
│   ├── wrangler.toml
│   ├── package.json
│   ├── src/
│   │   ├── index.ts
│   │   ├── routes/
│   │   └── mcp/
│   └── schema/
│       └── d1-schema.sql
│
├── compute/                      # Modal functions
│   ├── modal_app.py
│   ├── functions/
│   └── lib/
│
├── docs/                         # Documentation
│   ├── api.md
│   ├── mcp.md
│   └── data-model.md
│
└── .github/
    └── workflows/
        ├── deploy.yml
        └── extract.yml
```

---

## References

- [genieutils-py](https://github.com/SiegeEngineers/genieutils-py) — Python .dat parser
- [genieutils](https://github.com/sandsmark/genieutils) — C++ reference implementation
- [aoe2techtree](https://github.com/SiegeEngineers/aoe2techtree) — Reference for data structure
- [Krakenmeister/genieutils-examples](https://github.com/Krakenmeister/genieutils-examples) — Usage examples
- [AoE2DE UGC Guide](https://www.ageofempires.com/mods/) — Official modding documentation
- [MCP Specification](https://modelcontextprotocol.io/) — Model Context Protocol docs
- [Cloudflare D1 Docs](https://developers.cloudflare.com/d1/) — D1 SQLite database
- [Cloudflare Workers Docs](https://developers.cloudflare.com/workers/) — Serverless functions
- [Modal Docs](https://modal.com/docs) — Serverless compute platform

---

## License

Data extracted from Age of Empires II: Definitive Edition is subject to Microsoft's Game Content Usage Rules. This project is for non-commercial, community use.

Code will be released under MIT License.

---

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-02-01 | Public API, no auth | Maximize accessibility |
| 2025-02-01 | Latest patch only | Simplifies storage and maintenance |
| 2025-02-01 | English only | Reduce initial complexity |
| 2025-02-01 | Ranked civs only (no RoR) | Focus on competitive play |
| 2025-02-01 | Cloudflare + Modal architecture | Edge performance + scalable compute |

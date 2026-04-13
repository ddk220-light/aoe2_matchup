---
name: aoe2onlinereference
description: Use when pulling unit stats, civ bonuses, unique techs, armor class data, or unit ability descriptions from external online sources to document or validate the local database. Invoke when asked to "check the wiki", "compare with aoe2techtree", "pull online stats", "verify mechanic", or "build reference markdown files".
---

# AoE2 Online Reference Sources

Four external sources are used for AoE2 data. Each has different strengths. Always cross-reference at least two sources before drawing conclusions.

**Important:** These sources are for pulling EXTERNAL data to compare against our local database (`webapp/aoe2_reference.db`, `webapp/aoe2_units.db`). Do NOT use our own Railway API (aoe2.up.railway.app) as the source — that only reflects what we already have. The goal is to validate our DB against the authoritative external sources.

---

## ⭐ Source 0: Firecrawl (FIRST STEP for any wiki page)

**API key:** stored as env var `FIRECRAWL_API_KEY` (`fc-dc42befccd9640d5a2dfdc4bc5e92a4a`)  
**MCP tool:** `mcp__Apify__apify-slash-rag-web-browser` or direct `WebFetch` to Firecrawl API

Use Firecrawl **before** the raw wiki API for any page that may be:
- Behind JavaScript rendering (Fandom wiki renders some infoboxes client-side)
- A complex page with templates that the raw wikitext doesn't fully expand
- A page where the bare URL returns a stub (Fandom redirects can return 283-char stubs)

### Firecrawl API usage

```bash
# Scrape a Fandom wiki page to clean markdown
curl -X POST https://api.firecrawl.dev/v1/scrape \
  -H "Authorization: Bearer fc-dc42befccd9640d5a2dfdc4bc5e92a4a" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://ageofempires.fandom.com/wiki/Galleon_(Age_of_Empires_II)", "formats": ["markdown"]}'
```

Returns clean markdown with all template content rendered. Much richer than raw wikitext for ability sections, stat tables, and civ bonus lists.

### When to fall back to raw wiki API

If Firecrawl is unavailable or rate-limited, fall back to Source 1 (Fandom wiki API). The wiki API is still reliable for wikitext-level data but misses JS-rendered content.

---

## Source 1: Fandom Wiki API

**Base URL:** `https://ageofempires.fandom.com/api.php`

This is a MediaWiki API. Use `WebFetch` with JSON responses. Best for: civ bonuses, unique tech descriptions, flavor text, and stat infoboxes.

### Key Query Patterns

**Get raw wikitext for a page:**
```
https://ageofempires.fandom.com/api.php?action=parse&page=PAGE_NAME&prop=wikitext&format=json
```

**Search for a page:**
```
https://ageofempires.fandom.com/api.php?action=query&list=search&srsearch=TERM&format=json
```

**Get page sections only (faster than full wikitext):**
```
https://ageofempires.fandom.com/api.php?action=parse&page=PAGE_NAME&prop=sections&format=json
```

### Page Name Conventions

| Content | Pattern | Example |
|---------|---------|---------|
| Civilization | `CivName_(Age_of_Empires_II)` | `Muisca_(Age_of_Empires_II)` |
| Generic unit | `Unit_Name_(Age_of_Empires_II)` | `Arbalester_(Age_of_Empires_II)` |
| Unique unit | `Unit_Name_(Age_of_Empires_II)` | `Temple_Guard_(Age_of_Empires_II)` |
| Tech | `Tech_Name` | `Heresy` |
| Armor class | Not available directly | — |

**⚠️ ALWAYS try the `_(Age_of_Empires_II)` suffix FIRST.** Bare unit names (e.g., `Fire_Archer`) return 283-character stub pages that are NOT None — the API succeeds but the content is useless. The suffix version always returns the correct full page. Only fall back to the bare name if the suffix fails.

### What the Wikitext Contains

Civ pages have infoboxes with:
- `civ_bonuses` — list of civilization bonuses
- `unique_unit` — name(s) of unique units
- `unique_techs` — castle + imperial age unique techs with costs
- `team_bonus`
- `missing_units` / `missing_techs` — tech tree gaps

Unit pages have `infobox_unit` with:
- `hp`, `attack`, `armor` (melee/pierce), `range`, `speed`, `reload_time`
- `attack_bonuses` — bonus damage vs armor classes
- `cost`, `train_time`, `pop_space`, `line_of_sight`
- `special` — free-text description of unique mechanic

### Wikitext Parsing Tips

- Stats in wiki infoboxes are **post-tech, post-bonus values** (e.g., Briton archers show +1 range from civ bonus). Our DB stores BASE values. Adjust when comparing.
- Bonus attacks are listed as `+X vs Y` strings — parse with regex: `\+(\d+) vs (.+)`
- Unique tech costs look like `CastleUT=cost1 cost2` — extract the numbers.
- For civs with multiple unique units (e.g., Muisca has Temple Guard + Guecha Warrior), both appear in `unique_unit` separated by `<br>`.

---

## Source 2: SiegeEngineers/aoe2techtree

**GitHub:** `https://github.com/SiegeEngineers/aoe2techtree`  
**Raw files:** `https://raw.githubusercontent.com/SiegeEngineers/aoe2techtree/master/`

This is the **most reliable machine-readable source** for unit IDs, tech tree structure, and per-civ availability. Best for: unit IDs, tech IDs, civ tech tree coverage (what each civ can/cannot research), costs.

### Key Files

| File | URL | Content |
|------|-----|---------|
| Full data | `.../data/data.json` | Units, techs, buildings — ALL game data in one JSON |
| Civ tree (per civ) | `.../data/trees/{CIV_UPPER}.json` | Tech tree layout for one civ |
| English strings | `.../data/locales/en/strings.json` | ID → name mapping |
| Civ listing | `.../data/data.json` → `civs[]` | All 53 civs with unit/tech/building arrays |

### data.json Top-Level Keys

```json
{
  "units": { "ID": { "id", "name", "age", "cost", "hp", "attack", ... } },
  "techs": { "ID": { "id", "name", "age", "cost", "effect", ... } },
  "buildings": { "ID": { ... } },
  "civs": [
    {
      "name": "Aztecs",
      "uniqueTechs": [castleUT_id, imperialUT_id],
      "uniqueUnits": [unit_id],
      "bonuses": [...],
      "teamBonus": "..."
    }
  ]
}
```

### Per-Unit Fields in data.json

```json
{
  "id": 359,
  "name": "Arbalester",
  "age": 4,
  "cost": { "Food": 25, "Wood": 45 },
  "hp": 40,
  "attack": 6,
  "range": 5,
  "minimumRange": 0,
  "reloadTime": 2.0,
  "attackSpeed": 2.0,
  "lineOfSight": 7,
  "armor": "0/0",
  "speed": 0.96,
  "accuracy": "80%",
  "numberOfProjectiles": 1,
  "attackBonus": ["+3 Spearmen"],
  "armorClass": ["Archer", "FootArcher", "UniqueUnit"]
}
```

### Civ Tree Files

Each `.../data/trees/AZTECS.json` contains the complete tech tree layout for that civilization — which units/techs are AVAILABLE vs NOT AVAILABLE. Use this to validate:
- Does our DB include units a civ doesn't have? (false positives)
- Is a unit marked `has_unit=0` correctly?

### Fetching a Specific Civ

```python
# In a WebFetch call:
url = "https://raw.githubusercontent.com/SiegeEngineers/aoe2techtree/master/data/data.json"
# Top-level civs array — find by name
civ = next(c for c in data["civs"] if c["name"] == "Muisca")
```

---

## Source 3: hsynlms/aoe2techtree

**GitHub:** `https://github.com/hsynlms/aoe2techtree`  
**Website:** `https://aoe2techtree.net`

This is a **visual tech tree website** that mirrors the SiegeEngineers data. Best for: unit stats displayed on the website, icon picture_index values (used for fallback CDN icons in our frontend).

### Key Difference from SiegeEngineers

`hsynlms/aoe2techtree` uses **picture_index** (not game unit ID) for icon URLs:
```
https://aoe2techtree.net/img/Unit/{picture_index}.png
```
This is important because our `NAME_TO_ICON` mapping in `constants.js` uses picture_index for post-Last Khans units (ID > 1665). Cross-reference this source when adding new unit icons.

### Raw Data Files

Same structure as SiegeEngineers — check:
```
https://raw.githubusercontent.com/hsynlms/aoe2techtree/master/data/data.json
```
or
```
https://api.github.com/repos/hsynlms/aoe2techtree/contents/data
```

---

## Validation Workflow

Use this when comparing external data against our local DB.

### Step 1: Pull external data

```python
# Fandom wiki — get civ page wikitext
wiki_url = "https://ageofempires.fandom.com/api.php?action=parse&page=Muisca_(Age_of_Empires_II)&prop=wikitext&format=json"

# SiegeEngineers — full data.json (cache locally if running many comparisons)
se_url = "https://raw.githubusercontent.com/SiegeEngineers/aoe2techtree/master/data/data.json"
```

### Step 2: Query our DB

```bash
# Units for a specific civ
sqlite3 webapp/aoe2_reference.db "
  SELECT unit_slug, unit_name, age, base_hp, base_attack, base_melee_armor, base_pierce_armor, base_speed, base_range, base_reload_time
  FROM ref_units WHERE civ_name='Muisca' ORDER BY age, unit_slug;
"

# Special effects for a unit
sqlite3 webapp/aoe2_reference.db "
  SELECT ru.unit_slug, rs.property_name, rs.property_value, rs.source
  FROM ref_special_effects rs
  JOIN ref_units ru ON rs.ref_unit_id = ru.id
  WHERE ru.civ_name='Muisca' ORDER BY ru.unit_slug, rs.property_name;
"

# Techs applied to a unit
sqlite3 webapp/aoe2_reference.db "
  SELECT ru.unit_slug, rt.tech_name, rt.effect_description
  FROM ref_techs_applied rt
  JOIN ref_units ru ON rt.ref_unit_id = ru.id
  WHERE ru.civ_name='Muisca' ORDER BY ru.unit_slug;
"
```

### Step 3: Compare

Key things to diff:

| Field | Our DB column | External source field | Notes |
|-------|-------------|----------------------|-------|
| HP | `base_hp` | `hp` | Wiki shows POST-bonus HP |
| Attack | `base_attack` | `attack` | Wiki may include bonuses |
| Speed | `base_speed` | `speed` | Should match exactly |
| Range | `base_range` | `range` | Should match exactly |
| Reload | `base_reload_time` | `reloadTime` / `attackSpeed` | Same value |
| Melee armor | `base_melee_armor` | `armor` (first value) | e.g., "0/4" → 0 melee |
| Pierce armor | `base_pierce_armor` | `armor` (second value) | e.g., "0/4" → 4 pierce |
| Cost food | `base_cost_food` | `cost.Food` | Should match |
| Cost wood | `base_cost_wood` | `cost.Wood` | Should match |
| Cost gold | `base_cost_gold` | `cost.Gold` | Should match |

### Common Discrepancies

- **Wiki values are post-tech**: Briton archer range appears as 6 (civ bonus +1) but our DB stores 5. This is correct behavior — always compare BASE values from SiegeEngineers, not wiki.
- **Elite upgrade vs base**: SiegeEngineers lists the elite upgrade unit as a separate entry. Make sure you're comparing the right tier.
- **Civ-bonus stats baked in**: Some wikis bake civ bonuses into the listed stats (e.g., Mongol mangudai showing +25% faster fire rate). Our DB applies civ bonuses as techs — the `final_stats` fields reflect this.
- **New units may be missing from external sources**: Units added in very recent patches (like the Three Kingdoms civs) may not yet be in SiegeEngineers/aoe2techtree. The wiki is usually faster to update.

---

## Reference Markdown File Format

When building the full corpus of markdown reference files, use this structure:

### Civ file (`docs/reference/civs/{CivName}.md`)

```markdown
# {CivName}

**Type:** Archer/Cavalry/etc. Civilization  
**Source:** Fandom wiki + SiegeEngineers/aoe2techtree (pulled {date})

## Civilization Bonuses
- Bonus 1
- Bonus 2

## Team Bonus
{team bonus text}

## Unique Technologies
| Tech | Age | Cost | Effect |
|------|-----|------|--------|
| {castle UT} | Castle | {cost} | {effect} |
| {imperial UT} | Imperial | {cost} | {effect} |

## Unique Units
### {Unit Name}
| Stat | Regular | Elite |
|------|---------|-------|
| HP | ... | ... |
| Attack | ... | ... |
...

**Special Ability:** {description}

## Tech Tree Gaps
{notable missing units/techs}

## DB Comparison
| Field | External | Our DB | Match? |
|-------|----------|--------|--------|
| ... | ... | ... | ✅/❌ |
```

### Unit file (`docs/reference/units/{UnitName}.md`)

```markdown
# {Unit Name}

**Type:** {Infantry/Cavalry/Archer/Siege}  
**Available to:** {list of civs}  
**Building:** {Barracks/Stable/etc.}

## Stats
| Stat | Castle Age | Imperial Age |
|------|-----------|--------------|
...

## Bonus Damage
| Target | Amount |
|--------|--------|
...

## Armor Classes
{list}

## Special Effects
{any trample/bleed/charge/etc.}

## DB Comparison
...
```

### Armor classes file (`docs/reference/armor-classes.md`)

```markdown
# AoE2 Armor Classes

| ID | Name | Key Units |
|----|------|-----------|
| 0 | Infantry | Militia line, Eagle Warrior |
...
```

---

## Quick Reference: Supported Civs

The 53 civs in our DB (as of April 2026):
Armenians, Aztecs, Bengalis, Berbers, Bohemians, Britons, Bulgarians, Burgundians, Burmese, Byzantines, Celts, Chinese, Cumans, Dravidians, Ethiopians, Franks, Georgians, Goths, Gurjaras, Hindustanis, Huns, Incas, Italians, Japanese, Jurchens, Khitans, Khmer, Koreans, Lithuanians, Magyars, Malay, Malians, Mapuche, Mayans, Mongols, Muisca, Persians, Poles, Portuguese, Romans, Saracens, Shu, Sicilians, Slavs, Spanish, Tatars, Teutons, Tupi, Turks, Vietnamese, Vikings, Wei, Wu

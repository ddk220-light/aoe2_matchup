# Multi-Unit Line Cards Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Show all units in a line card (e.g., Paladin + Elite Leitis for Lithuanians) instead of only the highest-scoring one.

**Architecture:** Change `best_units.py` to return arrays per line instead of single entries. Update all consumers (strategic description, matchup recommendations, frontend) to handle arrays. Frontend renders all units with side-by-side icons.

**Tech Stack:** Python (best_units.py), vanilla JavaScript (matchup.js), CSS (matchup.css).

---

### Task 1: Change `best_units.py` query from LIMIT 1 to fetch all units

**Files:**
- Modify: `webapp/best_units.py:565-601`

**Step 1: Change query and line entry to array**

In `compute_civ_power_units()` (line 565), replace the `LIMIT 1` query block with a `fetchall` that returns an array:

Replace this block (lines 567-592):

```python
                for line_slug in line_slugs:
                    score_type = LINE_SCORE_TYPE[line_slug]
                    rc.execute(
                        """SELECT unit_slug, line_slug, score_value, rank, median_delta
                            FROM battle_scores
                            WHERE civ_name = ?
                              AND LOWER(age) = ?
                              AND score_type = ?
                              AND line_slug = ?
                            ORDER BY score_value DESC
                            LIMIT 1""",
                        [civ, age_key, score_type, line_slug],
                    )
                    row = rc.fetchone()

                    if row and civ in CIVS_WITHOUT_TREBUCHET and row["unit_slug"] in _TREBUCHET_SLUGS:
                        row = None

                    if row:
                        entry = _build_unit_entry(
                            row, civ, conn, db_age, reference_techs,
                            techs_by_slug, effects_by_slug, line_counts, score_type
                        )
                        col_data[line_slug] = entry
                    else:
                        col_data[line_slug] = None
```

With:

```python
                for line_slug in line_slugs:
                    score_type = LINE_SCORE_TYPE[line_slug]
                    rc.execute(
                        """SELECT unit_slug, line_slug, score_value, rank, median_delta
                            FROM battle_scores
                            WHERE civ_name = ?
                              AND LOWER(age) = ?
                              AND score_type = ?
                              AND line_slug = ?
                            ORDER BY score_value DESC""",
                        [civ, age_key, score_type, line_slug],
                    )
                    rows = rc.fetchall()

                    # Filter trebuchets for civs that don't have them
                    if civ in CIVS_WITHOUT_TREBUCHET:
                        rows = [r for r in rows if r["unit_slug"] not in _TREBUCHET_SLUGS]

                    if rows:
                        entries = []
                        for row in rows:
                            entry = _build_unit_entry(
                                row, civ, conn, db_age, reference_techs,
                                techs_by_slug, effects_by_slug, line_counts, score_type
                            )
                            entries.append(entry)
                        col_data[line_slug] = entries
                    else:
                        col_data[line_slug] = None
```

**Step 2: Update `strength_profile` to use first (best) entry**

Replace (line 600-601):

```python
                    entry = power_units[col_key].get(line_slug)
                    strength_profile[line_slug] = entry["strength"] if entry else None
```

With:

```python
                    entries = power_units[col_key].get(line_slug)
                    strength_profile[line_slug] = entries[0]["strength"] if entries else None
```

**Step 3: Verify by running best_units.py**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer && source venv/bin/activate && cd webapp && python3 best_units.py`

Expected: Writes `civ_power_units.json` for 50 civs. Spot-check:

```bash
python3 -c "import json; d=json.load(open('civ_power_units.json')); k=d['Lithuanians']['imperial']['power_units']['cavalry']['knight']; print(len(k), [u['unit_name'] for u in k])"
```

Expected: `2 ['Elite Leitis', 'Paladin']`

**Step 4: Commit**

```bash
git add webapp/best_units.py
git commit -m "feat: return all units per line as array in civ_power_units"
```

---

### Task 2: Update `_generate_strategic_description()` for array entries

**Files:**
- Modify: `webapp/best_units.py:390-530`

The function reads line entries as single dicts in several places. Each needs to handle the array format (use `entries[0]` for best unit).

**Step 1: Update all line entry reads**

At line 406-410, the function iterates `col_data.values()` to find best entry. With arrays, each value is now a list. Replace:

```python
        col_data = power_units.get(col, {})
        best_entry = None
        for entry in col_data.values():
            if entry and (best_entry is None or entry.get("percentile", 0) > best_entry.get("percentile", 0)):
                best_entry = entry
```

With:

```python
        col_data = power_units.get(col, {})
        best_entry = None
        for entries in col_data.values():
            if entries:
                top = entries[0]
                if best_entry is None or top.get("percentile", 0) > best_entry.get("percentile", 0):
                    best_entry = top
```

At line 449 (`camel_data`):

```python
        camel_data = power_units.get("cavalry", {}).get("camel")
        camel_name = camel_data["unit_name"] if camel_data else "camels"
```

Change to:

```python
        camel_entries = power_units.get("cavalry", {}).get("camel")
        camel_name = camel_entries[0]["unit_name"] if camel_entries else "camels"
```

At line 456 (`spear_data`):

```python
        spear_data = power_units.get("infantry", {}).get("spear")
        spear_name = spear_data["unit_name"] if spear_data else "spearmen"
```

Change to:

```python
        spear_entries = power_units.get("infantry", {}).get("spear")
        spear_name = spear_entries[0]["unit_name"] if spear_entries else "spearmen"
```

At lines 485-487 (siege entries):

```python
    ram_entry = siege_data.get("ram")
    treb_entry = siege_data.get("trebuchet")
    bbc_entry = siege_data.get("bombard_cannon")

    has_good_ram = ram_entry and ram_entry["strength"] in ("signature", "strong")
    has_good_treb = treb_entry and treb_entry["strength"] in ("signature", "strong")
    has_good_bbc = bbc_entry and bbc_entry["strength"] in ("signature", "strong")
```

Change to:

```python
    ram_entries = siege_data.get("ram")
    treb_entries = siege_data.get("trebuchet")
    bbc_entries = siege_data.get("bombard_cannon")

    has_good_ram = ram_entries and ram_entries[0]["strength"] in ("signature", "strong")
    has_good_treb = treb_entries and treb_entries[0]["strength"] in ("signature", "strong")
    has_good_bbc = bbc_entries and bbc_entries[0]["strength"] in ("signature", "strong")
```

At lines 496-500 (find best infantry):

```python
        best_inf = None
        for entry in inf_data.values():
            if entry and (best_inf is None or entry.get("percentile", 0) > best_inf.get("percentile", 0)):
                best_inf = entry
```

Change to:

```python
        best_inf = None
        for entries in inf_data.values():
            if entries:
                top = entries[0]
                if best_inf is None or top.get("percentile", 0) > best_inf.get("percentile", 0):
                    best_inf = top
```

At lines 507-511 (find best ranged), same pattern:

```python
        best_rng = None
        for entry in rng_data.values():
            if entry and (best_rng is None or entry.get("percentile", 0) > best_rng.get("percentile", 0)):
                best_rng = entry
```

Change to:

```python
        best_rng = None
        for entries in rng_data.values():
            if entries:
                top = entries[0]
                if best_rng is None or top.get("percentile", 0) > best_rng.get("percentile", 0):
                    best_rng = top
```

**Step 2: Verify by running best_units.py**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer/webapp && python3 best_units.py`

Expected: 50 civs generated, strategic descriptions still make sense. Spot-check:

```bash
python3 -c "import json; d=json.load(open('civ_power_units.json')); print(d['Britons']['imperial']['strategic_description'])"
```

**Step 3: Commit**

```bash
git add webapp/best_units.py
git commit -m "fix: update strategic description for array-based line entries"
```

---

### Task 3: Update `get_matchup_recommendations()` for array entries

**Files:**
- Modify: `webapp/best_units.py:902-1015`

**Step 1: Update opponent strength detection**

At lines 908-911, the function iterates `col_data.items()` where entries are now arrays:

```python
        for line_slug, entry in col_data.items():
            if entry and entry["strength"] in ("strong", "signature"):
                if best_entry is None or entry.get("median_delta", 0) > best_entry.get("median_delta", 0):
                    best_entry = entry
```

Change to:

```python
        for line_slug, entries in col_data.items():
            if entries:
                top = entries[0]
                if top["strength"] in ("strong", "signature"):
                    if best_entry is None or top.get("median_delta", 0) > best_entry.get("median_delta", 0):
                        best_entry = top
```

At lines 926-928 (fallback), same pattern:

```python
            for line_slug, entry in col_data.items():
                if entry and (best_entry is None or entry.get("median_delta", 0) > best_entry.get("median_delta", 0)):
                    best_entry = entry
```

Change to:

```python
            for line_slug, entries in col_data.items():
                if entries:
                    top = entries[0]
                    if best_entry is None or top.get("median_delta", 0) > best_entry.get("median_delta", 0):
                        best_entry = top
```

**Step 2: Update trash unit lookup**

At lines 1009-1013:

```python
        for col_data in civ_a_data["power_units"].values():
            entry = col_data.get(trash_line) if isinstance(col_data, dict) else None
            if entry:
                trash_entry = entry
                break
```

Change to:

```python
        for col_data in civ_a_data["power_units"].values():
            entries = col_data.get(trash_line) if isinstance(col_data, dict) else None
            if entries:
                trash_entry = entries[0]
                break
```

**Step 3: Verify**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer/webapp && python3 best_units.py`

Then start the webapp and test matchup recommendations:

```bash
PORT=5003 python3 app.py &
sleep 5
curl -s "http://localhost:5003/api/matchup-recommendations/Britons/Franks" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('individual_counters',[])), 'counters')"
```

Expected: Non-zero counter count.

**Step 4: Commit**

```bash
git add webapp/best_units.py
git commit -m "fix: update matchup recommendations for array-based line entries"
```

---

### Task 4: Update frontend `matchup.js` for multi-unit rendering

**Files:**
- Modify: `webapp/static/js/matchup.js:190-207`

**Step 1: Update `renderAnalysis()` line rendering**

Replace the line rendering block (lines 190-207):

```javascript
        /* Render each unit line */
        for (var j = 0; j < lineSlugs.length; j++) {
            var lineSlug = lineSlugs[j];
            var lineEntry = colData[lineSlug];
            var lineName = LINE_NAMES[lineSlug] || slugToName(lineSlug);

            html += '<div class="line-section">';
            html += '<div class="line-label">' + escapeHtml(lineName) + '</div>';

            if (lineEntry) {
                html += '<div class="unit-wrap">';
                html += renderUnitBadge(lineEntry);
                html += '</div>';
            } else {
                html += '<div class="line-unavailable">\u2014</div>';
            }
            html += '</div>';
        }
```

With:

```javascript
        /* Render each unit line */
        for (var j = 0; j < lineSlugs.length; j++) {
            var lineSlug = lineSlugs[j];
            var lineEntries = colData[lineSlug];
            var lineName = LINE_NAMES[lineSlug] || slugToName(lineSlug);

            html += '<div class="line-section">';
            html += '<div class="line-label">' + escapeHtml(lineName) + '</div>';

            if (lineEntries && lineEntries.length > 0) {
                var isMulti = lineEntries.length > 1;
                html += '<div class="unit-wrap' + (isMulti ? ' multi-unit' : '') + '">';
                for (var u = 0; u < lineEntries.length; u++) {
                    html += renderUnitBadge(lineEntries[u]);
                }
                html += '</div>';
            } else {
                html += '<div class="line-unavailable">\u2014</div>';
            }
            html += '</div>';
        }
```

**Step 2: Update column signature detection**

At lines 178-181:

```javascript
        for (var k = 0; k < lineSlugs.length; k++) {
            var entry = colData[lineSlugs[k]];
            if (entry && entry.is_signature) colHasSig = true;
        }
```

Change to:

```javascript
        for (var k = 0; k < lineSlugs.length; k++) {
            var entries = colData[lineSlugs[k]];
            if (entries && entries.length > 0 && entries[0].is_signature) colHasSig = true;
        }
```

**Step 3: Commit**

```bash
git add webapp/static/js/matchup.js
git commit -m "feat: render multiple units per line card with side-by-side layout"
```

---

### Task 5: Add CSS for multi-unit layout

**Files:**
- Modify: `webapp/static/css/matchup.css`

**Step 1: Add multi-unit styles**

Add after the `.line-unavailable` block:

```css
/* --- Multi-unit layout (2+ units in same line) --- */
.unit-wrap.multi-unit {
    display: flex;
    flex-direction: column;
    gap: 2px;
}
.unit-wrap.multi-unit .unit-badge {
    display: flex;
    align-items: center;
    gap: 6px;
}
```

The unit badges already stack vertically by default. The `multi-unit` class just ensures consistent spacing when there are 2+ badges in the same line section.

For the side-by-side icon display within each badge, the existing `.unit-badge` layout already places icon and info side by side (icon left, name+score right). No additional changes needed — each badge renders its own icon at the same size.

**Step 2: Commit**

```bash
git add webapp/static/css/matchup.css
git commit -m "feat: add multi-unit line card CSS styles"
```

---

### Task 6: Run full pipeline and verify

**Step 1: Regenerate civ_power_units.json**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer && source venv/bin/activate && cd webapp && python3 best_units.py
```

**Step 2: Validate JSON structure**

```bash
python3 -c "
import json
d = json.load(open('civ_power_units.json'))
errors = []
multi_count = 0
for civ, ages in d.items():
    for age_key in ['castle', 'imperial']:
        info = ages[age_key]
        for col, lines in info['power_units'].items():
            for line, entries in lines.items():
                if entries is None:
                    continue
                if not isinstance(entries, list):
                    errors.append(f'{civ}/{age_key}/{col}/{line}: not a list')
                elif len(entries) > 1:
                    multi_count += 1
if errors:
    for e in errors[:5]:
        print('ERROR:', e)
else:
    print(f'All 50 civs valid. {multi_count} multi-unit lines found.')
"
```

Expected: ~41 multi-unit lines, no errors.

**Step 3: Start webapp and visually verify**

```bash
PORT=5003 python3 app.py &
sleep 5
curl -s http://localhost:5003/api/civ-power-units/Lithuanians | python3 -c "
import json, sys
d = json.load(sys.stdin)
knight = d['power_units']['cavalry']['knight']
print(f'Knight line: {len(knight)} units')
for u in knight:
    print(f'  {u[\"unit_name\"]} - {u[\"percentile\"]:.0f}th - {u[\"strength\"]}')
"
```

Expected: 2 units — Elite Leitis and Paladin, each with their own percentile.

**Step 4: Spot-check 3 more civs**

- **Britons**: archer line should have 2 units (E. Longbowman + Arbalester)
- **Aztecs**: militia line should have 2 units (E. Jaguar Warrior + Champion)
- **Mongols**: cav_archer line should have 2 units (E. Mangudai + Heavy CA)

**Step 5: Commit regenerated data**

```bash
git add webapp/civ_power_units.json
git commit -m "data: regenerate civ_power_units.json with multi-unit arrays"
```

"""Shared civilization identity and presentation metadata, never combat rules."""
import json
from functools import lru_cache
from pathlib import Path
from .database import connect_readonly

@lru_cache(maxsize=1)
def presentation():
    return json.loads((Path(__file__).resolve().parents[3] / 'aoe2x/assets/presentation.json').read_text(encoding='utf-8'))

@lru_cache(maxsize=4)
def site_catalog(reference_path):
    conn = connect_readonly(reference_path)
    try:
        civs = [row[0] for row in conn.execute('SELECT DISTINCT civ_name FROM ref_units ORDER BY civ_name')]
    finally:
        conn.close()
    return {'schema_version':1, 'civilizations':civs, **presentation()}

def building_for_unit(unit, column, line):
    if unit.get('is_unique'):
        override = presentation()['unique_buildings'].get(unit.get('unit_name'))
        if override:
            return override.lower().replace(' ', '_')
        return 'dock' if column == 'navy' or line == 'cannon_galleon' else 'castle'
    if column == 'infantry': return 'barracks'
    if column == 'cavalry': return 'stable'
    if column == 'navy' or line == 'cannon_galleon': return 'dock'
    if line == 'trebuchet': return 'castle'
    if column == 'siege' or line == 'scorpion': return 'siege_workshop'
    return 'archery_range'

def grouped_units(analysis):
    grouped = {}
    for column in ('cavalry', 'ranged', 'infantry', 'siege', 'navy'):
        for line, units in (analysis.get('power_units', {}).get(column) or {}).items():
            for unit in units or []:
                grouped.setdefault(building_for_unit(unit, column, line), []).append(unit)
    return grouped

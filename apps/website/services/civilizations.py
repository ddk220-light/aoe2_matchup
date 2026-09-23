"""One source for the civilization API and its crawlable HTML projection."""
import json
from copy import deepcopy
from pathlib import Path

from aoe2x.advisor.best_units import load_civ_power_units


_PAGE_COLUMNS = ('cavalry', 'ranged', 'infantry', 'siege', 'navy')
_SUPPLEMENT_PATH = Path(__file__).resolve().parents[1] / 'static/data/civilizations-185872.json'


def load_civilization_supplement(path=None):
    """Read the scoped page reference release without changing ranking inputs."""
    return json.loads(Path(path or _SUPPLEMENT_PATH).read_text(encoding='utf-8'))


def civilization_page_names(reference_names, supplement):
    return sorted(set(reference_names) | set(supplement['civilizations']))


def compose_civilization_analysis(name, age, baseline, supplement):
    """Overlay reference rows on one page analysis, retaining any actual ranks."""
    result = deepcopy(baseline)
    release = supplement['civilizations'].get(name)
    if not release:
        return result

    result.setdefault('civ_name', name)
    result.setdefault('age', age)
    source_columns = baseline.get('power_units') or {}
    existing = {}
    for lines in source_columns.values():
        for rows in lines.values():
            for row in rows or []:
                slug = row['unit_slug'].removesuffix('_' + name.lower())
                existing[slug] = row

    if release['complete_roster']:
        result['power_units'] = {column: {} for column in _PAGE_COLUMNS}
    else:
        result.setdefault('power_units', {column: {} for column in _PAGE_COLUMNS})
    columns = result['power_units']
    replaced = set(release['remove_slugs']) | {row['unit_slug'] for row in release['units']}
    if 'cavalry_archer' in replaced:
        replaced.add('cav_archer')
    if 'heavy_cavalry_archer' in replaced:
        replaced.add('heavy_cav_archer')
    for lines in columns.values():
        for line in list(lines):
            if lines[line] is None:
                continue
            lines[line] = [row for row in lines[line]
                           if row['unit_slug'].removesuffix('_' + name.lower()) not in replaced]
            if not lines[line]:
                del lines[line]

    for reference_row in release['units']:
        slug = reference_row['unit_slug']
        ranked = existing.get(slug)
        if ranked is None and name == 'Vikings':
            alias = {'longship': 'longboat', 'elite_longship': 'elite_longboat'}.get(slug)
            if alias:
                ranked = existing.get(alias)
        row = deepcopy(ranked) if ranked is not None else {}
        row.update(deepcopy(reference_row))
        columns.setdefault(reference_row['column'], {}).setdefault(reference_row['line_slug'], []).append(row)

    if release['description']:
        result['strategic_description'] = release['description']
    if release['emblem_url']:
        result['emblem_url'] = release['emblem_url']
    return result

def civilization_analysis(name, age='imperial', *, build_number=None):
    return _analysis_from_data(load_civ_power_units(build_number=build_number), name, age)


def civilization_page_analysis(name, age='imperial', *, build_number=None, supplement=None):
    supplement = supplement or load_civilization_supplement()
    data = load_civ_power_units(build_number=build_number)
    return _page_analysis_from_data(data, name, age, supplement)


def _page_analysis_from_data(data, name, age, supplement):
    if not data:
        raise FileNotFoundError('civ_power_units/<build>.json not found')
    if name in data:
        baseline = _analysis_from_data(data, name, age)
    elif name in supplement['civilizations'] and supplement['civilizations'][name]['complete_roster']:
        baseline = {'civ_name': name, 'age': age, 'power_units': {}}
    else:
        raise LookupError(f"Civilization '{name}' not found")
    return compose_civilization_analysis(name, age, baseline, supplement)

def _analysis_from_data(data, name, age):
    if not data:
        raise FileNotFoundError('civ_power_units/<build>.json not found')
    if name not in data:
        raise LookupError(f"Civilization '{name}' not found")
    if not data[name].get(age):
        raise LookupError(f'No {age} data for {name}')
    return {'civ_name':name, 'age':age, **data[name][age]}

def civilization_overview(names, *, build_number=None, supplement=None):
    supplement = supplement or load_civilization_supplement()
    data = load_civ_power_units(build_number=build_number)
    out = []
    for name in names:
        try:
            analysis = _page_analysis_from_data(data, name, 'imperial', supplement)
        except (FileNotFoundError, LookupError):
            analysis = {}
        roles = []
        for key, label in [('cavalry','Cavalry'),('ranged','Ranged'),('infantry','Infantry'),('siege','Siege'),('navy','Navy')]:
            units = []
            for entries in (analysis.get('power_units', {}).get(key) or {}).values():
                for entry in entries or []:
                    slug = entry.get('unit_slug') or ''
                    units.append({'name':entry.get('unit_name') or slug.replace('_',' ').title(), 'slug':slug,
                                  'tier':(entry.get('tier') or entry.get('strength') or '').title(),
                                  'is_unique':bool(entry.get('is_unique'))})
            if units: roles.append({'label':label, 'units':units})
        out.append({'name':name,'slug':name.lower(),'description':analysis.get('strategic_description') or '',
                    'emblem_url': analysis.get('emblem_url') or '', 'roles':roles})
    return out

"""One source for the civilization API and its crawlable HTML projection."""
from aoe2x.advisor.best_units import load_civ_power_units

def civilization_analysis(name, age='imperial', *, build_number=None):
    data = load_civ_power_units(build_number=build_number)
    if not data:
        raise FileNotFoundError('civ_power_units/<build>.json not found')
    if name not in data:
        raise LookupError(f"Civilization '{name}' not found")
    if not data[name].get(age):
        raise LookupError(f'No {age} data for {name}')
    return {'civ_name':name, 'age':age, **data[name][age]}

def civilization_overview(names, *, build_number=None):
    out = []
    for name in names:
        try:
            analysis = civilization_analysis(name, build_number=build_number)
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
        out.append({'name':name,'slug':name.lower(),'description':analysis.get('strategic_description') or '', 'roles':roles})
    return out

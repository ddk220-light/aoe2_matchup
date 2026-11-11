"""Page projections for the Astro site: head metadata, JSON-LD and HTML fragments.

Each builder returns exactly what the export scripts publish for one page.
Long fragments and JSON-LD come from the verbatim snippets in ``templates/``;
everything else is plain Python. Pages served by the static build use the
production host for the robots policy; the remaining pages (matchups, advisor,
patches, /vs/) are built for SITE_URL's host, as they always were.
"""
import json
import re

from . import config
from .content import UNIT_LINE_PAGES
from .data import load_unit_for_landing, matchup_groups, popular_matchup_links, rankings_overview
from .metadata import head, website_json_ld
from .patches import get_patch_overview, patch_index, patch_unit
from .sources import (GOLDEN_DIR, REF_DB_PATH, SIM_REF_DB_PATH, advisor_catalog, civilization_overview,
                      load_civilization_supplement, load_published_methods, page_civilizations,
                      published_ranking_release, site_catalog, unit_line_data)
from .templating import json_ld, render, render_string


def _section(html, identifier):
    return re.search(r'<section id="%s".*?</section>' % identifier, html, re.S).group()


def _plain(value):
    """The value as page JavaScript sees it after ``tojson`` (JSON types only)."""
    return json.loads(json.dumps(value))


def civilization_count():
    return len(page_civilizations())


def simulation_civilization_count():
    return len(site_catalog(SIM_REF_DB_PATH)['civilizations'])


def civilization_emblems():
    return {name: civ['emblem_url'] for name, civ in load_civilization_supplement()['civilizations'].items()}


# ---- /about ---------------------------------------------------------------

def about():
    count = civilization_count()
    title = 'How AoE2 Matchup works — data & simulation methodology'
    description = (f'How AoE2 Matchup works: unit data extracted from the Age of Empires II:DE game files, '
                   f'fully-upgraded stats for all {count} civilizations, and 7,600 selected simulation runs '
                   f'behind the finalized land rankings.')
    page = head('/about', title, description,
                json_ld('about.jsonld.html', site_url=config.site_url(), civilization_count=count))
    html = render('about.html', civilization_count=count,
                  civilization_reference_build=load_civilization_supplement()['reference_build'],
                  ranking_release=published_ranking_release(GOLDEN_DIR))
    page['style'] = re.search(r'<style>(.*?)</style>', html, re.S).group(1)
    page['body'] = html.split('</style>', 1)[1].strip()
    # The shared civilization/presentation catalog every interactive page loads.
    page['catalog_script'] = render_string('window.SITE_CATALOG = {{ site_catalog | tojson }};',
                                           site_catalog=site_catalog(REF_DB_PATH))
    return page


# ---- /civilizations -------------------------------------------------------

def civilizations_frame():
    civs = page_civilizations()
    title = f'AoE2 Civilizations — Strengths, power units & strategic identity for all {len(civs)} civs'
    description = (f'Detailed Age of Empires II civilization breakdowns: power units, unique techs, civ bonuses, '
                   f'and the matchup-tested strengths of all {len(civs)} civilizations including Three Kingdoms.')
    structured = website_json_ld(len(civs)) + json_ld(
        'civilizations.jsonld.html', site_url=config.site_url(), civ_overview=civilization_overview())
    return head('/civilizations', title, description, structured)


def civilization_head(civ):
    """``civ`` is one civilization overview entry (name, slug, description)."""
    first_sentence = (civ['description'].split('. ')[0].strip().rstrip('.') + '.') if civ['description'] else ''
    description = (f"{civ['name']} in Age of Empires II — strongest fully-upgraded "
                   f"units by role, tiers, and strategy. {first_sentence}").strip()[:250]
    structured = website_json_ld(civilization_count()) + json_ld(
        'civilization.jsonld.html', site_url=config.site_url(), civ=civ)
    return head('/civilizations/' + civ['slug'], f"{civ['name']} — AoE2 Civilization: Best Units & Strategy",
                description, structured)


# ---- /units ---------------------------------------------------------------

def rankings_frame(overview=None):
    overview = rankings_overview() if overview is None else overview
    title = 'AoE2 Unit Rankings — Best units by class, simulated head-to-head'
    description = ('Age of Empires II unit rankings derived from population- and cost-balanced battle simulations. '
                   f'Compare every unit at full upgrades across all {civilization_count()} civilizations and see '
                   'which units actually dominate their class.')
    structured = website_json_ld(civilization_count()) + json_ld('rankings.jsonld.html', rankings_overview=overview)
    return head('/units', title, description, structured)


def rankings_overview_section(overview=None):
    """The server-rendered "Rankings at a glance" section of /units."""
    overview = rankings_overview() if overview is None else overview
    html = render('rankings_overview.html', rankings_overview=overview,
                  ranking_release=published_ranking_release(GOLDEN_DIR),
                  unit_line_pages=[(page['url'], page['short']) for page in UNIT_LINE_PAGES])
    return _section(html, 'rankings-ssr')


def ranking_methods():
    """RANKING_METHODS: the published score methodology per category."""
    return _plain(load_published_methods(GOLDEN_DIR))


def unit_line_head(page, line=None):
    """``page`` is a UNIT_LINE_PAGES entry; ``line`` its unit-line projection."""
    line = unit_line_data(page['line']) if line is None else line
    structured = website_json_ld(civilization_count()) + json_ld(
        'unit_line.jsonld.html', site_url=config.site_url(), page=page, line=line)
    return head('/units/' + page['url'], page['title'], page['desc'], structured)


# ---- / (battle simulator) -------------------------------------------------

def simulator_frame():
    title = 'AoE2 Battle Simulator — Compare fully upgraded armies'
    description = (f'Free Age of Empires II battle simulator. Choose supported land units from '
                   f'{simulation_civilization_count()} civilizations and compare armies at full Imperial '
                   f'upgrades in a seeded battle simulation.')
    return head('/', title, description, website_json_ld(civilization_count()))


def simulator_about():
    """The crawlable #home-about section under the simulator."""
    html = render('simulator_about.html', simulation_civilization_count=simulation_civilization_count())
    return _section(html, 'home-about')


def simulator_catalog():
    """SITE_CATALOG of the simulator: its civilizations, presentation names and emblems."""
    return _plain({**site_catalog(SIM_REF_DB_PATH), 'civilization_emblems': civilization_emblems()})


# ---- remaining pages (built for SITE_URL's host) -------------------------

def matchups():
    title = 'AoE2 Unit Matchups — Every unique-unit battle, simulated'
    description = ('Browse published Age of Empires II unit matchups, compare fully-upgraded stats, '
                   'and open supported matchups in the live battle simulator.')
    frame = head('/matchups', title, description, website_json_ld(civilization_count()),
                 stylesheets=['/static/css/matchups.css'], host=config.site_host())
    return {'groups': matchup_groups(), 'popular': popular_matchup_links(), 'frame': frame}


def advisor():
    catalog = advisor_catalog()
    title = 'AoE2 Matchup Advisor — Pick the right counter for every civ matchup'
    description = ('Civ-vs-civ matchup advisor for Age of Empires II. Enter your civ and your opponent, see which '
                   'units to build based on simulated combat results, costs, and counters.')
    frame = head('/matchup-advisor', title, description, website_json_ld(civilization_count()),
                 stylesheets=['/static/css/matchup_advisor.css'], host=config.site_host())
    return {'civs': catalog['civilizations'], 'advisor_catalog': catalog, 'frame': frame}


def patch_hub(path=None):
    patches = patch_index(path)
    description = ('Age of Empires II patch notes tracker: every balance update with per-unit stat changes, '
                   'ranking shifts, and simulated matchup swings.')
    if patches:
        description += f" Latest: {patches[0]['title']} ({patches[0]['release_date']})."
    structured = website_json_ld(civilization_count()) + json_ld(
        'patches.jsonld.html', site_url=config.site_url(), patches=patches)
    frame = head('/patches', 'AoE2 Patch Notes — Age of Empires II Balance Changes by Update', description,
                 structured, host=config.site_host())
    return {'patches': patches, 'frame': frame}


def patch_build(build, path=None):
    """One patch's landing page; None for an unknown build."""
    data = get_patch_overview(build, path)
    if data is None:
        return None
    number, released = data['build_number'], data['release_date']
    description = (f'Full balance changes for Age of Empires II Update {number} ({released}): every unit buffed '
                   f'or nerfed, with the simulated matchup shifts each change caused.')
    structured = json_ld('patch_build.jsonld.html', site_url=config.site_url(), build_number=number,
                         release_date=released)
    frame = head(f'/patches/{build}', f'Age of Empires II Update {number} — Patch Notes & Balance Changes',
                 description, structured, og_type='article', host=config.site_host())
    return {**data, 'frame': frame}


def patch_unit_page(build, civ, unit, path=None):
    """One unit's changes in one patch; None for an unknown build."""
    data = patch_unit(build, civ, unit, path)
    if data is None:
        return None
    patch, name = data['patch'], data['unit_title']
    description = (f"How {patch['title']} changed the {civ} {name} in Age of Empires II — exact stat changes, "
                   f"ranking movement, and which simulated matchups flipped.")
    structured = website_json_ld(civilization_count()) + json_ld(
        'patch_unit.jsonld.html', site_url=config.site_url(), build=build, civ=civ, unit=unit, unit_title=name)
    frame = head(f'/patches/{build}/{civ}/{unit}', f"{civ} {name} — {patch['title']}", description, structured,
                 host=config.site_host())
    return {**data, 'frame': frame}


def matchup_landing_frame(civ_a, unit_a, civ_b, unit_b):
    """Head of a /vs/ landing page; None when either unit is unknown."""
    a, b = load_unit_for_landing(civ_a, unit_a), load_unit_for_landing(civ_b, unit_b)
    if not a or not b:
        return None
    a_name = a.get('unit_name') or unit_a.replace('_', ' ').title()
    b_name = b.get('unit_name') or unit_b.replace('_', ' ').title()
    title = f'{a_name} ({civ_a}) vs {b_name} ({civ_b}) — Who Wins? | AoE2 Simulator'
    description = (f'Simulated 1v1 result for {a_name} ({civ_a}) versus {b_name} ({civ_b}) in '
                   f'Age of Empires II at full upgrades. Stat comparison, costs, armor classes, '
                   f'and a live battle simulator to test it yourself.')
    path = f'/vs/{civ_a}/{unit_a}/{civ_b}/{unit_b}'
    canonical = config.site_url() + path
    structured = json_ld('matchup_landing.jsonld.html', site_url=config.site_url(), canonical_url=canonical,
                         a=a, b=b, a_name=a_name, b_name=b_name, civ_a=civ_a, civ_b=civ_b)
    return head(path, title, description, structured, canonical=canonical, og_type='article',
                host=config.site_host())

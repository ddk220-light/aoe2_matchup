"""The data the page builders share with the API, imported from one place.

Everything here is data access or policy that the Flask API keeps using, so it
stays with the API; the builders never call an HTML route, render a website
template or read a website script. Stage 4 moves the API package and only the
imports in this file need to follow it.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
for _path in (ROOT / 'apps/website', ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from aoe2x.paths import GOLDEN_DIR  # noqa: E402
from aoe2x.rank.methodology import load_published_methods  # noqa: E402
from aoe2x.sim.unit_lines import UNIT_LINES  # noqa: E402
from aoe2x.storage import connect_readonly  # noqa: E402
from apps.website.services.advisor import advisor_catalog  # noqa: E402
from apps.website.services.catalog import grouped_units, site_catalog  # noqa: E402
from apps.website.services.civilizations import (  # noqa: E402
    civilization_page_names, load_civilization_supplement)
from apps.website.services.rankings import LAND_LINES as RANKING_LAND_LINES  # noqa: E402
from apps.website.services.release import published_ranking_release  # noqa: E402
from apps.website.services.seo import indexing_enabled  # noqa: E402

# Same string paths as the API, so its cached catalog lookups are shared.
REF_DB_PATH = str(GOLDEN_DIR / 'aoe2_reference.db')
SIM_REF_DB_PATH = str(GOLDEN_DIR / 'aoe2_reference_simulation.db')
PATCHES_DB_PATH = str(GOLDEN_DIR / 'patches.db')


def api():
    """The API module, for its data helpers (never its HTML routes)."""
    import app
    return app


def page_civilizations():
    return api()._get_page_civs()


def reference_civilizations():
    return api()._get_ref_civs()


def valid_civilizations():
    return api()._valid_civs()


def civilization_overview():
    return api().get_civ_overview_data()


def unit_line_data(line):
    return api().get_unit_line_data(line)

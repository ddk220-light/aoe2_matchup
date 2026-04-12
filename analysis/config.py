"""Re-exports all config constants for backwards compatibility.

The actual definitions now live in:
  - config_constants.py: magic IDs, paths, age/attribute constants
  - config_units.py: unit definitions, stat overrides, building mappings
  - config_combat.py: combat properties (COMBAT_PROPERTIES,
                      UNIQUE_COMBAT_PROPERTIES, CIV_COMBAT_PROPERTIES)

All existing ``from analysis.config import X`` imports continue to work
unchanged via this shim — zero import-churn in consumer modules.

Note: names beginning with ``_`` are not exported by ``*`` imports, so
``_tech_age_name`` and ``_PREVIOUS_AGE_NAMES`` are re-exported explicitly.
"""

from .config_constants import *  # noqa: F401,F403
from .config_units import *      # noqa: F401,F403
from .config_combat import *     # noqa: F401,F403

# Explicit re-exports for underscore-prefixed names excluded from star imports
from .config_constants import _tech_age_name  # noqa: F401
from .config_units import _PREVIOUS_AGE_NAMES  # noqa: F401

"""Battle-simulation engines (layer 4).

Three engines, three jobs (keep behavior-synced — golden tests pin them):
  simulation.py        abstract tick engine — live /api/matchup-sims
  simulation_real.py   position-based 2D engine — ALL batch matchup data
  (frontend canvas)    static/js/simulate.js in the website app
"""
import sys as _sys

from . import battle_outcome as _battle_outcome

# simulation_real.py is hashed byte-for-byte into the matchup-row cache key
# (sim_version.compute_sim_version) and therefore cannot be edited. Its
# `from battle_outcome import BattleOutcome` fallback import resolves through
# this top-level alias, registered before the module body ever runs.
_sys.modules.setdefault("battle_outcome", _battle_outcome)

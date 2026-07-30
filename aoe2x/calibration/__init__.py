"""Combat-calibration pipeline: ingest recorded fight "drops", extract truth
cards, run the JS engine against them, and score how well the engine matches
real Age of Empires II gameplay.

This package is intentionally decoupled from the batch-matchup sim engines
(``aoe2x/sim/simulation_real.py`` / ``aoe2x/dbgen/config_combat.py``) — it
must never modify those files, since they are byte-hashed into the
matchup-row cache key (``aoe2x/sim/sim_version.py``).
"""

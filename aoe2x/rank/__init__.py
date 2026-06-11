"""Unit ranking / pool scoring (layer 4): derive_* jobs reading a matchup
baseline DB and writing the committed derived_data.db / pool_scores.db.

pool_scores_lib.weighted_cost is INTENTIONALLY frozen at wood=0.8 (the
committed pool_scores.db was generated with it) — do not unify with
aoe2x.sim.simulation_real.weighted_cost (wood=0.7).
"""

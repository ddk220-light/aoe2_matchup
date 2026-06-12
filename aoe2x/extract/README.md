# aoe2x/extract — .dat extraction (layer 2, patch-dependent)

**In:** `data/inputs/empires2_x2_p1.dat` (copy from your AoE2:DE install).
**Out:** 8 JSONs in `data/inputs/extracted_data/` (units, technologies,
tech_ages, civilizations, armor_classes, effects, tech_effects,
civ_tech_trees).
**Run:** `python -m aoe2x.extract.run` (~10s; needs `genieutils-py` — use
the conda python, it is in neither requirements file).
**Consumed by:** `aoe2x.dbgen.generate_reference`.

Standalone use: the JSONs are plain, readable game data — nothing else in
the repo is needed to use them.

Patch sensitivity: TOTAL. Every game build changes counts/values; new units
may need `UNIT_NAMES`/`CIV_NAMES` updates in `extract_constants.py` /
`extract_units.py`. Follow `docs/architecture/runbooks.md` §1.

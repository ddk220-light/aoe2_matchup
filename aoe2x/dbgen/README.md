# aoe2x/dbgen — golden-database generators (layer 3)

**In:** `data/inputs/extracted_data/*.json` (from aoe2x.extract) + the
hand-curated config layers (`config_units.py` availability,
`config_combat.py` combat properties — BYTE-HASHED into sim_version, do not
touch outside a planned re-sim, `config_constants.py`).
**Out:** `data/golden/aoe2_reference.db` (the DB the apps serve, with a full
`ref_stat_chain` audit trail) and legacy-but-live `aoe2_units.db`.
**Run:**

```bash
python -m aoe2x.dbgen.generate_reference   # ~30s
python -m aoe2x.dbgen.generate_main_db     # ~2s
python aoe2x/dbgen/patches/patch_mayan_archer_cost.py   # surgical post-fix (idempotent)
```

Effect order (later wins): extracted dat → COMBAT_PROPERTIES →
UNIQUE_COMBAT_PROPERTIES → CIV_COMBAT_PROPERTIES.

`ability_registry.py` is the canonical list of combat-ability params — the
ref-DB schema/writer and `aoe2x/sim/combat_unit_loader.py` are GENERATED
from it (add an ability: registry entry + one handler per engine; runbooks §3).

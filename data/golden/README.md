# data/golden — the committed golden artifacts (layer 3)

These files ARE the deployment mechanism: the website serves whatever is on
the branch. Regenerate → commit → smoke-test → promote. They are also
published per game build as GitHub Releases (`data-v<build>`,
`tools/publish_data_release.ps1`).

| Artifact | Producer | Read by | Regenerate on patch? |
|---|---|---|---|
| `aoe2_reference.db` | `python -m aoe2x.dbgen.generate_reference` (+ surgical `aoe2x/dbgen/patches/*.py`) | every stat page/API, `combat_unit_loader`, batch runners | ALWAYS |
| `aoe2_units.db` | `python -m aoe2x.dbgen.generate_main_db` | `/units` page + `unit_verifications` badges (NOT dead — see docs/architecture/webapp.md) | ALWAYS |
| `derived_data.db` | `python -m aoe2x.rank.derive_unit_rankings --matchup-db <baseline> --build <N>` (+ `derive_siege_scores`) | rankings/role scores on civ + unit-line APIs | on patch |
| `pool_scores.db` | `python -m aoe2x.rank.derive_pool_scores --matchup-db <baseline> --build <N>` | rankings page pool payloads | on patch |
| `patches.db` | `python -m aoe2x.batch.patch_pipeline` | patch tracker pages; `get_current_build()` resolves the live build for every score lookup | each patch |
| `civ_power_units/<build>.json` | `aoe2x.advisor.best_units.save_civ_power_units('<build>')` | matchup advisor rosters | on patch |
| `civ_top_units.json` | `python -m aoe2x.advisor.top_units` | top-unit APIs / frontpage | on availability change |
| `civ_matchups_first_pass.db` | saved matchup evidence, updated in place by `scripts/apply_advisor_*.py` (latest: `apply_advisor_inferred_resim.py`, 2026-11-13: the 19,647 formerly rule-inferred cells now carry the PC re-simulation from `matchup-runs` 72d55423f, so every non-identity cell is simulated; report `civ_matchups_first_pass.inferred-resim.json`) | `/api/advisor-*`, the static advisor export | when new matchup runs are published (keep < 100 MiB) |
| `advisor_cell_metrics.json.gz` | `tools/economy/advisor_eco/build_advisor_metrics.py` (runbooks: "Advisor eco metrics") | `/api/advisor-matchups/<civ>` eco fields, `/api/advisor-catalog` `full_research_vm` | whenever `civ_matchups_first_pass.db` or the army-economics artefact changes |

Sources upstream: the matchup baseline (`D:/AI/matchup_baseline_<build>.db`,
not committed — too big; in the release assets) is produced by
`pypy3 -m aoe2x.batch.rebuild_matchup_baseline` from `aoe2_reference.db` +
`aoe2x/sim/simulation_real.py`. Rows are cache-keyed by `sim_version`
(byte-hash of simulation_real.py + config_combat.py) and re-simmed when the
engine changes.

Full pipeline + runbooks: `docs/architecture/runbooks.md` §1.

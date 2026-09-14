# Production correctness audit — 2026-09-11

Production is paused by the user. Do not resume stale suspended workers.

The read-only audit and repair inventory are in `data/local/production-audit/report.md` and `repair-plan.json`. These cover 1256 archived recorded plans, 1116 chapters in16 retained final compilations, and160 selected Shorts. 305 compiled chapters require cost-based retakes; other chapters are reuse candidates subject to broader stat/timing review.

## Root causes fixed

- Lab used registry baseCost rather than civilization-specific Imperial purchase cost.
- UnitAnalyzer ignored absolute SET_ATTRIBUTE food/wood/gold effects.
- Production batch size and population were not explicitly separated. Blackwood buys two physical units for35W45G; individual cost17.5W22.5G. Karambit is purchased singly despite half-population usage.

`data/recording-costs.json` is generated from isolated installed-DAT extraction by `scripts/audit_recording_costs.py`. It retains purchase and per-individual costs and effect evidence. JS Lab planning resolves these costs and embeds the catalog hash. `aoe2x/lab/costs.py` rejects stale/base-price capture plans. Old job IDs remain immutable; corrected captures need new IDs. Direct and batch YouTube upload entry points reject the saved pause/audit hold before accessing credentials or the API.

## Audit reproduction

1. Export UNIT_REGISTRY from JS to data/local/cost-audit-registry.json.
2. Extract installed DAT via aoe2x.extract.run.extract_all into data/local/cost-audit-extracted (do not replace golden DBs).
3. Run scripts/audit_recording_costs.py; installed DAT provenance is saved in the audit folder.
4. Run scripts/audit_recording_setup.py with apps/video on PYTHONPATH.
5. Run scripts/finalize_production_audit.py after the initial-HP evidence check.

## Release hold

Retain full originals and all frames. Do not upload or clean up while costBasisReview is REQUIRED_BEFORE_PENDING_UPLOADS. The remaining Mameluke120vs125HP issue is an effect-order discrepancy, not a reason to override actual game results. Independently verify actual researched stats and overlay alignment before claiming every gameplay condition is certified. No live acceptance runs were authorized during this pause. Resume only after the audit hold is resolved and the user resumes production.

# Sub-1% farming validation status

**Not achieved across the tested cases.** No engine parameters were changed in this pass.

- Existing six-case benchmark: three cases below 1%, largest discrepancy 3.533%.
- Additional independent 36-set test (286 usable observations): adjacent group +0.835%, corner group +2.897%. See [comparison](README.md). The source does not explain how its Folwark bonus was excluded, so this remains a conditional comparison.
- 192 diagnostic runs show that removing collisions or starting with a full farm buffer does not resolve the errors together. See [error budget](error-budget.md).
- All 11 existing mechanical regression checks pass. Resource conservation, time accounting, collision bounds and speed bounds pass in all new simulations.
- Four DE scenarios have been generated and parsed back, with coordinates, research IDs and unit counts verified. **They have not been executed in DE.** This workspace has no DE executable or relevant live farmer capture. See [capture protocol](de-capture/README.md).

The scenarios use native construction after selected upgrades, which avoids guessing how finished scenario-editor farms inherit food-capacity effects. Actual construction completion, farm food and worker positions must be checked in the recording before calculating errors. An in-game capture is needed to distinguish incorrect movement mechanics from differing benchmark conditions; another empirical multiplier would not establish accuracy.

All previous results and the serving database are preserved. Reproduce the statistical comparisons with `node tools/audit_farm_repeated_reference.mjs` and `node tools/check_farm_error_budget.mjs`. Generate scenarios with `AoE2ScenarioParser==0.9.9` using `tools/build_farm_validation_scenarios.py`.

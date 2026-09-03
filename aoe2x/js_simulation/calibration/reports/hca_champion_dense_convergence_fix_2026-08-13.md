# HCA-versus-Champion dense convergence result

## Outcome

The cohesive Heavy Cavalry Archer versus Champion engine now completes all five authorized golden-tape rosters. All five deterministic simulation runs select the same winner as the tape. The two dense cases that previously failed at the collision-convergence guard, 15v20 and 20v20, now finish normally without relaxing the published collision geometry.

| HCA vs Champion | Tape median | Simulation | Signed outcome delta | Duration delta |
|---|---|---|---:|---:|
| 5v10 | Champion, 316 HP, 41.076 s | Champion, 320 HP, 38.117 s | -0.57 points | -2.959 s |
| 10v5 | HCA, 787 HP, 14.912 s | HCA, 735 HP, 15.700 s | -6.50 points | +0.788 s |
| 15v20 | HCA, 674 HP, 49.782 s | HCA, 873 HP, 35.750 s | +16.58 points | -14.032 s |
| 20v15 | HCA, 1,522 HP, 24.620 s | HCA, 1,390 HP, 21.867 s | -8.25 points | -2.753 s |
| 20v20 | HCA, 1,349 HP, 35.726 s | HCA, 1,325 HP, 27.767 s | -1.50 points | -7.959 s |

Score is winner remaining HP divided by that side's starting HP, expressed in percentage points. HCA is positive and Champion is negative. Simulation minus tape median is the signed outcome delta.

The five-row summary is:

- Completed ratios: **5/5**.
- Correct winners: **5/5**.
- Winner HP inside the five-repeat tape range: **2/5**.
- Duration inside the tape range: **2/5**.
- Survivor count inside the tape range: **4/5**.
- Median absolute outcome delta: **6.50 points**.
- Mean absolute outcome delta: **6.68 points**.

## Engine change

The repair keeps the existing HCA mechanics, cohesive kiting policy, preventive contact-graph steering, attack behavior, and collision dimensions. It changes only collision/navigation execution:

- the deterministic hard-constraint solver may continue for up to 4,096 sweeps in dense contact instead of stopping at 256;
- hard enemy and obstacle constraints no longer skip a real correction because it is smaller than the validation epsilon;
- symmetric local detours receive a deterministic per-unit side choice;
- a locally certified tangent step is used when a full detour cannot yet be certified through the crowd;
- an already-reached attack goal cancels a stale pursuit step.

No unit-stat, damage, reload, attack-delay, or outcome-fitting values changed. No Scorpion-specific fallback is included.

## Source and reproduction

The source is the authorized project-local `aoe2_golden_kiting_hcavarchervschampion_2026-08-06.zip`, SHA-256 `EB47F418B2D88BFB99D0083CF05DE153B329D531B0E179494DAE1A5CA3D921C5`, with five tape repeats per roster.

Run the same HCA-only comparison with:

```powershell
node aoe2x/js_simulation/calibration/analysis/hca_champion_current_outcomes_2026-08-13.mjs
```

Focused regression coverage is in `tests/local-avoidance.test.mjs` and the HCA cases in `tests/server.test.mjs`.

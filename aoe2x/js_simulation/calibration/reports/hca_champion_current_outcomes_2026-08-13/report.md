# Current cohesive HCA-versus-Champion outcome comparison

## Technical summary

The preventive-contact engine is promising, but it is not yet validated across the complete five-ratio corpus. All three ratios that completed selected the same winner as all five tape repeats. Across those completed ratios, the median absolute end-state gap is **6.50 percentage points** of the winner side's starting HP and the mean is **6.68 points**.

The visually reviewed 5 HCA versus 10 Champion case is materially closer than the immediate pre-change engine: the current result is a Champion win with 262 HP after 44.00 seconds, versus the tape median of 316 HP after 41.08 seconds. Remaining HP is inside the tape's 256–344 range, duration misses the tape maximum by only 0.166 seconds, no four-Champion contact clique forms, and compact triples fall from the previous engine's 31.88% of frames to 7.12%. It is still too favorable to HCA in survivor count: four Champions remain versus six to eight on tape.

Two denser cases do not produce an outcome. The 15v20 and 20v20 viewer runs terminate at the deterministic collision-convergence guard with tiny residual unit/obstacle overlaps. These are real engine failures, not tape uncertainty, and are kept out of the aggregate error calculation.

## Key findings

| HCA vs Champion | Tape: winner, median HP (range) | Current simulation | Outcome delta | Duration delta | Assessment |
|---|---|---|---:|---:|---|
| 5v10 | Champion, 316 (256–344) | Champion, 262 HP, 4 survivors, 44.00 s | 7.71 pts toward HCA | +2.92 s (+7.12%) | Correct winner; HP in tape range; duration 0.166 s above tape maximum; survivor count below range |
| 10v5 | HCA, 787 (787–800) | HCA, 735 HP, 10 survivors, 15.70 s | 6.50 pts toward Champion | +0.79 s (+5.28%) | Correct winner and survivor count; HP 52 below range; duration 0.154 s above tape maximum |
| 15v20 | HCA, 674 (598–834) | No result | — | — | Collision solver did not converge after 256 sweeps |
| 20v15 | HCA, 1,522 (1,481–1,587) | HCA, 1,429 HP, 19 survivors, 21.93 s | 5.81 pts toward Champion | −2.69 s (−10.91%) | Correct winner; duration and survivor count in tape ranges; HP 52 below range |
| 20v20 | HCA, 1,349 (1,176–1,418) | No result | — | — | Collision solver did not converge after 256 sweeps |

The exact completed-run scorecard is:

- Correct winner: **3/3 completed**.
- Remaining winner HP inside tape range: **1/3**.
- Duration inside tape range: **1/3**.
- Survivor count inside tape range: **2/3**.
- Median absolute signed-outcome delta: **6.50 points**.
- Mean absolute signed-outcome delta: **6.68 points**.
- Mean absolute duration error: **7.77%**.

## Scope, data, and metric definitions

The tape side is the authorized project-local `aoe2_golden_kiting_hcavarchervschampion_2026-08-06.zip`, SHA-256 `EB47F418B2D88BFB99D0083CF05DE153B329D531B0E179494DAE1A5CA3D921C5`. It contains five repeats for each of 5v10, 10v5, 15v20, 20v15, and 20v20.

The simulation side is one deterministic run per ratio through the exact viewer endpoint: Heavy Cavalry Archer as owner 2, Champion as owner 3, cohesive navigation, tape-derived ratio placement, attack-move chasers, zero melee engagement dwell, and preventive contact-graph steering enabled.

The signed outcome score is remaining winner HP divided by that winner side's starting HP, expressed in percentage points. HCA wins are positive and Champion wins are negative. This preserves both winner identity and victory margin in one measure. “Outcome delta” is current simulation minus tape median; the table translates its direction into the unit favored by the difference.

## Methodology

The reproducible analysis starts an in-process copy of the same local map server used by the viewer and calls `/api/ranged-vs-melee-kiting` once for each recorded ratio. It verifies the requested side counts and `preventive-contact-graph` mode before accepting a run. Winner, remaining HP, survivor count, and ticks come directly from the returned battle and terminal snapshot. Tape medians and ranges are computed over the five authorized fixture rows for the same ratio.

For completed simulations, the script also reconstructs Champion contact graphs at the 0.40-tile allied envelope while both sides remain alive. This confirms that the 5v10 visual improvement is represented in the engine output: maximum clique three, zero frames with a four-unit clique, 7.12% compact-triple frame share, and a 0.75-second longest compact-triple episode.

## Limitations and confidence

Confidence is **high** in the three reported simulation outcomes because the engine path is deterministic and the analysis consumes the viewer response directly. Confidence is **high** that 15v20 and 20v20 currently fail: both return their exact solver diagnostics from the same endpoint.

Confidence is only **moderate** that the completed-ratio error summarizes the engine as a whole. The two missing ratios are the denser cases and could materially change the aggregate result. A single deterministic simulation is also compared with a five-repeat tape distribution; range membership is therefore more informative than implying sampling uncertainty on the simulation side.

## Recommended next steps

Keep the preventive steering change. Its 5v10 crowd shape and completed-ratio outcomes are strong enough to retain. Treat the dense-ratio collision convergence as the next bounded blocker before further outcome calibration. Do not tune damage, reload, movement speed, or desired winners from these results: first make 15v20 and 20v20 complete under the same physical setup, then rerun this unchanged report and judge all five end states.

## Further questions

- Do the dense failures disappear by allowing the existing constraint iteration to finish, without changing any collision tolerance or published movement geometry?
- Once all five ratios complete, does the mean outcome error remain near seven points, or are the missing dense cases systematically biased?
- Can compact-triple share be reduced from 7.12% toward the 5v10 tape's 1.05% without sacrificing the improved engagement flow?

## Reproduction

Run:

```powershell
node aoe2x/js_simulation/calibration/analysis/hca_champion_current_outcomes_2026-08-13.mjs
```

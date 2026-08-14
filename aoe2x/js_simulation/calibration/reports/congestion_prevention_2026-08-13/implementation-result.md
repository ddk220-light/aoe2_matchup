# Preventive contact-graph steering: 5 HCA vs 10 Champion result

## Scope

This is the focused implementation follow-up to `report.html`. The engine run is the exact-placement cohesive ranged-versus-melee viewer scenario with 5 Heavy Cavalry Archers and 10 Champions. No combat timing, damage, reload, attack-delay, seed, or outcome parameter was changed.

The implementation is scenario-gated and enabled by the viewer. It projects the allied contact graph one collision width along the already-computed movement headings, keeps direct movement for clear lanes and one-edge chain attachment, and selects the smallest full-speed lateral turn when the direct heading would close a triangle or create a compact four-unit clique. Existing local-avoidance state remains the only persistent side choice.

## Results

| Measure | Pre-change sim | Preventive sim | 5v10 tape |
|---|---:|---:|---:|
| Frames with a compact Champion triple | 31.88% | 7.12% | 1.05% |
| Maximum compact clique | 4 | 3 | 3 |
| Longest compact-triple episode | 10.03 s | 0.75 s | 0.41 s |
| New contacts closing a triangle | 34.83% | 15.97% | 4.78% |
| Frames with contact component of 4+ | 50.85% | 34.36% | 9.82% |
| Battle result | Champion, 210 HP at 2,999 ticks | Champion, 262 HP at 2,640 ticks | downstream only |

The compact-triple frame share fell by 77.7%, the longest compact episode fell by 92.5%, and four-unit compact cliques disappeared. Large connected components remain more common than tape, but they are now chains rather than four-unit stacks. The remaining 6.07-point triple-share and 11.18-point triangle-closure gaps mean this is a substantial improvement, not final tape parity.

## Rejected variant

Persisting a contact-detour side beyond the immediate local-avoidance geometry made congestion worse. Full target-lifetime persistence raised compact-triple frames to 13.24%; persistence limited to a continuous congestion episode still raised them to 8.17% and extended the longest episode to 1.12 seconds. Those variants were removed. This is why the final planner remains deterministic but does not add a second long-lived steering state.

## Verification

- `node --test tests/contact-graph-steering.test.mjs`
- Focused `target-state.test.mjs` scenario-gating test
- Focused `server.test.mjs` exact 5v10 viewer and debug-UI tests
- `node calibration/analysis/congestion_prevention_2026-08-13.mjs`

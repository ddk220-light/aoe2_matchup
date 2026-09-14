# Naval counter spike

The user-authored `water_map.aoe2scenario` is saved as `apps/video/templates/lab_goldens/water_map.aoe2scenario` and registered as the `water` Golden family. The source in the game scenario folder was not edited. SHA-256: `60e93202f138b3bc3d1b224fe1d35b72b4757728088bffd11c32d5cdc4fd5d1e`.

The 16x16 map preserves the authored camera at (8,7), first-N placement order from 15 slots per side, initial patrol orders, diplomacy, AI, and Post-Imperial starting age. P2/P3 civilizations and ship types are substituted; P1 matches P3 for music. There is no P4 army. The same template can be reused for other civilizations by supplying their specific ship variant in the recording catalogue.

This is capture-only. Naval simulation is explicitly rejected by runSeed. Raw gameplay, frames.bin, per-run scenario, checksums, HP sidecar, battle clip, and validation metadata are retained for later simulation development.

## Resource rules

Food + wood + gold have equal weight. The cheaper ship receives up to 15 units, subject to a 5,000-resource ceiling per army; the other count is floored to the affordable number at the same budget. Counts cannot exceed 15. Unit prices use civilization-specific Imperial final costs from ref_units, including discounts and Shipwright. Upgrades are available from the scenario's Post-Imperial start and are not charged to the army budget. All three tests are also below 5,000 resources combined.

| P2 | Unit cost | Count | Army cost | P3 | Unit cost | Count | Army cost |
|---|---:|---:|---:|---|---:|---:|---:|
| Portuguese Galleon | 114 | 15 | 1710 | Bulgarian Fire Ship | 120 | 14 | 1680 |
| Byzantine Fast Fire Ship | 105 | 15 | 1575 | Tupi War Hulk | 110 | 14 | 1540 |
| Portuguese Carrack | 103 | 15 | 1545 | Malian War Galley | 120 | 12 | 1440 |

## Reproduce

Use `aoe2lab.recorder.naval-counter-spike.json` with `python -m aoe2x.lab.recording_campaign MANIFEST --reports OUTPUT`. New experiments should use new job IDs to avoid reusing completed captures. The three naval tests are a specific exception to the capture pause; Champi, Guecha, and Temple Guard remain paused.

## Validation

All three generated scenarios passed roster/position, camera, AI, diplomacy, trigger, and no-P4 checks. Eight Node planner tests passed, covering legacy planning, naval counts, resource ceiling, and rejection of naval simulation. Recorded starting HP is checked against the actual gRPC capture, rather than inferred from a simulated fight.

Results and local video links are recorded in `aoe2x/js_simulation/calibration/lab/campaigns/naval-counter-spike/results.md`. Each result is one observed battle with the authored patrol behavior; it can demonstrate a counter reversal in this setup, but does not identify the exact break-even point or establish behavior under kiting or different formations.

## Armenian follow-up
User requested Armenian Galleons in place of Portuguese versus Bulgarian Fire Ships. Both Imperial final unit costs are120 resources, so counts are15vs15 and1800resources each. Separate manifest aoe2lab.recorder.naval-armenian-galleon.json and job naval_counter_spike_04_galleon_armenians_vs_fire_ship_bulgarians preserve the original Portuguese trial. No simulation and no general land-capture resume.


Armenian follow-up outcome: Bulgarian Fire Ships won with9survivors,837HP (46.5% of starting HP). No counter reversal in this trial. Raw video and frames retained in the separate naval-armenian-galleon campaign.

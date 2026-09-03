# Elite Conquistador versus Arbalester: tape/simulation diagnosis

## Technical summary

This report compares all four authorized Phase 2 golden recordings with five current-engine samples for the exact 12 Elite Conquistador versus 21 Arbalester row. It is diagnostic only; no engine behavior is changed.

- Archive SHA-256: `B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6`
- Geometry cadence: 100 ms
- Tape projectile hits come from the archive's decoded hit attribution; tape releases are inferred from full-rate action episodes that persist through the sourced release frame.

## Same-army overlap

| Unit | Source | Pair overlap share | Unit overlap share | Median depth | Max depth | Frames with overlap | Max pairs | Max neighbor degree | Max component | Attacking while overlapped | Attacking while clear |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Elite Conquistador | Tape | 4.74% (3.27%–5.2%) | 35.22% (25.1%–41.5%) | 0.04 (0.02–0.08) | 0.42 (0.42–0.43) | 81.81% (65.37%–89.5%) | 8 (8–8) | 3 (3–4) | 7 (6–7) | 34.35% (28.18%–36.5%) | 25.08% (24.81%–26.2%) |
| Elite Conquistador | Simulation | 0% (0%–0%) | 0% (0%–0%) | — | — | 0% (0%–0%) | 0 (0–0) | 0 (0–0) | 1 (1–1) | — | 28.89% (25.15%–32.44%) |
| Arbalester | Tape | 1.18% (0.92%–1.3%) | 17.5% (13.49%–19.34%) | 0 (0–0.04) | 0.07 (0.05–0.12) | 72.03% (66.36%–73.49%) | 3.5 (3–5) | 1.5 (1–2) | 2.5 (2–5) | 44.35% (43.96%–44.92%) | 42.72% (42.19%–42.99%) |
| Arbalester | Simulation | 0% (0%–0%) | 0% (0%–0%) | — | — | 0% (0%–0%) | 0 (0–0) | 0 (0–0) | 1 (1–1) | — | 43.43% (42.08%–43.7%) |

## Front/middle/rear firing access

| Unit | Source | Rank | Attacking share | Target assigned | In range given target |
|---|---|---|---:|---:|---:|
| Elite Conquistador | Tape | front | 35.49% (31.99%–38.31%) | 86.78% (84.44%–89.54%) | 88.57% (84.94%–94.04%) |
| Elite Conquistador | Tape | middle | 29.24% (26.17%–31.52%) | 83.82% (82.21%–85.45%) | 77% (68.28%–81.73%) |
| Elite Conquistador | Tape | rear | 19.68% (18.82%–23.3%) | 83.04% (81.91%–83.89%) | 48.74% (46.37%–53.33%) |
| Elite Conquistador | Simulation | front | 44.71% (42.41%–46.99%) | 93.26% (92.54%–94.25%) | 96.44% (94.34%–98.12%) |
| Elite Conquistador | Simulation | middle | 28.13% (24.42%–37.63%) | 90.83% (89.92%–92.31%) | 61.07% (48.41%–75.62%) |
| Elite Conquistador | Simulation | rear | 15.5% (5.46%–16.05%) | 91.03% (90.1%–92.12%) | 27.12% (10.87%–34.69%) |
| Arbalester | Tape | front | 44.56% (43.92%–45.8%) | 96% (95.09%–96.55%) | 99.16% (98.68%–99.61%) |
| Arbalester | Tape | middle | 43.03% (41.32%–43.87%) | 94% (93.93%–94.88%) | 96.69% (93.85%–97.15%) |
| Arbalester | Tape | rear | 41.27% (40.63%–41.82%) | 94.04% (93.82%–94.51%) | 92.96% (92.01%–93.91%) |
| Arbalester | Simulation | front | 43.86% (43.09%–44.59%) | 95.05% (94.54%–95.36%) | 100% (100%–100%) |
| Arbalester | Simulation | middle | 44.58% (41.93%–45.05%) | 94.17% (92.83%–94.48%) | 99.85% (99.79%–100%) |
| Arbalester | Simulation | rear | 42.02% (40.84%–42.38%) | 94.9% (94.51%–95.31%) | 98.9% (98.56%–98.98%) |

## Target/order observations

| Unit | Source | Units assigned | Distinct first targets | Largest first-target load | First-target concentration | Target changes |
|---|---|---:|---:|---:|---:|---:|
| Elite Conquistador | Tape | 12 (12–12) | 1 (1–1) | 12 (12–12) | 100% (100%–100%) | 197 (170–235) |
| Elite Conquistador | Simulation | 12 (12–12) | 3 (3–3) | 9 (9–9) | 75% (75%–75%) | 71 (59–89) |
| Arbalester | Tape | 21 (21–21) | 2 (2–2) | 12.5 (11–14) | 59.52% (52.38%–66.67%) | 26.5 (18–36) |
| Arbalester | Simulation | 21 (21–21) | 7 (6–8) | 6 (5–9) | 28.57% (23.81%–42.86%) | 44 (39–50) |

The raw tape exposes effective per-unit action/target state, not a named high-level command packet. The simulation scenario uses ordinary ranged combat with owner 3 target pressure, owner 2 opportunity retargeting, and owner 3 windup retargeting; neither side has the cohesive kiting order in this row.

## Shots

| Unit | Source | Fired | Hits | Misses | Hit rate |
|---|---|---:|---:|---:|---:|
| Elite Conquistador | Tape | 106 (100–110) | 70.5 (69–72) | 35 (30–40) | 67.19% (63.3%–70%) |
| Elite Conquistador | Simulation | 62 (49–84) | 45 (35–61) | 15 (14–23) | 72.62% (71.43%–77.42%) |
| Arbalester | Tape | 289 (275–298) | 187 (176–199) | 99.5 (99–104) | 64.7% (64%–66.78%) |
| Arbalester | Simulation | 313 (308–326) | 276 (276–276) | 37 (32–50) | 88.18% (84.66%–89.61%) |

## Scope and limitations

- Tape release counts are an inference from the full-rate action channel; hit counts are authoritative decoded archive values. A target death can truncate an action episode, and raw frame loss at the exact transition can shift release inference by one.
- Rank is recomputed each sampled frame from the direction between army centroids. It measures firing access, not a persistent formation slot.
- Overlap uses collision boxes, not outline boxes. Projectile reach uses sourced outline/range geometry.

## Next step

Use the overlap and rank-access gaps to decide whether the generic ranged ingress/spacing rule is suppressing rear-rank Conquistador access. Accuracy should be adjusted only if release opportunity first matches the tape and the residual hit rate still differs.

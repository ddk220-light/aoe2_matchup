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
| Elite Conquistador | Simulation | 8.18% (6.06%–8.61%) | 66.32% (49.65%–70.85%) | 0.38 (0.17–0.47) | 0.5 (0.5–0.5) | 94.92% (72.97%–95.99%) | 5 (5–5) | 1 (1–1) | 2 (2–2) | 42.2% (36.77%–45.21%) | 31.77% (23.95%–38.67%) |
| Arbalester | Tape | 1.18% (0.92%–1.3%) | 17.5% (13.49%–19.34%) | 0 (0–0.04) | 0.07 (0.05–0.12) | 72.03% (66.36%–73.49%) | 3.5 (3–5) | 1.5 (1–2) | 2.5 (2–5) | 44.35% (43.96%–44.92%) | 42.72% (42.19%–42.99%) |
| Arbalester | Simulation | 2.44% (0.64%–2.87%) | 33.36% (8.8%–36.51%) | 0.13 (0.07–0.21) | 0.15 (0.12–0.21) | 84.06% (47.51%–88.62%) | 3 (1–4) | 1 (1–1) | 2 (2–2) | 44% (43.41%–45.52%) | 41.71% (41.29%–43.03%) |

## Front/middle/rear firing access

| Unit | Source | Rank | Attacking share | Target assigned | In range given target |
|---|---|---|---:|---:|---:|
| Elite Conquistador | Tape | front | 35.49% (31.99%–38.31%) | 86.78% (84.44%–89.54%) | 88.57% (84.94%–94.04%) |
| Elite Conquistador | Tape | middle | 29.24% (26.17%–31.52%) | 83.82% (82.21%–85.45%) | 77% (68.28%–81.73%) |
| Elite Conquistador | Tape | rear | 19.68% (18.82%–23.3%) | 83.04% (81.91%–83.89%) | 48.74% (46.37%–53.33%) |
| Elite Conquistador | Simulation | front | 45.86% (43.84%–47.13%) | 94.25% (92.11%–94.76%) | 97.69% (97.41%–98.27%) |
| Elite Conquistador | Simulation | middle | 38.64% (35.58%–39.86%) | 90.08% (89.45%–92.63%) | 87% (76.33%–89.32%) |
| Elite Conquistador | Simulation | rear | 31.25% (27.91%–34.59%) | 87.89% (86.2%–90.11%) | 63.97% (59.64%–71.69%) |
| Arbalester | Tape | front | 44.56% (43.92%–45.8%) | 96% (95.09%–96.55%) | 99.16% (98.68%–99.61%) |
| Arbalester | Tape | middle | 43.03% (41.32%–43.87%) | 94% (93.93%–94.88%) | 96.69% (93.85%–97.15%) |
| Arbalester | Tape | rear | 41.27% (40.63%–41.82%) | 94.04% (93.82%–94.51%) | 92.96% (92.01%–93.91%) |
| Arbalester | Simulation | front | 43.56% (41.83%–44.58%) | 94.15% (93.6%–95.17%) | 100% (100%–100%) |
| Arbalester | Simulation | middle | 42.72% (42.43%–43.09%) | 92.72% (91.43%–93.12%) | 99.84% (99.74%–100%) |
| Arbalester | Simulation | rear | 42.39% (40.87%–42.68%) | 94.31% (93.73%–95.08%) | 98.77% (98.65%–98.88%) |

## Target/order observations

| Unit | Source | Units assigned | Distinct first targets | Largest first-target load | First-target concentration | Target changes |
|---|---|---:|---:|---:|---:|---:|
| Elite Conquistador | Tape | 12 (12–12) | 1 (1–1) | 12 (12–12) | 100% (100%–100%) | 197 (170–235) |
| Elite Conquistador | Simulation | 12 (12–12) | 3 (3–3) | 9 (9–9) | 75% (75%–75%) | 104 (88–112) |
| Arbalester | Tape | 21 (21–21) | 2 (2–2) | 12.5 (11–14) | 59.52% (52.38%–66.67%) | 26.5 (18–36) |
| Arbalester | Simulation | 21 (21–21) | 7 (6–8) | 6 (5–9) | 28.57% (23.81%–42.86%) | 27 (22–38) |

The raw tape exposes effective per-unit action/target state, not a named high-level command packet. The simulation scenario uses ordinary ranged combat with owner 3 target pressure, owner 2 opportunity retargeting, and owner 3 windup retargeting; neither side has the cohesive kiting order in this row.

## Shots

| Unit | Source | Fired | Hits | Misses | Hit rate |
|---|---|---:|---:|---:|---:|
| Elite Conquistador | Tape | 106 (100–110) | 70.5 (69–72) | 35 (30–40) | 67.19% (63.3%–70%) |
| Elite Conquistador | Simulation | 102 (95–106) | 70 (68–72) | 34 (25–36) | 66.67% (66.04%–73.68%) |
| Arbalester | Tape | 289 (275–298) | 187 (176–199) | 99.5 (99–104) | 64.7% (64%–66.78%) |
| Arbalester | Simulation | 254 (251–302) | 234 (222–268) | 30 (18–35) | 88.74% (87.46%–92.83%) |

## Scope and limitations

- Tape release counts are an inference from the full-rate action channel; hit counts are authoritative decoded archive values. A target death can truncate an action episode, and raw frame loss at the exact transition can shift release inference by one.
- Rank is recomputed each sampled frame from the direction between army centroids. It measures firing access, not a persistent formation slot.
- Overlap uses collision boxes, not outline boxes. Projectile reach uses sourced outline/range geometry.

## Next step

Use the overlap and rank-access gaps to decide whether the generic ranged ingress/spacing rule is suppressing rear-rank Conquistador access. Accuracy should be adjusted only if release opportunity first matches the tape and the residual hit rate still differs.

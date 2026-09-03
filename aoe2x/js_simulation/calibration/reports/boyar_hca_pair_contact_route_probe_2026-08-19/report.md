# Generic melee pair-contact analysis

- Golden archive: `aoe2_golden_phase2_WITH_TAPES.zip`
- SHA-256: `B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6`
- Sampling cadence: 100 ms
- Simulation samples per row: 1
- Seed: 20260817

Pair populations are named `relationship|motion|attack|intent|phase`.
Depth uses axis-aligned collision extents. Contact windows remain relationship-wide.

## Heavy Cavalry Archer vs Elite Boyar

Row ID: `elite_boyar_vs_heavy_cav_archer`

| Source | Run | Population | Pair share | p05 depth | Median depth | p95 depth | Window median (ms) | Max local degree | Max component | Triangles | Four-cliques |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Tape | repeat-1 | `enemies|both-moving|neither-attacking|corridor-contact|entering` | 1 | 0.0043 | 0.0142 | 0.0369 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|both-moving|neither-attacking|corridor-contact|persisting` | 1 | 0.0216 | 0.0514 | 0.0812 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|both-moving|neither-attacking|direct-target|entering` | 1 | 0.0247 | 0.0549 | 0.085 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|both-moving|neither-attacking|direct-target|persisting` | 1 | 0.0965 | 0.109 | 0.1214 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|both-moving|one-attacking|corridor-contact|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `enemies|both-moving|one-attacking|corridor-contact|persisting` | 1 | 0.0424 | 0.0695 | 0.0965 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|both-moving|one-attacking|direct-target|entering` | 1 | 0.0063 | 0.0444 | 0.1001 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|both-moving|one-attacking|direct-target|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `enemies|both-moving|one-attacking|direct-target|persisting` | 1 | 0.0297 | 0.0607 | 0.0918 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|neither-moving|both-attacking|corridor-contact|persisting` | 1 | 0.0227 | 0.0995 | 0.1492 | — | 6 | 7 | 0 | 0 |
| Tape | repeat-1 | `enemies|neither-moving|both-attacking|direct-target|persisting` | 1 | 0.0014 | 0.0598 | 0.1902 | — | 4 | 5 | 0 | 0 |
| Tape | repeat-1 | `enemies|neither-moving|neither-attacking|corridor-contact|persisting` | 1 | 0.0068 | 0.0399 | 0.0813 | — | 3 | 4 | 0 | 0 |
| Tape | repeat-1 | `enemies|neither-moving|neither-attacking|direct-target|persisting` | 1 | 0.0034 | 0.1119 | 0.1902 | — | 4 | 5 | 0 | 0 |
| Tape | repeat-1 | `enemies|neither-moving|one-attacking|corridor-contact|persisting` | 1 | 0 | 0.0256 | 0.1312 | — | 6 | 7 | 0 | 0 |
| Tape | repeat-1 | `enemies|neither-moving|one-attacking|direct-target|persisting` | 1 | 0.0039 | 0.0445 | 0.1557 | — | 4 | 5 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|both-attacking|corridor-contact|entering` | 1 | 0.0335 | 0.0335 | 0.0335 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|both-attacking|corridor-contact|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|both-attacking|corridor-contact|persisting` | 1 | 0.0159 | 0.0813 | 0.1433 | — | 6 | 7 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|both-attacking|direct-target|entering` | 1 | 0.0058 | 0.0235 | 0.0632 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|both-attacking|direct-target|persisting` | 1 | 0.0075 | 0.0574 | 0.1309 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|neither-attacking|corridor-contact|entering` | 1 | 0.0013 | 0.0109 | 0.0454 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|neither-attacking|corridor-contact|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|neither-attacking|corridor-contact|persisting` | 1 | 0.0117 | 0.0489 | 0.1321 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|neither-attacking|direct-target|entering` | 1 | 0.0038 | 0.0038 | 0.0038 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|neither-attacking|direct-target|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|neither-attacking|direct-target|persisting` | 1 | 0.0152 | 0.0224 | 0.0576 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|one-attacking|corridor-contact|entering` | 1 | 0.0008 | 0.0238 | 0.0888 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|one-attacking|corridor-contact|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|one-attacking|corridor-contact|persisting` | 1 | 0.0102 | 0.0818 | 0.125 | — | 7 | 8 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|one-attacking|direct-target|entering` | 1 | 0.0065 | 0.0345 | 0.1005 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|one-attacking|direct-target|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|one-attacking|direct-target|persisting` | 1 | 0.0144 | 0.0941 | 0.2379 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|both-moving|both-attacking|none|entering` | 1 | 0.0062 | 0.0329 | 0.1086 | — | 3 | 4 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|both-moving|both-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|both-moving|both-attacking|none|persisting` | 1 | 0.018 | 0.1397 | 0.399 | — | 8 | 16 | 56 | 59 |
| Tape | repeat-1 | `same-master-allies|both-moving|neither-attacking|none|entering` | 1 | 0.0028 | 0.0431 | 0.1315 | — | 5 | 7 | 3 | 0 |
| Tape | repeat-1 | `same-master-allies|both-moving|neither-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|both-moving|neither-attacking|none|persisting` | 1 | 0.0126 | 0.1226 | 0.3975 | — | 8 | 19 | 60 | 65 |
| Tape | repeat-1 | `same-master-allies|both-moving|one-attacking|none|entering` | 1 | 0.0168 | 0.0652 | 0.1014 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|both-moving|one-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|both-moving|one-attacking|none|persisting` | 1 | 0.0028 | 0.0936 | 0.1538 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|neither-moving|both-attacking|none|persisting` | 1 | 0.0159 | 0.1287 | 0.4299 | — | 9 | 17 | 71 | 90 |
| Tape | repeat-1 | `same-master-allies|neither-moving|neither-attacking|none|persisting` | 1 | 0.0159 | 0.1299 | 0.4299 | — | 9 | 17 | 71 | 90 |
| Tape | repeat-1 | `same-master-allies|neither-moving|one-attacking|none|persisting` | 1 | 0.0105 | 0.0616 | 0.4448 | — | 7 | 8 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|both-attacking|none|entering` | 1 | 0.033 | 0.033 | 0.033 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|both-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|both-attacking|none|persisting` | 1 | 0.0172 | 0.0842 | 0.3006 | — | 4 | 7 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|neither-attacking|none|entering` | 1 | 0.0024 | 0.0221 | 0.0798 | — | 2 | 4 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|neither-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|neither-attacking|none|persisting` | 1 | 0.0041 | 0.0564 | 0.1824 | — | 5 | 7 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|one-attacking|none|entering` | 1 | 0.0013 | 0.0179 | 0.0891 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|one-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|one-attacking|none|persisting` | 1 | 0.0032 | 0.0375 | 0.1522 | — | 2 | 3 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|both-moving|both-attacking|none|persisting` | 1 | 0.02 | 0.02 | 0.0228 | — | 8 | 20 | 46 | 10 |
| Simulation | sample-0 | `same-master-allies|both-moving|neither-attacking|none|entering` | 1 | 0.0006 | 0.0336 | 0.1407 | — | 2 | 4 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|both-moving|neither-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|both-moving|neither-attacking|none|persisting` | 1 | 0.02 | 0.02 | 0.25 | — | 8 | 20 | 46 | 10 |
| Simulation | sample-0 | `same-master-allies|both-moving|one-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|both-moving|one-attacking|none|persisting` | 1 | 0 | 0.0467 | 0.2492 | — | 3 | 10 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|neither-moving|both-attacking|none|persisting` | 1 | 0.02 | 0.02 | 0.035 | — | 8 | 20 | 46 | 10 |
| Simulation | sample-0 | `same-master-allies|neither-moving|neither-attacking|none|persisting` | 1 | 0.02 | 0.02 | 0.17 | — | 8 | 20 | 46 | 10 |
| Simulation | sample-0 | `same-master-allies|neither-moving|one-attacking|none|entering` | 1 | 0 | 0 | 0 | — | 1 | 2 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|neither-moving|one-attacking|none|persisting` | 1 | 0.02 | 0.02 | 0.2499 | — | 5 | 12 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|one-moving|both-attacking|none|entering` | 1 | 0.0045 | 0.0122 | 0.02 | — | 2 | 3 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|one-moving|both-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|one-moving|both-attacking|none|persisting` | 1 | 0 | 0.07 | 0.364 | — | 2 | 3 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|one-moving|neither-attacking|none|entering` | 1 | 0.0035 | 0.02 | 0.1006 | — | 4 | 5 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|one-moving|neither-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|one-moving|neither-attacking|none|persisting` | 1 | 0.0199 | 0.1624 | 0.25 | — | 7 | 9 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|one-moving|one-attacking|none|entering` | 1 | 0.0112 | 0.02 | 0.0659 | — | 1 | 2 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|one-moving|one-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|one-moving|one-attacking|none|persisting` | 1 | 0.0001 | 0.0664 | 0.2473 | — | 2 | 3 | 0 | 0 |

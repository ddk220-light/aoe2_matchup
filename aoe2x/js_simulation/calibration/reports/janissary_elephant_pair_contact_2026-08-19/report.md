# Generic melee pair-contact analysis

- Golden archive: `aoe2_golden_phase2_WITH_TAPES.zip`
- SHA-256: `B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6`
- Sampling cadence: 100 ms
- Simulation samples per row: 1
- Seed: 20260817

Pair populations are named `relationship|motion|attack|intent|phase`.
Depth uses axis-aligned collision extents. Contact windows remain relationship-wide.

## Elite Janissary vs Elite Battle Elephant

Row ID: `elite_janissary_vs_elite_elephant`

| Source | Run | Population | Pair share | p05 depth | Median depth | p95 depth | Window median (ms) | Max local degree | Max component | Triangles | Four-cliques |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Tape | repeat-1 | `enemies|both-moving|neither-attacking|corridor-contact|entering` | 1 | 0.001 | 0.0095 | 0.0188 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|both-moving|neither-attacking|corridor-contact|persisting` | 1 | 0.0368 | 0.0368 | 0.0368 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|both-moving|one-attacking|direct-target|entering` | 1 | 0.0175 | 0.032 | 0.0464 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|both-moving|one-attacking|direct-target|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `enemies|both-moving|one-attacking|direct-target|persisting` | 1 | 0.0515 | 0.0571 | 0.1038 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|both-attacking|direct-target|persisting` | 1 | 0.0294 | 0.0294 | 0.0294 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|neither-attacking|corridor-contact|entering` | 1 | 0.0329 | 0.0329 | 0.0329 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|neither-attacking|corridor-contact|persisting` | 1 | 0.0501 | 0.0501 | 0.0501 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|one-attacking|corridor-contact|entering` | 1 | 0.0086 | 0.0086 | 0.0086 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|one-attacking|corridor-contact|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|one-attacking|corridor-contact|persisting` | 1 | 0.0201 | 0.027 | 0.0378 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|one-attacking|direct-target|entering` | 1 | 0.0088 | 0.0101 | 0.0133 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|one-attacking|direct-target|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `enemies|one-moving|one-attacking|direct-target|persisting` | 1 | 0.0067 | 0.0576 | 0.1068 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|both-moving|both-attacking|none|entering` | 1 | 0.0006 | 0.0078 | 0.0669 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|both-moving|both-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|both-moving|both-attacking|none|persisting` | 1 | 0.0098 | 0.1026 | 0.3225 | — | 10 | 20 | 78 | 70 |
| Tape | repeat-1 | `same-master-allies|both-moving|neither-attacking|none|entering` | 1 | 0.0013 | 0.0203 | 0.1043 | — | 5 | 10 | 2 | 0 |
| Tape | repeat-1 | `same-master-allies|both-moving|neither-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|both-moving|neither-attacking|none|persisting` | 1 | 0.0109 | 0.101 | 0.3033 | — | 11 | 21 | 95 | 106 |
| Tape | repeat-1 | `same-master-allies|both-moving|one-attacking|none|entering` | 1 | 0.0026 | 0.0233 | 0.0441 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|both-moving|one-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|both-moving|one-attacking|none|persisting` | 1 | 0.0255 | 0.0487 | 0.0899 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|neither-moving|both-attacking|none|persisting` | 1 | 0.0078 | 0.1007 | 0.3142 | — | 10 | 20 | 79 | 70 |
| Tape | repeat-1 | `same-master-allies|neither-moving|neither-attacking|none|persisting` | 1 | 0.0139 | 0.1266 | 0.3879 | — | 10 | 16 | 45 | 32 |
| Tape | repeat-1 | `same-master-allies|neither-moving|one-attacking|none|persisting` | 1 | 0.0109 | 0.0977 | 0.3022 | — | 5 | 11 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|both-attacking|none|entering` | 1 | 0.0501 | 0.0541 | 0.0582 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|both-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|both-attacking|none|persisting` | 1 | 0.0985 | 0.249 | 0.3946 | — | 6 | 7 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|neither-attacking|none|entering` | 1 | 0.004 | 0.0359 | 0.0916 | — | 4 | 5 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|neither-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|neither-attacking|none|persisting` | 1 | 0.0138 | 0.1385 | 0.3818 | — | 9 | 11 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|one-attacking|none|entering` | 1 | 0.0005 | 0.0207 | 0.0702 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|one-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|one-attacking|none|persisting` | 1 | 0.0034 | 0.0283 | 0.1589 | — | 2 | 3 | 0 | 0 |
| Simulation | sample-0 | `enemies|both-moving|neither-attacking|direct-target|entering` | 1 | 0.0062 | 0.0066 | 0.0069 | — | 1 | 2 | 0 | 0 |
| Simulation | sample-0 | `enemies|both-moving|one-attacking|direct-target|entering` | 1 | 0.0349 | 0.0349 | 0.0349 | — | 1 | 2 | 0 | 0 |
| Simulation | sample-0 | `enemies|neither-moving|both-attacking|direct-target|persisting` | 1 | 0.0805 | 0.125 | 0.125 | — | 1 | 2 | 0 | 0 |
| Simulation | sample-0 | `enemies|neither-moving|neither-attacking|direct-target|persisting` | 1 | 0.125 | 0.125 | 0.125 | — | 2 | 3 | 0 | 0 |
| Simulation | sample-0 | `enemies|neither-moving|one-attacking|direct-target|persisting` | 1 | 0.125 | 0.125 | 0.125 | — | 2 | 3 | 0 | 0 |
| Simulation | sample-0 | `enemies|one-moving|both-attacking|direct-target|entering` | 1 | 0.0209 | 0.0258 | 0.0352 | — | 1 | 2 | 0 | 0 |
| Simulation | sample-0 | `enemies|one-moving|both-attacking|direct-target|persisting` | 1 | 0.0896 | 0.125 | 0.125 | — | 1 | 2 | 0 | 0 |
| Simulation | sample-0 | `enemies|one-moving|neither-attacking|direct-target|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Simulation | sample-0 | `enemies|one-moving|neither-attacking|direct-target|persisting` | 1 | 0.0267 | 0.106 | 0.125 | — | 2 | 3 | 0 | 0 |
| Simulation | sample-0 | `enemies|one-moving|one-attacking|direct-target|entering` | 1 | 0.0077 | 0.0314 | 0.0845 | — | 2 | 3 | 0 | 0 |
| Simulation | sample-0 | `enemies|one-moving|one-attacking|direct-target|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Simulation | sample-0 | `enemies|one-moving|one-attacking|direct-target|persisting` | 1 | 0.0349 | 0.125 | 0.125 | — | 2 | 3 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|both-moving|both-attacking|none|entering` | 1 | 0.0006 | 0.0046 | 0.0086 | — | 1 | 2 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|both-moving|both-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|both-moving|both-attacking|none|persisting` | 1 | 0.0437 | 0.2879 | 0.3989 | — | 5 | 8 | 10 | 5 |
| Simulation | sample-0 | `same-master-allies|both-moving|neither-attacking|none|entering` | 1 | 0.0025 | 0.0362 | 0.114 | — | 3 | 5 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|both-moving|neither-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|both-moving|neither-attacking|none|persisting` | 1 | 0.0256 | 0.2098 | 0.3628 | — | 5 | 9 | 11 | 5 |
| Simulation | sample-0 | `same-master-allies|both-moving|one-attacking|none|persisting` | 1 | 0.0552 | 0.1584 | 0.25 | — | 1 | 2 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|neither-moving|both-attacking|none|persisting` | 1 | 0.0333 | 0.2337 | 0.3987 | — | 5 | 8 | 10 | 5 |
| Simulation | sample-0 | `same-master-allies|neither-moving|neither-attacking|none|persisting` | 1 | 0.2337 | 0.275 | 0.4 | — | 3 | 4 | 4 | 1 |
| Simulation | sample-0 | `same-master-allies|neither-moving|one-attacking|none|persisting` | 1 | 0.1793 | 0.2337 | 0.25 | — | 1 | 2 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|one-moving|both-attacking|none|entering` | 1 | 0.011 | 0.0177 | 0.0501 | — | 2 | 3 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|one-moving|both-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|one-moving|both-attacking|none|persisting` | 1 | 0.0287 | 0.1331 | 0.3484 | — | 3 | 6 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|one-moving|neither-attacking|none|entering` | 1 | 0.0073 | 0.0337 | 0.0799 | — | 2 | 5 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|one-moving|neither-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|one-moving|neither-attacking|none|persisting` | 1 | 0.0193 | 0.2043 | 0.3714 | — | 5 | 9 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|one-moving|one-attacking|none|entering` | 1 | 0.0028 | 0.0471 | 0.081 | — | 1 | 2 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|one-moving|one-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Simulation | sample-0 | `same-master-allies|one-moving|one-attacking|none|persisting` | 1 | 0.0549 | 0.25 | 0.25 | — | 2 | 3 | 0 | 0 |

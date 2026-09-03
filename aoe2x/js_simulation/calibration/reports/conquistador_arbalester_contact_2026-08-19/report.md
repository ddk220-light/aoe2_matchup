# Generic melee pair-contact analysis

- Golden archive: `aoe2_golden_phase2_WITH_TAPES.zip`
- SHA-256: `B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6`
- Sampling cadence: 100 ms
- Simulation samples per row: 5
- Seed: 20260817

Pair populations are named `relationship|motion|attack|intent|phase`.
Depth uses axis-aligned collision extents. Contact windows remain relationship-wide.

## Elite Conquistador vs Arbalester

Row ID: `elite_conquistador_vs_arbalester`

| Source | Run | Population | Pair share | p05 depth | Median depth | p95 depth | Window median (ms) | Max local degree | Max component | Triangles | Four-cliques |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Tape | repeat-1 | `same-master-allies|both-moving|both-attacking|none|persisting` | 1 | 0.3006 | 0.3006 | 0.3006 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|both-moving|neither-attacking|none|entering` | 1 | 0.0003 | 0.0195 | 0.0729 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|both-moving|neither-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|both-moving|neither-attacking|none|persisting` | 1 | 0.0008 | 0.0915 | 0.3022 | — | 3 | 6 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|both-moving|one-attacking|none|entering` | 1 | 0.081 | 0.081 | 0.081 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|both-moving|one-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|both-moving|one-attacking|none|persisting` | 1 | 0.0062 | 0.1391 | 0.2245 | — | 2 | 4 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|neither-moving|both-attacking|none|persisting` | 1 | 0.0067 | 0.0067 | 0.3229 | — | 2 | 4 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|neither-moving|neither-attacking|none|persisting` | 1 | 0.0001 | 0.0067 | 0.0952 | — | 2 | 4 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|neither-moving|one-attacking|none|persisting` | 1 | 0.0035 | 0.0134 | 0.1298 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|both-attacking|none|entering` | 1 | 0.0055 | 0.0258 | 0.0462 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|both-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|both-attacking|none|persisting` | 1 | 0.165 | 0.2389 | 0.3602 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|neither-attacking|none|entering` | 1 | 0.0015 | 0.0169 | 0.104 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|neither-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|neither-attacking|none|persisting` | 1 | 0.0015 | 0.0277 | 0.1067 | — | 2 | 5 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|one-attacking|none|entering` | 1 | 0.0006 | 0.0142 | 0.0858 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|one-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-1 | `same-master-allies|one-moving|one-attacking|none|persisting` | 1 | 0.0013 | 0.0383 | 0.1999 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-2 | `same-master-allies|both-moving|both-attacking|none|persisting` | 1 | 0.3005 | 0.3005 | 0.3005 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-2 | `same-master-allies|both-moving|neither-attacking|none|entering` | 1 | 0.0001 | 0.0144 | 0.0994 | — | 2 | 4 | 0 | 0 |
| Tape | repeat-2 | `same-master-allies|both-moving|neither-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-2 | `same-master-allies|both-moving|neither-attacking|none|persisting` | 1 | 0.0019 | 0.1051 | 0.3058 | — | 3 | 6 | 0 | 0 |
| Tape | repeat-2 | `same-master-allies|both-moving|one-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-2 | `same-master-allies|both-moving|one-attacking|none|persisting` | 1 | 0.0587 | 0.1482 | 0.2185 | — | 2 | 5 | 0 | 0 |
| Tape | repeat-2 | `same-master-allies|neither-moving|both-attacking|none|persisting` | 1 | 0.0011 | 0.0505 | 0.3262 | — | 2 | 4 | 0 | 0 |
| Tape | repeat-2 | `same-master-allies|neither-moving|neither-attacking|none|persisting` | 1 | 0 | 0.0088 | 0.0995 | — | 2 | 4 | 0 | 0 |
| Tape | repeat-2 | `same-master-allies|neither-moving|one-attacking|none|persisting` | 1 | 0 | 0.0071 | 0.0505 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-2 | `same-master-allies|one-moving|both-attacking|none|entering` | 1 | 0.0068 | 0.0068 | 0.0068 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-2 | `same-master-allies|one-moving|both-attacking|none|persisting` | 1 | 0.0009 | 0.0995 | 0.303 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-2 | `same-master-allies|one-moving|neither-attacking|none|entering` | 1 | 0.0002 | 0.0192 | 0.0867 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-2 | `same-master-allies|one-moving|neither-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-2 | `same-master-allies|one-moving|neither-attacking|none|persisting` | 1 | 0 | 0.0251 | 0.1097 | — | 3 | 5 | 0 | 0 |
| Tape | repeat-2 | `same-master-allies|one-moving|one-attacking|none|entering` | 1 | 0 | 0.0208 | 0.073 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-2 | `same-master-allies|one-moving|one-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-2 | `same-master-allies|one-moving|one-attacking|none|persisting` | 1 | 0.0006 | 0.0309 | 0.1575 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-3 | `same-master-allies|both-moving|both-attacking|none|persisting` | 1 | 0.2979 | 0.2979 | 0.2979 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-3 | `same-master-allies|both-moving|neither-attacking|none|entering` | 1 | 0.0011 | 0.0238 | 0.0938 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-3 | `same-master-allies|both-moving|neither-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-3 | `same-master-allies|both-moving|neither-attacking|none|persisting` | 1 | 0.0019 | 0.0897 | 0.3045 | — | 3 | 5 | 0 | 0 |
| Tape | repeat-3 | `same-master-allies|both-moving|one-attacking|none|entering` | 1 | 0.0135 | 0.0463 | 0.0791 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-3 | `same-master-allies|both-moving|one-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-3 | `same-master-allies|both-moving|one-attacking|none|persisting` | 1 | 0.0219 | 0.1412 | 0.227 | — | 2 | 4 | 0 | 0 |
| Tape | repeat-3 | `same-master-allies|neither-moving|both-attacking|none|persisting` | 1 | 0 | 0.0255 | 0.2979 | — | 2 | 4 | 0 | 0 |
| Tape | repeat-3 | `same-master-allies|neither-moving|neither-attacking|none|persisting` | 1 | 0 | 0.0106 | 0.1728 | — | 2 | 4 | 0 | 0 |
| Tape | repeat-3 | `same-master-allies|neither-moving|one-attacking|none|persisting` | 1 | 0 | 0.0043 | 0.1017 | — | 2 | 4 | 0 | 0 |
| Tape | repeat-3 | `same-master-allies|one-moving|both-attacking|none|persisting` | 1 | 0.0086 | 0.0725 | 0.3127 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-3 | `same-master-allies|one-moving|neither-attacking|none|entering` | 1 | 0.0002 | 0.013 | 0.0754 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-3 | `same-master-allies|one-moving|neither-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-3 | `same-master-allies|one-moving|neither-attacking|none|persisting` | 1 | 0 | 0.0275 | 0.1566 | — | 2 | 5 | 0 | 0 |
| Tape | repeat-3 | `same-master-allies|one-moving|one-attacking|none|entering` | 1 | 0 | 0.01 | 0.0492 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-3 | `same-master-allies|one-moving|one-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-3 | `same-master-allies|one-moving|one-attacking|none|persisting` | 1 | 0 | 0.0283 | 0.1783 | — | 2 | 5 | 0 | 0 |
| Tape | repeat-4 | `same-master-allies|both-moving|both-attacking|none|persisting` | 1 | 0.2968 | 0.2968 | 0.2968 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-4 | `same-master-allies|both-moving|neither-attacking|none|entering` | 1 | 0.0015 | 0.014 | 0.0813 | — | 2 | 4 | 0 | 0 |
| Tape | repeat-4 | `same-master-allies|both-moving|neither-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-4 | `same-master-allies|both-moving|neither-attacking|none|persisting` | 1 | 0.0038 | 0.1163 | 0.3044 | — | 3 | 6 | 0 | 0 |
| Tape | repeat-4 | `same-master-allies|both-moving|one-attacking|none|entering` | 1 | 0.0144 | 0.0395 | 0.0646 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-4 | `same-master-allies|both-moving|one-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-4 | `same-master-allies|both-moving|one-attacking|none|persisting` | 1 | 0.0113 | 0.0796 | 0.2101 | — | 2 | 4 | 0 | 0 |
| Tape | repeat-4 | `same-master-allies|neither-moving|both-attacking|none|persisting` | 1 | 0.0011 | 0.0836 | 0.2968 | — | 2 | 4 | 0 | 0 |
| Tape | repeat-4 | `same-master-allies|neither-moving|neither-attacking|none|persisting` | 1 | 0.0011 | 0.0836 | 0.1301 | — | 2 | 4 | 0 | 0 |
| Tape | repeat-4 | `same-master-allies|neither-moving|one-attacking|none|persisting` | 1 | 0 | 0.0352 | 0.1269 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-4 | `same-master-allies|one-moving|both-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-4 | `same-master-allies|one-moving|both-attacking|none|persisting` | 1 | 0.018 | 0.1682 | 0.3471 | — | 2 | 3 | 0 | 0 |
| Tape | repeat-4 | `same-master-allies|one-moving|neither-attacking|none|entering` | 1 | 0.0037 | 0.0178 | 0.0891 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-4 | `same-master-allies|one-moving|neither-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-4 | `same-master-allies|one-moving|neither-attacking|none|persisting` | 1 | 0.0001 | 0.0392 | 0.1222 | — | 2 | 5 | 0 | 0 |
| Tape | repeat-4 | `same-master-allies|one-moving|one-attacking|none|entering` | 1 | 0 | 0.0144 | 0.0555 | — | 1 | 2 | 0 | 0 |
| Tape | repeat-4 | `same-master-allies|one-moving|one-attacking|none|leaving` | 0 | — | — | — | — | 0 | 0 | 0 | 0 |
| Tape | repeat-4 | `same-master-allies|one-moving|one-attacking|none|persisting` | 1 | 0 | 0.042 | 0.1842 | — | 2 | 3 | 0 | 0 |

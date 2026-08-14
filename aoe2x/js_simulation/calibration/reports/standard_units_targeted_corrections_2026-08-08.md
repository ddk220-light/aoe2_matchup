# Standard-units targeted comparison corrections

- Golden archive SHA-256: `38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D`
- Engine base: `cd506c87` (`chaser mobility + grid pathing engine`)
- Lane: tape-conditioned canonical `frames.bin` starting units and positions
- Simulation samples: 5 per row, seed `20260411`
- Sign: positive means owner 3 / the second-listed unit wins; negative means owner 2 / the first-listed unit wins
- Canonical HCA/Arbalester orientation: owner 2 Heavy Cavalry Archer (14), owner 3 Arbalester (21). The reversed mirror is excluded from the benchmark.

## Corrected siege rows

| Matchup | Tape mean | Tape band | Sim mean | Side-3 wins |
| --- | ---: | ---: | ---: | ---: |
| Hand Cannoneer vs Heavy Scorpion | +44.692 | +37.308…+52.692 | +29.500 | 5/5 |
| Hand Cannoneer vs Siege Onager | +30.119 | +29.048…+31.190 | +7.614 | 3/5 |
| Elite Skirmisher vs Heavy Scorpion | +69.861 | +68.889…+70.833 | +30.389 | 5/5 |
| Elite Skirmisher vs Siege Onager | +78.254 | +77.619…+78.571 | +19.714 | 5/5 |
| Heavy Cavalry Archer vs Heavy Scorpion | -11.958 | -23.363…+25.714 | -3.548 | 2/5 |
| Heavy Cavalry Archer vs Siege Onager | +57.347 | +57.347…+57.347 | +56.041 | 5/5 |
| Arbalester vs Heavy Scorpion | +44.333 | +38.000…+50.667 | +15.843 | 4/5 |
| Arbalester vs Siege Onager | +22.286 | +22.286…+22.286 | +14.743 | 5/5 |
| Heavy Scorpion vs Arbalester | +16.086 | +6.607…+25.000 | +24.619 | 5/5 |
| Heavy Scorpion vs Heavy Cavalry Archer | +30.461 | +25.982…+34.970 | +39.113 | 5/5 |

The previous `-100` siege values were invalid. The tape-conditioned runner had incorrectly enabled the melee-kiting control whenever exactly one side was mobile ranged, including mobile-ranged-versus-siege rows. These rows belong to the ranged-vs-ranged control family. After correcting that classification, no siege row has a `-100` mean and every stable row has the tape winner by five-sample mean.

## Elite Skirmisher vs Heavy Camel Rider

| Tape mean | Previous invalid sim mean | Corrected sim mean | Corrected Camel wins |
| ---: | ---: | ---: | ---: |
| +39.821 | -41.060 | +9.115 | 3/5 |

The contact-capture engine behavior from commit `31df43ae` is scenario-gated. The comparison runner omitted `chaseCapture: true`, so the previous run bypassed the implemented fix. Restoring the control flips the five-sample mean and majority back to Heavy Camel. This remains weaker than the earlier 22/25 calibration result, so the later movement/pathing engine still has a residual regression to investigate.

## Heavy Cavalry Archer vs Arbalester — canonical orientation

| Tape mean | Tape band | Tape Arbalester wins | Sim mean | Sim Arbalester wins |
| ---: | ---: | ---: | ---: | ---: |
| +26.071 | +15.714…+33.333 | 4/4 | -9.643 | 1/5 |

This is a real remaining engine mismatch. The standard-units documentation already marks ranged-vs-ranged patrol and volley interactions as unmodeled. The recent orientation-normalization change applies only to role-asymmetric kite and siege families; it deliberately leaves ranged-vs-ranged fights native. The canonical benchmark therefore remains red until that tape-observed ranged-vs-ranged order script is implemented.

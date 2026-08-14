# Hand Cannoneer tape-motion profile A/B results

- Decision: **REJECT**
- Source SHA-256: `38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D`
- Candidate: HC-only rigid translation plus persistent close-to-fire volleys
- Starts: exact canonical positions imported from each authorized `frames.bin` run
- Five-sample screen: FAIL
- 100-sample volatile expansion: skipped by gate
- HCA-vs-Champion hashes bit-identical: yes
- Aggregate HC tape-band error: 185.816 -> 122.049 (63.767 better)

| Matchup | Runs | Tape mean / band | Baseline mean | Candidate mean | Baseline error | Candidate error | Timeouts |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| Hand Cannoneer vs Halberdier | 5 | -76.5 / -76.5…-76.5 | -89.5 | -84.7 | 13 | 8.2 | 0 |
| Hand Cannoneer vs Hussar | 5 | 5.626 / -18.75…17.895 | 59.374 | 45.624 | 41.479 | 27.729 | 0 |
| Hand Cannoneer vs Champion | 5 | -76.607 / -82.5…-73.214 | -86.357 | -72.786 | 3.857 | 0.429 | 0 |
| Hand Cannoneer vs Elite Fire Lancer | 5 | -60.921 / -60.921…-60.921 | -68.658 | -64.132 | 7.737 | 3.211 | 0 |
| Hand Cannoneer vs Heavy Camel Rider | 5 | -67.52 / -73.571…-61.31 | -57.548 | -69.333 | 3.762 | 0 | 0 |
| Hand Cannoneer vs Paladin | 5 | 15.444 / -9.048…32.143 | 47.52 | -7.27 | 15.377 | 0 | 0 |
| Hand Cannoneer vs Elite Battle Elephant | 4 | 2.384 / -38.333…32.292 | 77.526 | 59.635 | 45.234 | 27.344 | 1 |
| Hand Cannoneer vs Elite Steppe Lancer | 5 | 8.026 / 8.026…8.026 | 63.395 | 63.163 | 55.368 | 55.137 | 0 |

## Gate failures and greater-than-25-point deltas

- Wrong stable winners: none.
- Greater-than-10-point regressions on good rows: none.
- Unresolved simulations: 1.
- Hand Cannoneer vs Hussar: 27.729 points outside the tape band.
- Hand Cannoneer vs Elite Battle Elephant: 27.344 points outside the tape band.
- Hand Cannoneer vs Elite Steppe Lancer: 55.137 points outside the tape band.

The candidate remains calibration-only; the generated product profile is unchanged.

# Hand Cannoneer tape-motion profile A/B results

- Decision: **REJECT**
- Source SHA-256: `38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D`
- Candidate: HC-only translated persistent volleys with measured half-roster melee wave
- Starts: exact canonical positions imported from each authorized `frames.bin` run
- Five-sample screen: FAIL
- 100-sample volatile expansion: skipped by gate
- HCA-vs-Champion hashes bit-identical: yes
- Aggregate HC tape-band error: 185.816 -> 198.555 (-12.739 better)

| Matchup | Runs | Tape mean / band | Baseline mean | Candidate mean | Baseline error | Candidate error | Timeouts |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| Hand Cannoneer vs Halberdier | 5 | -76.5 / -76.5…-76.5 | -89.5 | -92.2 | 13 | 15.7 | 0 |
| Hand Cannoneer vs Hussar | 5 | 5.626 / -18.75…17.895 | 59.374 | 67.569 | 41.479 | 49.674 | 0 |
| Hand Cannoneer vs Champion | 5 | -76.607 / -82.5…-73.214 | -86.357 | -55.286 | 3.857 | 17.929 | 0 |
| Hand Cannoneer vs Elite Fire Lancer | 5 | -60.921 / -60.921…-60.921 | -68.658 | -54.368 | 7.737 | 6.553 | 0 |
| Hand Cannoneer vs Heavy Camel Rider | 5 | -67.52 / -73.571…-61.31 | -57.548 | -51.048 | 3.762 | 10.262 | 0 |
| Hand Cannoneer vs Paladin | 5 | 15.444 / -9.048…32.143 | 47.52 | 43.889 | 15.377 | 11.746 | 0 |
| Hand Cannoneer vs Elite Battle Elephant | 5 | 2.384 / -38.333…32.292 | 77.526 | 56.583 | 45.234 | 24.292 | 0 |
| Hand Cannoneer vs Elite Steppe Lancer | 5 | 8.026 / 8.026…8.026 | 63.395 | 70.426 | 55.368 | 62.4 | 0 |

## Gate failures and greater-than-25-point deltas

- Wrong stable winners: none.
- Greater-than-10-point regressions on good rows: Hand Cannoneer vs Champion
- Unresolved simulations: none.
- Hand Cannoneer vs Hussar: 49.674 points outside the tape band.
- Hand Cannoneer vs Elite Steppe Lancer: 62.4 points outside the tape band.

The candidate remains calibration-only; the generated product profile is unchanged.

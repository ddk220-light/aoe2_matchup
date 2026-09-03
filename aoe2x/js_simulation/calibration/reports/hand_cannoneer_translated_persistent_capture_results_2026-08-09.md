# Hand Cannoneer tape-motion profile A/B results

- Decision: **REJECT**
- Source SHA-256: `38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D`
- Candidate: HC-only translated persistent volleys with contact target capture
- Starts: exact canonical positions imported from each authorized `frames.bin` run
- Five-sample screen: FAIL
- 100-sample volatile expansion: skipped by gate
- HCA-vs-Champion hashes bit-identical: yes
- Aggregate HC tape-band error: 185.816 -> 268.894 (-83.078 better)

| Matchup | Runs | Tape mean / band | Baseline mean | Candidate mean | Baseline error | Candidate error | Timeouts |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| Hand Cannoneer vs Halberdier | 5 | -76.5 / -76.5…-76.5 | -89.5 | -58.9 | 13 | 17.6 | 0 |
| Hand Cannoneer vs Hussar | 5 | 5.626 / -18.75…17.895 | 59.374 | 71.393 | 41.479 | 53.499 | 0 |
| Hand Cannoneer vs Champion | 5 | -76.607 / -82.5…-73.214 | -86.357 | -44.786 | 3.857 | 28.429 | 0 |
| Hand Cannoneer vs Elite Fire Lancer | 5 | -60.921 / -60.921…-60.921 | -68.658 | -42.868 | 7.737 | 18.053 | 0 |
| Hand Cannoneer vs Heavy Camel Rider | 5 | -67.52 / -73.571…-61.31 | -57.548 | -46.833 | 3.762 | 14.476 | 0 |
| Hand Cannoneer vs Paladin | 5 | 15.444 / -9.048…32.143 | 47.52 | 59.683 | 15.377 | 27.54 | 0 |
| Hand Cannoneer vs Elite Battle Elephant | 5 | 2.384 / -38.333…32.292 | 77.526 | 81.5 | 45.234 | 49.208 | 0 |
| Hand Cannoneer vs Elite Steppe Lancer | 5 | 8.026 / 8.026…8.026 | 63.395 | 68.116 | 55.368 | 60.089 | 0 |

## Gate failures and greater-than-25-point deltas

- Wrong stable winners: none.
- Greater-than-10-point regressions on good rows: Hand Cannoneer vs Champion, Hand Cannoneer vs Elite Fire Lancer, Hand Cannoneer vs Heavy Camel Rider
- Unresolved simulations: none.
- Hand Cannoneer vs Hussar: 53.499 points outside the tape band.
- Hand Cannoneer vs Champion: 28.429 points outside the tape band.
- Hand Cannoneer vs Paladin: 27.54 points outside the tape band.
- Hand Cannoneer vs Elite Battle Elephant: 49.208 points outside the tape band.
- Hand Cannoneer vs Elite Steppe Lancer: 60.089 points outside the tape band.

The candidate remains calibration-only; the generated product profile is unchanged.

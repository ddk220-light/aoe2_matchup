# Hand Cannoneer tape-motion profile A/B results

- Decision: **REJECT**
- Source SHA-256: `38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D`
- Candidate: HC-only formation spacing 0.35 tiles
- Starts: exact canonical positions imported from each authorized `frames.bin` run
- Five-sample screen: FAIL
- 100-sample volatile expansion: skipped by gate
- HCA-vs-Champion hashes bit-identical: yes
- Aggregate HC tape-band error: 185.816 -> 192.284 (-6.468 better)

| Matchup | Runs | Tape mean / band | Baseline mean | Candidate mean | Baseline error | Candidate error | Timeouts |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| Hand Cannoneer vs Halberdier | 5 | -76.5 / -76.5…-76.5 | -89.5 | -88 | 13 | 11.5 | 0 |
| Hand Cannoneer vs Hussar | 5 | 5.626 / -18.75…17.895 | 59.374 | 63.343 | 41.479 | 45.449 | 0 |
| Hand Cannoneer vs Champion | 5 | -76.607 / -82.5…-73.214 | -86.357 | -78.786 | 3.857 | 0 | 0 |
| Hand Cannoneer vs Elite Fire Lancer | 5 | -60.921 / -60.921…-60.921 | -68.658 | -63.868 | 7.737 | 2.947 | 0 |
| Hand Cannoneer vs Heavy Camel Rider | 5 | -67.52 / -73.571…-61.31 | -57.548 | -44.643 | 3.762 | 16.667 | 0 |
| Hand Cannoneer vs Paladin | 5 | 15.444 / -9.048…32.143 | 47.52 | 46.349 | 15.377 | 14.206 | 0 |
| Hand Cannoneer vs Elite Battle Elephant | 5 | 2.384 / -38.333…32.292 | 77.526 | 77.375 | 45.234 | 45.083 | 0 |
| Hand Cannoneer vs Elite Steppe Lancer | 5 | 8.026 / 8.026…8.026 | 63.395 | 64.458 | 55.368 | 56.432 | 0 |

## Gate failures and greater-than-25-point deltas

- Wrong stable winners: none.
- Greater-than-10-point regressions on good rows: Hand Cannoneer vs Heavy Camel Rider
- Unresolved simulations: none.
- Hand Cannoneer vs Hussar: 45.449 points outside the tape band.
- Hand Cannoneer vs Elite Battle Elephant: 45.083 points outside the tape band.
- Hand Cannoneer vs Elite Steppe Lancer: 56.432 points outside the tape band.

The candidate remains calibration-only; the generated product profile is unchanged.

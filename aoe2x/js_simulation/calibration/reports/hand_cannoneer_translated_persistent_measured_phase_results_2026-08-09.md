# Hand Cannoneer tape-motion profile A/B results

- Decision: **ACCEPT**
- Source SHA-256: `38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D`
- Candidate: HC-only translated persistent volleys on the measured 0.2/1.33-second phase
- Starts: exact canonical positions imported from each authorized `frames.bin` run
- Five-sample screen: PASS
- 100-sample volatile expansion: ran
- HCA-vs-Champion hashes bit-identical: yes
- Aggregate HC tape-band error: 185.816 -> 178.883 (6.933 better)

| Matchup | Runs | Tape mean / band | Baseline mean | Candidate mean | Baseline error | Candidate error | Timeouts |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| Hand Cannoneer vs Halberdier | 5 | -76.5 / -76.5…-76.5 | -89.5 | -88.5 | 13 | 12 | 0 |
| Hand Cannoneer vs Hussar | 100 | 5.626 / -18.75…17.895 | 59.374 | 61.467 | 41.479 | 43.572 | 0 |
| Hand Cannoneer vs Champion | 5 | -76.607 / -82.5…-73.214 | -86.357 | -67.786 | 3.857 | 5.429 | 0 |
| Hand Cannoneer vs Elite Fire Lancer | 5 | -60.921 / -60.921…-60.921 | -68.658 | -64.868 | 7.737 | 3.947 | 0 |
| Hand Cannoneer vs Heavy Camel Rider | 5 | -67.52 / -73.571…-61.31 | -57.548 | -53.452 | 3.762 | 7.857 | 0 |
| Hand Cannoneer vs Paladin | 100 | 15.444 / -9.048…32.143 | 47.52 | 45.486 | 15.377 | 13.343 | 0 |
| Hand Cannoneer vs Elite Battle Elephant | 100 | 2.384 / -38.333…32.292 | 77.526 | 68.152 | 45.234 | 35.86 | 0 |
| Hand Cannoneer vs Elite Steppe Lancer | 5 | 8.026 / 8.026…8.026 | 63.395 | 64.9 | 55.368 | 56.874 | 0 |

## Gate failures and greater-than-25-point deltas

- Wrong stable winners: none.
- Greater-than-10-point regressions on good rows: none.
- Unresolved simulations: none.
- Hand Cannoneer vs Hussar: 43.572 points outside the tape band.
- Hand Cannoneer vs Elite Battle Elephant: 35.86 points outside the tape band.
- Hand Cannoneer vs Elite Steppe Lancer: 56.874 points outside the tape band.

The candidate passed the full gate and is eligible for product-profile generation.

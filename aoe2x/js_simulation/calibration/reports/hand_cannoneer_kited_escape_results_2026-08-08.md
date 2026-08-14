# Hand Cannoneer HCA-style kited-escape A/B results

- Decision: **REJECT**
- Source SHA-256: `38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D`
- Samples: 5 stable; 100 volatile
- Aggregate HC band error: 185.816 -> 154.33 (31.486 better)
- HCA-vs-Champion hashes bit-identical: yes

| Matchup | Runs | Tape mean / band | Baseline mean | Candidate mean | Baseline error | Candidate error | Candidate side-3 win rate |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| Hand Cannoneer vs Halberdier | 5 | -76.5 / -76.5…-76.5 | -89.5 | -89.5 | 13 | 13 | 0% |
| Hand Cannoneer vs Hussar | 99 | 5.626 / -18.75…17.895 | 59.374 | 53.078 | 41.479 | 35.184 | 96.97% |
| Hand Cannoneer vs Champion | 5 | -76.607 / -82.5…-73.214 | -86.357 | -75.286 | 3.857 | 0 | 0% |
| Hand Cannoneer vs Elite Fire Lancer | 5 | -60.921 / -60.921…-60.921 | -68.658 | -71.079 | 7.737 | 10.158 | 0% |
| Hand Cannoneer vs Heavy Camel Rider | 5 | -67.52 / -73.571…-61.31 | -57.548 | -63.548 | 3.762 | 0 | 0% |
| Hand Cannoneer vs Paladin | 100 | 15.444 / -9.048…32.143 | 47.52 | 16.664 | 15.377 | 0 | 68% |
| Hand Cannoneer vs Elite Battle Elephant | 99 | 2.384 / -38.333…32.292 | 77.526 | 70.932 | 45.234 | 38.641 | 100% |
| Hand Cannoneer vs Elite Steppe Lancer | 5 | 8.026 / 8.026…8.026 | 63.395 | 65.374 | 55.368 | 57.347 | 100% |

## Failures and greater-than-25-point deltas

- Wrong stable winners: none.
- Greater-than-10-point regressions on good rows: none.
- Hand Cannoneer vs Hussar: 35.184 points outside the tape band.
- Hand Cannoneer vs Elite Battle Elephant: 38.641 points outside the tape band.
- Hand Cannoneer vs Elite Steppe Lancer: 57.347 points outside the tape band.

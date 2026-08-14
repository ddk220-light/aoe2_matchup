# Hand Cannoneer clearance-grid A/B results

- Decision: **REJECT**
- Source SHA-256: `38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D`
- Samples: 5 stable; 100 volatile
- Aggregate HC band error: 185.816 -> 151.176 (34.639 better)
- HCA-vs-Champion hashes bit-identical: no

| Matchup | Runs | Tape mean / band | Baseline mean | Candidate mean | Baseline error | Candidate error | Candidate side-3 win rate |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| Hand Cannoneer vs Halberdier | 5 | -76.5 / -76.5…-76.5 | -89.5 | -94 | 13 | 17.5 | 0% |
| Hand Cannoneer vs Hussar | 100 | 5.626 / -18.75…17.895 | 59.374 | 48.557 | 41.479 | 30.663 | 97% |
| Hand Cannoneer vs Champion | 5 | -76.607 / -82.5…-73.214 | -86.357 | -80.357 | 3.857 | 0 | 0% |
| Hand Cannoneer vs Elite Fire Lancer | 5 | -60.921 / -60.921…-60.921 | -68.658 | -68.816 | 7.737 | 7.895 | 0% |
| Hand Cannoneer vs Heavy Camel Rider | 5 | -67.52 / -73.571…-61.31 | -57.548 | -73.762 | 3.762 | 0.19 | 0% |
| Hand Cannoneer vs Paladin | 98 | 15.444 / -9.048…32.143 | 47.52 | 32.241 | 15.377 | 0.098 | 83.673% |
| Hand Cannoneer vs Elite Battle Elephant | 100 | 2.384 / -38.333…32.292 | 77.526 | 73.58 | 45.234 | 41.289 | 100% |
| Hand Cannoneer vs Elite Steppe Lancer | 5 | 8.026 / 8.026…8.026 | 63.395 | 61.568 | 55.368 | 53.542 | 100% |

## Failures and greater-than-25-point deltas

- Wrong stable winners: none.
- Greater-than-10-point regressions on good rows: none.
- Hand Cannoneer vs Hussar: 30.663 points outside the tape band.
- Hand Cannoneer vs Elite Battle Elephant: 41.289 points outside the tape band.
- Hand Cannoneer vs Elite Steppe Lancer: 53.542 points outside the tape band.

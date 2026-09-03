# Hand Cannoneer current-engine golden comparison — 2026-08-15

This report compares the current JavaScript engine with the two authorized
Hand Cannoneer golden archives. Every ratio uses all five tape repeats and each
simulation starts from that repeat's exact `starting_units` positions.

## Summary

- 2 matchup families
- 10 ratio rows
- 50/50 resolved simulations
- 0 wrong-winner repeats
- 0 rows above 25 points absolute mean delta
- 8/10 simulation means inside the tape five-repeat band
- 3.67 mean absolute row delta
- 1.42 median absolute row delta
- 19.80 maximum absolute row delta

Negative scores are owner 2/Hand Cannoneer wins. Positive scores are owner
3/melee wins.

| Matchup | Ratio | Tape mean | Tape range | Sim mean | Absolute delta | Wrong winners |
|---|---:|---:|---:|---:|---:|---:|
| Hand Cannoneer vs Champion | 5v10 | -39.20 | -59.00 to -12.00 | -59.00 | 19.80 | 0 |
| Hand Cannoneer vs Champion | 10v5 | -100.00 | -100.00 to -100.00 | -100.00 | 0.00 | 0 |
| Hand Cannoneer vs Champion | 15v20 | -89.80 | -93.00 to -81.67 | -93.00 | 3.20 | 0 |
| Hand Cannoneer vs Champion | 20v15 | -98.60 | -100.00 to -96.50 | -98.25 | 0.35 | 0 |
| Hand Cannoneer vs Champion | 20v20 | -98.95 | -100.00 to -98.25 | -96.50 | 2.45 | 0 |
| Hand Cannoneer vs Paladin | 5v10 | 87.56 | 86.67 to 88.06 | 88.33 | 0.78 | 0 |
| Hand Cannoneer vs Paladin | 10v5 | 12.67 | 5.00 to 17.22 | 13.89 | 1.22 | 0 |
| Hand Cannoneer vs Paladin | 15v20 | 73.11 | 70.97 to 76.39 | 74.72 | 1.61 | 0 |
| Hand Cannoneer vs Paladin | 20v15 | 30.52 | 23.52 to 39.26 | 30.19 | 0.33 | 0 |
| Hand Cannoneer vs Paladin | 20v20 | 49.25 | 43.33 to 59.44 | 56.25 | 7.00 | 0 |

The largest mean delta, Hand Cannoneer versus Champion 5v10, remains inside
the tape's wide observed band. The two simulation means just outside their
tape bands are Champion 20v20 by 1.75 points and Paladin 5v10 by 0.28 points.

## Provenance

| Archive | SHA-256 |
|---|---|
| `aoe2_golden_kiting_hcvschampion_2026-08-14.zip` | `468AB6CDBAD27FAEED9690E47A6B8BE4865A555DDD1063CFDE8B2A2D8D5C3A99` |
| `aoe2_golden_kiting_hcvspaladin_2026-08-14.zip` | `F472C648A06913B6E0DDAD1A7E2E9DAD17E70A7F62F113C5C2CD6A6F9AEC50F2` |

## Outputs

- `results.json`: all rows and repeat-level samples
- `results.csv`: compact comparison table
- `run-manifest.json`: run signature, worker count, and selected matchup IDs

The transient checkpoints and progress file are recovery artifacts and are not
required to interpret the committed result.

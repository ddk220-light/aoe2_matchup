# Standard-units simulation priority — 2026-08-03

## Scope

- Tape source: `calibration/source/aoe2_golden_STANDARD_UNITS_FINAL.zip` only.
- Tape SHA-256: `31A31FE39C025DDD88EB1F502FD62E0EC48464F4CBB72C1693D5C4FEED0713C9`.
- Simulation source: `calibration/runs/standard-units-current-5x-20260803`.
- Simulation sample: five seeds for each of 339 tape recordings (1,695 outputs).
- Success criterion: correct modal winner and median winner HP remaining within 25 percentage points of tape.
- User-accepted exceptions: Paladin–Elite Steppe Lancer and Heavy Camel–Elite Elephant.

## H1+H3 propagation findings: non-HC ranged versus melee

This is a calibration-branch result, not production behavior. The accepted
Hand Cannoneer H1+H3 candidate was applied without retuning to Arbalester,
Heavy Cavalry Archer, and Imperial Elite Skirmisher against all seven standard
melee lines.

- Evidence: `calibration/analysis/other_ranged_melee_h1_h3_20260803_results.json`.
- Full report: `calibration/analysis/other_ranged_melee_h1_h3_20260803_report.html`.
- Population: 133 FINAL recordings across 21 matchup families.
- Simulation sample: five deterministic seeds per recording and arm, for 665
  base simulations plus 665 H1+H3 simulations (1,330 total).
- Comparison: median signed winner HP remaining, where a negative value means
  the focal ranged line lost.
- Success criterion: same winner as FINAL tape and absolute gap no greater than
  25 percentage points.

| Ranged line | Base mean gap | H1+H3 mean gap | Within 25 points | Correct winners |
|---|---:|---:|---:|---:|
| Arbalester | 14.55 | 8.13 | 6/7 -> 7/7 | 7/7 -> 7/7 |
| Heavy Cavalry Archer | 13.27 | 14.60 | 6/7 -> 6/7 | 7/7 -> 6/7 |
| Imperial Elite Skirmisher | 16.63 | 47.24 | 6/7 -> 3/7 | 6/7 -> 4/7 |
| **Overall** | **14.81** | **23.32** | **18/21 -> 16/21** | **20/21 -> 17/21** |

The overall median absolute gap improves from 8.65 to 7.14 points, but this is
not a safe global improvement. The mean gap worsens from 14.81 to 23.32 points
because of several large regressions, two wrong-winner reversals, and one
non-resolving family.

### Reusable result

Arbalester is the only line that supports a scoped follow-up. H1+H3 improves
six of its seven melee families, brings all seven within the 25-point target,
and preserves every winner. Notable changes include:

- Arbalester-Paladin: absolute gap improves from 21.67 to 0.76 points.
- Arbalester-Hussar: absolute gap improves from 26.72 to 13.98 points, moving
  the family inside the target.
- Arbalester-Champion is the one regression, but remains within target with the
  correct winner: 2.78 to 11.11 points off.

Champion-Heavy Cavalry Archer also improves substantially, from 39.95 to 6.41
points off, but the Heavy Cavalry Archer line is not globally safe because it
introduces the Halberdier reversal below.

### Blocking regressions

- Champion-Imperial Elite Skirmisher: FINAL and base have Champion winning at
  about 54% HP remaining. H1+H3 instead gives Imperial Elite Skirmisher the
  win at 71.43% HP in all 20 simulations; the absolute gap becomes 125.81
  points.
- Paladin-Imperial Elite Skirmisher: FINAL is Paladin +87.46% and base is
  Paladin +90.24%. All 20 H1+H3 simulations reach the 600-second cap, so the
  candidate produces no valid winner-HP result. Fight duration is not an
  optimization target; the cap matters only because the fight never produces
  the required winner and remaining-HP measurement.
- Halberdier-Heavy Cavalry Archer: FINAL is Halberdier +16.27% and base is
  Halberdier +24.92%. H1+H3 flips all 50 simulations to Heavy Cavalry Archer
  +30.69%, increasing the absolute gap from 8.65 to 46.96 points.

### Propagation decision

- Keep H1+H3 isolated for Hand Cannoneer while it remains a calibration
  candidate.
- Test an Arbalester-scoped version separately; do not infer that the full
  combined rule is safe for every ranged line.
- Do not enable the candidate for Imperial Elite Skirmisher.
- Diagnose or explicitly guard the Heavy Cavalry Archer-Halberdier reversal
  before considering Heavy Cavalry Archer coverage.
- Separate H1 post-swing behavior from H3 obstruction steering in the next
  cross-line test so the reusable mechanism can be identified without carrying
  the failing behavior with it.

## Original baseline recommended order

1. **Hand Cannoneer mechanics.** Seven failing matchup families share HC. The failures span a wrong winner and large margin errors in both directions, so this should be treated as movement, kiting, firing-cycle, or melee-contact behavior rather than a simple damage adjustment.
2. **Re-evaluate Heavy Scorpion after the HC fix.** Scorpion has only two failures: HC–Scorpion and Elite Skirmisher–Scorpion. Because the former overlaps the HC cluster, rerun before changing Scorpion globally. If the latter remains, isolate the ranged-versus-siege interaction.
3. **Champion–Heavy Caval Archer.** Tape has Heavy Caval Archer at +45.2% versus +1.8% in the sim, a -43.4 point miss. This is the highest-confidence isolated residual because the tape has 14 recordings and a stable 13–1 winner split. The later H1+H3 candidate reduces this gap to 6.41 points, but cannot be promoted for the whole Heavy Cavalry Archer line because it reverses Halberdier-Heavy Caval Archer.
4. **Siege Onager interaction cluster.** Three independent non-HC failures remain: Halberdier–Siege Onager (-47.3 points), Elite Fire Lancer–Siege Onager (-36.3), and Siege Onager–Elite Elephant (+32.1). The error direction is mixed, so a global damage or reload adjustment is unlikely to be safe; inspect projectile, splash, formation, contact, and armor interactions.
5. **Elite Skirmisher–Elite Elephant termination.** All 20 simulation samples reached the 600-second cap. The leading HP margin is numerically close to tape, but the fight never resolves, making this a separate kiting/pathing termination bug.

## Lower-priority cleanup

- Arbalester–Elite Fire Lancer: 27.8 points outside tape, two tape recordings.
- Arbalester–Hussar: 26.7 points outside tape, five tape recordings. The later
  H1+H3 candidate reduces this to 13.98 points with the correct winner.

Both are only slightly outside the 25-point goal and should wait until the shared-mechanic clusters are fixed and the full matrix is rerun.

## Decision summary

The current ranged-versus-melee decision is **keep HC H1+H3 isolated -> test an
Arbalester-scoped version -> diagnose the Imperial Elite Skirmisher and Heavy
Cavalry Archer regressions -> only then consider broader propagation**.

For the remaining standard-unit queue, rerun HC-Heavy Scorpion after the HC
work, then continue with the Siege Onager cluster and the existing
Skirmisher-Elephant termination issue. Recompute the full matrix after every
shared-mechanic change because HC-Heavy Scorpion and HC-Siege Onager overlap
later clusters.

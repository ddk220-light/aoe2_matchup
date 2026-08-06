# Kiting AI order layer v2 — measured and converged (2026-08-06)

Replaces the first-pass beat controller (commit `ce4e2cdd`, mean band error
65.2, 2 wrong winners) with a fully measured reconstruction of both sides of
the `aoe2_golden_kiting_arbalestervschampion` archive (25 fights, command
streams decoded in full). Result: **mean band error 3.88, 0 wrong winners,
25/25 sampled orders resolved on every ratio**; 10v5, 15v20 and 20v15 land at
band error 0.

## Command-stream facts (all 25 fights)

### Kited side (player 2, scripted — not unit AI)

- Setup at 0.2 s: `stop` + stand-ground stance. No shot lands before the
  first attack order in any fight.
- **Attack beat every 2.00 s** (p10 1.99 / p90 2.01), first at ~2.0 s. Each
  beat issues one `interact` per designated target with an explicit unitIds
  roster. Assignment is damage bookkeeping:
  - per-shot damage is **5.0** — all 3270 recorded champion hp-drop quanta
    are multiples of 5, and the n-assigned-vs-target-HP p10 column
    reproduces `n = hp/5 + 1` at every n from 2 to 15;
  - targets still alive from the previous beat keep shooters first (in the
    previous beat's order); fresh targets are picked **nearest the group
    centroid** (rank-1 in 352/406 fresh designations);
  - each target gets exactly enough shooters to kill **plus one insurance
    shot**; the remainder spills to the next target; leftovers pile onto the
    last target (the recorded 15+5-on-one-champion endgame beats);
  - which arbs go to which target is geometrically arbitrary (nearest-own-
    target partition agreement ~50% = chance), so the sim slices the
    id-ordered roster;
  - probe C: p50 **100%** of assigned damage lands within 1.7 s of the beat
    (25/613 beat-targets below 90%).
- **Move order 0.67 s after each beat** (p10 0.66 / p90 0.68), plus one
  pre-fight move at ~1.3 s: a single shared waypoint + `formFormation 2`,
  sent twice. All **357 waypoints** sit on the perimeter lattice of the
  square ring centered on the map, half-size 3.0, step 1.5 (16-tile map →
  {5, 6.5, 8, 9.5, 11} on both axes). Every fight walks the ring in one
  consistent rotational direction, advancing 0-2 lattice steps per move.
  Realized waypoint lead over the group's own ring projection: p25 3.07 /
  p50 3.96 / p75 4.6 — reproduced by snapping (projection + 4.0) to the
  lattice, monotonic.
- **No auto-fire**: every champion hp drop lands 0.38-1.5 s after a beat
  (p50 0.56), none between beats. One shot per kiter per order.
- Formation: the group converges to a compact grid (20 units ≈ 2.0 x 2.3
  tiles, nearest-neighbor p50 0.29-0.43) and **reforms every cycle** — tape
  arb median displacement is 0.40 tiles/s against the 0.64 duty-cycle
  ceiling because arrived units stop while stragglers catch up. Implemented
  as per-unit absolute slots (~sqrt(n) columns, 0.5 spacing) at the shared
  waypoint.

### Melee side (player 3, one ai-order wave then unit AI)

- One wave of `aiOrder` records (orderType 700, targetOwner 2) at
  0.58-1.82 s. Coverage is exact across the four multi-champion fights:
  **all but the four lowest-id units** (10 champions → 6 ordered, 15 → 11,
  20 → 16; the unordered are 1605-1608 every time), while a side of ≤5 gets
  a single recipient-only platoon order covering everyone (10v5: all 5 move
  by 2.2 s).
- **Unordered units are spawn pickets**: they stand until an enemy enters
  their line of sight. In 5v10 two pickets first move at **15.0 s and
  19.1 s** — exactly when the kiting lap reaches their corner — and that
  ambush is what collapses the recorded 5v10 (arbs 5→0 between 24-32 s
  after running untouched for 24 s). In 10v5/20v20 the same units move at
  ~1-2 s because arbs spawn inside their LOS.
- **Pursuit is sticky and LOS-blind**: the pursued arb ranks OUTSIDE the 5
  nearest more often than not (7170/17884 heading samples rank 6+), pursuit
  distances reach 13 tiles vs LOS 5, and champions idle ≥1 s only 233 short
  times across 25 fights. A dead target is replaced by the nearest live
  kiter immediately.
- **Target discipline**: 64% of a chaser's sustained (≥0.5 s) adjacency
  windows produce no hit at all — champions brush past non-target arbs
  without swinging — while the svc control shows the same champion hitting
  its OWN caught target within the first second 63-80% of the time.
  Engagement in a kited world is therefore restricted to the pursuit target.
- **Release is unconditional**: hits land at champion-victim center distance
  p50 0.69 / max 1.91 at the damage frame — the target had already fled up
  to ~1.9 tiles. There is no delivery-reach check (the engine already
  matches this); all discipline is in the swing START.
- **Swing-start dwell**: window hit rate rises smoothly with duration
  (0.17 at 0.5 s / 0.25 at 1.0 s / 0.46 at 1.5 s / 0.51 at 2.0 s,
  attribution-inflated upper bounds) → the swing start needs ~1.0 s of
  continuous in-reach dwell on the pursuit target. A kiter that stands only
  0.67 s per beat escapes most catches; a blocked or cornered one (the 5v10
  pocket) is hit repeatedly. 150/200 victims were WALKING at swing start,
  so there is no target-standing requirement — only dwell.
- **Chase repath**: recorded chasers re-aim on a ~0.4-0.5 s cadence and
  realize p50 0.89 of their 1.056 dat speed; their in-reach windows against
  a walking target last 0.7-1.4 s, where frictionless per-tick tracking
  holds reach indefinitely (the sim's glued tail produced 6-16 s windows
  the tape never shows). Chasers therefore walk toward their target's
  position sampled every 0.5 s (per-unit phase). The stop rule still tests
  the live target.

## Ballistics (the missing damage mechanism)

The first controller pass lost ~40% of assigned shots: arrows aimed at the
target's fire-time position expire when a tangentially-running champion
leaves its box, yet the tape lands ~100% of assigned shots. The mechanism is
**Ballistics** (dat tech 93): 104 effect commands of type 0 set **attribute
19 (projectile smart mode) to 1** on an explicit list of 87 projectile
units — including the arbalester's 507 (and its secondary 1930), the
skirmisher's 366, and the heavy scorpion's 627. Bit 1 = lead moving
targets; bit 2 = full damage on unintended targets (the Fire Lancer's raw
`smart_mode 2`). Sources: the installed dat
(SHA `CE3530DF36CF0B33...`, matching every fixture's provenance lock),
[ugc.aoe2.rocks attributes reference](https://ugc.aoe2.rocks/general/attributes/attributes/),
[AoK Heaven smart-projectiles thread](https://aok.heavengames.com/cgi-bin/forums/display.cgi?action=st&fn=4&tn=44700).

Implementation: `ranged.smart_mode` exported per fixture (raw projectile
smart_mode, OR 1 when tech 93 lists the projectile — this project's data
model is fully-teched Imperial); `releaseRangedShot` aims led shots at the
target's current position plus its actual per-tick displacement times
flight time (two-pass fixed point). Velocities are computed transiently in
`moveUnits` and never stamped on units, so no hash outside the ranged
matchups can move. Targets that change direction mid-flight still escape —
which is what the avs walked-away residue measures.

NOTE: the exporter assumes Ballistics is researched; add civ tech-tree
gating before exporting an archer fixture for a civ that lacks it.

## Circuit results (25 sampled orders, band = tape min..max of 5 repeats)

| ratio | tape band (signed) | sim median | identity | band error |
|-------|--------------------|-----------|----------|------------|
| 10v5  | [-100, -92.5] | -100  | -100  | 0    |
| 15v20 | [-74.2, -45.8] | -49.2 | -30.0 | 0    |
| 20v15 | [-100, -91.3] | -94.4 | -93.1 | 0    |
| 20v20 | [-95, -91.3]  | -81.9 | -91.3 | 9.4  |
| 5v10  | [51.4, 55.7]  | 65.7  | 65.7  | 10.0 |

Mean 3.88, **0 wrong winners**. Residuals: 20v20's median loses 2-3 arbs the
tape does not (identity order sits inside the band); 5v10's champions win
~10 points cleaner than tape (sim arbs extract less champion HP before the
pocket collapse).

## Parity

- Melee + Fire Lancer matchups (107 ratios): **bit-identical** to HEAD
  (`ce4e2cdd`), verified via a HEAD worktree hash dump under the same
  circuit env.
- The four arrow matchups (avs/sva/svc/svp) change behavior by design
  (smart_mode 1 fixtures) and were re-validated by circuit — see the
  full-circuit table in the commit message.

## Five-archive extension (same day, second commit)

The controller generalized to the full {arbalester, elite skirmisher, heavy
cav archer} x {champion, paladin} kiting grid (five new archives, 125
fights) with three additions, each measured:

1. **Per-kiter cycle profiles** (`kiteProfile` in the truth fixture): the
   script runs a 0.667 s order clock; arbalesters beat every 3 slots
   (2.00 s, move +0.67), elite skirmishers every 5 (3.33 s — reload 3.0 —
   moves +0.67 and +2.00, cycle move pairs share one waypoint), heavy cav
   archers every 3 with first beat at ~0.57 s, finishing top-ups +0.67 and
   move +1.33. Wave coverage (all but the four lowest ids; <=5 gets one
   platoon order) verified EXACT on every multi-champion fight of all six
   archives.
2. **Reach-gated bookkeeping**: shooters are only assigned to targets they
   can legally hit (reach + minimum range) — 613/613 recorded beat-targets
   land ~100% of assigned damage, and without the gate a chaser grinding a
   straggler soaked whole volleys out of range. Pressure split: when even
   the full pool cannot kill the first target, pools >= 12 split ~75/25
   over the first two targets (mains 14-16 of 20, ~11 of 15; rosters of 10
   or fewer stack all-on-one in every archive; hcc's mains are exactly
   ceil(70/6)+1 = 13, disambiguating bookkeeping from the split).
3. **Minimum-range pin** (dat type_50.min_range, the esc/kac discriminator):
   a chaser inside its target's own minimum range cannot be shot by it —
   dwell accumulates through reach flickers while pinned (the skirmisher
   tapes' steady grind: 0.37 hit rate inside 0.5 s of contact) while
   min-range-0 kiters never pin and reset every walk cycle (the arbalester
   tapes' 0.09-0.17). Symmetrically, a PINNED ranged unit holds fire and
   min-range-retreats without freelancing onto another target — which also
   replaced scorpion_vs_champion's residual with its best-ever fit
   (12.24 -> 2.90 after the point-blank hole and the freelance fallback
   were both closed).

Final circuit (25 orders each, whole corpus): **21 matchups, 105 ratios, 0
wrong winners.** Kiting: kac 3.88 / avp 2.84 / esc 2.36 / esp 0.00 /
hcc 0.66 / hcp 0.54. Ranged: avs 1.70 / sva 0.68 / svc 2.90 / svp 1.38.
Melee + Fire Lancer bit-identical throughout.

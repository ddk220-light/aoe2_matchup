# Clean-room sim — calibration status, 2026-08-06

Branch `codex/cleanroom-champion-sim`. Continues
`CALIBRATION_STATUS_2026-08-05.md`. Commits this day: `756f1e7b` (Fire
Lancer charge), `a31e721c` (ranged combat v1), `ff00a99e` (scorpion
pass-through + minimum range), `38f54df3` (min-range retreat), `86d0137d`
(scorpion_vs_paladin), `ce4e2cdd` (kiting WIP), `4ea8dcec` (kiting order
layer v2 + ballistics), `2b969455` (five-archive kiting grid + min-range
pin).

## Headline

**The whole corpus — 21 matchups, 105 tape ratios, ~525 sampled circuit
runs — calls every winner correctly.** Every matchup's median winner-HP%
sits inside or within a few points of the tape's own five-repeat envelope.
The engine now covers melee, charge attacks, projectile combat,
pass-through bolts, ballistics lead, minimum range, and both sides of the
scripted-kiting AI — with every constant either dat-sourced or measured on
the authorized tapes, none fitted.

## Corpus scorecard (mean band error over 5-9 ratios each, 25 sampled orders)

| family | matchup | mean | wrong winners |
|---|---|---|---|
| melee | champion_vs_paladin (26 ratios) | 0.94 | 0 |
| melee | champion_vs_elephant | 0.38 | 0 |
| melee | paladin_vs_elephant | 0.21 | 0 |
| melee | champion_vs_steppe | 0.77 | 0 |
| melee | paladin_vs_steppe | 1.87 | 0 |
| melee | steppe_vs_elephant | 0.41 | 0 |
| charge | champion_vs_firelancer | 2.41 | 0 |
| charge | paladin_vs_firelancer | 0.40 | 0 |
| charge | firelancer_vs_steppe | 3.57 | 0 |
| charge | firelancer_vs_elephant | 0.72 | 0 |
| ranged | arbalester_vs_eliteskirm | 1.70 | 0 |
| ranged | scorpion_vs_arbalester | 0.68 | 0 |
| ranged | scorpion_vs_champion | **2.90** (was 6.32) | 0 |
| ranged | scorpion_vs_paladin | **1.38** (was 1.98) | 0 |
| kiting | arbalester_vs_champion | 3.88 | 0 |
| kiting | arbalester_vs_paladin | 2.84 | 0 |
| kiting | eliteskirm_vs_champion | 2.36 | 0 |
| kiting | eliteskirm_vs_paladin | **0.00** | 0 |
| kiting | hcavarcher_vs_champion | 0.66 | 0 |
| kiting | hcavarcher_vs_paladin | 0.54 | 0 |

Melee + Fire Lancer families are hash-verified bit-identical across every
engine change of the day. Test suite constant at 131/157 (the 26 failures
are the documented pre-existing set).

## Mechanics landed today (each with its measurement doc)

1. **Fire Lancer charge** (`FIRE_LANCER_CHARGE_2026-08-06.md`): charge_type
   6 volley as the first attack cycle on the dat special-graphic timing,
   flat armor-ignoring projectile damage, post-charge re-entry through the
   acquisition roll.
2. **Ranged combat v1** (`RANGED_COMBAT_2026-08-06.md`): projectiles as
   independent stepped entities; Euclidean range circles for shots vs
   Chebyshev boxes for melee; hit-on-meeting-the-box, expire-at-aim.
3. **Scorpion pass-through** (`SCORPION_PASSTHROUGH_2026-08-06.md`):
   line-sweep bolts, full damage on the action target, exactly half on
   every other crosser (5407/5407), 3.0-tile overshoot.
4. **Ballistics** (`KITING_AI_ORDER_LAYER_2026-08-06.md`): dat tech 93 sets
   projectile attribute 19 bit 1 (lead) on 87 projectile units incl. arb
   507, skirm 366, scorpion 627; led shots aim at position + per-tick
   velocity x flight time. Recovered the ~40% of beat-assigned shots that
   aim-at-fire-position lost against tangential runners.
5. **Kiting order layer** (same doc): the kited side's scripted 0.667 s
   order clock (per-kiter cycle profiles recorded as `kiteProfile` in each
   truth fixture), damage-bookkeeping target assignment (kill + one
   insurance shot) with reach gating and a 75/25 pressure split, square
   ring-lattice waypoints with reforming grid-slot formations, no
   auto-fire; the melee side's order wave (all but the four lowest ids,
   platoon at <=5), spawn pickets, sticky LOS-blind pursuit with 0.5 s
   repath staleness, strict target discipline, unconditional release, and
   the ~1.0 s swing-start dwell.
6. **The minimum-range pin** (the day's closing discovery): a chaser inside
   its target's dat min_range cannot be shot by its own victim — dwell
   accumulates through reach flickers while pinned, which is the
   skirmisher tapes' steady grind; min-range-0 kiters never pin, which is
   the arbalester tapes' near-immunity. Symmetrically, a pinned ranged
   unit holds fire and min-range-retreats without freelancing onto another
   target. One rule, three payoffs: eliminated the corpus's last wrong
   winner (eliteskirm_vs_champion 10v5) and took both scorpion-vs-melee
   matchups to their best-ever fits.

## Provenance notes

- The authoritative dat is the INSTALLED
  `D:\SteamLibrary\steamapps\common\AoE2DE\resources\_common\dat\empires2_x2_p1.dat`
  (SHA `CE3530DF36CF0B33…`, matching every fixture's provenance lock). The
  iCloudDrive copies hash differently — a different build; do not use them.
- Five new SHA-locked truth fixtures (125 fights) + the Heavy Cavalry
  Archer fixture (Saracens master 474, dat-locked: speed 1.54, delay
  0.897, reload 1.8, projectile 478 smart_mode 1).
- The exporter assumes Ballistics researched (fully-teched Imperial
  model); add civ tech-tree gating before exporting an archer fixture for
  a civ without it.

## Known residuals and cautions

- Largest per-ratio residuals (all correct-winner): kac 20v20 (9.4) and
  5v10 (10), esc 20v15 (9.9), svp 10v5/20v15 (~9.5), firelancer_vs_steppe
  3v5/3v6 (13/10.3), paladin_vs_steppe 2v3 (13.8).
- **The dwell seesaw**: the arbalester and skirmisher kiting archives pull
  the swing-dwell model in opposite directions; any change to dwell,
  repath, or the pin must re-run kac AND esc AND svc/svp together before
  judging it.
- `paladinvspaladin_2026-08-04.zip` remains the one tape on disk not wired
  into the circuit (superseded-era basics archive; the mirror baseline is
  the champion mirror).

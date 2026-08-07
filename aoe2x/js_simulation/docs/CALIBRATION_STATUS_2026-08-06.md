# Clean-room sim — calibration status, 2026-08-06

Branch `codex/cleanroom-champion-sim`. Continues
`CALIBRATION_STATUS_2026-08-05.md`. Commits this day: `756f1e7b` (Fire
Lancer charge), `a31e721c` (ranged combat v1), `ff00a99e` (scorpion
pass-through + minimum range), `38f54df3` (min-range retreat), `86d0137d`
(scorpion_vs_paladin), `ce4e2cdd` (kiting WIP), `4ea8dcec` (kiting order
layer v2 + ballistics), `2b969455` (five-archive kiting grid + min-range
pin), plus the steppe-chaser kiting column (three archives, same day).

## Headline

**The whole corpus — 28 matchups, 140 tape ratios, ~700 sampled circuit
runs — calls every winner correctly.** Every matchup's median winner-HP%
sits inside or within a few points of the tape's own five-repeat envelope.
The engine now covers melee, charge attacks, projectile combat,
pass-through bolts, ballistics lead, minimum range, and both sides of the
scripted-kiting AI against slow (champion), fast (paladin),
faster-than-the-kiter reach-fighter (Elite Steppe Lancer), and trampling
tank (Elite Battle Elephant) chasers — with every constant either
dat-sourced or measured on the authorized tapes, none fitted. The
elephant column converged OUT OF THE BOX (mean 1.98, no engine change):
the trample model, the kiting order layer, and the corrected wave rule
compose with zero new mechanics.

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
| kiting | arbalester_vs_paladin | 2.90 | 0 |
| kiting | eliteskirm_vs_champion | 2.54 | 0 |
| kiting | eliteskirm_vs_paladin | 0.22 | 0 |
| kiting | hcavarcher_vs_champion | **0.00** | 0 |
| kiting | hcavarcher_vs_paladin | 0.54 | 0 |
| kiting | arbalester_vs_steppe | 12.68 | 0 |
| kiting | eliteskirm_vs_steppe | 0.78 | 0 |
| kiting | hcavarcher_vs_steppe | 4.04 | 0 |
| kiting | arbalester_vs_elephant | 1.98 | 0 |
| kiting | hcavarcher_vs_elephant | 2.86 | 0 |
| kiting | eliteskirm_vs_elephant | **0.14** | 0 |
| kiting | arbalester_vs_firelancer | 4.36 | 0 |

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
6. **The minimum-range pin**: a chaser inside
   its target's dat min_range cannot be shot by its own victim — dwell
   accumulates through reach flickers while pinned, which is the
   skirmisher tapes' steady grind; min-range-0 kiters never pin, which is
   the arbalester tapes' near-immunity. Symmetrically, a pinned ranged
   unit holds fire and min-range-retreats without freelancing onto another
   target. One rule, three payoffs: eliminated the corpus's last wrong
   winner (eliteskirm_vs_champion 10v5) and took both scorpion-vs-melee
   matchups to their best-ever fits.
7. **Reach fighters swing on reach entry — no dwell** (steppe column, same
   doc): 3508 attributed Elite Steppe Lancer kills show median pre-swing
   dwell 0.0 s and median swing-start gap 1.5 tiles — its exact outline
   reach. The dwell gate is range-0 chaser behavior; the discriminator is
   the unit's own dat `attack_range_tiles`.
8. **The melee wave is `slice(4)` at every roster size** (the day's closing
   correction): a 5-melee side gets ONE aiOrder to the single highest id —
   recorded verbatim (recipient 1609, location = kiter centroid) in every
   10v5 of every archive including the champion one — and the other four
   are native LOS pickets (the steppe tapes show them frozen at spawn for
   20+ s; kac's pickets acquired in ~2 s by geometry, which the old
   "platoon covers everyone" reading had mistaken for order coverage).
   Fixing this alone repaired avst 10v5's wrong winner, zeroed esc 10v5,
   and took hcavarcher_vs_champion to a perfect 0.00 mean. Plus one bug
   fix: kite-move marchers no longer get goal-routed off their slot march
   by local avoidance.

## Provenance notes

- The authoritative dat is the INSTALLED
  `D:\SteamLibrary\steamapps\common\AoE2DE\resources\_common\dat\empires2_x2_p1.dat`
  (SHA `CE3530DF36CF0B33…`, matching every fixture's provenance lock). The
  iCloudDrive copies hash differently — a different build; do not use them.
- Five new SHA-locked truth fixtures (125 fights) + the Heavy Cavalry
  Archer fixture (Saracens master 474, dat-locked: speed 1.54, delay
  0.897, reload 1.8, projectile 478 smart_mode 1).
- Three steppe-column truth fixtures (75 fights), zip SHA-256:
  arbalestervssteppe `3F4D8F0B69AE…`, eliteskirmvssteppe `9500E4703ACB…`,
  hcavarchervssteppe `74D83F2EBE0D…`. The chaser reuses the existing
  Elite Steppe Lancer fixture (Cumans master 1372, dat-locked).
- Three elephant-column truth fixtures (75 fights), zip SHA-256
  arbalestervselephant `25B5C474F573…`, hcavarchervselephant
  `CB7D0D448D35…`, eliteskirmvselephant `12984A63F05B…`; the chaser
  reuses the Elite Battle Elephant fixture (Burmese master 1134). All
  tapes obey every established rule and the elephant dominates (74-99%
  HP). All three converged out of the box (1.98 / 2.86 / 0.14).
- One Fire Lancer-chaser fixture (25 fights), zip SHA-256
  arbalestervsfirelancer `2993135C74E0…` — the first CHARGE unit as a
  kited-world chaser. The tape splits the column (arbs win 10v5, 20v15,
  20v20; lancers win 5v10 and 15v20) and the sim reproduces every
  winner out of the box (mean 4.36): the charge-volley model composes
  with the kiting order layer unchanged.
- The exporter assumes Ballistics researched (fully-teched Imperial
  model); add civ tech-tree gating before exporting an archer fixture for
  a civ without it.

## Known residuals and cautions

- Largest per-ratio residuals (all correct-winner): arbalester_vs_steppe
  20v15 (21.6), 20v20 (17) and 10v5 (14) — the sim lancer over-converts
  against the arbalester group in wave fights; the tape's hit chains break
  after 1-2 hits on the flowing formation where the sim's re-close
  succeeds more often. Then kac 20v20 (9.4) and 5v10 (10), esc 20v15
  (9.9), hcst 20v15 (9.4), svp 10v5/20v15 (~9.5), firelancer_vs_steppe
  3v5/3v6 (13/10.3), paladin_vs_steppe 2v3 (13.8).
- **The dwell seesaw**: the arbalester and skirmisher kiting archives pull
  the swing-dwell model in opposite directions; any change to dwell,
  repath, or the pin must re-run kac AND esc AND svc/svp together before
  judging it.
- `paladinvspaladin_2026-08-04.zip` remains the one tape on disk not wired
  into the circuit (superseded-era basics archive; the mirror baseline is
  the champion mirror).

## Held-out check: the standard-units archive

The 28 matchups above are the *calibration* corpus — the tapes the engine
was measured against. The standard-units archive is the held-out set: 339
recorded fights, 101 distinct matchups, 14 units, none of it used to set a
constant. Full results in
[`STANDARD_UNITS_SUMMARY_2026-08-07.md`](STANDARD_UNITS_SUMMARY_2026-08-07.md)
(mean winner-HP% delta per matchup) and
[`STANDARD_UNITS_GAP_REPORT_2026-08-06.md`](STANDARD_UNITS_GAP_REPORT_2026-08-06.md)
(the earlier blind median-vs-band scoring). Headline: the purchase rule
reproduces **122/122** starting rosters, the order taxonomy **119/122**
command signatures, and the sim agrees with the tape on the winner in
**97/101** matchups (**77/80** excluding the ranged-vs-ranged group, whose
duel script is still undecoded), mean |delta| 14.6 / median 9.4.

Two per-unit biases dominate the residual and are the obvious next tape
requests: **Hand Cannoneer** (-33.5 in kite matchups, +2.3 in
ranged-vs-ranged — so it is the *constructed* kite beat, not the accuracy
model, that is wrong) and **Siege Onager** (-12.3 overall, two-signed
across opponents — the blast model fixed the winners without fixing the
magnitudes).

**Do not run this comparison without
`AOE2X_EXP_ENGAGEMENT=pursuit AOE2X_EXP_ORDERS=1`.** Without those flags
melee never walks to its designated target and the whole table silently
inverts (scorpions beating 21 champions, and so on) while still looking
like plausible output.

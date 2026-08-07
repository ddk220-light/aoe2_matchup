# Kiter flow: three measured fixes, and the one that is not landable yet

Investigation into the last wrong-winner matchup in the held-out standard-units
set — **Elite Skirmisher vs Heavy Camel Rider**, where the tape has the camels
winning with 39.8% of their HP pool and the sim had the skirmishers winning most
of the time.

Everything below is measured on the authorized tapes or read from the dat. No
constant here is fitted to an outcome.

## What was wrong: the kite formation could not flow

Comparing the tape's skirmisher block with ours, beat for beat:

| | tape | sim (before) | sim (after) |
|---|---:|---:|---:|
| realized step / desired step, mean | 0.80–0.82 | 0.57 | **0.82** |
| marching ticks stalled (<25% of step) | 14–20% | 38.7% | **15.9%** |
| block moving, mean fraction | 0.79 | 0.54 | 0.67 |
| settled frames | 6% | 36% | 19% |
| centroid advance per 3.335 s beat, p50 | 2.18 | 1.47 | **2.17** |

Two independent causes, each worth roughly half.

### 1. Formation-mates do not obstruct each other

While the kite formation marches, an ally sitting 0.42 tiles directly ahead
costs a tape skirmisher almost nothing: stalled 19.7% of frames against 14.4%
with a clear path, median step still a full walk. The block's own
nearest-neighbour pairs sit **inside** our 0.400 separation 58.6% of the time
and bottom out at 0.000 — it reforms straight through itself.

Our engine enforced the box, and 38.7% of our marching kiter-ticks stalled with
73% of those behind an ally.

Scope is what matters, and it is why the blanket version of this was
A/B-rejected earlier. Chasers under aiOrder attack waves are not exempt: tape
camels pay nothing for an ally ahead (19.5% vs 18.5%), but kac champions do
(13.2% vs 5.6%). The discriminator is **holding a formation move order**, not
being in motion — a unit that has arrived at its slot keeps its order until the
next beat, and gating on motion leaves those arrived units standing as walls.

### 2. A released swing does not hold a unit any more

Of 4175 recorded Elite Skirmisher shots, **39% leave the bow while the shooter
is already moving**, the median release-to-movement gap is 0.05 s, and 89% are
moving within 0.25 s. Our engine froze the unit for the rest of its 1.2 s attack
animation — 0.693 s after the arrow was away — which ate roughly a third of
every 3.335 s beat.

Recovery still governs *retargeting* (the measured "killers retarget half an
animation after the kill" rule is untouched); this is movement only, and only
for a unit already holding a move order, so no melee fight in the corpus can
reach it.

### 3. A projectile is a body too

An arrow lands when its own dat half width (projectile `collision_size_x`, 0.1
for every archer projectile in the corpus) meets the victim's collision box —
the same rule the scorpion bolt already used. Recorded arrows are last seen at a
Chebyshev separation from the victim's centre whose p97 is **0.310 against
champions** (collision 0.20 → 0.30) and **0.347 against heavy camels**
(collision 0.25 → 0.35). The camel is the first victim in the corpus whose
collision box differs from its outline, which is why a bare-collision rule
survived this long.

## Corpus effect

Melee, charge and scorpion matchups are **bit-identical** (they hold no move
orders and their projectile geometry is unchanged in the relevant cases). Over
the ten ranged/kiting matchups the sum of mean band errors goes 16.74 → 16.20
with **0 wrong winners** anywhere:

| matchup | before | after |
|---|---:|---:|
| arbalester_vs_champion_kiting | 3.88 | **1.90** |
| eliteskirm_vs_champion_kiting | 2.54 | 3.96 |
| arbalester_vs_paladin_kiting | 2.90 | 3.06 |
| eliteskirm_vs_paladin_kiting | 0.22 | 0.40 |
| hcavarcher_vs_champion_kiting | 0.00 | 0.00 |
| hcavarcher_vs_paladin_kiting | 0.54 | 0.32 |
| arbalester_vs_eliteskirm | 1.70 | 1.46 |
| scorpion_vs_champion | 2.90 | 2.90 |
| scorpion_vs_paladin | 1.38 | 1.38 |
| scorpion_vs_arbalester | 0.68 | 0.82 |

## The camel fight is still wrong, and this is why

Fixing the flow did **not** fix the outcome: camels win 10 of 25 sampled runs
(mean −9.4 against the tape's +39.8), against 13 of 23 before. The flow was a
real defect, but it was not the one deciding this fight.

The deciding mechanism is now identified and measured:

**Minimum range suppresses the shooter, not just the target it aimed at.** Per
attack beat of the camel tape, skirmishers that got an arrow away had their
nearest camel at p50 2.2 tiles (p10 1.4); those that held fire had it at p50 1.0
(p90 1.4). The tape's AI names 439 shooters across the fight and only **233**
arrows leave — and 225 of those 233 hit, so the game's arrows essentially never
miss. (An earlier reading of this as a 51% *miss* rate was wrong: it is a 51%
*fire* rate.) Independently on esc 20v20, measured at windup start, 4.0% of
launches begin with an enemy inside 1.0 against 18.2% of the alive population,
launch p10 = 1.43; the arbalester column (min_range 0.0) is the control and its
launch distribution equals its population distribution at every cutoff.

Implemented directly, this lands the camel fight's winner — camels win **25/25**
— but overshoots the margin (+75.8 vs +39.8) and costs
`eliteskirm_vs_champion_kiting` its convergence (2.54 → **13.50**). The reason
is geometric: our block packs tighter than the tape's (nearest-neighbour p50
0.28 against the tape's 0.37), so a single chaser suppresses more of our
shooters than it does in the game. The suppression rule is right; it cannot land
until the formation's slot geometry matches. That is the next step, and it is a
measurement, not a tuning knob: the tape's settled block is 2.01 × 2.23 tiles
for 21 units with nearest-neighbour spacing p50 0.371.

## Reproducing

Scratchpad tools: `camel_flow_measure.py`, `camel_pack_measure.py`,
`tape_jam_probe.py`, `tape_jam_control.py` (tape side); `camel_jam_probe.mjs`,
`camel_sim_flow.mjs`, `camel_weave_profile.mjs`, `camel_delivery.mjs` (sim
side); `post_shot_freeze.py`, `shot_budget.py`, `minrange_suppression.py`,
`arrow_hit_box.py`, `arrow_hit_box_esc.py` (the rules above).

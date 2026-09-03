# Following the camel fix plan: four candidate rules, none landable

`CAMEL_CHASER_GEOMETRY_2026-08-06.md` set out four steps — fix chaser mobility,
re-measure engulfment, then land min-range shooter suppression, then re-verify
the corpus. All four were run.

**Outcome: the engine default is unchanged.** Every candidate is behind an
`AOE2X_EXP_*` flag that defaults OFF; tests stay at 131/157 and the 14
non-kiting matchups are bit-identical. Two rules move the camel fight onto the
tape and both cost more elsewhere than they are worth; one is measurably right
about the physics and still makes the matchup worse; one does nothing.

## Scoreboard

Skirm-vs-camel, 25 sampled acquisition orders (tape: camels win, **+39.8**):

| config | camels win | mean | resolved |
|---|---:|---:|---:|
| HEAD | 10/25 | −9.4 | 25/25 |
| `AVOID=all` | 11/25 | +1.1 | 25/25 |
| `STEP=bimodal` | 8/25 | −19.2 | 25/25 |
| `AVOID=all STEP=bimodal` | 20/25 | +15.1 | 25/25 |
| `STEP=steer` | 1/25 | −43.6 | 25/25 |
| `MINRANGE=shooter` | 25/25 | +73.0 | 25/25 |
| `MINRANGE=shooter STEP=steer` | 8/10 | +38.3 | **10/25** |
| `KITE_ENGAGE=blocker` | 25/25 | **+41.5** | 25/25 |
| `KITE_ENGAGE=blocker` (enemy-caused only) | 25/25 | **+34.9** | 25/25 |

Corpus, 27 matchups × 25 orders, summed mean band error (lower is better):

| config | summed error | wrong winners |
|---|---:|---:|
| HEAD | **57.92** | 1 |
| `KITE_ENGAGE=blocker` | 183.12 | 3 |
| `MINRANGE=shooter` (4 skirmisher columns only) | 5.20 → 16.56 | 0 |

## Step 1 — chaser mobility: right about the physics, wrong about the fight

Two defects were implemented against the measured bimodality (tape camel speed
46.1% stopped / 0.6% partial / 52.9% full):

* `AOE2X_EXP_AVOID=all` — local avoidance considered **only allies** as
  obstacles (`constraintsFor` filtered on `unit.owner === mover.owner`), so a
  chaser never routed around the formation standing between it and its target.
* `AOE2X_EXP_STEP=bimodal|steer` — a step the solver had to shorten becomes no
  step (`bimodal`), or the unit first looks for a clear full-speed heading
  nearby (`steer`). The cancellation has to be iterated rather than applied
  afterwards: the solve is simultaneous, so a neighbour may already have moved
  into the space the cancelled unit was going to vacate. Cancelled units are fed
  back as stationary and the tick is re-solved until the set stops growing.

`steer` does what it was built to do — the partial-speed band drops 21.8% →
**0.3%** against the tape's 0.6%, and the kite block's own flow improves (duty
cycle 0.63 → 0.71 against the tape's 0.79, settled frames 21% → 16% against 6%).
It still makes the matchup worse, because a block that flows better also escapes
better: svcam falls to 1/25, and with suppression on top 15 of 25 runs never
resolve. `bimodal` alone is worse — it strands the formation the moment a chaser
stands in its lane (duty 0.18).

Engulfment barely moves either way: shooters covered per chaser 3.22 → 3.05,
against the tape's 0.69.

## Step 2 — engulfment: the chaser walks in, and stopping it is not free

Instrumented at the moment each chaser first has ≥3 shooters inside 1.0 tile:
over the preceding 2 s the **chaser** moved 2.43 tiles and the block's centroid
1.01, closing 2.46 tiles on the centroid, and the chaser out-moved the block in
95% of cases. Nothing is swallowing it — it drives in, because the kited-world
discipline has it engage only its sticky pursuit target and walk past every
shooter it touches on the way.

`AOE2X_EXP_KITE_ENGAGE=blocker` makes a blocked chaser engage what is stopping
it. On svcam it looks excellent, and not only on the outcome — the **victim
rank**, where the victim sits in the attacker's own nearest-shooter ordering,
moves onto the tape:

| | tape | sim HEAD | sim `blocker` |
|---|---:|---:|---:|
| svcam, victim is the attacker's nearest (r1) | **71%** | 31% | **70%** |
| r2 | 27% | 20% | 13% |

Engulfment halves (covered shooters 3.22 → 1.83, exposure 60.3% → 41.5%, chaser
gap p50 0.58 → 0.85), and the margin lands at +41.5 against the tape's +39.8.

**And it destroys the corpus**: 57.92 → 183.12 with 3 wrong winners.
`arbalester_vs_champion_kiting` goes 1.90 → **54.22** — its 20v20 median flips
from −87.5 to +27.1, i.e. the champions now win a fight the tape has the
arbalesters winning with 92% of their pool. Narrowing the trigger to blocks
*caused by an enemy body* (stamping the blocking enemy during movement, so an
ally queue no longer counts) keeps svcam at +34.9 but only takes kac to 46.40.

That is decisive against the rule, not against the measurement: the kac archive
resolves this behaviour with far more evidence (64% of sustained adjacency
windows produce no swing) than the 41 attributable svcam hits do. The tape's r1
dominance is better explained by chasers *pursuing* their nearest than by
converting on contact.

## Step 3 — min-range suppression: still not landable

Alone it makes the camel side exactly right — kiters take 8.48 hp/s against the
tape's 8.36, the fight lasts 88.5 s against 87.9 — while cutting skirmisher
output to 3.38 against 7.67, a +73.0 overshoot. Across the four Elite Skirmisher
kiting columns (the only kiters with a nonzero `min_range`) the summed mean band
error goes **5.20 → 16.56**, `eliteskirm_vs_champion_kiting` 3.96 → 12.84. Its
cost still scales with an exposure that is 41–67% where the tape is 22.9%.

## Refuted along the way

Kiters do **not** back off when a chaser enters their minimum range. Away-from-
chaser alignment for moving shooters is *lower* inside 1.0 (mean cos +0.463)
than in the 1.0–2.0 control (+0.688), and the min_range-0 arbalester column
behaves identically (+0.453 vs +0.603). The block simply runs; it does not
react to the pin.

## Where this leaves the camel fight

The chain is measured and unbroken — chasers wade into the formation, take and
deal point-blank damage they should not, and every rule that stops them either
overshoots or breaks a column that the tapes resolve better. What has not been
tried is the formation's own cohesion: the tape's block holds **1.63 × 1.71**
tiles for ~15 units where ours spreads to **2.43 × 1.98**, and the holes in a
block that never finishes forming are what a chaser walks into. That is a
measurement about slot occupancy over the beat cycle, not a new behaviour rule,
and it is the next thing to look at.

## Reproducing

```
AOE2X_EXP_ENGAGEMENT=pursuit AOE2X_EXP_ORDERS=1 [flags] node run_matchup_circuit.mjs 25
```

Scratchpad probes: `svcam_probe.mjs` (every metric with a tape counterpart in
one run), `blocker_victim_rank.py` / `sim_victim_rank.mjs`, `engulf_entry.mjs`,
`contact_cycle.py` / `sim_contact_cycle.mjs`, `kite_retreat_test.py`,
`pack_vs_suppress.py`, `block_shape.py`, `damage_curve.py`.
Circuit outputs: `base_circuit.json`, `blocker_circuit.json`, `mr_circuit.json`.

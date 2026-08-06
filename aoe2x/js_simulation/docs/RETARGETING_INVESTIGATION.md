# Retargeting — every approach tried

> ## RESOLVED: it is not unit AI. The AI player is issuing orders.
>
> The recordings carry a command stream the decoded `*.commands.jsonl` reduces
> to `{t, kind}`, throwing away everything useful. Read from the raw
> `.frames.bin` instead, each `aiOrder` is a full `Command.AiOrder`:
>
> ```json
> {"t": 2706, "playerId": 2, "recipient": 1743, "orderType": 700,
>  "priority": 100, "targetOwner": 3, "immediate": true,
>  "unitIds": [1743, 1742, 1741, 1740], "loc": [4.5, 7.64]}
> ```
>
> Both players' AIs issue `orderType 700` attack orders to small groups of their
> own units, repeatedly, all through the fight — 24-32 orders in a 40-unit
> fight, 1 in an 8-unit fight.
>
> | test | result |
> |---|---|
> | voluntary switches within 50 ms of ANY aiOrder | **66.9%** vs a 3.1% control — **21.6x** |
> | units NAMED in an order that switch within 60 ms | **81.0%** vs 3.8% for every other live unit — **21.2x** |
>
> So the target changes we have been trying to explain are **commanded**, not
> emergent. That is why every unit-level rule failed: nearest, path, detour,
> crowding, focus-fire, retaliation, load balancing, ally copying, scan order,
> stale snapshots and every distance metric. There was no unit-level rule to
> find, and the density scaling (+0.83 with unit count) is just the AI issuing
> more orders when it commands more units.
>
> **Consequence for calibration.** These tapes are AI-micromanaged fights. Our
> clean-room engine models units auto-engaging with no commander, so it can
> never reproduce this movement without replicating an AI ordering policy — which
> is scripted behaviour, not engine physics. Section 4's finding stands
> independently (engagement pinning is a real defect), but "our units never
> voluntarily retarget" is now the wrong framing: the game's units may not
> voluntarily retarget much either.
>
> Decision (2026-08-05, with the user): every non-human player always has an AI
> issuing these orders, so the order layer is part of the game being modelled.
> The sim gets one.
>
> Tools: `tools/read_ai_orders.py`, `tools/measure_order_match.py`.

---

## 6. The order policy, reverse-engineered

All 859 orders across the 92-fight set. Uniform envelope: `orderType 700`,
`priority 100`, `issuer 0`, `immediate true`, `range 0`, `targetOwner` = the
opponent; both players symmetric (431 vs 428).

**What an order IS.** `loc` sits exactly on a live enemy unit's position in
99% of orders (median miss 0.004 tiles): each order designates a SPECIFIC
enemy. It is not a generic attack-move: the named units' next combat target is
the enemy AT loc in **99%** of cases and the enemy nearest themselves in only
6%. Application is instant — median 0.00 s from order to target switch, and
81% of named units switch within 60 ms (vs 3.8% of unnamed units, 21x).

**Order shapes.** 611 single-unit orders (`recipient` only, empty `unitIds`)
and 248 group orders (2-4 units, `recipient` = first of `unitIds`). A group
order designates ONE enemy for the whole group — this is the concentration
mechanism: the 8v4 repeats the paladins won by 19-26% are exactly the ones
where pairs were group-ordered onto single champions.

**Opening sweep.** First order at median 2.72 s (range 2.51-3.14). Each AI
walks its OWN units in descending reference-id order, groups of 2-4 first
(group size loosely scaling with roster), then singles; median inter-order gap
0.20 s (p25 0.07, p75 0.60), widening as the sweep proceeds. Median coverage
60% of the roster. Recipients are strongly biased toward units NOT already
fighting: 13% of recipients were in attack state at the order vs 35% of other
own units. Each sweep order designates a DISTINCT enemy (median distinct
fraction 1.00; only 4.8% repeats) — the sweep SPREADS the army across the
enemy roster. The exact designation rule is imperfectly resolved: nearest
not-yet-assigned enemy explains 28.8% at rank 1 (vs 18.1% unconditioned), best
evaluated with sweep-start positions (rank<=2: 54.7%).

**Mid-fight orders (t >= 8 s).** Sporadic singles, sometimes short descending
re-sweeps. The trigger is REPAIR: recipients spent 26.7% of the preceding
second idle vs 7.1% for other live allies (~4x). The rare kill-triggered ones
arrive median 0.41 s after the target died.

**Why the unit-level search failed, retrospectively.** The unit AI really is
lock-until-death — our engine's pursuit lock is CORRECT. Initial acquisition
(0.952-1.708 s, unit-level) happens before the first order at ~2.7 s; every
"voluntary" switch after that is the AI player. The density scaling was the
AI's order rate, the "distinct targets" spreading was the sweep, the
concentration was group orders, and the idle-rescue explains why unpinning
engagement (E2) stranded units the game does not strand.

## 7. Sim implementation plan

Layer an AI-player order issuer over the engine, gated by the experiment
harness until validated:

1. **t ≈ 2.7 s: opening sweep** per side — own units descending by reference
   id, skipping units already engaged; groups first (2-4 adjacent ids), then
   singles; one order per ~0.2 s; each order designates a distinct enemy
   (greedy nearest-unassigned at sweep start); effect = set pursuit target
   immediately.
2. **Mid-fight: idle rescue** — a unit idle (no engagement, no progress) for
   ~1 s becomes eligible; orders re-designate it to a live enemy.
3. Combine with experiment E2 (engagement follows pursuit), which is what
   makes an ordered unit actually walk to its designated target through a
   crowd.

Implemented in `src/combat/ai-orders.js`, enabled with
`AOE2X_EXP_ENGAGEMENT=pursuit AOE2X_EXP_ORDERS=1`; baseline is untouched
(suite 112/27, 6v3 still 112 HP). Two refinements over the plan, both
measured: designation is computed against positions frozen at sweep START
(rank<=2 54.7% vs 41.9% at order time � the AI plans once while the world
moves), and mid-fight rescue is rate-limited to one order per side per 1.2 s
(the tape's re-order cadence; without it every idle unit recycles into an
attacker within a second and the attacking share overshoots again).

## 8. First results of the order layer (vs tape medians, sampled orders)

Mean |median error| over all 26 ratios: **4.34 -> 3.94 pts**. 13 ratios
improved, 6 worsened, 7 already exact stayed exact. Notable:

| ratio | baseline | with orders | note |
|---|---|---|---|
| 3v2 | +3.6 | **0.0 � exact** | the deterministic one-swing bug, gone |
| 20v15 | -4.6 | **+0.3** | |
| 5v3 | -7.2 | -2.4 | |
| 11v4 | +5.5 | +3.6 | |
| 20v18 | -9.1 | -7.1 | |
| 9v4 | +13.3 | +11.1 | still the worst knife-edge miss |
| 21v10 | +9.3 | **+15.8** | main regression; runaway fights 11/40 -> 2/40 |
| 10v5 | -4.4 | -7.2 | regression |

Open: the 21v10/10v5 regressions, and the attacking-share residual (the tape
keeps ~45% of a big fight walking; the sim with orders reaches ~25%, because
greedy designation still picks nearer enemies than the tape's � rank 5+ in 47%
of real designations means much longer cross-melee walks).


Why this file exists: the remaining calibration error is concentrated in how
units change target mid-fight, and the search has been long enough that the
dead ends are worth as much as the leads. Everything below is measured, with
the number that killed it. Nothing here is fitted.

Data: **122 recorded fights** — `championvschampion` (15), `paladinvspaladin`
(15) and the 92-fight `championvspaladin` set (26 ratios, 2 to 40 units).
**1485 voluntary target switches**, where "voluntary" means the abandoned
target was still alive.

Tools: `tools/measure_retarget_*.py`, `tools/measure_time_budget.py`.

---

## 1. What is established

| fact | evidence |
|---|---|
| The game switches target while the old target lives | 31-44% of all switches; ours 0-9% |
| Our units re-evaluate only on a kill | `selectPursuitTarget` returns a locked `pursuitTargetId`; `world.js` skips reselection entirely |
| The game's units spend 40-46% of a fight moving; ours 14-24% | time budget over each unit's own lifetime, every large ratio |
| That converts ~1:1 into attacking time | our losers deal 28-46% more damage per second alive while living 5-40% LESS |
| Retargeting is DENSITY-driven | per-fight correlation with unit count **+0.83**; 2-4 unit fights retarget **zero** times |
| Re-evaluation is continuous, not periodic | hold-time smooth and unimodal at 1.25-1.50 s; Rayleigh sweep 0.2-4.0 s finds only the trivial monotonic artifact |
| Units are NOT stuck when they switch | 96.8% of max move speed, versus a 98.7% baseline moving frame |
| Switches cluster at two moments | 54% mid-approach having never reached the target; 46% a median **0.02 s** after a swing lands |

All of it replicates in both mirror archives, so none of it is an artifact of
the asymmetric matchup.

---

## 2. Choice rules tested and REJECTED

Each was scored as "how often does this rule name the target the unit actually
picked", against 1453-1485 switches.

| # | rule | result | verdict |
|---|---|---|---|
| 1 | nearest enemy, Euclidean | 33.0% | best single rule, still explains a third |
| 2 | nearest by **path** (grid A* around every body) | 45% closer by path vs 40% by line | no real lift |
| 3 | old target became unreachable | 6% | dead |
| 4 | path-detour threshold | detour old **1.19** vs new **1.19** | identical — dead |
| 5 | nearest with a free slot (K attackers in contact, K=1..5) | flat **33%** at every K | dead |
| 6 | focus the wounded | median target-HP change **0** | dead |
| 7 | retaliation (new target is attacking me) | 14% vs a **12%** control | dead |
| 8 | copy a nearby ally's target | **0.98x** chance | dead |
| 9 | least-targeted enemy (load balancing) | **0.77x** — ANTI-correlated | dead, and informative |
| 10 | least-targeted, tie-broken by nearest | 2.30x lift, but no better than nearest alone | dead |
| 11 | fixed re-evaluation timer | no periodicity; zero switches in small fights | dead |
| 12 | stale snapshot / round-robin scan | hit rate **peaks at lag 0** (32.9%) and decays to 9.1% at 3 s | dead |
| 13 | cheaper distance metric | Chebyshev 34.9%, Euclid 33.0%, octile 32.8%, Manhattan 31.5%, single-axis ~20% | no metric wins |

Rule 9 is worth keeping in mind: units actively AVOID the least-targeted enemy,
which rules out any "spread the damage" model and is consistent with units
converging on whatever the crowd is already fighting.

---

## 3. Choice signals that SURVIVED

The first non-null results. Both geometric, neither a distance rule.

**Axis anisotropy**, with the candidate pool restricted to enemies within ±25%
of the chosen target's distance, so it is not a distance artifact:

| E | NE | N | NW | W | SW | S | SE |
|---|---|---|---|---|---|---|---|
| 1.41 | 0.86 | 0.77 | 1.22 | **1.52** | 0.84 | **0.43** | 0.97 |

**Heading preference** — monotonic across four bins, angle between the unit's
current velocity and the direction to the chosen target:

| ahead 0-45° | 45-90° | 90-135° | behind 135-180° |
|---|---|---|---|
| 1.15 | 1.01 | 0.83 | **0.63** |

Units prefer targets ahead of their motion and are reluctant to turn around.

---

## 4. Engine experiments

Run against the engine, not the tape. All reverted; each is listed with what it
proved.

### E1 — remove the pursuit lock (re-evaluate nearest every tick)

No new constants. Halved the 10v10 attacking-share error (+25.5 → +11.6 pt) but
left big fights near 22% moving against the tape's 46%. Outcome deltas a wash:
four ratios better, four worse.

**Proved:** re-evaluation frequency alone is not the gap. In a packed melee the
nearest enemy rarely changes, so units stay glued.

### E2 — unpin engagement (engagement FOLLOWS pursuit)

A unit engages the target it is pursuing and nothing else, instead of being
captured by the first body it brushes past. Necessary because `moveUnits`
refuses to move any unit whose action is `attacking`.

| ratio | attacking share Δ | damage/sec alive (tape → sim) |
|---|---|---|
| 20v18 | +15.0 → **-1.3 pt** | 2.84 → **2.76** |
| 20v15 | +15.1 → **-0.5 pt** | 2.88 → **2.85** |
| 20v20 | +10.9 → **-1.1 pt** | 2.97 → **2.89** |

Outcome deltas improved sharply on the big near-even fights: 20v18 -9.1 → -1.9,
8v4 -8.6 → -0.8, 15v10 -10.4 → -5.7.

**But** the freed time became **idle** (+11.8 to +20.1 pt), not moving, and it
broke the locked champion-mirror gates (5v3 and 6v3 medians; 112 → 109 pass).

**Proved:** the throughput half of the model is correct. Damage per second alive
is nearly exact once units stop being captured. What remains is that the idle
population — units pressed against the crowd, pursuing something they cannot
reach — is exactly who the game retargets.

---

## 5. Why combinations are the next step

E1 and E2 were each tested ALONE, and each fixes half a mechanism:

* E2 stops units grinding on whatever they bump into, but strands them idle.
* E1 gives them a fresh target, but on its own they were never stranded, so it
  had nothing to fix.

Together, E2 creates the stranded population and E1 (or a blocked-triggered
reselect) gives it somewhere to go. Neither alone can show that.

The parameter-free trigger already exists in the engine: `moveUnits` emits a
`blocked` event whenever a unit's actual movement differs from its proposal.
That is a physics condition, not a constant — no fitting.

Matrix to run:

| id | engagement | pursuit re-evaluation |
|---|---|---|
| base | free-floating | locked until death |
| E1 | free-floating | every tick |
| E2 | follows pursuit | locked until death |
| **E3** | follows pursuit | every tick |
| **E4** | follows pursuit | on `blocked` only |
| **E5** | follows pursuit | on `blocked` or on swing completion |

E5 is motivated by the tape's two switch moments: mid-approach (blocked) and a
median 0.02 s after a swing lands.

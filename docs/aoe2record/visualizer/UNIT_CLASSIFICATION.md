# Unit-type classification from `.aoe2record` — design & learnings

How we recover each unit's **exact type** (skirmisher vs. spearman vs. villager…) from a
`.aoe2record` replay **alone**. A gRPC engine capture is used only as ground truth for
validation; the production path never sees it.

This document records both the algorithm we shipped and the **hard-won negative results** —
the approaches that look promising but don't work, and *why* — so they aren't re-tried.

---

## 1. The core idea: the production order is the spine

The `.aoe2record` command log does **not** label units with their types. But it does record
every **production command** (`DE_QUEUE`), every **building**, and every unit's **instance_id**
when it's first commanded. The strategy:

1. **Reconstruct the exact sequence of units produced** (with types, from `DE_QUEUE`), per
   building, merged by spawn time. This is the "creation order."
2. **Map each commanded unit to a slot** in that sequence. The unit's type is the slot's type.

Everything below is about doing step 1 accurately (we got it to **~100%**) and step 2
robustly (the genuinely hard part).

### Why instance_id order is the authoritative spine
- **`instance_id` is a global spawn counter.** Proven: sorting any player's real units by
  `instance_id` reproduces their exact `created_ms` spawn order with **zero inversions**.
- So the commanded units' ids give their **exact relative production order for free**. The
  binding (step 2) is a *monotonic* assignment: `id(A) < id(B) ⇒ slot(A) ≤ slot(B)`.
- Command **time** is *not* a reliable order signal — a unit can spawn early and sit idle,
  commanded minutes later ("held" units). Always order by id, not by first-command time.

### …but you cannot predict the absolute instance_id
The id counter is **perfectly contiguous** (every integer used, no gaps), but it counts
*everything*: in a 1v1 game-2 sample, of 3525 consecutive ids only **~12% are real units**
(model-type 12); **~15% are buildings** (mt14, incl. farms & walls); and **~72% are transient
combat effects** (mt9). Those effects (explosions, projectile impacts, corpses) spawn at
combat-driven times we can't predict, so the id-gap between two real units swings from 1 to
150+. **You can recover the order of units; you cannot assign their absolute ids.** Any design
that tries to predict ids is doomed — use order only.

> The dataset mislabels effect master-id **112 as "Flare."** It is actually
> *Explosion (Demolition/Petard) / enemy missile object* (genie ids 111–116 are
> bodies/explosions). It lives a fixed ~7s and is weighted toward the *aggressor*. It is the
> single largest consumer of instance_ids.

### Engine model types (gRPC stream)
| mt | meaning |
|----|---------|
| 9 | gaia + transient effects/projectiles/corpses + map objects (trees, mines) |
| 10 | DoppleEntity — fog-of-war shadow copies (exclude; we capture fog-off) |
| 11, 13 | rare entity variants |
| **12** | **mobile units** — villagers + military (the things we classify) |
| **14** | **buildings** (incl. farms, walls, drop-sites) |

---

## 2. Reconstructing the production order (the FIFO model)

Per building, production is **serial (FIFO)**: `completion = max(queue_time, prev_done) +
train_time`. Layered on top:

- **Multiqueue.** A `DE_QUEUE`'s `object_ids` is the *full set* of selected production
  buildings (byte-for-byte identical to the gRPC `MultiQueue.buildingIds`). The game
  load-balances each unit to the building that frees up soonest — simulate this, do **not**
  dump everything on `object_ids[0]`.
- **Unqueue.** A cancelled unit never spawns. Players cancel from the **back** of the queue,
  so a `LIFO` cancel of the newest pending unit matches the gRPC spawns far better than
  honouring the raw slot index (`+7 pts` on ddk220 alone).
- **Resign cutoff.** A resigning player stops producing; anything still queued never spawns.
- **Tech research occupies the queue.** A tech researched *at a production building*
  (e.g. Light Cavalry at the Stable) blocks that building's unit queue for the research
  duration. We confirmed this causes a real residual (Armenian scout drift) but did **not**
  ship it — research times live in the genie `.dat`, not the reference DB. *Open item.*

### Train times — the calibration that mattered most
This is where most of the accuracy came from. Three bugs, all found by comparing modeled
completion times to the gRPC spawn gaps:

1. **Civ creation-speed bonuses are passive and not in the DB.** Aztec "military created 11%
   faster" must be applied as a `×0.89` multiplier on top of the base train time. The DB's
   `final_train_time` only reflects *tech* upgrades, not this passive bonus.
2. **The bonus applies per building-line, not uniformly.** Calibrated from spawn gaps:
   Barracks / Archery / Stable / **Siege Workshop** *are* sped up; the **Monastery is not**
   (monks spawn exactly 51s apart = base). Bonusing monks/siege wrongly drifts the order.
3. **Unlisted units defaulted to a generic 30s.** Pull base train times from the DB for
   *every* unit (Composite Bowman/Jaguar = 12s — confirmed by 12.0s spawn gaps; Eagle Scout
   = 35s — its single-building gap is ~30s = 35×0.89).

Then **quantize to the 20-tick/second game clock** and break same-tick ties by **building id**
(the engine processes buildings in id order within a tick).

**Result:** military creation order reached **100%** (ddk220/Aztecs) and **97.7%**
(Armenian); the single remaining miss is a tech-blocked stable (item above). The order model
is essentially exact — spawn-time error is **0–2s median**.

### How to recover correct train times for a new patch/civ
Derive empirically from a gRPC capture: for a unit produced steadily from one building, the
recurring inter-spawn gap **is** its effective (civ-adjusted) train time. We did exactly this
to fix Eagle Scout (60→35) and confirm the per-line bonus rule.

---

## 3. Class resolution (villager vs. military)

Once a unit's **class** is known, typing is easy: villagers → `villager`; military units bind
to military slots by order (below). So class is the crux.

**Signal reliability hierarchy** (this is where the infamous "slinger bug" lives):
- **Rock-solid villager:** `BUILD` / `REPAIR` / `WALL`. Military physically cannot.
- **Rock-solid military:** `PATROL` / `STANCE` / `FORMATION` / `ATTACK_GROUND` / attack-move /
  `GUARD`. Villagers cannot.
- **NOT reliable — `gather`.** A military unit co-selected with villagers and right-clicked
  onto a resource picks up a **phantom gather it cannot perform**. Treating gather as a hard
  villager signal demotes real slingers/scouts to villager. *Only* sustained gathering (many
  gathers, no military actions) is a villager signal.
- **NOT reliable — a single attack.** Villagers attack too (defending, force-attack).

**The building-derived class fix:** a unit produced from a military building (archery range,
stable, …) *is* military, even with a phantom gather. This — not behaviour alone — is what
fixed the slinger/scout misclassification.

**Co-command** propagates class along units commanded together, and a **squad-smoothing** pass
(snap a squad whose assigned types are ≥60% one type) corrects held units. Threshold **0.6 is
optimal across all games** — raising or removing it only hurts (munq 93→78%). Co-command
votes on **class**, never directly on exact type (a mixed army moves together; letting the
dominant type vote swallows minorities).

---

## 4. The binding (command → production slot)

- Sort commanded units by `instance_id`. Bind **monotonically** to slots.
- **Per-line claiming**, smallest line first (Monk 2 slots claims before the dominant Archery
  line can absorb its units), with strict command-lag matching so the exact-spawn owner wins a
  slot. Then **earliest-pack** within a line for held units (a unit commanded long after it
  spawned takes its *earliest* valid slot, not a nearer late one).
- **Decomposition:** because id-order = spawn-order, you can bind each class independently —
  villagers are all type `villager` regardless of slot, so only **military** units need the
  order-preserving match/skip alignment to get their exact type.

---

## 5. The ambiguity floor — what's actually achievable

Categorizing every commanded unit (game 2):

| Category | share | reliability |
|---|---|---|
| **A** hard signal (build/wall or military command) | 62–65% | ~100% |
| **B** co-command resolved (≥5 confident neighbours, one class) | ~8% | ~98% |
| **C** spine-forced (slot-window between confident anchors is class-homogeneous) | 2–19% | ~95% |
| **D** true guess (signal-less, no consensus, class-straddling window) | 12–24% | coin-flip |

The **D** floor skews **military for the aggressor** (heuristic-exploitable) but is a dead
**50/50 for the passive player** (signal-less units in mixed slot-windows — genuinely
information-less in the record).

**Crucial correction:** D is *not* fully irreducible. The shipped classifier hits **~96%
class** — well above the A+B+C ceiling — because it uses **production-fit** ("this unit was
first commanded right after a *military* slot spawned and slots cleanly into the military
FIFO ⇒ military"). Production-fit resolves most of D. **This is the key to why the joint
classifier beats any class-first scheme.**

---

## 6. Dead ends (do not re-try)

- **A standalone "spine" classifier that resolves class first, then types** underperforms the
  joint classifier badly (class 87% vs **96%**; military type 32–62% vs **70–93%**). Reason:
  **production-fit is the strongest class signal, and you destroy it by committing class
  first.** Resolve class and type *jointly* through the production binding.
- **Tuning the co-command thresholds (x/y) does not help.** Swept across games: 0.6 smoothing
  is optimal; nothing moves the residual. The residual is in the *binding*, not co-command.
- **Window-forcing and co-attack grafts fix 0 of the actual errors.** The remaining class
  errors are signal-less early units *not* in homogeneous windows; window-forcing on the
  gather-units would *confirm the wrong villager class*.
- **Rebinding leftover (unclaimed) units to unclaimed slots didn't help** — the swallowed
  minorities are *claimed by the dominant line in Phase 1*, not leftover.

---

## 7. The genuine residual (information limit, not a bug)

The remaining ~15–20% on a hard player is two things, both irreducible from the record:

1. **A small signal-less floor** (~2–4 units): early scouts/monks that only ever MOVE, in
   class-straddling id-windows. The record contains nothing to disambiguate them.
2. **Gather-contaminated / held minorities swallowed by the dominant line** (~6–18 units).
   Mechanism: a minority unit (spearman, siege, monk, militia) with a *phantom gather* has no
   hard signal, so it's *soft*; in per-line claiming its lag to its own line's slots exceeds
   the skip cost, so it's skipped, and the dominant Archery line — with slots near the unit's
   *late* command — claims it. The line determines the type, but the unit is **time-ambiguous**
   between its own line's early slot and the dominant line's late slot, and **no signal in the
   record breaks the tie**. Same-building concurrent units (slinger vs. skirmisher from one
   archery range) are likewise irreducible.

The strong conclusion: for a player producing a **mixed army from multiple buildings
concurrently**, exact per-unit typing has an information ceiling well below 100% — that's the
data, not the algorithm. Players who commit to one or two unit lines should classify in the
high 90s.

---

## 8. Validation methodology & tooling

- **Ground truth:** gRPC engine capture with **fog OFF + perspective = ALL players**
  (`SetFogOfWar(false)`, `SetPerspective(0)`) — without these you only get player-1's units
  and fog-shadow doppels. `record_games.py` is the armed recorder (one file per game; the
  critical bug was passing a `~1e12s` deadline to the `Frames` stream, which fails instantly —
  use `timeout=None`).
- **Label extraction:** `extract_labels.py <capture.bin> <out.json>` decodes the frame stream
  to `{instance_id: {type, owner, created_ms, died_ms}}`. The gRPC `entity_id` == the mgz
  `instance_id`, so labels join directly to the classifier output. **Zero id-link failures
  confirmed.**
- **Dataset caveat:** the bundled `aocref` dataset (DE v33315) is **stale** — newer DLC units
  (and many `id####` effect objects) aren't named. A current id→name map can be rebuilt from
  the game's `CivTechTrees/*.json`. The eval canon (`eval_against_truth.py`) was extended for
  Composite Bowman / Jaguar Warrior / Scorpion / Warrior Priest so they score as themselves,
  not generic `unit`.
- **Analysis scripts** (in the `aoe2grpc` workspace): `compare_order.py` (creation-order
  accuracy), `order_misses.py` (exact mis-ordered units), `ambiguity_floor.py` (A/B/C/D split),
  `error_structure.py` (cross-line vs within-line), `smooth_sweep.py`.

---

## 9. Results (exact type, last 5 minutes ignored)

| game / player | overall | military |
|---|---|---|
| Original — munq/Bohemians | 95.9% | 93.2% |
| Original — ddk220/Incas | 83.4% | 70.8% |
| Game 2 — ddk220/Aztecs | 86% | 84% |
| Game 2 — wR.Baxter/Armenians | 87% | 73% |

**Creation-order** (the production model itself): ddk220/Aztecs **100%**, Armenian **97.7%**,
spawn-time error 0–2s.

---

## 10. Key files

- `visualizer/unit_classifier.py` — the classifier (the algorithm).
- `visualizer/train_times.json` — DB-sourced base train times (+ civ overrides). **Required**;
  without it the classifier falls back to approximate values.
- `visualizer/watch_replays.py` — folder watcher that auto-analyzes new `.aoe2record` files.

## 11. Open items / future work

1. **Tech-queue modeling** — research at a production building blocks its unit queue. Needs
   research times from the genie `.dat` (extract once, cache). Would close the Armenian
   scout-drift residual.
2. **Record cleaner games** (a 1v1 where a player commits to one/two lines) to confirm the
   classifier reaches the high 90s — i.e. that we're at the *data's* ceiling, not the
   algorithm's.
3. **Per-civ train-time table** for all civs (currently only the civs encountered are
   calibrated) — regenerate from the DB + the empirical gap method.

# Unit Classifier & Simulation Rework

A ground-up rework of how the visualizer identifies unit types and drives
behavior-specific simulation (siege firing). Motivated by an extended forensic
investigation of AoE2:DE recorded games (see "Findings" below).

## Why

A recorded game is a **command log, not a state log**. Produced units' types are
never announced; only the ~24 starting units are named. The shipping classifier
(`server._classify_units`) guesses a produced unit's type with a greedy
production-time matcher, which is unreliable — e.g. it labels patrolling huszars
as "trebuchet", and the siege-firing animation (keyed off that label) then plays
on cavalry.

Key findings that drive this rework:

- **Co-command is a ~100% same-class signal.** Of 4,515 co-command edges (units
  commanded together) with both endpoints hard-labeled, **100.0% share a class**,
  zero mixed, even at edge weight ≥1. This is the strongest signal available.
- **Squads are behaviorally coherent.** Co-command clusters are uniformly
  patrol (cavalry), build/gather (villagers), or attack-building (siege).
- **`instance_id` is the global creation counter** (lower id = created earlier;
  Spearman 0.966 vs time within the clean band). Good creation-order proxy.
- **Train times matter.** Units complete at `max(queue_ts, prev_done)+train_time`
  per building, not instantly — a better creation-time model than queue time.
- **Refined behavioral rules.** Villagers also attack (enemy units, boar), so
  "attacks enemy/boar" is NOT a class signal. Only patrol/stance/formation/etc.
  are military-hard; only gather/build/repair/wall are villager-hard.
- **SPECIAL/UNGARRISON ids are shifted** (`id<<8`): ~619 phantom double-counts
  per game. Must be normalized (`id>>8`) and deduped.
- **Rare types (trebs) are NOT recoverable per-unit** — 9 trebs buried among
  ~335 huszars + ~189 cav-archers, no produced-id in the stream, SYNC obj_count
  too coarse to isolate single births. So the **siege animation must be driven
  by behavior, not by the type label.**

## Principles

1. **Group-first, not unit-first.** Co-command class propagation is the backbone.
2. **Every label carries confidence and is sticky.** A guess changes only when a
   *strictly higher*-confidence signal arrives; idle/"death" never resets it.
3. **Behavior drives simulation; labels drive icons.** Rare types are
   unrecoverable, so siege firing keys off behavior (stationary unit attacking a
   building), never the type string.
4. **Class is near-certain; type is inference.** Track them as separate
   confidences.

## Target architecture

Classification moves out of `server.py` into `visualizer/unit_classifier.py`
(standalone, takes a parsed mgz `match`, no Flask dependency). It emits a rich
per-unit record; `process_replay` keeps a flat `{id: type_string}` for backward
compatibility and adds the rich records + a precomputed `siege_episodes` list.

```python
@dataclass
class UnitGuess:
    instance_id: int
    player: str
    cls: str          # 'villager' | 'military' | 'unknown'
    cls_conf: float
    type: str         # 'magyarhuszar' | 'villager' | 'siege' | 'unit' ...
    type_conf: float
    squad_id: int | None
    role: str         # behavioral: 'eco' | 'cavalry' | 'ranged' | 'siege' ...
    signals: list[str]
    behavior: dict
```

### Pipeline

```
classify(match):
  ctx = build_context(match)     # Stage 0: owner, gaia split, behavior, id-normalize
  behavioral_labels(ctx)         # Stage 1: refined hard class (conf 0.95)
  g = cocommand_graph(ctx)       # Stage 2a: weighted co-command edges
  propagate_class(ctx, g)        # Stage 2b: 100%-reliable class fill (conf 0.90)
  prod = production_timeline(ctx)# Stage 3: per-building serial train-time completions
  squads = form_squads(ctx, g)   # Stage 4a: cluster the graph
  type_squads(ctx, squads, prod) # Stage 4b: one type per squad (role+prod+id-range)
  type_remaining(ctx, prod)      # Stage 4c: id-rank fallback for ungrouped
  finalize(ctx)                  # Stage 5: monotonic, sticky, no generic-overwrite
```

**Confidence ladder:** header-known 0.99 > hard class 0.95 > co-command class
0.90 > coherent-squad type 0.80 > id-rank type 0.55 > fallback 0.30.

### Simulation rework (frontend)

Replace `playback.js`'s `SIEGE_SHOOTER_RE` name match with **behavior-driven
siege episodes** (precomputed server-side, passed as `siege_episodes`): a unit
that ORDER-attacks a building/static target then stays ~stationary → a firing
episode until its next move/death. `role == 'siege'` (or a siege type hint)
boosts but isn't required. Icons still use the `type` label; only the animation
is behavior-gated. The 3-minute "death" stays render-only fade; `type` is
computed once and never reset.

## Delivery phases (each behind a `classifier_v2` flag, with side-by-side metrics)

| Phase | Scope | Gate |
|---|---|---|
| 0 | Extract module; ID normalization; eval harness | phantom dupes gone; baseline reproduced |
| 1 | Refined behavioral class rules | boar/enemy-attacking villagers stay villager |
| 2 | Co-command class propagation | class coverage ↑; 100% pair consistency; villager total ≈ DE_QUEUE |
| 3 | Production timeline + train times | unknowns ↓; per-type counts track production |
| 4 | Squad formation + squad typing + finalize | squad purity ↑; no generic-overwrite |
| 5 | Behavior-driven siege episodes (FE) | siege fires on stationary building-attackers, not cavalry |
| 6 | Wire into process_replay; JSON contract; remove old path | end-to-end on ≥10 replays; perf within budget |

## Validation

- **Held-out behavioral accuracy**: hide some hard labels, predict, score.
- **Production-consistency**: per-player typed counts vs DE_QUEUE multiset.
- **Co-command consistency**: must stay ~100%.
- **Multi-replay generalization**: the last ~10 matches from the Browse Matches
  list, preferring games with **ddk220** as a player. Required before Phase 6
  removes the old path.
- **Performance budget**: graph + clustering well under parse time on large games.
- **Visual smoke test**: siege animation via the preview harness.

## Risks & mitigations

- **Overfit to one replay** → multi-replay gate before Phase 6.
- **Train times vary by civ/bonus** → base values + tolerant windows; never
  hard-match exact time.
- **Squad-assignment cost/perf** → thresholded union-find + greedy assignment.
- **Rare types stay uncertain** → confidence reflects it; animation is
  behavior-driven so rendering is unaffected.
- **Backward compat** → keep flat type strings; additive JSON; `v2` flag with
  instant rollback to `server._classify_units`.

## Status

- **Phases 0–4 implemented + wired** (`unit_classifier.py`, `server.py`). Typing
  is now **group-first**: `assign_types` types each co-command blob as one unit
  from the production stream with a fill-ratio quota (homogeneous groups + honest
  proportions). Edge fixes landed: **C1** phantom dedup (canonical `unit_name_map`
  key; 4783→4147 units), **C2** source-aware id normalization (SPECIAL/UNGARRISON,
  not a magnitude threshold), **M3** class-aware fallback, partial **M2** unique
  train times.
- **Gate results (481391706):** G1 every stage active · G2 heterogeneity 68%→**3%**
  · G3 huszar/villager/CA track production (~76–89%) · G4 hard-class purity 97.5%
  · G5 phantoms collapsed. Run `python eval_classifier.py <replay> [player]`.
- **Known gaps:** rare types (trebuchet/trade cart) still under-detected — needs
  role-based detection; **Phase 5** behavior-driven siege rendering not started;
  **Phase 6** multi-replay validation + legacy-path removal pending.

## Decisions (locked)

- Sequence: **foundation-first**, phases 0→6 in order.
- This design doc lives in the repo and is updated as phases land.
- Multi-replay validation: last ~10 Browse-Matches games, preferring ddk220.

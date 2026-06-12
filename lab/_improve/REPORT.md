# Unit Classifier Improvement — Final Report

Date: 2026-06-10
Final classifier: `C:\dev\aoe2\aoe2record\lab\_improve\final\unit_classifier.py`
(API preserved: `tm, _ = unit_classifier.build_type_map(mt)`; only file read at
classify time is `train_times.json` beside the module, same as production.)

Scorer: `C:\dev\aoe2\aoe2record\lab\_improve\score_game.py` (patched copy of
`compare_game.py`) with `UC_DIR=C:\dev\aoe2\aoe2record\lab\_improve\final`.
Raw outputs: `final_g0.txt`, `final_train.txt`, `final_holdout.txt` in `_improve`.

## Baseline vs final

| game | metric | baseline | final | delta |
|---|---|---|---|---|
| g0 (dev) | coverage | 93.5 | 93.5 | 0.0 |
| g0 (dev) | overall vil+mil | 88.9 | **92.2** | **+3.3** |
| g0 (dev) | military only | 80.9 | **84.7** | **+3.8** |
| train (tune) | coverage | 76.8 | 76.8 | 0.0 |
| train (tune) | overall vil+mil | 90.1 | **96.1** | **+6.0** |
| train (tune) | military only | 78.9 | **90.8** | **+11.9** |
| holdout (FINAL, scored once) | coverage | 79.8 | 79.8 | 0.0 |
| holdout | overall vil+mil | 99.5 | 99.5 | 0.0 |
| holdout | military only | 100.0 | **100.0** | 0.0 (at ceiling) |

Games: g0 = `fresh_newpatch.aoe2record` / `labels.json` / 42.6 min;
train = `AgeIIDE_Replay_482723861` / `labels_g2.json` / 44.5 min;
holdout = `AgeIIDE_Replay_482721813` / `labels_g1.json` / 15.8 min.

## What each angle tried (all 5 accepted by independent verification)

Ranked by holdout military (all tied at 100.0), tie-broken by train military:

| rank | angle | core technique | g0 mil | train mil | holdout (verified) |
|---|---|---|---|---|---|
| 1 | behavior-fingerprint | physical-ability pins (pack-treb, relic-monk), soft moves-only military + scout fingerprint, eco-exclusion, siege fence, atomic batch claiming of id-adjacent co-commanded units, lag-reliability claim order | 84.7 | 90.8 | 100.0 mil / 99.5 ov |
| 2 | id-spine-solver | per-player monotone id->slot DP hybrid merged with the local stack by confidence tier, plus behavioral arbitration overrides | 82.4 | 84.4 | 100.0 mil / 99.5 ov |
| 3 | ensemble-arbiter | per-stage decision instrumentation + gated post-hoc arbiters (villager abstain, conservative quota repair, reclaim), iso lag gate, per-unit DP skip costs | 82.4 | 82.6 | 100.0 mil / 98.9 ov |
| 4 | queue-ledger | discrete-event per-building production ledger; shipped subset = building-faithful line map + end-of-recording cutoff (faithful timing regresses the lag-tuned aligner) | 80.9 | 79.8 | 100.0 mil / 99.5 ov |
| 5 | civ-tech-prior | research-timeline pre-pass (TC blocks), co-production claim lines, availability veto | 81.7 | 78.9 | 100.0 mil / **100.0 ov** |

## What was merged into the final

Base = behavior-fingerprint's classifier, unchanged (best single angle by a wide
margin: train military 90.8 vs 84.4 for the runner-up). Grafts were selected on
g0+train only; holdout was scored exactly once, at the end, on the shipped file.

Merged and ON (flags at the top of the file):

1. **`FP_ARB_VIL` — villager abstain** (ensemble-arbiter): a unit typed military
   purely on time evidence whose behavior is eco-dominant (gathered/built >= 1,
   attacks <= gathers, moves <= 2, no hard-military signal, not pinned) is forced
   back to villager. **+3 g0 overall, +1 train overall, zero military change.**
2. **`FP_ARB_GARR` — garrison-villager override** (id-spine-solver): bld_order >= 2
   onto own buildings, zero gathers, moves <= 6, not monk/pinned -> villager (a
   tasked-to-garrison/deposit villager, not the type a FIFO snap claims; real monks
   move 70+). **+3 train overall, g0 neutral.**
3. **`FP_AVAIL_VETO` — availability veto** (civ-tech-prior): a predicted specific
   type the owning player never queued and didn't start with is impossible
   (cross-player leak); re-type from the unit's own class. Dev-neutral here, but
   verified in its own angle to fix the only holdout overall error (99.5 -> 100.0),
   and by construction it can never introduce a new specific-type error.
4. **`FP_LINE_REMAP` — building-faithful line map** (queue-ledger): composite
   bowman is an archery-range unit; trebuchet + all castle-only uniques share one
   castle queue, so they form one claiming line. Pure tech-tree fact; +0.9 train
   military in queue-ledger's own stack, dev-neutral inside this one.
5. **`FP_END_CUTOFF` — end-of-recording cutoff** (queue-ledger): production
   completing after the recorded duration never spawned (players spam-queue
   phantoms while losing). Dev-neutral, strictly more correct.

Tested on g0+train and rejected (left in the file, flag OFF, with the measured
reason in comments):

- `FP_ARB_RECLAIM` / `FP_ARB_MONK` (ensemble-arbiter): **regressed train overall
  (-1 to -3)** — the base's soft moves-only fingerprint already rescues true
  military, so these now grab real villagers into unused quota.
- `FP_VIL_SKIP`, `FP_ISO_LAG_GATE` (ensemble-arbiter): exactly score-neutral here
  (eco-exclusion/batch-exemption already cover their cases); left off to ship the
  holdout-verified base behavior, since they came from the one stack whose holdout
  overall dipped (98.9).
- Aztec `CIV_MIL_SPEED` 1/1.2 (queue-ledger's tick-exact calibration): **-0.9
  train military** in this stack — the base's batch/claim thresholds are tuned
  around the legacy 0.89; reverted (correcting timing requires a lag-robust
  aligner, see queue-ledger's key insight).
- id-spine monotone-DP hybrid: not ported — large, deeply coupled to baseline
  confidence tiers, and its own verified ceiling (84.4 train mil) is far below the
  base's 90.8; its two portable overrides were taken instead (one shipped, the
  eco-pin variant tested score-identical to the tighter ensemble abstain).
- civ-tech research blocks / co-production lines: skipped — blocks traded
  -0.7 train overall for +0.8 g0 military in their own stack (bad trade, likely
  overfit); co-production lines are dev-neutral and redundant with the static
  remap while requiring an invasive line-key change through the batch-claim code.

## Remaining top error patterns

- **Within-line archery confusions** (g0: archer->skirmisher x4, slinger->
  skirmisher x3, spearman->skirmisher x3, skirm misc x4): units first commanded
  10-30s after a foreign-type completion inside the SAME busy production line;
  time evidence cannot separate them (would need spatial/combat-target features).
- **Rare slow-train siege stolen by the dominant stream** (train: scorpion x2,
  mangonel x1, jaguarwarrior x1 -> scoutcavalry): sparse isolated siege slots vs
  a 95-eagle stream; the global monotone DP (id-spine) fixes exactly these but
  loses more elsewhere — the known next step is merging it tier-wise.
- **Passive military typed villager** (g0 champiscout->villager x2,
  spearman->villager x1; train monk->villager x1): units that never emit a single
  military-exclusive command in the recording.
- **`unit`->villager x3 (train)**: Armenian mule carts; their truth token
  canonicalizes to `unit`, which no concrete prediction can match, and they
  behave exactly like villagers — a permanent ~3-unit floor on that game.
- **knight->archer x2 (g0)**: cross-line claim collision when two buildings
  finish near-simultaneously and the knight is first-commanded late.

## Honest caveats

- **Sample size: 3 labelled games, 1 clean holdout.** Every selection decision
  used the same two dev games; the holdout was touched exactly once.
- **The holdout cannot demonstrate improvement**, only non-regression: its
  scoring window (10.8 min) contains just 15 military units and the baseline was
  already 100% military / 99.5% overall there. The +3.8/+11.9 military gains are
  measured on the two games the techniques were tuned on, and will shrink on
  unseen games.
- The one holdout overall error survived despite the availability veto (which
  fixed civ-tech-prior's holdout error in its own stack) — different stacks make
  different final calls; 185/186 was the merge's ceiling there.
- Coverage is unchanged by design: the classifier can only label units that ever
  appear in the command stream (held-back/never-commanded units are invisible).
- Train-game labels cover only a small subset of one player's villagers, so that
  game's overall % rests more heavily on military rows than g0's.
- Several base thresholds (batch adjacency <= 3 ids / 4s, iso gate 14s, scout
  n <= 3) are behaviorally motivated but numerically tuned on g0+train; treat
  them as priors to re-validate when more labelled games exist.
- The Aztec production-speed constant is knowingly wrong (0.89 vs the tick-exact
  1/1.2) because the aligner is calibrated around the legacy bias; fixing timing
  faithfully requires a lag-robust aligner first (queue-ledger's main finding).

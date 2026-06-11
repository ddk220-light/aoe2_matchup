# lab/ — ground-truth extraction & unit-classifier training for AoE2:DE replays

The research lab of the aoe2record repo (formerly the standalone `aoe2grpc` repo;
github.com/ddk220-light/aoe2grpc is now a frozen archive of its pre-merge history).

Part of the larger goal to **recreate an Age of Empires 2 game in the browser from
just the `.aoe2record` replay file**. Record files contain player *commands*, not game
state — so you cannot directly know which units existed or what type each one was.
This lab solves that by capturing the live game's internal state through its gRPC
spectator API, decoding it into per-unit ground-truth labels, and using those labels
to score and improve the classifier in `../visualizer/unit_classifier.py` — which
works from the record file *alone*.

**The foundational unlock (verified 2026-06-02):** gRPC `entity_id` == mgz
`instance_id` (98% overlap on the same game). Decoding the gRPC state to
`{entity_id → unit type}` therefore gives `{instance_id → true type}` — a direct
answer key for the replay, no positional correlation needed.

## Pipeline

1. **Capture** — `cade_api.proto` + generated stubs; `record_games.py` /
   `capture_session.py` stream the game state as length-delimited `FrameSequence`
   protobufs (~1 GB per 45-min game). Raw captures are **not** in the repo
   (gitignored, GB-scale).
2. **Decode** — `decode_state_v2.py`: flat-document + object-id model of the game
   state; seeds initial entities from full-state snapshots via a robust entity-band
   scan; applies per-frame delta patches. The 2026-06-10 fix added *re-anchor
   recovery*: on any desync signal the parser jumps to the next valid delta marker
   instead of silently corrupting the persistent document (this was the bug that
   previously made the decode plateau at ~6 minutes of game time).
3. **Ground truth** —
   - `extract_events.py`: production from the command stream
     (`MultiQueue{playerId, trainId, trainCount}`) — verified **13/13 unit types
     exact** against the replay's DE_QUEUE log;
   - `build_ground_truth.py`: initial + surviving entities from the start/end
     snapshots, deaths by difference;
   - `extract_labels.py`: per-unit labels `{instance_id → type, owner, created_ms,
     died_ms}` by anchoring on every op8 entity-create signature (desync-immune)
     plus `EntityKilled` events.
4. **Scoring** — `eval_against_truth.py` / `compare_game.py` /
   `_improve/score_game.py`: run the record-only classifier, map predictions and
   truth into a canonical token space, report coverage, overall (villager+military)
   and military-only accuracy with full confusion breakdowns.
5. **HP-over-time (side track)** — `grpc_hp_log.py`: live HP logger + `LiveEnd`
   fight-end tailer for staged army-vs-army fights (validated offline against a
   golden Jaguar Warrior dump via `_replay_live_end.py`); feeds combat-sim
   validation in the sibling `aoe2-unit-analyzer` project.

## Games & labels in this repo

| Game | Replay | Labels | Notes |
|---|---|---|---|
| g0 (dev) | `fresh_newpatch.aoe2record` (42.6 min, munq Bohemians vs ddk220 Incas) | `labels.json` | the original deep-dive game |
| train | `AgeIIDE_Replay_482723861` (44.5 min, Aztecs vs Armenians 1v1) | `labels_g2.json` | used for classifier tuning |
| holdout | `AgeIIDE_Replay_482721813` (15.8 min, 8 players) | `labels_g1.json` | never used for tuning; regression guard |

Replay files and raw captures live outside the repo (savegame folder / `captures/`,
gitignored). Label JSONs are small and tracked.

## Classifier & the multi-agent improvement run (2026-06-10)

The classifier itself lives in this repo at `../visualizer/unit_classifier.py` —
a staged, confidence-ladder design (behavioral hard pins → co-command propagation →
production timeline → squad typing → id-rank fallback). The improved version from
the run below was adopted there on 2026-06-10. This lab holds the scoring harness
and the `_improve/` workspaces from a multi-agent improvement workflow: five independent algorithm
angles, each iterating only on g0+train, then **adversarially verified** (claims
independently reproduced, clean holdout scored by the verifier only, code diff
inspected for label-leakage/hardcoding), then synthesized into
`_improve/final/unit_classifier.py` (see `_improve/REPORT.md`).

Baseline → verified per-angle results (military-only accuracy, the hard metric):

| Variant | g0 military | train military | Verdict |
|---|---|---|---|
| baseline | 80.9% | 78.9% | — |
| queue-ledger (production ledger sim) | 80.9% | 79.8% | accepted |
| civ-tech-prior (tech-tree constraints) | 81.7% | 78.9% | accepted |
| ensemble-arbiter (stage arbitration + villager-abstain) | 82.4% | 82.6% | accepted |
| id-spine-solver (global id↔production assignment) | 82.4% | 84.4% | accepted |
| **behavior-fingerprint** (movement/attack-target/task signals) | **84.7%** | **90.8%** | accepted |

Holdout (15 military units, baseline already 100%): no variant regressed it.
Key transferable findings: negative behavioral evidence beats positive timing
evidence (a unit that ever gathered cannot be military); command-log production
counts are a lower bound, not exact; time-fit is anti-correlated with truth inside
mass-select blobs (real army units idle before their first command, imposters get
commanded instantly after a completion).

## Repo map

- **gRPC client**: `cade_api.proto`, `cade_api_pb2*.py`, `info_test.py` (certs/keys gitignored)
- **Capture**: `record_games.py`, `capture_session.py`, `capture_lean.py`, `capture_state.py`, `dump_frames.py`
- **Decode**: `decode_state_v2.py` (+ `.pre_fix.bak.py` for the pre-fix state), `decode_state.py`, `decode_lifecycle.py`, `patch_decode.py`, `schema_patches.py`
- **Ground truth / labels**: `extract_events.py`, `build_ground_truth.py`, `extract_labels.py`, `extract_creates*.py`, `build_labels.py`
- **Scoring / analysis**: `eval_against_truth.py`, `compare_game.py`, `eval_goal.py`, `ambiguity_floor.py` (evidence-tier ceiling analysis), `compare_*`, `error_*`, `spine_classify.py`
- **HP logging**: `grpc_hp_log.py`, `redecode_hp.py`, `_replay_live_end.py`
- **Improvement workspaces**: `_improve/` (per-angle classifier copies, `final/`, `REPORT.md`)
- **Reference material**: `reference_model.rs`, `reference_patcher.rs`, `reference_format.md`, `fetched_*.rs` (the 2024 open-source model the wire format was reverse-engineered from)
- **Status docs**: `STATUS.md` (decode milestone summary), `OVERNIGHT_PLAN.md` (the 99%-accuracy north star + iteration log)
- `_*.py` files are one-off probes/diagnostics kept for the paper trail (`_wf_*` = the June-10 desync-fix investigation battery)

## Known gaps & caveats

- `aocref` dataset 100 lacks names for newer-patch master_ids (`idNNNN` truth units,
  e.g. post-upgrade eagle-line morphs) — excluded from scoring fairly; a current
  name table is in `de_names_current.json`.
- Coverage caps what any record-only classifier can see: units never individually
  commanded cannot be id-linked from the replay (e.g. train game coverage is 77%).
- Accuracy numbers rest on 2 full games + 1 short holdout; the holdout is
  military-saturated (100% at baseline) and serves as a regression guard only.
- Per-unit death times / continuous HP need the delta decode; the June-10 re-anchor
  fix addressed the known desync corruption.

## Related projects

- **../visualizer/** (this repo) — the browser isometric replay visualizer, the consumer of this work
- **C:\dev\aoe2\aoe2-unit-analyzer** — .dat extraction, combat simulator, matchup website (embeds a fork of the viewer; sync via `../docs/ANALYZER_SYNC.md`)
- **C:\dev\aoe2\aoc-mgz-67x** — local clone of the mgz parser fork (both deployments pip-pin the same commit)

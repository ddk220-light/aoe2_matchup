"""The replay layer (layer 4/5): replay-understanding + the viewer.

- unit_classifier.py — infers every unit's true type from the .aoe2record
  command stream alone (improved 2026-06-10 against gRPC ground truth from
  lab/: military accuracy g0 84.7% / train 90.8% / holdout 100%). Reads
  train_times.json BESIDE the module — keep them together (this is also the
  lab scoring harness's $env:UC_DIR contract).
- blueprint.py — `replay_bp`, the single mountable viewer backend.
- public/ — the canvas SPA (relative API fetches; serves under any prefix).
- clip_export.py — server-side WebM highlight clips.
"""

# aoe2x/replay — replay understanding + THE viewer (layer 4/5)

One canonical copy of everything replay (the historical
visualizer/server.py ↔ analyzer replay_core.py fork was unified here
2026-06-11; nothing is synced anymore).

## The classifier

`unit_classifier.py` infers every unit's true type from the `.aoe2record`
command stream alone — staged confidence ladder (behavioral hard pins →
co-command propagation → production timeline → squad typing → id-rank
fallback). API: `build_type_map(match)` on a parsed
`mgz.model.parse_match(...)` object.

Measured against gRPC ground truth (lab/): military-type accuracy
**84.7%** (g0) / **90.8%** (train) / **100%** (holdout) — see
`lab/_improve/REPORT.md`. `train_times.json` MUST sit beside the module
(also the lab harness's `$env:UC_DIR` contract).

## The viewer

`blueprint.py` exposes `replay_bp` — prefix-free Flask blueprint: SPA
serving (`public/`: canvas renderer, playback, player search) + API
(upload, load-match via aoe.ms, player/match browse via AoE2 Companion,
WebM clip export via `clip_export.py`). The SPA fetches RELATIVE URLs, so
one bundle works under any mount:

```python
app.register_blueprint(replay_bp)                        # at / (apps/viewer)
app.register_blueprint(replay_bp, url_prefix="/replay")  # embedded (website)
app.config["REPLAY_VIEW_URL"] = "/replay"                # share-link shell (optional)
```

Embedding elsewhere needs: this package + the pinned mgz fork + Pillow +
imageio-ffmpeg + requests (see `apps/viewer/requirements.txt`).

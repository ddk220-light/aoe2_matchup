#!/usr/bin/env python3
"""Role: serving — the standalone AoE2 Replay Viewer deployment.

A thin shell around the canonical viewer blueprint (aoe2x/replay/): serves
the SPA at / and the API at /api/* — the exact public URLs of the historical
aoe2record visualizer (whose server.py this replaced on 2026-06-11). The
matchup website mounts the SAME blueprint under /replay/*.
"""
import os

from flask import Flask
from flask_cors import CORS

from aoe2x.replay.blueprint import replay_bp

app = Flask(__name__)
CORS(app)
app.register_blueprint(replay_bp)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    print("Starting AoE2 Replay Viewer server...")
    print(f"Open http://localhost:{port} in your browser")
    app.run(debug=debug, host="0.0.0.0", port=port)

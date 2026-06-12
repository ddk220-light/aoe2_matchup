"""Engine-viewer host: static SPA + scenario data. PORT env, default 5003."""
import os
from pathlib import Path

from flask import Flask, jsonify, send_from_directory

ROOT = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=str(ROOT / "public"), static_url_path="")


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/scenarios")
def scenarios():
    return jsonify(sorted(p.name for p in (ROOT / "data").iterdir()
                          if p.is_dir()))


@app.get("/data/<scen>/<name>.json")
def data(scen, name):
    if name not in ("commands", "truth"):
        return jsonify({"error": "unknown file"}), 404
    path = ROOT / "data" / scen
    if not path.is_dir():
        return jsonify({"error": "unknown scenario",
                        "available": sorted(p.name for p in
                                            (ROOT / "data").iterdir()
                                            if p.is_dir())}), 404
    return send_from_directory(path, f"{name}.json")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5003)),
            debug=False)

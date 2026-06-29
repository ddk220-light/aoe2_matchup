import pytest


def _replay_html(client):
    """Rendered enabled-path replay.html (render directly when disabled here)."""
    import app
    if not getattr(app, "REPLAY_ENABLED", False):
        with app.app.test_request_context("/replay"):
            from flask import render_template
            return render_template("replay.html", active_nav="replay", replay_qs="")
    return client.get("/replay").data.decode()


def test_replay_describes_the_tool(client):
    body = _replay_html(client)
    assert "Replay Analyzer" in body
    assert "build order" in body.lower()
    assert "webm" in body.lower() or "clip" in body.lower()
    assert "/replay/index.html" in body  # embedded viewer preserved


def test_replay_softwareapplication_jsonld(client):
    body = _replay_html(client)
    assert '"@type": "SoftwareApplication"' in body
    assert '"@type": "HowTo"' in body

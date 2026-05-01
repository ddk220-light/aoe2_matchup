import importlib
import os

import pytest


@pytest.fixture
def reload_app(monkeypatch):
    """Reload webapp.app with a clean env so context processors re-read env vars."""
    def _reload(env_overrides):
        for k, v in env_overrides.items():
            if v is None:
                monkeypatch.delenv(k, raising=False)
            else:
                monkeypatch.setenv(k, v)
        import app as flask_app
        importlib.reload(flask_app)
        flask_app.app.config["TESTING"] = True
        return flask_app

    return _reload


def test_footer_config_all_set(reload_app):
    flask_app = reload_app({
        "CONTACT_FORM_ENDPOINT": "https://formspree.io/f/abc123",
        "SOCIAL_DISCORD_URL": "https://discord.gg/example",
        "SOCIAL_YOUTUBE_URL": "https://youtube.com/@example",
        "SOCIAL_INSTAGRAM_URL": "https://instagram.com/example",
    })
    with flask_app.app.test_request_context("/"):
        ctx = {}
        for processor in flask_app.app.template_context_processors[None]:
            ctx.update(processor())
        assert ctx["contact_form_endpoint"] == "https://formspree.io/f/abc123"
        assert ctx["social_links"] == {
            "discord": "https://discord.gg/example",
            "youtube": "https://youtube.com/@example",
            "instagram": "https://instagram.com/example",
        }


def test_footer_config_all_unset(reload_app):
    flask_app = reload_app({
        "CONTACT_FORM_ENDPOINT": None,
        "SOCIAL_DISCORD_URL": None,
        "SOCIAL_YOUTUBE_URL": None,
        "SOCIAL_INSTAGRAM_URL": None,
    })
    with flask_app.app.test_request_context("/"):
        ctx = {}
        for processor in flask_app.app.template_context_processors[None]:
            ctx.update(processor())
        assert ctx["contact_form_endpoint"] is None
        assert ctx["social_links"] == {
            "discord": None,
            "youtube": None,
            "instagram": None,
        }

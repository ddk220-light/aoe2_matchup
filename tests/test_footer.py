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


def test_home_page_uses_new_site_name(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "AoE2 Matchup" in body
    # Old name must not appear anywhere in the rendered HTML
    assert "AoE2 Unit Analyzer" not in body
    assert "AoE2 Analyzer" not in body


def test_og_site_name_is_renamed(client):
    resp = client.get("/")
    body = resp.data.decode()
    assert '<meta property="og:site_name" content="AoE2 Matchup"' in body


def test_jsonld_includes_sameas_when_social_urls_set(monkeypatch):
    monkeypatch.setenv("SOCIAL_DISCORD_URL",   "https://discord.gg/example")
    monkeypatch.setenv("SOCIAL_YOUTUBE_URL",   "https://youtube.com/@example")
    monkeypatch.setenv("SOCIAL_INSTAGRAM_URL", "https://instagram.com/example")
    import importlib, app as flask_app
    importlib.reload(flask_app)
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        body = c.get("/").data.decode()
    assert '"sameAs"' in body
    assert "https://discord.gg/example" in body
    assert "https://youtube.com/@example" in body
    assert "https://instagram.com/example" in body


def test_jsonld_omits_sameas_when_no_social_urls(monkeypatch):
    monkeypatch.delenv("SOCIAL_DISCORD_URL",   raising=False)
    monkeypatch.delenv("SOCIAL_YOUTUBE_URL",   raising=False)
    monkeypatch.delenv("SOCIAL_INSTAGRAM_URL", raising=False)
    import importlib, app as flask_app
    importlib.reload(flask_app)
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        body = c.get("/").data.decode()
    # When all social URLs are unset, the sameAs key should not appear.
    assert '"sameAs"' not in body


def test_footer_renders_on_home_page(client):
    body = client.get("/").data.decode()
    assert '<footer class="site-footer"' in body
    # Brand column
    assert "AoE2 Matchup" in body
    # Explore column has the four nav links
    for href in ["/", "/matchup-advisor", "/units", "/civilizations"]:
        assert f'href="{href}"' in body
    # Sources column
    assert "aoe2techtree.net" in body
    assert "genieutils" in body.lower()
    assert "ageofempires.fandom.com" in body
    # Microsoft disclaimer
    assert "not affiliated" in body.lower()
    assert "Microsoft" in body


def test_footer_hides_contact_button_when_endpoint_unset(client, monkeypatch):
    monkeypatch.delenv("CONTACT_FORM_ENDPOINT", raising=False)
    import importlib, app as flask_app
    importlib.reload(flask_app)
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        body = c.get("/").data.decode()
    assert 'data-action="open-contact-modal"' not in body


def test_footer_hides_social_link_when_url_unset(client, monkeypatch):
    monkeypatch.delenv("SOCIAL_DISCORD_URL",   raising=False)
    monkeypatch.setenv("SOCIAL_YOUTUBE_URL",   "https://youtube.com/@example")
    monkeypatch.delenv("SOCIAL_INSTAGRAM_URL", raising=False)
    import importlib, app as flask_app
    importlib.reload(flask_app)
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        body = c.get("/").data.decode()
    assert "youtube.com/@example" in body
    # No discord or instagram link rendered
    assert "discord.gg" not in body
    assert "instagram.com" not in body


def test_contact_modal_renders_when_endpoint_set(client, monkeypatch):
    monkeypatch.setenv("CONTACT_FORM_ENDPOINT", "https://formspree.io/f/abc123")
    import importlib, app as flask_app
    importlib.reload(flask_app)
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        body = c.get("/").data.decode()
    assert 'class="contact-modal"' in body
    assert 'action="https://formspree.io/f/abc123"' in body
    # Honeypot field present
    assert 'name="_gotcha"' in body
    # Required fields
    assert 'name="email"' in body
    assert 'name="message"' in body


def test_contact_modal_absent_when_endpoint_unset(client, monkeypatch):
    monkeypatch.delenv("CONTACT_FORM_ENDPOINT", raising=False)
    import importlib, app as flask_app
    importlib.reload(flask_app)
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        body = c.get("/").data.decode()
    assert 'class="contact-modal"' not in body

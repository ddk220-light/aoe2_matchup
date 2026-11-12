"""Regression coverage for the retired website Replay Analyzer."""


def test_replay_routes_are_not_registered(client):
    assert client.get("/replay").status_code == 404
    # Flask canonicalizes the trailing slash to /replay before returning 404.
    assert client.get("/replay/", follow_redirects=True).status_code == 404
    assert client.get("/replay/api/default").status_code == 404


def test_replay_is_not_linked_from_public_pages():
    from scripts.migration.site import pages
    for text in (pages.simulator_about(), pages.about()['body']):
        assert "Replay Analyzer" not in text
        assert 'href="/replay"' not in text


def test_replay_is_not_in_sitemap():
    from scripts.migration.site import sitemap
    assert "/replay" not in sitemap.sitemap_xml()

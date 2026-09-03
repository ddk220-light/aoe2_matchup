"""Regression coverage for the retired website Replay Analyzer."""


def test_replay_routes_are_not_registered(client):
    assert client.get("/replay").status_code == 404
    # Flask canonicalizes the trailing slash to /replay before returning 404.
    assert client.get("/replay/", follow_redirects=True).status_code == 404
    assert client.get("/replay/api/default").status_code == 404


def test_replay_is_not_linked_from_public_pages(client):
    for path in ("/", "/about"):
        body = client.get(path).data.decode()
        assert "Replay Analyzer" not in body
        assert 'href="/replay"' not in body


def test_replay_is_not_in_sitemap(client):
    body = client.get("/sitemap.xml").data.decode()
    assert "/replay" not in body

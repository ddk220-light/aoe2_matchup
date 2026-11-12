# tests/test_seo_audit.py — canonical-URL redirects (the API's _seo_canonical_redirects hook).
# The patch-page metadata assertions live in tests/test_site_builders.py with the page builders.


def test_trailing_slash_redirects(client):
    resp = client.get("/api/armor-classes/")
    assert resp.status_code == 301
    assert resp.headers["Location"].endswith("/api/armor-classes")


def test_trailing_slash_redirect_preserves_query(client):
    resp = client.get("/api/armor-classes/?foo=1")
    assert resp.status_code == 301
    assert resp.headers["Location"].endswith("/api/armor-classes?foo=1")


def test_root_is_not_redirected(client):
    # "/" is not an API path (404 here), but it is never trailing-slash redirected.
    resp = client.get("/")
    assert resp.status_code != 301
    assert "Location" not in resp.headers


def test_www_host_redirects_to_apex(client):
    resp = client.get("/api/armor-classes", base_url="https://www.aoe2matchup.com")
    assert resp.status_code == 301
    assert resp.headers["Location"] == "https://aoe2matchup.com/api/armor-classes"


def test_www_host_redirect_preserves_query(client):
    resp = client.get("/api/ref/unit-line/stable?tab=cavalry", base_url="https://www.aoe2matchup.com")
    assert resp.status_code == 301
    assert resp.headers["Location"] == "https://aoe2matchup.com/api/ref/unit-line/stable?tab=cavalry"


def test_local_hosts_are_not_redirected(client):
    # Staging / localhost must NOT be forced onto the prod domain.
    assert client.get("/api/armor-classes").status_code == 200

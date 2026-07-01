# tests/test_seo_audit.py — SEO audit fixes: canonical-URL redirects + patch-page metadata.
_DEFAULT_DESC = "Free Age of Empires II matchup simulator"  # base.html fallback description


def test_trailing_slash_redirects(client):
    resp = client.get("/matchups/")
    assert resp.status_code == 301
    assert resp.headers["Location"].endswith("/matchups")


def test_trailing_slash_redirect_preserves_query(client):
    resp = client.get("/matchups/?foo=1")
    assert resp.status_code == 301
    assert resp.headers["Location"].endswith("/matchups?foo=1")


def test_root_is_not_redirected(client):
    assert client.get("/").status_code == 200


def test_www_host_redirects_to_apex(client):
    resp = client.get("/units", base_url="https://www.aoe2matchup.com")
    assert resp.status_code == 301
    assert resp.headers["Location"] == "https://aoe2matchup.com/units"


def test_www_host_redirect_preserves_query(client):
    resp = client.get("/units?tab=cavalry", base_url="https://www.aoe2matchup.com")
    assert resp.status_code == 301
    assert resp.headers["Location"] == "https://aoe2matchup.com/units?tab=cavalry"


def test_local_hosts_are_not_redirected(client):
    # Staging / localhost must NOT be forced onto the prod domain.
    assert client.get("/units").status_code == 200


def test_patches_hub_has_keyword_title_and_description(client):
    body = client.get("/patches").data.decode()
    assert "<title>AoE2 Patch Notes" in body
    head = body.split("</head>")[0]
    assert _DEFAULT_DESC not in head  # dedicated description, not the homepage fallback
    assert "patch notes" in head.lower()


def test_patch_unit_page_has_specific_description_and_breadcrumbs(client):
    import app
    conn = app._patches_conn()
    row = conn.execute(
        "SELECT p.build_number AS b, c.civ_name AS civ, c.unit_slug AS slug "
        "FROM patch_unit_changes c JOIN patches p ON p.id = c.patch_id LIMIT 1"
    ).fetchone()
    conn.close()
    body = client.get(f"/patches/{row['b']}/{row['civ']}/{row['slug']}").data.decode()
    head = body.split("</head>")[0]
    assert _DEFAULT_DESC not in head  # dedicated description, not the homepage fallback
    assert '"@type": "BreadcrumbList"' in body

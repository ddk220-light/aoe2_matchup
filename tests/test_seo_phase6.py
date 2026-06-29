# tests/test_seo_phase6.py
def test_popular_matchups_all_resolve(client):
    import app
    for m in app._POPULAR_MATCHUPS:
        (ca, ua), (cb, ub) = m["a"], m["b"]
        url = f"/vs/{ca}/{ua}/{cb}/{ub}"
        assert client.get(url).status_code == 200, f"{m['label']} -> {url} did not 200"


def test_popular_matchups_on_hub(client):
    body = client.get("/matchups").data.decode()
    assert "Popular matchups" in body
    assert "Knight vs Pikeman" in body
    assert "/vs/Franks/paladin/Bulgarians/halberdier" in body


def test_popular_matchups_in_sitemap(client):
    body = client.get("/sitemap.xml").data.decode()
    assert "/vs/Franks/paladin/Bulgarians/halberdier</loc>" in body

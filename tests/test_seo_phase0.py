# tests/test_seo_phase0.py
import datetime


def test_sitemap_lastmod_reflects_data_build(client):
    import app
    body = client.get("/sitemap.xml").data.decode()
    expected = app._data_lastmod()
    # Every <lastmod> in the sitemap uses the data-build date, not "today".
    assert f"<lastmod>{expected}</lastmod>" in body
    # And it is a valid ISO date.
    datetime.date.fromisoformat(expected)

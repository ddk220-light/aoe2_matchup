import re


def _primary_nav(body: str) -> str:
    match = re.search(
        r'<div class="nav-links" id="navLinks">(.*?)</div>',
        body,
        flags=re.DOTALL,
    )
    assert match, "primary navigation was not rendered"
    return match.group(1)


def test_primary_navigation_includes_the_matchup_advisor(client):
    nav = _primary_nav(client.get("/").data.decode())

    assert nav.count('class="nav-tab ') == 4
    assert 'href="/"' in nav
    assert 'href="/civilizations"' in nav
    assert 'href="/units"' in nav
    assert 'href="/matchup-advisor"' in nav
    assert 'href="/patches"' not in nav
    assert 'href="/replay"' not in nav


def test_primary_navigation_uses_labelled_svg_icons_and_active_state(client):
    nav = _primary_nav(client.get("/").data.decode())

    assert nav.count('class="nav-tab-icon"') == 4
    assert nav.count("<svg ") == 4
    assert "Battle Simulation" in nav
    assert "Civilizations" in nav
    assert "Unit Rankings" in nav
    assert "Matchup Advisor" in nav
    assert 'aria-current="page"' in nav


def test_advisor_navigation_marks_its_own_tab_active(client):
    nav = _primary_nav(client.get("/matchup-advisor").data.decode())
    assert re.search(
        r'<a href="/matchup-advisor" class="nav-tab active"\s+aria-label="Matchup Advisor"\s+aria-current="page"',
        nav,
    )
    assert nav.count('aria-current="page"') == 1

import re


def _primary_nav(body: str) -> str:
    match = re.search(
        r'<div class="nav-links" id="navLinks">(.*?)</div>',
        body,
        flags=re.DOTALL,
    )
    assert match, "primary navigation was not rendered"
    return match.group(1)


def test_primary_navigation_exposes_only_the_three_public_sections(client):
    nav = _primary_nav(client.get("/").data.decode())

    assert nav.count('class="nav-tab ') == 3
    assert 'href="/"' in nav
    assert 'href="/civilizations"' in nav
    assert 'href="/units"' in nav
    assert 'href="/matchup-advisor"' not in nav
    assert 'href="/patches"' not in nav
    assert 'href="/replay"' not in nav


def test_primary_navigation_uses_labelled_svg_icons_and_active_state(client):
    nav = _primary_nav(client.get("/").data.decode())

    assert nav.count('class="nav-tab-icon"') == 3
    assert nav.count("<svg ") == 3
    assert "Battle Simulation" in nav
    assert "Civilizations" in nav
    assert "Unit Rankings" in nav
    assert 'aria-current="page"' in nav

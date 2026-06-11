"""Availability-resolver REPORT-MODE tests (Phase B gate — swap NOT performed).

Census re-pinned 2026-06-11 against the IMPERIAL-ONLY ref DB (build 177723):
**163 mismatches** across 1,325 standard (civ x line) Imperial cells; 1,162
agree. **The ref DB side is CLEAN**: every remaining mismatch is a documented
RESOLVER-SIDE limitation (information the dat does not carry), not a wrong
ref row. The Phase B decision rule still requires exactly 0 mismatches to
swap generate_reference onto the resolver, so `_AVAILABILITY_OVERRIDES`
stays authoritative and this module pins the report instead.

History of the ref-DB-side mismatches (all fixed, none remain):
  * 4 militia-line ghost rows (Incas/Mapuche/Muisca/Tupi `champion` showing
    Man-at-Arms) — killed DERIVATIONALLY 2026-06-11: generate_reference now
    consults `AvailabilityResolver.tech_tree_disabled_unit_closure()` (the
    civ tech-tree's type-2 unit disables + the dat's type-3 upgrade-edge
    closure), so a civ whose tree disables a line's root unit never emits
    any tier of that line.
  * 4 phantom 3K siege rows (`trebuchet` Shu/Wei/Wu, `heavy_scorpion` Shu) —
    purged 2026-06-11 with CivTechTrees evidence (the game's
    CivTechTrees/<CIV>.json marks Trebuchet NotAvailable for all three —
    they field the Traction Trebuchet — and Scorpion/Heavy Scorpion
    NotAvailable for Shu). Fixed derivationally via the existing
    `availability_tech` gate: trebuchet -> tech 256, heavy_scorpion ->
    tech 94, both tree-disabled for exactly the affected civs.
  * The Castle-age tier-bonus disagreements (Khitans HCA, Cumans Capped Ram,
    Armenians Halberdier/Champion @Castle) vanished with the Castle rows
    themselves — the Imperial-only data model has no Castle universe.

Root cause of the remaining 163 (verified in the dat, see
analysis/availability_resolver.py and docs/architecture/data-model-review.md
section 3.1): tech 79 "Disable Regionals" fires for every civ in normal
games and 102-disables every regional make-avail/upgrade tech; the only
counter is tech 78 with full_tech_mode == -1 (Full-Tech-Tree-only). The
per-civ regional grants live outside empires2_x2_p1.dat, in the game's
CivTechTrees/<CIV>.json files (exactly what aoe2techtree.net reads). The dat
therefore CANNOT express the regional allowlist lines; the curated lists are
irreducible until the pipeline extracts CivTechTrees JSON.

Remaining mismatch census by category (per-key category in
MISMATCH_CATEGORIES below; civ lists pinned in EXPECTED_MISMATCHES):

  regional_grant (missing, 56 rows): the regional lines tech-79 locks in the
    dat whose per-civ grants are CivTechTrees-side — heavy_camel(13),
    elite_elephant(6), elite_ele_archer(3), elite_eagle(2), imp_slinger(4),
    elite_champi_warrior(4), elite_steppe(5), elite_fire_lancer(5),
    paladin(3: the Hei-Kuang alternate), siege_onager(4: the Rocket Cart
    alternate), siege_ram(4: the armored/siege-elephant alternate),
    traction_trebuchet(3). The ref rows are REAL (granted in-game).

  team_bonus_leak (phantom, 104 rows): condottiero(52) + elite_genitour(52)
    — their enabler techs are civ=-1 shadow techs with no in-dat per-civ
    gate (team-bonus sharing is engine/CivTechTrees logic), so the resolver
    grants them to everyone. The ref DB correctly restricts them.

  enable_mechanism (missing, 1 row): flemish_militia Burgundians — Flemish
    Revolution converts villagers (unit-spawn), not a resolvable type-2
    enable.

  mode_gating (tier, 1 row): Wei champion — resolver reaches the Paphos
    Champion variant via tech 1174 (Wei does not 102-disable 1138 Paphos
    Shadow Tech); Chronicles mode-gating is outside the dat.

  regional_grant (tier, 1 row): Vietnamese imp_elite_skirm — tech 656
    auto-disables Imperial Skirmisher 655 at Castle for everyone; the
    Vietnamese grant is CivTechTrees-side.

What the resolver DOES get right (1,162 rows, kept green below): every
default-roster line and tier across all 53 civs at Imperial (knight/militia/
spear/archer/skirm/scout/CA/siege/HC/BBC gating via tech-tree 102-disables,
including the new availability_tech gates above), the Winged Hussar OR-slot
derivation, the 655/656 interlock, and the type-2 militia-line removal for
the four American civs.
"""

import os

import pytest

# The resolver reads extraction/extracted_data/*.json, which is gitignored
# (regenerated locally from the .dat, like the dat itself) — absent on CI.
# The census is a local guard, same policy as the extraction toolchain.
_EXTRACTED = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "extraction", "extracted_data", "units.json",
)
pytestmark = pytest.mark.skipif(
    not os.path.exists(_EXTRACTED),
    reason="requires local extraction outputs (extraction/extracted_data/, gitignored)",
)

if os.path.exists(_EXTRACTED):
    from analysis.availability_resolver import AvailabilityResolver, build_report

# ---------------------------------------------------------------------------
# Pinned report (2026-06-11, build 177723, Imperial-only ref DB).
# Regenerate the literals with:  python -m analysis.availability_resolver
# ---------------------------------------------------------------------------
EXPECTED_TOTAL = 1325
EXPECTED_AGREE = 1162

_ALL_53 = ["Armenians", "Aztecs", "Bengalis", "Berbers", "Bohemians", "Britons", "Bulgarians", "Burgundians", "Burmese", "Byzantines", "Celts", "Chinese", "Cumans", "Dravidians", "Ethiopians", "Franks", "Georgians", "Goths", "Gurjaras", "Hindustanis", "Huns", "Incas", "Italians", "Japanese", "Jurchens", "Khitans", "Khmer", "Koreans", "Lithuanians", "Magyars", "Malay", "Malians", "Mapuche", "Mayans", "Mongols", "Muisca", "Persians", "Poles", "Portuguese", "Romans", "Saracens", "Shu", "Sicilians", "Slavs", "Spanish", "Tatars", "Teutons", "Tupi", "Turks", "Vietnamese", "Vikings", "Wei", "Wu"]

EXPECTED_MISMATCHES = {
    ("champion", "Imperial", "tier"): ["Wei"],
    # condottiero leaks to all civs except its real ref owner (Italians);
    # elite_genitour to all except its real ref owner (Berbers).
    ("condottiero", "Imperial", "phantom"): [c for c in _ALL_53 if c != "Italians"],
    ("elite_champi_warrior", "Imperial", "missing"): ["Incas", "Mapuche", "Muisca", "Tupi"],
    ("elite_eagle", "Imperial", "missing"): ["Aztecs", "Mayans"],
    ("elite_ele_archer", "Imperial", "missing"): ["Bengalis", "Dravidians", "Gurjaras"],
    ("elite_elephant", "Imperial", "missing"): ["Bengalis", "Burmese", "Dravidians", "Khmer", "Malay", "Vietnamese"],
    ("elite_fire_lancer", "Imperial", "missing"): ["Chinese", "Jurchens", "Khitans", "Koreans", "Vietnamese"],
    ("elite_genitour", "Imperial", "phantom"): [c for c in _ALL_53 if c != "Berbers"],
    ("elite_steppe", "Imperial", "missing"): ["Cumans", "Jurchens", "Khitans", "Mongols", "Tatars"],
    ("flemish_militia", "Imperial", "missing"): ["Burgundians"],
    ("heavy_camel", "Imperial", "missing"): ["Berbers", "Byzantines", "Cumans", "Ethiopians", "Gurjaras", "Hindustanis", "Khitans", "Malians", "Mongols", "Persians", "Saracens", "Tatars", "Turks"],
    ("imp_elite_skirm", "Imperial", "tier"): ["Vietnamese"],
    ("imp_slinger", "Imperial", "missing"): ["Incas", "Mapuche", "Muisca", "Tupi"],
    ("paladin", "Imperial", "missing"): ["Shu", "Wei", "Wu"],
    ("siege_onager", "Imperial", "missing"): ["Chinese", "Jurchens", "Khitans", "Koreans"],
    ("siege_ram", "Imperial", "missing"): ["Bengalis", "Dravidians", "Gurjaras", "Hindustanis"],
    ("traction_trebuchet", "Imperial", "missing"): ["Shu", "Wei", "Wu"],
}

# Every pinned mismatch key is a documented RESOLVER-side limitation — the
# census is "ref DB clean". A key here without a category is a test bug; a
# mismatch without a pin is a regression in one of (resolver, extraction,
# ref DB) and must be investigated, not re-pinned.
MISMATCH_CATEGORIES = {
    ("champion", "Imperial", "tier"): "mode_gating",
    ("condottiero", "Imperial", "phantom"): "team_bonus_leak",
    ("elite_champi_warrior", "Imperial", "missing"): "regional_grant",
    ("elite_eagle", "Imperial", "missing"): "regional_grant",
    ("elite_ele_archer", "Imperial", "missing"): "regional_grant",
    ("elite_elephant", "Imperial", "missing"): "regional_grant",
    ("elite_fire_lancer", "Imperial", "missing"): "regional_grant",
    ("elite_genitour", "Imperial", "phantom"): "team_bonus_leak",
    ("elite_steppe", "Imperial", "missing"): "regional_grant",
    ("flemish_militia", "Imperial", "missing"): "enable_mechanism",
    ("heavy_camel", "Imperial", "missing"): "regional_grant",
    ("imp_elite_skirm", "Imperial", "tier"): "regional_grant",
    ("imp_slinger", "Imperial", "missing"): "regional_grant",
    ("paladin", "Imperial", "missing"): "regional_grant",
    ("siege_onager", "Imperial", "missing"): "regional_grant",
    ("siege_ram", "Imperial", "missing"): "regional_grant",
    ("traction_trebuchet", "Imperial", "missing"): "regional_grant",
}


@pytest.fixture(scope="module")
def resolver():
    return AvailabilityResolver()


@pytest.fixture(scope="module")
def report(resolver):
    return build_report(resolver)


def test_report_totals_and_clean_run(report):
    """The report covers every Imperial (civ, slug) cell exactly once, with
    no unmappable ref names and no fixed-point anomalies."""
    assert report["total"] == EXPECTED_TOTAL
    assert report["agree"] + report["mismatch_count"] == report["total"]
    assert report["warnings"] == []


@pytest.mark.xfail(
    reason="163 mismatches (2026-06-11, Imperial-only universe): all "
    "resolver-side — empires2_x2_p1.dat does not encode per-civ regional "
    "availability (tech 79 'Disable Regionals' locks the regional lines in "
    "normal games; the per-civ grants live in the game's "
    "CivTechTrees/<CIV>.json) and team-bonus unit sharing has no in-dat "
    "gate. Swap gate per Phase B decision rule: requires exactly 0. See "
    "module docstring and data-model-review.md section 3.1.",
    strict=False,
)
def test_resolver_matches_committed_rosters_exactly(report):
    """THE PHASE B GATE: resolver == committed ref DB rosters, 0 mismatches.

    Flips green when a CivTechTrees JSON extractor lands and the resolver
    learns the regional grants + team-bonus restrictions."""
    assert report["mismatch_count"] == 0, (
        f"{report['mismatch_count']} mismatches; first 10: "
        f"{report['mismatches'][:10]}"
    )


def test_mismatches_are_exactly_the_documented_163(report):
    """Regression pin: the mismatch set is frozen as documented above.

    STRICT EQUALITY: any drift (new dat extraction, resolver edit, ref
    regen) must update this pin consciously. Because every pinned key is
    categorized as resolver-side in MISMATCH_CATEGORIES, a NEW mismatch is
    by definition a candidate ref-DB-side bug (the phantom-row class) and
    needs investigation, not a re-pin.
    """
    got = {}
    for mm in report["mismatches"]:
        got.setdefault((mm["slug"], mm["age"], mm["kind"]), []).append(mm["civ"])
    got = {key: sorted(civs) for key, civs in got.items()}
    assert got == EXPECTED_MISMATCHES
    assert report["mismatch_count"] == sum(len(v) for v in EXPECTED_MISMATCHES.values())
    assert report["agree"] == EXPECTED_AGREE


def test_every_pinned_mismatch_is_categorized_resolver_side():
    """The census headline: ref DB clean — every remaining mismatch carries
    a documented resolver-side category."""
    assert set(MISMATCH_CATEGORIES) == set(EXPECTED_MISMATCHES)
    allowed = {"regional_grant", "team_bonus_leak", "enable_mechanism", "mode_gating"}
    assert set(MISMATCH_CATEGORIES.values()) <= allowed


def test_override_lists_vs_resolver(report):
    """The 17 curated _AVAILABILITY_OVERRIDES lists (SiegeEngineers truth)
    against resolver line presence: the dat grants regionals to NOBODY (no
    phantom regional civs either — tech 79 cuts both ways), and paladin
    resolves for every curated civ except the three Hei-Kuang (3K) civs."""
    overrides = report["overrides"]
    assert len(overrides) == 17
    for slug, cmp in overrides.items():
        curated = set(cmp["curated"])
        got = set(cmp["resolver"])
        if slug == "paladin":
            assert got == curated - {"Shu", "Wei", "Wu"}
        else:
            # regional lines: resolver grants none, and invents none
            assert got == set(), f"{slug}: resolver granted {got}"


# ---------------------------------------------------------------------------
# Green guards: what the dat DOES resolve correctly today.
# ---------------------------------------------------------------------------
def test_knight_line_tiers(resolver):
    """Default-roster gating via tech-tree 102-disables works end to end."""
    # Franks: full line to Paladin 569
    assert resolver.resolve("Franks", 4).line_status([38]) == (True, 569)
    # Britons: Paladin (265) disabled -> Cavalier 283
    assert resolver.resolve("Britons", 4).line_status([38]) == (True, 283)
    # Burgundians: Cavalier in CASTLE age (civ-bound OR-slot on tech 209)
    assert resolver.resolve("Burgundians", 3).line_status([38]) == (True, 283)
    # Persians: Savar 1813 tops the line (civ-bound tech 526)
    assert resolver.resolve("Persians", 4).line_status([38]) == (True, 1813)
    # Dravidians: knight line disabled outright (tech 166 in their tree)
    assert resolver.resolve("Dravidians", 4).line_status([38]) == (False, None)


def test_winged_hussar_or_slot(resolver):
    """Tech 786 requires 3 of [115, 254, 788, 789]; 788/789 are Lithuanians/
    Poles-bound layer-0 shadow techs that also disable Hussar 428 — the
    required_tech_count mechanism the extraction gained in cb979b1."""
    assert resolver.resolve("Poles", 4).line_status([448]) == (True, 1707)
    assert resolver.resolve("Lithuanians", 4).line_status([448]) == (True, 1707)
    # a regular hussar civ stays on Hussar 441
    assert resolver.resolve("Magyars", 4).line_status([448]) == (True, 441)
    # Franks: Hussar (428) disabled -> Light Cavalry 546
    assert resolver.resolve("Franks", 4).line_status([448]) == (True, 546)


def test_early_tier_civ_bonuses_resolved_from_dat(resolver):
    """Civ-bound OR-slots grant upgrades an age early — real bonuses the
    config age-gating cannot express. The ref DB no longer materializes a
    Castle universe, so these resolve-only checks are the record that the
    mechanism works (they feed nothing user-facing today)."""
    # Cumans: Capped Ram at Castle (tech 96 req [103, 706] cnt=1, 706 Cumans-bound)
    assert resolver.resolve("Cumans", 3).line_status([35]) == (True, 422)
    # Khitans: Heavy Cav Archer at Castle (tech 218 req [103, 192, 1004] cnt=2)
    assert resolver.resolve("Khitans", 3).line_status([39]) == (True, 474)
    # Armenians: infantry upgrades one age earlier -> Halberdier at Castle
    assert resolver.resolve("Armenians", 3).line_status([93]) == (True, 359)


def test_imperial_skirmisher_interlock(resolver):
    """Tech 656 (req [98]) fires at Castle and disables 655 before its
    Imperial eligibility — for every civ, including Vietnamese (their grant
    is CivTechTrees-side). The phase-staged fixed point preserves this."""
    res = resolver.resolve("Vietnamese", 4)
    assert 656 in res.fired
    assert 655 in res.disabled
    assert res.line_status([7]) == (True, 6)  # Elite Skirmisher, not Imperial


def test_regional_lockout_is_total(resolver):
    """Tech 79 fires for every civ and locks the regional enablers — even the
    civs that own the lines in-game (the grants live in CivTechTrees JSON)."""
    for civ in ("Franks", "Berbers", "Gurjaras", "Aztecs", "Khmer"):
        res = resolver.resolve(civ, 4)
        assert 79 in res.fired
        assert 235 in res.disabled  # camels
        assert 630 in res.disabled  # battle elephants
        assert 433 in res.disabled  # eagles
        assert res.line_status([329, 1755]) == (False, None)
        assert res.line_status([1132]) == (False, None)


def test_american_civs_militia_line_removed(resolver):
    """Incas/Muisca/Mapuche/Tupi tech trees type-2-disable unit 74 (Militia).
    The in-game CivTechTrees JSON agrees (Militia/Man-at-Arms/Champion are
    NotAvailable for Incas) — and since 2026-06-11 generate_reference
    consults the same disable closure, so the ref DB agrees too (the ghost
    champion rows are gone)."""
    for civ in ("Incas", "Muisca", "Mapuche", "Tupi"):
        assert resolver.resolve(civ, 4).line_status([74, 75]) == (False, None)
    assert resolver.resolve("Aztecs", 4).line_status([74, 75]) == (True, 567)


def test_type2_disabled_unit_closure(resolver):
    """The ghost-killing gate generate_reference consumes: type-2 tech-tree
    disables expanded through the dat's type-3 upgrade edges."""
    closure = resolver.tech_tree_disabled_unit_closure("Incas")
    # Militia root 74 and every tier above it, incl. Champion 567
    assert {74, 75, 77, 473, 567} <= closure
    # Buildings the tree also disables come along (68 Mill etc.) — harmless,
    # no line config carries their ids.
    assert 68 in closure
    # Civs without type-2 unit disables get an empty closure
    assert resolver.tech_tree_disabled_unit_closure("Franks") == frozenset()


def test_3k_siege_availability_gates(resolver):
    """The 2026-06-11 phantom purge encoded in the dat-driven config gates:
    tech 256 (Trebuchet) is tree-disabled for exactly Shu/Wei/Wu, tech 94
    (Scorpion) for exactly Shu — matching CivTechTrees NotAvailable."""
    disabled_256 = {
        civ for civ in ("Shu", "Wei", "Wu", "Franks", "Chinese", "Mongols")
        if 256 in resolver.analyzer.get_disabled_techs(civ)
    }
    assert disabled_256 == {"Shu", "Wei", "Wu"}
    disabled_94 = {
        civ for civ in ("Shu", "Wei", "Wu", "Franks", "Celts")
        if 94 in resolver.analyzer.get_disabled_techs(civ)
    }
    assert disabled_94 == {"Shu"}

"""Availability-resolver REPORT-MODE tests (Phase B gate — swap NOT performed).

Resolver report 2026-06-10 (build 177723, committed ref DB): **282 mismatches**
across 2,332 standard (civ x line x age) rows; 2,050 agree. The Phase B
decision rule required exactly 0 to swap generate_reference onto the resolver,
so `_AVAILABILITY_OVERRIDES` stays authoritative and this module pins the
report instead.

Root cause (verified in the dat, see analysis/availability_resolver.py and
docs/architecture/data-model-review.md section 3.1): tech 79 "Disable
Regionals" fires for every civ in normal games and 102-disables every
regional make-avail/upgrade tech; the only counter is tech 78 with
full_tech_mode == -1 (Full-Tech-Tree-only). The per-civ regional grants live
outside empires2_x2_p1.dat, in the game's CivTechTrees/<CIV>.json files
(exactly what aoe2techtree.net reads). The dat therefore CANNOT express the
17 allowlist lines; the curated lists are irreducible until the pipeline
extracts CivTechTrees JSON.

Mismatch census by (slug, age, kind) — civ lists pinned in
EXPECTED_MISMATCHES below:

  missing (resolver denies a line the ref DB grants) — 223 rows:
    the 16 regional override lists in full (camel/heavy_camel 13+13,
    elephant/elite 6+6, elephant_archer/elite 3+3, eagle/elite 2+2,
    slinger/imp_slinger 4+4, champi/elite 4+4, steppe/elite 5+5,
    fire_lancer/elite 5+5) — tech-79 regional lockout;
    paladin Shu/Wei/Wu (Hei-Kuang alternate is regional-locked);
    ram/siege_ram Bengalis/Dravidians/Gurjaras/Hindustanis (armored-elephant
    alternate regional-locked); mangonel/siege_onager Chinese/Jurchens/
    Khitans/Koreans (dat disables Mangonel 358; Rocket Cart regional-locked);
    trebuchet+traction_trebuchet Shu/Wei/Wu; scorpion+heavy_scorpion Shu;
    swordsmen/champion/champi lines Incas/Mapuche/Muisca/Tupi (their tech
    trees type-2-disable unit 74 Militia — the in-game CivTechTrees JSON
    confirms Militia/Man-at-Arms/Champion are NotAvailable for Incas, so
    these ref rows are themselves phantom); flemish_militia Burgundians
    (Flemish Revolution enables via unit-spawn, not a resolvable enable).

  phantom (resolver grants a line the ref DB denies) — 52+52+52 rows:
    genitour/elite_genitour/condottiero leak to every civ — their enabler
    techs (601/427, 462-era condottiero chain) are civ=-1 shadow techs with
    no in-dat per-civ gate (team-bonus sharing is engine/CivTechTrees logic).

  tier (line present on both sides, different top unit) — 6 rows:
    Khitans cav_archer Castle: resolver Heavy Cav Archer 474 via tech 218
      OR-slot [103, 192, 1004] cnt=2 (1004 = Khitans-bound shadow) — a real
      civ bonus the config age-gating cannot express (ref pins CA 39);
    Cumans ram Castle: Capped Ram 422 via tech 96 [103, 706] cnt=1
      (706 = Cumans-bound shadow) — real Cumans bonus, same class;
    Armenians pikeman + swordsmen Castle: Halberdier 359 / Champion 567 via
      techs 429/264 Armenian OR-slots (956/954) — "infantry upgrades one age
      earlier", same class;
    Wei champion Imperial: resolver reaches Champion 567 via tech 1174
      (Paphos Champion variant; Wei does not 102-disable 1138 Paphos Shadow
      Tech) — Chronicles mode-gating is also outside the dat;
    Vietnamese imp_elite_skirm Imperial: resolver Elite Skirm 6 — tech 656
      auto-disables Imperial Skirmisher 655 at Castle for everyone; the
      Vietnamese grant lives in CivTechTrees JSON.

What the resolver DOES get right (2,050 rows, kept green below): every
default-roster line and tier across all 53 civs (knight/militia/spear/archer/
skirm/scout/CA/siege/HC/BBC gating via tech-tree 102-disables), Burgundians
Castle-age Cavalier, the Winged Hussar OR-slot derivation, and the early-tier
civ bonuses listed above.
"""

import pytest

from analysis.availability_resolver import AvailabilityResolver, build_report

# ---------------------------------------------------------------------------
# Pinned report (2026-06-10, build 177723). Regenerate the literals with:
#   python -m analysis.availability_resolver
# ---------------------------------------------------------------------------
EXPECTED_TOTAL = 2332
EXPECTED_AGREE = 2050

EXPECTED_MISMATCHES = {
    ("camel", "Castle", "missing"): ["Berbers", "Byzantines", "Cumans", "Ethiopians", "Gurjaras", "Hindustanis", "Khitans", "Malians", "Mongols", "Persians", "Saracens", "Tatars", "Turks"],
    ("cav_archer", "Castle", "tier"): ["Khitans"],
    ("champi_warrior", "Castle", "missing"): ["Incas", "Mapuche", "Muisca", "Tupi"],
    ("champion", "Imperial", "missing"): ["Incas", "Mapuche", "Muisca", "Tupi"],
    ("champion", "Imperial", "tier"): ["Wei"],
    ("condottiero", "Imperial", "phantom"): ["Armenians", "Aztecs", "Bengalis", "Berbers", "Bohemians", "Britons", "Bulgarians", "Burgundians", "Burmese", "Byzantines", "Celts", "Chinese", "Cumans", "Dravidians", "Ethiopians", "Franks", "Georgians", "Goths", "Gurjaras", "Hindustanis", "Huns", "Incas", "Japanese", "Jurchens", "Khitans", "Khmer", "Koreans", "Lithuanians", "Magyars", "Malay", "Malians", "Mapuche", "Mayans", "Mongols", "Muisca", "Persians", "Poles", "Portuguese", "Romans", "Saracens", "Shu", "Sicilians", "Slavs", "Spanish", "Tatars", "Teutons", "Tupi", "Turks", "Vietnamese", "Vikings", "Wei", "Wu"],
    ("eagle_warrior", "Castle", "missing"): ["Aztecs", "Mayans"],
    ("elephant", "Castle", "missing"): ["Bengalis", "Burmese", "Dravidians", "Khmer", "Malay", "Vietnamese"],
    ("elephant_archer", "Castle", "missing"): ["Bengalis", "Dravidians", "Gurjaras"],
    ("elite_champi_warrior", "Imperial", "missing"): ["Incas", "Mapuche", "Muisca", "Tupi"],
    ("elite_eagle", "Imperial", "missing"): ["Aztecs", "Mayans"],
    ("elite_ele_archer", "Imperial", "missing"): ["Bengalis", "Dravidians", "Gurjaras"],
    ("elite_elephant", "Imperial", "missing"): ["Bengalis", "Burmese", "Dravidians", "Khmer", "Malay", "Vietnamese"],
    ("elite_fire_lancer", "Imperial", "missing"): ["Chinese", "Jurchens", "Khitans", "Koreans", "Vietnamese"],
    ("elite_genitour", "Imperial", "phantom"): ["Armenians", "Aztecs", "Bengalis", "Bohemians", "Britons", "Bulgarians", "Burgundians", "Burmese", "Byzantines", "Celts", "Chinese", "Cumans", "Dravidians", "Ethiopians", "Franks", "Georgians", "Goths", "Gurjaras", "Hindustanis", "Huns", "Incas", "Italians", "Japanese", "Jurchens", "Khitans", "Khmer", "Koreans", "Lithuanians", "Magyars", "Malay", "Malians", "Mapuche", "Mayans", "Mongols", "Muisca", "Persians", "Poles", "Portuguese", "Romans", "Saracens", "Shu", "Sicilians", "Slavs", "Spanish", "Tatars", "Teutons", "Tupi", "Turks", "Vietnamese", "Vikings", "Wei", "Wu"],
    ("elite_steppe", "Imperial", "missing"): ["Cumans", "Jurchens", "Khitans", "Mongols", "Tatars"],
    ("fire_lancer", "Castle", "missing"): ["Chinese", "Jurchens", "Khitans", "Koreans", "Vietnamese"],
    ("flemish_militia", "Imperial", "missing"): ["Burgundians"],
    ("genitour", "Castle", "phantom"): ["Armenians", "Aztecs", "Bengalis", "Bohemians", "Britons", "Bulgarians", "Burgundians", "Burmese", "Byzantines", "Celts", "Chinese", "Cumans", "Dravidians", "Ethiopians", "Franks", "Georgians", "Goths", "Gurjaras", "Hindustanis", "Huns", "Incas", "Italians", "Japanese", "Jurchens", "Khitans", "Khmer", "Koreans", "Lithuanians", "Magyars", "Malay", "Malians", "Mapuche", "Mayans", "Mongols", "Muisca", "Persians", "Poles", "Portuguese", "Romans", "Saracens", "Shu", "Sicilians", "Slavs", "Spanish", "Tatars", "Teutons", "Tupi", "Turks", "Vietnamese", "Vikings", "Wei", "Wu"],
    ("heavy_camel", "Imperial", "missing"): ["Berbers", "Byzantines", "Cumans", "Ethiopians", "Gurjaras", "Hindustanis", "Khitans", "Malians", "Mongols", "Persians", "Saracens", "Tatars", "Turks"],
    ("heavy_scorpion", "Imperial", "missing"): ["Shu"],
    ("imp_elite_skirm", "Imperial", "tier"): ["Vietnamese"],
    ("imp_slinger", "Imperial", "missing"): ["Incas", "Mapuche", "Muisca", "Tupi"],
    ("mangonel", "Castle", "missing"): ["Chinese", "Jurchens", "Khitans", "Koreans"],
    ("paladin", "Imperial", "missing"): ["Shu", "Wei", "Wu"],
    ("pikeman", "Castle", "tier"): ["Armenians"],
    ("ram", "Castle", "missing"): ["Bengalis", "Dravidians", "Gurjaras", "Hindustanis"],
    ("ram", "Castle", "tier"): ["Cumans"],
    ("scorpion", "Castle", "missing"): ["Shu"],
    ("siege_onager", "Imperial", "missing"): ["Chinese", "Jurchens", "Khitans", "Koreans"],
    ("siege_ram", "Imperial", "missing"): ["Bengalis", "Dravidians", "Gurjaras", "Hindustanis"],
    ("slinger", "Castle", "missing"): ["Incas", "Mapuche", "Muisca", "Tupi"],
    ("steppe_lancer", "Castle", "missing"): ["Cumans", "Jurchens", "Khitans", "Mongols", "Tatars"],
    ("swordsmen", "Castle", "missing"): ["Incas", "Mapuche", "Muisca", "Tupi"],
    ("swordsmen", "Castle", "tier"): ["Armenians"],
    ("traction_trebuchet", "Imperial", "missing"): ["Shu", "Wei", "Wu"],
    ("trebuchet", "Imperial", "missing"): ["Shu", "Wei", "Wu"],
}


@pytest.fixture(scope="module")
def resolver():
    return AvailabilityResolver()


@pytest.fixture(scope="module")
def report(resolver):
    return build_report(resolver)


def test_report_totals_and_clean_run(report):
    """The report covers every (civ, slug, age) cell exactly once, with no
    unmappable ref names and no fixed-point anomalies."""
    assert report["total"] == EXPECTED_TOTAL
    assert report["agree"] + report["mismatch_count"] == report["total"]
    assert report["warnings"] == []


@pytest.mark.xfail(
    reason="282 mismatches (2026-06-10): empires2_x2_p1.dat does not encode "
    "per-civ regional availability — tech 79 'Disable Regionals' locks all "
    "regional lines in normal games and the per-civ grants live in the "
    "game's CivTechTrees/<CIV>.json, outside the dat. Swap gate per Phase B "
    "decision rule: requires exactly 0. See module docstring and "
    "data-model-review.md section 3.1.",
    strict=False,
)
def test_resolver_matches_committed_rosters_exactly(report):
    """THE PHASE B GATE: resolver == committed ref DB rosters, 0 mismatches."""
    assert report["mismatch_count"] == 0, (
        f"{report['mismatch_count']} mismatches; first 10: "
        f"{report['mismatches'][:10]}"
    )


def test_mismatches_are_exactly_the_documented_282(report):
    """Regression pin: the mismatch set is frozen as documented above.

    Any drift (new dat extraction, resolver edit, ref regen) must update this
    pin consciously — a NEW kind of disagreement is a bug in one of the three
    (resolver, extraction, ref DB) and needs investigation, not a re-pin.
    """
    got = {}
    for mm in report["mismatches"]:
        got.setdefault((mm["slug"], mm["age"], mm["kind"]), []).append(mm["civ"])
    got = {key: sorted(civs) for key, civs in got.items()}
    assert got == EXPECTED_MISMATCHES
    assert report["mismatch_count"] == sum(len(v) for v in EXPECTED_MISMATCHES.values())
    assert report["agree"] == EXPECTED_AGREE


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
    config age-gating cannot express (these are 4 of the 6 'tier' rows)."""
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
    NotAvailable for Incas) — the committed ref DB rows are the outliers."""
    for civ in ("Incas", "Muisca", "Mapuche", "Tupi"):
        assert resolver.resolve(civ, 4).line_status([74, 75]) == (False, None)
    assert resolver.resolve("Aztecs", 4).line_status([74, 75]) == (True, 567)

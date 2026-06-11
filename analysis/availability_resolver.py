"""Tech-tree availability resolver over the extracted dat JSONs — REPORT MODE.

Fixed-point resolution of per-civ unit availability from the extracted dat
facts alone (technologies.json required_techs/required_tech_count/civ,
tech_effects.json type-2/3/102 commands, civ_tech_trees.json disables),
modelling a NORMAL (non-Full-Tech-Tree) game at fully-upgraded state.

Status (2026-06-10, build 177723): REPORT MODE ONLY — generate_reference does
NOT consult this module. The report (``python -m analysis.availability_resolver``)
shows the resolver cannot reproduce the committed rosters, because the dat
itself does not encode per-civ availability for the "regional" lines:

* Tech 79 "Disable Regionals" (civ=-1, no prereqs, full_tech_mode=0) fires for
  EVERY civ at game start and 102-disables all regional make-avail/upgrade
  techs (camel 235/236, battle elephant 630/631, eagle 433/384/434, steppe
  lancer 714/715, slinger 528, fire lancer 981/982, elephant archer 480/481,
  armored elephant 837/838, rocket cart 979/980, hei-kuang 1032/1033, champi
  1350/1351/1352/1402, traction treb 1025, lou chuan 1034, dromon 886, ...).
* The only in-dat counter is tech 78 "[FTT] Enable Regionals" with
  full_tech_mode == -1 — the Full-Tech-Tree-only marker — so in normal games
  nothing re-enables them.
* The per-civ regional grants live OUTSIDE the dat, in the game's shipped
  per-civ tech-tree JSONs (``resources/_common/dat/CivTechTrees/<CIV>.json``,
  e.g. Berbers' file carries node 329 "Camel Rider" / Node Type
  "RegionalUnit" / Node Status "ResearchedCompleted"). aoe2techtree.net's
  data generator reads exactly those files — it does not resolve the dat.

What the resolver DOES derive correctly from the dat (verified by the report):
default-roster lines and their per-civ top tiers (knight/militia/spear/archer/
skirm/scout/cavalry-archer/siege/hand-cannoneer/bombard-cannon gating via the
civ tech-tree 102-disables), the Winged Hussar OR-slot pattern (tech 786
requires 3 of [115, 254, 788, 789] where 788/789 are civ-bound layer-0 shadow
techs that also dynamically disable Hussar 428), the Imperial Skirmisher
auto-disable (tech 656 fires at Castle off Elite Skirmisher and kills 655
before its Imperial eligibility), and the four American civs' militia-line
removal (tech-tree type-2 disable of unit 74).

Mechanics implemented:
* A tech fires when: not 102-disabled (statically by the civ tech tree or
  dynamically by an earlier-fired tech), its ``civ`` field is -1 or this civ,
  ``full_tech_mode != -1`` (-1 marks Full-Tech-Tree-only techs like 78/121/717),
  and at least ``required_tech_count`` of its listed ``required_techs`` have
  fired (count<=0 means ALL listed; count > len(listed) is unreachable —
  the dat uses that for event/building markers such as 266 "Castle built").
* Research is assumed: researchable techs (research_location >= 0) fire under
  the same rule as shadow techs — we model fully-upgraded availability.
* Age techs (104/101/102/103) are SEEDED phase by phase up to the requested
  age cap, never derived from their own prereq chains (those chains run
  through building-construction event markers that never fire from the graph).
  Phase staging preserves the in-game temporal order that makes the 655/656
  Imperial Skirmisher interlock resolve correctly.
* Within a phase, eligible techs fire in ascending tech-id order, applying
  effect commands as they fire: type 102 grows the disabled set (mutually
  exclusive C-bonus pairs like Mongols 286/288 resolve deterministically),
  type 2 enables/disables units, type 3 records upgrade edges in fire order.
* The enabled-unit seed is DEFAULT_ENABLED_UNIT_IDS (probed from the dat's
  per-civ unit tables: identical for all 53 civs). Tech-tree type-2 disables
  (e.g. unit 74 Militia for Incas/Muisca/Mapuche/Tupi) are permanent: fired
  enables cannot override them.
* A line's top tier = walk the fire-ordered upgrade edges from each enabled
  root unit (genie type-3 upgrades persist, so edges fired before an enable
  still apply).

Loading reuses UnitAnalyzer's loaders (same JSONs, same civ-name mapping).
"""

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from .unit_analyzer import UnitAnalyzer

# Dark -> Feudal -> Castle -> Imperial. Numeric age values match the rest of
# the pipeline (1=Dark .. 4=Imperial, see analysis.config AGE_TECH_IDS).
AGE_PHASES = ((1, 104), (2, 101), (3, 102), (4, 103))
AGE_PHASE_TECH_IDS = {tid for _, tid in AGE_PHASES}

# Units enabled by default in the dat's per-civ unit tables (unit.enabled == 1,
# restricted to ids present in extraction/extracted_data/units.json). Probed
# from empires2_x2_p1.dat build 177723 with genieutils: identical for all 53
# extracted civs. units.json does not carry the ``enabled`` flag, so the seed
# is pinned here with provenance; re-probe when the dat updates.
# 74 = Militia (the only combat line trainable with no enabling tech),
# 545 = Transport Ship.
DEFAULT_ENABLED_UNIT_IDS = frozenset({74, 545})

# The Trebuchet's trainable form in the dat is unit 331 (packed); tech 256
# enables 331, while the pipeline's config/ref rows use the unpacked twin 42.
# This is a structural pack/unpack pairing in the dat, not an upgrade edge.
TREBUCHET_UNPACKED_ID = 42
TREBUCHET_PACKED_ID = 331

_REF_DB_DEFAULT = Path(__file__).parent.parent / "webapp" / "aoe2_reference.db"


@dataclass
class Resolution:
    """Fixed-point result for one (civ, age cap)."""

    civ_name: str
    max_age: int
    fired: set = field(default_factory=set)
    disabled: set = field(default_factory=set)
    enabled_units: set = field(default_factory=set)
    upgrade_edges: list = field(default_factory=list)  # (from_unit, to_unit) in fire order
    warnings: list = field(default_factory=list)
    _chain_terminal: dict = field(default=None, repr=False)

    def chain_terminal(self) -> dict:
        """Map every unit id reachable from an enabled root to its top tier."""
        if self._chain_terminal is None:
            terminal = {}
            for root in sorted(self.enabled_units):
                cur = root
                visited = [root]
                for from_u, to_u in self.upgrade_edges:
                    if from_u == cur:
                        cur = to_u
                        visited.append(to_u)
                for vid in visited:
                    terminal.setdefault(vid, cur)
            self._chain_terminal = terminal
        return self._chain_terminal

    def line_status(self, base_ids):
        """(present, top_tier_unit_id) for the first known base id of a line."""
        terminal = self.chain_terminal()
        for base_id in base_ids:
            if base_id in terminal:
                return True, terminal[base_id]
        return False, None


class AvailabilityResolver:
    """Pure resolver over the extracted JSONs (no config_units curation)."""

    def __init__(self, analyzer: UnitAnalyzer = None):
        # Reuse UnitAnalyzer's loaders: techs, tech_effect_map, civ_tech_trees,
        # effects, civ_name_to_id all come from the same extracted JSONs the
        # rest of the analysis stage consumes.
        self.analyzer = analyzer or UnitAnalyzer()
        self.techs = self.analyzer.techs
        self.tech_effect_map = self.analyzer.tech_effect_map
        self.civ_tech_trees = self.analyzer.civ_tech_trees
        self.civ_name_to_id = self.analyzer.civ_name_to_id
        self.effects = self.analyzer.effects
        self._resolution_cache = {}

    # ------------------------------------------------------------------
    # tech-tree effect ingestion
    # ------------------------------------------------------------------
    def _tech_tree_unit_commands(self, civ_name):
        """(hard_disabled_units, tree_enabled_units) from the civ tech-tree
        effect's type-2 commands. Type 101/103 commands in tech-tree effects
        are tech COST/TIME modifiers (free techs like Franks' farm upgrades),
        not availability signals — the mislabelled ``disabled_units`` list in
        civ_tech_trees.json (built from type-103) is intentionally ignored."""
        hard_disabled = set()
        tree_enabled = set()
        civ_data = self.civ_tech_trees.get(civ_name, {})
        eff = self.effects.get(civ_data.get("tech_tree_effect_id"))
        for cmd in (eff or {}).get("commands", []):
            if cmd["type"] == 2:
                if cmd["b"] == 1:
                    tree_enabled.add(cmd["a"])
                else:
                    hard_disabled.add(cmd["a"])
        return hard_disabled, tree_enabled

    # ------------------------------------------------------------------
    # fixed point
    # ------------------------------------------------------------------
    def resolve(self, civ_name: str, max_age: int = 4) -> Resolution:
        key = (civ_name, max_age)
        if key in self._resolution_cache:
            return self._resolution_cache[key]

        civ_id = self.civ_name_to_id.get(civ_name, -1)
        res = Resolution(civ_name=civ_name, max_age=max_age)
        res.disabled = set(self.analyzer.get_disabled_techs(civ_name))
        hard_disabled_units, tree_enabled = self._tech_tree_unit_commands(civ_name)
        res.enabled_units = (set(DEFAULT_ENABLED_UNIT_IDS) | tree_enabled) - hard_disabled_units

        def apply_effects(tech_id):
            te = self.tech_effect_map.get(tech_id)
            for cmd in (te or {}).get("commands", []):
                ctype = cmd["type"]
                if ctype == 102:
                    target = int(cmd["d"])
                    if target in res.fired:
                        res.warnings.append(
                            f"tech {tech_id} disables already-fired tech {target} (kept fired)"
                        )
                    res.disabled.add(target)
                elif ctype == 2:
                    unit_id = cmd["a"]
                    if cmd["b"] == 1:
                        if unit_id not in hard_disabled_units:
                            res.enabled_units.add(unit_id)
                    else:
                        res.enabled_units.discard(unit_id)
                elif ctype == 3:
                    res.upgrade_edges.append((cmd["a"], cmd["b"]))

        def eligible(tech_id, tech):
            if tech_id in res.fired or tech_id in res.disabled:
                return False
            if tech_id in AGE_PHASE_TECH_IDS:
                return False  # ages are seeded, never derived
            if tech.get("full_tech_mode", 0) == -1:
                return False  # Full-Tech-Tree-only techs never fire in normal games
            tech_civ = tech.get("civ", -1)
            if tech_civ not in (-1, civ_id):
                return False
            listed = tech.get("required_techs") or []
            count = tech.get("required_tech_count", 0)
            satisfied = sum(1 for req in listed if req in res.fired)
            if count <= 0:
                return satisfied == len(listed)
            return satisfied >= count

        for age_num, age_tech_id in AGE_PHASES:
            if age_num > max_age:
                break
            if age_tech_id in res.disabled:
                res.warnings.append(f"age tech {age_tech_id} disabled for {civ_name}")
                break
            res.fired.add(age_tech_id)
            apply_effects(age_tech_id)
            while True:
                batch = sorted(
                    tech_id
                    for tech_id, tech in self.techs.items()
                    if eligible(tech_id, tech)
                )
                progressed = False
                for tech_id in batch:
                    # an earlier fire in this batch may have disabled it
                    if tech_id in res.disabled or tech_id in res.fired:
                        continue
                    res.fired.add(tech_id)
                    apply_effects(tech_id)
                    progressed = True
                if not progressed:
                    break

        self._resolution_cache[key] = res
        return res


# ----------------------------------------------------------------------
# REPORT MODE: resolver output vs the committed reference DB rosters and
# the curated _AVAILABILITY_OVERRIDES lists (SiegeEngineers-sourced truth).
# ----------------------------------------------------------------------
def _config_name_to_id(config):
    """Every display name a ref row for this line config can carry -> unit id."""
    from .config import _PREVIOUS_AGE_NAMES

    mapping = {config["display_name"]: config["base_id"]}
    prev = _PREVIOUS_AGE_NAMES.get(config["base_id"])
    if prev:
        mapping.setdefault(prev, config["base_id"])
    for tech_id, unit_id, name in config.get("upgrades", []):
        mapping[name] = unit_id
    for upgrades in config.get("civ_upgrades", {}).values():
        for tech_id, unit_id, name in upgrades:
            mapping[name] = unit_id
    alt = config.get("alternate")
    if alt:
        mapping[alt["display_name"]] = alt["base_id"]
        prev = _PREVIOUS_AGE_NAMES.get(alt["base_id"])
        if prev:
            mapping.setdefault(prev, alt["base_id"])
        for tech_id, unit_id, name in alt.get("upgrades", []):
            mapping[name] = unit_id
    return mapping


def _line_candidate_ids(config):
    candidates = [config["base_id"]]
    alt = config.get("alternate")
    if alt:
        candidates.append(alt["base_id"])
    if config["base_id"] == TREBUCHET_UNPACKED_ID:
        candidates.append(TREBUCHET_PACKED_ID)
    return candidates


def build_report(resolver: AvailabilityResolver = None, ref_db_path=_REF_DB_DEFAULT):
    """Compare resolver output against ref DB standard rosters + overrides.

    Returns a dict:
      total/agree counts, mismatches (list of dicts with civ/slug/age/kind/
      expected/got), overrides {slug: {curated, resolver, match}}, warnings.
    Mismatch kinds: 'missing'  ref has the row, resolver denies the line
                    'phantom'  resolver grants a line the ref DB lacks
                    'tier'     both present but at different top tiers
    """
    from .config_constants import ORIGINAL_13_CIVS
    from .config_units import CASTLE_UNITS, IMPERIAL_UNITS, _AVAILABILITY_OVERRIDES

    resolver = resolver or AvailabilityResolver()

    conn = sqlite3.connect(ref_db_path)
    ref_rows = {
        (civ, slug, age): name
        for civ, slug, age, name in conn.execute(
            "SELECT civ_name, unit_slug, age, unit_name FROM ref_units "
            "WHERE unit_type='standard'"
        )
    }
    conn.close()

    civs = list(ORIGINAL_13_CIVS)
    total = 0
    agree = 0
    mismatches = []
    warnings = []

    age_blocks = (("Castle", 3, CASTLE_UNITS), ("Imperial", 4, IMPERIAL_UNITS))
    for age_label, age_num, config_map in age_blocks:
        for slug in sorted(config_map):
            config = config_map[slug]
            name_to_id = _config_name_to_id(config)
            candidates = _line_candidate_ids(config)
            for civ in civs:
                total += 1
                res = resolver.resolve(civ, max_age=age_num)
                got_present, got_tier = res.line_status(candidates)
                if got_tier == TREBUCHET_PACKED_ID:
                    got_tier = TREBUCHET_UNPACKED_ID  # report the unpacked twin
                ref_name = ref_rows.get((civ, slug, age_label))
                exp_present = ref_name is not None
                exp_tier = name_to_id.get(ref_name) if exp_present else None
                if exp_present and exp_tier is None:
                    warnings.append(
                        f"unmappable ref unit_name {ref_name!r} for ({civ}, {slug}, {age_label})"
                    )
                    continue
                if exp_present != got_present:
                    mismatches.append(
                        {
                            "civ": civ,
                            "slug": slug,
                            "age": age_label,
                            "kind": "missing" if exp_present else "phantom",
                            "expected": ref_name,
                            "got": got_tier,
                        }
                    )
                elif exp_present and exp_tier != got_tier:
                    mismatches.append(
                        {
                            "civ": civ,
                            "slug": slug,
                            "age": age_label,
                            "kind": "tier",
                            "expected": f"{ref_name} ({exp_tier})",
                            "got": got_tier,
                        }
                    )
                else:
                    agree += 1

    # The 17 curated allowlists (SiegeEngineers truth) vs resolver line presence.
    overrides = {}
    for slug, curated in _AVAILABILITY_OVERRIDES.items():
        for age_label, age_num, config_map in age_blocks:
            if slug not in config_map:
                continue
            config = config_map[slug]
            candidates = _line_candidate_ids(config)
            resolver_civs = [
                civ
                for civ in civs
                if resolver.resolve(civ, max_age=age_num).line_status(candidates)[0]
            ]
            overrides[slug] = {
                "age": age_label,
                "curated": sorted(curated),
                "resolver": sorted(resolver_civs),
                "match": sorted(curated) == sorted(resolver_civs),
            }

    return {
        "total": total,
        "agree": agree,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "overrides": overrides,
        "warnings": warnings,
    }


def main():
    report = build_report()
    print(f"rows compared: {report['total']}")
    print(f"agree:         {report['agree']}")
    print(f"mismatches:    {report['mismatch_count']}")
    by_slug = {}
    for mm in report["mismatches"]:
        by_slug.setdefault((mm["slug"], mm["age"], mm["kind"]), []).append(mm["civ"])
    for (slug, age, kind), civ_list in sorted(by_slug.items()):
        print(f"  {slug:22} {age:8} {kind:8} x{len(civ_list):2}: {', '.join(civ_list)}")
    print("\noverride-list comparison (curated SiegeEngineers truth vs resolver):")
    for slug, cmp in sorted(report["overrides"].items()):
        status = "MATCH" if cmp["match"] else "DIFFER"
        print(f"  {slug:22} {cmp['age']:8} {status}")
        if not cmp["match"]:
            curated = set(cmp["curated"])
            got = set(cmp["resolver"])
            if curated - got:
                print(f"    curated-only: {', '.join(sorted(curated - got))}")
            if got - curated:
                print(f"    resolver-only: {', '.join(sorted(got - curated))}")
    if report["warnings"]:
        print("\nwarnings:")
        for w in report["warnings"]:
            print(f"  {w}")


if __name__ == "__main__":
    main()

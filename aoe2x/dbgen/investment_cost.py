"""Total investment cost — what it really costs to field one fully-upgraded unit.

``ref_units.upgrade_cost_*`` already sums every tech that MODIFIED the unit's stats
(Forging, Bracer, Husbandry, Thumb Ring, the unique techs...). Two kinds of spending it
misses, both unavoidable for the player:

  * **the unit-line upgrade research itself** — Crossbowman + Arbalester before you can
    train an Arbalester, Long Swordsman + Two-Handed + Champion before a Champion, the
    Elite <UU> upgrade for a unique unit. These ENABLE the unit rather than restat an
    existing one, so no stat-chain step ever records them.
  * **Ballistics**, which changes no stat at all (it makes projectiles lead a moving
    target) and so can never appear in a stat chain — but is not optional for a
    projectile unit.

Everything here runs through ``analyzer.get_modified_tech_cost``, so per-civ tech
discounts and free-tech civ bonuses (TECH_COST_SET / RESEARCH_COST_MOD effects) apply to
the upgrade path exactly as they already do to the stat techs.

Why this matters: an infantry line is cheap to tech into and an archer or cavalry-archer
line is not, and the per-unit train cost alone hides that completely. A Champion's train
cost is 60 resources; getting to Champion costs ~3,600 more.
"""

from .config_units import (
    CASTLE_UNITS,
    FEUDAL_UNITS,
    IMPERIAL_UNITS,
    NAVAL_LINE_CONFIGS,
)

# Ballistics (University, Castle Age): no stat change, so it is invisible to the stat
# chain, but every projectile unit needs it.
BALLISTICS_TECH_ID = 93


def _predecessor_map():
    """{upgraded_unit_id: (tech_id, from_unit_id)} across every age's line configs.

    Each age's config only lists the upgrades reachable IN that age, and an Imperial
    config starts from wherever the Castle line left off (the ``champion`` line's
    base_id is the Man-at-Arms, not the Militia). Walking this map backwards from a
    base_id recovers the earlier-age steps the player still had to pay for.
    """
    pred = {}
    for cfgs in (FEUDAL_UNITS, CASTLE_UNITS, IMPERIAL_UNITS, NAVAL_LINE_CONFIGS):
        for cfg in cfgs.values():
            frm = cfg.get("base_id")
            for tech_id, to_id, _name in cfg.get("upgrades", []):
                if to_id is not None and frm is not None:
                    pred[to_id] = (tech_id, frm)
                frm = to_id
    return pred


_PRED = _predecessor_map()


def line_path_techs(config):
    """Tech ids needed to field the top of a standard line: the enabling tech, any
    earlier-age upgrade steps below this config's base unit, then this config's own
    upgrade chain — in the order the player researches them."""
    techs, seen = [], set()

    def add(t):
        if t and t not in seen:
            seen.add(t)
            techs.append(t)

    earlier, cur, guard = [], config.get("base_id"), 0
    while cur in _PRED and guard < 12:                  # guard: never trust a cycle
        tech_id, frm = _PRED[cur]
        earlier.append(tech_id)
        cur, guard = frm, guard + 1
    add(config.get("availability_tech"))
    for t in reversed(earlier):                         # oldest age first
        add(t)
    for tech_id, _to, _name in config.get("upgrades", []):
        add(tech_id)
    return techs


def unique_path_techs(uu_config, *, elite: bool):
    """Tech ids for a unique unit: the make-available tech (usually free — the Castle
    unlocks it) plus, for the elite form, the Elite upgrade."""
    techs = [t for t in (uu_config.get("availability_tech"),) if t]
    if elite and uu_config.get("elite_tech"):
        techs.append(uu_config["elite_tech"])
    return techs


def path_cost(analyzer, civ_name, tech_ids, *, exclude_tech_ids=()):
    """Sum (food, wood, gold) for `tech_ids` under `civ_name`, honouring civ tech-cost
    overrides. `exclude_tech_ids` drops anything already counted elsewhere (the stat
    techs in ref_techs_applied) so nothing is paid for twice.

    Returns (food, wood, gold, rows) where rows is the audit trail:
    [(tech_id, tech_name, food, wood, gold)].
    """
    exclude = set(exclude_tech_ids or ())
    total = [0, 0, 0]
    rows = []
    for tech_id in tech_ids:
        if tech_id in exclude:
            continue
        tech = analyzer.techs.get(tech_id) or {}
        cost = tech.get("cost") or {}
        f, w, g = (cost.get("food", 0) or 0, cost.get("wood", 0) or 0,
                   cost.get("gold", 0) or 0)
        modified = analyzer.get_modified_tech_cost(civ_name, tech_id)
        if modified is not None:
            f, w, g = modified
        if not (f or w or g):                # free enabling techs add nothing but noise
            continue
        total[0] += f
        total[1] += w
        total[2] += g
        rows.append((tech_id, tech.get("name") or f"tech {tech_id}", f, w, g))
    return total[0], total[1], total[2], rows

"""Role: declaration — the single source of truth for special-ability properties.

Phase A of the ability-model redesign (docs/architecture/data-model-review.md
§3.2/§3.5): every special-ability property that flows through the pipeline is
DECLARED here, grouped into abilities and families, and validated by
tests/test_ability_registry.py against the four places it currently lives:

    analysis/config_combat.py          (curated values)
    analysis/generate_reference.py     (ref_units columns + writer)
    webapp/combat_unit_loader.py       (the serving combat dict)
    the three engines (simulation.py / simulation_real.py / static/js/simulate.js)

Phase A is purely additive: nothing imports this module on the serving path
yet. Phase B (pending) will generate the loader mapping, prepare_combat_unit
defaults, and a JS manifest FROM this registry. Until then the tests keep the
hand-maintained chain honest.

Scope notes
-----------
* Params map 1:1 to combat-dict keys (``Param.name``) and, where stored, to a
  ``ref_units`` column (``Param.ref_column`` — defaults to the param name;
  ``None`` = not stored, e.g. generation-time-only inputs like
  ``transform_unit_id``).
* ``accuracy`` / ``base_accuracy`` / ``outline_size`` are deliberately NOT
  registry entries — they are base/geometry stat columns
  (``final_accuracy`` / ``base_accuracy`` / ``outline_size_x``), not special
  abilities. base_accuracy's role in volley mechanics is documented in the
  ``extra_projectiles`` quirks instead.
* ``engines`` records which engine IMPLEMENTS the behavior (verified by
  reading the engine code, not by assumption). Parsing-without-use does not
  count (e.g. simulation.py parses ``hp_regen_in_combat`` and
  ``charge_projectile_speed`` but never acts on them).
* Sources:
    ``dat:<rule>``                          decoded from the extracted dat by
                                            combat_properties.get_extracted_combat_properties()
    ``curated:COMBAT_PROPERTIES``           hardcoded, standard-unit dict
    ``curated:UNIQUE_COMBAT_PROPERTIES``    hardcoded, unique-unit dict
    ``curated:CIV_COMBAT_PROPERTIES``       hardcoded, civ-conditional dict
    ``curated:PAIRED_UNITS``                hardcoded in analysis/config_units.py
    ``derived:form_tech_chain``             multi-form stat blocks derived at
                                            generation time (commit bcdbcbc):
                                            analyzer.calculate_form_stats() runs the
                                            form's dat unit through the full tech chain
    ``schema:default-only``                 column exists but no producer sets it today
  A ``+``-joined source means several producers layer onto the same param
  (later wins, per combat_properties.get_combat_properties()).
"""

from dataclasses import dataclass

ENGINE_ABSTRACT = "abstract"   # webapp/simulation.py        (tick, no positions)
ENGINE_POSITION = "position"   # webapp/simulation_real.py   (2D, batch matchup data)
ENGINE_JS = "js"               # webapp/static/js/simulate.js (interactive page)

ALL_ENGINES = (ENGINE_ABSTRACT, ENGINE_POSITION, ENGINE_JS)

FAMILIES = (
    "projectile_volley",
    "area_damage",
    "charge",
    "damage_over_time",
    "on_kill",
    "armor_interaction",
    "defensive",
    "aura",
    "form_change",
    "tempo",
    "misc",
)

# Sentinel: ref_column defaults to the param name.
_SAME = "__same_as_name__"


@dataclass(frozen=True)
class Param:
    """One scalar/JSON property of an ability.

    name          combat-dict key (and ref_units column unless ref_column set)
    type          python type of the stored value
    default       neutral value (must match prepare_combat_unit where both define one)
    ref_column    ref_units column name; _SAME -> name; None -> not stored in ref_units
    engines       per-param override of the ability's engines (None -> inherit)
    in_combat_dict  True if combat_unit_loader.build_combat_dict_from_ref emits it
    quirks        param-level deviations worth knowing
    """

    name: str
    type: type
    default: object
    ref_column: str = _SAME
    engines: tuple = None
    in_combat_dict: bool = True
    quirks: str = ""

    @property
    def column(self):
        return self.name if self.ref_column == _SAME else self.ref_column


@dataclass(frozen=True)
class Ability:
    """One special ability: a named group of params with shared semantics."""

    name: str
    family: str
    params: tuple
    source: str
    engines: tuple
    description: str
    quirks: str = ""

    def param_engines(self, param):
        """Effective engine set for a param (param override wins)."""
        return self.engines if param.engines is None else param.engines


def _p(name, type_, default, **kw):
    return Param(name, type_, default, **kw)


ABILITIES = {
    # ------------------------------------------------------------------
    # projectile_volley — multiple projectiles per attack command
    # ------------------------------------------------------------------
    "extra_projectiles": Ability(
        name="extra_projectiles",
        family="projectile_volley",
        params=(
            _p("extra_projectiles", int, 0),
            _p("extra_projectile_attacks_json", str, None,
               engines=(ENGINE_ABSTRACT, ENGINE_POSITION),
               quirks="JS never parses it: frontend extras always deal the "
                      "PRIMARY damage profile (over-states Chu Ko Nu/Kipchak "
                      "extras client-side)."),
        ),
        source="dat:total_projectiles-1 (charge_type==6 uses max_total_projectiles-1) "
               "+ dat:secondary_projectile_attacks "
               "+ curated:UNIQUE_COMBAT_PROPERTIES + curated:CIV_COMBAT_PROPERTIES",
        engines=ALL_ENGINES,
        description="Sustained volley: N extra projectiles on every attack "
                    "(Chu Ko Nu, Kipchak, Organ Gun, War Chariot, Shu Bolt "
                    "Magazine, Mayan Hul'che, Jurchen Thunderclap Bombs, Wu "
                    "Fire Archer).",
        quirks=(
            "ACCURACY: extras roll the unit's base_accuracy (pre-Thumb-Ring; "
            "TR is a primary-only bonus) in all three engines — Chu Ko Nu "
            "primary 100 (final) vs extras 85 (base). simulation.py's "
            "EXTRA_PROJ_ACCURACY=0.85 is only the legacy default in helper "
            "signatures (s.EXTRA_PROJ_ACCURACY / a_extra_accuracy=0.85); every "
            "live call site passes the per-side base_accuracy, so 0.85 is dead "
            "in practice. The JS contract is pinned by the 'isExtra uses "
            "baseAccuracy' test in tests/test_frontend_projectile_miss.js. "
            "In simulation.py, extras of scatter or pass-through units skip "
            "the roll entirely and always land. "
            "SECONDARY DAMAGE: Chu Ko Nu extras carry {3:3} vs primary 8; "
            "Kipchak extras {3:3}. Organ Gun rows have extra_projectile_"
            "attacks_json NULL (dat secondary attacks not present for it), so "
            "its extras reuse the primary profile; Organ Gun also has dat "
            "accuracy 0/0 (final/base) — its abstract-engine output rides on "
            "scatter extras (always land) and miss-graze elsewhere. "
            "Chu Ko Nu has NO modeled first-shot/sustained distinction: "
            "first_attack_extra_projectiles is Xianbei-only in the current DB."
        ),
    ),
    "first_attack_burst": Ability(
        name="first_attack_burst",
        family="projectile_volley",
        params=(_p("first_attack_extra_projectiles", int, 0),),
        source="dat:charge_type==7 (max_total_projectiles - total_projectiles)",
        engines=ALL_ENGINES,
        description="Opening burst: extra projectiles on the FIRST attack only "
                    "(Xianbei Raider: 5).",
        quirks="Xianbei Raider is the only unit with a non-zero value in the "
               "committed DB (census 2026-06-10). The docs' older 'Kipchak' "
               "example is wrong — Kipchak is sustained extra_projectiles=3, "
               "first burst 0. Xianbei ALSO carries the charge_projectile "
               "volley (5 @ 30s recharge), so its opening burst and its "
               "recharging burst are two separate mechanisms on one row.",
    ),
    "charge_projectile_volley": Ability(
        name="charge_projectile_volley",
        family="projectile_volley",
        params=(
            _p("charge_projectile_count", int, 0),
            _p("charge_projectile_attacks_json", str, None),
            _p("charge_projectile_speed", float, 0,
               engines=(ENGINE_POSITION, ENGINE_JS),
               quirks="dat-extracted only — no config entry overrides it. "
                      "simulation.py parses it but has no projectile flight, "
                      "so it is behaviorally unused there."),
        ),
        source="dat:charge_type==6/7 (max-total delta), dat:charge_projectile_attacks "
               "+ curated:UNIQUE_COMBAT_PROPERTIES (Xianbei per-arrow override, "
               "Bolas count=1, Fire Archer disabled via count=0)",
        engines=ALL_ENGINES,
        description="Recharging projectile salvo with its own damage profile "
                    "(Fire Lancer 3, Xianbei 5, Bolas Rider 1, Lou Chuan 9).",
        quirks=(
            "Recharge: charge_recharge_time > 0 fires the salvo IN ADDITION "
            "to the normal attack then recharges (Fire Lancer/Xianbei/Bolas, "
            "all 30s); <= 0 REPLACES the normal shot every attack (Lou Chuan, "
            "recharge 0). Wu Fire Archer was remodeled to extra_projectiles "
            "(config forces charge_projectile_count=0) after the charge path "
            "over-buffed it. ENGINE GAP: simulation.py collapses the salvo to "
            "ONE primary-replacing charge-damage shot per recharge (count "
            "acts as a flag, not a multiplier) and ignores charge_attack_"
            "range/charge_ignores_armor; the position engine and JS fire "
            "`count` real projectiles."
        ),
    ),
    "extra_proj_scatter": Ability(
        name="extra_proj_scatter",
        family="projectile_volley",
        params=(_p("extra_proj_scatter", int, 0),),
        source="curated:UNIQUE_COMBAT_PROPERTIES",
        engines=ALL_ENGINES,
        description="Extra projectiles spread to DIFFERENT targets instead of "
                    "the focus target (Organ Gun).",
        quirks="In simulation.py scattered extras always land (no accuracy "
               "roll) on a random alive enemy; position/JS pick distinct "
               "non-target enemies round-robin.",
    ),
    # ------------------------------------------------------------------
    # area_damage — damage beyond the single struck target
    # ------------------------------------------------------------------
    "siege_splash": Ability(
        name="siege_splash",
        family="area_damage",
        params=(
            _p("is_siege_projectile", int, 0),
            _p("splash_radius", float, 0),
        ),
        source="dat:class==13 & blast_width>0 & blast_damage>=1 & range>=1",
        engines=ALL_ENGINES,
        description="Siege impact AoE around the landing point (Mangonel, "
                    "Siege Onager, Bombard Cannon).",
        quirks="Sketch deviation (code wins): is_siege_projectile lives here, "
               "not in misc — it gates the splash branch and the projectile "
               "arc flag. Position engine applies linear falloff "
               "1-0.75*(d/r) and bumps small radii to >=2.5 tiles; "
               "simulation.py converts radius to a victim count "
               "(radius/0.75 spacing).",
    ),
    "splash_on_hit": Ability(
        name="splash_on_hit",
        family="area_damage",
        params=(
            _p("splash_on_hit_radius", float, 0),
            _p("splash_on_hit_fraction", float, 1.0,
               engines=(ENGINE_ABSTRACT, ENGINE_POSITION),
               quirks="schema default-only: no extractor or config entry sets "
                      "it — every row holds 1.0. JS ignores it (frontend "
                      "splash always full damage)."),
        ),
        source="dat:blast_attack_level==11 (radius) + schema:default-only (fraction)",
        engines=ALL_ENGINES,
        description="AoE around the struck target on every hit (Grenadier, "
                    "blast level 11, radius 0.65).",
        quirks="Grenadier (Jurchens) is the only unit with a radius in the "
               "committed DB.",
    ),
    "trample": Ability(
        name="trample",
        family="area_damage",
        params=(
            _p("trample_percent", float, 0),
            _p("trample_radius", float, 0),
            _p("trample_flat_damage", int, 0),
        ),
        source="dat:blast_attack_level==2 & 0<blast_damage<1 (percent+radius) "
               "+ curated:UNIQUE_COMBAT_PROPERTIES (Ibirapema cone->1.0/0.5) "
               "+ curated:CIV_COMBAT_PROPERTIES (Logistica/Druzhina flat 5, "
               "Poles Lechitic Legacy 0.5)",
        engines=ALL_ENGINES,
        description="Melee-only AoE: trample_dmg = hit*percent + flat, within "
                    "radius (elephants 0.25-0.5, Ratha melee 0.2, Urumi 0.5, "
                    "Siege Ram, Logistica/Druzhina flat 5).",
        quirks=(
            "FAMILY BOUNDARY: Centurion/Comitatenses is NOT trample/splash — "
            "it is charge_attack_melee=5 @ 20s (DB: elite_centurion trample_"
            "percent=0). Easily confused; keep it in the charge family. "
            "Logistica vs Druzhina: both write trample_flat_damage=5 via "
            "CIV_COMBAT_PROPERTIES on disjoint rosters (Byz cataphract / "
            "Slavs militia+halb lines); dict-update semantics REPLACE, so "
            "there is no stacking path even in principle. "
            "Urumi gating: units with charge_attack_melee>0 trample only on "
            "the charged strike in position/JS engines; simulation.py cannot "
            "see strikes so it approximates with TRAMPLE_HIT_CHANCE=0.25 on "
            "every hit, ungated. Ghulam's dat 0.5 melee splash is "
            "deliberately NOT modeled (over-amplifies vs cheap swarms)."
        ),
    ),
    "pass_through": Ability(
        name="pass_through",
        family="area_damage",
        params=(
            _p("pass_through_percent", float, 0),
            _p("pass_through_count", int, 1,
               engines=(ENGINE_ABSTRACT, ENGINE_POSITION),
               quirks="JS has no count — frontend pass-through always hits "
                      "exactly 1 unit behind the target. The position engine "
                      "honors count only on the RANGED path; its melee "
                      "pass-through also hits exactly 1."),
        ),
        source="dat:blast_attack_level==3 & multi-class secondary attacks "
               "(secondary/primary pierce ratio) + curated:COMBAT_PROPERTIES "
               "+ curated:UNIQUE_COMBAT_PROPERTIES + curated:CIV_COMBAT_PROPERTIES",
        engines=ALL_ENGINES,
        description="Projectile rakes targets behind the impact for a "
                    "fraction of damage (Scorpion line 50%/3, Chakram 100%/3, "
                    "Ballista Elephant, Mapuche Malon 30%/1, Pirotecnia 15%).",
        quirks="In simulation.py, pass-through EXTRAS also skip the accuracy "
               "roll (grouped with scatter in the always-land branch).",
    ),
    # ------------------------------------------------------------------
    # charge — recharging bonus effects on the normal attack
    # ------------------------------------------------------------------
    "melee_charge": Ability(
        name="melee_charge",
        family="charge",
        params=(
            _p("charge_attack_melee", int, 0),
            _p("charge_recharge_time", float, 0),
        ),
        source="curated:UNIQUE_COMBAT_PROPERTIES (Coustillier 20/25, Urumi "
               "12/15) + curated:CIV_COMBAT_PROPERTIES (Comitatenses 5, "
               "Samurai 1) — dat-informed (MaxCharge/RechargeRate) but the "
               "type-1 melee charge is not auto-extracted",
        engines=ALL_ENGINES,
        description="Bonus melee damage on the charged strike, then recharges "
                    "(recharge_time = dat MaxCharge/RechargeRate: Coustillier "
                    "40s, Urumi 24/20s, Comitatenses+Samurai 20/30s).",
        quirks=(
            "charge_recharge_time is SHARED with charge_projectile_volley — "
            "one timer field serves both the melee charge and the ranged "
            "salvo (no unit carries both). Damage model differs by engine: "
            "position/JS add max(0, charge - target_melee_armor); "
            "simulation.py adds the flat value with no armor subtraction. "
            "Samurai's +25% conditional speed boost (update 141935) is NOT "
            "modeled — only the +1 charge damage."
        ),
    ),
    "ranged_charge_mods": Ability(
        name="ranged_charge_mods",
        family="charge",
        params=(
            _p("charge_attack_range", float, 0),
            _p("charge_ignores_armor", int, 0),
        ),
        source="curated:UNIQUE_COMBAT_PROPERTIES (Fire Lancer)",
        engines=(ENGINE_POSITION, ENGINE_JS),
        description="Mods for melee units launching charge projectiles: "
                    "launch range (Fire Lancer 4 tiles) and armor-ignoring "
                    "charge damage.",
        quirks="KNOWN GAP: simulation.py ignores both (its charge volley has "
               "no range concept and computes charge damage through normal "
               "armor). Only Fire Lancer (+Elite) carries them in the DB.",
    ),
    "charge_slow": Ability(
        name="charge_slow",
        family="charge",
        params=(
            _p("charge_slow_percent", float, 0),
            _p("charge_slow_duration", float, 0),
        ),
        source="curated:UNIQUE_COMBAT_PROPERTIES (Bolas Rider)",
        engines=ALL_ENGINES,
        description="Charge projectile slows the struck target (Bolas Rider: "
                    "15% for 10s).",
        quirks="Position/JS re-apply only after the previous slow expires "
               "(no refresh-stacking); simulation.py refreshes the timer on "
               "every charge hit.",
    ),
    # ------------------------------------------------------------------
    # damage_over_time
    # ------------------------------------------------------------------
    "bleed": Ability(
        name="bleed",
        family="damage_over_time",
        params=(
            _p("bleed_dps", float, 0),
            _p("bleed_duration", float, 0),
        ),
        source="curated:UNIQUE_COMBAT_PROPERTIES (Liao Dao 3.0/3s) "
               "+ curated:CIV_COMBAT_PROPERTIES (Tupi Curare: arbalester "
               "0.333/15s, blackwood 0.133/15s)",
        engines=ALL_ENGINES,
        description="Damage over time applied on hit (Liao Dao bleed, Tupi "
                    "Curare poison).",
        quirks="One bleed slot per target, refreshed on hit — the real game "
               "stacks per-shot, so multi-shooter Curare is undermodeled "
               "(documented in config_combat.py).",
    ),
    # ------------------------------------------------------------------
    # on_kill
    # ------------------------------------------------------------------
    "attack_per_kill": Ability(
        name="attack_per_kill",
        family="on_kill",
        params=(_p("attack_bonus_per_kill", int, 0),),
        source="curated:UNIQUE_COMBAT_PROPERTIES (Jaguar Warrior, Tiger Cavalry)",
        engines=ALL_ENGINES,
        description="+1 attack per kill up to a cap; the stored value IS the "
                    "cap (4), not the increment.",
    ),
    "hp_per_kill": Ability(
        name="hp_per_kill",
        family="on_kill",
        params=(
            _p("hp_per_kill", int, 0),
            _p("hp_per_kill_max", int, 0),
        ),
        source="curated:UNIQUE_COMBAT_PROPERTIES (Tiger Cavalry +10, max +40)",
        engines=ALL_ENGINES,
        description="Heal on kill, capped by total HP gained.",
        quirks="simulation.py lets healing exceed max_hp by up to the cap "
               "(hp + hp_per_kill_max ceiling); position/JS clamp to max_hp.",
    ),
    "resources_per_kill": Ability(
        name="resources_per_kill",
        family="on_kill",
        params=(
            _p("food_per_kill", float, 0,
               quirks="No producer sets food today (column + engine support "
                      "exist for symmetry with gold)."),
            _p("wood_per_kill", float, 0,
               quirks="No producer sets wood today (column + engine support "
                      "exist for symmetry with gold)."),
            _p("gold_per_kill", float, 0),
        ),
        source="curated:CIV_COMBAT_PROPERTIES (Mapuche mounted units: gold 3)",
        engines=(ENGINE_POSITION,),
        description="Eco gain per military kill, credited to BattleOutcome "
                    "*_gained fields (Mapuche civ bonus).",
        quirks="POSITION-ONLY by design: simulation.py does not even parse "
               "the trio (no BattleOutcome), JS has no economy. Verified vs "
               "tests/test_resource_per_kill.py.",
    ),
    # ------------------------------------------------------------------
    # armor_interaction
    # ------------------------------------------------------------------
    "ignore_armor": Ability(
        name="ignore_armor",
        family="armor_interaction",
        params=(
            _p("ignores_melee_armor", int, 0),
            _p("ignores_pierce_armor", int, 0),
        ),
        source="curated:UNIQUE_COMBAT_PROPERTIES (Leitis, Composite Bowman) "
               "+ curated:CIV_COMBAT_PROPERTIES (Wootz Steel)",
        engines=ALL_ENGINES,
        description="Base damage bypasses the matching armor type (Leitis "
                    "melee, Composite Bowman pierce, Dravidian Wootz Steel).",
        quirks="Zeroes only the BASE armor term — class-specific bonus armor "
               "still applies to bonus damage.",
    ),
    "armor_strip": Ability(
        name="armor_strip",
        family="armor_interaction",
        params=(_p("armor_strip_per_hit", int, 0),),
        source="curated:UNIQUE_COMBAT_PROPERTIES (Obuch)",
        engines=ALL_ENGINES,
        description="Each hit permanently removes 1 melee + 1 pierce armor "
                    "from the target (floor 0).",
    ),
    "bonus_damage_reduction": Ability(
        name="bonus_damage_reduction",
        family="armor_interaction",
        params=(_p("bonus_damage_reduction", float, 0),),
        source="dat:bonus_damage_resistance + curated:CIV_COMBAT_PROPERTIES "
               "(Sicilians 0.4, Bengalis elephants/Ratha 0.25)",
        engines=ALL_ENGINES,
        description="Reduces incoming BONUS (class) damage by a fraction; "
                    "base damage unaffected.",
    ),
    "damage_reflect": Ability(
        name="damage_reflect",
        family="armor_interaction",
        params=(_p("damage_reflect_percent", float, 0),),
        source="curated:CIV_COMBAT_PROPERTIES (Khitan Lamellar Armor 0.25)",
        engines=ALL_ENGINES,
        description="Reflects a fraction of received MELEE damage back at "
                    "the attacker (Khitan infantry + skirm + Fire Lancer "
                    "lines).",
    ),
    # ------------------------------------------------------------------
    # defensive
    # ------------------------------------------------------------------
    "dodge_shield": Ability(
        name="dodge_shield",
        family="defensive",
        params=(
            _p("dodge_shield_max", int, 0),
            _p("dodge_shield_recharge", float, 0),
        ),
        source="dat:charge_type==4 (charge_attack=charges, "
               "recharge=charge_attack/charge_recharge_rate)",
        engines=ALL_ENGINES,
        description="Absorbs N ranged hits, then recharges (Shrivamsha "
                    "Rider 5/7 charges, 20s).",
    ),
    "block_first_melee": Ability(
        name="block_first_melee",
        family="defensive",
        params=(_p("block_first_melee", int, 0),),
        source="curated:UNIQUE_COMBAT_PROPERTIES (Iron Pagoda)",
        engines=ALL_ENGINES,
        description="Negates the first melee hit ever received (once per "
                    "unit, no recharge).",
    ),
    # ------------------------------------------------------------------
    # aura — effects driven by nearby/army allies
    # ------------------------------------------------------------------
    "attack_aura": Ability(
        name="attack_aura",
        family="aura",
        params=(
            _p("attack_bonus_nearby", float, 0),
            _p("nearby_bonus_count", int, 0),
        ),
        source="curated:UNIQUE_COMBAT_PROPERTIES (Monaspa +1, cap 4)",
        engines=ALL_ENGINES,
        description="Attack bonus per nearby ally up to a cap (Monaspa; "
                    "real game: +1 per 7 Knights/Monaspas in 15 tiles).",
        quirks="Approximation everywhere: +1 per adjacent ally capped — the "
               "7-unit threshold is not modeled. simulation.py pre-computes "
               "it as flat damage from army size at setup (min(cap, n-1)), "
               "so it never decays as allies die; position/JS recompute "
               "live within a radius.",
    ),
    "hp_aura": Ability(
        name="hp_aura",
        family="aura",
        params=(
            _p("hp_nearby_percent_per_unit", float, 0),
            _p("hp_nearby_max_units", int, 0),
        ),
        source="curated:CIV_COMBAT_PROPERTIES (Shu Coiled Serpent Array: "
               "+0.5%/unit, cap 30)",
        engines=ALL_ENGINES,
        description="Max-HP percent bonus per nearby qualifying ally (Shu "
                    "spear line + White Feather Guard).",
        quirks="simulation.py applies it once at setup from army size; "
               "position/JS update it live (HP scales down as allies die).",
    ),
    "ally_death_heal": Ability(
        name="ally_death_heal",
        family="aura",
        params=(
            _p("ally_death_heal", float, 0),
            _p("ally_death_heal_duration", float, 0),
        ),
        source="curated:UNIQUE_COMBAT_PROPERTIES (Guecha Warrior +5 over 3s)",
        engines=ALL_ENGINES,
        description="When a same-type ally dies, survivors gain a refreshing "
                    "(non-stacking) heal-over-time.",
        quirks="Placed in the aura family (ally-interaction trigger), not "
               "on_kill — it keys on ALLY deaths, not own kills.",
    ),
    # ------------------------------------------------------------------
    # form_change — units that become another stat block
    # ------------------------------------------------------------------
    "dismount_on_death": Ability(
        name="dismount_on_death",
        family="form_change",
        params=(
            _p("dismount_unit_id", int, 0, engines=(), in_combat_dict=False,
               quirks="Generation-time input (which dat unit to derive) + "
                      "audit column; no engine or loader reads it."),
            _p("dismount_hp", int, None),
            _p("dismount_attack", int, None),
            _p("dismount_melee_armor", int, None),
            _p("dismount_pierce_armor", int, None),
            _p("dismount_attack_speed", float, None,
               quirks="attacks/sec (engines compute reload=1/x). The old "
                      "config block stored reload-seconds (2.4) — fixed by "
                      "the derived block (0.4167)."),
            _p("dismount_attack_delay", float, None),
            _p("dismount_movement_speed", float, None),
            _p("dismount_attacks_json", str, None),
            _p("dismount_armors_json", str, None),
        ),
        source="derived:form_tech_chain (stat block, since commit bcdbcbc) "
               "+ curated:UNIQUE_COMBAT_PROPERTIES (dismount_unit_id 1252/1253; "
               "the config's stat values are dead inputs pending deletion in "
               "a bundled re-sim window)",
        engines=(ENGINE_ABSTRACT,),
        description="On death the unit respawns as its dismounted form "
                    "(Konnik -> foot Konnik, dat units 1252/1253), now "
                    "derived through the full infantry tech chain per civ.",
        quirks="KNOWN ENGINE GAP: abstract-only. simulation_real.py and "
               "simulate.js contain NO dismount handling — the Konnik second "
               "life is missing from ALL batch matchup data and the "
               "interactive page (form-fix report 2026-06-10). Document, "
               "don't fix, in Phase A.",
    ),
    "hp_transform": Ability(
        name="hp_transform",
        family="form_change",
        params=(
            _p("hp_transform_threshold", float, 0,
               quirks="Curated ratio (45/70) — genuinely not in the dat."),
            _p("transform_unit_id", int, 0, ref_column=None, engines=(),
               in_combat_dict=False,
               quirks="Generation-time input only (dat unit 1976); unlike "
                      "dismount_unit_id it is not even stored as a column."),
            _p("transform_hp", int, None),
            _p("transform_attack", int, None),
            _p("transform_melee_armor", int, None),
            _p("transform_pierce_armor", int, None),
            _p("transform_attack_speed", float, None),
            _p("transform_attack_delay", float, None, engines=(ENGINE_ABSTRACT,),
               quirks="Only simulation.py's _parse_transform reads the delay; "
                      "position/JS keep the pre-transform delay."),
            _p("transform_movement_speed", float, None),
            _p("transform_attacks_json", str, None),
            _p("transform_armors_json", str, None),
        ),
        source="derived:form_tech_chain (stat block, since commit bcdbcbc) "
               "+ curated:UNIQUE_COMBAT_PROPERTIES (threshold + unit id; the "
               "config's stat values are dead inputs pending deletion)",
        engines=ALL_ENGINES,
        description="Below an HP threshold the unit swaps to a second stat "
                    "block (Jian Swordsman -> dual-wield form, dat unit 1976).",
        quirks="One-way, once per unit. The transform block keeps current_hp; "
               "max_hp becomes transform_hp.",
    ),
    "paired_forms": Ability(
        name="paired_forms",
        family="form_change",
        params=(
            _p("paired_unit_slug", str, None, ref_column=None, engines=()),
        ),
        source="curated:PAIRED_UNITS",
        engines=(),
        description="Two-row pattern for switchable units: Ratha (melee) and "
                    "Ratha (ranged) are SEPARATE fully-pipelined ref_units "
                    "rows linked by slug — the model §3.3 wants form_change "
                    "to converge on.",
        quirks="Defined in analysis/config_units.py PAIRED_UNITS, not "
               "config_combat.py. No engine reads it: build_combat_dict_"
               "from_ref hardcodes None; consumers are serving/scoring "
               "(compute_battle_scores _DISPLAY_FIELDS, generate_main_db).",
    ),
    # ------------------------------------------------------------------
    # tempo — attack timing modifiers
    # ------------------------------------------------------------------
    "attack_speed_ramp": Ability(
        name="attack_speed_ramp",
        family="tempo",
        params=(
            _p("attack_speed_ramp", float, 0),
            _p("attack_speed_min", float, 0),
        ),
        source="curated:UNIQUE_COMBAT_PROPERTIES (Temple Guard 0.2/1.0)",
        engines=ALL_ENGINES,
        description="Each hit shortens reload by `ramp` seconds toward a "
                    "floor of `min` (Temple Guard).",
        quirks="Position engine resets the ramp out of combat; simulation.py "
               "has no out-of-combat concept so the ramp only grows.",
    ),
    "execute": Ability(
        name="execute",
        family="tempo",
        params=(
            _p("execute_damage_per_step", float, 0),
            _p("execute_hp_step", float, 0),
        ),
        source="curated:UNIQUE_COMBAT_PROPERTIES (Kona: +1 per 15% missing HP)",
        engines=ALL_ENGINES,
        description="Bonus damage scaling with the target's missing HP "
                    "(Kona).",
    ),
    # ------------------------------------------------------------------
    # misc
    # ------------------------------------------------------------------
    "min_attack_range": Ability(
        name="min_attack_range",
        family="misc",
        params=(_p("min_attack_range", float, 0, ref_column="min_range"),),
        source="dat:min_range",
        engines=ALL_ENGINES,
        description="Dead zone: cannot fire inside this range (Mangonel "
                    "line, Genitour, ships).",
        quirks="Only stored param whose ref_units column name differs from "
               "the combat-dict key (min_range -> min_attack_range). "
               "Engines: abstract flags cant_attack_melee at >=2; position "
               "backs out of the dead zone until the 60s kite stop.",
    ),
    "miss_damage": Ability(
        name="miss_damage",
        family="misc",
        params=(_p("miss_damage_percent", float, 0),),
        source="curated:UNIQUE_COMBAT_PROPERTIES (Arambai 1.0)",
        engines=ALL_ENGINES,
        description="Missed shots deal this fraction of damage to a grazed "
                    "nearby enemy (Arambai full damage).",
        quirks="Interacts with a GLOBAL engine mechanic, not per-unit: the "
               "position engine lands every miss within MISS_SPREAD_RADIUS="
               "2.0 tiles and grazes any covering hitbox at 0.5x (or this "
               "override); simulation.py instead rolls a stray-hit chance "
               "min(0.5, alive*0.05) replaced by this value.",
    ),
    "pop_space": Ability(
        name="pop_space",
        family="misc",
        params=(_p("pop_space", float, 1.0),),
        source="curated:UNIQUE_COMBAT_PROPERTIES (Karambit 0.5, Blackwood "
               "Archer 0.5)",
        engines=ALL_ENGINES,
        description="Population cost used to size equal-pop (fixed_count) "
                    "armies — half-pop units field twice as many.",
        quirks="Army-sizing knob, not a combat behavior; all three engines "
               "divide fixed_count/pop by it.",
    ),
    "hp_regen": Ability(
        name="hp_regen",
        family="misc",
        params=(_p("hp_regen", float, 0),),
        source="dat:hp_regen (attr 109, stored as rear_attack_modifier) + "
               "tech-effect chain (generate_reference merges the higher of "
               "extracted vs analyzer-tracked attr-109 additions)",
        engines=ALL_ENGINES,
        description="Passive HP/minute regeneration (Berserk 40, War Dog, "
                    "Camel Archer, ships).",
    ),
    "hp_regen_in_combat": Ability(
        name="hp_regen_in_combat",
        family="misc",
        params=(_p("hp_regen_in_combat", float, 0),),
        source="curated:CIV_COMBAT_PROPERTIES (Khitan Ordo Cavalry: "
               "round(base_hp*1.5)/min)",
        engines=(ENGINE_POSITION,),
        description="HP/minute regeneration gated to combat (within 5s of "
                    "attacking; COMBAT_WINDOW_S).",
        quirks="KNOWN ENGINE GAP: position-only. simulation.py parses the "
               "field but never applies it; simulate.js does not read it at "
               "all. Khitan Ordo regen exists only in batch matchup data.",
    ),
    "projectile_speed": Ability(
        name="projectile_speed",
        family="misc",
        params=(_p("projectile_speed", float, 0),),
        source="dat:projectile_speed (speed of the projectile unit)",
        engines=(ENGINE_POSITION, ENGINE_JS),
        description="Projectile flight speed in tiles/s (fallback 7); shots "
                    "land after travel time, possibly after the shooter "
                    "dies.",
        quirks="simulation.py parses it but resolves all shots instantly "
               "(no flight model).",
    ),
    "unit_category": Ability(
        name="unit_category",
        family="misc",
        params=(_p("unit_category", str, "military", ref_column=None, engines=()),),
        source="curated:COMBAT_PROPERTIES",
        engines=(),
        description="Classification tag (siege/trash/infantry/military) for "
                    "scoring and pool composition, not combat behavior.",
        quirks="Not a ref_units column: build_combat_dict_from_ref hardcodes "
               "'military'; the curated values reach only the legacy "
               "aoe2_units.db path (generate_main_db) and display fields. "
               "Most COMBAT_PROPERTIES entries exist solely to set this tag, "
               "and the unique-unit ones never match (exact-slug lookup vs "
               "civ-suffixed slugs) — see the orphan-key test allowlist.",
    ),
}


# ---------------------------------------------------------------------------
# Convenience accessors (used by the validation tests; cheap, no caching)
# ---------------------------------------------------------------------------

def iter_params():
    """Yield (ability, param) for every declared param."""
    for ability in ABILITIES.values():
        for param in ability.params:
            yield ability, param


def param_names():
    """Set of all declared param names (combat-dict keys)."""
    return {p.name for _, p in iter_params()}


def stored_columns():
    """Set of all ref_units columns the registry claims to exist."""
    return {p.column for _, p in iter_params() if p.column is not None}


def families_in_use():
    return {a.family for a in ABILITIES.values()}


def per_family_counts():
    counts = {}
    for a in ABILITIES.values():
        counts.setdefault(a.family, [0, 0])
        counts[a.family][0] += 1
        counts[a.family][1] += len(a.params)
    return {f: tuple(v) for f, v in counts.items()}

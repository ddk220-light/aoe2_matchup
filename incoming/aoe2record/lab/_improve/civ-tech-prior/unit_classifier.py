"""Group-first, confidence-based AoE2:DE unit-type classifier.

Standalone: takes a parsed mgz ``match`` (no Flask dependency). See
CLASSIFIER_REWORK.md for the full design and rationale.

Implemented so far: Stage 0 (context + id normalization), Stage 1 (refined
behavioral class), Stage 2 (co-command class propagation). Stages 3-5 (production
timeline, squad typing, finalize) are scaffolded and filled in subsequent phases.
"""

import bisect
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import combinations

# --- command semantics (refined; see findings in CLASSIFIER_REWORK.md) --------
# Only a MILITARY unit can be the subject of these.
MIL_CMDS = {"STANCE", "FORMATION", "PATROL", "ATTACK_GROUND", "DE_ATTACK_MOVE", "GUARD"}
# Only a VILLAGER can BUILD/REPAIR/WALL (gather is handled via resource targets).
VIL_CMDS = {"BUILD", "REPAIR", "WALL"}
# Commands whose object_ids reference a BUILDING, not the acting unit.
BLD_SUBJECT_CMDS = {
    "DE_QUEUE", "RESEARCH", "GATHER_POINT", "SELL", "BUY",
    "TOWN_BELL", "UNGARRISON", "DE_MULTI_GATHERPOINT",
}
# Commands that can carry a unit "group" (multiple object_ids that act together).
GROUP_CMDS = {"MOVE", "PATROL", "ORDER", "DE_ATTACK_MOVE", "GUARD", "STANCE", "FORMATION"}
# GAIA names only villagers gather (NOT animals: scouts lure boar, both attack).
RESOURCE_KW = ("gold mine", "stone mine", "tree", "bush", "berr", "forage", "shrub", "plant")

# SPECIAL/UNGARRISON encode object ids byte-shifted (id<<8); normalize via >>8.
SHIFT_THRESHOLD = 1_000_000

# Confidence ladder.
CONF = {
    "header": 0.99,
    "hard_class": 0.95,
    "cocmd_class": 0.90,
    "squad_type": 0.80,
    "idrank_type": 0.55,
    "fallback": 0.30,
}

# Base DE train times (seconds). Loaded from train_times.json (extracted from the
# aoe2-unit-analyzer .dat database -- civ-accurate base values); this dict is the
# fallback for tokens the DB names differently. Default 30 for unknowns.
_FALLBACK_TRAIN_TIMES = {
    "villager": 25, "fishingship": 40, "tradecart": 51, "tradecog": 36,
    "militia": 21, "manatarms": 21, "spearman": 22, "eaglescout": 60,
    "archer": 35, "crossbowman": 27, "skirmisher": 22, "cavalryarcher": 34, "handcannoneer": 34,
    "scoutcavalry": 30, "knight": 30, "camelrider": 22, "camelscout": 22, "battleelephant": 24,
    "monk": 51, "mangonel": 46, "scorpion": 30, "batteringram": 36, "trebuchet": 50,
    "bombardcannon": 56, "magyarhuszar": 16,
    # common unique/regional units (base DE values; default 30 otherwise)
    "berserk": 16, "mangudai": 26, "rattanarcher": 16, "steppelancer": 24,
    "battleelephant": 24, "eaglewarrior": 35, "eaglescout": 60, "konnik": 19,
    "woadraider": 10, "huskarl": 16, "tarkan": 14, "genoesecrossbowman": 22,
    "camel": 22, "lightcavalry": 30, "hussar": 30, "elephantarcher": 25,
}


def _load_train_times():
    """Merge the DB-extracted civ-accurate base train times over the fallback."""
    import json as _json
    import os as _os
    tt = dict(_FALLBACK_TRAIN_TIMES)
    try:
        p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "train_times.json")
        data = _json.load(open(p))
        for k, v in (data.get("base") or {}).items():
            if v:
                tt[k] = float(v)
    except Exception:
        pass
    # tokens the DB names differently than DE_QUEUE / the classifier
    tt.setdefault("militia", 21)
    tt.setdefault("manatarms", 21)
    tt.setdefault("champiscout", tt.get("champiwarrior", 26))
    return tt


TRAIN_TIMES = _load_train_times()

# Passive CIV bonuses that change unit CREATION speed. These are NOT in the DB's
# final_train_time (which only reflects tech upgrades), so they must be applied here as
# a multiplier on military train time. Without this the per-building FIFO mis-times (and
# thus mis-orders) a civ's whole army -- e.g. Aztec military trains 11% faster, so the
# base-time model runs ~11% slow and drifts later as the queue deepens.
CIV_MIL_SPEED = {
    "Aztecs": 0.89,   # "Military units created 11% faster"
}


TICKS_PER_SEC = 20   # AoE2 simulation granularity; production completes on tick boundaries

# Lines the Aztec-style "military created faster" bonus applies to. Calibrated from gRPC
# spawn data: Barracks/Archery/Stable AND Siege Workshop ARE sped up (mangonel queue+41s
# = 46x0.89, confirmed), but the MONASTERY is NOT (monks spawn exactly 51s apart = base).
# So the bonus covers every military-production building except the Monastery.
_SPEED_BONUS_LINES = {"arch", "inf", "cav", "siege", "unique"}

# --- CIV + TECH-TREE PRIORS ----------------------------------------------------
# Research DURATIONS (seconds) for techs hosted at unit-producing buildings. While a
# tech researches, that building's production queue is BLOCKED -- ignoring this makes
# the FIFO run early (gRPC calibration: Armenian militia stream drifted -68s across
# Man-at-Arms/LS/THS/Squires/Arson research). Game constants from the DE tech tree.
TECH_DURATIONS = {
    # town center (blocks villager production!)
    "Feudal Age": 130, "Castle Age": 160, "Imperial Age": 190,
    "Loom": 25, "Wheelbarrow": 75, "Hand Cart": 55, "Town Watch": 25, "Town Patrol": 40,
    # barracks
    "Man-at-Arms": 40, "Long Swordsman": 45, "Two-Handed Swordsman": 75, "Champion": 100,
    "Pikeman": 45, "Halberdier": 50, "Eagle Warrior": 50, "Elite Eagle Warrior": 40,
    "Squires": 40, "Arson": 25, "Supplies": 35, "Gambesons": 25,
    # archery range
    "Crossbowman": 35, "Arbalester": 50, "Elite Skirmisher": 50, "Imperial Skirmisher": 65,
    "Heavy Cavalry Archer": 50, "Thumb Ring": 45, "Parthian Tactics": 65,
    "Elite Elephant Archer": 80,
    # stable
    "Bloodlines": 50, "Husbandry": 40, "Light Cavalry": 45, "Hussar": 50,
    "Winged Hussar": 75, "Cavalier": 100, "Paladin": 170, "Heavy Camel Rider": 125,
    "Imperial Camel Rider": 125, "Elite Battle Elephant": 80, "Elite Steppe Lancer": 50,
    # siege workshop
    "Capped Ram": 50, "Siege Ram": 75, "Onager": 75, "Siege Onager": 150,
    "Heavy Scorpion": 90, "Houfnice": 150,
    # monastery
    "Redemption": 50, "Atonement": 40, "Herbal Medicine": 35, "Heresy": 60,
    "Sanctity": 60, "Fervor": 50, "Faith": 60, "Illumination": 65,
    "Block Printing": 55, "Theocracy": 75, "Devotion": 40,
    # castle
    "Conscription": 60, "Hoardings": 75, "Sappers": 10, "Spies/Treason": 1,
}
TECH_DUR_DEFAULT = 45.0     # unknown techs (unique techs etc.)

# Unit-line UPGRADES: after the tech completes, the building trains the upgraded unit,
# whose train time can differ (Crossbowman 27s vs Archer 35s -- munq's g0 archer stream
# drifted +44s late without this). DE_QUEUE keeps recording the BASE unit name, so map
# tech -> (queue token, token to look the train time up under).
UPGRADE_TIME = {
    "Man-at-Arms": ("militia", "manatarms"),
    "Long Swordsman": ("militia", "longswordsman"),
    "Two-Handed Swordsman": ("militia", "twohandedswordsman"),
    "Champion": ("militia", "champion"),
    "Pikeman": ("spearman", "pikeman"),
    "Halberdier": ("spearman", "halberdier"),
    "Eagle Warrior": ("eaglescout", "eaglewarrior"),
    "Elite Eagle Warrior": ("eaglescout", "eliteeaglewarrior"),
    "Crossbowman": ("archer", "crossbowman"),
    "Arbalester": ("archer", "arbalester"),
    "Elite Skirmisher": ("skirmisher", "eliteskirmisher"),
    "Imperial Skirmisher": ("skirmisher", "imperialskirmisher"),
    "Heavy Cavalry Archer": ("cavalryarcher", "heavycavalryarcher"),
    "Light Cavalry": ("scoutcavalry", "lightcavalry"),
    "Hussar": ("scoutcavalry", "hussar"),
    "Winged Hussar": ("scoutcavalry", "winghussar"),
    "Cavalier": ("knight", "cavalier"),
    "Paladin": ("knight", "paladin"),
    "Heavy Camel Rider": ("camelrider", "heavycamelrider"),
    "Imperial Camel Rider": ("camelrider", "imperialcamelrider"),
    "Capped Ram": ("batteringram", "cappedram"),
    "Siege Ram": ("batteringram", "siegeram"),
    "Onager": ("mangonel", "onager"),
    "Siege Onager": ("mangonel", "siegeonager"),
    "Heavy Scorpion": ("scorpion", "heavyscorpion"),
    "Elite Battle Elephant": ("battleelephant", "elitebattleelephant"),
    "Elite Steppe Lancer": ("steppelancer", "elitesteppelancer"),
}

# Techs that change production SPEED of whole lines once researched.
TECH_SPEED = {
    "Conscription": (frozenset({"inf", "arch", "cav", "unique"}), 1 / 1.33),
    "Perfusion": (frozenset({"inf"}), 0.5),               # Goths unique
}

# Static civ bonuses on production speed (beyond the Aztec global one).
CIV_LINE_SPEED = {
    "Huns": {"cav": 1 / 1.2},       # Stables work 20% faster
    "Britons": {"arch": 1 / 1.2},   # team bonus: Archery Ranges work 20% faster
    "Celts": {"siege": 1 / 1.2},    # team bonus: Siege Workshops work 20% faster
}

AGE_TECHS = ("Feudal Age", "Castle Age", "Imperial Age")

# Ablation switches for the civ/tech-prior mechanisms (all independent).
PRIORS = {
    "blocks": True,       # research occupies the building FIFO (production pauses)
    "blocks_scope": "tc",   # 'all' buildings, or 'tc' = only villager-training ones
    "lb_blocks": True,    # ... also in the DE_QUEUE multiqueue load-balancer
    # The mechanisms below are REAL game mechanics and measurably reduce FIFO drift
    # (calib2.py), but the downstream lag-cost line-claiming DP was empirically tuned
    # around the uncorrected timing bias: enabling them flips MORE units wrong than
    # right (late-commanded units get claimed by the wrong, now-nearer line). Kept
    # implemented + calibrated but DISABLED until the aligner is made lag-robust.
    "upgrades": False,    # unit-line upgrade train times (Crossbowman 27s vs Archer 35s)
    "eagle_age": False,   # age-gated eagle/champi scout train times
    "line_speed": False,  # Huns/Britons/Celts production-speed bonuses
    "speed_techs": False,  # Conscription / Perfusion
    "coprod_lines": True,  # claim-lines from observed co-production (real prod tree)
    "avail_veto": True,    # veto types the owning player never produced/started with
}

# Eagle-analog scouts train much slower before Castle Age (hidden age tech). Eagle
# Scout: 60s feudal -> 35s castle (DE constant). Champi Scout (Inca analog): gRPC
# calibration shows 42s feudal -> ~35s castle.
PRE_CASTLE_TIME = {"eaglescout": 60.0, "champiscout": 42.0}
POST_CASTLE_TIME = {"champiscout": 35.0}


def _tt(unit, civ=None):
    """Civ-aware train time in TICKS (20/sec): base DB value x any passive creation-speed
    bonus, then quantised to the game's tick clock so completions land where the engine
    actually spawns them."""
    base = TRAIN_TIMES.get(unit, 30)
    if civ in CIV_MIL_SPEED and unit != "villager" and _line_of(unit) in _SPEED_BONUS_LINES:
        base *= CIV_MIL_SPEED[civ]
    return round(base * TICKS_PER_SEC) / TICKS_PER_SEC   # quantise to the tick clock


def _norm(s):
    return (s or "").lower().replace(" ", "")


def canonical_id(oid):
    """Collapse SPECIAL/UNGARRISON shifted refs (id<<8) back to the real id."""
    return oid >> 8 if oid >= SHIFT_THRESHOLD else oid


@dataclass
class UnitGuess:
    instance_id: int
    player: str = None
    cls: str = "unknown"          # 'villager' | 'military' | 'unknown'
    cls_conf: float = 0.0
    type: str = "unit"
    type_conf: float = 0.0
    squad_id: int = None
    role: str = "unknown"          # behavioral: 'eco'|'cavalry'|'ranged'|'siege'...
    signals: list = field(default_factory=list)
    behavior: dict = field(default_factory=dict)


@dataclass
class Context:
    match: object
    guesses: dict = field(default_factory=dict)        # canonical id -> UnitGuess
    owner: dict = field(default_factory=dict)          # canonical id -> player name
    building_ids: set = field(default_factory=set)     # canonical building ids
    start_ids: set = field(default_factory=set)
    resource_ids: set = field(default_factory=set)     # gaia resources (villager-only)
    gaia_all: set = field(default_factory=set)
    group_cmds: list = field(default_factory=list)     # [(player, [canonical ids]), ...]
    # production: building id -> list of (queue_time, unit_type)
    queues: dict = field(default_factory=lambda: defaultdict(list))
    shifted: set = field(default_factory=set)  # raw ids that arrive byte-shifted
    timeseries: dict = field(default_factory=dict)  # player -> [(t_sec, total_objects)]
    resign: dict = field(default_factory=dict)      # player -> resign time (sec)
    unqueues: dict = field(default_factory=lambda: defaultdict(list))  # building -> [(t, slot)]
    civ: dict = field(default_factory=dict)         # player name -> civilization
    # civ/tech priors (research timeline evidence)
    research_blocks: dict = field(default_factory=lambda: defaultdict(list))  # bldg -> [(t, dur)]
    tech_done: dict = field(default_factory=dict)   # player -> {tech: completion t}
    upgrades: dict = field(default_factory=dict)    # player -> {queue tok: [(eff t, time tok)]}
    speed_evt: dict = field(default_factory=dict)   # player -> [(eff t, lines, mult)]
    age_done: dict = field(default_factory=dict)    # player -> {age tech: completion t}

    def train_time(self, player, u, start_t):
        """Tech- and age-aware train time (seconds, tick-quantised) for player's unit u
        STARTING to train at start_t. Layers: base DB time -> unit-line upgrade in effect
        (Crossbowman 27s vs Archer 35s) -> age-gated eagle-line times -> static civ
        production-speed bonuses -> researched speed techs (Conscription)."""
        civ = self.civ.get(player)
        tok = u
        if PRIORS["upgrades"]:
            for eff, t2 in (self.upgrades.get(player) or {}).get(u, ()):
                if eff <= start_t:
                    tok = t2
        base = TRAIN_TIMES.get(tok, TRAIN_TIMES.get(u, 30))
        if PRIORS["eagle_age"] and u in PRE_CASTLE_TIME:
            castle = (self.age_done.get(player) or {}).get("Castle Age", float("inf"))
            if start_t < castle:
                base = PRE_CASTLE_TIME[u]
            elif u in POST_CASTLE_TIME and tok == u:
                base = POST_CASTLE_TIME[u]
        line = _line_of(u)
        if civ in CIV_MIL_SPEED and u != "villager" and line in _SPEED_BONUS_LINES:
            base *= CIV_MIL_SPEED[civ]
        if PRIORS["line_speed"]:
            for ln, m in (CIV_LINE_SPEED.get(civ) or {}).items():
                if ln == line:
                    base *= m
        if PRIORS["speed_techs"]:
            for eff, lines, m in self.speed_evt.get(player, ()):
                if eff <= start_t and line in lines:
                    base *= m
        return round(base * TICKS_PER_SEC) / TICKS_PER_SEC

    def canon(self, oid):
        """Source-aware id normalization. Only ids that arrive via SPECIAL/
        UNGARRISON are byte-shifted (id<<8) by the parser, so decode *only* those
        -- avoids the fragile >=1M magnitude heuristic that could corrupt a
        legitimate large id in a long game."""
        return (oid >> 8) if oid in self.shifted else oid


def _at(action):
    return str(action.type).replace("Action.", "")


def _seed_class_from_name(name):
    n = _norm(name)
    if "villager" in n or "fishing" in n:
        return "villager"
    if "scout" in n or "king" in n:
        return "military"
    return None


def _collect_tech(ctx, match):
    """Pre-pass: per-player research timeline from RESEARCH commands.

    Spam-clicked duplicates within 120s collapse into one research; a later cluster of
    the same tech means the first was canceled and redone, so the LAST cluster is the
    effective one. Yields: research occupancy blocks per hosting building (production
    pauses), per-player age completion times, unit-line upgrade effects, and production
    speed effects (Conscription/Perfusion)."""
    raw = defaultdict(list)
    for a in match.actions:
        if a.player and _at(a) == "RESEARCH":
            payload = a.payload or {}
            tech = payload.get("technology")
            if not tech:
                continue
            ids = payload.get("object_ids") or []
            raw[(a.player.name, tech)].append(
                (a.timestamp.total_seconds(), ctx.canon(ids[0]) if ids else None))
    for (player, tech), evts in raw.items():
        evts.sort()
        clusters = [[evts[0]]]
        for e in evts[1:]:
            if e[0] - clusters[-1][-1][0] <= 120:
                clusters[-1].append(e)
            else:
                clusters.append([e])
        dur = float(TECH_DURATIONS.get(tech, TECH_DUR_DEFAULT))
        # every cluster start occupies its building (a canceled research still blocked
        # the queue until canceled; full duration is the best available estimate)
        for cl in clusters:
            tc, bc = cl[0]
            if bc is not None:
                ctx.research_blocks[bc].append((tc, dur))
        t0, _b0 = clusters[-1][0]
        done = t0 + dur
        ctx.tech_done.setdefault(player, {})[tech] = done
        if tech in AGE_TECHS:
            ctx.age_done.setdefault(player, {})[tech] = done
        ut = UPGRADE_TIME.get(tech)
        if ut:
            ctx.upgrades.setdefault(player, {}).setdefault(ut[0], []).append((done, ut[1]))
        ts = TECH_SPEED.get(tech)
        if ts:
            ctx.speed_evt.setdefault(player, []).append((done, ts[0], ts[1]))
    for d in ctx.research_blocks.values():
        d.sort()
    for pu in ctx.upgrades.values():
        for lst in pu.values():
            lst.sort()
    for lst in ctx.speed_evt.values():
        lst.sort()


def build_context(match):
    """Stage 0: owner map, gaia split, behavior counters, group commands, queues.

    All object ids are normalized to canonical (shifted SPECIAL/UNGARRISON refs
    collapsed and deduped), so each physical unit is one id.
    """
    ctx = Context(match=match)

    # Pre-pass: collect the byte-shifted ids (those that arrive via SPECIAL /
    # UNGARRISON) so ctx.canon can decode exactly those.
    for a in match.actions:
        if a.player and _at(a) in ("SPECIAL", "UNGARRISON"):
            for o in (a.payload or {}).get("object_ids", []):
                ctx.shifted.add(o)

    # gaia: all ids + the villager-only resource subset
    gaia = getattr(match, "gaia", None) or []
    for g in gaia:
        iid = getattr(g, "instance_id", None)
        nm = (getattr(g, "name", None) or "").lower()
        if iid is None:
            continue
        ctx.gaia_all.add(iid)
        if nm and any(k in nm for k in RESOURCE_KW) and "dry" not in nm and "grass" not in nm:
            ctx.resource_ids.add(iid)

    # total_objects timeseries (per-player object count over time) -> used to
    # CALIBRATE production-completion timing for dense/concurrent production where
    # the per-building serial model misfires (multiqueue spreads one building's
    # queue impossibly). Increments are spawn events.
    for p in match.players:
        ctx.civ[p.name] = getattr(p, "civilization", None)
        ts = getattr(p, "timeseries", None) or []
        try:
            ctx.timeseries[p.name] = [(e.timestamp.total_seconds(), e.total_objects) for e in ts]
        except Exception:
            ctx.timeseries[p.name] = []

    # research timeline pre-pass (CIV+TECH PRIORS): research occupancy blocks per
    # building, age completion, unit-line upgrades, production-speed techs. RESEARCH
    # ids are never byte-shifted, so running before the shifted-id-aware walk is safe.
    _collect_tech(ctx, match)
    # per-building pending research items (consumed in command-time order by the
    # DE_QUEUE load-balancer below -- research occupies the queue like a unit does)
    res_pend = {b: list(blocks) for b, blocks in ctx.research_blocks.items()}

    # starting (header) units: known owner + name -> seed class at top confidence
    for p in match.players:
        for o in (p.objects or []):
            cid = ctx.canon(o.instance_id)
            ctx.start_ids.add(cid)
            ctx.owner[cid] = p.name
            g = _ensure(ctx, cid, p.name)
            onm = getattr(o, "name", None)
            seeded = _seed_class_from_name(onm)
            if seeded:
                _set_class(g, seeded, CONF["header"], "header")
                # starting units have a KNOWN identity from the header -> type them
                # directly (e.g. the free Scout Cavalry). They aren't produced, so the
                # production alignment must not touch them.
                if seeded == "military" and onm:
                    _set_type(g, _norm(onm), CONF["header"], "header")

    # walk actions: owner, behavior, group commands, queues, building ids
    building_free = defaultdict(float)   # building -> time its queue next goes idle
    for a in match.actions:
        if not a.player:
            continue
        at = _at(a)
        payload = a.payload or {}
        t = a.timestamp.total_seconds()
        if at == "RESIGN":
            # a resigning player stops producing immediately: anything still in the
            # build queue never spawns. Record the cutoff for production_timeline.
            ctx.resign[a.player.name] = t
            continue
        if payload.get("order") == "Unqueue":
            # cancel a unit from a building's production queue (it never spawns). The
            # building id arrives byte-shifted; slot_id is the queue position. Recorded
            # for production_timeline to remove from the FIFO -- without this the model
            # produces phantom units (e.g. ddk220 queued 10 archers, unqueued 5).
            slot = payload.get("slot_id")
            for o in payload.get("object_ids", []):
                ctx.unqueues[ctx.canon(o)].append((t, slot))
            continue
        ids = [ctx.canon(o) for o in payload.get("object_ids", [])]

        # DE_QUEUE etc: object_ids are BUILDINGS, not acting units
        if at in BLD_SUBJECT_CMDS:
            for b in ids:
                ctx.building_ids.add(b)
                ctx.owner.setdefault(b, a.player.name)
            if at == "DE_QUEUE" and ids:
                u = _norm(payload.get("unit"))
                amt = payload.get("amount", 1) or 1
                # research commanded at-or-before t occupies these buildings' queues
                # first (FIFO: a tech enters the queue at its command time)
                if PRIORS["lb_blocks"] and (PRIORS["blocks_scope"] == "all"
                                            or u == "villager"):
                    for bb in ids:
                        rq = res_pend.get(bb)
                        while rq and rq[0][0] <= t:
                            rt, dur = rq.pop(0)
                            building_free[bb] = max(building_free[bb], rt) + dur
                # MULTIQUEUE: object_ids is the full set of selected production
                # buildings; the game load-balances each unit to the one that
                # becomes free soonest. Simulate that so per-building queues are
                # realistic (not all dumped on ids[0]).
                for _ in range(amt):
                    b = min(ids, key=lambda bb: max(building_free[bb], t))
                    start = max(building_free[b], t)
                    building_free[b] = start + ctx.train_time(a.player.name, u, start)
                    ctx.queues[b].append((t, u))
            continue

        tgt = payload.get("target_id")
        for cid in ids:
            ctx.owner.setdefault(cid, a.player.name)
            g = _ensure(ctx, cid, a.player.name)
            b = g.behavior
            b.setdefault("first_seen", t)
            if at == "MOVE":
                b["moves"] = b.get("moves", 0) + 1
            elif at == "PATROL":
                b["patrols"] = b.get("patrols", 0) + 1
            elif at in VIL_CMDS:
                b["builds"] = b.get("builds", 0) + 1
            elif at == "ORDER" and isinstance(tgt, int):
                if tgt in ctx.resource_ids:
                    b["gathers"] = b.get("gathers", 0) + 1
                elif tgt not in ctx.gaia_all and ctx.owner.get(tgt) and ctx.owner.get(tgt) != a.player.name:
                    # NOTE: attacking an enemy object is NOT a class signal
                    # (villagers attack too). Recorded only as behavior.
                    b["attacks_building"] = b.get("attacks_building", 0) + 1
                elif tgt in ctx.building_ids and ctx.owner.get(tgt) == a.player.name:
                    # ORDER on a FRIENDLY (own-player) BUILDING. A monk does this to
                    # garrison its home monastery (drop a relic / re-bless); villagers do
                    # it to drop resources at a camp. NOT a class signal -- but among
                    # units already classed MILITARY it is monk-exclusive (a skirmisher/
                    # scout/knight never returns to a building), used by the monk override.
                    b["bld_order"] = b.get("bld_order", 0) + 1

        if at in GROUP_CMDS and len(ids) >= 2:
            ctx.group_cmds.append((a.player.name, sorted(set(ids))))

    return ctx


def _ensure(ctx, cid, player):
    g = ctx.guesses.get(cid)
    if g is None:
        g = ctx.guesses[cid] = UnitGuess(instance_id=cid, player=player)
    if g.player is None:
        g.player = player
    return g


def _set_class(g, cls, conf, signal):
    """Monotonic class update: only raise, never lower confidence."""
    if conf > g.cls_conf:
        g.cls = cls
        g.cls_conf = conf
        if signal not in g.signals:
            g.signals.append(signal)


def behavioral_labels(ctx):
    """Stage 1: refined hard class from a unit's own commands.

    A real unit cannot be both — so a unit that somehow carries BOTH a military
    and a villager hard-signal is treated as CONFLICTED (left unknown, not a
    seed). These are rare and stem from id ambiguity (imperfect SPECIAL/UNGARRISON
    shift-decode or id reuse); forcing a class on them is what erodes the
    otherwise ~100% co-command class purity.
    """
    mil_sig = defaultdict(int)
    vil_sig = defaultdict(int)
    for a in ctx.match.actions:
        if not a.player:
            continue
        at = _at(a)
        is_mil = at in MIL_CMDS
        is_vil = at in VIL_CMDS
        if not (is_mil or is_vil):
            continue
        for o in (a.payload or {}).get("object_ids", []):
            cid = ctx.canon(o)
            if cid in ctx.building_ids:
                continue
            _ensure(ctx, cid, a.player.name)
            (mil_sig if is_mil else vil_sig)[cid] += 1
    # gather-on-resource is a villager-hard signal (recorded during build_context)
    for cid, g in ctx.guesses.items():
        if g.behavior.get("gathers"):
            vil_sig[cid] += 1

    # BUILD/REPAIR/WALL is the only UNAMBIGUOUS villager signal: military units can
    # never build. GATHER, by contrast, is contaminated -- a player who co-selects
    # military with villagers and right-clicks a resource gives the military a phantom
    # "gather" it physically cannot perform. So we record gather separately (soft) and
    # let the production alignment, not the gather, decide a gather-only unit's class.
    build_sig = defaultdict(int)
    for a in ctx.match.actions:
        if not a.player or _at(a) not in VIL_CMDS:
            continue
        for o in (a.payload or {}).get("object_ids", []):
            cid = ctx.canon(o)
            if cid not in ctx.building_ids:
                build_sig[cid] += 1

    for cid in set(mil_sig) | set(vil_sig):
        g = ctx.guesses.get(cid)
        if g is None:
            continue
        m = mil_sig.get(cid, 0)
        bld = build_sig.get(cid, 0)
        gth = g.behavior.get("gathers", 0)
        # flags consumed by the production-alignment stage
        if m:
            g.behavior["hard_mil"] = m
        if bld:
            g.behavior["hard_build"] = bld
        if m and bld:
            g.signals.append("conflict")            # genuine id ambiguity -> unknown
        elif bld:
            _set_class(g, "villager", CONF["hard_class"], "behavior")
        elif m:
            _set_class(g, "military", CONF["hard_class"], "behavior")
        elif gth:
            # gather-only: provisional villager, but LOW confidence so the production
            # alignment can promote it to military if it claims a military slot.
            _set_class(g, "villager", CONF["idrank_type"], "gather")


def cocommand_graph(ctx):
    """Stage 2a: weighted co-command edges between (non-building) units."""
    weight = Counter()
    for _player, ids in ctx.group_cmds:
        units = [i for i in ids if i not in ctx.building_ids]
        if 2 <= len(units) <= 40:
            for x, y in combinations(units, 2):
                weight[(x, y)] += 1
    return weight


def propagate_class(ctx, weight, min_weight=2, iters=12):
    """Stage 2b: spread hard class across the co-command graph.

    Co-command is ~100% class-consistent on hard labels, so we propagate by
    UNANIMITY rather than majority: an unknown unit takes a class only if all of
    its (strong, weight >= min_weight) labeled group-mates agree. This keeps the
    100% purity of the signal instead of letting a lone off-class neighbour drag
    a unit across the boundary. Only fills 'unknown' units; hard/header labels
    are never overwritten.
    """
    adj = defaultdict(list)
    for (x, y), w in weight.items():
        if w < min_weight:
            continue
        adj[x].append((y, w))
        adj[y].append((x, w))

    for _ in range(iters):
        updates = {}
        for cid, nbrs in adj.items():
            g = ctx.guesses.get(cid)
            if g is None or g.cls != "unknown":
                continue
            classes = {ctx.guesses[n].cls for n, _ in nbrs
                       if n in ctx.guesses and ctx.guesses[n].cls != "unknown"}
            if len(classes) == 1:
                updates[cid] = next(iter(classes))
        if not updates:
            break
        for cid, cls in updates.items():
            _set_class(ctx.guesses[cid], cls, CONF["cocmd_class"], "cocmd")


# --- Stage 3: production timeline -------------------------------------------
GENERIC_TYPES = {"unit", "military"}

# Unit type -> production LINE (= the building that makes it). Units from different
# buildings are different lines; the merged FIFO blurs them (a knight reads as a
# concurrent archer), so we align each line's FIFO separately. Default 'arch' for
# unmapped tokens is deliberately overridden below to 'unique' so a stray unique
# unit does not pollute the archery line.
_TYPE_LINE = {
    # archery range
    "archer": "arch", "crossbowman": "arch", "arbalester": "arch", "skirmisher": "arch",
    "eliteskirmisher": "arch", "imperialskirmisher": "arch", "slinger": "arch",
    "cavalryarcher": "arch", "heavycavalryarcher": "arch", "handcannoneer": "arch",
    "genitour": "arch", "elitegenitour": "arch", "rattanarcher": "arch", "elephantarcher": "arch",
    "mangudai": "arch", "warwagon": "arch", "chukonu": "arch", "genoesecrossbowman": "arch",
    "plumedarcher": "arch", "longbowman": "arch", "warwagon": "arch",
    # barracks
    "militia": "inf", "manatarms": "inf", "longswordsman": "inf", "twohandedswordsman": "inf",
    "champion": "inf", "spearman": "inf", "pikeman": "inf", "halberdier": "inf",
    "eaglescout": "inf", "eaglewarrior": "inf", "eliteeaglewarrior": "inf", "champiscout": "inf",
    "huskarl": "inf", "woadraider": "inf", "berserk": "inf", "jaguarwarrior": "inf",
    "throwingaxeman": "inf", "gbeto": "inf", "shotelwarrior": "inf", "condottiero": "inf",
    "karambitwarrior": "inf", "teutonicknight": "inf", "samurai": "inf", "legionary": "inf",
    # stable
    "scoutcavalry": "cav", "lightcavalry": "cav", "hussar": "cav", "winghussar": "cav",
    "knight": "cav", "cavalier": "cav", "paladin": "cav", "camelrider": "cav",
    "heavycamelrider": "cav", "camelscout": "cav", "battleelephant": "cav",
    "steppelancer": "cav", "konnik": "cav", "tarkan": "cav", "magyarhuszar": "cav",
    "boyar": "cav", "cataphract": "cav", "warelephant": "cav", "leitis": "cav",
    "keshik": "cav", "coustillier": "cav", "shrivamsharider": "cav",
    # siege workshop / castle siege
    "batteringram": "siege", "cappedram": "siege", "siegeram": "siege", "mangonel": "siege",
    "onager": "siege", "siegeonager": "siege", "scorpion": "siege", "heavyscorpion": "siege",
    "trebuchet": "siege", "bombardcannon": "siege", "siegetower": "siege", "hussitewagon": "siege",
    "armoredelephant": "siege", "siegeelephant": "siege",
    # monastery
    "monk": "monk", "missionary": "monk", "warriorpriest": "monk", "imam": "monk",
}


def _line_of(t):
    return _TYPE_LINE.get((t or "").replace(" ", "").lower(), "unique")


def _coprod_lines(ctx, player):
    """Production-TREE line map from observed CO-PRODUCTION: tokens queued at the
    same building share that building's serial FIFO, so they must be claimed as ONE
    line. This recovers the real hosting building for unique/regional units the
    name-based _TYPE_LINE can't know: e.g. a castle queuing jaguar warriors AND
    trebuchets is one stream (the name map wrongly puts JW with barracks infantry),
    and an Armenian castle making composite bowmen + trebuchets is one stream (CB is
    otherwise a synthetic 'unique' line that claims early and steals militia).
    Returns {token: (sem_label, component_id)}; sem_label is the production-weighted
    majority _TYPE_LINE of the component (drives the siege/monk patrol fence and the
    raider-pool count)."""
    nbrs = defaultdict(set)
    counts = Counter()
    for b, q in ctx.queues.items():
        if ctx.owner.get(b) != player:
            continue
        toks = {u for _, u in q if u != "villager"}
        for u in toks:
            nbrs[u] |= toks
        for _, u in q:
            if u != "villager":
                counts[u] += 1
    out = {}
    seen = set()
    for start in nbrs:
        if start in seen:
            continue
        comp, stack = set(), [start]
        while stack:
            x = stack.pop()
            if x in comp:
                continue
            comp.add(x)
            stack.extend(nbrs[x] - comp)
        seen |= comp
        sem = Counter()
        for m in comp:
            sem[_line_of(m)] += counts[m]
        lab = sem.most_common(1)[0][0]
        key = (lab, min(comp))
        for m in comp:
            out[m] = key
    return out


def _set_type(g, t, conf, signal):
    """Monotonic type update; never downgrade a specific type to a generic one."""
    if not t:
        return
    if g.type not in GENERIC_TYPES and t in GENERIC_TYPES:
        return
    if (g.type in GENERIC_TYPES and t not in GENERIC_TYPES) or conf > g.type_conf:
        g.type = t
        g.type_conf = max(g.type_conf, conf) if g.type == t else conf
        if signal not in g.signals:
            g.signals.append(signal)


def _apply_unqueues(queue, unqs, ctx, player, blocks):
    """Remove unqueued units from a building's queue. Each Unqueue(t) cancels the
    most-recently-queued unit still PENDING (completion > t) at that moment -- players
    cancel from the BACK of the queue (the excess they just over-queued), which matches
    the gRPC spawns far better than honouring the raw slot index. Removing a unit also
    speeds up everything behind it, so completion is recomputed between unqueues.
    Research items (blocks) occupy the same FIFO (shifting completions later) but are
    never themselves canceled here."""
    if not unqs:
        return queue
    q = list(queue)
    for utime, _slot in sorted(unqs):
        if not q:
            break
        items = sorted([(qt, 0, i) for i, (qt, _u) in enumerate(q)]
                       + [(rt, 1, dur) for rt, dur in blocks])
        done = 0.0
        comp = {}
        for ts, kind, x in items:
            start = max(ts, done)
            if kind == 1:
                done = start + x
            else:
                done = start + ctx.train_time(player, q[x][1], start)
                comp[x] = done
        pend = [i for i in range(len(q)) if comp.get(i, 0.0) > utime]  # not yet completed
        if not pend:
            continue
        q = q[:pend[-1]] + q[pend[-1] + 1:]                   # cancel the newest pending
    return q


def production_timeline(ctx):
    """Stage 3: per-building serial completion (max(queue,prev_done)+train_time).

    Tech-aware: research items share each building's FIFO (production pauses for the
    tech's duration -- age-ups block the TC's villagers, Man-at-Arms blocks the rax);
    train times are upgrade-aware (Crossbowman 27s vs Archer 35s), age-aware (eagle
    scouts), and civ/speed-tech-aware (Conscription etc.) via ctx.train_time.

    Returns (full, mil): per-player lists of (completion_time, type), full
    including villagers, mil military-only.
    """
    full = defaultdict(list)
    mil = defaultdict(list)
    # buildings that train villagers (TCs): the 'tc' blocks scope applies research
    # pauses only there (age-ups etc. stall the villager stream; the military FIFO
    # alignment is lag-calibrated and must not be perturbed).
    vil_blds = {b for b, q in ctx.queues.items() if any(u == "villager" for _, u in q)}
    for b, q in ctx.queues.items():
        player = ctx.owner.get(b)
        blocks = ctx.research_blocks.get(b, []) if PRIORS["blocks"] and (
            PRIORS["blocks_scope"] == "all" or b in vil_blds) else []
        cutoff = ctx.resign.get(player, float("inf"))   # stop producing at resign
        q = _apply_unqueues(sorted(q), ctx.unqueues.get(b, []), ctx, player, blocks)
        items = sorted([(qt, 0, u) for qt, u in q]
                       + [(rt, 1, dur) for rt, dur in blocks])
        done = 0.0
        for ts, kind, x in items:
            start = max(ts, done)
            if kind == 1:               # research occupies the queue, spawns nothing
                done = start + x
                continue
            u = x
            done = start + ctx.train_time(player, u, start)
            if done > cutoff:
                break       # FIFO: this + every later unit in this building never trains
            # carry the building id so units completing on the SAME tick are ordered by
            # building (the engine processes buildings in id order within a tick) -- this
            # resolves sub-tick ties the completion time alone can't.
            full[player].append((done, b, u))
            if u != "villager":
                mil[player].append((done, b, u))
    for d in (full, mil):
        for player in d:
            d[player].sort()                       # (completion, building_id) order
            d[player][:] = [(t, u) for t, _b, u in d[player]]
    ctx.prod_full, ctx.prod_mil = full, mil
    return full, mil


def count_calibrated_mil_stream(ctx, player):
    """Time each military completion using the total_objects increments (real spawn
    events) instead of guessed train times. Returns sorted [(completion_t, type)].
    This fixes ordering for dense/multiqueue production the serial model gets wrong."""
    ts = ctx.timeseries.get(player) or []
    incs = []
    prev = None
    for t, tot in ts:
        if prev is not None and tot > prev:
            incs.extend([t] * (tot - prev))
        prev = tot if prev is None else max(prev, tot)
    events = sorted((qt, u) for b, q in ctx.queues.items() if ctx.owner.get(b) == player
                    for qt, u in q if u != "villager")
    stream = []
    ii = 0
    for qt, u in events:
        while ii < len(incs) and incs[ii] < qt:
            ii += 1
        ct = incs[ii] if ii < len(incs) else qt + 30
        stream.append((ct, u))
        ii += 1
    stream.sort()
    return stream


def _align(ids_sorted, comp_types):
    """Proportional rank alignment: i-th created unit -> i-th completion type."""
    out = {}
    m = len(comp_types)
    n = len(ids_sorted)
    if m == 0:
        return out
    for i, cid in enumerate(ids_sorted):
        j = round(i * (m - 1) / (n - 1)) if n > 1 else 0
        out[cid] = comp_types[j]
    return out


def _role_of(g):
    b = g.behavior
    if g.cls == "villager":
        return "eco"
    if b.get("attacks_building") and not b.get("patrols") and b.get("moves", 0) <= 6:
        return "siege"
    if b.get("patrols"):
        return "cavalry"
    return "military"


def assign_types(ctx, squads):
    """Stage 4: GROUP-based typing.

    Each 'blob' -- a co-command squad, or a lone unit -- is typed as ONE unit, so
    co-moving groups come out homogeneous (the strongest signal we have:
    co-commanded units are ~100% the same type). Military types are handed out
    from the player's production stream with a REMAINING-BUDGET constraint, so
    homogenizing can't let the dominant unit (huszar) absorb the minorities
    (cav-archer/treb) -- global proportions still track production.

    This replaces the old per-unit id-rank typing + inert gap-fill smoothing.
    """
    for cid, g in ctx.guesses.items():
        if cid in ctx.building_ids or cid in ctx.start_ids or cid in ctx.gaia_all:
            continue
        g.role = _role_of(g)

    squad_of = {}
    for sid, c in enumerate(squads):
        for cid in c:
            squad_of[cid] = sid

    blobs = defaultdict(list)
    for cid, g in ctx.guesses.items():
        if cid in ctx.building_ids or cid in ctx.start_ids or cid in ctx.gaia_all:
            continue
        key = ("sq", squad_of[cid]) if cid in squad_of else ("solo", cid)
        blobs[key].append(cid)

    by_player = defaultdict(list)
    for members in blobs.values():
        by_player[ctx.guesses[members[0]].player].append(members)

    def blob_class(members):
        known = [ctx.guesses[m].cls for m in members if ctx.guesses[m].cls != "unknown"]
        return Counter(known).most_common(1)[0][0] if known else None

    def med(members):
        s = sorted(members)
        return s[len(s) // 2]

    for player, blist in by_player.items():
        # ONE budget over the full production stream (villagers + every military
        # type), so blobs are handed types in creation order, constrained by what
        # the player actually produced. This keeps proportions honest across BOTH
        # classes -- unknowns can't all pile into the single most-common type.
        full = [t for _, t in ctx.prod_full.get(player, [])]
        F = len(full)
        mil_types = set(t for t in full if t != "villager") or {"military"}
        target = Counter(full)        # production counts per type (the quota)
        assigned = Counter()          # running assignment

        all_ids = sorted(cid for members in blist for cid in members)
        Nall = len(all_ids)
        rank = {cid: i for i, cid in enumerate(all_ids)}

        def pos(cid):
            return round(rank[cid] * (F - 1) / (Nall - 1)) if (Nall > 1 and F > 0) else 0

        # Pick the in-window candidate furthest BELOW its production quota, so
        # minorities (cav-archer/cart/treb) get their share and large blobs still
        # fall to the large types -- proportions track production without one
        # type starving the rest.
        def pick(cand, s):
            return min(cand, key=lambda c: (assigned[c] + s) / max(1, target.get(c, 1)))

        HARD = CONF["hard_class"]
        for members in sorted(blist, key=med):
            s = len(members)
            cls = blob_class(members)
            window = full[min(pos(m) for m in members):max(pos(m) for m in members) + 1] if F else []
            mil_cand = set(w for w in window if w != "villager") or mil_types
            # A blob that carries BOTH hard-villager and hard-military members is a
            # mass-select (select-all + move), NOT a real co-typed squad. Co-command
            # co-typing is invalid here, so SOFT members are typed individually by
            # their own production rank instead of inheriting the blob majority.
            hetero = (any(ctx.guesses[m].cls_conf >= HARD and ctx.guesses[m].cls == "military" for m in members)
                      and any(ctx.guesses[m].cls_conf >= HARD and ctx.guesses[m].cls == "villager" for m in members))
            # base type for the blob's SOFT (no-hard-signal) members
            if cls == "villager":
                base_t, base_conf = "villager", CONF["squad_type"]
            elif cls == "military":
                base_t, base_conf = pick(mil_cand, s), CONF["squad_type"]
            else:  # no class signal -> full window decides vil/mil
                cand = set(window) or set(full) or {"unit"}
                base_t, base_conf = pick(cand, s), CONF["idrank_type"]
            # A HARD individual class (gather->villager, patrol/stance/attack-ground
            # ->military) must NEVER be overridden by the blob majority. Big mixed
            # "mass-select" components otherwise paint their minority class wrong.
            for m in members:
                gm = ctx.guesses[m]
                if gm.cls_conf >= HARD and gm.cls == "military":
                    t = base_t if base_t != "villager" else pick(mil_cand, 1)
                    _set_type(gm, t, CONF["squad_type"], "group")
                    _set_class(gm, "military", CONF["squad_type"], "group")
                    assigned[t] += 1
                elif gm.cls_conf >= HARD and gm.cls == "villager":
                    _set_type(gm, "villager", CONF["squad_type"], "group")
                    _set_class(gm, "villager", CONF["squad_type"], "group")
                    assigned["villager"] += 1
                elif hetero and F:
                    # mass-select: type this soft unit by its own production rank
                    t = full[pos(m)]
                    _set_type(gm, t, CONF["idrank_type"], "group")
                    _set_class(gm, "villager" if t == "villager" else "military",
                               CONF["idrank_type"], "group")
                    assigned[t] += 1
                else:
                    _set_type(gm, base_t, base_conf, "group")
                    _set_class(gm, "villager" if base_t == "villager" else "military",
                               base_conf, "group")
                    assigned[base_t] += 1


class _UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def form_squads(ctx, weight, min_weight=2):
    """Stage 4a: connected components of the strong co-command graph = squads."""
    uf = _UF()
    for (x, y), w in weight.items():
        if w >= min_weight and x not in ctx.building_ids and y not in ctx.building_ids:
            uf.union(x, y)
    comps = defaultdict(list)
    for cid, g in ctx.guesses.items():
        if cid in ctx.building_ids or cid in ctx.start_ids or cid in ctx.gaia_all:
            continue
        comps[uf.find(cid)].append(cid)
    squads = [c for c in comps.values() if len(c) >= 3]
    for sid, c in enumerate(squads):
        for cid in c:
            ctx.guesses[cid].squad_id = sid
    return squads


def dp_align_player(ctx, player, TOL=4.0, BIG=1e9):
    """Order-preserving (instance_id) alignment of a player's commanded military to
    the FIFO production stream. Lag-free: matches by spawn ORDER, with the hard
    constraint that a unit's slot is at-or-before its first command (spawn precedes
    command). Globally one-to-one (a DP), so each produced unit claims its own slot
    -- which resolves dense interleavings (skirmisher/spearman/slinger; knight amid
    archers) that command-time matching blurs. Returns {cid: type}."""
    units = sorted(c for c, g in ctx.guesses.items()
                   if g.player == player and g.cls == "military"
                   and c not in ctx.building_ids and c not in ctx.gaia_all
                   and c not in ctx.start_ids                       # starting units aren't produced
                   and g.behavior.get("first_seen") is not None)   # instance_id order
    fifo = sorted(ctx.prod_mil.get(player, []))
    N, M = len(units), len(fifo)
    if N == 0 or M == 0 or N > M:
        return {}
    ft = [t for t, _ in fifo]; fu = [u for _, u in fifo]
    fs = [ctx.guesses[c].behavior["first_seen"] for c in units]
    INF = float("inf")
    dp = [[INF] * (M + 1) for _ in range(N + 1)]
    bt = [[0] * (M + 1) for _ in range(N + 1)]
    for j in range(M + 1):
        dp[0][j] = 0.0
    for i in range(1, N + 1):
        di, dim1, bti, fsi = dp[i], dp[i - 1], bt[i], fs[i - 1]
        for j in range(i, M + 1):
            skip = di[j - 1]
            # spawn precedes command; among valid slots prefer the one closest to the
            # command (lowest lag). The order constraint (monotonic DP) keeps the
            # instance_id ordering; this resolves the dense interleaving + knights.
            lag = fsi - ft[j - 1]
            cst = BIG if lag < -TOL else (lag if lag > 0 else 0.0)
            match = dim1[j - 1] + cst
            if match <= skip:
                di[j] = match; bti[j] = 1
            else:
                di[j] = skip
    i, j = N, M; out = {}
    while i > 0 and j > 0:
        if bt[i][j] == 1:
            out[units[i - 1]] = fu[j - 1]; i -= 1; j -= 1
        else:
            j -= 1
    return out


def align_production(ctx, TOL=4.0, SKIP=22.0, EPS=0.5, BIG=1e9):
    """Unified class+type assignment from the per-player military FIFO.

    Aligns every candidate unit (anything not a confirmed builder-villager) to the
    military production stream by instance_id ORDER (lag-free spawn order) with a
    match/skip DP:
      - match unit i -> military slot j   (cost = command lag; spawn must precede cmd)
      - skip unit i   -> the unit is a villager (cost SKIP; +inf for a hard-military
        unit that MUST occupy a slot)
      - skip slot j   -> a produced unit that was never individually commanded (cost 0)
    A matched unit becomes military with its slot's exact type; an unmatched candidate
    keeps villager. This is where the building/queue -- not the contaminated gather --
    sets a unit's class, so a slinger from an archery range is military even with a
    phantom gather. Returns the set of matched cids."""
    matched_all = set()
    players = set(g.player for g in ctx.guesses.values() if g.player)
    for player in players:
        fifo = sorted(ctx.prod_mil.get(player, []))
        M = len(fifo)
        if M == 0:
            continue
        ft = [t for t, _ in fifo]
        fu = [u for _, u in fifo]
        cand = []
        for c, g in ctx.guesses.items():
            if g.player != player:
                continue
            if c in ctx.building_ids or c in ctx.gaia_all or c in ctx.start_ids:
                continue
            if g.behavior.get("first_seen") is None:
                continue
            if g.behavior.get("hard_build"):
                continue                       # confirmed villager: never military
            cand.append(c)
        cand.sort()                            # instance_id == spawn order
        if not cand:
            continue
        fsmap = {c: ctx.guesses[c].behavior["first_seen"] for c in cand}
        hmmap = {c: bool(ctx.guesses[c].behavior.get("hard_mil")) for c in cand}
        patmap = {c: bool(ctx.guesses[c].behavior.get("patrols")) for c in cand}
        # Split the FIFO into per-LINE streams and claim them SMALLEST-FIRST: a
        # distinctive line (monk: 2 slots) claims its units before the dominant
        # archery line can absorb them. Each line's match/skip DP only sees the units
        # not yet claimed by a more specific line.
        lines = defaultdict(list)
        if PRIORS["coprod_lines"]:
            lmap = _coprod_lines(ctx, player)
            for t, u in fifo:
                lines[lmap.get(u, (_line_of(u), u))].append((t, u))
        else:
            for t, u in fifo:
                lines[(_line_of(u), "")].append((t, u))
        # Phase 1 -- LINE: claim units to lines SMALLEST-FIRST with STRICT lag, so the
        # exact-spawn owner wins each slot and a distinctive line is not absorbed by
        # archery. This decides which building-line each unit came from (and its class).
        claimed = {}
        raider_pool = sum(len(v) for L, v in lines.items() if L[0] in ("cav", "inf"))
        for L in sorted(lines, key=lambda L: (len(lines[L]), L)):
            fifo_L = lines[L]
            ftL = [t for t, _ in fifo_L]
            fuL = [u for _, u in fifo_L]
            pool = [c for c in cand if c not in claimed]
            # A patrol-microd unit is a mobile raider (scout/cav/infantry). A set-and-fire
            # siege/monk line should not absorb it -- UNLESS that line is the player's main
            # army (mass hussite/monk push). Fence patrollers out of a SMALL siege/monk line
            # only when cav+inf raider production outnumbers it, so it can't steal raiders
            # from the cav/inf line they belong to. (Unified, no per-player branch.)
            if L[0] in ("siege", "monk") and len(fifo_L) >= 4 and raider_pool > len(fifo_L):
                pool = [c for c in pool if not patmap[c]]
            if not pool:
                continue
            fsL = [fsmap[c] for c in pool]
            hmL = [hmmap[c] for c in pool]
            mm = _match_dp(pool, fsL, hmL, ftL, fuL, TOL, SKIP, EPS, BIG, pack=False, strict=True)
            for c in mm:
                claimed[c] = L
        # Phase 2 -- TYPE: within each line, re-align its claimed units by EARLIEST-
        # PACKING (every time-valid slot equal), so a held unit takes its true early
        # slot instead of stealing a later same-line slot of another type via low lag.
        byline = defaultdict(list)
        for c, L in claimed.items():
            byline[L].append(c)
        for L, cids in byline.items():
            fifo_L = lines[L]
            ftL = [t for t, _ in fifo_L]
            fuL = [u for _, u in fifo_L]
            cs = sorted(cids)
            fsL = [fsmap[c] for c in cs]
            hmL = [True] * len(cs)
            mm = _match_dp(cs, fsL, hmL, ftL, fuL, TOL, SKIP, EPS, BIG, pack=True)
            for c in cs:
                g = ctx.guesses[c]
                g.type = mm.get(c, fuL[0])
                g.type_conf = CONF["squad_type"]
                g.cls = "military"
                g.cls_conf = max(g.cls_conf, CONF["squad_type"])
                matched_all.add(c)
        # Leftover-raider rescue: a candidate the primary alignment SKIPPED that attacked
        # an enemy building is ~85% military in truth (a raiding scout/militia the soft skip
        # dropped to villager). Tolerate a FEW phantom gathers (co-selected with villagers
        # right-clicking a resource) by requiring building-attacks to dominate (ab>=2*gh).
        # Leftover-SCOUT rescue: a skipped candidate that ONLY moves -- scouts/lures but never
        # gathers/builds/attacks-a-building -- is a scout/eagle dropped to villager. To avoid
        # grabbing a real villager from a select-all ball, require a SMALL co-command squad
        # with a military member and NO hard-villager (a real scouting pack). Neither branch
        # disturbs the primary one-to-one alignment (we only rescue units the DP left behind).
        SCOUT_MOVES = 5
        SCOUT_SQUAD_MAX = 10
        if M:
            sq_members = defaultdict(list)
            for mm_, gm in ctx.guesses.items():
                if gm.squad_id is not None:
                    sq_members[gm.squad_id].append(mm_)
            sq_mil_type = {}
            for sid, mem in sq_members.items():
                votes = Counter(ctx.guesses[m].type for m in mem
                                if ctx.guesses[m].cls == "military"
                                and ctx.guesses[m].type not in GENERIC_TYPES)
                if votes:
                    sq_mil_type[sid] = votes.most_common(1)[0][0]
            for c in cand:
                if c in claimed:
                    continue
                g = ctx.guesses[c]
                b = g.behavior
                ab = b.get("attacks_building", 0)
                gh = b.get("gathers", 0)
                raider = ab >= 1 and ab >= 2 * gh
                scout = (not raider and not gh and not b.get("builds")
                         and not ab and b.get("moves", 0) >= SCOUT_MOVES)
                rescued_type = None
                if scout:
                    sid = g.squad_id
                    if sid is None:
                        continue
                    mates = sq_members.get(sid, [])
                    if len(mates) > SCOUT_SQUAD_MAX:
                        continue
                    has_mil = any(ctx.guesses[m].cls == "military" for m in mates)
                    has_hard_vil = any(ctx.guesses[m].cls == "villager"
                                       and ctx.guesses[m].cls_conf >= CONF["hard_class"]
                                       for m in mates)
                    if not has_mil or has_hard_vil:
                        continue
                    rescued_type = sq_mil_type.get(sid)
                elif not raider:
                    continue
                if rescued_type is None:
                    fs = b["first_seen"]
                    k = bisect.bisect_right(ft, fs + TOL) - 1
                    if k < 0:
                        k = 0
                    rescued_type = fu[k]
                g.type = rescued_type
                g.type_conf = CONF["idrank_type"]
                g.cls = "military"
                g.cls_conf = max(g.cls_conf, CONF["squad_type"])
                matched_all.add(c)
    return matched_all


def _match_dp(cand, fs, hardmil, ft, fu, TOL, SKIP, EPS, BIG, pack, strict=False):
    """Order-preserving match/skip DP. Returns {cid: slot_type}.
      - match unit i -> slot j: cost 0 if pack-or-hardmil (earliest slot wins via the
        EPS skip cost), else the command lag (gates ambiguous units to nearby slots).
      - skip unit i: cost SKIP (BIG for a hard-military unit that must occupy a slot).
      - skip slot j: cost EPS (favours packing units onto their earliest valid slots)."""
    N, M = len(cand), len(ft)
    if N == 0 or M == 0:
        return {}
    INF = float("inf")
    dp = [[INF] * (M + 1) for _ in range(N + 1)]
    bt = [[0] * (M + 1) for _ in range(N + 1)]   # 0 skip-slot, 1 match, 2 skip-unit
    dp[0][0] = 0.0
    for j in range(1, M + 1):
        dp[0][j] = j * EPS
    for i in range(1, N + 1):
        su = BIG if hardmil[i - 1] else SKIP
        fsi = fs[i - 1]
        # strict: cost is the command lag for EVERYONE, so the unit that spawned just
        # before a slot (lowest lag) wins it -- the exact-spawn true owner beats a
        # held concurrent unit. Used for per-line claiming where stealing a slot means
        # a cross-line type error.
        free = (pack or hardmil[i - 1]) and not strict
        di, dim1, bti = dp[i], dp[i - 1], bt[i]
        di[0] = dim1[0] + su
        bti[0] = 2
        for j in range(1, M + 1):
            best = dim1[j] + su
            arg = 2
            v0 = di[j - 1] + EPS
            if v0 < best:
                best = v0
                arg = 0
            lag = fsi - ft[j - 1]
            if lag >= -TOL:
                mc = dim1[j - 1] + (0.0 if free else (lag if lag > 0 else 0.0))
                if mc < best:
                    best = mc
                    arg = 1
            di[j] = best
            bti[j] = arg
    i, j = N, M
    out = {}
    while i > 0 or j > 0:
        a = bt[i][j]
        if a == 1:
            out[cand[i - 1]] = fu[j - 1]
            i -= 1
            j -= 1
        elif a == 2:
            i -= 1
        else:
            j -= 1
    return out


def refine_military(ctx, iso_gate=14.0, TOL=4.0, smooth_thresh=0.6):
    """UNIFIED class+type assignment (same for every player):
      1. align_production: match/skip DP -> class + base type from the FIFO.
      2. co-command smoothing: snap a HOMOGENEOUS squad to its majority type -- this
         corrects held units whose command lag drifted them off their FIFO slot (a
         defensive ball is commanded together, so it is homogeneous); a genuinely
         mixed squad has no majority and is left to the alignment.
      3. FIFO-isolation override: a matched unit whose spawn time lands in a clean
         single-type production run IS that type (rescues time-separated minorities
         like militia that the order-DP can drift on)."""
    matched = align_production(ctx)
    # 2. co-command smoothing of homogeneous squads
    members = defaultdict(list)
    for c in matched:
        sid = ctx.guesses[c].squad_id
        if sid is not None:
            members[sid].append(c)
    for mem in members.values():
        votes = Counter(ctx.guesses[c].type for c in mem)
        dom, dn = votes.most_common(1)[0]
        if dn / sum(votes.values()) >= smooth_thresh:
            for c in mem:
                ctx.guesses[c].type = dom
    players = set(ctx.guesses[c].player for c in matched)
    for player in players:
        pm = sorted(ctx.prod_mil.get(player, []))
        PT = [t for t, _ in pm]
        PU = [u for _, u in pm]
        if not PT:
            continue
        iso = [min((abs(PT[x] - PT[k]) for x in range(len(PT)) if PU[x] != PU[k]),
                   default=float("inf")) for k in range(len(PT))]
        for c in matched:
            if ctx.guesses[c].player != player:
                continue
            fs = ctx.guesses[c].behavior.get("first_seen")
            if fs is None:
                continue
            k = bisect.bisect_right(PT, fs + TOL) - 1
            if 0 <= k < len(PU) and iso[k] >= iso_gate:
                ctx.guesses[c].type = PU[k]
                ctx.guesses[c].type_conf = CONF["hard_class"]

    # MONK override (unified, no per-player branch). A meso monk heals/blesses at its
    # monastery and converts enemy units, but never builds, gathers, or attack-moves --
    # so the spawn-order FIFO alignment (which matches on first-command lag) hands its
    # slot to a same-time eagle scout, leaving the monk typed eaglescout or villager.
    # Recover it from behaviour: the player produced monks, the unit ordered its OWN
    # monastery (bld_order = relic/heal garrison), repeatedly "attacked" enemy mobiles
    # (attacks_building = the convert order), and never built/gathered. The conjunction
    # is monk-exclusive across all labelled games (0 false positives).
    monk_players = {p for p, comp in ctx.prod_mil.items()
                    if any(u == "monk" for _, u in comp)}
    for c, g in ctx.guesses.items():
        if c in ctx.building_ids or c in ctx.gaia_all or c in ctx.start_ids:
            continue
        b = g.behavior
        if g.player not in monk_players or b.get("builds") or b.get("gathers") or b.get("hard_build"):
            continue
        strong = b.get("bld_order", 0) >= 1 and b.get("attacks_building", 0) >= 5
        # an already-military unit that garrisons its own monastery is a monk even
        # without a logged convert (returning to a building is monk-exclusive among military)
        weak = g.cls == "military" and b.get("bld_order", 0) >= 1
        if strong or weak:
            g.type = "monk"
            g.type_conf = CONF["hard_class"]
            g.cls = "military"
            g.cls_conf = max(g.cls_conf, CONF["hard_class"])


def refine_ball_types(ctx, squads):
    """For BALL players (a heterogeneous mass-select squad mixes hard-villager and
    hard-military, so co-command can't separate types), re-type ALL their military
    with the order-preserving DP alignment to the FIFO stream. Matching by instance_id
    ORDER (lag-free) resolves the dense interleaved production that command-time
    matching blurs -- the ball case where the squad/budget logic fails."""
    HARD = CONF["hard_class"]
    ball_players = set()
    for c in squads:
        hm = any(ctx.guesses[m].cls == "military" and ctx.guesses[m].cls_conf >= HARD for m in c)
        hv = any(ctx.guesses[m].cls == "villager" and ctx.guesses[m].cls_conf >= HARD for m in c)
        if hm and hv:
            ball_players.add(ctx.guesses[c[0]].player)
    for player in ball_players:
        for cid, t in dp_align_player(ctx, player).items():
            ctx.guesses[cid].type = t
            ctx.guesses[cid].type_conf = CONF["squad_type"]


def refine_separable_military(ctx, threshold=0.3):
    """Your pipeline for SEPARABLE players: attribute each military unit to the
    production stream by anchoring its first-command time (instance_id/production
    + correct multiqueue/train-time order), then snap minority squad outliers to
    the squad majority (co-command update). Applied only to players whose military
    is NOT dominated by a mass-select ball (where this fails -> keep current/ball
    handling). On separable play this beats budget-typing."""
    HARD = CONF["hard_class"]
    sm = defaultdict(list)
    for cid, g in ctx.guesses.items():
        if g.squad_id is not None:
            sm[g.squad_id].append(cid)
    ball = set()
    for mem in sm.values():
        hm = any(ctx.guesses[m].cls == "military" and ctx.guesses[m].cls_conf >= HARD for m in mem)
        hv = any(ctx.guesses[m].cls == "villager" and ctx.guesses[m].cls_conf >= HARD for m in mem)
        if hm and hv:
            ball |= set(mem)
    by_player = defaultdict(list)
    for cid, g in ctx.guesses.items():
        if g.cls == "military" and cid not in ctx.building_ids and cid not in ctx.gaia_all:
            by_player[g.player].append(cid)
    for player, mil in by_player.items():
        if not mil or sum(c in ball for c in mil) / len(mil) >= threshold:
            continue   # ball-blob player -> keep current/ball-refined handling
        pm = sorted(ctx.prod_mil.get(player, []))
        if not pm:
            continue
        PT = [c for c, _ in pm]; PU = [t for _, t in pm]    # FIFO spawn times (sec) + types
        # A unit's spawn time is the LAST FIFO completion at or before its first
        # command (a unit is only commanded after it spawns -> lag is never negative,
        # so "last-before" lands on its own slot; "nearest" would wrongly grab the
        # next unit that spawned during the command lag). A small +tolerance absorbs
        # the FIFO's own few-second prediction error. No co-command re-homogenizing.
        # isolation[k] = gap from slot k to the nearest DIFFERENT-typed slot. A slot
        # in a clean single-type run is trustworthy; one wedged among other types
        # (a hussite amid archers) is not -- leave those to the squad typing.
        isolation = []
        for k in range(len(PT)):
            isolation.append(min((abs(PT[x] - PT[k]) for x in range(len(PT)) if PU[x] != PU[k]),
                                 default=float("inf")))
        TOL, GATE = 4.0, 14.0
        for c in mil:
            fs = ctx.guesses[c].behavior.get("first_seen")
            if fs is None:
                continue
            k = bisect.bisect_right(PT, fs + TOL) - 1
            if 0 <= k < len(PU) and isolation[k] >= GATE:   # isolated -> trust FIFO
                ctx.guesses[c].type = PU[k]
                ctx.guesses[c].type_conf = CONF["hard_class"]


def finalize(ctx):
    """Stage 5: class-aware fallback -- a unit we know is MILITARY but couldn't
    type still gets the player's dominant military type, never bare 'unit'.

    AVAILABILITY VETO (civ/production prior): a specific predicted type that the
    owning player NEVER produced (not in their queue stream) and that is not one of
    their starting units is impossible -- it can only arise from a cross-player type
    leak (e.g. a mixed-player blob handing an Aztec unit the Armenian composite
    bowman). Re-type from the unit's own class: villager, or the player's dominant
    military production."""
    dom = {}
    for player, comp in ctx.prod_mil.items():
        c = Counter(t for _, t in comp)
        if c:
            dom[player] = c.most_common(1)[0][0]
    if PRIORS["avail_veto"]:
        prod = {}
        for b, q in ctx.queues.items():
            prod.setdefault(ctx.owner.get(b), set()).update(u for _, u in q)
        start_types = {}
        for p in ctx.match.players:
            st = set()
            for o in (p.objects or []):
                nm = _norm(getattr(o, "name", None))
                if nm:
                    st.add(nm)
            start_types[p.name] = st
        for g in ctx.guesses.values():
            if (g.type in GENERIC_TYPES or g.type == "villager" or g.player is None):
                continue
            if (g.type in prod.get(g.player, ()) or g.type in start_types.get(g.player, ())):
                continue
            g.type = "villager" if g.cls == "villager" else dom.get(g.player, "unit")
            g.type_conf = CONF["fallback"]
            g.signals.append("avail_veto")
    for g in ctx.guesses.values():
        if g.type in GENERIC_TYPES:
            if g.cls == "villager":
                _set_type(g, "villager", CONF["fallback"], "fallback")
            elif g.cls == "military" and g.player in dom:
                _set_type(g, dom[g.player], CONF["fallback"], "fallback")


def _run(match):
    """Run the full pipeline; returns the Context."""
    ctx = build_context(match)
    behavioral_labels(ctx)
    weight = cocommand_graph(ctx)
    propagate_class(ctx, weight)
    production_timeline(ctx)
    squads = form_squads(ctx, weight)
    assign_types(ctx, squads)
    refine_military(ctx)
    finalize(ctx)
    return ctx


def classify(match):
    """Run the full pipeline. Returns {canonical instance_id: UnitGuess}."""
    return _run(match).guesses


def build_type_map(match):
    """For process_replay: returns (flat, remap).

    flat  = {canonical instance_id: type_string} (class-only units -> 'villager'
            or 'unit').
    remap = {raw shifted id: canonical id} so the caller can canonicalize the
            ids it sees (collapsing the SPECIAL/UNGARRISON phantom duplicates).
    """
    ctx = _run(match)
    flat = {}
    for cid, g in ctx.guesses.items():
        # buildings and gaia (resources/herdables) are not mobile units -- the
        # visualizer renders them from building/gaia data, so don't emit a unit type.
        if cid in ctx.building_ids or cid in ctx.gaia_all:
            continue
        t = g.type if g.type not in GENERIC_TYPES else ("villager" if g.cls == "villager" else "unit")
        flat[cid] = t
    remap = {o: (o >> 8) for o in ctx.shifted}
    return flat, remap

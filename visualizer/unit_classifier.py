"""Group-first, confidence-based AoE2:DE unit-type classifier.

Standalone: takes a parsed mgz ``match`` (no Flask dependency). See
CLASSIFIER_REWORK.md for the full design and rationale.

Implemented so far: Stage 0 (context + id normalization), Stage 1 (refined
behavioral class), Stage 2 (co-command class propagation). Stages 3-5 (production
timeline, squad typing, finalize) are scaffolded and filled in subsequent phases.
"""

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

# Base DE train times (seconds), used by Stage 3. Default 30 for unknowns.
TRAIN_TIMES = {
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
# TODO(M2): prefer match.dataset train times (civ-complete, locale-proof) over
# this hardcoded table; defaults to 30s for anything missing.


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

    # starting (header) units: known owner + name -> seed class at top confidence
    for p in match.players:
        for o in (p.objects or []):
            cid = ctx.canon(o.instance_id)
            ctx.start_ids.add(cid)
            ctx.owner[cid] = p.name
            g = _ensure(ctx, cid, p.name)
            seeded = _seed_class_from_name(getattr(o, "name", None))
            if seeded:
                _set_class(g, seeded, CONF["header"], "header")

    # walk actions: owner, behavior, group commands, queues, building ids
    for a in match.actions:
        if not a.player:
            continue
        at = _at(a)
        payload = a.payload or {}
        t = a.timestamp.total_seconds()
        ids = [ctx.canon(o) for o in payload.get("object_ids", [])]

        # DE_QUEUE etc: object_ids are BUILDINGS, not acting units
        if at in BLD_SUBJECT_CMDS:
            for b in ids:
                ctx.building_ids.add(b)
                ctx.owner.setdefault(b, a.player.name)
            if at == "DE_QUEUE" and ids:
                u = _norm(payload.get("unit"))
                amt = payload.get("amount", 1) or 1
                for _ in range(amt):
                    ctx.queues[ids[0]].append((t, u))
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

    for cid in set(mil_sig) | set(vil_sig):
        g = ctx.guesses.get(cid)
        if g is None:
            continue
        m, v = mil_sig.get(cid, 0), vil_sig.get(cid, 0)
        if m and v:
            g.signals.append("conflict")           # ambiguous id -> leave unknown
        elif m:
            _set_class(g, "military", CONF["hard_class"], "behavior")
        elif v:
            _set_class(g, "villager", CONF["hard_class"], "behavior")


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


def production_timeline(ctx):
    """Stage 3: per-building serial completion (max(queue,prev_done)+train_time).

    Returns (full, mil): per-player lists of (completion_time, type), full
    including villagers, mil military-only.
    """
    full = defaultdict(list)
    mil = defaultdict(list)
    for b, q in ctx.queues.items():
        player = ctx.owner.get(b)
        done = 0.0
        for ts, u in sorted(q):
            done = max(ts, done) + TRAIN_TIMES.get(u, 30)
            full[player].append((done, u))
            if u != "villager":
                mil[player].append((done, u))
    for d in (full, mil):
        for player in d:
            d[player].sort()
    ctx.prod_full, ctx.prod_mil = full, mil
    return full, mil


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
        if cid in ctx.building_ids or cid in ctx.start_ids:
            continue
        g.role = _role_of(g)

    squad_of = {}
    for sid, c in enumerate(squads):
        for cid in c:
            squad_of[cid] = sid

    blobs = defaultdict(list)
    for cid, g in ctx.guesses.items():
        if cid in ctx.building_ids or cid in ctx.start_ids:
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

        for members in sorted(blist, key=med):
            s = len(members)
            cls = blob_class(members)
            window = full[min(pos(m) for m in members):max(pos(m) for m in members) + 1] if F else []
            if cls == "villager":
                t, conf = "villager", CONF["squad_type"]
            elif cls == "military":
                cand = set(w for w in window if w != "villager") or mil_types
                t, conf = pick(cand, s), CONF["squad_type"]
            else:  # no class signal -> full window decides vil/mil
                cand = set(window) or set(full) or {"unit"}
                t, conf = pick(cand, s), CONF["idrank_type"]
            assigned[t] += s
            bcls = "villager" if t == "villager" else "military"
            for m in members:
                _set_type(ctx.guesses[m], t, conf, "group")
                _set_class(ctx.guesses[m], bcls, conf, "group")


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
        if cid in ctx.building_ids or cid in ctx.start_ids:
            continue
        comps[uf.find(cid)].append(cid)
    squads = [c for c in comps.values() if len(c) >= 3]
    for sid, c in enumerate(squads):
        for cid in c:
            ctx.guesses[cid].squad_id = sid
    return squads


def finalize(ctx):
    """Stage 5: class-aware fallback -- a unit we know is MILITARY but couldn't
    type still gets the player's dominant military type, never bare 'unit'."""
    dom = {}
    for player, comp in ctx.prod_mil.items():
        c = Counter(t for _, t in comp)
        if c:
            dom[player] = c.most_common(1)[0][0]
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
        t = g.type if g.type not in GENERIC_TYPES else ("villager" if g.cls == "villager" else "unit")
        flat[cid] = t
    remap = {o: (o >> 8) for o in ctx.shifted}
    return flat, remap

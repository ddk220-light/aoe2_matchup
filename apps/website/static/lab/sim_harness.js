/*
 * Role: lab — the standalone battle-sim diagnostic harness (page half).
 *
 * The instrument this whole extraction sub-project exists to produce: watch ANY
 * fight, with diagnostic overlays, from a replayable seed, and settle a matchup
 * over N seeds in a worker — without the product page's chrome, pickers, deep
 * links or army-mode baggage.
 *
 * It imports the SAME modules the Battle Sim page imports (absolute paths,
 * because this page lives under /static/lab/):
 *   /static/js/engine/index.js   — state + physics, host-agnostic, seeded
 *   /static/js/sim_renderer.js   — every pixel of the battlefield
 * so anything seen here is bit-for-bit what production and the batch runs do.
 * The harness adds nothing to the engine except reading sim.combatStats, the
 * pure bookkeeping counters added for exactly this readout.
 *
 * Layering rules this file obeys:
 *   * it never mutates engine COMBAT state. Across the whole render stack there
 *     are exactly TWO deliberate writes to engine-owned cosmetic state, and this
 *     file performs the second of them:
 *       (a) sim_renderer.js writes `unit.faceRight` — see the rationale block at
 *           that assignment;
 *       (b) EVERY host that renders animated fights stamps `unit.attackSheet`
 *           after createSimulation — production simulate.js does it at 1263-1264
 *           and onRun() below does it identically. It is required host wiring,
 *           not a layering violation: the engine's triggerAttackAnim() sizes
 *           `animHold` from the sheet's frame count (0.4s without one), so a host
 *           that owns artwork has to hand it over. (The engine reads the sheet
 *           for that one duration and nothing else; the renderer gets its own
 *           copy through setTeamAssets.)
 *     Both fields are excluded from stateHash() and are never read by combat
 *     logic, so neither can affect parity or determinism — verified by the
 *     205-fight bit-exact gate.
 *   * overlays are drawn AFTER renderer.render(sim) onto the same context, in
 *     the renderer's logical 900x600 space (its DPR transform is re-applied
 *     here rather than assumed, so a resize mid-fight cannot skew them);
 *   * ENABLED_CIVS / spriteFor / sheetFor come from the CLASSIC constants.js +
 *     unit_sprites.js loaded before this module. `const ENABLED_CIVS` in a
 *     classic script is a global LEXICAL binding, NOT a window property — it is
 *     read as a bare identifier below, guarded by typeof.
 */

import {
    createSimulation,
    CANVAS_WIDTH,
    CANVAS_HEIGHT,
} from "/static/js/engine/index.js";
import { SimRenderer } from "/static/js/sim_renderer.js";

const $ = (id) => document.getElementById(id);
const STEP = 1 / 60; // the engine's fixed sub-step; everything is a multiple of it

// ===== PRESETS =====
// The six fights the migration write-up (docs/simulation-engine-migration.md
// §4-§7) picks apart. Each carries the count MODE it was measured under, which
// is the whole point: the "21 v 6" Slinger rows are corpus-rule counts, the
// "50 v 20" Cataphract row is the Battle Sim page's own rule, and comparing one
// to the other without saying which is an error the doc records having made.
// The counts below are what the rule produces at a 3000 budget — they are
// pre-filled so the setup is visible before Run, and Run recomputes them.
const PRESETS = [
    {
        id: "slinger-elephant",
        label: "Slinger 21 v Bengalis Elite Battle Elephant 6 (corpus)",
        mode: "corpus-rule",
        t1: { civ: "Incas", slug: "imp_slinger", name: "Slinger", count: 21 },
        t2: { civ: "Bengalis", slug: "elite_elephant", name: "Elite Battle Elephant", count: 6 },
        note: "Tape: 0 Slingers, 6 elephants @ 70.5%. The reference problem fight.",
    },
    {
        id: "slinger-paladin",
        label: "Slinger 21 v Huns Paladin 7 (corpus)",
        mode: "corpus-rule",
        t1: { civ: "Incas", slug: "imp_slinger", name: "Slinger", count: 21 },
        t2: { civ: "Huns", slug: "paladin", name: "Paladin", count: 7 },
        note: "Tape: 0 Slingers, 7 Paladins @ 63.3%.",
    },
    {
        id: "slinger-hussar",
        label: "Slinger 21 v Bulgarians Hussar 15 (corpus)",
        mode: "corpus-rule",
        t1: { civ: "Incas", slug: "imp_slinger", name: "Slinger", count: 21 },
        t2: { civ: "Bulgarians", slug: "hussar", name: "Hussar", count: 15 },
        note: "Tape: 0 Slingers, 13 Hussars @ 58.5%.",
    },
    {
        id: "slinger-cataphract",
        label: "Slinger 50 v Byzantines Elite Cataphract 20 (ui-rule)",
        mode: "ui-rule",
        t1: { civ: "Incas", slug: "imp_slinger", name: "Slinger", count: 50 },
        t2: { civ: "Byzantines", slug: "elite_cataphract_byzantines", name: "Elite Cataphract", count: 20 },
        note: "Production JS, unmodified: bimodal — Slingers won 3/5 seeds.",
    },
    {
        id: "arbalest-ckn",
        label: "Britons Arbalester 20 v Chinese Elite Chu Ko Nu 15 (explicit)",
        mode: "explicit",
        t1: { civ: "Britons", slug: "arbalester", name: "Arbalester", count: 20 },
        t2: { civ: "Chinese", slug: "elite_chu_ko_nu_chinese", name: "Elite Chu Ko Nu", count: 15 },
        note: "Ranged mirror — the row that survived every physics experiment.",
    },
    {
        id: "camelarcher-knight",
        label: "Berbers Camel Archer 18 v Franks Knight 18 (explicit)",
        mode: "explicit",
        t1: { civ: "Berbers", slug: "elite_camel_archer_berbers", name: "Elite Camel Archer", count: 18 },
        t2: { civ: "Franks", slug: "paladin", name: "Paladin", count: 18 },
        note: "Kite-vs-chase: the golden_cavvsranged shape. Franks Knight line = Paladin at Imperial.",
    },
];

// ===== COUNT RULES =====
// Units trained in batches cost their listed price for the WHOLE batch, so the
// corpus rule divides by the batch size before comparing spend. Same table the
// corpus scoring used; everything else is 1.
const TRAIN_BATCH = {
    blackwood_archer_tupi: 2,
    elite_blackwood_archer_tupi: 2,
};
const CORPUS_CAP = 21; // the corpus never fields more than 21 of the cheap side

// The Battle Sim page's rule (simulate.js calcUnitCost): unweighted sum, no cap.
function uiCost(cd) {
    return (cd.cost_wood || 0) + (cd.cost_food || 0) + (cd.cost_gold || 0);
}
// The corpus/tape rule: gold is 1.5x (it is the scarce resource), then per-unit
// price is the batch price divided by the batch size.
function corpusCost(cd, slug) {
    const weighted =
        (cd.cost_food || 0) * 1.0 +
        (cd.cost_wood || 0) * 1.0 +
        (cd.cost_gold || 0) * 1.5;
    return weighted / (TRAIN_BATCH[slug] || 1);
}

// Returns [n1, n2] for the chosen mode. `explicit` hands back what was typed.
function resolveCounts(mode, budget, d1, d2, slug1, slug2, typed1, typed2) {
    if (mode === "explicit") return [typed1, typed2];
    if (mode === "ui-rule") {
        const c1 = uiCost(d1) || d1.total_cost || 1;
        const c2 = uiCost(d2) || d2.total_cost || 1;
        return [
            Math.max(1, Math.floor(budget / c1)),
            Math.max(1, Math.floor(budget / c2)),
        ];
    }
    // corpus-rule: the CHEAPER side gets as many as the budget buys, capped at
    // 21; the pricier side is then scaled to the SAME SPEND, never below 1. The
    // cap is what makes "21 Slingers" a fixed reference point across matchups.
    const c1 = corpusCost(d1, slug1) || 1;
    const c2 = corpusCost(d2, slug2) || 1;
    if (c1 <= c2) {
        const n1 = Math.max(1, Math.min(CORPUS_CAP, Math.floor(budget / c1)));
        return [n1, Math.max(1, Math.floor((n1 * c1) / c2))];
    }
    const n2 = Math.max(1, Math.min(CORPUS_CAP, Math.floor(budget / c2)));
    return [Math.max(1, Math.floor((n2 * c2) / c1)), n2];
}

// ===== OVERLAYS =====
const STATE_COLORS = {
    idle: "#888",
    moving: "#4aa3ff",
    attacking: "#ff4a4a",
    kiting: "#ffd14a",
    committed: "#ff9900",
    dead: "#333",
};
const TEAM_COLORS = { 1: "#4a9fd4", 2: "#cf5a4b" };

const overlayOn = { state: true, target: true, range: true };

// Drawn AFTER renderer.render(sim), onto the renderer's own context. The
// renderer leaves a DPR transform on the context; rather than rely on that
// still being current (a resize between frames rebuilds it), re-apply it from
// the renderer's public scale factors and work in logical 900x600 space.
function drawOverlays(ctx, renderer, sim) {
    if (!sim) return;
    ctx.save();
    ctx.setTransform(renderer.renderScaleX, 0, 0, renderer.renderScaleY, 0, 0);
    const units = [...sim.team1, ...sim.team2];

    // Range rings first (faintest, and they should sit under everything).
    if (overlayOn.range) {
        ctx.globalAlpha = 0.15;
        ctx.lineWidth = 1;
        for (const u of units) {
            if (u.state === "dead" || !(u.rawAttackRange > 0)) continue;
            ctx.strokeStyle = TEAM_COLORS[u.team];
            ctx.beginPath();
            ctx.arc(u.x, u.y, u.attackRange, 0, Math.PI * 2);
            ctx.stroke();
        }
        ctx.globalAlpha = 1;
    }

    // Target lines: who is committed to whom — the single most useful overlay
    // for the "elephants dither over which Slinger to chase" failure mode.
    if (overlayOn.target) {
        ctx.globalAlpha = 0.55;
        ctx.lineWidth = 1;
        for (const u of units) {
            if (u.state === "dead" || !u.target) continue;
            ctx.strokeStyle = TEAM_COLORS[u.team];
            ctx.beginPath();
            ctx.moveTo(u.x, u.y);
            ctx.lineTo(u.target.x, u.target.y);
            ctx.stroke();
        }
        ctx.globalAlpha = 1;
    }

    // State ring on top: idle/moving/attacking/kiting/committed/dead.
    if (overlayOn.state) {
        ctx.lineWidth = 2;
        for (const u of units) {
            ctx.strokeStyle = STATE_COLORS[u.state] || "#888";
            ctx.beginPath();
            ctx.arc(u.x, u.y, u.radius + 3, 0, Math.PI * 2);
            ctx.stroke();
        }
    }
    ctx.restore();
}

// ===== THE DRIVER =====
// The harness's half of what PageSim does on the product page: a clamped
// requestAnimationFrame loop that converts wall-clock into fixed 1/60 engine
// sub-steps. Everything time-related funnels through advance() so that Step,
// Run and a scripted smoke test all drive the engine identically.
class Harness {
    constructor(canvas) {
        this.renderer = new SimRenderer(canvas);
        this.ctx = canvas.getContext("2d");
        this.sim = null;
        this.speed = 1;
        this.running = false;
        this.paused = false;
        this.lastTs = 0;
        this.ticks = 0;
        // Live-DPS ring buffer: { t, d1, d2 } samples of battleTime + cumulative
        // damage, trimmed to the last DPS_WINDOW seconds of SIM time (not wall
        // time — so the number means the same thing at 0.25x and at 8x).
        this.dps = [];
        // battleTime of each side's first landed damage; the free-fire timer.
        this.firstDamage = { 1: null, 2: null };
    }

    setup({ teams, seed }) {
        this.sim = createSimulation({
            mapW: CANVAS_WIDTH,
            mapH: CANVAS_HEIGHT,
            teams,
            seed,
        });
        this.running = false;
        this.paused = false;
        this.ticks = 0;
        this.dps = [];
        this.firstDamage = { 1: null, 2: null };
    }

    start() {
        if (!this.sim || this.sim.winner !== null) return;
        this.running = true;
        this.paused = false;
        this.lastTs = performance.now();
        this.loop();
    }

    setPaused(p) {
        this.paused = p;
        if (!p && this.running) {
            this.lastTs = performance.now();
            this.loop();
        }
    }

    loop() {
        if (!this.running || this.paused || !this.sim) return;
        const now = performance.now();
        // Same clamp as PageSim.loop: cap the catch-up after a tab stall, then
        // spend it in fixed sub-steps so 8x stays accurate instead of letting
        // units tunnel past each other in one giant dt.
        const remaining = Math.min(
            ((now - this.lastTs) / 1000) * this.speed,
            0.25,
        );
        this.lastTs = now;
        this.advance(remaining);
        this.frame();
        if (this.sim.winner !== null) {
            this.running = false;
        } else {
            requestAnimationFrame(() => this.loop());
        }
    }

    // Advance `simSeconds` of battle in 1/60 sub-steps. Public so a headless
    // smoke test can drive the harness when requestAnimationFrame is throttled
    // (a backgrounded automation tab gets zero rAF callbacks).
    advance(simSeconds) {
        if (!this.sim) return;
        let remaining = simSeconds;
        while (remaining > 1e-6 && this.sim.winner === null) {
            const dt = Math.min(remaining, STEP);
            this.sim.step(dt);
            this.ticks++;
            this.sampleTick();
            remaining -= dt;
        }
    }

    // Exactly one engine tick, paused. Step is the whole reason the engine
    // exposes step(dt) — this is the frame-by-frame debugger.
    stepOnce() {
        if (!this.sim || this.sim.winner !== null) return;
        this.paused = true;
        this.running = false;
        this.sim.step(STEP);
        this.ticks++;
        this.sampleTick();
        this.frame();
    }

    // Per-TICK bookkeeping (not per rendered frame): the free-fire timer has to
    // be sampled at tick resolution or it would be quantised to the frame rate.
    sampleTick() {
        const cs = this.sim.combatStats;
        for (const t of [1, 2]) {
            if (this.firstDamage[t] === null && cs[t].damageDealt > 0)
                this.firstDamage[t] = this.sim.battleTime;
        }
    }

    // One rendered frame: battlefield, overlays, readouts.
    frame() {
        this.render();
        updateLive(this);
    }

    render() {
        if (this.sim) {
            this.renderer.render(this.sim);
            drawOverlays(this.ctx, this.renderer, this.sim);
        } else {
            this.renderer.renderEmpty();
        }
    }
}

const DPS_WINDOW = 5; // seconds of sim time

// ===== PAGE STATE =====
const teamState = {
    1: { civ: null, slug: null, name: null, dict: null },
    2: { civ: null, slug: null, name: null, dict: null },
};
const assets = { 1: null, 2: null };
const civCache = new Map(); // civ -> units_by_age.Imperial array
let harness = null;
let worker = null;
let boardRows = [];
let boardMax = { 1: 0, 2: 0 }; // count * unit maxHp, for the HP% column

function setError(msg) {
    $("err").textContent = msg || "";
}

// ===== PICKERS =====
function civList() {
    // Bare identifier on purpose — see the header note about classic-script
    // `const` not landing on `window`.
    return typeof ENABLED_CIVS !== "undefined" && Array.isArray(ENABLED_CIVS)
        ? ENABLED_CIVS
        : [];
}

function fillCivSelects() {
    const civs = civList();
    for (const n of [1, 2]) {
        const sel = $(`civ${n}`);
        sel.innerHTML =
            '<option value="">— pick a civ —</option>' +
            civs.map((c) => `<option value="${c}">${c}</option>`).join("");
    }
    if (!civs.length) setError("constants.js did not load — no civ list.");
}

// Imperial unit list for a civ, cached. The endpoint is heavy (full stat chains
// for every unit), so one fetch per civ per page load is worth caching.
async function loadCivUnits(civ) {
    if (civCache.has(civ)) return civCache.get(civ);
    const res = await fetch(`/api/ref/civ/${encodeURIComponent(civ)}`);
    if (!res.ok) throw new Error(`civ ${civ}: HTTP ${res.status}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    const units = (data.units_by_age && data.units_by_age.Imperial) || [];
    units.sort((a, b) => a.unit_name.localeCompare(b.unit_name));
    civCache.set(civ, units);
    return units;
}

async function onCivChange(n, keepSlug = null) {
    const civ = $(`civ${n}`).value;
    teamState[n].civ = civ || null;
    const sel = $(`unit${n}`);
    if (!civ) {
        sel.innerHTML = '<option value="">— pick a civ —</option>';
        teamState[n].slug = teamState[n].name = null;
        return;
    }
    sel.innerHTML = '<option value="">loading…</option>';
    try {
        const units = await loadCivUnits(civ);
        sel.innerHTML = units
            .map(
                (u) =>
                    `<option value="${u.unit_slug}" data-name="${u.unit_name}">${u.unit_name}</option>`,
            )
            .join("");
        const want =
            keepSlug && units.some((u) => u.unit_slug === keepSlug)
                ? keepSlug
                : sel.options[0] && sel.options[0].value;
        sel.value = want || "";
        onUnitChange(n);
    } catch (e) {
        sel.innerHTML = '<option value="">— failed —</option>';
        setError(`Unit list for ${civ}: ${e.message}`);
    }
}

function onUnitChange(n) {
    const sel = $(`unit${n}`);
    const opt = sel.selectedOptions[0];
    teamState[n].slug = sel.value || null;
    teamState[n].name = (opt && opt.dataset.name) || null;
    preloadArt(n);
}

// Mirrors simulate.js selectUnit(): the red idle sprite for both teams (attack
// animations are red-only, so a blue idle would flip colour mid-swing; teams are
// told apart by HP-bar colour), plus the attack sheet when the bucket serves one.
// All of it is optional — with no sprites at all the renderer draws its circle
// fallback and the harness works exactly the same.
function preloadArt(n) {
    const name = teamState[n].name;
    if (!name) {
        assets[n] = null;
        return;
    }
    let img = null;
    let isSprite = false;
    let sheet = null;
    try {
        const url = typeof spriteFor === "function" ? spriteFor(name, n) : "";
        if (url) {
            img = new Image();
            img.src = url;
        }
        isSprite = typeof hasSprite === "function" ? hasSprite(name) : false;
        const sh = typeof sheetFor === "function" ? sheetFor(name) : null;
        if (sh && sh.url) {
            const sImg = new Image();
            sImg.src = sh.url;
            sheet = { img: sImg, meta: sh };
        }
    } catch (e) {
        /* art is decoration — never let it break the instrument */
    }
    assets[n] = { img, isSprite, sheet };
}

// ===== PRESETS =====
function fillPresetSelect() {
    $("preset").innerHTML =
        '<option value="">— custom —</option>' +
        PRESETS.map((p) => `<option value="${p.id}">${p.label}</option>`).join("");
}

async function applyPreset(id) {
    const p = PRESETS.find((x) => x.id === id);
    if (!p) return;
    $("preset").value = p.id; // also covers the auto-load on init
    $("presetHint").textContent = p.note;
    for (const n of [1, 2]) {
        const spec = n === 1 ? p.t1 : p.t2;
        $(`civ${n}`).value = spec.civ;
        $(`count${n}`).value = spec.count;
        await onCivChange(n, spec.slug);
    }
    const radio = document.querySelector(
        `input[name="countMode"][value="${p.mode}"]`,
    );
    if (radio) radio.checked = true;
}

// ===== RUN ONE FIGHT =====
function currentMode() {
    const r = document.querySelector('input[name="countMode"]:checked');
    return r ? r.value : "explicit";
}
function currentSeed() {
    return (parseInt($("seed").value, 10) || 0) >>> 0;
}

// One fetch per team, exactly like the Battle Sim page: the SAME dict object
// decides the army size and is handed to the engine (which deep-copies it), so
// the count and the spawned units can never disagree.
async function fetchDicts() {
    const s1 = teamState[1];
    const s2 = teamState[2];
    if (!s1.civ || !s1.slug || !s2.civ || !s2.slug)
        throw new Error("pick a civ + unit for both teams");
    const [d1, d2] = await Promise.all(
        [s1, s2].map((s) =>
            fetch(
                `/api/ref/combat-unit/${encodeURIComponent(s.civ)}/${encodeURIComponent(s.slug)}?age=Imperial`,
            ).then((r) => r.json()),
        ),
    );
    if (d1.error) throw new Error(`${s1.civ} ${s1.slug}: ${d1.error}`);
    if (d2.error) throw new Error(`${s2.civ} ${s2.slug}: ${d2.error}`);
    s1.dict = d1;
    s2.dict = d2;
    return [d1, d2];
}

// Build the engine team specs for the current selection, resolving counts under
// the active mode and writing the derived numbers back into the count boxes.
async function buildTeams() {
    const [d1, d2] = await fetchDicts();
    const mode = currentMode();
    const budget = parseInt($("budget").value, 10) || 3000;
    const typed1 = Math.max(1, parseInt($("count1").value, 10) || 1);
    const typed2 = Math.max(1, parseInt($("count2").value, 10) || 1);
    const [n1, n2] = resolveCounts(
        mode,
        budget,
        d1,
        d2,
        teamState[1].slug,
        teamState[2].slug,
        typed1,
        typed2,
    );
    $("count1").value = n1;
    $("count2").value = n2;
    return [
        { combatDict: d1, slug: teamState[1].slug, civ: teamState[1].civ, count: n1 },
        { combatDict: d2, slug: teamState[2].slug, civ: teamState[2].civ, count: n2 },
    ];
}

async function onRun() {
    setError("");
    $("run").disabled = true;
    try {
        const teams = await buildTeams();
        const seed = currentSeed();
        harness.setup({ teams, seed });

        // Artwork goes to the RENDERER, not onto the units — sprites are a
        // rendering concern since the Task 6 split.
        harness.renderer.setTeamAssets(1, assets[1] || {});
        harness.renderer.setTeamAssets(2, assets[2] || {});
        harness.renderer.setLabels({
            team1Civ: teamState[1].civ,
            team1Unit: teamState[1].name,
            team2Civ: teamState[2].civ,
            team2Unit: teamState[2].name,
        });
        // Required host wiring, identical to production simulate.js:1263-1264 —
        // see write (b) in the header. triggerAttackAnim() sizes its post-swing
        // hold from the sheet's frame count (0.4s without one), so a host that
        // owns artwork must hand it to the units as well as to the renderer.
        // Cosmetic state: never read by combat logic, never hashed.
        const sheets = { 1: assets[1] && assets[1].sheet, 2: assets[2] && assets[2].sheet };
        for (const u of harness.sim.team1) u.attackSheet = sheets[1] || null;
        for (const u of harness.sim.team2) u.attackSheet = sheets[2] || null;

        $("liveName1").textContent = `${teamState[1].civ} ${teamState[1].name} ×${teams[0].count}`;
        $("liveName2").textContent = `${teamState[2].civ} ${teamState[2].name} ×${teams[1].count}`;
        $("seedEcho").textContent = `seed ${seed} · ${teams[0].count} v ${teams[1].count} · ${currentMode()}`;
        console.log("harness fight:", {
            seed,
            mode: currentMode(),
            t1: `${teamState[1].civ}/${teamState[1].slug} x${teams[0].count}`,
            t2: `${teamState[2].civ}/${teamState[2].slug} x${teams[1].count}`,
        });

        $("pause").disabled = false;
        $("pause").textContent = "Pause";
        $("step").disabled = false;
        harness.frame();
        harness.start();
    } catch (e) {
        setError(e.message || String(e));
    } finally {
        $("run").disabled = false;
    }
}

// ===== LIVE READOUT =====
function fmt(n, digits = 0) {
    return Number(n).toFixed(digits);
}

function updateLive(h) {
    const sim = h.sim;
    if (!sim) return;
    const t = sim.battleTime;
    $("clock").textContent = `${t.toFixed(1)}s`;

    const cs = sim.combatStats;
    // Ring buffer: keep only the last DPS_WINDOW seconds of SIM time.
    h.dps.push({ t, d1: cs[1].damageDealt, d2: cs[2].damageDealt });
    while (h.dps.length > 1 && t - h.dps[0].t > DPS_WINDOW) h.dps.shift();
    const old = h.dps[0];
    const span = t - old.t;

    for (const n of [1, 2]) {
        const team = n === 1 ? sim.team1 : sim.team2;
        const alive = team.filter((u) => u.state !== "dead");
        const hp = alive.reduce((s, u) => s + u.currentHp, 0);
        const maxHp = team.length * (team[0] ? team[0].maxHp : 0);
        $(`alive${n}`).textContent = `${alive.length} / ${team.length}`;
        $(`hp${n}`).textContent = maxHp
            ? `${Math.round(hp)} (${fmt((hp / maxHp) * 100, 1)}%)`
            : Math.round(hp);
        $(`sw${n}`).textContent = cs[n].swings;
        $(`hits${n}`).textContent =
            cs[n].swings > 0
                ? `${cs[n].hitsLanded} (${fmt((cs[n].hitsLanded / cs[n].swings) * 100, 0)}%)`
                : cs[n].hitsLanded;
        $(`dmg${n}`).textContent = Math.round(cs[n].damageDealt);
        $(`dps${n}`).textContent =
            span > 0.2
                ? fmt((cs[n].damageDealt - old[`d${n}`]) / span, 1)
                : "—";
        $(`first${n}`).textContent =
            h.firstDamage[n] === null ? "∞" : `${h.firstDamage[n].toFixed(1)}s`;
    }
    $("freefire").textContent = freeFireText(h);
}

// Free-fire = how long the ranged side shoots before the MELEE side can answer.
// Defined only when exactly one side is melee (rawAttackRange === 0); with two
// melee or two ranged armies there is no such window, and the per-side "1st dmg"
// rows above already say everything there is to say.
function freeFireText(h) {
    const sim = h.sim;
    if (!sim) return "Free-fire: —";
    const isMelee = (team) => team.length > 0 && team[0].rawAttackRange === 0;
    const m1 = isMelee(sim.team1);
    const m2 = isMelee(sim.team2);
    if (m1 === m2) {
        return `Free-fire: n/a — both sides ${m1 ? "melee" : "ranged"} (see “1st dmg” per side)`;
    }
    const melee = m1 ? 1 : 2;
    const ranged = m1 ? 2 : 1;
    const tm = h.firstDamage[melee];
    const tr = h.firstDamage[ranged];
    if (tm === null)
        return `Free-fire: ∞ — team ${melee} (melee) has not landed a hit yet`;
    const window =
        tr === null ? null : Math.max(0, tm - tr);
    return (
        `Free-fire: ${tm.toFixed(1)}s — team ${melee} (melee) first damage` +
        (window === null ? "" : `; team ${ranged} shot unopposed for ${window.toFixed(1)}s`)
    );
}

// ===== MULTI-SEED SCOREBOARD =====
function resetBoard() {
    boardRows = [];
    $("board").querySelector("tbody").innerHTML = "";
    $("board").querySelector("tfoot").innerHTML = "";
}

// `null` from runToEnd means neither side was wiped inside the 600 s cap — for
// this engine that is a RESULT, not a missing one (the kiting residue that never
// gets caught), so it gets its own label rather than being folded into a draw.
function winnerCell(w) {
    if (w === 1) return '<span class="win1">T1</span>';
    if (w === 2) return '<span class="win2">T2</span>';
    if (w === 0) return '<span class="wind">mutual</span>';
    return '<span class="wind">cap</span>';
}

function addBoardRow(r) {
    boardRows.push(r);
    const pct = (hp, side) =>
        boardMax[side] > 0 ? `${((hp / boardMax[side]) * 100).toFixed(1)}%` : "—";
    const tr = document.createElement("tr");
    tr.innerHTML =
        `<td>${r.seed}</td><td>${winnerCell(r.winner)}</td><td>${r.time.toFixed(1)}s</td>` +
        `<td>${r.alive1}</td><td>${pct(r.hp1, 1)}</td>` +
        `<td>${r.alive2}</td><td>${pct(r.hp2, 2)}</td>`;
    $("board").querySelector("tbody").appendChild(tr);
    renderBoardFooter();
}

function renderBoardFooter() {
    const n = boardRows.length;
    if (!n) return;
    const mean = (f) => boardRows.reduce((s, r) => s + f(r), 0) / n;
    const wins1 = boardRows.filter((r) => r.winner === 1).length;
    const wins2 = boardRows.filter((r) => r.winner === 2).length;
    const pct = (hp, side) =>
        boardMax[side] > 0 ? `${((hp / boardMax[side]) * 100).toFixed(1)}%` : "—";
    $("board").querySelector("tfoot").innerHTML =
        `<tr><td>${n} seeds</td>` +
        `<td>${((wins1 / n) * 100).toFixed(0)}% / ${((wins2 / n) * 100).toFixed(0)}%</td>` +
        `<td>${mean((r) => r.time).toFixed(1)}s</td>` +
        `<td>${mean((r) => r.alive1).toFixed(1)}</td><td>${pct(mean((r) => r.hp1), 1)}</td>` +
        `<td>${mean((r) => r.alive2).toFixed(1)}</td><td>${pct(mean((r) => r.hp2), 2)}</td></tr>`;
}

function stopWorker() {
    if (worker) {
        worker.terminate();
        worker = null;
    }
    $("cancelN").disabled = true;
    $("runN").disabled = false;
}

async function onRunN() {
    setError("");
    stopWorker();
    resetBoard();
    $("runN").disabled = true;
    try {
        const teams = await buildTeams();
        const seed0 = currentSeed();
        const n = Math.max(1, parseInt($("nSeeds").value, 10) || 10);
        const seeds = Array.from({ length: n }, (_, i) => (seed0 + i) >>> 0);
        // HP% denominator: count x the unit's max HP straight off the combat
        // dict, so the column means the same thing as the live readout.
        boardMax = {
            1: teams[0].count * (teams[0].combatDict.hp || 0),
            2: teams[1].count * (teams[1].combatDict.hp || 0),
        };
        $("boardStatus").textContent = `0/${n}…`;
        $("cancelN").disabled = false;

        // Off the main thread on purpose: 600 s x 60 Hz x N fights would freeze
        // the page for seconds. The engine is a module, so the worker is too.
        worker = new Worker("/static/lab/sim_worker.js", { type: "module" });
        const started = performance.now();
        worker.onmessage = (e) => {
            const m = e.data;
            if (m.done) {
                $("boardStatus").textContent =
                    `${m.count} seeds in ${((performance.now() - started) / 1000).toFixed(1)}s`;
                stopWorker();
                return;
            }
            if (m.error) {
                setError(`seed ${m.seed}: ${m.error}`);
                return;
            }
            addBoardRow(m);
            $("boardStatus").textContent = `${boardRows.length}/${n}…`;
        };
        worker.onerror = (e) => {
            setError(`worker: ${e.message || "failed"}`);
            stopWorker();
        };
        worker.postMessage({ teams, seeds });
    } catch (e) {
        setError(e.message || String(e));
        stopWorker();
    }
}

// ===== WIRING =====
function init() {
    const canvas = $("canvas");
    harness = new Harness(canvas);
    harness.render();

    fillCivSelects();
    fillPresetSelect();

    $("preset").addEventListener("change", (e) => {
        if (e.target.value) applyPreset(e.target.value);
    });
    for (const n of [1, 2]) {
        $(`civ${n}`).addEventListener("change", () => {
            $("preset").value = "";
            onCivChange(n);
        });
        $(`unit${n}`).addEventListener("change", () => {
            $("preset").value = "";
            onUnitChange(n);
        });
    }
    $("randomSeed").addEventListener("click", () => {
        $("seed").value = (Math.random() * 2 ** 32) >>> 0;
    });
    $("run").addEventListener("click", onRun);
    $("pause").addEventListener("click", () => {
        if (!harness.sim) return;
        // Resuming a fight that ran to a winner is meaningless; Pause simply
        // toggles the loop, Run is what starts a new one.
        const next = !harness.paused;
        if (next) {
            harness.paused = true;
            harness.running = false;
            $("pause").textContent = "Resume";
        } else {
            $("pause").textContent = "Pause";
            harness.paused = false;
            harness.start();
        }
    });
    $("step").addEventListener("click", () => {
        harness.stepOnce();
        $("pause").textContent = "Resume";
    });
    $("speed").addEventListener("change", (e) => {
        harness.speed = parseFloat(e.target.value) || 1;
    });
    for (const [id, key] of [
        ["ovState", "state"],
        ["ovTarget", "target"],
        ["ovRange", "range"],
    ]) {
        $(id).addEventListener("change", (e) => {
            overlayOn[key] = e.target.checked;
            // Repaint immediately so a toggle is visible while paused too.
            harness.render();
        });
    }
    $("runN").addEventListener("click", onRunN);
    $("cancelN").addEventListener("click", () => {
        stopWorker();
        $("boardStatus").textContent = `cancelled at ${boardRows.length}`;
    });

    // Load the reference fight so the page is useful the moment it opens.
    applyPreset(PRESETS[0].id);

    // Automation handle. A backgrounded tab gets zero requestAnimationFrame
    // callbacks, so a scripted smoke test drives the engine through
    // __harness.advance(seconds) + __harness.frame() instead of waiting on the
    // loop. Debug-only: nothing on the page reads it.
    window.__harness = harness;
    window.__harnessApi = { onRun, onRunN, applyPreset, PRESETS, boardRows: () => boardRows };
}

if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", init);
else init();

/*
 * Role: page — the Battle Sim page shell served at /.
 *
 * The battle itself no longer lives here. The simulation is the shared,
 * host-agnostic engine under static/js/engine/ (Engine 3 of 3, mirroring the
 * position-based backend engine aoe2x/sim/simulation_real.py), and every pixel
 * is drawn by static/js/sim_renderer.js. What stays in this file is the PAGE:
 * civ/unit pickers, rail search, army-size modes, deep links, the live stat and
 * damage-breakdown panels, and the thin PageSim wrapper that drives the engine
 * off requestAnimationFrame.
 *
 * This file is an ES module (templates/simulate.html loads it with
 * type="module"), so it can read the classic scripts' globals — constants.js,
 * unit_sprites.js, api_client.js, sim_params.js and the template's UNIT_SEARCH —
 * but nothing it declares is global. Page functions are wired up through
 * addEventListener, never through inline on*= attributes.
 */

import {
    createSimulation,
    setArmorClassNames,
    CANVAS_WIDTH,
    CANVAS_HEIGHT,
    RELIC_MAX,
    RELIC_BONUS_UNITS,
    KILL_BONUS_MAX,
    KILL_BONUS_UNITS,
} from "./engine/index.js";
import { SimRenderer } from "./sim_renderer.js";

// ENABLED_CIVS, NAME_TO_ICON, UNIQUE_BUILDING, ICON_BASE,
// CIV_EMBLEM_BASE are loaded from constants.js (via base.html)

function iconUrl(id) {
    return ICON_BASE + id + ".png";
}
function unitIconUrl(name) {
    const id = NAME_TO_ICON[name];
    return id ? iconUrl(id) : "";
}

function hasRelicOption(state) {
    return (
        state.civ === "Lithuanians" &&
        RELIC_BONUS_UNITS.has(state.unitSlug)
    );
}
function hasKillOption(state) {
    return KILL_BONUS_UNITS.has(state.unitSlug);
}

// ===== SELECTION STATE =====
const teamState = {
    1: {
        civ: null,
        age: "Imperial",
        unitSlug: null,
        unitName: null,
        civData: null,
        relics: RELIC_MAX,
        startKills: 0,
    },
    2: {
        civ: null,
        age: "Imperial",
        unitSlug: null,
        unitName: null,
        civData: null,
        relics: RELIC_MAX,
        startKills: 0,
    },
};

// Preloaded unit images for canvas
const unitImages = { 1: null, 2: null };
// Whether the preloaded image is a real (square) sprite vs a portrait fallback —
// drives the no-circle sprite rendering in BattleUnit.render().
const unitIsSprite = { 1: false, 2: false };
// Preloaded attack sprite-sheet per team: { img, meta:{frames,fw,fh,dur} } or null.
// Played frame-by-frame in the canvas while a unit is attacking.
const unitSheets = { 1: null, 2: null };

// ===== SELECTION UI =====
// Click handlers are bound once via delegation in DOMContentLoaded (see
// initSelectionDelegation below). The selection container reads
// [data-action] + sibling data attributes rather than using inline
// onclick= handlers, so user-controllable strings (unit name, civ name)
// never land inside an attribute that becomes executable JavaScript.
// Start is enabled only once both teams have a civ + unit; otherwise the hint
// tells first-time visitors exactly what's missing.
function updateStartReady() {
    const ready = !!(
        teamState[1].civ && teamState[1].unitSlug &&
        teamState[2].civ && teamState[2].unitSlug
    );
    const btn = document.getElementById("startBtn");
    const hint = document.getElementById("startHint");
    if (btn) btn.disabled = !ready;
    if (hint) hint.style.display = ready ? "none" : "";
    return ready;
}

// Keep the "Change options" summary showing the current army setup.
function updateOptionsCurrent() {
    const el = document.getElementById("optionsCurrent");
    if (!el) return;
    const checked = document.querySelector('input[name="armyMode"]:checked');
    const mode = checked ? checked.value : "count";
    const res = (document.getElementById("totalResources") || {}).value;
    if (mode === "resources") {
        el.textContent = `${res || "3000"} Resources`;
    } else if (mode === "resources_upgrades") {
        el.textContent = `${res || "5000"} incl. Upgrades`;
    } else {
        const c1 = (document.getElementById("team1Count") || {}).value || "30";
        const c2 = (document.getElementById("team2Count") || {}).value || "30";
        el.textContent = `${c1} vs ${c2}`;
    }
}

function renderSelection(teamNum) {
    const container = document.getElementById(
        `team${teamNum}Selection`,
    );
    const state = teamState[teamNum];

    if (!state.civ) {
        // Show civ grid
        let html = '<div class="civ-grid">';
        for (const civ of ENABLED_CIVS) {
            const civSafe = escapeHtml(civ);
            html += `<div class="civ-card" data-action="selectCiv" data-team="${teamNum}" data-civ="${civSafe}">
                        <img src="${CIV_EMBLEM_BASE}${civ.toLowerCase()}.png" alt="${civSafe}" />
                        <span>${civSafe}</span>
                    </div>`;
        }
        html += "</div>";
        container.innerHTML = html;
        updateStartReady();
        return;
    }

    // Civ selected badge
    const civSafe = escapeHtml(state.civ);
    let html = `<div class="selection-badge">
                <img src="${CIV_EMBLEM_BASE}${state.civ.toLowerCase()}.png" alt="${civSafe}" />
                <span class="badge-text">${civSafe}</span>
                <span class="change-btn" data-action="clearCiv" data-team="${teamNum}">change</span>
            </div>`;

    if (!state.unitSlug) {
        // Imperial-only (fully upgraded). Age toggle removed.
        if (state.civData) {
            const units =
                state.civData.units_by_age[state.age] || [];
            const groups = {};
            for (const u of units) {
                let bldg =
                    CLASS_TO_BUILDING[u.unit_class_name] ||
                    "Castle";
                if (u.unit_type === "unique")
                    bldg = UNIQUE_BUILDING[u.unit_name] || "Castle";
                if (!groups[bldg]) groups[bldg] = [];
                groups[bldg].push(u);
            }
            for (const bldg of BUILDING_ORDER) {
                const bUnits = groups[bldg];
                if (!bUnits || bUnits.length === 0) continue;
                const bIconId = BUILDING_ICONS[bldg];
                const bldgSafe = escapeHtml(bldg);
                html += `<div class="unit-grid-section">
                            <h4><img src="${iconUrl(bIconId)}" alt="${bldgSafe}" onerror="this.style.display='none'" /> ${bldgSafe}</h4>
                            <div class="unit-grid">`;
                for (const u of bUnits) {
                    // Transparent in-game sprite when available (red default);
                    // spriteless units (naval) keep the boxed portrait. The
                    // `sprite` class drops the circular frame in CSS.
                    const useSprite =
                        typeof hasSprite === "function" &&
                        hasSprite(u.unit_name);
                    const iUrl = useSprite
                        ? spriteFor(u.unit_name)
                        : unitIconUrl(u.unit_name);
                    const imgCls = useSprite ? ' class="sprite"' : "";
                    const nameSafe = escapeHtml(u.unit_name);
                    const slugSafe = escapeHtml(u.unit_slug);
                    html += `<div class="unit-pick" data-action="selectUnit" data-team="${teamNum}" data-slug="${slugSafe}" data-name="${nameSafe}">
                                <img${imgCls} src="${iUrl}" alt="${nameSafe}" onerror="this.style.display='none'" />
                                <span>${nameSafe}</span>
                            </div>`;
                }
                html += "</div></div>";
            }
        } else {
            html +=
                '<div style="color:var(--text-muted);font-size:0.8rem;padding:8px">Loading units...</div>';
        }
    } else {
        // Unit selected badge — transparent sprite when available (red default),
        // boxed portrait otherwise. `sprite` class drops the circular frame.
        const useSprite =
            typeof hasSprite === "function" &&
            hasSprite(state.unitName);
        const iUrl = useSprite
            ? spriteFor(state.unitName)
            : unitIconUrl(state.unitName);
        const imgCls = useSprite ? ' class="sprite"' : "";
        const unitNameSafe = escapeHtml(state.unitName);
        html += `<div class="selection-badge">
                    <img${imgCls} src="${iUrl}" alt="${unitNameSafe}" onerror="this.style.display='none'" />
                    <span class="badge-text">${unitNameSafe}</span>
                    <span class="change-btn" data-action="clearUnit" data-team="${teamNum}">change</span>
                </div>`;
        html += renderUnitOptions(teamNum, state);
    }

    container.innerHTML = html;
    updateStartReady();
}

// Contextual pre-battle condition pickers, shown under the unit badge only
// when the picked unit has an adjustable mechanic (Lithuanian relic count,
// starting kills for per-kill snowball units).
function renderUnitOptions(teamNum, state) {
    const pills = (action, max, current) => {
        let s = '<div class="opt-pills">';
        for (let n = 0; n <= max; n++) {
            s += `<span class="opt-pill${n === current ? " active" : ""}" data-action="${action}" data-team="${teamNum}" data-value="${n}">${n}</span>`;
        }
        return s + "</div>";
    };
    let html = "";
    if (hasRelicOption(state)) {
        html += `<div class="unit-opts">
                <div class="opt-label">Relics captured <span class="opt-effect">+${state.relics} attack</span></div>
                ${pills("setRelics", RELIC_MAX, state.relics)}
            </div>`;
    }
    if (hasKillOption(state)) {
        const bonus = Math.min(KILL_BONUS_MAX, state.startKills);
        html += `<div class="unit-opts">
                <div class="opt-label">Starting kills <span class="opt-effect">+${bonus} attack</span></div>
                ${pills("setKills", KILL_BONUS_MAX, state.startKills)}
            </div>`;
    }
    return html;
}

function initSelectionDelegation() {
    [1, 2].forEach((teamNum) => {
        const container = document.getElementById(
            `team${teamNum}Selection`,
        );
        if (!container) return;
        container.addEventListener("click", (event) => {
            const target = event.target.closest("[data-action]");
            if (!target || !container.contains(target)) return;
            const action = target.dataset.action;
            const team = parseInt(target.dataset.team, 10);
            switch (action) {
                case "selectCiv":
                    selectCiv(team, target.dataset.civ);
                    break;
                case "clearCiv":
                    clearCiv(team);
                    break;
                case "setAge":
                    setTeamAge(team, target.dataset.age);
                    break;
                case "selectUnit":
                    selectUnit(
                        team,
                        target.dataset.slug,
                        target.dataset.name,
                    );
                    break;
                case "clearUnit":
                    clearUnit(team);
                    break;
                case "setRelics":
                    setRelics(team, target.dataset.value);
                    break;
                case "setKills":
                    setStartKills(team, target.dataset.value);
                    break;
            }
        });
    });
}

function clampInt(n, lo, hi, dflt) {
    n = parseInt(n, 10);
    if (isNaN(n)) return dflt;
    return Math.max(lo, Math.min(hi, n));
}

function setRelics(teamNum, n) {
    teamState[teamNum].relics = clampInt(n, 0, RELIC_MAX, RELIC_MAX);
    renderSelection(teamNum);
}

function setStartKills(teamNum, n) {
    teamState[teamNum].startKills = clampInt(n, 0, KILL_BONUS_MAX, 0);
    renderSelection(teamNum);
}

async function selectCiv(teamNum, civName) {
    const state = teamState[teamNum];
    state.civ = civName;
    state.unitSlug = null;
    state.unitName = null;
    state.civData = null;
    renderSelection(teamNum);

    // Fetch civ data
    try {
        state.civData = await apiGet(`/api/ref/civ/${civName}`);
    } catch (e) {
        console.error("Failed to load civ data:", e);
    }
    renderSelection(teamNum);
}

function clearCiv(teamNum) {
    teamState[teamNum].civ = null;
    teamState[teamNum].unitSlug = null;
    teamState[teamNum].unitName = null;
    teamState[teamNum].civData = null;
    renderSelection(teamNum);
}

function setTeamAge(teamNum, age) {
    teamState[teamNum].age = age;
    teamState[teamNum].unitSlug = null;
    teamState[teamNum].unitName = null;
    renderSelection(teamNum);
}

function selectUnit(teamNum, slug, name) {
    teamState[teamNum].unitSlug = slug;
    teamState[teamNum].unitName = name;
    // Preload canvas image: the red idle sprite (both teams) when the unit has a
    // square sprite, else the portrait. Teams are told apart by HP-bar colour, not
    // sprite colour, so the unit doesn't flip colour when its (red) attack anim
    // plays. unitIsSprite drives no-circle render.
    const url = spriteFor(name, teamNum);
    if (url) {
        const img = new Image();
        img.src = url;
        unitImages[teamNum] = img;
    } else {
        unitImages[teamNum] = null;
    }
    unitIsSprite[teamNum] = hasSprite(name);
    // Preload the attack sprite-sheet (animated frames) if this unit has one.
    const sheet = (typeof sheetFor === "function") ? sheetFor(name) : null;
    if (sheet && sheet.url) {
        const sImg = new Image();
        sImg.src = sheet.url;
        unitSheets[teamNum] = { img: sImg, meta: sheet };
    } else {
        unitSheets[teamNum] = null;
    }
    renderSelection(teamNum);
}

function clearUnit(teamNum) {
    teamState[teamNum].unitSlug = null;
    teamState[teamNum].unitName = null;
    renderSelection(teamNum);
}

// ===== RAIL SEARCH (civ + unique unit) =====
// Index = every enabled civ + every unique unit (embedded as UNIT_SEARCH by the
// template). Typing filters; clicking a civ opens its unit grid, clicking a
// unique unit picks that civ + unit directly. Standard units stay reachable via
// the civ -> unit grid.
const _UNIT_SEARCH =
    typeof UNIT_SEARCH !== "undefined" && Array.isArray(UNIT_SEARCH)
        ? UNIT_SEARCH
        : [];
const SEARCH_ITEMS = (() => {
    const items = [];
    const enabled = new Set(ENABLED_CIVS);
    for (const civ of ENABLED_CIVS) {
        items.push({ type: "civ", civ, name: civ, _search: civ.toLowerCase() });
    }
    for (const u of _UNIT_SEARCH) {
        if (!enabled.has(u.civ)) continue;
        items.push({
            type: "unit",
            civ: u.civ,
            slug: u.slug,
            name: u.name,
            _search: `${u.name} ${u.civ}`.toLowerCase(),
        });
    }
    return items;
})();
const _searchResults = { 1: [], 2: [] };

function renderSearchResults(teamNum, raw) {
    const box = document.getElementById(`team${teamNum}SearchResults`);
    if (!box) return;
    const q = (raw || "").trim().toLowerCase();
    if (!q) {
        box.hidden = true;
        _searchResults[teamNum] = [];
        return;
    }
    const matches = SEARCH_ITEMS.filter((it) => it._search.includes(q)).slice(0, 40);
    _searchResults[teamNum] = matches;
    if (!matches.length) {
        box.innerHTML = '<div class="search-empty">No civ or unit matches</div>';
        box.hidden = false;
        return;
    }
    let html = "";
    matches.forEach((it, idx) => {
        if (it.type === "civ") {
            html += `<div class="search-result" data-idx="${idx}">
                <img class="emblem" src="${CIV_EMBLEM_BASE}${it.civ.toLowerCase()}.png" alt="" onerror="this.style.display='none'" />
                <span class="sr-name">${escapeHtml(it.name)}</span>
                <span class="sr-sub">Civ</span>
            </div>`;
        } else {
            const useSprite =
                typeof hasSprite === "function" && hasSprite(it.name);
            const iUrl = useSprite ? spriteFor(it.name) : unitIconUrl(it.name);
            html += `<div class="search-result" data-idx="${idx}">
                <img class="${useSprite ? "" : "emblem"}" src="${iUrl}" alt="" onerror="this.style.display='none'" />
                <span class="sr-name">${escapeHtml(it.name)}</span>
                <span class="sr-sub">${escapeHtml(it.civ)}</span>
            </div>`;
        }
    });
    box.innerHTML = html;
    box.hidden = false;
}

function clearSearch(teamNum) {
    const input = document.getElementById(`team${teamNum}Search`);
    const box = document.getElementById(`team${teamNum}SearchResults`);
    if (input) input.value = "";
    if (box) {
        box.hidden = true;
        box.innerHTML = "";
    }
    _searchResults[teamNum] = [];
}

async function pickFromSearch(teamNum, item) {
    clearSearch(teamNum);
    await selectCiv(teamNum, item.civ); // also loads civData for the grid
    if (item.type === "unit") {
        selectUnit(teamNum, item.slug, item.name);
    }
}

function initRailSearch() {
    [1, 2].forEach((teamNum) => {
        const input = document.getElementById(`team${teamNum}Search`);
        const box = document.getElementById(`team${teamNum}SearchResults`);
        if (!input || !box) return;
        input.addEventListener("input", () =>
            renderSearchResults(teamNum, input.value),
        );
        input.addEventListener("focus", () => {
            if (input.value.trim()) renderSearchResults(teamNum, input.value);
        });
        // Delay hide so a result click registers before blur dismisses the list.
        input.addEventListener("blur", () =>
            setTimeout(() => {
                box.hidden = true;
            }, 160),
        );
        input.addEventListener("keydown", (e) => {
            if (e.key === "Escape") clearSearch(teamNum);
        });
        // mousedown fires before the input's blur, so the pick still registers.
        box.addEventListener("mousedown", (e) => {
            const el = e.target.closest("[data-idx]");
            if (!el) return;
            e.preventDefault();
            const item = _searchResults[teamNum][parseInt(el.dataset.idx, 10)];
            if (item) pickFromSearch(teamNum, item);
        });
    });
}

// ===== PHASE TRANSITION (pick <-> battle) =====
// Battle expands the arena and shrinks the rails to the picked unit + live team
// stats; pick phase restores the full pickers + Start button.
function setSimPhase(battle) {
    const stage = document.getElementById("simStage");
    if (stage) stage.classList.toggle("battle-active", battle);
    const hide = (id, h) => {
        const el = document.getElementById(id);
        if (el) el.hidden = h;
    };
    hide("startBtn", battle);
    hide("simControls", !battle);
    hide("battleTimer", !battle);
    hide("dmgToggle", !battle);
    hide("team1Live", !battle);
    hide("team2Live", !battle);
    const hint = document.getElementById("startHint");
    if (battle) {
        if (hint) hint.style.display = "none";
    } else {
        hide("debugPanel", true);
        const t = document.getElementById("dmgToggle");
        if (t) t.setAttribute("aria-expanded", "false");
        updateStartReady(); // restores Start button + hint state
    }
}

// ===== PAGE-SIDE SIM DRIVER =====
// The engine has no clock and no canvas: it exposes step(dt) and a pile of
// state. PageSim is the page's half of the old BattleSimulation — the rAF loop,
// the play/pause/reset controls and the speed multiplier — wrapping an engine
// Simulation (this.sim) and a SimRenderer (this.renderer).
class PageSim {
    constructor(canvas) {
        this.renderer = new SimRenderer(canvas);
        this.sim = null;
        this.speedMultiplier = 3.0;
        this.running = false;
        this.paused = false;
        this.lastTimestamp = 0;
    }

    get winner() {
        return this.sim ? this.sim.winner : null;
    }

    // Build a fresh battle. `teams` is the engine's team-spec pair
    // ({ combatDict, slug, civ, count, relics, startKills }) — every battle gets
    // a brand-new Simulation, so nothing needs clearing between runs.
    setup({ teams, seed }) {
        this.sim = createSimulation({
            mapW: CANVAS_WIDTH,
            mapH: CANVAS_HEIGHT,
            teams,
            seed,
        });
    }

    start() {
        if (!this.sim) {
            alert("Please configure both teams");
            return;
        }
        this.running = true;
        this.paused = false;
        this.lastTimestamp = performance.now();
        updateStats(this.sim);
        updateDebugPanel(this.sim);
        this.loop();
    }

    pause() {
        this.paused = !this.paused;
        if (!this.paused) {
            this.lastTimestamp = performance.now();
            this.loop();
        }
    }

    reset() {
        this.sim = null;
        this.running = false;
        this.paused = false;
        updateStats(null);
        this.render();
        document.getElementById("debugContent").innerHTML =
            '<p style="color:var(--text-muted)">Start a battle to see combat stats</p>';
    }

    loop() {
        if (!this.running || this.paused) return;
        const now = performance.now();
        // Total sim-time to advance this frame. Clamp to avoid a huge catch-up
        // after a tab stall, then step it in small fixed increments so fast
        // speeds (5x/10x) stay accurate without large per-step movement that
        // would let units tunnel past each other or skip attack ticks.
        let remaining = Math.min(
            ((now - this.lastTimestamp) / 1000) * this.speedMultiplier,
            0.25,
        );
        this.lastTimestamp = now;
        const STEP = 1 / 60; // ~one 60fps tick per sub-step
        while (remaining > 1e-6 && this.sim.winner === null) {
            const dt = Math.min(remaining, STEP);
            this.sim.step(dt);
            remaining -= dt;
        }
        // The live readout used to be refreshed inside every sub-step; once per
        // rendered frame is the same thing on screen and a lot less DOM churn.
        updateStats(this.sim);
        this.render();
        if (this.sim.winner !== null) {
            this.running = false;
            updateBattleWinner(this.sim.winner);
        } else {
            requestAnimationFrame(() => this.loop());
        }
    }

    render() {
        if (this.sim) this.renderer.render(this.sim);
        else this.renderer.renderEmpty();
    }
}

// ===== LIVE STAT READOUT =====
// Free function over an engine sim (null before/after a battle) — the DOM half
// of the old BattleSimulation.updateStats. Army costs come from `currentBattle`
// (page selection data the engine knows nothing about).
function updateStats(sim) {
    const team1 = sim ? sim.team1 : [];
    const team2 = sim ? sim.team2 : [];
    const team1Stats = sim ? sim.team1Stats : null;
    const team2Stats = sim ? sim.team2Stats : null;
    const battleTime = sim ? sim.battleTime : 0;
    const t1Alive = team1.filter(
        (u) => u.state !== "dead",
    );
    const t2Alive = team2.filter(
        (u) => u.state !== "dead",
    );
    const t1Hp = t1Alive.reduce((s, u) => s + u.currentHp, 0);
    const t2Hp = t2Alive.reduce((s, u) => s + u.currentHp, 0);

    document.getElementById("battleTimer").textContent =
        `${battleTime.toFixed(1)}s`;

    // Team 1 progress
    document.getElementById("prog1Units").textContent =
        `${t1Alive.length} / ${team1.length}`;
    document.getElementById("prog1Hp").textContent =
        `${Math.round(t1Hp)} / ${Math.round(team1.length * (team1Stats?.hp || 0))}`;
    if (currentBattle) {
        document.getElementById("prog1Res").textContent =
            currentBattle.team1_total_cost;
        const t1Dead = team1.length - t1Alive.length;
        const t1MaxHp =
            t1Alive.length * currentBattle.team1_max_hp;
        const t1HpLostPct =
            t1MaxHp > 0 ? (t1MaxHp - t1Hp) / t1MaxHp : 0;
        const t1Lost =
            t1Dead * currentBattle.team1_unit_cost +
            Math.round(
                t1Alive.length *
                    currentBattle.team1_unit_cost *
                    t1HpLostPct,
            );
        document.getElementById("prog1Lost").textContent =
            t1Lost;
    }

    // Team 2 progress
    document.getElementById("prog2Units").textContent =
        `${t2Alive.length} / ${team2.length}`;
    document.getElementById("prog2Hp").textContent =
        `${Math.round(t2Hp)} / ${Math.round(team2.length * (team2Stats?.hp || 0))}`;
    if (currentBattle) {
        document.getElementById("prog2Res").textContent =
            currentBattle.team2_total_cost;
        const t2Dead = team2.length - t2Alive.length;
        const t2MaxHp =
            t2Alive.length * currentBattle.team2_max_hp;
        const t2HpLostPct =
            t2MaxHp > 0 ? (t2MaxHp - t2Hp) / t2MaxHp : 0;
        const t2Lost =
            t2Dead * currentBattle.team2_unit_cost +
            Math.round(
                t2Alive.length *
                    currentBattle.team2_unit_cost *
                    t2HpLostPct,
            );
        document.getElementById("prog2Lost").textContent =
            t2Lost;
    }
}

// ===== DAMAGE BREAKDOWN PANEL =====
// Free function over an engine sim — the DOM half of the old
// BattleSimulation.updateDebugPanel. Reads sim.team1Stats/team2Stats (the
// combat dicts the scenario builder kept) and the units' own damage model.
function updateDebugPanel(sim) {
    if (
        !sim ||
        !sim.team1Stats ||
        !sim.team2Stats ||
        sim.team1.length === 0 ||
        sim.team2.length === 0
    )
        return;
    const unit1 = sim.team1[0];
    const unit2 = sim.team2[0];
    const dmg1to2 = unit1.getDamageAgainst(unit2, true);
    const dmg2to1 = unit2.getDamageAgainst(unit1, true);

    // Build upgrade chain from stat_chain data
    const buildUpgradeChain = (chain, classId) => {
        if (!chain || chain.length === 0) return [];
        const steps = [];
        let prevVal = null;
        for (const step of chain) {
            const attacks = step.attacks_json
                ? JSON.parse(step.attacks_json)
                : {};
            const armors = step.armors_json
                ? JSON.parse(step.armors_json)
                : {};
            const atkVal = attacks[classId] ?? null;
            const armorVal = armors[classId] ?? null;
            if (prevVal === null) {
                // Base stats
                steps.push({
                    tech: step.tech,
                    atk: atkVal,
                    armor: armorVal,
                    type: step.type,
                });
            } else {
                // Only record if the value changed
                if (
                    atkVal !== prevVal.atk ||
                    armorVal !== prevVal.armor
                ) {
                    steps.push({
                        tech: step.tech,
                        atk: atkVal,
                        armor: armorVal,
                        type: step.type,
                    });
                }
            }
            prevVal = { atk: atkVal, armor: armorVal };
        }
        return steps;
    };

    const buildFormula = (
        attacker,
        defender,
        dmgResult,
        atkStats,
        defStats,
    ) => {
        const isRanged = attacker.isRanged();
        const baseClass = isRanged ? "3" : "4";
        const baseAtk =
            attacker.attacks[baseClass] || atkStats.attack;
        const defArmorClass = isRanged ? "3" : "4";
        const defArmor = isRanged
            ? (defender.armors["3"] ??
              defender.pierceArmor ??
              0)
            : (defender.armors["4"] ??
              defender.meleeArmor ??
              0);

        let html = "";

        // === ATTACK SECTION ===
        html += `<div class="formula-section"><div class="formula-label">Total Attack (${isRanged ? "Pierce" : "Melee"}):</div>`;
        html += `<div class="formula-value"><span class="attack-val">${baseAtk}</span></div>`;
        // Show attack upgrade chain
        const atkChain = buildUpgradeChain(
            atkStats.stat_chain,
            baseClass,
        );
        if (atkChain.length > 0) {
            html += `<div style="margin-top:4px;padding-left:8px;">`;
            for (const step of atkChain) {
                const val = step.atk ?? 0;
                const label =
                    step.type === "base"
                        ? step.tech
                        : step.tech;
                html += `<div style="font-size:0.65rem;color:var(--text-muted);">${label}: <span style="color:#f39c12">${val}</span></div>`;
            }
            html += `</div>`;
        }
        html += `</div>`;

        // === BONUS ATTACK SECTION ===
        const bonuses = dmgResult.breakdown.filter(
            (b) =>
                b.applies &&
                b.classId !== "3" &&
                b.classId !== "4" &&
                b.damage > 0,
        );
        if (bonuses.length > 0) {
            html += `<div class="formula-section"><div class="formula-label">+ Bonus Attack:</div><div class="formula-value" style="flex-direction:column;align-items:flex-start;gap:2px;">`;
            for (const b of bonuses) {
                html += `<div class="bonus-item">+${b.attack}`;
                if (b.armor && b.armor > 0)
                    html += ` <span style="color:var(--team2);font-size:0.7rem">&minus;${b.armor}</span>`;
                html += ` = <span style="color:#fff">${b.damage}</span> <span class="class-tag">${b.className}</span></div>`;
            }
            html += `</div></div>`;
        }

        // === DEFENSE SECTION ===
        html += `<div class="formula-section"><div class="formula-label">&minus; Total Defense (${isRanged ? "Pierce" : "Melee"} Armor):</div>`;
        html += `<div class="formula-value"><span class="armor-val">${defArmor}</span></div>`;
        // Show defense upgrade chain
        const defChain = buildUpgradeChain(
            defStats.stat_chain,
            defArmorClass,
        );
        if (defChain.length > 0) {
            html += `<div style="margin-top:4px;padding-left:8px;">`;
            for (const step of defChain) {
                const val = step.armor ?? 0;
                html += `<div style="font-size:0.65rem;color:var(--text-muted);">${step.tech}: <span style="color:var(--team2)">${val}</span></div>`;
            }
            html += `</div>`;
        }
        html += `</div>`;

        // === BONUS ARMOR SECTION ===
        const defBonuses = dmgResult.breakdown.filter(
            (b) =>
                b.applies &&
                b.classId !== "3" &&
                b.classId !== "4" &&
                b.armor > 0 &&
                b.damage < b.attack,
        );
        if (defBonuses.length > 0) {
            html += `<div class="formula-section"><div class="formula-label">&minus; Bonus Armor:</div><div class="formula-value" style="flex-direction:column;align-items:flex-start;gap:2px;">`;
            for (const b of defBonuses) {
                html += `<div><span style="color:var(--team2)">${b.armor}</span> <span class="class-tag">${b.className}</span></div>`;
            }
            html += `</div></div>`;
        }

        // === TOTAL ===
        html += `<div class="formula-result"><div class="formula-label">Damage per Hit:</div>`;
        html += `<div class="formula-total">${dmgResult.total}</div></div>`;

        // === SPECIAL MECHANICS ===
        const mechanics = [];
        if (attacker.passThroughPercent > 0)
            mechanics.push(
                `Pass-through: ${Math.round(attacker.passThroughPercent * 100)}% damage to 1 unit behind target`,
            );
        if (
            attacker.tramplePercent > 0 ||
            attacker.trampleFlatDamage > 0
        ) {
            const parts = [];
            if (attacker.tramplePercent > 0)
                parts.push(
                    `${Math.round(attacker.tramplePercent * 100)}%`,
                );
            if (attacker.trampleFlatDamage > 0)
                parts.push(
                    `+${attacker.trampleFlatDamage} flat`,
                );
            mechanics.push(
                `Trample: ${parts.join(" ")} to nearby units`,
            );
        }
        if (attacker.extraProjectiles > 0)
            mechanics.push(
                `+${attacker.extraProjectiles} extra projectile${attacker.extraProjectiles > 1 ? "s" : ""}`,
            );
        if (attacker.ignoresPierceArmor)
            mechanics.push("Ignores pierce armor");
        if (attacker.ignoresMeleeArmor)
            mechanics.push("Ignores melee armor");
        if (attacker.bleedDps > 0)
            mechanics.push(
                `Bleed: ${attacker.bleedDps} DPS for ${attacker.bleedDuration}s`,
            );
        if (attacker.hpRegen > 0)
            mechanics.push(
                `HP Regen: ${attacker.hpRegen} HP/min`,
            );
        if (attacker.dodgeShieldMax > 0)
            mechanics.push(
                `Dodge Shield: ${attacker.dodgeShieldMax} charges`,
            );
        if (defender.bonusDamageReduction > 0)
            mechanics.push(
                `Target resists ${Math.round(defender.bonusDamageReduction * 100)}% bonus damage`,
            );
        if (mechanics.length > 0) {
            html += `<div style="margin-top:6px;padding:4px 6px;border-left:2px solid var(--gold);font-size:0.65rem;color:var(--text-muted)">`;
            for (const m of mechanics) {
                html += `<div>${m}</div>`;
            }
            html += `</div>`;
        }

        return html;
    };

    const team1CivSafe = escapeHtml(sim.team1Stats.civ);
    const team1NameSafe = escapeHtml(sim.team1Stats.name);
    const team2CivSafe = escapeHtml(sim.team2Stats.civ);
    const team2NameSafe = escapeHtml(sim.team2Stats.name);

    let html = "";
    html += `<div class="debug-section team1"><h4>${team1CivSafe} ${team1NameSafe}</h4>`;
    html += `<h5 style="color:var(--text-muted);margin-bottom:8px;font-size:0.7rem">&rarr; vs ${team2CivSafe} ${team2NameSafe}</h5>`;
    html +=
        buildFormula(
            unit1,
            unit2,
            dmg1to2,
            sim.team1Stats,
            sim.team2Stats,
        ) + `</div>`;

    html += `<div class="debug-section team2"><h4>${team2CivSafe} ${team2NameSafe}</h4>`;
    html += `<h5 style="color:var(--text-muted);margin-bottom:8px;font-size:0.7rem">&rarr; vs ${team1CivSafe} ${team1NameSafe}</h5>`;
    html +=
        buildFormula(
            unit2,
            unit1,
            dmg2to1,
            sim.team2Stats,
            sim.team1Stats,
        ) + `</div>`;

    document.getElementById("debugContent").innerHTML = html;
}

// ===== INITIALIZATION =====
let pageSim = null;
let currentBattle = null;

document.addEventListener("DOMContentLoaded", async () => {
    const canvas = document.getElementById("battleCanvas");
    pageSim = new PageSim(canvas);
    // Nothing in the templates reaches for the old `simulation` global (grepped
    // at cutover), but this module declares nothing globally, so expose the
    // driver for console debugging and any future inline straggler.
    window.simulation = pageSim;

    // Load armor class names — injected into the engine, which uses them to
    // label bonus-damage rows.
    try {
        const resp = await fetch("/api/armor-classes");
        setArmorClassNames(await resp.json());
    } catch (e) {
        console.error("Failed to load armor classes:", e);
    }

    // Render initial selection UI
    initSelectionDelegation();
    initRailSearch();
    renderSelection(1);
    renderSelection(2);

    // Controls
    document
        .getElementById("startBtn")
        .addEventListener("click", startBattle);
    document
        .getElementById("pauseBtn")
        .addEventListener("click", () => {
            pageSim.pause();
            document.getElementById("pauseBtn").textContent =
                pageSim.paused ? "Resume" : "Pause";
        });
    document
        .getElementById("resetBtn")
        .addEventListener("click", () => {
            pageSim.reset();
            document.getElementById("pauseBtn").textContent = "Pause";
            // Return to the pick phase: rails expand, search returns, arena
            // shrinks, Start button comes back.
            setSimPhase(false);
        });

    // Damage-breakdown toggle (battle phase only).
    const dmgToggle = document.getElementById("dmgToggle");
    if (dmgToggle) {
        dmgToggle.addEventListener("click", () => {
            const panel = document.getElementById("debugPanel");
            if (!panel) return;
            const willOpen = panel.hidden;
            panel.hidden = !willOpen;
            dmgToggle.setAttribute("aria-expanded", String(willOpen));
        });
    }
    const speedSlider = document.getElementById("speedSlider");
    speedSlider.addEventListener("input", (e) => {
        pageSim.speedMultiplier = parseFloat(e.target.value);
        document.getElementById("speedLabel").textContent =
            `${e.target.value}x`;
    });
    // Sync the sim + label to the slider's initial value (defaults to 3x).
    pageSim.speedMultiplier = parseFloat(speedSlider.value);
    document.getElementById("speedLabel").textContent = `${speedSlider.value}x`;

    // Army mode toggle
    document
        .querySelectorAll('input[name="armyMode"]')
        .forEach((radio) => {
            radio.addEventListener("change", (e) => {
                const mode = e.target.value;
                if (mode === "count") {
                    document.getElementById(
                        "countInputs",
                    ).style.display = "flex";
                    document.getElementById(
                        "resourceInput",
                    ).style.display = "none";
                } else if (mode === "resources") {
                    document.getElementById(
                        "countInputs",
                    ).style.display = "none";
                    document.getElementById(
                        "resourceInput",
                    ).style.display = "flex";
                    document.getElementById(
                        "totalResources",
                    ).value = "3000";
                } else if (mode === "resources_upgrades") {
                    document.getElementById(
                        "countInputs",
                    ).style.display = "none";
                    document.getElementById(
                        "resourceInput",
                    ).style.display = "flex";
                    document.getElementById(
                        "totalResources",
                    ).value = "5000";
                }
                updateOptionsCurrent();
            });
        });

    // Keep the collapsed-options summary in sync as numbers change.
    ["team1Count", "team2Count", "totalResources"].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.addEventListener("input", updateOptionsCurrent);
    });
    updateOptionsCurrent();

    pageSim.render();

    // Handle URL params for deep-linking from ranking hover cards
    const params = new URLSearchParams(window.location.search);
    const dl = (typeof readSimParams === "function") ? readSimParams(window.location.search) : null;
    if (params.has("civ1") && params.has("unit1")) {
        const civ1 = params.get("civ1");
        const unit1 = params.get("unit1");
        if (dl && dl.age1) setTeamAge(1, dl.age1);
        await selectCiv(1, civ1);
        // Find unit in civ data by slug
        if (teamState[1].civData) {
            const units =
                teamState[1].civData.units_by_age[
                    teamState[1].age
                ] || [];
            const found = units.find((u) => u.unit_slug === unit1);
            if (found)
                selectUnit(1, found.unit_slug, found.unit_name);
        }
        if (dl && dl.relics1 != null) setRelics(1, dl.relics1);
        if (dl && dl.kills1 != null) setStartKills(1, dl.kills1);
    }
    if (params.has("civ2") && params.has("unit2")) {
        const civ2 = params.get("civ2");
        const unit2 = params.get("unit2");
        if (dl && dl.age2) setTeamAge(2, dl.age2);
        await selectCiv(2, civ2);
        if (teamState[2].civData) {
            const units =
                teamState[2].civData.units_by_age[
                    teamState[2].age
                ] || [];
            const found = units.find((u) => u.unit_slug === unit2);
            if (found)
                selectUnit(2, found.unit_slug, found.unit_name);
        }
        if (dl && dl.relics2 != null) setRelics(2, dl.relics2);
        if (dl && dl.kills2 != null) setStartKills(2, dl.kills2);
    }
    if (params.has("mode")) {
        const mode = params.get("mode");
        const radio = document.querySelector(
            `input[name="armyMode"][value="${mode}"]`,
        );
        if (radio) {
            radio.checked = true;
            radio.dispatchEvent(new Event("change"));
        }
        if (params.has("resources")) {
            const resEl = document.getElementById("totalResources");
            if (resEl) resEl.value = params.get("resources");
        }
        if (params.has("count1")) {
            const c1 = document.getElementById("team1Count");
            if (c1) c1.value = params.get("count1");
        }
        if (params.has("count2")) {
            const c2 = document.getElementById("team2Count");
            if (c2) c2.value = params.get("count2");
        }
    }
    if (dl && dl.autorun && teamState[1].unitSlug && teamState[2].unitSlug) {
        await startBattle();
    }
});

async function startBattle() {
    const s1 = teamState[1],
        s2 = teamState[2];
    if (!s1.unitSlug || !s1.civ || !s2.unitSlug || !s2.civ) {
        alert(
            "Please select a civilization and unit for both teams",
        );
        return;
    }

    try {
        document.getElementById("startBtn").disabled = true;
        document.getElementById("startBtn").textContent =
            "Loading...";

        const armyMode = document.querySelector(
            'input[name="armyMode"]:checked',
        ).value;
        let team1Count, team2Count;

        // Imperial-only: resource cost = Wood + Food + Gold (no age weighting).
        function calcUnitCost(s) {
            return (s.cost_wood || 0) + (s.cost_food || 0) + (s.cost_gold || 0);
        }
        function calcUpgradeCost(s) {
            return (
                (s.upgrade_cost_wood || 0) +
                (s.upgrade_cost_food || 0) +
                (s.upgrade_cost_gold || 0)
            );
        }

        // ONE fetch per team regardless of army mode: the army size is derived
        // from these dicts and the very same objects are handed to the engine,
        // which deep-copies before applying the relic delta — so the counts and
        // the spawned units can never disagree.
        const [stats1, stats2] = await Promise.all([
            fetch(
                `/api/ref/combat-unit/${encodeURIComponent(s1.civ)}/${s1.unitSlug}?age=${encodeURIComponent(s1.age)}`,
            ).then((r) => r.json()),
            fetch(
                `/api/ref/combat-unit/${encodeURIComponent(s2.civ)}/${s2.unitSlug}?age=${encodeURIComponent(s2.age)}`,
            ).then((r) => r.json()),
        ]);
        if (stats1.error) throw new Error(stats1.error);
        if (stats2.error) throw new Error(stats2.error);

        if (
            armyMode === "resources" ||
            armyMode === "resources_upgrades"
        ) {
            const totalResources =
                parseInt(
                    document.getElementById("totalResources").value,
                ) || 3000;

            const unitCost1 = calcUnitCost(stats1) || stats1.total_cost;
            const unitCost2 = calcUnitCost(stats2) || stats2.total_cost;

            let budget1 = totalResources,
                budget2 = totalResources;
            if (armyMode === "resources_upgrades") {
                budget1 -= calcUpgradeCost(stats1);
                budget2 -= calcUpgradeCost(stats2);
                budget1 = Math.max(budget1, unitCost1); // at least 1 unit
                budget2 = Math.max(budget2, unitCost2);
            }

            team1Count = Math.max(
                1,
                Math.floor(budget1 / unitCost1),
            );
            team2Count = Math.max(
                1,
                Math.floor(budget2 / unitCost2),
            );
        } else {
            // "30 vs 30" mode: the entered number is a POPULATION budget, not a
            // raw unit count. Half-pop units (Karambit Warrior 0.5, Blackwood
            // Archer 0.5) therefore field 2x as many units for the same pop
            // (30 pop -> 60 units). Mirrors simulation_real._calc_count
            // (count = int(fixed_count / pop_space)) which drives the matchup
            // table, so the on-page sim and the table agree. No-op for the 1847
            // units that take 1.0 pop.
            const pop1 =
                parseInt(
                    document.getElementById("team1Count").value,
                ) || 30;
            const pop2 =
                parseInt(
                    document.getElementById("team2Count").value,
                ) || 30;
            const popSpace1 = stats1.pop_space || 1.0;
            const popSpace2 = stats2.pop_space || 1.0;
            team1Count = Math.max(1, Math.floor(pop1 / popSpace1));
            team2Count = Math.max(1, Math.floor(pop2 / popSpace2));
        }

        pageSim.reset();

        // Hand the preloaded artwork to the renderer. Legacy stamped these onto
        // every unit in setupTeam; sprites are a rendering concern now, so the
        // renderer holds them per team instead.
        pageSim.renderer.setTeamAssets(1, {
            img: unitImages[1],
            isSprite: unitIsSprite[1],
            sheet: unitSheets[1],
        });
        pageSim.renderer.setTeamAssets(2, {
            img: unitImages[2],
            isSprite: unitIsSprite[2],
            sheet: unitSheets[2],
        });

        // Fresh seed per battle. Math.random is fine HERE — the ban on unseeded
        // randomness is an engine rule; the page picks the seed and logs it so a
        // surprising fight can be replayed exactly.
        const seed = (Math.random() * 2 ** 32) >>> 0;
        console.log("battle seed:", seed);
        pageSim.setup({
            teams: [
                {
                    combatDict: stats1,
                    slug: s1.unitSlug,
                    civ: s1.civ,
                    count: team1Count,
                    relics: s1.relics,
                    startKills: s1.startKills,
                },
                {
                    combatDict: stats2,
                    slug: s2.unitSlug,
                    civ: s2.civ,
                    count: team2Count,
                    relics: s2.relics,
                    startKills: s2.startKills,
                },
            ],
            seed,
        });

        // The ONE piece of artwork the engine still needs: BattleUnit.
        // triggerAttackAnim() sizes its post-swing animation latch from the
        // attack sheet's frame count/duration (falling back to 0.4s without
        // one), so the sheet has to be on the unit as well as in the renderer.
        for (const u of pageSim.sim.team1) u.attackSheet = unitSheets[1];
        for (const u of pageSim.sim.team2) u.attackSheet = unitSheets[2];

        const team1Stats = pageSim.sim.team1Stats;
        const team2Stats = pageSim.sim.team2Stats;
        currentBattle = {
            team1_civ: s1.civ,
            team1_unit: s1.unitSlug,
            team1_unit_name: team1Stats?.name || s1.unitName,
            team1_count: team1Count,
            team1_total_cost: team1Stats.total_cost * team1Count,
            team1_unit_cost: team1Stats.total_cost,
            team1_max_hp: team1Stats.hp,
            team2_civ: s2.civ,
            team2_unit: s2.unitSlug,
            team2_unit_name: team2Stats?.name || s2.unitName,
            team2_count: team2Count,
            team2_total_cost: team2Stats.total_cost * team2Count,
            team2_unit_cost: team2Stats.total_cost,
            team2_max_hp: team2Stats.hp,
            winner: null,
        };

        // Winner banner text: page-selection strings the engine cannot supply.
        pageSim.renderer.setLabels({
            team1Civ: s1.civ,
            team1Unit: currentBattle.team1_unit_name,
            team2Civ: s2.civ,
            team2Unit: currentBattle.team2_unit_name,
        });

        // Populate progress headers
        document.getElementById("prog1Name").textContent =
            `${s1.civ} ${currentBattle.team1_unit_name}`;
        document.getElementById("prog2Name").textContent =
            `${s2.civ} ${currentBattle.team2_unit_name}`;
        const icon1 = document.getElementById("prog1Icon");
        const icon2 = document.getElementById("prog2Icon");
        if (unitImages[1]?.src) {
            icon1.src = unitImages[1].src;
            icon1.classList.toggle("sprite", !!unitIsSprite[1]);
            icon1.style.display = "";
        }
        if (unitImages[2]?.src) {
            icon2.src = unitImages[2].src;
            icon2.classList.toggle("sprite", !!unitIsSprite[2]);
            icon2.style.display = "";
        }

        document.getElementById("startBtn").textContent =
            "Start Battle";
        document.getElementById("pauseBtn").disabled = false;
        document.getElementById("resetBtn").disabled = false;
        pageSim.start();

        // Expand the arena, shrink the rails to the picked unit + live stats.
        setSimPhase(true);
        // On a phone (3-row stack) the arena is the middle row — bring it up.
        const stageEl = document.getElementById("simStage");
        if (stageEl && typeof stageEl.scrollIntoView === "function") {
            stageEl.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
        document.getElementById("startBtn").disabled = false;
        document.getElementById("startBtn").textContent =
            "Start Battle";
    }
}

function updateBattleWinner(winner) {
    if (currentBattle) currentBattle.winner = winner;
}

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && pageSim) pageSim.pause();
});

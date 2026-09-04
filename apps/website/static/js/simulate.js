/*
 * Role: page — the Battle Sim page shell served at /.
 *
 * The battle runs in a module worker using the shared simulationv3 engine.
 * The page owns selection, playback and the live readout; Golden Arena and its
 * units are drawn by the shared production map renderer.
 *
 * This file is an ES module (templates/simulate.html loads it with
 * type="module"), so it can read the classic scripts' globals — constants.js,
 * unit_sprites.js, api_client.js, sim_params.js and the template's UNIT_SEARCH —
 * but nothing it declares is global. Page functions are wired up through
 * addEventListener, never through inline on*= attributes.
 */

import {
    buildSelectionPreviewUnits,
    createMapRenderer,
} from "/v3-runtime/viewer/map-renderer.js";

const RELIC_MAX = 0;
const KILL_BONUS_MAX = 0;

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
    return false;
}
function hasKillOption(state) {
    return false;
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
// Play is enabled only once both teams have a civ + unit; otherwise the hint
// tells first-time visitors exactly what's missing.
function updateStartReady() {
    const ready = !!(
        teamState[1].civ && teamState[1].unitSlug &&
        teamState[2].civ && teamState[2].unitSlug
    );
    const btn = document.getElementById("playPauseBtn");
    const hint = document.getElementById("startHint");
    if (btn) btn.disabled = battleLoading || !ready;
    if (hint) hint.hidden = ready || !!pageSim?.config;
    return ready;
}

function refreshArenaPreview() {
    pageSim?.showSelectionPreview(teamState, unitImages);
}

function formatResourceBudget(value) {
    const budget = parseInt(value, 10) || 5000;
    if (budget >= 1000 && budget % 1000 === 0) return `${budget / 1000}K`;
    if (budget >= 1000) return `${(budget / 1000).toFixed(1).replace(/\.0$/, "")}K`;
    return String(budget);
}

// Keep the collapsed options summary showing the current army setup.
function updateOptionsCurrent() {
    const el = document.getElementById("optionsCurrent");
    if (!el) return;
    const checked = document.querySelector('input[name="armyMode"]:checked');
    const mode = checked ? checked.value : "resources";
    const res = (document.getElementById("totalResources") || {}).value;
    if (mode === "resources") {
        el.textContent = `${formatResourceBudget(res)} resources`;
    } else {
        const count = (document.getElementById("equalCount") || {}).value || "15";
        el.textContent = `${count} each`;
    }
}

function isBattlePickerUnit(unit) {
    const type = String(unit?.unit_type || "").toLowerCase();
    const unitClass = String(unit?.unit_class_name || "").toLowerCase();
    const slug = String(unit?.unit_slug || unit?.slug || "").toLowerCase();
    return type !== "naval"
        && unitClass !== "unknown"
        && !slug.includes("trebuchet");
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
                (state.civData.units_by_age[state.age] || [])
                    .filter(isBattlePickerUnit);
            html += '<div class="unit-grid">';
            for (const u of units) {
                const useSprite =
                    typeof hasSprite === "function" &&
                    hasSprite(u.unit_name);
                const iUrl = useSprite
                    ? spriteFor(u.unit_name)
                    : unitIconUrl(u.unit_name);
                const imgCls = useSprite ? ' class="sprite"' : "";
                const nameSafe = escapeHtml(u.unit_name);
                const slugSafe = escapeHtml(u.unit_slug);
                html += `<div class="unit-pick" title="${nameSafe}" data-action="selectUnit" data-team="${teamNum}" data-slug="${slugSafe}" data-name="${nameSafe}">
                            <img${imgCls} src="${iUrl}" alt="${nameSafe}" onerror="this.style.display='none'" />
                            <span>${nameSafe}</span>
                        </div>`;
            }
            html += "</div>";
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

function leaveBattleForRosterEdit() {
    if (!pageSim?.config) return;
    currentBattle = null;
    pageSim.reset();
    setSimPhase(false);
}

async function selectCiv(teamNum, civName) {
    leaveBattleForRosterEdit();
    const state = teamState[teamNum];
    state.civ = civName;
    state.unitSlug = null;
    state.unitName = null;
    state.civData = null;
    renderSelection(teamNum);
    refreshArenaPreview();

    // Fetch civ data
    try {
        state.civData = await apiGet(`/api/ref/civ/${civName}`);
    } catch (e) {
        console.error("Failed to load civ data:", e);
    }
    renderSelection(teamNum);
}

function clearCiv(teamNum) {
    leaveBattleForRosterEdit();
    teamState[teamNum].civ = null;
    teamState[teamNum].unitSlug = null;
    teamState[teamNum].unitName = null;
    teamState[teamNum].civData = null;
    renderSelection(teamNum);
    refreshArenaPreview();
}

function setTeamAge(teamNum, age) {
    leaveBattleForRosterEdit();
    teamState[teamNum].age = age;
    teamState[teamNum].unitSlug = null;
    teamState[teamNum].unitName = null;
    renderSelection(teamNum);
    refreshArenaPreview();
}

function selectUnit(teamNum, slug, name) {
    leaveBattleForRosterEdit();
    teamState[teamNum].unitSlug = slug;
    teamState[teamNum].unitName = name;
    // Preload canvas image: the red idle sprite (both teams) when the unit has a
    // square sprite, else the portrait. Teams are told apart by HP-bar colour, not
    // sprite colour, so the unit doesn't flip colour when its (red) attack anim
    // plays. unitIsSprite drives no-circle render.
    const url = spriteFor(name, teamNum);
    if (url) {
        const img = new Image();
        img.addEventListener("load", refreshArenaPreview, { once: true });
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
    refreshArenaPreview();
}

function clearUnit(teamNum) {
    leaveBattleForRosterEdit();
    teamState[teamNum].unitSlug = null;
    teamState[teamNum].unitName = null;
    renderSelection(teamNum);
    refreshArenaPreview();
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
        if (!isBattlePickerUnit(u)) continue;
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
// stats. The media controls remain in place below the arena in every phase.
function setSimPhase(battle) {
    const stage = document.getElementById("simStage");
    if (stage) stage.classList.toggle("battle-active", battle);
    const hide = (id, h) => {
        const el = document.getElementById(id);
        if (el) el.hidden = h;
    };
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
        updateStartReady();
    }
    syncPlayerControls();
}

function syncPlayerControls() {
    const button = document.getElementById("playPauseBtn");
    const stage = document.getElementById("simStage");
    if (!button) return;

    const ready = !!(
        teamState[1].civ && teamState[1].unitSlug &&
        teamState[2].civ && teamState[2].unitSlug
    );
    button.disabled = battleLoading || !ready;
    button.classList.toggle("loading", battleLoading);
    stage?.classList.toggle(
        "battle-running",
        !!pageSim?.running && !pageSim.paused,
    );

    if (battleLoading) {
        button.dataset.state = "loading";
        button.setAttribute("aria-label", "Preparing battle");
    } else if (pageSim?.running && !pageSim.paused) {
        button.dataset.state = "pause";
        button.setAttribute("aria-label", "Pause battle");
    } else if (pageSim?.running && pageSim.paused) {
        button.dataset.state = "play";
        button.setAttribute("aria-label", "Resume battle");
    } else if (pageSim?.complete) {
        button.dataset.state = "replay";
        button.setAttribute("aria-label", "Replay with a new random battle");
    } else {
        button.dataset.state = "play";
        button.setAttribute("aria-label", "Start battle");
    }
}

// ===== PAGE-SIDE V3 PLAYBACK DRIVER =====
function deepFreeze(value, visited = new Set()) {
    if (!value || typeof value !== "object" || visited.has(value)) return value;
    visited.add(value);
    for (const child of Object.values(value)) deepFreeze(child, visited);
    return Object.freeze(value);
}

class PageSim {
    constructor(canvas) {
        this.canvas = canvas;
        this.renderer = null;
        this.previewPlacementByOwner = null;
        this.worker = null;
        this.config = null;
        this.unitIndex = new Map();
        this.snapshots = [];
        this.cursor = 0;
        this.latestSnapshot = null;
        this.result = null;
        this.complete = false;
        this.playheadTick = 0;
        this.runId = 0;
        this.animationFrame = null;
        this.speedMultiplier = 1.0;
        this.running = false;
        this.paused = false;
        this.lastTimestamp = 0;
        this.resizeObserver = new ResizeObserver(() => this.renderer?.resize());
        this.resizeObserver.observe(canvas);
    }

    get winner() {
        return this.result?.winnerOwner ?? null;
    }

    setStatus(message, isError = false) {
        const element = document.getElementById("v3MapStatus");
        if (!element) return;
        element.textContent = message;
        element.classList.toggle("error", isError);
    }

    ensureRenderer(map) {
        if (this.renderer) return;
        this.renderer = createMapRenderer(
            this.canvas,
            map,
            {
                presentation: "production",
                unitScale: 0.9,
            },
        );
    }

    initializeArena({ map, placementByOwner }) {
        this.ensureRenderer(map);
        this.previewPlacementByOwner = placementByOwner;
        this.renderer.setUnits([]);
        this.renderer.resize();
    }

    showSelectionPreview(selections, images) {
        if (!this.renderer || !this.previewPlacementByOwner || this.running) return;
        const previewCounts = {};
        const input = document.getElementById("equalCount");
        const count = Math.min(27, Math.max(1,
            parseInt(input?.value, 10) || 15));
        for (const teamNumber of [1, 2]) {
            previewCounts[teamNumber] = count;
            this.renderer.setUnitAssets(teamNumber === 1 ? 2 : 3, {
                img: images[teamNumber],
                sheet: null,
            });
        }
        this.renderer.setUnits(buildSelectionPreviewUnits(
            selections,
            this.previewPlacementByOwner,
            previewCounts,
        ));
    }

    buildUnitIndex(config) {
        const index = new Map();
        const addArmy = (owner, team, count) => {
            const base = owner === 2 ? 9000 : owner === 3 ? 9500 : 10000;
            for (let offset = 0; offset < count; offset += 1) {
                index.set(base + offset, {
                    owner,
                    slug: team.mechanics.unit_slug,
                    label: team.unit_name,
                    master: team.mechanics.unit_master,
                    mechanics: team.mechanics,
                });
            }
        };
        addArmy(2, config.teams[0], config.teams[0].count);
        addArmy(3, config.teams[1], config.teams[1].count);
        const auxiliary = config.scenario.auxiliaryArmiesByOwner || {};
        for (const [ownerText, army] of Object.entries(auxiliary)) {
            const owner = Number(ownerText);
            addArmy(owner, {
                unit_name: army.unit_name || "Scout Cavalry",
                mechanics: army.mechanics,
            }, army.cells.length);
        }
        return index;
    }

    rendererSnapshot(snapshot) {
        const units = snapshot.units.map((row) => {
            const [referenceId, x, y, facing, hp, alive, action,
                pursuitTargetId, engagedTargetId, attackTargetId] = row;
            const meta = this.unitIndex.get(referenceId);
            if (!meta) throw new Error(`Missing unit metadata for ${referenceId}`);
            return {
                referenceId,
                x,
                y,
                facing,
                hp,
                alive: alive === 1,
                action,
                pursuitTargetId,
                engagedTargetId,
                attackTargetId,
                owner: meta.owner,
                slug: meta.slug,
                label: meta.label,
                unitMaster: meta.master,
                mechanics: meta.mechanics,
            };
        });
        return deepFreeze({
            tick: snapshot.tick,
            units,
            events: snapshot.events,
            ...(snapshot.navigation ? { navigation: snapshot.navigation } : {}),
        });
    }

    setup({ config, assets }) {
        this.stop();
        this.config = deepFreeze(config);
        this.unitIndex = this.buildUnitIndex(this.config);
        this.snapshots = [];
        this.cursor = 0;
        this.latestSnapshot = null;
        this.result = null;
        this.complete = false;
        this.playheadTick = 0;
        this.paused = false;
        this.ensureRenderer(this.config.scenario.mapFixture.map);
        this.renderer.showFormation();
        this.renderer.setUnitAssets(2, assets[2]);
        this.renderer.setUnitAssets(3, assets[3]);
        if (assets[4]) this.renderer.setUnitAssets(4, assets[4]);
        this.renderer.resize();

        const runId = ++this.runId;
        this.worker = new Worker("/static/js/v3_sim_worker.js", { type: "module" });
        this.worker.onmessage = ({ data }) => {
            if (data?.runId !== runId) return;
            if (data.type === "started") {
                this.setStatus("Battle in progress");
            } else if (data.type === "snapshots") {
                this.snapshots.push(...data.snapshots);
            } else if (data.type === "complete") {
                this.result = data.result;
                this.complete = true;
                this.worker?.terminate();
                this.worker = null;
            } else if (data.type === "error") {
                console.error("simulationv3 worker failed", data.error, data.stack);
                this.complete = true;
                this.running = false;
                this.setStatus(`Simulation error: ${data.error}`, true);
                syncPlayerControls();
                this.worker?.terminate();
                this.worker = null;
            }
        };
        this.worker.onerror = (event) => {
            console.error(
                `simulationv3 worker error: ${event.message || "unknown error"} `
                + `at ${event.filename || "worker"}:${event.lineno || 0}:${event.colno || 0}`,
            );
            this.complete = true;
            this.running = false;
            this.setStatus("Simulation worker failed to load", true);
            syncPlayerControls();
        };
        this.worker.postMessage({ runId, config: this.config });
        this.setStatus("Preparing battle…");
    }

    start() {
        if (!this.config) {
            alert("Please configure both teams");
            return;
        }
        this.running = true;
        this.paused = false;
        this.lastTimestamp = performance.now();
        updateStats(null, this.unitIndex);
        syncPlayerControls();
        this.loop();
    }

    pause() {
        if (!this.running) return;
        this.paused = !this.paused;
        if (!this.paused) {
            this.lastTimestamp = performance.now();
            this.loop();
        }
        syncPlayerControls();
    }

    stop() {
        if (this.animationFrame !== null) cancelAnimationFrame(this.animationFrame);
        this.animationFrame = null;
        this.worker?.terminate();
        this.worker = null;
        this.running = false;
        this.paused = false;
    }

    reset() {
        this.stop();
        this.config = null;
        this.snapshots = [];
        this.cursor = 0;
        this.latestSnapshot = null;
        this.result = null;
        this.complete = false;
        this.playheadTick = 0;
        updateStats(null);
        this.renderer?.showFormation();
        this.setStatus("Golden Arena ready");
        syncPlayerControls();
    }

    loop() {
        if (!this.running || this.paused) return;
        const now = performance.now();
        const elapsed = Math.min((now - this.lastTimestamp) / 1000, 0.25);
        this.lastTimestamp = now;
        if (this.cursor < this.snapshots.length || this.complete) {
            this.playheadTick += elapsed * this.speedMultiplier * 60;
        }
        while (
            this.cursor < this.snapshots.length
            && this.snapshots[this.cursor].tick <= this.playheadTick
        ) {
            this.latestSnapshot = this.snapshots[this.cursor];
            this.cursor += 1;
        }
        if (this.latestSnapshot) {
            const snapshot = this.rendererSnapshot(this.latestSnapshot);
            this.renderer.setSimulationSnapshot(snapshot);
            updateStats(snapshot, this.unitIndex);
        }
        if (this.complete && this.cursor >= this.snapshots.length && this.result) {
            this.running = false;
            updateBattleWinner(this.result.winnerOwner);
            const winningTeam = this.result.winnerOwner === 2 ? 1 : 2;
            const winner = this.config.teams[winningTeam - 1];
            const remaining = Math.round(this.result.winnerHp);
            this.setStatus(`${winner.civ} ${winner.unit_name} wins · ${remaining} HP remaining`);
            syncPlayerControls();
        } else {
            this.animationFrame = requestAnimationFrame(() => this.loop());
        }
    }

    render() {
        this.renderer?.resize();
    }
}

// ===== LIVE STAT READOUT =====
function updateStats(snapshot, unitIndex = new Map()) {
    const rows = { 2: [], 3: [] };
    for (const unit of snapshot?.units || []) {
        if (unit.owner === 2 || unit.owner === 3) rows[unit.owner].push(unit);
    }
    const t1Alive = rows[2].filter((unit) => unit.alive);
    const t2Alive = rows[3].filter((unit) => unit.alive);
    const t1Hp = snapshot
        ? t1Alive.reduce((sum, unit) => sum + unit.hp, 0)
        : (currentBattle?.team1_start_hp || 0);
    const t2Hp = snapshot
        ? t2Alive.reduce((sum, unit) => sum + unit.hp, 0)
        : (currentBattle?.team2_start_hp || 0);
    const t1AliveCount = snapshot ? t1Alive.length : (currentBattle?.team1_count || 0);
    const t2AliveCount = snapshot ? t2Alive.length : (currentBattle?.team2_count || 0);
    const battleTime = (snapshot?.tick ?? 0) / 60;

    document.getElementById("battleTimer").textContent =
        `${battleTime.toFixed(1)}s`;

    document.getElementById("prog1Units").textContent =
        `${t1AliveCount} / ${rows[2].length || currentBattle?.team1_count || 0}`;
    document.getElementById("prog1Hp").textContent =
        `${Math.round(t1Hp)} / ${Math.round(currentBattle?.team1_start_hp || 0)}`;
    if (currentBattle) {
        document.getElementById("prog1Res").textContent =
            currentBattle.team1_total_cost;
        const lostFraction = currentBattle.team1_start_hp > 0
            ? 1 - t1Hp / currentBattle.team1_start_hp : 0;
        const t1Lost = Math.round(currentBattle.team1_total_cost * lostFraction);
        document.getElementById("prog1Lost").textContent =
            t1Lost;
    }

    document.getElementById("prog2Units").textContent =
        `${t2AliveCount} / ${rows[3].length || currentBattle?.team2_count || 0}`;
    document.getElementById("prog2Hp").textContent =
        `${Math.round(t2Hp)} / ${Math.round(currentBattle?.team2_start_hp || 0)}`;
    if (currentBattle) {
        document.getElementById("prog2Res").textContent =
            currentBattle.team2_total_cost;
        const lostFraction = currentBattle.team2_start_hp > 0
            ? 1 - t2Hp / currentBattle.team2_start_hp : 0;
        const t2Lost = Math.round(currentBattle.team2_total_cost * lostFraction);
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
let battleLoading = false;
const PLAYBACK_SPEEDS = [1, 2, 5, 10];
let playbackSpeedIndex = 0;

function setPlaybackSpeed(index) {
    playbackSpeedIndex = ((index % PLAYBACK_SPEEDS.length) + PLAYBACK_SPEEDS.length)
        % PLAYBACK_SPEEDS.length;
    const speed = PLAYBACK_SPEEDS[playbackSpeedIndex];
    if (pageSim) pageSim.speedMultiplier = speed;
    const label = document.getElementById("speedLabel");
    const button = document.getElementById("speedBtn");
    if (label) label.textContent = `${speed}×`;
    if (button) button.setAttribute("aria-label", `Playback speed ${speed}x`);
}

document.addEventListener("DOMContentLoaded", async () => {
    const canvas = document.getElementById("battleCanvas");
    pageSim = new PageSim(canvas);
    // Nothing in the templates reaches for the old `simulation` global (grepped
    // at cutover), but this module declares nothing globally, so expose the
    // driver for console debugging and any future inline straggler.
    window.simulation = pageSim;

    try {
        const response = await fetch("/api/v3/arena-preview");
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        pageSim.initializeArena(await response.json());
    } catch (error) {
        console.error("Could not load the Golden Arena preview", error);
        pageSim.setStatus("Could not load the arena preview", true);
    }

    // Render initial selection UI
    initSelectionDelegation();
    initRailSearch();
    renderSelection(1);
    renderSelection(2);

    // Video-player controls: the first play starts the simulation, play/pause
    // toggles during it, and replay starts a fresh randomized run.
    document.getElementById("playPauseBtn").addEventListener("click", async () => {
        if (battleLoading) return;
        if (pageSim.running) {
            pageSim.pause();
            return;
        }
        await startBattle();
    });
    document.getElementById("speedBtn").addEventListener("click", () => {
        setPlaybackSpeed(playbackSpeedIndex + 1);
    });
    setPlaybackSpeed(0);

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
                }
                updateOptionsCurrent();
                refreshArenaPreview();
            });
        });

    // Keep the collapsed-options summary in sync as numbers change.
    ["equalCount", "totalResources"].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.addEventListener("input", () => {
            if (id === "equalCount") {
                const parsed = parseInt(el.value, 10);
                if (parsed > 27) el.value = "27";
            }
            updateOptionsCurrent();
            refreshArenaPreview();
        });
    });
    document.getElementById("equalCount")?.addEventListener("change", (event) => {
        event.target.value = String(Math.min(27, Math.max(1,
            parseInt(event.target.value, 10) || 15)));
        updateOptionsCurrent();
        refreshArenaPreview();
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
        const linkedCount = params.get("count1") || params.get("count2");
        if (linkedCount) {
            const count = document.getElementById("equalCount");
            if (count) count.value = String(Math.min(27, Math.max(1,
                parseInt(linkedCount, 10) || 15)));
        }
        updateOptionsCurrent();
        refreshArenaPreview();
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
        battleLoading = true;
        syncPlayerControls();
        document.getElementById("simOptions")?.removeAttribute("open");

        const armyMode = document.querySelector(
            'input[name="armyMode"]:checked',
        ).value;
        const seed = (Math.random() * 2 ** 32) >>> 0;
        const teams = [
            { civ: s1.civ, unit_slug: s1.unitSlug, age: s1.age },
            { civ: s2.civ, unit_slug: s2.unitSlug, age: s2.age },
        ];
        let army;
        if (armyMode === "resources") {
            army = {
                mode: "equal_resources",
                budget: parseInt(document.getElementById("totalResources").value, 10) || 5000,
                weights: { food: 1, wood: 1, gold: 1 },
                cap: 27,
            };
        } else {
            const count = Math.min(27, Math.max(1,
                parseInt(document.getElementById("equalCount").value, 10) || 15));
            document.getElementById("equalCount").value = String(count);
            teams[0].count = count;
            teams[1].count = count;
            army = { mode: "explicit", cap: 27 };
        }

        const response = await fetch("/api/v3/battle-config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                teams,
                army,
                engagement_mode: document.getElementById("rangedBuffer")?.checked
                    ? "ranged_buffer"
                    : "direct",
                seed,
            }),
        });
        const config = await response.json();
        if (!response.ok || config.error) {
            throw new Error(config.detail || config.error || `HTTP ${response.status}`);
        }
        const unitCost = (mechanics) => {
            const cost = mechanics.cost;
            return cost.food + cost.wood + cost.gold;
        };
        const [team1, team2] = config.teams;
        const team1Cost = unitCost(team1.mechanics);
        const team2Cost = unitCost(team2.mechanics);
        currentBattle = {
            team1_civ: team1.civ,
            team1_unit: team1.unit_slug,
            team1_unit_name: team1.unit_name,
            team1_count: team1.count,
            team1_total_cost: team1Cost * team1.count,
            team1_unit_cost: team1Cost,
            team1_max_hp: team1.mechanics.hp,
            team1_start_hp: team1.mechanics.hp * team1.count,
            team2_civ: team2.civ,
            team2_unit: team2.unit_slug,
            team2_unit_name: team2.unit_name,
            team2_count: team2.count,
            team2_total_cost: team2Cost * team2.count,
            team2_unit_cost: team2Cost,
            team2_max_hp: team2.mechanics.hp,
            team2_start_hp: team2.mechanics.hp * team2.count,
            winner: null,
        };

        const assets = {
            2: { img: unitImages[1], sheet: unitSheets[1] },
            3: { img: unitImages[2], sheet: unitSheets[2] },
        };
        if (config.scenario.hasRangedBuffer) {
            const img = new Image();
            img.src = spriteFor("Scout Cavalry", 4);
            const sheetMeta = typeof sheetFor === "function" ? sheetFor("Scout Cavalry") : null;
            let sheet = null;
            if (sheetMeta?.url) {
                const sheetImage = new Image();
                sheetImage.src = sheetMeta.url;
                sheet = { img: sheetImage, meta: sheetMeta };
            }
            assets[4] = { img, sheet };
        }

        pageSim.reset();
        pageSim.setup({
            config,
            assets,
        });

        updateOptionsCurrent();

        document.getElementById("prog1Name").textContent =
            `${team1.civ} ${team1.unit_name}`;
        document.getElementById("prog2Name").textContent =
            `${team2.civ} ${team2.unit_name}`;
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

        battleLoading = false;
        setSimPhase(true);
        pageSim.start();

        const stageEl = document.getElementById("simStage");
        if (stageEl && typeof stageEl.scrollIntoView === "function") {
            stageEl.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    } catch (error) {
        console.error(error);
        battleLoading = false;
        pageSim?.setStatus(`Could not start: ${error.message}`, true);
        alert(`Error: ${error.message}`);
        syncPlayerControls();
    }
}

function updateBattleWinner(winner) {
    if (currentBattle) currentBattle.winner = winner;
}

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && pageSim) pageSim.pause();
});

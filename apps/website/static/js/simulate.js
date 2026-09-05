import {ENABLED_CIVS, NAME_TO_ICON, UNIQUE_BUILDING, ICON_BASE, CIV_EMBLEM_BASE} from "./shared/catalog.js";
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

import { createPlaybackController } from "./battle/playback.js";
import { createStatisticsView } from "./battle/statistics.js";
import { LatestRequest, requestJson } from "./shared/api.js";
import { createTeamState, readBattleOptions } from "./battle/selection.js";

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
const teamState = createTeamState();

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
    const restartBtn = document.getElementById("restartBtn");
    const hint = document.getElementById("startHint");
    if (btn) btn.disabled = battleLoading || !ready;
    if (restartBtn) restartBtn.disabled = battleLoading || !ready || !pageSim?.config;
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
    if (mode === "resources") {
        const teamA = (document.getElementById("team1Resources") || {}).value || 5000;
        const teamB = (document.getElementById("team2Resources") || {}).value || 5000;
        el.textContent = `Resource-based · ${formatResourceBudget(teamA)} / ${formatResourceBudget(teamB)}`;
    } else {
        const teamA = (document.getElementById("team1Count") || {}).value || "27";
        const teamB = (document.getElementById("team2Count") || {}).value || "27";
        el.textContent = `Count-based · ${teamA} / ${teamB}`;
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
    battleRequest.cancel();
    battleLoading = false;
    cancelMatchupPreview();
    currentBattle = null;
    pageSim?.reset();
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

    const ticket = civRequests[teamNum].begin();
    try {
        const data = await requestJson(`/api/ref/civ/${encodeURIComponent(civName)}`, {signal:ticket.signal});
        if (!ticket.isCurrent() || state.civ !== civName) return;
        state.civData = data;
    } catch (e) {
        if (!ticket.isCurrent() || e.name === "AbortError") return;
        console.error("Failed to load civ data:", e);
    }
    renderSelection(teamNum);
    scheduleMatchupPreview();
}

function clearCiv(teamNum) {
    civRequests[teamNum].cancel();
    leaveBattleForRosterEdit();
    teamState[teamNum].civ = null;
    teamState[teamNum].unitSlug = null;
    teamState[teamNum].unitName = null;
    teamState[teamNum].civData = null;
    renderSelection(teamNum);
    refreshArenaPreview();
    scheduleMatchupPreview();
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
    scheduleMatchupPreview();
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
    if (item.type === "unit" && teamState[teamNum].civ === item.civ && teamState[teamNum].civData) {
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
    const showMatchupCards = battle || !!currentBattle;
    hide("team1Live", !showMatchupCards);
    hide("team2Live", !showMatchupCards);
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
    const restartButton = document.getElementById("restartBtn");
    const stage = document.getElementById("simStage");
    if (!button) return;

    const ready = !!(
        teamState[1].civ && teamState[1].unitSlug &&
        teamState[2].civ && teamState[2].unitSlug
    );
    button.disabled = battleLoading || !ready;
    if (restartButton) {
        restartButton.disabled = battleLoading || !ready || !pageSim?.config;
    }
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
        button.dataset.state = "play";
        button.setAttribute("aria-label", "Start a new battle");
    } else {
        button.dataset.state = "play";
        button.setAttribute("aria-label", "Start battle");
    }
}

// ===== PAGE-SIDE V3 PLAYBACK DRIVER =====
// ===== INITIALIZATION =====
let pageSim = null;
let currentBattle = null;
let battleLoading = false;
let matchupPreviewSequence = 0;
let matchupPreviewTimer = null;
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

const battleRequest = new LatestRequest();
const previewRequest = new LatestRequest();
const civRequests = {1: new LatestRequest(), 2: new LatestRequest()};
const buildBattlePayload = seed => readBattleOptions(teamState, seed);
const fetchBattleConfig = (payload, signal) => requestJson("/api/v3/battle-config", {method:"POST", body:payload, signal});

function cancelMatchupPreview() {
    previewRequest.cancel();
    matchupPreviewSequence += 1;
    if (matchupPreviewTimer !== null) {
        clearTimeout(matchupPreviewTimer);
        matchupPreviewTimer = null;
    }
}

function scheduleMatchupPreview(delay = 100) {
    cancelMatchupPreview();
    if (pageSim?.config) return;
    const ready = teamState[1].civ && teamState[1].unitSlug
        && teamState[2].civ && teamState[2].unitSlug;
    if (!ready) {
        currentBattle = null;
        setSimPhase(false);
        return;
    }
    const sequence = matchupPreviewSequence;
    matchupPreviewTimer = setTimeout(async () => {
        matchupPreviewTimer = null;
        try {
            const ticket = previewRequest.begin();
            const config = await fetchBattleConfig(buildBattlePayload(0), ticket.signal);
            if (!ticket.isCurrent()) return;
            if (sequence !== matchupPreviewSequence || pageSim?.config) return;
            renderMatchupCards(config);
        } catch (error) {
            if (sequence !== matchupPreviewSequence || error.name === "AbortError") return;
            console.error("Could not load matchup statistics", error);
            currentBattle = null;
            setSimPhase(false);
        }
    }, delay);
}

const {updateStats, renderMatchupCards} = createStatisticsView({
    getBattle: () => currentBattle, setBattle: value => {currentBattle = value;},
    getPageSim: () => pageSim, unitImages, unitIsSprite, setSimPhase,
});
const PageSim = createPlaybackController({updateStats, syncPlayerControls, updateBattleWinner});

document.addEventListener("DOMContentLoaded", async () => {
    const canvas = document.getElementById("battleCanvas");
    pageSim = new PageSim(canvas);
    // Nothing in the templates reaches for the old `simulation` global (grepped
    // at cutover), but this module declares nothing globally, so expose the
    // driver for console debugging and any future inline straggler.
    window.simulation = pageSim;

    try {
        pageSim.initializeArena(await requestJson("/api/v3/arena-preview"));
    } catch (error) {
        console.error("Could not load the Golden Arena preview", error);
        pageSim.setStatus("Could not load the arena preview", true);
    }

    // Render initial selection UI
    initSelectionDelegation();
    initRailSearch();
    renderSelection(1);
    renderSelection(2);

    // Video-player controls: Play starts or resumes, while the dedicated
    // restart control always starts a fresh randomized run.
    document.getElementById("playPauseBtn").addEventListener("click", async () => {
        if (battleLoading) return;
        if (pageSim.running) {
            pageSim.pause();
            return;
        }
        await startBattle();
    });
    document.getElementById("restartBtn").addEventListener("click", async () => {
        if (battleLoading || !pageSim.config) return;
        if (pageSim.running && !pageSim.paused) pageSim.pause();
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
    const invalidateBattleOptions = () => {
        if (battleLoading || pageSim?.config) leaveBattleForRosterEdit();
    };
    document
        .querySelectorAll('input[name="armyMode"]')
        .forEach((radio) => {
            radio.addEventListener("change", (e) => {
                invalidateBattleOptions();
                const mode = e.target.value;
                if (mode === "count") {
                    document.getElementById(
                        "countInputs",
                    ).style.display = "grid";
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
                scheduleMatchupPreview();
            });
        });

    // Keep the collapsed-options summary in sync as numbers change.
    ["team1Count", "team2Count", "team1Resources", "team2Resources"].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.addEventListener("input", () => {
            invalidateBattleOptions();
            if (id === "team1Count" || id === "team2Count") {
                const parsed = parseInt(el.value, 10);
                if (parsed > 27) el.value = "27";
            }
            updateOptionsCurrent();
            refreshArenaPreview();
            scheduleMatchupPreview();
        });
    });
    ["team1Count", "team2Count"].forEach((id) => {
        document.getElementById(id)?.addEventListener("change", (event) => {
            invalidateBattleOptions();
            event.target.value = String(Math.min(27, Math.max(1,
                parseInt(event.target.value, 10) || 27)));
            updateOptionsCurrent();
            refreshArenaPreview();
            scheduleMatchupPreview();
        });
    });
    ["team1Resources", "team2Resources"].forEach((id) => {
        document.getElementById(id)?.addEventListener("change", (event) => {
            invalidateBattleOptions();
            event.target.value = String(Math.max(1,
                parseInt(event.target.value, 10) || 5000));
            updateOptionsCurrent();
            scheduleMatchupPreview();
        });
    });
    document.getElementById("rangedBuffer")?.addEventListener("change", () => {
        invalidateBattleOptions();
        refreshArenaPreview();
        scheduleMatchupPreview();
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
            for (const id of ["team1Resources", "team2Resources"]) {
                const element = document.getElementById(id);
                if (element) element.value = params.get("resources");
            }
        }
        for (const [param, id] of [
            ["resources1", "team1Resources"],
            ["resources2", "team2Resources"],
        ]) {
            if (params.has(param)) {
                document.getElementById(id).value = String(Math.max(1,
                    parseInt(params.get(param), 10) || 5000));
            }
        }
        for (const [param, id] of [
            ["count1", "team1Count"],
            ["count2", "team2Count"],
        ]) {
            if (params.has(param)) {
                document.getElementById(id).value = String(Math.min(27, Math.max(1,
                    parseInt(params.get(param), 10) || 27)));
            }
        }
        updateOptionsCurrent();
        refreshArenaPreview();
    }
    if (dl && dl.autorun && teamState[1].unitSlug && teamState[2].unitSlug) {
        await startBattle();
    }
});

async function startBattle() {
    const ticket = battleRequest.begin();
    const s1 = teamState[1],
        s2 = teamState[2];
    if (!s1.unitSlug || !s1.civ || !s2.unitSlug || !s2.civ) {
        alert(
            "Please select a civilization and unit for both teams",
        );
        return;
    }

    try {
        cancelMatchupPreview();
        battleLoading = true;
        pageSim.state = "loading";
        syncPlayerControls();
        document.getElementById("simOptions")?.removeAttribute("open");

        const seed = (Math.random() * 2 ** 32) >>> 0;
        const config = await fetchBattleConfig(buildBattlePayload(seed), ticket.signal);
        if (!ticket.isCurrent()) return;

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
        renderMatchupCards(config);

        battleLoading = false;
        setSimPhase(true);
        pageSim.start();

        const arenaEl = document.getElementById("arena");
        if (arenaEl && typeof arenaEl.scrollIntoView === "function") {
            const arenaRect = arenaEl.getBoundingClientRect();
            const arenaFullyVisible = arenaRect.top >= 0
                && arenaRect.bottom <= window.innerHeight;
            const desktopShell = window.matchMedia(
                "(min-width: 1025px) and (min-height: 560px)",
            ).matches;
            if (!desktopShell && !arenaFullyVisible) {
                arenaEl.scrollIntoView({
                    behavior: "smooth",
                    block: "start",
                });
            }
        }
    } catch (error) {
        if (!ticket.isCurrent() || error.name === "AbortError") return;
        console.error(error);
        pageSim.state = "failed";
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

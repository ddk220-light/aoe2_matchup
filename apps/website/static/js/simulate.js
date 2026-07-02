/*
 * Role: engine — Engine 3 of 3: FRONTEND CANVAS battle sim.
 *
 * Runs the interactive Battle Sim page at / entirely client-side (the
 * BattleUnit class + the animation loop). Mirrors the position-based backend
 * engine webapp/simulation_real.py — abilities and tuning constants (miss
 * spread, movement smoothing, stuck threshold) are kept in lockstep by
 * comments in both files; change one, change the other.
 *
 * tests/test_frontend_projectile_miss.js brace-extracts the BattleUnit class
 * from this file at test time by searching for its declaration, so keep the
 * class top-level and brace-balanced, and never write the declaration token
 * ("class" + space + the class name) anywhere above the real one.
 */

// ===== CONSTANTS =====
const CANVAS_WIDTH = 900;
const CANVAS_HEIGHT = 600;
const TILE_SIZE = 30;

// Canvas palette — read from the central design tokens so the battlefield matches
// the active theme (light default / dark toggle). Refreshed on load + theme change.
let CANVAS_PAL = {
    bg: "#26301a", grid: "rgba(128,128,128,0.10)", text: "#ece1cd", gold: "#cdac50",
    hpStrong: "#6fb15e", hpWeak: "#cf9a4a", hpPoor: "#cf6a5e",
    team1: "#4a9fd4", team2: "#cf5a4b",
};
function refreshCanvasPalette() {
    try {
        const cs = getComputedStyle(document.documentElement);
        const g = (n, fb) => cs.getPropertyValue(n).trim() || fb;
        CANVAS_PAL = {
            bg: g("--canvas-bg", CANVAS_PAL.bg),
            grid: "rgba(128,128,128,0.10)",
            text: g("--text", CANVAS_PAL.text),
            gold: g("--gold", CANVAS_PAL.gold),
            hpStrong: g("--strong", CANVAS_PAL.hpStrong),
            hpWeak: g("--weak", CANVAS_PAL.hpWeak),
            hpPoor: g("--poor", CANVAS_PAL.hpPoor),
            team1: g("--team1", CANVAS_PAL.team1),
            team2: g("--team2", CANVAS_PAL.team2),
        };
    } catch (e) { /* keep last palette */ }
}
if (typeof document !== "undefined") {
    refreshCanvasPalette();
    // Re-read when the theme toggles (data-theme attribute on <html>).
    try {
        new MutationObserver(refreshCanvasPalette).observe(document.documentElement, {
            attributes: true, attributeFilter: ["data-theme"],
        });
    } catch (e) {}
}
const MELEE_RANGE_BUFFER = 5;

// ENABLED_CIVS, NAME_TO_ICON, UNIQUE_BUILDING, ICON_BASE,
// CIV_EMBLEM_BASE are loaded from constants.js (via base.html)

function iconUrl(id) {
    return ICON_BASE + id + ".png";
}
function unitIconUrl(name) {
    const id = NAME_TO_ICON[name];
    return id ? iconUrl(id) : "";
}

let armorClassNames = {};

// ===== ADJUSTABLE PRE-BATTLE CONDITIONS =====
// Lithuanian relic bonus: the reference DB bakes in all 4 relics (+1 base
// melee attack each) for these units. The rail picker lets the user dial
// 0-4; setupTeam applies the delta vs the baked-in 4 client-side.
const RELIC_MAX = 4;
const RELIC_BONUS_UNITS = new Set(["paladin", "elite_leitis_lithuanians"]);
// Units that snowball +1 attack per kill up to attack_bonus_per_kill (cap 4):
// Jaguar Warrior (Aztecs), Tiger Cavalry (Wei). "Starting kills" pre-loads
// that counter so the battle can start mid-rampage.
const KILL_BONUS_MAX = 4;
const KILL_BONUS_UNITS = new Set([
    "elite_jaguar_warrior_aztecs",
    "elite_tiger_cavalry_wei",
]);
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

// ===== PROJECTILE & EFFECT CLASSES =====

// Classify a firing unit (by slug) into a projectile KIND, so each unit line
// gets a realistic, recognisable projectile (NOT team-tinted — projectiles are
// coloured by what they are). Order matters: bombard before gunpowder.
function classifyProjectile(slug) {
    const s = slug || "";
    if (s.indexOf("bombard_cannon") !== -1) return "cannonball"; // big black ball
    if (s.indexOf("siege_onager") !== -1) return "stone";        // onager boulder
    if (s.indexOf("hand_cannoneer") !== -1 || s.indexOf("janissary") !== -1
        || s.indexOf("conquistador") !== -1 || s.indexOf("organ_gun") !== -1)
        return "bullet";                                          // gunpowder shot
    if (s.indexOf("scorpion") !== -1 || s.indexOf("ballista_elephant") !== -1)
        return "bolt";                                            // heavy ballista bolt
    if (s.indexOf("skirm") !== -1 || s.indexOf("genitour") !== -1)
        return "javelin";                                         // thrown javelin
    return "arrow";                                               // archers / default
}

class Projectile {
    constructor(
        startX,
        startY,
        targetX,
        targetY,
        speed,
        team,
        kind,
        onHit,
    ) {
        this.x = startX;
        this.y = startY;
        this.targetX = targetX;
        this.targetY = targetY;
        this.speed = speed || 7 * TILE_SIZE; // default fallback
        this.team = team;
        // Projectile kind drives the shape/colour: arrow | javelin | bolt |
        // bullet | cannonball | stone. (Back-compat: a truthy non-string — the
        // old is_siege_projectile flag — maps to a generic siege "stone".)
        this.kind = typeof kind === "string" ? kind : (kind ? "stone" : "arrow");
        this.onHit = onHit; // callback when projectile arrives
        this.done = false;
        this.prevX = startX;
        this.prevY = startY;
        // Constant flight heading (straight line start->target), used to orient
        // the arrow so it always points the way it's travelling.
        this.angle = Math.atan2(targetY - startY, targetX - startX);
    }

    update(dt) {
        if (this.done) return;
        this.prevX = this.x;
        this.prevY = this.y;

        const dx = this.targetX - this.x;
        const dy = this.targetY - this.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const moveAmt = this.speed * dt;

        if (dist <= moveAmt) {
            this.x = this.targetX;
            this.y = this.targetY;
            this.done = true;
            if (this.onHit) this.onHit();
        } else {
            this.x += (dx / dist) * moveAmt;
            this.y += (dy / dist) * moveAmt;
        }
    }

    // Round projectiles (bullet / cannonball / stone): a filled ball with a faint
    // motion trail and a small specular highlight. No team tint — coloured by what
    // the projectile is.
    _renderBall(ctx, r, fill, trail) {
        ctx.globalAlpha = 0.25;
        ctx.beginPath();
        ctx.moveTo(this.prevX, this.prevY);
        ctx.lineTo(this.x, this.y);
        ctx.strokeStyle = trail;
        ctx.lineWidth = r;
        ctx.lineCap = "round";
        ctx.stroke();
        ctx.globalAlpha = 1.0;
        ctx.beginPath();
        ctx.arc(this.x, this.y, r, 0, Math.PI * 2);
        ctx.fillStyle = fill;
        ctx.fill();
        ctx.beginPath();
        ctx.arc(this.x - r * 0.3, this.y - r * 0.3, r * 0.32, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(255,255,255,0.4)";
        ctx.fill();
    }

    render(ctx) {
        if (this.done) return;
        const k = this.kind;

        // --- Round shots ---
        if (k === "bullet") { this._renderBall(ctx, 2.6, "#141414", "#333"); return; }
        if (k === "cannonball") { this._renderBall(ctx, 5.5, "#0d0d0d", "#000"); return; }
        if (k === "stone") { this._renderBall(ctx, 5, "#867c6e", "#6f665a"); return; }

        // --- Elongated shots (arrow / javelin / bolt): oriented along flight ---
        ctx.save();
        ctx.translate(this.x, this.y);
        ctx.rotate(this.angle);
        ctx.lineCap = "round";
        ctx.lineJoin = "round";

        if (k === "javelin") {
            // Longer + thicker than an arrow, brown wooden shaft, sharp metal tip,
            // NO fletching.
            const TIP = 5, TIPW = 2.5, SHAFT = 18;
            ctx.strokeStyle = "#7a5230";
            ctx.lineWidth = 2.6;
            ctx.beginPath();
            ctx.moveTo(-TIP, 0);
            ctx.lineTo(-TIP - SHAFT, 0);
            ctx.stroke();
            ctx.fillStyle = "#cfd4da"; // steel tip
            ctx.beginPath();
            ctx.moveTo(3, 0);
            ctx.lineTo(-TIP + 1, -TIPW);
            ctx.lineTo(-TIP + 1, TIPW);
            ctx.closePath();
            ctx.fill();
        } else if (k === "bolt") {
            // Ballista bolt: much thicker + bigger, heavy dark-wood shaft + broad
            // steel head (reads as a bolt that punches through).
            const HEAD = 6, HEADW = 4, SHAFT = 14;
            ctx.strokeStyle = "#4f3f28";
            ctx.lineWidth = 4;
            ctx.beginPath();
            ctx.moveTo(-HEAD, 0);
            ctx.lineTo(-HEAD - SHAFT, 0);
            ctx.stroke();
            ctx.fillStyle = "#aeb4bd";
            ctx.beginPath();
            ctx.moveTo(4, 0);
            ctx.lineTo(-HEAD + 1, -HEADW);
            ctx.lineTo(-HEAD + 1, HEADW);
            ctx.closePath();
            ctx.fill();
        } else {
            // Arrow: brown shaft, black head, white feathers. ~18px long.
            const HEAD = 5, HEADW = 3, SHAFT = 10, FLETCH = 3.5;
            ctx.strokeStyle = "#6b4a2b"; // wooden shaft
            ctx.lineWidth = 1.7;
            ctx.beginPath();
            ctx.moveTo(-HEAD + 1, 0);
            ctx.lineTo(-HEAD - SHAFT, 0);
            ctx.stroke();
            ctx.strokeStyle = "#f0f0f0"; // white feathers
            ctx.lineWidth = 1.3;
            ctx.beginPath();
            ctx.moveTo(-HEAD - SHAFT, 0);
            ctx.lineTo(-HEAD - SHAFT - FLETCH, -2.6);
            ctx.moveTo(-HEAD - SHAFT, 0);
            ctx.lineTo(-HEAD - SHAFT - FLETCH, 2.6);
            ctx.stroke();
            ctx.fillStyle = "#15110d"; // black arrowhead
            ctx.beginPath();
            ctx.moveTo(2, 0);
            ctx.lineTo(-HEAD + 2, -HEADW);
            ctx.lineTo(-HEAD + 2, HEADW);
            ctx.closePath();
            ctx.fill();
        }
        ctx.restore();
    }
}

class MeleeEffect {
    constructor(x, y, team, splashRadius) {
        this.x = x;
        this.y = y;
        this.team = team;
        this.splashRadius = splashRadius || 0;
        this.lifetime = this.splashRadius > 0 ? 0.4 : 0.2;
        this.age = 0;
        this.done = false;
    }

    update(dt) {
        this.age += dt;
        if (this.age >= this.lifetime) this.done = true;
    }

    render(ctx) {
        if (this.done) return;
        const progress = this.age / this.lifetime;
        const alpha = 1.0 - progress;

        if (this.splashRadius > 0) {
            // Siege splash: expanding filled circle
            const radius =
                this.splashRadius * (0.3 + 0.7 * progress);
            ctx.globalAlpha = alpha * 0.35;
            ctx.beginPath();
            ctx.arc(this.x, this.y, radius, 0, Math.PI * 2);
            ctx.fillStyle = "#ff6600";
            ctx.fill();
            ctx.globalAlpha = alpha * 0.6;
            ctx.strokeStyle = "#ff9900";
            ctx.lineWidth = 2;
            ctx.stroke();
        } else {
            // Melee / ranged hit: a bright gold impact burst — a soft filled
            // core under a fast-expanding ring — so a landed attack pops out
            // clearly, regardless of which team landed it.
            const r = 6 + progress * 18;
            ctx.globalAlpha = alpha * 0.5;
            ctx.beginPath();
            ctx.arc(this.x, this.y, r * 0.55, 0, Math.PI * 2);
            ctx.fillStyle = "#ffe8a3";
            ctx.fill();
            ctx.globalAlpha = alpha;
            ctx.beginPath();
            ctx.arc(this.x, this.y, r, 0, Math.PI * 2);
            ctx.strokeStyle = "#ffd14a";
            ctx.lineWidth = 2.5;
            ctx.stroke();
        }
        ctx.globalAlpha = 1.0;
    }
}

// ===== BATTLE UNIT CLASS =====
class BattleUnit {
    constructor(id, team, stats, slug = "", civName = "") {
        this.id = id;
        this.team = team;
        this.stats = stats;
        this.slug = slug;
        // Realistic per-line projectile shape (arrow/javelin/bolt/bullet/cannonball/stone).
        this.projectileKind = classifyProjectile(slug);
        this.civName = civName;

        this.maxHp = stats.hp;
        this.currentHp = stats.hp;
        this.attack = stats.attack;
        this.rawAttackRange = stats.attack_range || 0;
        this.attackRange =
            this.rawAttackRange * TILE_SIZE + MELEE_RANGE_BUFFER;
        this.attackSpeed = stats.attack_speed || 0.5;
        this.reloadTime = 1.0 / this.attackSpeed;
        this.attackDelay = stats.attack_delay || 0;
        this.moveSpeed = (stats.movement_speed || 1) * TILE_SIZE;
        this.meleeArmor = stats.melee_armor || 0;
        this.pierceArmor = stats.pierce_armor || 0;
        this.attacks = stats.attacks_json
            ? JSON.parse(stats.attacks_json)
            : {};
        this.armors = stats.armors_json
            ? JSON.parse(stats.armors_json)
            : {};

        // Combat properties
        this.minAttackRange =
            (stats.min_attack_range || 0) * TILE_SIZE;
        this.isSiegeProjectile = stats.is_siege_projectile || 0;
        this.splashRadius = (stats.splash_radius || 0) * TILE_SIZE;
        this.projectileSpeed =
            (stats.projectile_speed || 0) * TILE_SIZE;
        this.ignoresPierceArmor = stats.ignores_pierce_armor || 0;
        this.ignoresMeleeArmor = stats.ignores_melee_armor || 0;
        this.tramplePercent = stats.trample_percent || 0;
        this.trampleRadius =
            (stats.trample_radius || 0) * TILE_SIZE;
        this.trampleFlatDamage = stats.trample_flat_damage || 0;
        this.bonusDamageReduction =
            stats.bonus_damage_reduction || 0;
        // Projectile accuracy (0-1 fraction). A missed shot still flies but
        // deals no direct damage; it may graze a different nearby unit (default
        // 0.5x, Arambai missDamagePercent=1.0 -> full). Mirrors simulation_real.py.
        // Primary arrow uses `accuracy`; extra/secondary arrows use baseAccuracy
        // (Thumb Ring only boosts the primary), matching the backend.
        this.accuracy = (stats.accuracy || 100) / 100;
        this.baseAccuracy = (stats.base_accuracy || 100) / 100;

        // Unique mechanics
        this.extraProjectiles = stats.extra_projectiles || 0;
        this.splashOnHitRadius =
            (stats.splash_on_hit_radius || 0) * TILE_SIZE;
        this.dodgeShieldMax = stats.dodge_shield_max || 0;
        this.dodgeShieldRecharge = stats.dodge_shield_recharge || 0;
        this.bleedDps = stats.bleed_dps || 0;
        this.bleedDuration = stats.bleed_duration || 0;
        this.blockFirstMelee = stats.block_first_melee || 0;
        this.attackBonusPerKill = stats.attack_bonus_per_kill || 0;
        this.firstAttackExtraProjectiles =
            stats.first_attack_extra_projectiles || 0;
        this.hpTransformThreshold =
            stats.hp_transform_threshold || 0;
        this.hpRegen = stats.hp_regen || 0;
        this.passThroughPercent = stats.pass_through_percent || 0;

        // Charge projectiles (Fire Lancer)
        this.chargeProjectileCount =
            stats.charge_projectile_count || 0;
        this.chargeProjectileSpeed =
            (stats.charge_projectile_speed || 0) * TILE_SIZE;
        this.chargeAttackRange =
            (stats.charge_attack_range || 0) * TILE_SIZE;
        this.chargeIgnoresArmor = stats.charge_ignores_armor || 0;
        this.chargeProjectileAttacks =
            stats.charge_projectile_attacks_json
                ? JSON.parse(stats.charge_projectile_attacks_json)
                : null;

        // State
        this.shieldCharges = this.dodgeShieldMax;
        this.shieldRechargeTimer = 0;
        this.hasBlockedFirstMelee = false;
        this.killBonusAttack = 0;
        this.hasUsedFirstAttack = false;
        this.isTransformed = false;
        this.bleedEffect = null;
        this.hasUsedCharge = false;

        // --- ported abilities (parity with simulation_real.py) ---
        this.chargeAttackMelee = stats.charge_attack_melee || 0;
        this.chargeRechargeTime = stats.charge_recharge_time || 0;
        this.chargeTimer = 0;
        this.chargeSlowPercent = stats.charge_slow_percent || 0;
        this.chargeSlowDuration = stats.charge_slow_duration || 0;
        this.executeDamagePerStep = stats.execute_damage_per_step || 0;
        this.executeHpStep = stats.execute_hp_step || 0;
        this.attackSpeedRamp = stats.attack_speed_ramp || 0;
        this.attackSpeedMin = stats.attack_speed_min || 0;
        this.rampReduction = 0;
        this.hpPerKill = stats.hp_per_kill || 0;
        this.hpPerKillMax = stats.hp_per_kill_max || 0;
        this.hpGainedFromKills = 0;
        this.missDamagePercent = stats.miss_damage_percent || 0;
        this.armorStripPerHit = stats.armor_strip_per_hit || 0;
        this.attackBonusNearby = stats.attack_bonus_nearby || 0;
        this.nearbyBonusCount = stats.nearby_bonus_count || 0;
        this.auraAttackBonus = 0;
        this.hpNearbyPercentPerUnit = stats.hp_nearby_percent_per_unit || 0;
        this.hpNearbyMaxUnits = stats.hp_nearby_max_units || 0;
        this.auraHpBonus = 0;
        this.damageReflectPercent = stats.damage_reflect_percent || 0;
        this.allyDeathHeal = stats.ally_death_heal || 0;
        this.allyDeathHealDuration = stats.ally_death_heal_duration || 0;
        this.allyHealRemaining = 0;
        this.allyHealRate = 0;
        this.extraProjScatter = stats.extra_proj_scatter || 0;
        this.slowTimer = 0;
        this.baseMoveSpeed = this.moveSpeed;
        // Transform target stats (Jian Swordsman)
        this.transformMaxHp = stats.transform_hp || 0;
        this.transformAttack = stats.transform_attack || 0;
        this.transformMeleeArmor = stats.transform_melee_armor || 0;
        this.transformPierceArmor = stats.transform_pierce_armor || 0;
        this.transformAttackSpeed = stats.transform_attack_speed || 0;
        this.transformMoveSpeed = stats.transform_movement_speed || 0;
        this.transformAttacks = stats.transform_attacks_json
            ? JSON.parse(stats.transform_attacks_json)
            : null;
        this.transformArmors = stats.transform_armors_json
            ? JSON.parse(stats.transform_armors_json)
            : null;
        // Dismount-on-death stat block (Konnik); inert unless dismountHp > 0.
        // Mirrors the simulation_real.py port (2026-06-10).
        this.dismountHp = stats.dismount_hp || 0;
        this.dismountAttack = stats.dismount_attack || 0;
        this.dismountMeleeArmor = stats.dismount_melee_armor || 0;
        this.dismountPierceArmor = stats.dismount_pierce_armor || 0;
        this.dismountAttackSpeed = stats.dismount_attack_speed || 0;
        this.dismountAttackDelay = stats.dismount_attack_delay || 0;
        this.dismountMovementSpeed = stats.dismount_movement_speed || 0;
        this.dismountAttacks = stats.dismount_attacks_json
            ? JSON.parse(stats.dismount_attacks_json)
            : null;
        this.dismountArmors = stats.dismount_armors_json
            ? JSON.parse(stats.dismount_armors_json)
            : null;
        this.isDismounted = false;

        this.x = 0;
        this.y = 0;
        // Scale radius based on unit outline_size
        // infantry(0.2)->14, cavalry(0.4)->18, paladin(0.5)->20, mangonel(0.5)->20, ram(0.8)->26, treb(1.0)->30
        const outlineSize = stats.outline_size || 0.2;
        this.radius = Math.round(
            10 + Math.min(outlineSize, 1.0) * 20,
        );
        this.target = null;
        this.state = "idle";
        this.attackCooldown = 0;
        this.wasMoving = true;
        this.committedAttack = null;
        this.attackAnimTimer = 0;
        // Seconds the attack sprite-sheet keeps playing after a swing/shot fires,
        // independent of state — so the animation completes even once the unit
        // starts moving/kiting away (set to one full sheet cycle on each attack).
        this.animHold = 0;
        this.damageNumbers = [];

        // Movement smoothing -- prevents vibration
        this.vx = 0;
        this.vy = 0;
        // Horizontal facing: sprites are authored facing LEFT, so faceRight=true
        // means mirror. At spawn, team 1 (left) faces its enemies on the right and
        // team 2 (right) faces left; during battle it tracks the target/movement
        // direction (see render) so a unit always faces what it's attacking.
        this.faceRight = this.team === 1;
        // Stuck detection -- switch targets when blocked
        this.stuckTimer = 0;
        this.lastDistToTarget = Infinity;
        this.blockedTargets = new Set();

        // Sprite image ref (set externally)
        this.spriteImg = null;
        this.attackSheet = null;
    }

    isRanged() {
        return this.rawAttackRange >= 1.0;
    }

    // Latch the attack sprite-sheet to keep playing for one full cycle from now,
    // so a swing/shot finishes on-screen even if the unit immediately moves or
    // kites away. Frames are sampled off the global clock, so this just extends
    // how long playback stays on past the brief "attacking" state.
    triggerAttackAnim() {
        const sh = this.attackSheet;
        this.animHold =
            sh && sh.meta ? (sh.meta.frames * sh.meta.dur) / 1000 : 0.4;
    }

    getDamageAgainst(target, detailed = false) {
        const isRanged = this.isRanged();
        const baseAttackClass = isRanged ? "3" : "4";
        const baseAttack =
            (this.attacks[baseAttackClass] ||
                this.attacks["4"] ||
                this.attack) + this.auraAttackBonus;
        let targetBaseArmor;
        if (isRanged && this.ignoresPierceArmor) {
            targetBaseArmor = 0;
        } else if (!isRanged && this.ignoresMeleeArmor) {
            targetBaseArmor = 0;
        } else {
            targetBaseArmor = isRanged
                ? target.armors["3"] || target.pierceArmor || 0
                : target.armors["4"] || target.meleeArmor || 0;
        }

        let bonusDamage = 0;
        const breakdown = [];

        const baseDmg = Math.max(0, baseAttack - targetBaseArmor);
        breakdown.push({
            classId: baseAttackClass,
            className: isRanged ? "Base Pierce" : "Base Melee",
            attack: baseAttack,
            armor: targetBaseArmor,
            damage: baseDmg,
            applies: true,
        });

        for (const [armorClass, attackValue] of Object.entries(
            this.attacks,
        )) {
            if (armorClass === "3" || armorClass === "4") continue;
            if (attackValue <= 0) continue;
            const targetHasClass =
                target.armors.hasOwnProperty(armorClass);
            const targetArmor = targetHasClass
                ? target.armors[armorClass]
                : 0;

            if (targetHasClass) {
                const effectiveBonus = Math.max(
                    0,
                    attackValue - targetArmor,
                );
                bonusDamage += effectiveBonus;
                breakdown.push({
                    classId: armorClass,
                    className:
                        armorClassNames[armorClass] ||
                        `Class ${armorClass}`,
                    attack: attackValue,
                    armor: targetArmor,
                    damage: effectiveBonus,
                    applies: true,
                });
            } else if (detailed) {
                breakdown.push({
                    classId: armorClass,
                    className:
                        armorClassNames[armorClass] ||
                        `Class ${armorClass}`,
                    attack: attackValue,
                    armor: "-",
                    damage: 0,
                    applies: false,
                });
            }
        }

        if (target.bonusDamageReduction > 0) {
            bonusDamage = Math.floor(
                bonusDamage * (1 - target.bonusDamageReduction),
            );
        }

        // Execute scaling (Kona): +N damage per missing-HP step on the target.
        let executeBonus = 0;
        if (
            this.executeDamagePerStep > 0 &&
            this.executeHpStep > 0 &&
            target.maxHp > 0
        ) {
            const missing = 1 - target.currentHp / target.maxHp;
            executeBonus =
                this.executeDamagePerStep *
                Math.floor(missing / this.executeHpStep);
        }
        const totalDamage = Math.max(
            1,
            baseDmg + bonusDamage + executeBonus,
        );
        if (detailed) return { total: totalDamage, breakdown };
        return totalDamage;
    }

    findTarget(enemies) {
        let closest = null;
        let closestDist = Infinity;
        let fallback = null;
        let fallbackDist = Infinity;
        for (const enemy of enemies) {
            if (enemy.state === "dead") continue;
            const dist = this.distanceTo(enemy);
            // Prefer targets not in blockedTargets
            if (!this.blockedTargets.has(enemy)) {
                if (dist < closestDist) {
                    closestDist = dist;
                    closest = enemy;
                }
            }
            // Track overall closest as fallback
            if (dist < fallbackDist) {
                fallbackDist = dist;
                fallback = enemy;
            }
        }
        // Use unblocked target if available, else fall back to closest
        this.target = closest || fallback;
        // Reset stuck tracking for new target
        this.stuckTimer = 0;
        this.lastDistToTarget = this.target
            ? this.distanceTo(this.target)
            : Infinity;
        return this.target;
    }

    distanceTo(other) {
        const dx = other.x - this.x;
        const dy = other.y - this.y;
        return Math.sqrt(dx * dx + dy * dy);
    }

    inRange() {
        if (!this.target) return false;
        const dist = this.distanceTo(this.target);
        const effectiveRange =
            this.attackRange + this.radius + this.target.radius;
        if (dist > effectiveRange) return false;
        if (this.minAttackRange > 0 && dist < this.minAttackRange)
            return false;
        return true;
    }

    tooClose() {
        if (!this.target || this.minAttackRange <= 0) return false;
        return this.distanceTo(this.target) < this.minAttackRange;
    }

    update(dt, allUnits, enemies) {
        if (this.state === "dead") return;

        this.attackCooldown = Math.max(0, this.attackCooldown - dt);
        this.attackAnimTimer = Math.max(
            0,
            this.attackAnimTimer - dt,
        );
        this.animHold = Math.max(0, this.animHold - dt);

        this.damageNumbers = this.damageNumbers.filter((dn) => {
            dn.y -= 40 * dt;
            dn.alpha -= dt * 1.5;
            return dn.alpha > 0;
        });

        // HP regen
        if (
            this.hpRegen > 0 &&
            this.currentHp > 0 &&
            this.currentHp < this.maxHp
        ) {
            this.currentHp = Math.min(
                this.maxHp,
                this.currentHp + (this.hpRegen / 60) * dt,
            );
        }

        // Bleed damage tick
        if (this.bleedEffect) {
            this.currentHp -= this.bleedEffect.dps * dt;
            this.bleedEffect.timeRemaining -= dt;
            if (this.bleedEffect.timeRemaining <= 0)
                this.bleedEffect = null;
            if (this.currentHp <= 0) {
                this.currentHp = 0;
                this.state = "dead";
                this.target = null;
                return;
            }
        }

        // Shield recharge
        if (this.shieldRechargeTimer > 0) {
            this.shieldRechargeTimer -= dt;
            if (this.shieldRechargeTimer <= 0) {
                this.shieldCharges = Math.min(
                    this.shieldCharges + 1,
                    this.dodgeShieldMax,
                );
                if (this.shieldCharges < this.dodgeShieldMax) {
                    this.shieldRechargeTimer =
                        this.dodgeShieldRecharge;
                } else {
                    this.shieldRechargeTimer = 0;
                }
            }
        }

        // Charge recharge timer (melee charge + charge projectiles)
        if (this.chargeTimer > 0)
            this.chargeTimer = Math.max(0, this.chargeTimer - dt);

        // Charge-slow expiry: restore movement speed
        if (this.slowTimer > 0) {
            this.slowTimer = Math.max(0, this.slowTimer - dt);
            if (this.slowTimer <= 0) this.moveSpeed = this.baseMoveSpeed;
        }

        // Ally-death heal-over-time (Guecha Warrior)
        if (
            this.allyHealRemaining > 0 &&
            this.currentHp > 0 &&
            this.currentHp < this.maxHp
        ) {
            const heal = Math.min(
                this.allyHealRate * dt,
                this.allyHealRemaining,
            );
            this.currentHp = Math.min(this.maxHp, this.currentHp + heal);
            this.allyHealRemaining -= heal;
        }

        // Nearby-ally auras (Monaspa attack, Shu %HP)
        if (this.attackBonusNearby > 0 || this.hpNearbyPercentPerUnit > 0) {
            const auraRadius = 5 * TILE_SIZE;
            const allies =
                this.team === 1 ? simulation.team1 : simulation.team2;
            let n = 0;
            for (const ally of allies) {
                if (ally === this || ally.state === "dead") continue;
                if (this.distanceTo(ally) <= auraRadius) n++;
            }
            if (this.attackBonusNearby > 0) {
                const cap = this.nearbyBonusCount || n;
                this.auraAttackBonus =
                    this.attackBonusNearby * Math.min(n, cap);
            }
            if (this.hpNearbyPercentPerUnit > 0) {
                const cap = this.hpNearbyMaxUnits || n;
                const base = this.maxHp - this.auraHpBonus;
                const targetBonus =
                    base *
                    (this.hpNearbyPercentPerUnit / 100) *
                    Math.min(n, cap);
                const delta = targetBonus - this.auraHpBonus;
                this.maxHp += delta;
                if (delta > 0) this.currentHp += delta;
                else if (this.currentHp > this.maxHp)
                    this.currentHp = this.maxHp;
                this.auraHpBonus = targetBonus;
            }
        }

        // HP transform (Jian Swordsman): swap to transformed stats once
        if (this.hpTransformThreshold > 0 && !this.isTransformed) {
            if (
                this.currentHp <=
                    this.maxHp * this.hpTransformThreshold &&
                this.currentHp > 0
            ) {
                this.isTransformed = true;
                if (this.transformMaxHp > 0) {
                    this.maxHp = this.transformMaxHp;
                    if (this.currentHp > this.maxHp)
                        this.currentHp = this.maxHp;
                    if (this.transformAttack > 0)
                        this.attack = this.transformAttack;
                    this.meleeArmor = this.transformMeleeArmor;
                    this.pierceArmor = this.transformPierceArmor;
                    if (this.transformAttacks)
                        this.attacks = this.transformAttacks;
                    if (this.transformArmors)
                        this.armors = this.transformArmors;
                    if (this.transformAttackSpeed > 0) {
                        this.attackSpeed = this.transformAttackSpeed;
                        this.reloadTime = 1.0 / this.transformAttackSpeed;
                    }
                    if (this.transformMoveSpeed > 0) {
                        this.moveSpeed = this.transformMoveSpeed * TILE_SIZE;
                        this.baseMoveSpeed = this.moveSpeed;
                    }
                } else {
                    this.killBonusAttack += 3;
                }
            }
        }

        // Clean up blockedTargets: remove dead enemies
        for (const bt of this.blockedTargets) {
            if (bt.state === "dead") this.blockedTargets.delete(bt);
        }
        // If all alive enemies are blocked, clear and retry
        if (
            this.blockedTargets.size > 0 &&
            this.blockedTargets.size >=
                enemies.filter((e) => e.state !== "dead").length
        ) {
            this.blockedTargets.clear();
        }

        if (!this.target || this.target.state === "dead") {
            this.findTarget(enemies);
        }
        if (!this.target) {
            this.state = "idle";
            return;
        }

        if (this.isRanged()) {
            const shouldKite = !this.target.isRanged();
            if (this.tooClose()) {
                this.state = "kiting";
                this.moveAwayFromTarget(dt, allUnits);
                this.wasMoving = true;
            } else if (
                !this.wasMoving &&
                this.attackCooldown <= 0
            ) {
                this.state = "attacking";
                this.performAttack();
                this.wasMoving = true;
            } else if (!this.wasMoving) {
                this.state = "attacking";
            } else if (this.attackCooldown > 0 && shouldKite) {
                this.state = "kiting";
                this.moveAwayFromTarget(dt, allUnits);
            } else if (this.attackCooldown > 0) {
                this.state = "attacking";
            } else if (this.inRange()) {
                this.attackCooldown = this.attackDelay;
                this.wasMoving = false;
                this.state = "attacking";
            } else {
                this.state = "moving";
                this.moveTowardTarget(dt, allUnits);
            }
        } else {
            // Charge projectile attack (Fire Lancer): fire at range before melee
            if (
                this.chargeProjectileCount > 0 &&
                !this.hasUsedCharge &&
                this.target
            ) {
                const distToTarget = this.distanceTo(this.target);
                const chargeRange =
                    this.chargeAttackRange +
                    this.radius +
                    this.target.radius;
                if (distToTarget <= chargeRange) {
                    // In charge range -- fire charge projectiles
                    this.hasUsedCharge = true;
                    this.state = "attacking";
                    this.attackAnimTimer = 0.3;
                    this.triggerAttackAnim();
                    for (
                        let cp = 0;
                        cp < this.chargeProjectileCount;
                        cp++
                    ) {
                        this.fireChargeProjectile(this.target);
                    }
                    this.attackCooldown = this.reloadTime;
                } else {
                    // Move toward target to get in charge range
                    this.state = "moving";
                    this.moveTowardTarget(dt, allUnits);
                    this.wasMoving = true;
                }
            } else if (this.committedAttack) {
                this.committedAttack.timeLeft -= dt;
                this.state = "committed";
                if (this.committedAttack.timeLeft <= 0) {
                    const target = this.committedAttack.target;
                    if (target.state !== "dead") {
                        this.performAttackOn(target);
                    }
                    this.committedAttack = null;
                    this.attackCooldown = this.reloadTime;
                    this.wasMoving = false;
                }
            } else if (this.inRange()) {
                if (this.attackCooldown <= 0) {
                    if (this.attackDelay > 0) {
                        this.committedAttack = {
                            target: this.target,
                            timeLeft: this.attackDelay,
                        };
                        this.state = "committed";
                        this.wasMoving = false;
                    } else {
                        this.state = "attacking";
                        this.performAttack();
                    }
                } else {
                    this.state = "attacking";
                }
            } else {
                this.state = "moving";
                this.moveTowardTarget(dt, allUnits);
                this.wasMoving = true;
            }
        }
    }

    performAttack() {
        if (!this.target || this.target.state === "dead") return;
        // Ranged charge volley (Fire Archer/Xianbei/Bolas). recharge<=0 fires
        // every attack and replaces the normal shot; recharge>0 adds then recharges.
        if (
            this.isRanged() &&
            this.chargeProjectileCount > 0 &&
            this.chargeTimer <= 0
        ) {
            for (let c = 0; c < this.chargeProjectileCount; c++)
                this.fireChargeProjectile(this.target);
            if (this.chargeRechargeTime > 0) {
                this.chargeTimer = this.chargeRechargeTime;
            } else {
                this.attackCooldown = this.reloadTime;
                return;
            }
        }
        let numProjectiles = 1 + this.extraProjectiles;
        if (
            this.firstAttackExtraProjectiles > 0 &&
            !this.hasUsedFirstAttack
        ) {
            numProjectiles += this.firstAttackExtraProjectiles;
            this.hasUsedFirstAttack = true;
        }
        // Organ Gun: extra projectiles scatter to different enemies.
        let scatter = null;
        if (this.extraProjScatter && this.isRanged()) {
            const foes =
                this.team === 1 ? simulation.team2 : simulation.team1;
            scatter = foes.filter(
                (e) => e.state !== "dead" && e !== this.target,
            );
        }
        let scatI = 0;
        for (let p = 0; p < numProjectiles; p++) {
            if (this.target && this.target.state !== "dead") {
                if (this.isRanged()) {
                    let tgt = this.target;
                    if (p > 0 && scatter && scatter.length > 0) {
                        tgt = scatter[scatI % scatter.length];
                        scatI++;
                    }
                    this.fireProjectile(tgt, p > 0);
                } else {
                    this.performAttackOn(this.target);
                }
            }
        }
        this.attackCooldown = this.reloadTime;
    }

    fireProjectile(target, isExtra = false) {
        const damage =
            this.getDamageAgainst(target) +
            Math.floor(this.killBonusAttack);
        // Accuracy roll (mirrors simulation_real.py fire_projectile). A miss
        // still spawns a projectile but applies 0 direct damage; on impact it
        // grazes a random nearby unit instead. Primary arrow uses unit accuracy;
        // extra arrows use baseAccuracy.
        const accuracy = isExtra ? this.baseAccuracy : this.accuracy;
        const willHit = accuracy >= 1.0 ? true : Math.random() < accuracy;
        const MISS_SPREAD = 2.0 * TILE_SIZE; // tiles, matches MISS_SPREAD_RADIUS
        const speed =
            this.projectileSpeed > 0
                ? this.projectileSpeed
                : 7 * TILE_SIZE;
        const attacker = this;
        // Siege splash: scale up radius so mangonel/onager can hit clusters
        const splashR =
            attacker.splashRadius > 0
                ? Math.max(attacker.splashRadius, 2.5 * TILE_SIZE)
                : 0;
        const impactX = target.x;
        const impactY = target.y;
        const proj = new Projectile(
            this.x,
            this.y,
            target.x,
            target.y,
            speed,
            this.team,
            this.projectileKind,
            () => {
                const targetWasAlive = target.state !== "dead";
                if (target.state !== "dead" && willHit) {
                    target.takeDamage(damage, attacker);
                } else if (target.state !== "dead" && !willHit) {
                    // Missed: the arrow lands at a random point within
                    // MISS_SPREAD of the intended impact. If a (different) unit
                    // happens to occupy that spot it is grazed; otherwise the
                    // shot is wasted. Graze is 0.5x by default; Arambai
                    // (missDamagePercent=1.0) deals full damage on a graze.
                    const missAngle = Math.random() * 2 * Math.PI;
                    const missDist = Math.random() * MISS_SPREAD;
                    const landX = impactX + missDist * Math.cos(missAngle);
                    const landY = impactY + missDist * Math.sin(missAngle);
                    const foes =
                        attacker.team === 1
                            ? simulation.team2
                            : simulation.team1;
                    for (const enemy of foes) {
                        if (enemy === target || enemy.state === "dead")
                            continue;
                        const ex = enemy.x - landX;
                        const ey = enemy.y - landY;
                        if (
                            ex * ex + ey * ey <=
                            enemy.radius * enemy.radius
                        ) {
                            const frac =
                                attacker.missDamagePercent > 0
                                    ? attacker.missDamagePercent
                                    : 0.5;
                            enemy.takeDamage(
                                Math.max(1, Math.floor(damage * frac)),
                                attacker,
                            );
                            break;
                        }
                    }
                }

                if (
                    attacker.attackBonusPerKill > 0 &&
                    targetWasAlive &&
                    target.state === "dead"
                ) {
                    // attackBonusPerKill is the MAX CAP: +1 per kill up to it
                    // (Tiger Cav/Jaguar: +1/kill, max +4), not +cap/kill.
                    attacker.killBonusAttack = Math.min(
                        attacker.attackBonusPerKill,
                        attacker.killBonusAttack + 1,
                    );
                }

                // Siege area splash damage with distance falloff
                if (splashR > 0 && willHit) {
                    const enemies =
                        attacker.team === 1
                            ? simulation.team2
                            : simulation.team1;
                    for (const enemy of enemies) {
                        if (
                            enemy === target ||
                            enemy.state === "dead"
                        )
                            continue;
                        const dx = enemy.x - impactX;
                        const dy = enemy.y - impactY;
                        const dist = Math.sqrt(dx * dx + dy * dy);
                        if (dist <= splashR + enemy.radius) {
                            // Damage falls off linearly from 100% at center to 25% at edge
                            const distRatio = Math.min(
                                1,
                                dist / splashR,
                            );
                            const falloff = 1.0 - 0.75 * distRatio;
                            const splashDmg = Math.max(
                                1,
                                Math.round(damage * falloff),
                            );
                            enemy.takeDamage(splashDmg, attacker);
                        }
                    }
                    // Visual: add a splash effect
                    simulation.effects.push(
                        new MeleeEffect(
                            impactX,
                            impactY,
                            attacker.team,
                            splashR,
                        ),
                    );
                }

                // Splash on hit (non-siege, e.g. scorpion pass-through)
                if (
                    attacker.splashOnHitRadius > 0 &&
                    splashR === 0 &&
                    willHit
                ) {
                    const enemies =
                        attacker.team === 1
                            ? simulation.team2
                            : simulation.team1;
                    for (const enemy of enemies) {
                        if (
                            enemy !== target &&
                            enemy.state !== "dead"
                        ) {
                            const dx = enemy.x - impactX;
                            const dy = enemy.y - impactY;
                            const dist = Math.sqrt(
                                dx * dx + dy * dy,
                            );
                            if (
                                dist <=
                                attacker.splashOnHitRadius +
                                    enemy.radius
                            ) {
                                enemy.takeDamage(damage, attacker);
                            }
                        }
                    }
                }

                // Pass-through: 1 unit behind target takes fraction of damage
                if (attacker.passThroughPercent > 0 && willHit) {
                    const ptDmg = Math.max(
                        1,
                        Math.floor(
                            damage * attacker.passThroughPercent,
                        ),
                    );
                    const enemies =
                        attacker.team === 1
                            ? simulation.team2
                            : simulation.team1;
                    // Find closest alive enemy behind target (not the target itself)
                    let best = null;
                    let bestDist = Infinity;
                    for (const enemy of enemies) {
                        if (
                            enemy !== target &&
                            enemy.state !== "dead"
                        ) {
                            const dx = enemy.x - target.x;
                            const dy = enemy.y - target.y;
                            const d = Math.sqrt(dx * dx + dy * dy);
                            if (d < bestDist) {
                                bestDist = d;
                                best = enemy;
                            }
                        }
                    }
                    if (best) {
                        best.takeDamage(ptDmg, attacker);
                    }
                }

                // Bleed
                if (attacker.bleedDps > 0 && targetWasAlive && willHit) {
                    target.bleedEffect = {
                        dps: attacker.bleedDps,
                        timeRemaining: attacker.bleedDuration,
                    };
                }
            },
        );
        simulation.projectiles.push(proj);
        this.attackAnimTimer = 0.15;
        this.triggerAttackAnim();
    }

    fireChargeProjectile(target) {
        if (!target || target.state === "dead") return;
        // Calculate charge projectile damage using charge attacks
        let chargeDmg = 0;
        if (this.chargeProjectileAttacks) {
            for (const [cls, atkVal] of Object.entries(
                this.chargeProjectileAttacks,
            )) {
                if (atkVal <= 0) continue;
                if (this.chargeIgnoresArmor) {
                    chargeDmg += atkVal;
                } else {
                    const armor = target.armors[cls] || 0;
                    chargeDmg += Math.max(0, atkVal - armor);
                }
            }
        }
        chargeDmg = Math.max(1, chargeDmg);
        const speed =
            this.chargeProjectileSpeed > 0
                ? this.chargeProjectileSpeed
                : 7 * TILE_SIZE;
        const proj = new Projectile(
            this.x,
            this.y,
            target.x,
            target.y,
            speed,
            this.team,
            this.projectileKind,
            () => {
                if (target.state === "dead") return;
                target.takeDamage(chargeDmg, this);
                // Charge slow (Bolas Rider): slow the struck target.
                if (this.chargeSlowPercent > 0 && target.slowTimer <= 0) {
                    target.moveSpeed =
                        target.baseMoveSpeed * (1 - this.chargeSlowPercent);
                    target.slowTimer = this.chargeSlowDuration;
                }
            },
        );
        simulation.projectiles.push(proj);
        this.attackAnimTimer = 0.3;
        this.triggerAttackAnim();
    }

    performAttackOn(target) {
        if (!target || target.state === "dead") return;
        let damage =
            this.getDamageAgainst(target) +
            Math.floor(this.killBonusAttack);

        // Melee charge bonus (Coustillier/Centurion/Urumi): extra damage on the
        // charged strike (reduced by target melee armor), then it recharges.
        let charged = false;
        if (this.chargeAttackMelee > 0 && this.chargeTimer <= 0) {
            damage += Math.max(0, this.chargeAttackMelee - target.meleeArmor);
            this.chargeTimer = this.chargeRechargeTime;
            charged = true;
        }

        const targetWasAlive = target.state !== "dead";
        target.takeDamage(damage, this);

        // Armor strip (Obuch): permanently lower the target's armor each hit.
        if (this.armorStripPerHit > 0 && target.state !== "dead") {
            target.meleeArmor = Math.max(
                0,
                target.meleeArmor - this.armorStripPerHit,
            );
            target.pierceArmor = Math.max(
                0,
                target.pierceArmor - this.armorStripPerHit,
            );
            if ("4" in target.armors)
                target.armors["4"] = Math.max(
                    0,
                    target.armors["4"] - this.armorStripPerHit,
                );
            if ("3" in target.armors)
                target.armors["3"] = Math.max(
                    0,
                    target.armors["3"] - this.armorStripPerHit,
                );
        }

        if (
            this.attackBonusPerKill > 0 &&
            targetWasAlive &&
            target.state === "dead"
        ) {
            // attackBonusPerKill is the MAX CAP: +1 per kill, up to it.
            this.killBonusAttack = Math.min(
                this.attackBonusPerKill,
                this.killBonusAttack + 1,
            );
        }

        // HP per kill (Tiger Cavalry): heal on kill, up to the cap.
        if (
            this.hpPerKill > 0 &&
            targetWasAlive &&
            target.state === "dead" &&
            this.hpGainedFromKills < this.hpPerKillMax
        ) {
            const heal = Math.min(
                this.hpPerKill,
                this.hpPerKillMax - this.hpGainedFromKills,
            );
            this.currentHp = Math.min(this.maxHp, this.currentHp + heal);
            this.hpGainedFromKills += heal;
        }

        // Attack-speed ramp (Temple Guard): shorten reload toward the floor.
        if (this.attackSpeedRamp > 0) {
            const baseReload =
                this.attackSpeed > 0 ? 1.0 / this.attackSpeed : 2.0;
            this.rampReduction = Math.min(
                this.rampReduction + this.attackSpeedRamp,
                Math.max(0, baseReload - this.attackSpeedMin),
            );
            this.reloadTime = Math.max(
                this.attackSpeedMin,
                baseReload - this.rampReduction,
            );
        }

        // Trample (melee). Charge-melee units (Urumi) splash only on the charged
        // strike; always-on tramplers (Cataphract/elephants) every hit.
        if (!this.isRanged() && (this.chargeAttackMelee <= 0 || charged)) {
            const trampleInfo = this.getTrampleInfo();
            if (trampleInfo) {
                const trampleDmg =
                    Math.floor(damage * trampleInfo.percent) +
                    trampleInfo.flat;
                if (trampleDmg > 0) {
                    const enemies =
                        this.team === 1
                            ? simulation.team2
                            : simulation.team1;
                    for (const enemy of enemies) {
                        if (
                            enemy !== target &&
                            enemy.state !== "dead"
                        ) {
                            const dist = this.distanceTo(enemy);
                            if (
                                dist <=
                                trampleInfo.radius + enemy.radius
                            ) {
                                enemy.takeDamage(trampleDmg, this);
                            }
                        }
                    }
                }
            }
        }

        // Splash on hit (melee)
        if (this.splashOnHitRadius > 0) {
            const enemies =
                this.team === 1
                    ? simulation.team2
                    : simulation.team1;
            for (const enemy of enemies) {
                if (enemy !== target && enemy.state !== "dead") {
                    const dx = enemy.x - target.x;
                    const dy = enemy.y - target.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (
                        dist <=
                        this.splashOnHitRadius + enemy.radius
                    ) {
                        enemy.takeDamage(damage, this);
                    }
                }
            }
        }

        // Pass-through (melee path, if applicable)
        if (this.passThroughPercent > 0) {
            const ptDmg = Math.max(
                1,
                Math.floor(damage * this.passThroughPercent),
            );
            const enemies =
                this.team === 1
                    ? simulation.team2
                    : simulation.team1;
            let best = null;
            let bestDist = Infinity;
            for (const enemy of enemies) {
                if (enemy !== target && enemy.state !== "dead") {
                    const dx = enemy.x - target.x;
                    const dy = enemy.y - target.y;
                    const d = Math.sqrt(dx * dx + dy * dy);
                    if (d < bestDist) {
                        bestDist = d;
                        best = enemy;
                    }
                }
            }
            if (best) {
                best.takeDamage(ptDmg, this);
            }
        }

        // Bleed
        if (this.bleedDps > 0 && targetWasAlive) {
            target.bleedEffect = {
                dps: this.bleedDps,
                timeRemaining: this.bleedDuration,
            };
        }

        this.attackAnimTimer = 0.15;
        this.triggerAttackAnim();

        // Spawn melee visual effect
        simulation.effects.push(
            new MeleeEffect(target.x, target.y, this.team),
        );
    }

    getTrampleInfo() {
        if (this.tramplePercent > 0 || this.trampleFlatDamage > 0) {
            return {
                percent: this.tramplePercent,
                radius: this.trampleRadius,
                flat: this.trampleFlatDamage,
            };
        }
        return null;
    }

    takeDamage(amount, attacker) {
        if (
            this.dodgeShieldMax > 0 &&
            attacker &&
            attacker.isRanged() &&
            this.shieldCharges > 0
        ) {
            this.shieldCharges--;
            this.shieldRechargeTimer = this.dodgeShieldRecharge;
            this.damageNumbers.push({
                value: "DODGE",
                x: this.x,
                y: this.y - this.radius - 5,
                alpha: 1.0,
            });
            return;
        }
        if (
            this.blockFirstMelee &&
            attacker &&
            !attacker.isRanged() &&
            !this.hasBlockedFirstMelee
        ) {
            this.hasBlockedFirstMelee = true;
            this.damageNumbers.push({
                value: "BLOCK",
                x: this.x,
                y: this.y - this.radius - 5,
                alpha: 1.0,
            });
            return;
        }
        // Damage reflect (Khitan Lamellar Armor): bounce a % of melee damage back.
        if (
            this.damageReflectPercent > 0 &&
            amount > 0 &&
            attacker &&
            !attacker.isRanged() &&
            attacker.state !== "dead"
        ) {
            attacker.currentHp -= amount * this.damageReflectPercent;
            if (attacker.currentHp <= 0) {
                attacker.currentHp = 0;
                attacker.state = "dead";
                attacker.target = null;
            }
        }
        this.currentHp -= amount;
        // Floating per-hit damage numbers were removed — at 30v30 they spawn
        // dozens/sec and just clutter the field; live damage is read from the
        // team side panels (HP + Res Lost) instead. DODGE/BLOCK event labels
        // (rare, word-based) still use damageNumbers above.
        if (this.currentHp <= 0) {
            this.currentHp = 0;
            this.state = "dead";
            this.target = null;
        }
    }

    applyDismount() {
        // Replace this dead mounted unit in place with its dismounted form
        // (Konnik). Called by BattleSimulation.update() at END of tick,
        // mirroring simulation_real.py / simulation.py: the horse's death
        // still credits on-kill effects, same-tick overkill is forgiven,
        // any committed strike is cancelled and a killing-blow bleed dies
        // with the old body. The foot soldier spawns at FULL dismount HP
        // with its cooldown starting at one full dismount reload, and is
        // always melee (the dismount block carries no range).
        this.isDismounted = true;
        this.maxHp = this.dismountHp;
        this.currentHp = this.dismountHp;
        if (this.dismountAttack > 0) this.attack = this.dismountAttack;
        this.meleeArmor = this.dismountMeleeArmor;
        this.pierceArmor = this.dismountPierceArmor;
        if (this.dismountAttacks) this.attacks = this.dismountAttacks;
        if (this.dismountArmors) this.armors = this.dismountArmors;
        if (this.dismountAttackSpeed > 0) {
            this.attackSpeed = this.dismountAttackSpeed;
            this.reloadTime = 1.0 / this.dismountAttackSpeed;
        }
        this.attackDelay = this.dismountAttackDelay;
        if (this.dismountMovementSpeed > 0) {
            this.moveSpeed = this.dismountMovementSpeed * TILE_SIZE;
            this.baseMoveSpeed = this.moveSpeed;
        }
        this.rawAttackRange = 0;
        this.attackRange = MELEE_RANGE_BUFFER; // dismounted is always melee
        this.state = "idle";
        this.target = null;
        this.attackCooldown = this.reloadTime;
        this.committedAttack = null;
        this.bleedEffect = null;
        // The second, final death may trigger ally-death heals again.
        this.deathHealTriggered = false;
    }

    moveTowardTarget(dt, allUnits) {
        if (!this.target) return;
        let dx = this.target.x - this.x;
        let dy = this.target.y - this.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 1) return;
        dx /= dist;
        dy /= dist;
        const avoidance = this.calculateAvoidance(allUnits);
        const avoidMag = Math.sqrt(
            avoidance.x * avoidance.x + avoidance.y * avoidance.y,
        );
        // If avoidance is strong (units very close), let it dominate
        if (avoidMag > 2) {
            dx = avoidance.x + dx * 0.2;
            dy = avoidance.y + dy * 0.2;
        } else {
            dx += avoidance.x;
            dy += avoidance.y;
        }
        const len = Math.sqrt(dx * dx + dy * dy);
        if (len > 0) {
            dx /= len;
            dy /= len;
        }

        // Smooth velocity -- blend desired direction with previous velocity
        const smoothing = 0.3; // 0=instant snap, 1=no change
        this.vx = this.vx * smoothing + dx * (1 - smoothing);
        this.vy = this.vy * smoothing + dy * (1 - smoothing);
        const vLen = Math.sqrt(
            this.vx * this.vx + this.vy * this.vy,
        );
        if (vLen > 0) {
            this.vx /= vLen;
            this.vy /= vLen;
        }

        const moveAmount = this.moveSpeed * dt;
        this.x += this.vx * moveAmount;
        this.y += this.vy * moveAmount;
        this.x = Math.max(
            this.radius,
            Math.min(CANVAS_WIDTH - this.radius, this.x),
        );
        this.y = Math.max(
            this.radius,
            Math.min(CANVAS_HEIGHT - this.radius, this.y),
        );

        // Stuck detection: if not making progress, mark target as blocked
        const newDist = this.distanceTo(this.target);
        if (newDist >= this.lastDistToTarget - 0.5) {
            this.stuckTimer += dt;
        } else {
            this.stuckTimer = Math.max(0, this.stuckTimer - dt * 2);
        }
        this.lastDistToTarget = newDist;
        if (this.stuckTimer > 0.8) {
            this.blockedTargets.add(this.target);
            this.target = null; // force re-target next frame
            this.stuckTimer = 0;
        }
    }

    moveAwayFromTarget(dt, allUnits) {
        if (!this.target) return;
        let dx = this.x - this.target.x;
        let dy = this.y - this.target.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 1) {
            dx = this.team === 1 ? -1 : 1;
            dy = 0;
        } else {
            dx /= dist;
            dy /= dist;
        }
        const avoidance = this.calculateAvoidance(allUnits);
        dx += avoidance.x;
        dy += avoidance.y;
        const len = Math.sqrt(dx * dx + dy * dy);
        if (len > 0) {
            dx /= len;
            dy /= len;
        }
        // Smooth velocity for kiting too
        const smoothing = 0.3;
        this.vx = this.vx * smoothing + dx * (1 - smoothing);
        this.vy = this.vy * smoothing + dy * (1 - smoothing);
        const vLen = Math.sqrt(
            this.vx * this.vx + this.vy * this.vy,
        );
        if (vLen > 0) {
            this.vx /= vLen;
            this.vy /= vLen;
        }
        const moveAmount = this.moveSpeed * dt;
        this.x += this.vx * moveAmount;
        this.y += this.vy * moveAmount;
        this.x = Math.max(
            this.radius,
            Math.min(CANVAS_WIDTH - this.radius, this.x),
        );
        this.y = Math.max(
            this.radius,
            Math.min(CANVAS_HEIGHT - this.radius, this.y),
        );
    }

    calculateAvoidance(allUnits) {
        let avoidX = 0,
            avoidY = 0;
        for (const other of allUnits) {
            if (other === this || other.state === "dead") continue;
            const dx = this.x - other.x;
            const dy = this.y - other.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            const minDist = this.radius + other.radius + 2;
            if (dist < minDist * 1.5 && dist > 0) {
                const overlap =
                    Math.max(0, minDist - dist) / minDist;
                // Strong force when overlapping, moderate when close
                const force = overlap > 0 ? 3 + overlap * 5 : 0.5;
                avoidX += (dx / dist) * force;
                avoidY += (dy / dist) * force;
            }
        }
        return { x: avoidX, y: avoidY };
    }

    render(ctx) {
        if (this.state === "dead") ctx.globalAlpha = 0.3;

        const img = this.spriteImg;
        const imgReady =
            img && img.complete && img.naturalWidth > 0;

        if (this.isSprite && imgReady) {
            // Sprite mode: no circle/ring — team color is baked into the sprite
            // (team 1 blue, team 2 red). Contain the whole sprite within a box of
            // 2.8*radius (a bit bigger than the unit footprint for readability),
            // scaling by the LARGER sprite dimension so wide/tall off-shapes stay
            // fully contained and never explode in one axis.
            const box = this.radius * 2.8;
            // Attack tell: a warm glow + slight lunge that pulses out over the
            // attack timer, so a swing/shot is unmistakable. atk goes 1 -> 0.
            const atk =
                this.attackAnimTimer > 0
                    ? Math.min(1, this.attackAnimTimer / 0.18)
                    : 0;
            // Attack sprite-sheet playback: while a unit is attacking, play its
            // attack animation frame-by-frame off a horizontal strip (canvas can't
            // auto-play a WebP); otherwise draw the static idle sprite. The strip
            // is single-colour (red) for both teams by design. Source rect picks
            // the current frame; the static path uses the whole image.
            const sheet = this.attackSheet;
            // Play while actively attacking OR while the post-attack latch is still
            // running (animHold), so a swing/shot completes even as the unit moves
            // or kites away. Dead units never play attack frames.
            const playing = this.state !== "dead"
                && (this.state === "attacking" || this.animHold > 0)
                && sheet && sheet.img
                && sheet.img.complete && sheet.img.naturalWidth > 0;
            let src = img, sx = 0, sy = 0, sw = img.naturalWidth, sh = img.naturalHeight;
            if (playing) {
                const m = sheet.meta;
                const phase = parseInt(String(this.id).split("-")[1], 10) || 0;
                const frame = (Math.floor((simulation.battleTime * 1000) / m.dur) + phase) % m.frames;
                src = sheet.img; sx = frame * m.fw; sy = 0; sw = m.fw; sh = m.fh;
            }
            let s = box / Math.max(sw, sh);
            // Per-unit calibration: the attack frames are sized for the full swing
            // arc, so the figure fills a smaller fraction than the tight idle sprite.
            // scale (from the catalog) makes the typical attack pose match the idle
            // unit's on-screen size so it doesn't appear to shrink mid-attack.
            if (playing && sheet.meta.scale) s *= sheet.meta.scale;
            if (atk > 0) s *= 1 + 0.1 * atk;
            const dw = sw * s;
            const dh = sh * s;
            // Face toward what the unit is fighting: its target if engaged (so it
            // faces where it attacks even after maneuvering past the enemy), else
            // its movement direction. A deadzone avoids flicker on near-vertical
            // alignment (target dx is in px; vx is normalized ~-1..1).
            if (this.target && this.target.state !== "dead") {
                const fdx = this.target.x - this.x;
                if (Math.abs(fdx) > 4) this.faceRight = fdx > 0;
            } else if (Math.abs(this.vx) > 0.05) {
                this.faceRight = this.vx > 0;
            }
            ctx.save();
            if (atk > 0) {
                ctx.shadowColor = `rgba(255, 209, 74, ${0.95 * atk})`;
                ctx.shadowBlur = 22 * atk;
            }
            if (this.faceRight) {
                // Sprites are authored facing left, so mirror horizontally about
                // the unit's center to make it face right.
                ctx.translate(this.x, 0);
                ctx.scale(-1, 1);
                ctx.drawImage(src, sx, sy, sw, sh, -dw / 2, this.y - dh / 2, dw, dh);
            } else {
                ctx.drawImage(src, sx, sy, sw, sh, this.x - dw / 2, this.y - dh / 2, dw, dh);
            }
            ctx.restore();
        } else {
            // Legacy ring + circular portrait (fallback units / image not loaded yet)
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.radius + 2, 0, Math.PI * 2);
            let ringColor = this.team === 1 ? "#3498db" : "#e74c3c";
            if (this.attackAnimTimer > 0) ringColor = "#ffffff";
            else if (this.state === "kiting")
                ringColor = this.team === 1 ? "#9b59b6" : "#1abc9c";
            ctx.fillStyle = ringColor;
            ctx.fill();

            if (imgReady) {
                ctx.save();
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
                ctx.clip();
                ctx.drawImage(
                    img,
                    this.x - this.radius,
                    this.y - this.radius,
                    this.radius * 2,
                    this.radius * 2,
                );
                ctx.restore();
            } else {
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
                ctx.fillStyle = this.team === 1 ? "#2980b9" : "#c0392b";
                ctx.fill();
            }
        }

        ctx.globalAlpha = 1.0;

        // HP bar
        if (this.state !== "dead") {
            const barWidth = this.radius * 2;
            const barHeight = 4;
            const barX = this.x - this.radius;
            const barY = this.y - this.radius - 10;
            ctx.fillStyle = "rgba(0,0,0,0.45)";
            ctx.fillRect(barX, barY, barWidth, barHeight);
            const hpPercent = this.currentHp / this.maxHp;
            // Team-coloured bar (team 1 blue, team 2 red) so it's obvious whose
            // unit is whose at a glance; remaining HP is shown by the fill width.
            ctx.fillStyle =
                this.team === 1 ? CANVAS_PAL.team1 : CANVAS_PAL.team2;
            ctx.fillRect(
                barX,
                barY,
                barWidth * hpPercent,
                barHeight,
            );
        }

        // Damage numbers
        for (const dn of this.damageNumbers) {
            ctx.globalAlpha = dn.alpha;
            ctx.fillStyle = "#ff0";
            ctx.font = "bold 13px Alegreya Sans, Arial";
            ctx.textAlign = "center";
            ctx.fillText(`-${dn.value}`, dn.x, dn.y);
        }
        ctx.globalAlpha = 1.0;
    }
}

// ===== BATTLE SIMULATION =====
class BattleSimulation {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext("2d");
        // Logical (CSS-pixel) coordinate space the whole sim works in. The canvas
        // backing store is sized larger (display size * devicePixelRatio) and the
        // context is scaled to match each frame, so sprites stay crisp on HiDPI /
        // upscaled displays instead of being blurred by the browser stretching a
        // fixed 900x600 bitmap. All layout/spawn math uses this.W / this.H.
        this.W = canvas.width || CANVAS_WIDTH;
        this.H = canvas.height || CANVAS_HEIGHT;
        this.renderScaleX = 1;
        this.renderScaleY = 1;
        this.team1 = [];
        this.team2 = [];
        this.team1Stats = null;
        this.team2Stats = null;
        this.running = false;
        this.paused = false;
        this.battleTime = 0;
        this.speedMultiplier = 3.0;
        this.lastTimestamp = 0;
        this.winner = null;
        this.projectiles = [];
        this.effects = [];
        this.resizeBackingStore();
        // Re-fit the backing store whenever the canvas's displayed size changes
        // (window resize, the pick->battle arena transition, mobile stacking) and
        // repaint so a static (paused / pre-battle) frame stays sharp too.
        try {
            new ResizeObserver(() => {
                this.resizeBackingStore();
                this.render();
            }).observe(canvas);
        } catch (e) {
            /* ResizeObserver unsupported: keep the initial backing-store size */
        }
    }

    // Match the backing store to the on-screen size * devicePixelRatio. Setting
    // canvas.width/height does NOT change the CSS layout box (width:100% drives
    // that), so this never re-triggers the ResizeObserver into a loop.
    resizeBackingStore() {
        const dpr = window.devicePixelRatio || 1;
        const rect = this.canvas.getBoundingClientRect();
        const cssW = rect.width || this.W;
        const cssH = rect.height || this.H;
        const pxW = Math.max(1, Math.round(cssW * dpr));
        const pxH = Math.max(1, Math.round(cssH * dpr));
        if (this.canvas.width !== pxW || this.canvas.height !== pxH) {
            this.canvas.width = pxW;
            this.canvas.height = pxH;
        }
        // Map the logical W x H space onto the full backing store. aspect-ratio:3/2
        // is locked in CSS, so these scales stay ~equal (no stretch).
        this.renderScaleX = this.canvas.width / this.W;
        this.renderScaleY = this.canvas.height / this.H;
    }

    async setupTeam(teamNum, unitSlug, civName, count, age, opts = {}) {
        const ageParam = age
            ? `?age=${encodeURIComponent(age)}`
            : "";
        const response = await fetch(
            `/api/ref/combat-unit/${encodeURIComponent(civName)}/${unitSlug}${ageParam}`,
        );
        if (!response.ok) {
            const err = await response.json();
            throw new Error(
                err.error ||
                    `Failed to load ${civName} ${unitSlug}`,
            );
        }
        const stats = await response.json();

        // Lithuanian relic picker: the served stats bake in all RELIC_MAX
        // relics (+1 base melee attack each), so apply the user-picked delta
        // to both the flat attack and the base-melee armor class ("4").
        const relics =
            opts.relics != null ? opts.relics : RELIC_MAX;
        if (
            relics !== RELIC_MAX &&
            civName === "Lithuanians" &&
            RELIC_BONUS_UNITS.has(unitSlug)
        ) {
            const delta = relics - RELIC_MAX;
            stats.attack = Math.max(0, (stats.attack || 0) + delta);
            if (stats.attacks_json) {
                const atk = JSON.parse(stats.attacks_json);
                if (atk["4"] != null)
                    atk["4"] = Math.max(0, atk["4"] + delta);
                stats.attacks_json = JSON.stringify(atk);
            }
        }

        const team = [];
        const outlineSize = stats.outline_size || 0.2;
        const unitRadius = Math.round(
            10 + Math.min(outlineSize, 1.0) * 20,
        );
        const startX =
            teamNum === 1
                ? 30 + unitRadius
                : this.W - 30 - unitRadius;
        const minSpacing = unitRadius * 2.2;
        const naturalSpacing =
            count > 1
                ? (this.H - 2 * unitRadius) /
                  (count - 1)
                : 0;
        const spacing = Math.max(naturalSpacing, minSpacing);
        const totalHeight = (count - 1) * spacing;
        const startY =
            count > 1
                ? Math.max(
                      unitRadius,
                      (this.H - totalHeight) / 2,
                  )
                : this.H / 2;

        for (let i = 0; i < count; i++) {
            const unit = new BattleUnit(
                `${teamNum}-${i}`,
                teamNum,
                stats,
                unitSlug,
                civName,
            );
            unit.x = startX + (Math.random() - 0.5) * 10;
            unit.y = startY + i * spacing;
            // Starting-kills picker: pre-load the per-kill snowball counter
            // (capped at attackBonusPerKill, same as kills earned in-battle).
            if (opts.startKills > 0 && unit.attackBonusPerKill > 0) {
                unit.killBonusAttack = Math.min(
                    unit.attackBonusPerKill,
                    opts.startKills,
                );
            }
            // Assign preloaded sprite image
            unit.spriteImg = unitImages[teamNum];
            unit.isSprite = unitIsSprite[teamNum];
            unit.attackSheet = unitSheets[teamNum];
            team.push(unit);
        }

        if (teamNum === 1) {
            this.team1 = team;
            this.team1Stats = stats;
        } else {
            this.team2 = team;
            this.team2Stats = stats;
        }
    }

    start() {
        if (this.team1.length === 0 || this.team2.length === 0) {
            alert("Please configure both teams");
            return;
        }
        this.running = true;
        this.paused = false;
        this.battleTime = 0;
        this.winner = null;
        this.projectiles = [];
        this.effects = [];
        this.lastTimestamp = performance.now();
        this.updateStats();
        this.updateDebugPanel();
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
        this.running = false;
        this.paused = false;
        this.battleTime = 0;
        this.winner = null;
        this.team1 = [];
        this.team2 = [];
        this.team1Stats = null;
        this.team2Stats = null;
        this.projectiles = [];
        this.effects = [];
        this.updateStats();
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
        while (remaining > 1e-6 && !this.winner) {
            const dt = Math.min(remaining, STEP);
            this.update(dt);
            remaining -= dt;
        }
        this.render();
        if (!this.winner) requestAnimationFrame(() => this.loop());
    }

    update(dt) {
        this.battleTime += dt;
        const allUnits = [...this.team1, ...this.team2];
        for (const unit of this.team1)
            unit.update(dt, allUnits, this.team2);
        for (const unit of this.team2)
            unit.update(dt, allUnits, this.team1);

        // Hard collision resolution -- push overlapping units apart
        this.resolveCollisions(allUnits);

        // Update projectiles
        for (const p of this.projectiles) p.update(dt);
        this.projectiles = this.projectiles.filter((p) => !p.done);

        // Ally-death heal (Guecha Warrior): when a unit dies, nearby allies with
        // ally_death_heal gain a refreshing heal-over-time.  Each death fires once.
        for (const dead of allUnits) {
            if (dead.state !== "dead" || dead.deathHealTriggered) continue;
            dead.deathHealTriggered = true;
            const allies = dead.team === 1 ? this.team1 : this.team2;
            for (const ally of allies) {
                if (
                    ally === dead ||
                    ally.state === "dead" ||
                    ally.allyDeathHeal <= 0
                )
                    continue;
                if (dead.distanceTo(ally) <= 5 * TILE_SIZE) {
                    ally.allyHealRemaining = ally.allyDeathHeal;
                    ally.allyHealRate =
                        ally.allyDeathHealDuration > 0
                            ? ally.allyDeathHeal / ally.allyDeathHealDuration
                            : ally.allyDeathHeal;
                }
            }
        }

        // Update effects
        for (const e of this.effects) e.update(dt);
        this.effects = this.effects.filter((e) => !e.done);

        // Dismount on death (Konnik): dead mounted units respawn in place as
        // their dismounted form at END of tick — after all damage and before
        // the winner check, mirroring simulation_real.py / simulation.py.
        // The revived unit counts as alive and cannot act until next tick.
        for (const unit of allUnits) {
            if (
                unit.state === "dead" &&
                !unit.isDismounted &&
                unit.dismountHp > 0
            ) {
                unit.applyDismount();
            }
        }

        const team1Alive = this.team1.filter(
            (u) => u.state !== "dead",
        ).length;
        const team2Alive = this.team2.filter(
            (u) => u.state !== "dead",
        ).length;
        this.updateStats();

        if (team1Alive === 0 && team2Alive > 0) {
            this.winner = 2;
            this.running = false;
            updateBattleWinner(2);
        } else if (team2Alive === 0 && team1Alive > 0) {
            this.winner = 1;
            this.running = false;
            updateBattleWinner(1);
        } else if (team1Alive === 0 && team2Alive === 0) {
            this.winner = 0;
            this.running = false;
            updateBattleWinner(0);
        }
    }

    resolveCollisions(allUnits) {
        const alive = allUnits.filter((u) => u.state !== "dead");
        const n = alive.length;
        // Run multiple passes to resolve cascading overlaps
        for (let pass = 0; pass < 3; pass++) {
            for (let i = 0; i < n; i++) {
                for (let j = i + 1; j < n; j++) {
                    const a = alive[i],
                        b = alive[j];
                    const dx = b.x - a.x;
                    const dy = b.y - a.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    const minDist = a.radius + b.radius + 1;
                    if (dist < minDist && dist > 0.01) {
                        const overlap = (minDist - dist) / 2;
                        const nx = dx / dist;
                        const ny = dy / dist;
                        a.x -= nx * overlap;
                        a.y -= ny * overlap;
                        b.x += nx * overlap;
                        b.y += ny * overlap;
                    } else if (dist <= 0.01) {
                        // Exactly on top -- nudge apart
                        a.x -= 2;
                        b.x += 2;
                    }
                }
            }
        }
        // Clamp to canvas bounds
        for (const u of alive) {
            u.x = Math.max(
                u.radius,
                Math.min(CANVAS_WIDTH - u.radius, u.x),
            );
            u.y = Math.max(
                u.radius,
                Math.min(CANVAS_HEIGHT - u.radius, u.y),
            );
        }
    }

    render() {
        const ctx = this.ctx;
        // Draw in logical (W x H) space; the transform scales it up to the HiDPI
        // backing store. High-quality smoothing keeps the downscaled sprites sharp.
        ctx.setTransform(this.renderScaleX, 0, 0, this.renderScaleY, 0, 0);
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = "high";
        ctx.fillStyle = CANVAS_PAL.bg;
        ctx.fillRect(0, 0, this.W, this.H);
        this.drawGrid(ctx);

        const allUnits = [...this.team1, ...this.team2];
        const dead = allUnits.filter((u) => u.state === "dead");
        const alive = allUnits.filter((u) => u.state !== "dead");
        for (const unit of dead) unit.render(ctx);
        for (const unit of alive) unit.render(ctx);

        // Draw projectiles
        for (const p of this.projectiles) p.render(ctx);
        // Draw effects
        for (const e of this.effects) e.render(ctx);

        if (this.winner !== null) this.drawWinner(ctx);
    }

    drawGrid(ctx) {
        ctx.strokeStyle = CANVAS_PAL.grid;
        ctx.lineWidth = 1;
        for (let x = 0; x <= this.W; x += 50) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, this.H);
            ctx.stroke();
        }
        for (let y = 0; y <= this.H; y += 50) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(this.W, y);
            ctx.stroke();
        }
    }

    drawWinner(ctx) {
        ctx.fillStyle = "rgba(0,0,0,0.7)";
        ctx.fillRect(0, 0, this.W, this.H);
        let text, subtext, color;
        if (this.winner === 1) {
            const civ = currentBattle?.team1_civ || "Team 1";
            const unit = currentBattle?.team1_unit_name || "";
            text = `${civ} ${unit}`;
            subtext = "Victory!";
            color = CANVAS_PAL.team1;
        } else if (this.winner === 2) {
            const civ = currentBattle?.team2_civ || "Team 2";
            const unit = currentBattle?.team2_unit_name || "";
            text = `${civ} ${unit}`;
            subtext = "Victory!";
            color = CANVAS_PAL.team2;
        } else {
            text = "Draw!";
            subtext = "";
            color = CANVAS_PAL.gold;
        }
        ctx.fillStyle = color;
        ctx.font = "bold 34px Cinzel, serif";
        ctx.textAlign = "center";
        ctx.fillText(
            text,
            this.W / 2,
            this.H / 2 - 10,
        );
        if (subtext) {
            ctx.fillStyle = CANVAS_PAL.gold;
            ctx.font = "bold 22px Cinzel, serif";
            ctx.fillText(
                subtext,
                this.W / 2,
                this.H / 2 + 22,
            );
        }
        ctx.fillStyle = "#ece1cd";
        ctx.font = "16px 'Source Sans 3', sans-serif";
        ctx.fillText(
            `Battle time: ${this.battleTime.toFixed(1)}s`,
            this.W / 2,
            this.H / 2 + 50,
        );
    }

    updateStats() {
        const t1Alive = this.team1.filter(
            (u) => u.state !== "dead",
        );
        const t2Alive = this.team2.filter(
            (u) => u.state !== "dead",
        );
        const t1Hp = t1Alive.reduce((s, u) => s + u.currentHp, 0);
        const t2Hp = t2Alive.reduce((s, u) => s + u.currentHp, 0);

        document.getElementById("battleTimer").textContent =
            `${this.battleTime.toFixed(1)}s`;

        // Team 1 progress
        document.getElementById("prog1Units").textContent =
            `${t1Alive.length} / ${this.team1.length}`;
        document.getElementById("prog1Hp").textContent =
            `${Math.round(t1Hp)} / ${Math.round(this.team1.length * (this.team1Stats?.hp || 0))}`;
        if (currentBattle) {
            document.getElementById("prog1Res").textContent =
                currentBattle.team1_total_cost;
            const t1Dead = this.team1.length - t1Alive.length;
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
            `${t2Alive.length} / ${this.team2.length}`;
        document.getElementById("prog2Hp").textContent =
            `${Math.round(t2Hp)} / ${Math.round(this.team2.length * (this.team2Stats?.hp || 0))}`;
        if (currentBattle) {
            document.getElementById("prog2Res").textContent =
                currentBattle.team2_total_cost;
            const t2Dead = this.team2.length - t2Alive.length;
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

    updateDebugPanel() {
        if (
            !this.team1Stats ||
            !this.team2Stats ||
            this.team1.length === 0 ||
            this.team2.length === 0
        )
            return;
        const unit1 = this.team1[0];
        const unit2 = this.team2[0];
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

        const team1CivSafe = escapeHtml(this.team1Stats.civ);
        const team1NameSafe = escapeHtml(this.team1Stats.name);
        const team2CivSafe = escapeHtml(this.team2Stats.civ);
        const team2NameSafe = escapeHtml(this.team2Stats.name);

        let html = "";
        html += `<div class="debug-section team1"><h4>${team1CivSafe} ${team1NameSafe}</h4>`;
        html += `<h5 style="color:var(--text-muted);margin-bottom:8px;font-size:0.7rem">&rarr; vs ${team2CivSafe} ${team2NameSafe}</h5>`;
        html +=
            buildFormula(
                unit1,
                unit2,
                dmg1to2,
                this.team1Stats,
                this.team2Stats,
            ) + `</div>`;

        html += `<div class="debug-section team2"><h4>${team2CivSafe} ${team2NameSafe}</h4>`;
        html += `<h5 style="color:var(--text-muted);margin-bottom:8px;font-size:0.7rem">&rarr; vs ${team1CivSafe} ${team1NameSafe}</h5>`;
        html +=
            buildFormula(
                unit2,
                unit1,
                dmg2to1,
                this.team2Stats,
                this.team1Stats,
            ) + `</div>`;

        document.getElementById("debugContent").innerHTML = html;
    }
}

// ===== INITIALIZATION =====
let simulation = null;
let currentBattle = null;

document.addEventListener("DOMContentLoaded", async () => {
    const canvas = document.getElementById("battleCanvas");
    simulation = new BattleSimulation(canvas);

    // Load armor class names
    try {
        const resp = await fetch("/api/armor-classes");
        armorClassNames = await resp.json();
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
            simulation.pause();
            document.getElementById("pauseBtn").textContent =
                simulation.paused ? "Resume" : "Pause";
        });
    document
        .getElementById("resetBtn")
        .addEventListener("click", () => {
            simulation.reset();
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
        simulation.speedMultiplier = parseFloat(e.target.value);
        document.getElementById("speedLabel").textContent =
            `${e.target.value}x`;
    });
    // Sync the sim + label to the slider's initial value (defaults to 3x).
    simulation.speedMultiplier = parseFloat(speedSlider.value);
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

    simulation.render();

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

        if (
            armyMode === "resources" ||
            armyMode === "resources_upgrades"
        ) {
            const totalResources =
                parseInt(
                    document.getElementById("totalResources").value,
                ) || 3000;
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
            const [pstats1, pstats2] = await Promise.all([
                fetch(
                    `/api/ref/combat-unit/${encodeURIComponent(s1.civ)}/${s1.unitSlug}?age=${encodeURIComponent(s1.age)}`,
                ).then((r) => r.json()),
                fetch(
                    `/api/ref/combat-unit/${encodeURIComponent(s2.civ)}/${s2.unitSlug}?age=${encodeURIComponent(s2.age)}`,
                ).then((r) => r.json()),
            ]);
            const popSpace1 = (pstats1 && pstats1.pop_space) || 1.0;
            const popSpace2 = (pstats2 && pstats2.pop_space) || 1.0;
            team1Count = Math.max(1, Math.floor(pop1 / popSpace1));
            team2Count = Math.max(1, Math.floor(pop2 / popSpace2));
        }

        simulation.reset();
        await simulation.setupTeam(
            1,
            s1.unitSlug,
            s1.civ,
            team1Count,
            s1.age,
            { relics: s1.relics, startKills: s1.startKills },
        );
        await simulation.setupTeam(
            2,
            s2.unitSlug,
            s2.civ,
            team2Count,
            s2.age,
            { relics: s2.relics, startKills: s2.startKills },
        );

        currentBattle = {
            team1_civ: s1.civ,
            team1_unit: s1.unitSlug,
            team1_unit_name:
                simulation.team1Stats?.name || s1.unitName,
            team1_count: team1Count,
            team1_total_cost:
                simulation.team1Stats.total_cost * team1Count,
            team1_unit_cost: simulation.team1Stats.total_cost,
            team1_max_hp: simulation.team1Stats.hp,
            team2_civ: s2.civ,
            team2_unit: s2.unitSlug,
            team2_unit_name:
                simulation.team2Stats?.name || s2.unitName,
            team2_count: team2Count,
            team2_total_cost:
                simulation.team2Stats.total_cost * team2Count,
            team2_unit_cost: simulation.team2Stats.total_cost,
            team2_max_hp: simulation.team2Stats.hp,
            winner: null,
        };

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
        simulation.start();

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
    if (e.key === "Escape" && simulation) simulation.pause();
});

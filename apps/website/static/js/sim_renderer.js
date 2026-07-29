/*
 * Role: renderer — browser-only canvas drawing for the battle sim.
 *
 * Every pixel the Battle Sim page paints is drawn here. The engine modules under
 * engine/ own state and physics and know nothing about a canvas; this module owns
 * the 2D context, the HiDPI backing store, the theme palette and the per-team
 * sprite assets, and reads engine state through the public surface only
 * (sim.team1/team2/projectiles/effects/battleTime/winner/W/H + unit fields).
 *
 * The one exception to "reads only": drawUnit writes `unit.faceRight`, which is
 * render-only state the engine initializes and never reads back (and never
 * hashes). See the comment block at that assignment for the full rationale.
 *
 * Provenance — every drawing body below was lifted out of simulate.js, which
 * keeps its own copy until the Task 8 cutover (change one, change the other
 * until then):
 *
 *   simulate.js 21-53      -> CANVAS_PAL + refreshCanvasPalette + MutationObserver
 *   simulate.js 636-654    -> drawProjectileBall   (was Projectile._renderBall)
 *   simulate.js 656-775    -> drawProjectile       (was Projectile.render)
 *   simulate.js 794-831    -> drawEffect           (was MeleeEffect.render)
 *   simulate.js 2175-2313  -> drawUnit             (was BattleUnit.render)
 *   simulate.js 2342-2374  -> the ResizeObserver + resizeBackingStore
 *   simulate.js 2656-2679  -> SimRenderer.render   (was BattleSimulation.render)
 *   simulate.js 2681-2696  -> drawGrid
 *   simulate.js 2698-2743  -> drawWinner
 *
 * The transplants are byte-faithful apart from mechanical rewrites forced by the
 * split (every colour, alpha, radius, formula and comment is unchanged):
 *   * `this.` becomes the parameter the object now arrives as (p./e./unit./sim.).
 *   * `simulation.battleTime` (a page global) becomes `sim.battleTime`.
 *   * the sprite assets legacy setupTeam stamped onto each unit
 *     (`unit.spriteImg` / `unit.isSprite` / `unit.attackSheet`, simulate.js
 *     2456-2458) become `assets.img` / `assets.isSprite` / `assets.sheet`,
 *     registered per team via setTeamAssets() and looked up by unit.team.
 *   * drawWinner's page-global `currentBattle?.team1_civ` / `team1_unit_name`
 *     become renderer labels set via setLabels() — they are page-selection
 *     strings, not engine state, so the engine cannot supply them.
 */

import { CANVAS_WIDTH, CANVAS_HEIGHT } from "./engine/constants.js";

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

// Stand-in for a team whose assets were never registered. Legacy units started
// with spriteImg/attackSheet null and no isSprite at all, so an unregistered team
// falls through to the same legacy ring + circular-portrait path it always did.
const NO_ASSETS = { img: null, isSprite: false, sheet: null };
// Same idea for the winner banner: unset labels reproduce the legacy
// `currentBattle?.x || "Team 1"` fallbacks.
const NO_LABELS = {};

// ===== PROJECTILES =====

// Round projectiles (bullet / cannonball / stone): a filled ball with a faint
// motion trail and a small specular highlight. No team tint — coloured by what
// the projectile is.
function drawProjectileBall(ctx, p, r, fill, trail) {
    ctx.globalAlpha = 0.25;
    ctx.beginPath();
    ctx.moveTo(p.prevX, p.prevY);
    ctx.lineTo(p.x, p.y);
    ctx.strokeStyle = trail;
    ctx.lineWidth = r;
    ctx.lineCap = "round";
    ctx.stroke();
    ctx.globalAlpha = 1.0;
    ctx.beginPath();
    ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
    ctx.fillStyle = fill;
    ctx.fill();
    ctx.beginPath();
    ctx.arc(p.x - r * 0.3, p.y - r * 0.3, r * 0.32, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(255,255,255,0.4)";
    ctx.fill();
}

function drawProjectile(ctx, p) {
    if (p.done) return;
    const k = p.kind;

    // --- Round shots ---
    if (k === "bullet") { drawProjectileBall(ctx, p, 2.6, "#141414", "#333"); return; }
    if (k === "cannonball") { drawProjectileBall(ctx, p, 5.5, "#0d0d0d", "#000"); return; }
    if (k === "stone") { drawProjectileBall(ctx, p, 5, "#867c6e", "#6f665a"); return; }

    // --- Elongated shots (arrow / javelin / bolt): oriented along flight ---
    ctx.save();
    ctx.translate(p.x, p.y);
    ctx.rotate(p.angle);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    if (k === "rocket") {
        // Rocket: exhaust trail behind, dark shaft, red-banded head and a
        // bright flame at the tail. Reads as a streak of fire in flight.
        const SHAFT = 12, TAIL = -SHAFT - 1;
        // Smoke/fire trail along the recent flight path.
        ctx.globalAlpha = 0.35;
        ctx.strokeStyle = "#ffb347";
        ctx.lineWidth = 2.4;
        ctx.beginPath();
        ctx.moveTo(TAIL, 0);
        ctx.lineTo(TAIL - 10, 0);
        ctx.stroke();
        ctx.globalAlpha = 1.0;
        // Shaft
        ctx.strokeStyle = "#5a4632";
        ctx.lineWidth = 2.4;
        ctx.beginPath();
        ctx.moveTo(-2, 0);
        ctx.lineTo(TAIL, 0);
        ctx.stroke();
        // Warhead (red-banded tip)
        ctx.fillStyle = "#b3382e";
        ctx.beginPath();
        ctx.moveTo(4, 0);
        ctx.lineTo(-3, -2.4);
        ctx.lineTo(-3, 2.4);
        ctx.closePath();
        ctx.fill();
        // Tail flame: outer orange + inner yellow
        ctx.fillStyle = "#ff7a1a";
        ctx.beginPath();
        ctx.moveTo(TAIL, -2.6);
        ctx.lineTo(TAIL - 7, 0);
        ctx.lineTo(TAIL, 2.6);
        ctx.closePath();
        ctx.fill();
        ctx.fillStyle = "#ffd54a";
        ctx.beginPath();
        ctx.moveTo(TAIL, -1.3);
        ctx.lineTo(TAIL - 4, 0);
        ctx.lineTo(TAIL, 1.3);
        ctx.closePath();
        ctx.fill();
    } else if (k === "javelin") {
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

// ===== MELEE / SPLASH IMPACT EFFECTS =====

function drawEffect(ctx, e) {
    if (e.done) return;
    const progress = e.age / e.lifetime;
    const alpha = 1.0 - progress;

    if (e.splashRadius > 0) {
        // Siege splash: expanding filled circle
        const radius =
            e.splashRadius * (0.3 + 0.7 * progress);
        ctx.globalAlpha = alpha * 0.35;
        ctx.beginPath();
        ctx.arc(e.x, e.y, radius, 0, Math.PI * 2);
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
        ctx.arc(e.x, e.y, r * 0.55, 0, Math.PI * 2);
        ctx.fillStyle = "#ffe8a3";
        ctx.fill();
        ctx.globalAlpha = alpha;
        ctx.beginPath();
        ctx.arc(e.x, e.y, r, 0, Math.PI * 2);
        ctx.strokeStyle = "#ffd14a";
        ctx.lineWidth = 2.5;
        ctx.stroke();
    }
    ctx.globalAlpha = 1.0;
}

// ===== UNITS =====

function drawUnit(ctx, unit, assets, sim, pal) {
    if (unit.state === "dead") ctx.globalAlpha = 0.3;

    const img = assets.img;
    const imgReady =
        img && img.complete && img.naturalWidth > 0;

    if (assets.isSprite && imgReady) {
        // Sprite mode: no circle/ring — team color is baked into the sprite
        // (team 1 blue, team 2 red). Contain the whole sprite within a box of
        // 2.8*radius (a bit bigger than the unit footprint for readability),
        // scaling by the LARGER sprite dimension so wide/tall off-shapes stay
        // fully contained and never explode in one axis.
        const box = unit.radius * 2.8;
        // Attack tell: a warm glow + slight lunge that pulses out over the
        // attack timer, so a swing/shot is unmistakable. atk goes 1 -> 0.
        const atk =
            unit.attackAnimTimer > 0
                ? Math.min(1, unit.attackAnimTimer / 0.18)
                : 0;
        // Attack sprite-sheet playback: while a unit is attacking, play its
        // attack animation frame-by-frame off a horizontal strip (canvas can't
        // auto-play a WebP); otherwise draw the static idle sprite. The strip
        // is single-colour (red) for both teams by design. Source rect picks
        // the current frame; the static path uses the whole image.
        const sheet = assets.sheet;
        // Play while actively attacking OR while the post-attack latch is still
        // running (animHold), so a swing/shot completes even as the unit moves
        // or kites away. Dead units never play attack frames.
        const playing = unit.state !== "dead"
            && (unit.state === "attacking" || unit.animHold > 0)
            && sheet && sheet.img
            && sheet.img.complete && sheet.img.naturalWidth > 0;
        let src = img, sx = 0, sy = 0, sw = img.naturalWidth, sh = img.naturalHeight;
        if (playing) {
            const m = sheet.meta;
            const phase = parseInt(String(unit.id).split("-")[1], 10) || 0;
            const frame = (Math.floor((sim.battleTime * 1000) / m.dur) + phase) % m.frames;
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
        // ---------------------------------------------------------------
        // THE ONE DELIBERATE WRITE TO ENGINE-OWNED STATE IN THIS MODULE.
        // Everywhere else the renderer only reads. The two `unit.faceRight =`
        // assignments below are inherited byte-faithfully from legacy
        // BattleUnit.render (simulate.js:2230/2232) and stay here on purpose:
        //   * faceRight is render-only state. The engine initializes it once
        //     (engine/battle_unit.js:218, faceRight = team === 1) and never
        //     reads it again — no update/attack/movement path touches it — and
        //     Simulation.stateHash() does not hash it, so this write cannot
        //     affect determinism, parity or the golden baseline.
        //   * Facing is recomputed per RENDER FRAME, not per tick. Moving it
        //     into the engine's update() would re-time it to the tick rate and
        //     change the visual cadence of turning, so it is not relocated.
        // ---------------------------------------------------------------
        // Face toward what the unit is fighting: its target if engaged (so it
        // faces where it attacks even after maneuvering past the enemy), else
        // its movement direction. A deadzone avoids flicker on near-vertical
        // alignment (target dx is in px; vx is normalized ~-1..1).
        if (unit.target && unit.target.state !== "dead") {
            const fdx = unit.target.x - unit.x;
            if (Math.abs(fdx) > 4) unit.faceRight = fdx > 0;
        } else if (Math.abs(unit.vx) > 0.05) {
            unit.faceRight = unit.vx > 0;
        }
        ctx.save();
        if (atk > 0) {
            ctx.shadowColor = `rgba(255, 209, 74, ${0.95 * atk})`;
            ctx.shadowBlur = 22 * atk;
        }
        if (unit.faceRight) {
            // Sprites are authored facing left, so mirror horizontally about
            // the unit's center to make it face right.
            ctx.translate(unit.x, 0);
            ctx.scale(-1, 1);
            ctx.drawImage(src, sx, sy, sw, sh, -dw / 2, unit.y - dh / 2, dw, dh);
        } else {
            ctx.drawImage(src, sx, sy, sw, sh, unit.x - dw / 2, unit.y - dh / 2, dw, dh);
        }
        ctx.restore();
    } else {
        // Legacy ring + circular portrait (fallback units / image not loaded yet)
        ctx.beginPath();
        ctx.arc(unit.x, unit.y, unit.radius + 2, 0, Math.PI * 2);
        let ringColor = unit.team === 1 ? "#3498db" : "#e74c3c";
        if (unit.attackAnimTimer > 0) ringColor = "#ffffff";
        else if (unit.state === "kiting")
            ringColor = unit.team === 1 ? "#9b59b6" : "#1abc9c";
        ctx.fillStyle = ringColor;
        ctx.fill();

        if (imgReady) {
            ctx.save();
            ctx.beginPath();
            ctx.arc(unit.x, unit.y, unit.radius, 0, Math.PI * 2);
            ctx.clip();
            ctx.drawImage(
                img,
                unit.x - unit.radius,
                unit.y - unit.radius,
                unit.radius * 2,
                unit.radius * 2,
            );
            ctx.restore();
        } else {
            ctx.beginPath();
            ctx.arc(unit.x, unit.y, unit.radius, 0, Math.PI * 2);
            ctx.fillStyle = unit.team === 1 ? "#2980b9" : "#c0392b";
            ctx.fill();
        }
    }

    ctx.globalAlpha = 1.0;

    // HP bar
    if (unit.state !== "dead") {
        const barWidth = unit.radius * 2;
        const barHeight = 4;
        const barX = unit.x - unit.radius;
        const barY = unit.y - unit.radius - 10;
        ctx.fillStyle = "rgba(0,0,0,0.45)";
        ctx.fillRect(barX, barY, barWidth, barHeight);
        const hpPercent = unit.currentHp / unit.maxHp;
        // Team-coloured bar (team 1 blue, team 2 red) so it's obvious whose
        // unit is whose at a glance; remaining HP is shown by the fill width.
        ctx.fillStyle =
            unit.team === 1 ? pal.team1 : pal.team2;
        ctx.fillRect(
            barX,
            barY,
            barWidth * hpPercent,
            barHeight,
        );
    }

    // Damage numbers
    for (const dn of unit.damageNumbers) {
        ctx.globalAlpha = dn.alpha;
        ctx.fillStyle = "#ff0";
        ctx.font = "bold 13px Alegreya Sans, Arial";
        ctx.textAlign = "center";
        ctx.fillText(`-${dn.value}`, dn.x, dn.y);
    }
    ctx.globalAlpha = 1.0;
}

// ===== BATTLEFIELD CHROME =====

function drawGrid(ctx, w, h) {
    ctx.strokeStyle = CANVAS_PAL.grid;
    ctx.lineWidth = 1;
    for (let x = 0; x <= w; x += 50) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
    }
    for (let y = 0; y <= h; y += 50) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
    }
}

function drawWinner(ctx, sim, labels, w, h) {
    ctx.fillStyle = "rgba(0,0,0,0.7)";
    ctx.fillRect(0, 0, w, h);
    let text, subtext, color;
    if (sim.winner === 1) {
        const civ = labels.team1Civ || "Team 1";
        const unit = labels.team1Unit || "";
        text = `${civ} ${unit}`;
        subtext = "Victory!";
        color = CANVAS_PAL.team1;
    } else if (sim.winner === 2) {
        const civ = labels.team2Civ || "Team 2";
        const unit = labels.team2Unit || "";
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
        w / 2,
        h / 2 - 10,
    );
    if (subtext) {
        ctx.fillStyle = CANVAS_PAL.gold;
        ctx.font = "bold 22px Cinzel, serif";
        ctx.fillText(
            subtext,
            w / 2,
            h / 2 + 22,
        );
    }
    ctx.fillStyle = "#ece1cd";
    ctx.font = "16px 'Source Sans 3', sans-serif";
    ctx.fillText(
        `Battle time: ${sim.battleTime.toFixed(1)}s`,
        w / 2,
        h / 2 + 50,
    );
}

// ===== RENDERER =====

export class SimRenderer {
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
        // Per-team sprite assets: { img, isSprite, sheet }. Registered by the
        // host via setTeamAssets(); the draw path never reads them off a unit.
        this.assets = { 1: NO_ASSETS, 2: NO_ASSETS };
        // Winner-banner strings (page selection data, not engine state).
        this.labels = NO_LABELS;
        // Last sim handed to render(), so a resize can repaint the current frame.
        this._sim = null;
        this.resizeBackingStore();
        // Re-fit the backing store whenever the canvas's displayed size changes
        // (window resize, the pick->battle arena transition, mobile stacking) and
        // repaint so a static (paused / pre-battle) frame stays sharp too.
        try {
            new ResizeObserver(() => {
                this.resizeBackingStore();
                this.repaint();
            }).observe(canvas);
        } catch (e) {
            /* ResizeObserver unsupported: keep the initial backing-store size */
        }
    }

    // Register the preloaded artwork for one team. Replaces legacy setupTeam's
    // per-unit stamping (simulate.js 2456-2458): `img` is the idle sprite or the
    // portrait fallback, `isSprite` says which of the two it is (a real square
    // sprite draws with no ring), `sheet` is the attack strip
    // ({ img, meta: { frames, fw, fh, dur, scale } }) or null.
    setTeamAssets(team, { img = null, isSprite = false, sheet = null } = {}) {
        this.assets[team] = { img, isSprite, sheet };
    }

    // Winner-banner text. Legacy drawWinner read the page-global `currentBattle`
    // (simulate.js 3348); these are the same four strings, pushed in instead.
    setLabels({ team1Civ = "", team1Unit = "", team2Civ = "", team2Unit = "" } = {}) {
        this.labels = { team1Civ, team1Unit, team2Civ, team2Unit };
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

    // Repaint the current frame without advancing anything (resize, theme change,
    // paused UI). Legacy's ResizeObserver called `this.render()` on the sim object
    // itself; the renderer no longer owns a sim, so it repaints the last one.
    repaint() {
        if (this._sim) this.render(this._sim);
        else this.renderEmpty();
    }

    // Set the transform and lay down the battlefield: the bg+grid half of the
    // legacy render body (simulate.js 2657-2665), shared by render() and
    // renderEmpty() so the verbatim copy exists exactly once.
    _paintBackdrop() {
        const ctx = this.ctx;
        // Draw in logical (W x H) space; the transform scales it up to the HiDPI
        // backing store. High-quality smoothing keeps the downscaled sprites sharp.
        ctx.setTransform(this.renderScaleX, 0, 0, this.renderScaleY, 0, 0);
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = "high";
        ctx.fillStyle = CANVAS_PAL.bg;
        ctx.fillRect(0, 0, this.W, this.H);
        drawGrid(ctx, this.W, this.H);
    }

    // Pre-battle frame: background + grid, no units — what the legacy render()
    // drew while both teams were still empty.
    renderEmpty() {
        this._paintBackdrop();
    }

    render(sim) {
        // The DPR transform is built from the renderer's logical space while the
        // battle lives in the engine's sim.W/sim.H. On the Battle Sim page both
        // are 900x600 and this is a no-op; a host that builds a different-sized
        // map gets the backing store refitted rather than a mis-scaled field.
        if (sim.W !== this.W || sim.H !== this.H) {
            this.W = sim.W;
            this.H = sim.H;
            this.resizeBackingStore();
        }
        this._sim = sim;
        const ctx = this.ctx;
        this._paintBackdrop();

        const allUnits = [...sim.team1, ...sim.team2];
        const dead = allUnits.filter((u) => u.state === "dead");
        const alive = allUnits.filter((u) => u.state !== "dead");
        for (const unit of dead) drawUnit(ctx, unit, this.assets[unit.team] || NO_ASSETS, sim, CANVAS_PAL);
        for (const unit of alive) drawUnit(ctx, unit, this.assets[unit.team] || NO_ASSETS, sim, CANVAS_PAL);

        // Draw projectiles
        for (const p of sim.projectiles) drawProjectile(ctx, p);
        // Draw effects
        for (const e of sim.effects) drawEffect(ctx, e);

        if (sim.winner !== null) drawWinner(ctx, sim, this.labels, this.W, this.H);
    }
}

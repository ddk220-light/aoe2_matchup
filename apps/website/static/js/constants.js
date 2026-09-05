/* ============================================
   AoE2 Unit Analyzer — Shared Constants

   SINGLE source of truth for frontend constants:
   ENABLED_CIVS, NAME_TO_ICON, UNIQUE_BUILDING,
   ICON_BASE, CIV_EMBLEM_BASE. Loaded by base.html
   before the page scripts — do NOT re-declare
   these in templates or page JS (the old
   per-template copies are gone). The Python civ
   list is validated server-side against
   aoe2_reference.db; keep ENABLED_CIVS in sync
   when a civ is added (see
   docs/architecture/runbooks.md).
   ============================================ */

/* --- Icon URLs --- */
const ICON_BASE = "/static/img/units/";
const CIV_EMBLEM_BASE =
    "https://backend.cdn.aoe2companion.com/public/aoe2/de/civilizations/";

/* --- Enabled Civilizations --- */
const ENABLED_CIVS = window.SITE_CATALOG.civilizations;

/* --- Unit Icon Mapping (wiki infobox portraits) --- */
const NAME_TO_ICON = window.SITE_CATALOG.icon_names;

/* --- Unique Unit Building Overrides --- */
const UNIQUE_BUILDING = window.SITE_CATALOG.unique_buildings;

/* --- Icon Helpers --- */
function getIconUrl(name) {
    const id = NAME_TO_ICON[name];
    // The catalog `icons` map is keyed by icon id (the file stem), which also
    // de-dupes display names that share one icon (e.g. Ratha (Melee)/(Ranged)).
    const icons = (typeof window !== "undefined") ? window._ASSET_ICONS : null;
    if (id && icons && icons[id]) return icons[id];
    return id ? `${ICON_BASE}${id}.png` : "";
}

/* Attack-animation URL (animated WebP in the bucket) for a unit display name,
   or null. Populated only in bucket mode (anims live only in the bucket); used
   for hover-to-animate on table icons and hover cards. */
function animFor(name) {
    const anims = (typeof window !== "undefined") ? window._ASSET_ANIMS : null;
    return (anims && anims[name]) || null;
}

/* Attack sprite-sheet for a unit: {url, frames, fw, fh, dur} or null. Used by
   the battle-sim canvas to play the attack animation frame-by-frame (canvas
   can't auto-play a WebP). Present only in bucket mode. */
function sheetFor(name) {
    const sheets = (typeof window !== "undefined") ? window._ASSET_SHEETS : null;
    return (sheets && sheets[name]) || null;
}

/* Hover-to-animate. Any element with [data-anim-name] animates a target <img>
   on hover and reverts on leave. The target is the element's `.anim-slot` child
   (used by hover cards) or the element itself if it's an <img> (table icons).
   The WebP loads lazily on first hover; if the unit has no animation, nothing
   happens. One delegated listener covers every page. */
(function () {
    if (typeof document === "undefined") return;
    function targetImg(el) {
        const slot = el.querySelector && el.querySelector(".anim-slot");
        if (slot) return slot;
        return el.tagName === "IMG" ? el : null;
    }
    document.addEventListener("mouseover", function (e) {
        const el = e.target.closest && e.target.closest("[data-anim-name]");
        if (!el) return;
        const url = (typeof animFor === "function") && animFor(el.dataset.animName);
        if (!url) return;
        const img = targetImg(el);
        if (!img) return;
        if (img.dataset.staticSrc === undefined)
            img.dataset.staticSrc = img.getAttribute("src") || "";
        if (img.getAttribute("src") !== url) img.src = url;
    });
    document.addEventListener("mouseout", function (e) {
        const el = e.target.closest && e.target.closest("[data-anim-name]");
        if (!el || el.contains(e.relatedTarget)) return;
        const img = targetImg(el);
        if (img && img.dataset.staticSrc !== undefined) img.src = img.dataset.staticSrc;
    });
})();

/* Generated in-game idle sprite (transparent). Returns a sprite URL only for
   units with a square-enough sprite (UNIT_SPRITES, loaded from unit_sprites.js);
   everything else falls back to the portrait so the UI degrades cleanly.
   Always returns the RED sprite for both teams: the attack ANIMATIONS are
   red-only, so a blue idle sprite would visibly flip colour the moment a unit
   attacks. Teams are told apart by HP-bar colour instead. (The `team` param is
   kept for call-site compatibility but is intentionally unused; the blue
   `url_blue` variant is no longer rendered.) */
function spriteFor(name, team) {
    const map = (typeof window !== "undefined" && window._ASSET_SPRITES)
        || (typeof UNIT_SPRITES !== "undefined" ? UNIT_SPRITES : null);
    const s = map ? map[name] : null;
    if (s && s.url) {
        return s.url;
    }
    return getIconUrl(name);
}

// NOTE: hasSprite/spriteRatio read the static UNIT_SPRITES (not the catalog
// override). The committed UNIT_SPRITES must stay a superset of the PG catalog.
/* Does this unit have a usable sprite at all? Includes off-shape (borderline /
   extreme) sprites, not just square — only truly spriteless units (naval) miss.
   Call sites use this to switch layout (drop the circle/frame) when a real sprite
   shows; aspect is handled per-view with object-fit: contain + sane bounds. */
function hasSprite(name) {
    const s = (typeof UNIT_SPRITES !== "undefined") ? UNIT_SPRITES[name] : null;
    return !!(s && s.url);
}

/* Sprite aspect ratio (longer:shorter side) or null — lets a view clamp the
   off-shape sprites (tall pikes, wide cavalry) so they never bleed their box. */
function spriteRatio(name) {
    const s = (typeof UNIT_SPRITES !== "undefined") ? UNIT_SPRITES[name] : null;
    return s && s.ratio ? s.ratio : null;
}

/* --- Building Config --- */
const CLASS_TO_BUILDING = {
    Infantry: "Barracks",
    Archer: "Archery Range",
    "Hand Cannoneer": "Archery Range",
    "Cavalry Archer": "Archery Range",
    Cavalry: "Stable",
    "Siege Weapon": "Siege Workshop",
    Ballista: "Siege Workshop",
    "Unpacked Siege Unit": "Castle",
};
const BUILDING_ORDER = [
    "Barracks", "Archery Range", "Stable", "Castle", "Siege Workshop",
];
const BUILDING_ICONS = {
    Barracks: 12, "Archery Range": 87, Stable: 101,
    "Siege Workshop": 49, Castle: 82,
};

/* --- HTML Escaping ---
   Escape a string so it is safe to interpolate into an innerHTML template
   literal. For attributes, make sure the attribute is quoted — this escaping
   turns `&`, `<`, `>`, `"` into character entities via DOM textContent. */
function escapeHtml(str) {
    if (str == null) return "";
    const div = document.createElement("div");
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
}

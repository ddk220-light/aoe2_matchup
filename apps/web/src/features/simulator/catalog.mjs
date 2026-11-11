export const catalog = JSON.parse(document.getElementById('simulator-config').textContent);
export const ENABLED_CIVS = catalog.civilizations;
export const NAME_TO_ICON = catalog.icon_names;
export const UNIQUE_BUILDING = catalog.unique_buildings;
export const CIV_EMBLEM_BASE = 'https://backend.cdn.aoe2companion.com/public/aoe2/de/civilizations/';
export const ENGINE_ROOT = catalog.engine_worker_url.replace(/\/worker\.js$/, '');
export const iconUrl = id => catalog.icons[id] || '';
export const hasSprite = name => !!catalog.sprites[name]?.url;
// Team 1 (Team A) uses the blue player-colour render when one exists; every
// other team, and any caller that names no team, gets the red default.
export const spriteFor = (name, team) => (team === 1 && catalog.sprites[name]?.url_blue)
  || catalog.sprites[name]?.url || iconUrl(NAME_TO_ICON[name]);
export const sheetFor = name => catalog.sheets[name] || null;
export const escapeHtml = value => String(value ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

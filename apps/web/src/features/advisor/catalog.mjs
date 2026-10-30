import {requestJson} from './request.mjs';
export const config=JSON.parse(document.getElementById('advisor-config').textContent);
export const CIVS=config.civilizations;
export const CIV_EMBLEM_BASE='https://backend.cdn.aoe2companion.com/public/aoe2/de/civilizations/';
export const getIconUrl=name=>config.icons[config.icon_names[name]]||'';
export const escapeHtml=value=>String(value??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
export const apiGet=(url,signal)=>requestJson(url,{signal});

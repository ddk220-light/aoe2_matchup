import {buildAdvisorRecommendations} from './advisor-model.mjs';

/** Shared advisor UI: saved first-pass evidence, never on-demand simulations. */
export function mountAdvisor(config) {
    const units = new Map(config.units.map(unit => [unit.id, unit]));
    const names = config.civilizations;
    const grid = document.getElementById('civ-grid');
    const results = document.getElementById('results');
    const top = document.getElementById('top-units');
    const slots = {left: document.getElementById('slot-left'), right: document.getElementById('slot-right')};
    let left = null, right = null, active = 'left', sequence = 0;
    const cache = new Map();
    const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const icon = unit => config.icons?.[config.icon_names?.[unit.name]] || unit.icon;
    const image = (unit, cls = 'ma-unit-icon') => `<img class="${cls}" src="${esc(icon(unit))}" alt="${esc(unit.name)}" loading="lazy" width="44" height="44">`;
    const costs = unit => Object.entries(unit.costs).filter(([,v]) => v > 0).map(([key,v]) => `<span class="ma-cost ma-cost-${key}"><span aria-hidden="true">${{food:'●',wood:'◆',gold:'●'}[key]}</span> ${Number(v.toFixed(1))}<span class="ma-cost-name"> ${key}</span></span>`).join('');
    function choose(name) {
        if (name === left) { left = null; active = 'left'; }
        else if (name === right) { right = null; active = 'right'; }
        else if (active === 'left') { left = name; if (!right) active = 'right'; }
        else { right = name; if (!left) active = 'left'; }
        renderPicker();
        if (left && right) loadComparison();
        else {
            sequence += 1; top.innerHTML = '';
            results.innerHTML = '<div class="ma-empty">Choose your civilization and an opponent to explore their matchups.</div>';
            document.getElementById('ma-detail').hidden = true;
        }
    }
    for (const name of names) {
        const button = [...grid.children].find(button => button.dataset.civ === name) || document.createElement('button');
        button.type = 'button'; button.className = 'ma-civ-card'; button.dataset.civ = name;
        button.innerHTML = `<img class="ma-civ-emblem" src="${esc(config.emblems[name])}" alt="" loading="lazy" width="30" height="30"><span class="ma-civ-card-name">${esc(name)}</span>`;
        button.addEventListener('click', () => choose(name)); grid.appendChild(button);
    }
    function renderPicker() {
        for (const side of ['left','right']) {
            const name = side === 'left' ? left : right;
            const button = slots[side];
            button.classList.toggle('active', side === active); button.classList.toggle('filled', Boolean(name));
            button.setAttribute('aria-pressed', String(side === active));
            button.innerHTML = `<span class="ma-slot-eyebrow">${side === 'left' ? 'Your civilization' : 'Opponent'}</span>${name ? `<img class="ma-slot-emblem" src="${esc(config.emblems[name])}" alt="" width="48" height="48"><span class="ma-slot-name">${esc(name)}</span>` : '<span class="ma-slot-placeholder">Choose a civilization</span>'}`;
        }
        for (const button of grid.children) {
            button.classList.toggle('selected-left', button.dataset.civ === left);
            button.classList.toggle('selected-right', button.dataset.civ === right);
            button.setAttribute('aria-pressed', String(button.dataset.civ === left || button.dataset.civ === right));
        }
    }
    for (const [side, button] of Object.entries(slots)) button.addEventListener('click', () => { active = side; renderPicker(); });
    async function loadComparison() {
        const ticket = ++sequence, selectedLeft = left, selectedRight = right;
        results.innerHTML = '<div class="ma-loading" role="status">Loading saved matchups…</div>'; top.innerHTML = '';
        document.getElementById('ma-detail').hidden = true;
        try {
            if (!cache.has(selectedLeft)) {
                const url = config.files?.[selectedLeft.toLowerCase()]?.url || `/api/advisor-matchups/${encodeURIComponent(selectedLeft)}`;
                cache.set(selectedLeft, fetch(url).then(async response => {
                    if (!response.ok) throw new Error('Saved comparison unavailable'); return response.json();
                }).catch(error => { cache.delete(selectedLeft); throw error; }));
            }
            const data = await cache.get(selectedLeft);
            if (ticket !== sequence) return;
            const rows = data.opponents[selectedRight];
            if (!rows?.length) throw new Error('No saved comparison');
            renderComparison(rows);
        } catch (error) {
            if (ticket === sequence) results.innerHTML = '<div class="ma-loading" role="alert">Could not load this comparison. Choose the civilizations again to retry.</div>';
        }
    }
    const scoreText = value => value.toLocaleString(undefined, {maximumFractionDigits: 2});
    function matchLine(card, rows, label, cls, named = false) {
        if (!rows.length) return;
        const line = document.createElement('div'); line.className = `ma-match-line ma-line-${cls}`;
        const heading = document.createElement('span'); heading.className = 'ma-match-label'; heading.textContent = label; line.appendChild(heading);
        const icons = document.createElement('div'); icons.className = 'ma-opponents';
        for (const row of rows) {
            const other = units.get(row[1]);
            const button = document.createElement('button'); button.type = 'button';
            button.className = `ma-match ma-match-${cls}${named ? ' ma-match-named' : ''}`;
            button.dataset.opponent = String(other.id);
            button.title = `${other.name}: ${label.toLowerCase()} · ${row[4]} vs ${row[5]} units`;
            button.setAttribute('aria-label', button.title);
            button.innerHTML = image(other, 'ma-opponent-icon') + (named ? `<span>${esc(other.name)}</span>` : '');
            button.addEventListener('click', () => showDetail(row)); icons.appendChild(button);
        }
        line.appendChild(icons); card.appendChild(line);
    }
    function unitHeading(entry, metric, caption, featured = false) {
        return `<div class="ma-unit-heading">${image(entry.unit)}<div><${featured ? 'h3' : 'h4'}>${esc(entry.unit.name)}</${featured ? 'h3' : 'h4'}><div class="ma-costs">${costs(entry.unit)}</div></div><div class="ma-coverage"${caption === 'value score' ? ' title="Sum of enemy weight × (1 + its weighted wins) for every enemy this unit counters. Gold = 1; no gold = ½."' : ''}><strong>${metric}</strong><small>${caption}</small></div></div>`;
    }
    function recommendation(plan, role) {
        const entry = role === 'main' ? plan.main : plan.sidekick;
        const card = document.createElement('article'); card.className = `ma-unit-card ma-recommendation ma-${role}`; card.dataset.role = role;
        if (!entry) { card.innerHTML = '<span class="ma-kicker">Trash sidekick</span><p>No no-gold unit is available.</p>'; return card; }
        card.dataset.unit = entry.unit.key;
        const heading = role === 'main' ? 'Main unit' : !entry.wins.length && !entry.holdsClose.length ? 'Trash fallback' : 'Trash sidekick';
        const metric = role === 'main' ? scoreText(entry.score) : (plan.main.losses.length ? `${entry.covers.length}<span>/${plan.main.losses.length}</span>` : '—');
        const caption = role === 'main' ? 'value score' : plan.main.losses.length ? 'threats covered' : 'no main losses';
        card.innerHTML = `<span class="ma-role">${heading}</span>${unitHeading(entry, metric, caption, true)}`;
        if (role === 'main') {
            card.insertAdjacentHTML('beforeend', `<p class="ma-recommendation-note">Counters ${entry.wins.length} of ${entry.matches.length} enemy unit options, prioritizing their biggest threats.</p>`);
            matchLine(card, entry.wins, 'Counters', 'win', true);
        } else {
            let note;
            if (entry.covers.length) note = `Pair with ${plan.main.unit.name} to counter ${entry.covers.length} of the ${plan.main.losses.length} enemy units that beat it, without spending gold.`;
            else if (!entry.wins.length && !entry.holdsClose.length) note = `${entry.unit.name} has no winning matchups here and adds no winning coverage to ${plan.main.unit.name}.`;
            else if (!plan.main.losses.length) note = `${plan.main.unit.name} has no losing matchups here. ${entry.unit.name} is a no-gold alternative against the units below.`;
            else if (entry.holdsClose.length) note = `No trash unit beats these counters to ${plan.main.unit.name}. ${entry.unit.name} keeps ${entry.holdsClose.length} of them close.`;
            else note = `No trash unit beats the counters to ${plan.main.unit.name}. ${entry.wins.length ? `${entry.unit.name} offers other no-gold counter options below.` : `${entry.unit.name} also has no winning matchups here.`}`;
            card.insertAdjacentHTML('beforeend', `<p class="ma-recommendation-note">${esc(note)}</p>`);
            matchLine(card, entry.covers, 'Protects main from', 'win', true);
            const protectedIds = new Set(entry.covers.map(row => row[1]));
            matchLine(card, entry.wins.filter(row => !protectedIds.has(row[1])), 'Other counters', 'win', true);
        }
        matchLine(card, entry.losses, 'Loses to', 'loss', true);
        matchLine(card, entry.close, 'Close / equal', 'close', true);
        return card;
    }
    function fillPlan(element, plan, civilization, side) {
        element.innerHTML = `<header class="ma-plan-header"><span class="ma-kicker">${side === 'left' ? 'Your composition' : "Opponent's composition"}</span><h2>${esc(civilization)}</h2></header>`;
        element.appendChild(recommendation(plan, 'main'));
        element.appendChild(recommendation(plan, 'sidekick'));
        if (plan.uncovered.length) {
            const gap = document.createElement('div'); gap.className = 'ma-pair-gap';
            gap.innerHTML = '<p>Remaining threats</p>';
            matchLine(gap, plan.uncovered, 'Not covered', 'loss', true);
            element.appendChild(gap);
        }
    }
    function renderComparison(rows) {
        const plans = buildAdvisorRecommendations(rows, units);
        top.innerHTML = `<div class="ma-result-banner"><div><strong>${rows.length} unit matchups</strong><span>Fully upgraded land units · cost-adjusted armies, up to 27 units</span><p class="ma-score-note">Counters to dangerous enemy units rank higher. Gold units weigh 1; no-gold units weigh ½. Sidekicks target the main unit’s weaknesses.</p></div></div><div class="ma-compositions"><section class="ma-plan ma-plan-left" id="ma-left-plan"></section><section class="ma-plan ma-plan-right" id="ma-right-plan"></section></div>`;
        fillPlan(document.getElementById('ma-left-plan'), plans.left, left, 'left');
        fillPlan(document.getElementById('ma-right-plan'), plans.right, right, 'right');
        results.innerHTML = `<div class="ma-legend"><span><i class="ma-dot ma-dot-win"></i>Favorable</span><span><i class="ma-dot ma-dot-loss"></i>Difficult</span><span><i class="ma-dot ma-dot-close"></i>Close / equal</span></div><div class="ma-team-columns"><section class="ma-team ma-team-left"><header><span>Other candidates</span><h2>${esc(left)}</h2></header><div id="ma-left-units"></div></section><section class="ma-team ma-team-right"><header><span>Other candidates</span><h2>${esc(right)}</h2></header><div id="ma-right-units"></div></section></div>`;
        fillAlternatives(document.getElementById('ma-left-units'), plans.left.alternatives);
        fillAlternatives(document.getElementById('ma-right-units'), plans.right.alternatives);
    }
    function fillAlternatives(element, entries) {
        if (!entries.length) { element.innerHTML = '<p class="ma-candidate-note">No other unit has a favorable matchup here.</p>'; return; }
        const section = document.createElement('div'); section.className = 'ma-unit-group';
        section.innerHTML = `<h3>Top ${entries.length} alternatives</h3>`;
        for (const entry of entries) {
            const card = document.createElement('article'); card.className = 'ma-unit-card'; card.dataset.unit = entry.unit.key;
            card.innerHTML = unitHeading(entry, scoreText(entry.score), 'value score');
            matchLine(card, entry.wins, 'Counters', 'win');
            matchLine(card, entry.losses, 'Loses to', 'loss');
            matchLine(card, entry.close, 'Close / equal', 'close');
            section.appendChild(card);
        }
        element.appendChild(section);
    }
    function showDetail(row) {
        const a = units.get(row[0]), b = units.get(row[1]), detail = document.getElementById('ma-detail');
        const result = row[2] === 'a_win' ? `${a.name} is favored` : row[2] === 'b_win' ? `${b.name} is favored` : row[2] === 'equivalent' ? 'Equivalent combat profiles' : 'Close matchup';
        detail.innerHTML = `<button type="button" class="ma-detail-close" aria-label="Close matchup details">×</button><div class="ma-detail-armies">${image(a)}<span>${row[4]} ${esc(a.name)}<small>${esc(a.civilization)}</small></span><b>vs</b>${image(b)}<span>${row[5]} ${esc(b.name)}<small>${esc(b.civilization)}</small></span></div><strong>${esc(result)}</strong><p>Fully upgraded land units · cost-adjusted armies.</p>`;
        detail.hidden = false; detail.querySelector('button').addEventListener('click', () => { detail.hidden = true; });
    }
    renderPicker();
}

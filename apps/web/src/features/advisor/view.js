import {buildAdvisorRecommendations} from './model.mjs';

/** Advisor UI: saved first-pass evidence, never on-demand simulations. */
export function mountAdvisor(config) {
    const units = new Map(config.units.map(unit => [unit.id, unit]));
    const names = config.civilizations;
    const grid = document.getElementById('civ-grid');
    const results = document.getElementById('results');
    const top = document.getElementById('top-units');
    const slots = {left: document.getElementById('slot-left'), right: document.getElementById('slot-right')};
    let left = null, right = null, active = 'left', sequence = 0, choosing = true;
    const root = grid.closest('.ma-advisor'), filter = document.getElementById('civ-filter');
    const EMPTY = '<p class="ma-empty">Pick both civilizations above to see what each side should build.</p>';
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
        choosing = !(left && right);
        if (filter && filter.value) { filter.value = ''; applyFilter(); }
        renderPicker();
        if (left && right) loadComparison();
        else {
            sequence += 1; top.innerHTML = '';
            results.innerHTML = EMPTY;
            document.getElementById('ma-detail').hidden = true;
        }
    }
    for (const name of names) {
        const button = [...grid.children].find(button => button.dataset.civ === name) || document.createElement('button');
        button.type = 'button'; button.className = 'ma-civ-card civ-tile'; button.dataset.civ = name;
        button.innerHTML = `<img class="ma-civ-emblem" src="${esc(config.emblems[name])}" alt="" loading="lazy" width="36" height="36"><span class="ma-civ-card-name">${esc(name)}</span>`;
        button.addEventListener('click', () => choose(name)); grid.appendChild(button);
    }
    function renderPicker() {
        for (const side of ['left','right']) {
            const name = side === 'left' ? left : right;
            const button = slots[side];
            button.classList.toggle('active', side === active); button.classList.toggle('filled', Boolean(name));
            button.setAttribute('aria-pressed', String(side === active));
            button.classList.toggle('active', choosing && side === active);
            button.innerHTML = `${name ? `<img class="ma-slot-emblem" src="${esc(config.emblems[name])}" alt="" width="44" height="44">` : '<span class="ma-slot-emblem ma-slot-blank" aria-hidden="true"></span>'}<span class="ma-slot-text"><span class="ma-slot-eyebrow">${side === 'left' ? 'You' : 'Opponent'}</span><span class="${name ? 'ma-slot-name' : 'ma-slot-placeholder'}">${name ? esc(name) : 'Choose a civilization'}</span></span>${name && !choosing ? '<span class="ma-slot-change">Change</span>' : ''}`;
        }
        root.classList.toggle('is-choosing', choosing);
        const prompt = document.getElementById('civ-prompt');
        if (prompt) prompt.textContent = active === 'left' ? 'Choose your civilization' : "Choose your opponent's civilization";
        for (const button of grid.children) {
            button.classList.toggle('selected-left', button.dataset.civ === left);
            button.classList.toggle('selected-right', button.dataset.civ === right);
            button.setAttribute('aria-pressed', String(button.dataset.civ === left || button.dataset.civ === right));
        }
    }
    for (const [side, button] of Object.entries(slots)) button.addEventListener('click', () => {
        choosing = !(choosing && active === side && left && right); active = side; renderPicker();
        if (choosing && filter && matchMedia('(hover: hover)').matches) filter.focus();
    });
    function applyFilter() {
        const query = filter.value.trim().toLowerCase(); let shown = 0;
        for (const button of grid.children) { button.hidden = !button.dataset.civ.toLowerCase().includes(query); if (!button.hidden) shown += 1; }
        document.getElementById('civ-none').hidden = shown > 0;
    }
    if (filter) {
        filter.addEventListener('input', applyFilter);
        filter.addEventListener('keydown', event => {
            if (event.key !== 'Enter') return;
            const first = [...grid.children].find(button => !button.hidden);
            if (first) { event.preventDefault(); choose(first.dataset.civ); }
        });
    }
    async function loadComparison() {
        const ticket = ++sequence, selectedLeft = left, selectedRight = right;
        results.innerHTML = '<p class="ma-loading" role="status">Loading matchups…</p>'; top.innerHTML = '';
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
            const picker = root.querySelector('.ma-picker').getBoundingClientRect();
            if (picker.top < 0 || picker.top > innerHeight * 0.5) scrollTo({top: 0});
            
        } catch (error) {
            if (ticket === sequence) results.innerHTML = '<p class="ma-loading" role="alert">Could not load this comparison. Choose the civilizations again to retry.</p>';
        }
    }
    const scoreText = value => value.toLocaleString(undefined, {maximumFractionDigits: 2});
    function matchLine(card, rows, label, cls) {
        if (!rows.length) return;
        const line = document.createElement('div'); line.className = `ma-match-line ma-line-${cls}`;
        const heading = document.createElement('span'); heading.className = 'ma-match-label'; heading.textContent = label; line.appendChild(heading);
        const icons = document.createElement('div'); icons.className = 'ma-opponents';
        for (const row of rows) {
            const other = units.get(row[1]);
            const button = document.createElement('button'); button.type = 'button';
            button.className = `ma-match ma-match-${cls}`;
            button.dataset.opponent = String(other.id);
            button.title = `${other.name}: ${label.toLowerCase()} · ${row[4]} vs ${row[5]} units`;
            button.setAttribute('aria-label', button.title);
            button.innerHTML = image(other, 'ma-opponent-icon');
            button.addEventListener('click', () => showDetail(row)); icons.appendChild(button);
        }
        line.appendChild(icons); card.appendChild(line);
    }
    function unitHeading(entry, featured = false) {
        return `<div class="ma-unit-heading">${image(entry.unit)}<div><${featured ? 'h3' : 'h4'}>${esc(entry.unit.name)}</${featured ? 'h3' : 'h4'}><div class="ma-costs">${costs(entry.unit)}</div></div><div class="ma-coverage" title="How much of the opposing army this unit beats, weighted by how dangerous each opposing unit is"><strong>${scoreText(entry.score)}</strong><small>coverage</small></div></div>`;
    }
    function mainCard(plan) {
        const entry = plan.main, card = document.createElement('article');
        card.className = 'ma-unit-card ma-recommendation ma-main'; card.dataset.role = 'main'; card.dataset.unit = entry.unit.key;
        card.innerHTML = `<span class="ma-role">Main unit</span>${unitHeading(entry, true)}`;
        matchLine(card, entry.wins, 'Beats', 'win');
        matchLine(card, entry.losses, 'Loses to', 'loss');
        matchLine(card, entry.close, 'Close', 'close');
        return card;
    }
    function sidekickCard(plan) {
        const entry = plan.sidekick, card = document.createElement('article');
        card.className = 'ma-sidekick'; card.dataset.role = 'sidekick';
        if (!entry) { card.innerHTML = '<span class="ma-role">Support, no gold</span><span class="ma-short-note">No unit without a gold cost helps here</span>'; return card; }
        card.dataset.unit = entry.unit.key;
        card.innerHTML = `<div class="ma-support-heading"><span class="ma-role">Support, no gold</span><div class="ma-support-unit">${image(entry.unit)}<h3>${esc(entry.unit.name)}</h3></div></div>`;
        const job = document.createElement('div'); job.className = 'ma-support-job';
        if (entry.covers.length) matchLine(job, entry.covers, 'Covers', 'win');
        else if (entry.holdsClose.length) matchLine(job, entry.holdsClose, 'Holds', 'close');
        else job.innerHTML = `<span class="ma-short-note">${plan.main.losses.length ? 'Does not cover the main unit\u2019s losses' : 'Main unit has no losses to cover'}</span>`;
        card.appendChild(job);
        return card;
    }
    function additionalCounters(plan) {
        const section = document.createElement('section'); section.className = 'ma-additions'; section.dataset.role = 'additions';
        const heading = document.createElement('span'); heading.className = 'ma-role'; heading.textContent = 'Add against the rest'; section.appendChild(heading);
        const groups = document.createElement('div'); groups.className = 'ma-counter-groups';
        for (const addition of plan.additions) {
            const group = document.createElement('div'); group.className = 'ma-counter-group'; group.dataset.counter = String(addition.unit.id);
            group.innerHTML = `<img class="ma-unit-icon" src="${esc(icon(addition.unit))}" alt="${esc(addition.unit.name)}" title="Add ${esc(addition.unit.name)}" loading="lazy" width="32" height="32"><span class="ma-counter-arrow" aria-hidden="true">→</span>`;
            const targets = document.createElement('div'); targets.className = 'ma-counter-targets';
            matchLine(targets, addition.covers, 'Counters', 'win');
            group.appendChild(targets); groups.appendChild(group);
        }
        section.appendChild(groups);
        if (plan.unanswered.length) matchLine(section, plan.unanswered, 'No answer', 'loss');
        if (!plan.uncovered.length) section.insertAdjacentHTML('beforeend', '<span class="ma-short-note">Nothing left uncovered</span>');
        return section;
    }
    function fillPlan(element, plan, civilization, side) {
        element.innerHTML = `<header class="ma-plan-header"><h2>${esc(civilization)}</h2><span class="ma-kicker">${side === 'left' ? 'What you should build' : 'What to expect'}</span></header>`;
        const body = document.createElement('div'); body.className = 'ma-plan-body';
        body.appendChild(mainCard(plan));
        body.appendChild(sidekickCard(plan));
        body.appendChild(additionalCounters(plan));
        element.appendChild(body);
    }
    function renderComparison(rows) {
        const plans = buildAdvisorRecommendations(rows, units);
        top.innerHTML = '<p class="ma-legend">Coverage is how much of the other side\u2019s army a unit beats. Icons are the opposing units; select one for army sizes.</p><div class="ma-compositions"><section class="ma-plan ma-plan-left" id="ma-left-plan"></section><section class="ma-plan ma-plan-right" id="ma-right-plan"></section></div>';
        fillPlan(document.getElementById('ma-left-plan'), plans.left, left, 'left');
        fillPlan(document.getElementById('ma-right-plan'), plans.right, right, 'right');
        results.innerHTML = `<div class="ma-team-columns"><section class="ma-team ma-team-left"><header><h2>Other ${esc(left)} options</h2></header><div id="ma-left-units"></div></section><section class="ma-team ma-team-right"><header><h2>Other ${esc(right)} options</h2></header><div id="ma-right-units"></div></section></div>`;
        fillAlternatives(document.getElementById('ma-left-units'), plans.left.alternatives);
        fillAlternatives(document.getElementById('ma-right-units'), plans.right.alternatives);
    }
    function fillAlternatives(element, entries) {
        if (!entries.length) { element.innerHTML = '<p class="ma-short-note">No other winning options</p>'; return; }
        for (const entry of entries) {
            const card = document.createElement('article'); card.className = 'ma-unit-card'; card.dataset.unit = entry.unit.key;
            card.innerHTML = unitHeading(entry);
            matchLine(card, entry.wins, 'Beats', 'win');
            matchLine(card, entry.losses, 'Loses to', 'loss');
            matchLine(card, entry.close, 'Close', 'close');
            element.appendChild(card);
        }
    }
    function showDetail(row) {
        const a = units.get(row[0]), b = units.get(row[1]), detail = document.getElementById('ma-detail');
        const result = row[2] === 'a_win' ? `${a.name} is favored` : row[2] === 'b_win' ? `${b.name} is favored` : row[2] === 'equivalent' ? 'Equivalent combat profiles' : 'Close matchup';
        detail.innerHTML = `<button type="button" class="ma-detail-close" aria-label="Close matchup details">×</button><div class="ma-detail-armies">${image(a)}<span>${row[4]} ${esc(a.name)}<small>${esc(a.civilization)}</small></span><b>vs</b>${image(b)}<span>${row[5]} ${esc(b.name)}<small>${esc(b.civilization)}</small></span></div><strong>${esc(result)}</strong><p>Fully upgraded units, army sizes adjusted so both sides cost the same.</p>`;
        detail.hidden = false; detail.querySelector('button').addEventListener('click', () => { detail.hidden = true; });
    }
    renderPicker();
}

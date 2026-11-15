import {buildAdvisorRecommendations} from './model.mjs';

/** Advisor UI: saved matchup evidence, never on-demand simulations. */
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
    /** team 'a' (left civ) = blue render, 'b' (right civ) = red render; portrait icon otherwise. */
    const image = (unit, cls = 'ma-unit-icon', team) => `<img class="${cls}${team && config.team_icons?.[unit.name] ? ' ma-team-icon' : ''}" src="${esc((team && config.team_icons?.[unit.name]?.[team]) || icon(unit))}" alt="${esc(unit.name)}" loading="lazy" width="44" height="44">`;
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
    /** Weighted matchup number (value x opponent multiplier) and its underline shade. */
    const fmt = x => (x > 0 ? '+' : x < 0 ? '\u2212' : '') + Math.abs(x).toFixed(2);
    const shade = c => c >= 0.5 ? 'win-strong' : c > 0 ? 'win' : c === 0 ? 'close' : c > -0.5 ? 'loss-light' : 'loss';
    function matchIcon(entry, opp, teams, number = entry.vs.get(opp).contribution) {
        const {row} = entry.vs.get(opp), other = units.get(opp);
        const button = document.createElement('button'); button.type = 'button';
        button.className = `ma-match ma-match-${shade(number)}`;
        button.dataset.opponent = String(opp);
        button.title = `${other.name}: ${fmt(number)} \u00b7 ${row[4]} vs ${row[5]} units`;
        button.setAttribute('aria-label', button.title);
        button.innerHTML = `${image(other, 'ma-opponent-icon', teams.opp)}<span class="ma-num">${fmt(number)}</span>`;
        button.addEventListener('click', () => showDetail(row, teams));
        return button;
    }
    function line(container, label, entry, opponents, teams, number) {
        if (!opponents.length) return;
        const el = document.createElement('div'); el.className = 'ma-match-line';
        const head = document.createElement('span'); head.className = 'ma-match-label';
        if (typeof label === 'string') head.textContent = label; else head.appendChild(label);
        const icons = document.createElement('div'); icons.className = 'ma-opponents';
        for (const opp of opponents) icons.appendChild(matchIcon(entry, opp, teams, number?.(opp)));
        el.append(head, icons); container.appendChild(el);
    }
    /** Beats: weakest win first (where it struggles). Loses to: worst loss first. Support: Beats only. */
    function unitCard(entry, role, teams) {
        const card = document.createElement('article');
        const kind = role === 'Main unit' ? 'main' : 'support';
        card.className = `ma-unit-card ma-recommendation ma-${kind}`; card.dataset.role = kind; card.dataset.unit = entry.unit.key;
        card.innerHTML = `<span class="ma-role">${role}</span><div class="ma-unit-heading">${image(entry.unit, 'ma-unit-icon', teams.own)}<div><h3>${esc(entry.unit.name)}</h3><div class="ma-costs">${costs(entry.unit)}</div></div></div>`;
        const opps = [...entry.vs.keys()], c = opp => entry.vs.get(opp).contribution, v = opp => entry.vs.get(opp).value;
        line(card, 'Beats', entry, opps.filter(o => v(o) > 0).sort((a, b) => c(a) - c(b) || a - b), teams);
        if (kind === 'main') {
            line(card, 'Loses to', entry, opps.filter(o => v(o) < 0).sort((a, b) => c(a) - c(b) || a - b), teams);
            line(card, 'Close', entry, opps.filter(o => v(o) === 0).sort((a, b) => a - b), teams);
        }
        return card;
    }
    function extras(plan, teams) {
        if (!plan.additions.length && !plan.unanswered.length) return null;
        const section = document.createElement('section'); section.className = 'ma-extras'; section.dataset.role = 'additions';
        for (const {entry, covers} of plan.additions) {
            const label = document.createElement('span'); label.className = 'ma-add';
            label.innerHTML = `Add ${image(entry.unit, 'ma-add-icon', teams.own)}<span class="ma-add-name">${esc(entry.unit.name)}</span>`;
            line(section, label, entry, covers, teams);
        }
        const best = opp => Math.max(...[plan.main, plan.support].filter(Boolean).map(e => e.vs.get(opp).contribution));
        line(section, 'No better counter', plan.main, plan.unanswered, teams, best);
        return section;
    }
    function fillPlan(element, plan, civilization, side) {
        const teams = side === 'left' ? {own: 'a', opp: 'b'} : {own: 'b', opp: 'a'};
        element.innerHTML = `<header class="ma-plan-header"><h2>${esc(civilization)}</h2><span class="ma-kicker">${side === 'left' ? 'What you should build' : 'What to expect'}</span></header>`;
        const body = document.createElement('div'); body.className = 'ma-plan-body';
        if (plan.main) body.appendChild(unitCard(plan.main, 'Main unit', teams));
        if (plan.support) body.appendChild(unitCard(plan.support, 'Support', teams));
        const more = extras(plan, teams);
        if (more) body.appendChild(more);
        element.appendChild(body);
    }
    function renderComparison(rows) {
        const plans = buildAdvisorRecommendations(rows, units);
        top.innerHTML = '<div class="ma-compositions"><section class="ma-plan ma-plan-left" id="ma-left-plan"></section><section class="ma-plan ma-plan-right" id="ma-right-plan"></section></div>';
        fillPlan(document.getElementById('ma-left-plan'), plans.left, left, 'left');
        fillPlan(document.getElementById('ma-right-plan'), plans.right, right, 'right');
        results.innerHTML = '';
    }
    function showDetail(row, teams = {own: 'a', opp: 'b'}) {
        const a = units.get(row[0]), b = units.get(row[1]), detail = document.getElementById('ma-detail');
        const result = row[2] === 'a_win' ? `${a.name} is favored` : row[2] === 'b_win' ? `${b.name} is favored` : row[2] === 'equivalent' ? 'Equivalent combat profiles' : 'Close matchup';
        detail.innerHTML = `<button type="button" class="ma-detail-close" aria-label="Close matchup details">×</button><div class="ma-detail-armies">${image(a, 'ma-unit-icon', teams.own)}<span>${row[4]} ${esc(a.name)}<small>${esc(a.civilization)}</small></span><b>vs</b>${image(b, 'ma-unit-icon', teams.opp)}<span>${row[5]} ${esc(b.name)}<small>${esc(b.civilization)}</small></span></div><strong>${esc(result)}</strong><p>Fully upgraded units; army sizes scaled by unit cost.</p>`;
        detail.hidden = false; detail.querySelector('button').addEventListener('click', () => { detail.hidden = true; });
    }
    renderPicker();
}

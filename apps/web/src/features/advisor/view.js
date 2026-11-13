import {buildAdvisorRecommendations, cheaperToUpgrade, CATEGORY_LABELS, LOSS_CATS, WIN_CATS} from './model.mjs';

/** Advisor UI (Revision 4, eco-aware): saved first-pass evidence + per-cell economics, never on-demand simulations. */
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
    const scoreText = value => value.toLocaleString(undefined, {maximumFractionDigits: 1});
    const pct = value => `${Math.round(100 * value)}%`;
    const vmText = value => `${Math.round(value)} villager-minutes`;
    /** Display groups, best to worst; pending cells are split by their provisional result. */
    const GROUPS = [
        ['dominance', 'win'], ['kite', 'win'], ['plain_win', 'win'], ['power_win', 'win'],
        ['eco_win', 'eco'], ['close', 'close'], ['cheap_loss', 'eco'], ['plain_loss', 'loss'],
        ['kited_loss', 'loss'], ['outclassed_loss', 'loss'], ['pending_win', 'pending'], ['pending_loss', 'pending'],
    ];
    const GROUP_LABEL = {...CATEGORY_LABELS, pending_win: 'Pending, likely win', pending_loss: 'Pending, likely loss'};
    const groupOf = info => info.pending ? (info.won ? 'pending_win' : 'pending_loss') : info.cat;
    /** Category text of one matchup from the first unit's side, for titles and the detail panel. */
    function resultText(info) {
        if (info.pending) return `Pending (likely ${info.won ? 'win' : 'loss'})`;
        let text = CATEGORY_LABELS[info.cat];
        if (info.cat === 'cheap_loss' && info.hpWinner === null) text += ' (winner HP unknown)';
        return text;
    }
    function hpText(info) {
        if (info.hpWinner === null || info.hpWinner === undefined) return '';
        return info.won ? `keeps ${pct(info.hpWinner)} HP` : `winner keeps ${pct(info.hpWinner)} HP`;
    }
    function upgradeTitle(unit, other) {
        return cheaperToUpgrade(unit, other) ? ` · cheaper to fully upgrade (${Math.round(unit.full_research_vm)} vs ${Math.round(other.full_research_vm)} villager-minutes)` : '';
    }
    function opponentButton(entry, opp, plan) {
        const info = entry.vs.get(opp), row = entry.rows.get(opp), other = units.get(opp);
        const button = document.createElement('button'); button.type = 'button';
        const group = GROUPS.find(([key]) => key === groupOf(info))[1];
        button.className = `ma-match ma-match-${group} ma-cat-${info.cat}${info.pending ? ' ma-match-pending' : ''}`;
        button.dataset.opponent = String(opp);
        button.dataset.category = info.pending ? 'pending' : info.cat;
        const hp = hpText(info);
        button.title = `${other.name}: ${resultText(info)}${hp ? `, ${hp}` : ''} · ${row[4]} vs ${row[5]} units${upgradeTitle(entry.unit, other)}`;
        button.setAttribute('aria-label', button.title);
        button.innerHTML = image(other, 'ma-opponent-icon') + (cheaperToUpgrade(entry.unit, other) ? '<span class="ma-upgrade-mark" aria-hidden="true"></span>' : '');
        button.addEventListener('click', () => showDetail(entry, opp, plan));
        return button;
    }
    function matchLine(container, entry, opponents, label, cls, plan, category) {
        if (!opponents.length) return;
        const line = document.createElement('div'); line.className = `ma-match-line ma-line-${cls}`;
        if (category) line.dataset.category = category;
        const heading = document.createElement('span'); heading.className = 'ma-match-label'; heading.textContent = label; line.appendChild(heading);
        const icons = document.createElement('div'); icons.className = 'ma-opponents';
        for (const opp of opponents) icons.appendChild(opponentButton(entry, opp, plan));
        line.appendChild(icons); container.appendChild(line);
    }
    /** One line per result category, opponents strongest first. */
    function categoryLines(container, entry, plan) {
        const order = [...entry.vs.keys()].sort((a, b) => plan.strength.get(b) - plan.strength.get(a) || a - b);
        for (const [key, cls] of GROUPS) {
            matchLine(container, entry, order.filter(opp => groupOf(entry.vs.get(opp)) === key), GROUP_LABEL[key], cls, plan, key);
        }
    }
    function badges(entry) {
        const enemies = [...entry.vs.keys()].map(id => units.get(id));
        const cheaper = enemies.filter(other => cheaperToUpgrade(entry.unit, other)).length;
        const pending = [...entry.vs.values()].filter(info => info.pending).length;
        const out = [];
        if (cheaper) out.push(`<span class="ma-badge ma-badge-upgrade" title="Its full set of upgrades costs at most half of what the opposing unit's does (villager-minutes of research)"><span class="ma-upgrade-mark" aria-hidden="true"></span>Cheaper to fully upgrade than ${cheaper} of ${enemies.length}</span>`);
        if (pending) out.push(`<span class="ma-badge ma-badge-pending" title="Not simulated yet: these results are provisional until the re-simulation lands">${pending} pending</span>`);
        return out.length ? `<div class="ma-badges">${out.join('')}</div>` : '';
    }
    function unitHeading(entry, featured = false) {
        return `<div class="ma-unit-heading">${image(entry.unit)}<div><${featured ? 'h3' : 'h4'}>${esc(entry.unit.name)}</${featured ? 'h3' : 'h4'}><div class="ma-costs">${costs(entry.unit)}</div></div><div class="ma-coverage" title="Advantage: every matchup scored by its result (a plain win is 1), weighted by how strong the opposing unit is"><strong>${scoreText(entry.adv)}</strong><small>advantage</small></div></div>${badges(entry)}`;
    }
    function mainCard(plan) {
        const entry = plan.main, card = document.createElement('article');
        card.className = 'ma-unit-card ma-recommendation ma-main'; card.dataset.role = 'main'; card.dataset.unit = entry.unit.key;
        card.innerHTML = `<span class="ma-role">Main unit</span>${unitHeading(entry, true)}`;
        categoryLines(card, entry, plan);
        return card;
    }
    const kindText = {loss: 'main loses', struggle: 'main struggles'};
    function helpReason(help, si, mi) {
        if (help.why === 'more_hp') return `same result, keeps ${pct(si.hpOwn)} HP instead of ${pct(mi.hpOwn)}`;
        if (help.why === 'cheaper') return `same result with a ${Math.round(100 * (1 - si.vmOwn / mi.vmOwn))}% cheaper army`;
        if (mi.cat !== si.cat && LOSS_CATS.has(mi.cat) && WIN_CATS.has(si.cat)) return 'wins where the main loses';
        return 'better result';
    }
    function supportCard(plan) {
        const support = plan.support, card = document.createElement('article');
        card.className = 'ma-sidekick'; card.dataset.role = 'sidekick';
        const role = '<span class="ma-role" title="A unit without a gold cost, or a Scorpion">Support</span>';
        if (!support) {
            const note = plan.targets.length ? 'No unit without gold, and no Scorpion, does better than the main unit against its weak spots'
                : 'No support needed: the main unit wins every matchup comfortably';
            card.innerHTML = `${role}<span class="ma-short-note">${note}</span>`;
            return card;
        }
        const entry = support.entry;
        card.dataset.unit = entry.unit.key;
        card.innerHTML = `<div class="ma-support-heading">${role}<div class="ma-support-unit">${image(entry.unit)}<h3>${esc(entry.unit.name)}</h3></div></div>`;
        const list = document.createElement('ul'); list.className = 'ma-helps'; list.setAttribute('aria-label', `Where ${entry.unit.name} helps`);
        for (const help of support.helps) {
            const si = entry.vs.get(help.opp), mi = plan.main.vs.get(help.opp), other = units.get(help.opp);
            const item = document.createElement('li'); item.className = 'ma-help'; item.dataset.opponent = String(help.opp); item.dataset.why = help.why;
            item.appendChild(opponentButton(entry, help.opp, plan));
            const pending = si.pending || mi.pending ? ' <span class="ma-pending-tag">pending</span>' : '';
            const text = document.createElement('span'); text.className = 'ma-help-text';
            text.innerHTML = `<strong>${esc(other.name)}</strong> <span class="ma-help-kind">${kindText[help.kind]}</span>${pending}<span class="ma-help-why">${esc(helpReason(help, si, mi))}: ${esc(resultText(si))} vs main ${esc(resultText(mi).toLowerCase())}</span>`;
            item.appendChild(text); list.appendChild(item);
        }
        card.appendChild(list);
        return card;
    }
    function additionalCounters(plan) {
        const section = document.createElement('section'); section.className = 'ma-additions'; section.dataset.role = 'additions';
        const heading = document.createElement('span'); heading.className = 'ma-role'; heading.textContent = 'Add against the rest'; section.appendChild(heading);
        const groups = document.createElement('div'); groups.className = 'ma-counter-groups';
        for (const addition of plan.additions) {
            const unit = addition.entry.unit;
            const group = document.createElement('div'); group.className = 'ma-counter-group'; group.dataset.counter = String(unit.id);
            group.innerHTML = `<img class="ma-unit-icon" src="${esc(icon(unit))}" alt="${esc(unit.name)}" title="Add ${esc(unit.name)}" loading="lazy" width="32" height="32"><span class="ma-counter-arrow" aria-hidden="true">→</span>`;
            const targets = document.createElement('div'); targets.className = 'ma-counter-targets';
            matchLine(targets, addition.entry, addition.covers, 'Counters', 'win', plan);
            group.appendChild(targets); groups.appendChild(group);
        }
        section.appendChild(groups);
        if (plan.unanswered.length) matchLine(section, plan.main, plan.unanswered, 'No answer', 'loss', plan);
        if (!plan.uncovered.length) section.insertAdjacentHTML('beforeend', '<span class="ma-short-note">Nothing left uncovered</span>');
        return section;
    }
    function fillPlan(element, plan, civilization, side) {
        element.innerHTML = `<header class="ma-plan-header"><h2>${esc(civilization)}</h2><span class="ma-kicker">${side === 'left' ? 'What you should build' : 'What to expect'}</span></header>`;
        const body = document.createElement('div'); body.className = 'ma-plan-body';
        body.appendChild(mainCard(plan));
        body.appendChild(supportCard(plan));
        body.appendChild(additionalCounters(plan));
        element.appendChild(body);
    }
    const LEGEND = [
        ['dominance', 'win', 'Wins with an army at least 25% cheaper and keeps at least half its HP.'],
        ['kite', 'win', 'A ranged unit beats a melee unit it can outrun while shooting.'],
        ['plain_win', 'win', 'Wins; both armies cost about the same.'],
        ['power_win', 'win', 'Wins, but its army costs at least 25% more (often the Castles needed to train it).'],
        ['eco_win', 'eco', 'Loses narrowly (the winner keeps under half its HP) with an army at least 25% cheaper: a fair trade.'],
        ['close', 'close', 'Too close to call, or the same unit on both sides.'],
        ['cheap_loss', 'eco', 'Loses clearly, but its army costs at least 25% less.'],
        ['plain_loss', 'loss', 'Loses at about the same cost.'],
        ['kited_loss', 'loss', 'A melee unit that cannot catch the ranged unit shooting it.'],
        ['outclassed_loss', 'loss', 'Loses to an army at least 25% cheaper that keeps at least half its HP.'],
        ['pending', 'pending', 'Not simulated yet. The provisional result counts as a plain win or loss until the re-simulation lands.'],
    ];
    function legend() {
        const items = LEGEND.map(([key, cls, text]) => `<li><span class="ma-match ma-legend-swatch ma-match-${cls} ma-cat-${key}${key === 'pending' ? ' ma-match-pending' : ''}" aria-hidden="true"></span><b>${esc(CATEGORY_LABELS[key])}</b> ${esc(text)}</li>`).join('');
        return `<details class="ma-legend-box"><summary>How the results are labelled</summary><ul class="ma-legend-list">${items}</ul><p>Costs are each army's 60-second investment in villager-minutes, production buildings included. <span class="ma-upgrade-mark ma-upgrade-inline" aria-hidden="true"></span>Cheaper to fully upgrade: the unit's full set of upgrades costs at most half of the opposing unit's. The main unit has the best advantage among gold units (Scorpions excluded); the support is a unit without gold, or a Scorpion, that does better where the main loses or struggles.</p></details>`;
    }
    function renderComparison(rows) {
        const plans = buildAdvisorRecommendations(rows, units);
        top.innerHTML = `<p class="ma-legend">Icons are the opposing units, grouped by result; select one for army sizes, HP and costs.</p>${legend()}<div class="ma-compositions"><section class="ma-plan ma-plan-left" id="ma-left-plan"></section><section class="ma-plan ma-plan-right" id="ma-right-plan"></section></div>`;
        fillPlan(document.getElementById('ma-left-plan'), plans.left, left, 'left');
        fillPlan(document.getElementById('ma-right-plan'), plans.right, right, 'right');
        results.innerHTML = `<div class="ma-team-columns"><section class="ma-team ma-team-left"><header><h2>Other ${esc(left)} options</h2></header><div id="ma-left-units"></div></section><section class="ma-team ma-team-right"><header><h2>Other ${esc(right)} options</h2></header><div id="ma-right-units"></div></section></div>`;
        fillAlternatives(document.getElementById('ma-left-units'), plans.left);
        fillAlternatives(document.getElementById('ma-right-units'), plans.right);
    }
    function fillAlternatives(element, plan) {
        if (!plan.alternatives.length) { element.innerHTML = '<p class="ma-short-note">No other winning options</p>'; return; }
        for (const entry of plan.alternatives) {
            const card = document.createElement('article'); card.className = 'ma-unit-card'; card.dataset.unit = entry.unit.key;
            card.innerHTML = unitHeading(entry);
            categoryLines(card, entry, plan);
            element.appendChild(card);
        }
    }
    function showDetail(entry, opp, plan) {
        const row = entry.rows.get(opp), info = entry.vs.get(opp);
        const a = units.get(row[0]), b = units.get(row[1]), detail = document.getElementById('ma-detail');
        const facts = [];
        const hp = hpText(info);
        if (hp) facts.push(`${info.won ? a.name : b.name} ${hp.replace('winner ', '')}.`);
        if (info.vmOwn !== null && info.vmOpp !== null) facts.push(`60-second army investment: ${Math.round(info.vmOwn)} vs ${vmText(info.vmOpp)}.`);
        if (a.full_research_vm != null && b.full_research_vm != null) facts.push(`Full upgrades: ${Math.round(a.full_research_vm)} vs ${vmText(b.full_research_vm)}${cheaperToUpgrade(a, b) ? ` (${a.name} cheaper to fully upgrade)` : cheaperToUpgrade(b, a) ? ` (${b.name} cheaper to fully upgrade)` : ''}.`);
        if (info.pending) facts.push('Not simulated yet: the result is a provisional estimate until the re-simulation lands.');
        detail.innerHTML = `<button type="button" class="ma-detail-close" aria-label="Close matchup details">×</button><div class="ma-detail-armies">${image(a)}<span>${row[4]} ${esc(a.name)}<small>${esc(a.civilization)}</small></span><b>vs</b>${image(b)}<span>${row[5]} ${esc(b.name)}<small>${esc(b.civilization)}</small></span></div><strong>${esc(a.name)}: ${esc(resultText(info))}</strong><p>${facts.map(esc).join(' ')}</p><p>Fully upgraded units; army sizes set so both armies cost about the same to buy. The 60-second investment also counts the production buildings and research needed.</p>`;
        detail.hidden = false; detail.querySelector('button').addEventListener('click', () => { detail.hidden = true; });
    }
    renderPicker();
}

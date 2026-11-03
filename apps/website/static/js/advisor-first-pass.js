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
    const evidence = row => row[3] === 'predicted_unvalidated' ? 'Estimated' : row[3] === 'inferred' ? 'Inferred' : row[3] === 'identity' ? 'Equivalent' : 'Observed';
    const invert = row => [row[1], row[0], row[2] === 'a_win' ? 'b_win' : row[2] === 'b_win' ? 'a_win' : row[2], row[3], row[5], row[4], ...row.slice(6)];
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
    function unitRows(rows) {
        const grouped = new Map();
        for (const row of rows) { if (!grouped.has(row[0])) grouped.set(row[0], []); grouped.get(row[0]).push(row); }
        return [...grouped].map(([id, matches]) => ({unit: units.get(id), matches, wins: matches.filter(r => r[2] === 'a_win')}));
    }
    const ordered = entries => entries.sort((a,b) => b.wins.length - a.wins.length || a.unit.name.localeCompare(b.unit.name));
    function summary(entries, side, name) {
        const best = ordered([...entries])[0];
        return `<article class="ma-feature ma-feature-${side}"><span class="ma-kicker">${esc(name)} · broadest coverage</span><div class="ma-feature-body">${image(best.unit, 'ma-feature-icon')}<div><h2>${esc(best.unit.name)}</h2><p>${best.wins.length} favorable matchups <span>of ${best.matches.length}</span></p></div></div><div class="ma-feature-foot">${best.wins.filter(r => r[3] !== 'predicted_unvalidated').length} observed / inferred · ${best.wins.filter(r => r[3] === 'predicted_unvalidated').length} estimated</div></article>`;
    }
    function renderComparison(rows) {
        const mine = unitRows(rows), theirs = unitRows(rows.map(invert));
        top.innerHTML = `<div class="ma-evidence-banner"><span class="ma-provisional">PROVISIONAL</span><div><strong>${rows.length} saved unit matchups</strong><span>Fully upgraded land units · cost-adjusted armies, up to 27 units</span></div><a href="${esc(config.dataset.source_url)}" target="_blank" rel="noopener">Data &amp; methodology ↗</a></div><div class="ma-features">${summary(mine,'left',left)}${summary(theirs,'right',right)}</div>`;
        results.innerHTML = `<div class="ma-legend"><span><i class="ma-dot ma-dot-win"></i>Favorable</span><span><i class="ma-dot ma-dot-loss"></i>Difficult</span><span><i class="ma-dot ma-dot-close"></i>Close / equal</span><span class="ma-legend-note"><b>Est.</b> is an unvalidated forecast; dashed icons show estimates.</span></div><div class="ma-team-columns"><section class="ma-team ma-team-left"><header><span>Your options</span><h2>${esc(left)}</h2></header><div id="ma-left-units"></div></section><section class="ma-team ma-team-right"><header><span>Opponent's options</span><h2>${esc(right)}</h2></header><div id="ma-right-units"></div></section></div>`;
        fillSide(document.getElementById('ma-left-units'), mine);
        fillSide(document.getElementById('ma-right-units'), theirs);
        fillSiege(document.getElementById('ma-left-units'), left);
        fillSiege(document.getElementById('ma-right-units'), right);
    }
    function fillSiege(element, civilization) {
        const entries = config.reference_units?.[civilization] || [];
        if (!entries.length) return;
        const section = document.createElement('div'); section.className = 'ma-unit-group ma-reference';
        section.innerHTML = '<h3>Siege · reference</h3><p class="ma-reference-note">Outside the land-unit matchup table. Existing published ranks are shown where available.</p>';
        for (const unit of entries) {
            const card = document.createElement('article'); card.className = 'ma-unit-card';
            card.innerHTML = `<div class="ma-unit-heading">${image(unit)}<div><h4>${esc(unit.name)}</h4><div class="ma-costs">${costs(unit)}</div></div>${unit.rank != null ? `<div class="ma-coverage"><strong>#${unit.rank}</strong><small>published rank</small></div>` : ''}</div>`;
            section.appendChild(card);
        }
        element.appendChild(section);
    }
    function fillSide(element, entries) {
        for (const group of ['Cavalry','Ranged','Infantry']) {
            const available = ordered(entries.filter(entry => entry.unit.group === group));
            if (!available.length) continue;
            const section = document.createElement('div'); section.className = 'ma-unit-group';
            section.innerHTML = `<h3>${group}</h3>`;
            for (const entry of available) {
                const card = document.createElement('article'); card.className = 'ma-unit-card'; card.dataset.unit = entry.unit.key;
                card.innerHTML = `<div class="ma-unit-heading">${image(entry.unit)}<div><h4>${esc(entry.unit.name)}</h4><div class="ma-costs">${costs(entry.unit)}</div></div><div class="ma-coverage"><strong>${entry.wins.length}<span>/${entry.matches.length}</span></strong><small>favorable</small></div></div>`;
                const groups = [['a_win','Favorable','win'],['b_win','Difficult','loss'],['close','Close / equal','close']];
                for (const [outcome,label,cls] of groups) {
                    const matches = entry.matches.filter(r => outcome === 'close' ? ['equivalent','close_uncertain'].includes(r[2]) : r[2] === outcome);
                    if (!matches.length) continue;
                    const line = document.createElement('div'); line.className = `ma-match-line ma-line-${cls}`;
                    const heading = document.createElement('span'); heading.className = 'ma-match-label'; heading.textContent = label; line.appendChild(heading);
                    const icons = document.createElement('div'); icons.className = 'ma-opponents';
                    for (const row of matches) {
                        const other = units.get(row[1]); const estimated = row[3] === 'predicted_unvalidated';
                        const button = document.createElement('button'); button.type = 'button'; button.className = `ma-match ma-match-${cls}${estimated ? ' is-estimated' : ''}${row[7] & 2 ? ' is-low-support' : ''}`;
                        button.title = `${other.name}: ${label.toLowerCase()} · ${evidence(row)} · ${row[4]} vs ${row[5]} units${row[7] & 1 ? ' · Estimate has conflicting validation examples' : ''}`;
                        button.setAttribute('aria-label', button.title);
                        button.innerHTML = `${image(other, 'ma-opponent-icon')}<span class="ma-evidence-mark">${estimated ? 'Est.' : row[3] === 'inferred' ? 'Inf.' : row[3] === 'identity' ? '=' : 'Obs.'}</span>`;
                        button.addEventListener('click', () => showDetail(row)); icons.appendChild(button);
                    }
                    line.appendChild(icons); card.appendChild(line);
                }
                section.appendChild(card);
            }
            element.appendChild(section);
        }
    }
    function showDetail(row) {
        const a = units.get(row[0]), b = units.get(row[1]), detail = document.getElementById('ma-detail');
        const result = row[2] === 'a_win' ? `${a.name} is favored` : row[2] === 'b_win' ? `${b.name} is favored` : row[2] === 'equivalent' ? 'Equivalent combat profiles' : 'Close / uncertain outcome';
        detail.innerHTML = `<button type="button" class="ma-detail-close" aria-label="Close matchup details">×</button><div class="ma-detail-armies">${image(a)}<span>${row[4]} ${esc(a.name)}<small>${esc(a.civilization)}</small></span><b>vs</b>${image(b)}<span>${row[5]} ${esc(b.name)}<small>${esc(b.civilization)}</small></span></div><strong>${esc(result)}</strong><p><span class="ma-detail-badge">${evidence(row)}</span> ${row[3] === 'predicted_unvalidated' ? 'A first-pass estimate, not a verified winner.' : row[3] === 'inferred' ? 'Inferred from the recorded matchup evidence.' : 'Saved combat evidence for these army counts.'}${row[7] & 2 ? ' Low-support estimate.' : ''}${row[7] & 1 ? ' Related validation examples disagree; treat this estimate cautiously.' : ''}</p>`;
        detail.hidden = false; detail.querySelector('button').addEventListener('click', () => { detail.hidden = true; });
    }
    renderPicker();
}

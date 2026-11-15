/**
 * Matchup Advisor, Revision 5 (owner design 2026-11-15): weighted matchup values.
 *
 * JavaScript twin of tools/economy/advisor_eco/advisor_model_v5.py (the reference);
 * tests/advisor/v5-parity.test.mjs pins this file to the Python plans for all 3,080 plans.
 * Change a number in CONFIG here and in the Python reference together, then regenerate the
 * fixture (python tools/economy/advisor_eco/build_advisor_parity_fixture.py).
 *
 * Rows (API /api/advisor-matchups/<civ>, ROW_FIELDS in aoe2_api/services/advisor.py):
 *   [a, b, outcome, evidence_type, count_a, count_b, tier, flags, evidence_id, value]
 * value: the matchup value from a's side (positive win, negative loss, 0 draw).
 * Recommendation scores only: never change a saved matchup or its context.
 */

export const CONFIG = Object.freeze({
    multiplierSlope: 0.7,        // opponent multiplier = 1 + slope x its average value ...
    multiplierMin: 0.5,          // ... clamped to [min, max]
    multiplierMax: 1.5,
    gap: 0.5,                    // the main's weighted contribution below this is a gap for the support
    excludedMain: Object.freeze(['Scorpion', 'Heavy Scorpion']),
    supportExtra: Object.freeze(['Scorpion', 'Heavy Scorpion']),   // gold units allowed as support
});

const INVERSE = {a_win: 'b_win', b_win: 'a_win'};
export const isGold = unit => Number(unit.costs.gold) > 0;

export function invertMatchup(row) {
    const head = [row[1], row[0], INVERSE[row[2]] || row[2], row[3], row[5], row[4], row[6], row[7], row[8]];
    return row.length > 9 ? [...head, row[9] === 0 ? 0 : -row[9]] : head;
}

/** Lowest key wins: [-primary, -score, id], like min(key=...) in the Python reference. */
function best(candidates, primary, score) {
    let chosen = null;
    for (const i of candidates) {
        if (chosen === null) { chosen = i; continue; }
        const a = [-primary(i), -score.get(i), i], b = [-primary(chosen), -score.get(chosen), chosen];
        if (a[0] < b[0] || (a[0] === b[0] && (a[1] < b[1] || (a[1] === b[1] && a[2] < b[2])))) chosen = i;
    }
    return chosen;
}

/** Plan for the rows' own civilization (row[0]) against the opponent civilization (row[1]). */
export function plan(rows, units, cfg = CONFIG) {
    const value = new Map(), rowOf = new Map();
    const ownSet = new Set(), enemySet = new Set();
    for (const row of rows) {
        if (!units.has(row[0]) || !units.has(row[1])) throw new Error('Unknown matchup unit');
        value.set(`${row[0]}:${row[1]}`, row[9]); rowOf.set(`${row[0]}:${row[1]}`, row);
        ownSet.add(row[0]); enemySet.add(row[1]);
    }
    const own = [...ownSet].sort((a, b) => a - b), enemy = [...enemySet].sort((a, b) => a - b);
    if (value.size !== own.length * enemy.length) throw new Error('Incomplete matchup matrix');
    const v = (i, j) => value.get(`${i}:${j}`);
    const multiplier = new Map();
    for (const j of enemy) {
        let total = 0;
        for (const i of own) total += -v(i, j);
        multiplier.set(j, Math.min(cfg.multiplierMax, Math.max(cfg.multiplierMin, 1 + cfg.multiplierSlope * (total / own.length))));
    }
    const contribution = new Map(), score = new Map();
    for (const i of own) {
        let total = 0;
        for (const j of enemy) {
            const x = v(i, j), m = multiplier.get(j);
            const c = x >= 0 ? x * m : x * (2 - m);
            contribution.set(`${i}:${j}`, c);
            total += c;
        }
        score.set(i, total);
    }
    const c = (i, j) => contribution.get(`${i}:${j}`);
    const main = best(own.filter(i => !cfg.excludedMain.includes(units.get(i).name)), i => score.get(i), score);
    const gaps = enemy.filter(j => c(main, j) < cfg.gap);
    const candidates = own.filter(i => i !== main && (!isGold(units.get(i)) || cfg.supportExtra.includes(units.get(i).name)));
    const gains = new Map();
    for (const s of candidates) {
        let total = 0;
        for (const j of gaps) total += Math.max(0, c(s, j) - c(main, j));
        gains.set(s, total);
    }
    const support = best(candidates.filter(s => gains.get(s) > 0), s => gains.get(s), score)
        ?? best(candidates, s => score.get(s), score);
    const pair = support === null ? [main] : [main, support];
    const additions = new Map(), unanswered = [];
    for (const j of enemy) {
        if (pair.some(i => v(i, j) > 0)) continue;
        const pairBest = Math.max(...pair.map(i => c(i, j)));
        const counter = best(own.filter(i => !pair.includes(i) && c(i, j) > pairBest), i => c(i, j), score);
        if (counter === null) unanswered.push(j);
        else { if (!additions.has(counter)) additions.set(counter, []); additions.get(counter).push(j); }
    }
    const order = [...additions.keys()].sort((a, b) => additions.get(b).length - additions.get(a).length
        || score.get(b) - score.get(a) || a - b);
    const entry = i => i === null ? null : {
        unit: units.get(i), score: score.get(i),
        vs: new Map(enemy.map(j => [j, {value: v(i, j), contribution: c(i, j), row: rowOf.get(`${i}:${j}`)}])),
    };
    return {
        main: entry(main), support: entry(support), supportGain: support === null ? null : gains.get(support),
        gaps, additions: order.map(i => ({entry: entry(i), covers: additions.get(i)})),
        unanswered, score, multiplier, contribution, enemy,
    };
}

/** Both sides' plans from the rows of the left civilization's document. */
export function buildAdvisorRecommendations(rows, catalog, cfg = CONFIG) {
    const units = catalog instanceof Map ? catalog : new Map(catalog.map(unit => [unit.id, unit]));
    return {left: plan(rows, units, cfg), right: plan(rows.map(invertMatchup), units, cfg)};
}

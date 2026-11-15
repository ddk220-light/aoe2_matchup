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
    gap: 0.5,                    // a win below this weighted value is a weak win (support fallback)
    excludedMain: Object.freeze(['Scorpion', 'Heavy Scorpion']),
    supportExtra: Object.freeze([]),   // gold units allowed as support (none: Scorpions only as extra units, owner 2026-11-15)
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

/** Smallest key array (lexicographic), like min(key=tuple) in the Python reference. */
function minBy(items, key) {
    let chosen = null, chosenKey = null;
    for (const item of items) {
        const k = key(item);
        if (chosen !== null) {
            let less = false;
            for (let i = 0; i < k.length; i += 1) if (k[i] !== chosenKey[i]) { less = k[i] < chosenKey[i]; break; }
            if (!less) continue;
        }
        chosen = item; chosenKey = k;
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
    /** Support for one main: holes strongest first, then weak wins, then best score (rule 4). */
    function supportFor(main) {
        const candidates = own.filter(i => i !== main && (!isGold(units.get(i)) || cfg.supportExtra.includes(units.get(i).name)));
        const holes = enemy.filter(j => v(main, j) <= 0).sort((a, b) => multiplier.get(b) - multiplier.get(a) || a - b);
        const gain = (s, targets) => {
            let total = 0;
            for (const j of targets) total += Math.max(0, v(s, j) - v(main, j)) * multiplier.get(j);
            return total;
        };
        for (const t of holes) {
            const better = candidates.filter(s => v(s, t) > v(main, t));
            if (better.length) return [minBy(better, s => [-v(s, t), -gain(s, holes), -score.get(s), s]), 'threat', t, holes];
        }
        const weak = enemy.filter(j => v(main, j) > 0 && c(main, j) < cfg.gap);
        const helped = candidates.filter(s => gain(s, weak) > 0);
        if (helped.length) return [best(helped, s => gain(s, weak), score), 'weak_wins', null, holes];
        if (candidates.length) return [best(candidates, s => score.get(s), score), 'score', null, holes];
        return [null, null, null, holes];
    }
    // Main and support as a pair: strength of the enemy units beaten (draw = half), then pair score.
    const pairs = new Map();
    for (const m of own.filter(i => !cfg.excludedMain.includes(units.get(i).name))) {
        const found = supportFor(m), members = found[0] === null ? [m] : [m, found[0]];
        let wins = 0, draws = 0, beaten = 0, total = 0;
        for (const j of enemy) {
            const top = Math.max(...members.map(i => v(i, j)));
            if (top > 0) { wins += 1; beaten += multiplier.get(j); }
            else if (top === 0) { draws += 1; beaten += 0.5 * multiplier.get(j); }
            total += Math.max(...members.map(i => c(i, j)));
        }
        pairs.set(m, {found, beaten, total, wins: wins + 0.5 * draws});
    }
    const main = minBy([...pairs.keys()], m => [-pairs.get(m).beaten, -pairs.get(m).total, -score.get(m), m]);
    const [support, supportReason, supportTarget, holes] = pairs.get(main).found;
    const pairWins = pairs.get(main).wins, pairBeaten = pairs.get(main).beaten, pairScore = pairs.get(main).total;
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
        main: entry(main), support: entry(support), supportReason, supportTarget, pairWins, pairBeaten, pairScore,
        holes, additions: order.map(i => ({entry: entry(i), covers: additions.get(i)})),
        unanswered, score, multiplier, contribution, enemy,
    };
}

/** Both sides' plans from the rows of the left civilization's document. */
export function buildAdvisorRecommendations(rows, catalog, cfg = CONFIG) {
    const units = catalog instanceof Map ? catalog : new Map(catalog.map(unit => [unit.id, unit]));
    return {left: plan(rows, units, cfg), right: plan(rows.map(invertMatchup), units, cfg)};
}

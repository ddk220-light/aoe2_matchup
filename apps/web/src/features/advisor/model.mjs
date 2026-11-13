/**
 * Matchup Advisor, Revision 4 (eco-aware): category-weighted scoring with opponent strength.
 *
 * JavaScript port of tools/economy/advisor_eco/advisor_model_rev4.py (the reference; default
 * weight set). tests/advisor/rev4-parity.test.mjs pins this file to the Python plans for all
 * 3,080 plans. Spec: docs/army-economics/ADVISOR_ECO_DESIGN.md, "Revision 4".
 *
 * Every tunable number lives in WEIGHTS and CONFIG below. Changing one changes the site's
 * recommendations: change the Python reference the same way and regenerate the fixture
 * (python tools/economy/advisor_eco/build_advisor_parity_fixture.py).
 *
 * Rows (API /api/advisor-matchups/<civ>, ROW_FIELDS in aoe2_api/services/advisor.py):
 *   [a, b, outcome, evidence_type, count_a, count_b, tier, flags, evidence_id,
 *    category_a, category_b, winner_hp, vm_a, vm_b]
 * Recommendation scores only: never change a saved matchup or its context.
 */

import {pySum} from '../economy/accounting.mjs';

/** Category weights (WEIGHT_SETS.default). A plain win is the unit. */
export const WEIGHTS = Object.freeze({
    dominance: 1.5, kite: 1.5, plain_win: 1.0, power_win: 0.6, eco_win: 0.25,
    close: 0.0, cheap_loss: -0.25, plain_loss: -0.5, kited_loss: -0.75, outclassed_loss: -0.75,
});

/** Everything else (CONFIG in advisor_model_rev4.py, plus the badge ratio of classify.py). */
export const CONFIG = Object.freeze({
    strength: 'minmax',          // minmax | rank | none
    lo: 0.5, hi: 1.5,            // opponent-strength range
    goldMain: true,              // prefer a gold main with at least one win
    struggleHp: 0.50,            // a win where the main keeps < this share of HP is a struggle
    strugglePower: true,         // a power win (main's army >= 25% dearer) is a struggle ...
    strugglePowerHp: 1.01,       // ... when the main keeps < this share of HP (1.01 = always)
    struggleClose: true,         // a close result is a struggle
    helpHpMargin: 0.15,          // same result: support keeps >= 15 HP points more
    helpEco: 0.25,               // same result: support army >= 25% cheaper (60-s investment)
    helpTieBonus: 0.25,          // help value of a same-result-but-better help
    excludedMain: Object.freeze(['Scorpion', 'Heavy Scorpion']),
    supportExtra: Object.freeze(['Scorpion', 'Heavy Scorpion']),   // gold units allowed as support
    badgeResearchRatio: 0.5,     // badge: own full research package <= this x the opponent's
});

export const CATEGORIES = Object.freeze(['dominance', 'kite', 'plain_win', 'power_win', 'eco_win', 'close',
    'cheap_loss', 'plain_loss', 'kited_loss', 'outclassed_loss']);
export const WIN_CATS = new Set(['dominance', 'kite', 'plain_win', 'power_win']);
export const LOSS_CATS = new Set(['eco_win', 'cheap_loss', 'plain_loss', 'kited_loss', 'outclassed_loss']);
export const CATEGORY_LABELS = Object.freeze({
    dominance: 'Complete dominance', kite: 'Clear win (kite)', plain_win: 'Plain win', power_win: 'Power win',
    eco_win: 'Eco win', close: 'Close', cheap_loss: 'Cheap loss', plain_loss: 'Plain loss',
    kited_loss: 'Kited loss', outclassed_loss: 'Outclassed loss', pending: 'Pending',
});

const EPS = 1e-12;
const CLOSE = new Set(['equivalent', 'close_uncertain']);
const INVERSE = {a_win: 'b_win', b_win: 'a_win'};
export const isGold = unit => Number(unit.costs.gold) > 0;
/**
 * Python's round(x, digits): nearest decimal of the exact binary value, ties to even
 * (toFixed alone rounds ties up; dyadic scores such as 9.1328125 do hit ties).
 * toFixed(100) is the exact expansion for every magnitude these scores reach.
 */
export function pyRound(x, digits) {
    if (!Number.isFinite(x)) return x;
    const sign = x < 0 ? -1 : 1, abs = Math.abs(x);
    const exact = abs.toFixed(100), point = exact.indexOf('.');
    const tail = exact.slice(point + 1 + digits);
    if (/^50*$/.test(tail)) {
        const kept = exact.slice(0, digits ? point + 1 + digits : point);
        const last = Number(kept[kept.length - 1]);
        const down = Number(kept);
        return sign * (last % 2 === 0 ? down : Number((down + 10 ** -digits).toFixed(digits)));
    }
    return sign * Number(abs.toFixed(digits));
}
const r9 = x => pyRound(x, 9);
const byCodePoint = (a, b) => a < b ? -1 : a > b ? 1 : 0;

export function invertMatchup(row) {
    const head = [row[1], row[0], INVERSE[row[2]] || row[2], row[3], row[5], row[4], row[6], row[7], row[8]];
    return row.length > 9 ? [...head, row[10], row[9], row[11], row[13], row[12]] : head;
}

/** Category info of a row from its first unit's side (advisor_model_rev4.row_info). */
export function rowInfo(row) {
    const [, , outcome, evidence] = row;
    const blank = {hpOwn: null, hpWinner: null, vmOwn: null, vmOpp: null};
    const category = row.length > 9 ? row[9] : null;
    if (CLOSE.has(outcome) || evidence === 'identity' || category === 'close') return {cat: 'close', won: false, pending: false, ...blank};
    if (evidence === 'inferred' || category === 'pending') {
        const won = outcome === 'a_win';
        return {cat: won ? 'plain_win' : 'plain_loss', won, pending: true, ...blank};
    }
    if (category === null) {  // a nine-field row without eco fields: plain result
        const won = outcome === 'a_win';
        return {cat: won ? 'plain_win' : 'plain_loss', won, pending: false, ...blank};
    }
    const won = WIN_CATS.has(category), hp = row[11];
    return {cat: category, won, pending: false, hpWinner: hp, hpOwn: won ? hp : 0, vmOwn: row[12], vmOpp: row[13]};
}

function entries(rows, units) {
    const out = new Map();
    for (const row of rows) {
        if (!units.has(row[0]) || !units.has(row[1])) throw new Error('Unknown matchup unit');
        if (!out.has(row[0])) out.set(row[0], {unit: units.get(row[0]), vs: new Map(), rows: new Map()});
        const entry = out.get(row[0]);
        entry.vs.set(row[1], rowInfo(row));
        entry.rows.set(row[1], row);
    }
    return out;
}

function normalise(scores, cfg) {
    const {lo, hi} = cfg, keys = [...scores.keys()];
    if (cfg.strength === 'none' || !keys.length) return new Map(keys.map(k => [k, 1.0]));
    if (cfg.strength === 'rank') {
        const order = [...keys].sort((a, b) => scores.get(a) - scores.get(b) || a - b);
        const n = order.length;
        if (n === 1) return new Map([[order[0], 1.0]]);
        const ranks = new Map();
        for (let i = 0; i < n;) {
            let j = i;
            while (j + 1 < n && scores.get(order[j + 1]) === scores.get(order[i])) j += 1;
            for (const k of order.slice(i, j + 1)) ranks.set(k, (i + j) / 2);
            i = j + 1;
        }
        return new Map(keys.map(k => [k, lo + (hi - lo) * ranks.get(k) / (n - 1)]));
    }
    const values = [...scores.values()], mn = Math.min(...values), mx = Math.max(...values);
    if (mx === mn) return new Map(keys.map(k => [k, (lo + hi) / 2]));
    return new Map(keys.map(k => [k, lo + (hi - lo) * (scores.get(k) - mn) / (mx - mn)]));
}

/** Base score: sum() of the weights (pySum: CPython's compensated float sum). */
function base(entry, w) {
    return pySum([...entry.vs.values()].map(info => w[info.cat]));
}

/** Advantage: a plain running total, as the Python loop. */
function score(own, w, strength, cfg) {
    const s = cfg.lo + cfg.hi;
    for (const entry of own.values()) {
        let adv = 0, wins = 0;
        for (const [opp, info] of entry.vs) {
            const wt = w[info.cat];
            adv += wt * (wt >= 0 ? strength.get(opp) : s - strength.get(opp));
            if (WIN_CATS.has(info.cat)) wins += 1;
        }
        Object.assign(entry, {adv, nWins: wins});
    }
}

/** _rank_key order: advantage, base score, gold first, name, id. */
export function rankCompare(a, b) {
    return r9(b.adv) - r9(a.adv) || r9(b.base) - r9(a.base)
        || Number(!isGold(a.unit)) - Number(!isGold(b.unit))
        || byCodePoint(a.unit.name, b.unit.name) || a.unit.id - b.unit.id;
}

export function struggles(info, cfg = CONFIG) {
    if (info.cat === 'close') return cfg.struggleClose;
    if (!WIN_CATS.has(info.cat)) return false;
    if (info.cat === 'power_win' && cfg.strugglePower && (info.hpOwn === null || info.hpOwn < cfg.strugglePowerHp)) return true;
    return info.hpOwn !== null && info.hpOwn < cfg.struggleHp;
}

/** [value, why] of the support's row against the main's row for the same target. */
export function helpValue(si, mi, w = WEIGHTS, cfg = CONFIG) {
    const gain = w[si.cat] - w[mi.cat];
    if (gain > EPS) return [gain, 'better'];
    if (Math.abs(gain) <= EPS && WIN_CATS.has(si.cat) && WIN_CATS.has(mi.cat)) {
        if (si.hpOwn !== null && mi.hpOwn !== null && si.hpOwn >= mi.hpOwn + cfg.helpHpMargin) return [cfg.helpTieBonus, 'more_hp'];
        if (si.vmOwn !== null && mi.vmOwn !== null && si.vmOwn <= (1 - cfg.helpEco) * mi.vmOwn) return [cfg.helpTieBonus, 'cheaper'];
    }
    return [0, null];
}

const byStrength = strength => (a, b) => strength.get(b) - strength.get(a) || a - b;

function recommend(own, strength, w, cfg) {
    const ranked = [...own.values()].sort(rankCompare);
    const excluded = new Set(cfg.excludedMain), extra = new Set(cfg.supportExtra);
    const eligible = ranked.filter(e => !excluded.has(e.unit.name));
    let main = cfg.goldMain ? eligible.find(e => isGold(e.unit) && e.nWins) || null : null;
    main = main || eligible[0] || null;
    const result = {ranked, main, topEligible: eligible[0] || null, topOverall: ranked[0] || null, strength,
        support: null, supportCandidates: [], targets: [], additions: [], uncovered: [], unanswered: [], alternatives: []};
    if (!main) return result;
    const targets = [];
    for (const [opp, mi] of main.vs) {
        if (LOSS_CATS.has(mi.cat)) targets.push([opp, 'loss']);
        else if (struggles(mi, cfg)) targets.push([opp, 'struggle']);
    }
    targets.sort((a, b) => strength.get(b[0]) - strength.get(a[0]) || a[0] - b[0]);
    result.targets = targets;
    const candidates = [];
    for (const entry of ranked) {
        if (entry === main || !(!isGold(entry.unit) || extra.has(entry.unit.name))) continue;
        const helps = [];
        for (const [opp, kind] of targets) {
            const [value, why] = helpValue(entry.vs.get(opp), main.vs.get(opp), w, cfg);
            if (value > 0) helps.push({opp, kind, value, why, credit: strength.get(opp) * value});
        }
        const total = pySum(helps.map(h => h.credit));
        const converts = helps.filter(h => WIN_CATS.has(entry.vs.get(h.opp).cat) && h.kind === 'loss').length;
        candidates.push({entry, helps, score: total, converts});
    }
    candidates.sort((a, b) => r9(b.score) - r9(a.score) || b.converts - a.converts || rankCompare(a.entry, b.entry));
    const support = candidates.length && candidates[0].score > 0 ? candidates[0] : null;
    result.support = support;
    result.supportCandidates = candidates;
    const beaten = new Set(support ? [...support.entry.vs].filter(([, i]) => WIN_CATS.has(i.cat)).map(([opp]) => opp) : []);
    const realLosses = [...main.vs].filter(([, i]) => LOSS_CATS.has(i.cat) && i.cat !== 'eco_win').map(([opp]) => opp);
    const remaining = new Set(realLosses.filter(opp => !beaten.has(opp)));
    result.uncovered = [...remaining].sort(byStrength(strength));
    const taken = new Set([main.unit.id, ...(support ? [support.entry.unit.id] : [])]);
    while (remaining.size) {
        const options = [];
        for (const entry of ranked) {
            if (taken.has(entry.unit.id)) continue;
            const covers = [...remaining].sort((a, b) => a - b).filter(o => WIN_CATS.has(entry.vs.get(o).cat));
            if (covers.length) options.push({entry, covers, value: pySum(covers.map(o => strength.get(o)))});
        }
        if (!options.length) break;
        options.sort((a, b) => r9(b.value) - r9(a.value) || b.covers.length - a.covers.length || rankCompare(a.entry, b.entry));
        const {entry, covers} = options[0];
        result.additions.push({entry, covers: [...covers].sort(byStrength(strength))});
        taken.add(entry.unit.id);
        for (const o of covers) remaining.delete(o);
    }
    result.unanswered = [...remaining].sort(byStrength(strength));
    result.alternatives = eligible.filter(e => !taken.has(e.unit.id) && e.nWins).slice(0, 3);
    return result;
}

/** Both plans for one civ pair; rows are the left civilization's rows against the right one. */
export function buildAdvisorRecommendations(rows, catalog, {weights = WEIGHTS, config = CONFIG} = {}) {
    const units = catalog instanceof Map ? catalog : new Map(catalog.map(unit => [unit.id, unit]));
    const left = entries(rows, units), right = entries(rows.map(invertMatchup), units);
    const bases = side => {
        for (const entry of side.values()) entry.base = base(entry, weights);
        return new Map([...side].map(([id, entry]) => [id, entry.base]));
    };
    const sLeft = normalise(bases(left), config), sRight = normalise(bases(right), config);
    for (const [id, entry] of left) entry.strength = sLeft.get(id);
    for (const [id, entry] of right) entry.strength = sRight.get(id);
    score(left, weights, sRight, config);
    score(right, weights, sLeft, config);
    return {left: {...recommend(left, sRight, weights, config), enemy: right},
            right: {...recommend(right, sLeft, weights, config), enemy: left}};
}

/** "Cheaper to fully upgrade": own full research package <= half the opponent's. */
export function cheaperToUpgrade(unit, opponent, cfg = CONFIG) {
    const own = unit.full_research_vm, other = opponent.full_research_vm;
    return own != null && other != null && own <= cfg.badgeResearchRatio * other;
}

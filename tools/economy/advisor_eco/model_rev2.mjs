/** SCRATCH COPY of apps/web/src/features/advisor/model.mjs with the Revision 2 rule
 * (docs/army-economics/ADVISOR_ECO_DESIGN.md, owner decisions 2026-11-12). Not site code.
 * Differences from the live model (marked REV2):
 *  - options.ecoWins: Set of "loserId:winnerId" cells classified "Eco win" for the loser
 *    (narrow loss, winner kept < 50% HP, loser's 60-s army investment >= 25% cheaper,
 *    kite rule not applicable). Such a row leaves the loser's `losses` (no counter is
 *    assigned) and is listed in `ecoLosses` (shown with a caveat). The winner keeps it
 *    as a win ("lite"): its score and threat weight are unchanged.
 *  - entry.contender: no real losses and at least one eco-win loss ("strong contender").
 *  - Main choice: if the usual main still has a real loss, the best-ranked gold strong
 *    contender with wins becomes main. A main with no real loss is never replaced.
 *  - Kite clear wins and power wins are ordinary wins (nothing to change).
 * With no options the output equals the live model. */
export const unitWeight = unit => Number(unit.costs.gold) > 0 ? 1 : 0.5;
export const invertMatchup = row => [row[1], row[0], row[2] === 'a_win' ? 'b_win' : row[2] === 'b_win' ? 'a_win' : row[2], row[3], row[5], row[4], ...row.slice(6)];
const isClose = row => ['equivalent', 'close_uncertain'].includes(row[2]);
const sum = (values, score) => values.reduce((total, value) => total + score(value), 0);
const compare = (a, b) => b.score - a.score || b.winWeight - a.winWeight || unitWeight(b.unit) - unitWeight(a.unit) || a.unit.name.localeCompare(b.unit.name) || a.unit.id - b.unit.id;

function group(rows, units, ecoWins) {
    const isEco = row => ecoWins.has(`${row[0]}:${row[1]}`); // REV2
    const grouped = new Map();
    for (const row of rows) {
        if (!units.has(row[0]) || !units.has(row[1])) throw new Error('Unknown matchup unit');
        if (!grouped.has(row[0])) grouped.set(row[0], {unit: units.get(row[0]), matches: []});
        grouped.get(row[0]).matches.push(row);
    }
    return [...grouped.values()].map(entry => ({...entry,
        wins: entry.matches.filter(row => row[2] === 'a_win'),
        losses: entry.matches.filter(row => row[2] === 'b_win' && !isEco(row)),
        ecoLosses: entry.matches.filter(row => row[2] === 'b_win' && isEco(row)), // REV2
        close: entry.matches.filter(isClose)}));
}

function recommend(own, enemy, units) {
    // Baseline weight preserves broad coverage even for enemies with no wins.
    // Threat(b) = weight(b) * (1 + weighted number of our units beaten by b).
    const threats = new Map(enemy.map(entry => [entry.unit.id,
        unitWeight(entry.unit) * (1 + sum(entry.wins, row => unitWeight(units.get(row[1]))))]));
    const threat = row => threats.get(row[1]);
    const ranked = own.map(entry => ({...entry,
        score: sum(entry.wins, threat),
        winWeight: sum(entry.wins, row => unitWeight(units.get(row[1]))),
    })).sort(compare);
    const sortThreats = rows => [...rows].sort((a, b) => threat(b) - threat(a) || a[1] - b[1]);
    for (const entry of ranked) {
        entry.wins = sortThreats(entry.wins);
        entry.losses = sortThreats(entry.losses);
        entry.close = sortThreats(entry.close);
        entry.ecoLosses = sortThreats(entry.ecoLosses); // REV2
        entry.contender = !entry.losses.length && entry.ecoLosses.length > 0; // REV2
    }
    // Prefer a gold main with actual wins; fall back if no gold unit can win.
    let main = ranked.find(entry => unitWeight(entry.unit) === 1 && entry.wins.length) || ranked[0];
    // REV2: a strong contender replaces a main that still has a real loss.
    if (main && main.losses.length) main = ranked.find(entry => unitWeight(entry.unit) === 1 && entry.wins.length && entry.contender) || main;
    if (!main) return {main: null, sidekick: null, alternatives: [], threats, uncovered: [], additions: [], unanswered: []};
    const weaknesses = new Set(main.losses.map(row => row[1]));
    const mainWins = new Set(main.wins.map(row => row[1]));
    const candidates = ranked.filter(entry => entry.unit.id !== main.unit.id && unitWeight(entry.unit) === 0.5).map(entry => {
        const covers = entry.wins.filter(row => weaknesses.has(row[1]));
        const holdsClose = entry.close.filter(row => weaknesses.has(row[1]));
        const newWins = entry.wins.filter(row => !mainWins.has(row[1]));
        return {...entry, covers, holdsClose, newWins,
            coverScore: sum(covers, threat), closeScore: sum(holdsClose, threat), newScore: sum(newWins, threat)};
    });
    candidates.sort((a, b) => b.coverScore - a.coverScore || b.closeScore - a.closeScore || b.newScore - a.newScore || compare(a, b));
    const sidekick = candidates[0] || null;
    const covered = new Set(sidekick?.covers.map(row => row[1]) || []);
    const uncovered = main.losses.filter(row => !covered.has(row[1]));
    const remaining = new Set(uncovered.map(row => row[1]));
    const additions = [];
    // Cover remaining threats with useful additions, grouping shared counters.
    // Every assignment comes from a winning row, never a close or inferred chain.
    while (remaining.size) {
        const options = ranked.filter(entry => entry.unit.id !== main.unit.id && entry.unit.id !== sidekick?.unit.id)
            .map(entry => ({entry, covers: entry.wins.filter(row => remaining.has(row[1]))}))
            .filter(option => option.covers.length);
        options.sort((a, b) => sum(b.covers, threat) - sum(a.covers, threat) || b.covers.length - a.covers.length || compare(a.entry, b.entry));
        if (!options.length) break;
        const best = options[0];
        additions.push({unit: best.entry.unit, covers: best.covers});
        for (const row of best.covers) remaining.delete(row[1]);
    }
    return {main, sidekick, threats, uncovered, additions,
        unanswered: uncovered.filter(row => remaining.has(row[1])),
        alternatives: ranked.filter(entry => entry.unit.id !== main.unit.id && entry.unit.id !== sidekick?.unit.id && entry.wins.length).slice(0, 3)};
}

export function buildAdvisorRecommendations(rows, catalog, options = {}) {
    const units = catalog instanceof Map ? catalog : new Map(catalog.map(unit => [unit.id, unit]));
    const ecoWins = options.ecoWins || new Set(); // REV2
    const left = group(rows, units, ecoWins), right = group(rows.map(invertMatchup), units, ecoWins);
    return {left: recommend(left, right, units), right: recommend(right, left, units)};
}

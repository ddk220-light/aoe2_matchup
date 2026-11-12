// Run the Revision 2 scratch model (model_rev2.mjs) on pairs given as JSON lines
// {left, right, rows} on stdin, with the eco-win cells from argv[3] (eco_wins.json of
// classify.py). Prints compact plans like dump_js_plans.mjs. Used by impact_rev2.py.
import {createInterface} from 'node:readline';
import {readFileSync} from 'node:fs';
import {buildAdvisorRecommendations} from './model_rev2.mjs';

const units = new Map(JSON.parse(readFileSync(process.argv[2], 'utf8')).map(u => [u.id, u]));
const ecoWins = new Set(JSON.parse(readFileSync(process.argv[3], 'utf8')).ecoWins.map(([l, w]) => `${l}:${w}`));
const id = entry => entry ? entry.unit.id : null;
const compact = plan => ({
    main: id(plan.main), sidekick: id(plan.sidekick),
    additions: plan.additions.map(a => [a.unit.id, a.covers.map(r => r[1])]),
    unanswered: plan.unanswered.map(r => r[1]), uncovered: plan.uncovered.map(r => r[1]),
    alternatives: plan.alternatives.map(e => e.unit.id),
    main_losses: plan.main ? plan.main.losses.map(r => r[1]) : [],
    main_wins: plan.main ? plan.main.wins.map(r => r[1]) : [],
});
for await (const line of createInterface({input: process.stdin})) {
    if (!line) continue;
    const {left, right, rows} = JSON.parse(line);
    const plans = buildAdvisorRecommendations(rows, units, {ecoWins});
    process.stdout.write(JSON.stringify({left, right, plans: {left: compact(plans.left), right: compact(plans.right)}}) + '\n');
}

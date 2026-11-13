// Run the pre-Revision-4 live advisor model (model_live_pre_rev4.mjs, a frozen copy of
// apps/web/src/features/advisor/model.mjs at d43113234) on pairs given as JSON lines {left, right, rows}
// on stdin; prints JSON lines of compact plans (same shape as advisor_model.summary). Used by check_js_parity.py.
import {createInterface} from 'node:readline';
import {readFileSync} from 'node:fs';
import {buildAdvisorRecommendations} from './model_live_pre_rev4.mjs';

const units = new Map(JSON.parse(readFileSync(process.argv[2], 'utf8')).map(u => [u.id, u]));
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
    const plans = buildAdvisorRecommendations(rows, units);
    process.stdout.write(JSON.stringify({left, right, plans: {left: compact(plans.left), right: compact(plans.right)}}) + '\n');
}

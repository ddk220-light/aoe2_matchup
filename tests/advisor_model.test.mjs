// Behaviour of the Revision 5 advisor model on small hand-made rosters. The full parity check
// against the Python reference (all 3,080 plans) is tests/advisor/v5-parity.test.mjs.
import test from 'node:test';
import assert from 'node:assert/strict';
import {buildAdvisorRecommendations as build, invertMatchup, plan, CONFIG} from '../apps/web/src/features/advisor/model.mjs';

const unit = (id, gold = 20, name = `Unit ${id}`) => ({id, key: `unit-${id}`, name, costs: {food: 50, wood: 0, gold}});
/** A served row from a's side with matchup value v. */
const row = (a, b, v) => [a, b, v > 0 ? 'a_win' : v < 0 ? 'b_win' : 'close_uncertain', 'observed', 27, 27, '', 0, 1, v];
const units = list => new Map(list.map(u => [u.id, u]));

test('settings', () => {
    assert.deepEqual({...CONFIG, excludedMain: [...CONFIG.excludedMain], supportExtra: [...CONFIG.supportExtra]},
        {multiplierSlope: 0.7, multiplierMin: 0.5, multiplierMax: 1.5, gap: 0.5,
            excludedMain: ['Scorpion', 'Heavy Scorpion'], supportExtra: ['Scorpion', 'Heavy Scorpion']});
});

test('opponent multiplier: 1 + 0.7 x average value from its side, clamped to 0.5..1.5', () => {
    const all = units([unit(1), unit(2), unit(101), unit(102)]);
    // 101 averages +0.5 against us -> 1.35; 102 averages -1 -> 0.3, clamped to 0.5.
    const p = plan([row(1, 101, -0.4), row(2, 101, -0.6), row(1, 102, 1), row(2, 102, 1)], all);
    assert.ok(Math.abs(p.multiplier.get(101) - 1.35) < 1e-12);
    assert.equal(p.multiplier.get(102), 0.5);
    // Wins scale by m, losses by 2 - m: unit 1 = -0.4 x 0.65 + 1 x 0.5.
    assert.ok(Math.abs(p.score.get(1) - (-0.4 * 0.65 + 0.5)) < 1e-12);
});

test('the main is the best weighted score but never a Scorpion; ties go to the lower id', () => {
    const all = units([unit(1, 75, 'Heavy Scorpion'), unit(2, 0, 'Halberdier'), unit(3, 20, 'Knight'), unit(101)]);
    const p = plan([row(1, 101, 2), row(2, 101, 1), row(3, 101, 1)], all);
    assert.equal(p.main.unit.id, 2);  // Halberdier ties the Knight; a no-gold main is allowed
});

test('support: the no-gold unit or Scorpion doing best against the strongest enemy the main does not beat', () => {
    const all = units([unit(1, 20, 'Knight'), unit(2, 0, 'Spearman'), unit(3, 75, 'Scorpion'), unit(4, 30, 'Archer'),
        unit(101), unit(102), unit(103)]);
    const rows = [row(1, 101, 1.5), row(1, 102, -1), row(1, 103, -1),
        row(2, 101, -1), row(2, 102, -1.2), row(2, 103, 1),     // wins against the weaker hole
        row(3, 101, -1), row(3, 102, -0.5), row(3, 103, -1),    // only softens the stronger hole
        row(4, 101, -1), row(4, 102, -1), row(4, 103, -1)];     // the Archer costs gold: never support
    const p = plan(rows, all);
    assert.equal(p.main.unit.id, 1);
    assert.deepEqual(p.holes, [102, 103]);  // 102 is the stronger enemy unit
    assert.equal(p.support.unit.id, 3);
    assert.deepEqual([p.supportReason, p.supportTarget], ['threat', 102]);
    assert.deepEqual(p.additions.map(a => [a.entry.unit.id, a.covers]), [[2, [103]]]);
});

test('support: when the main beats everything, the biggest help on its weakest wins', () => {
    const all = units([unit(1, 20, 'Knight'), unit(2, 0, 'Spearman'), unit(101), unit(102)]);
    const p = plan([row(1, 101, 0.2), row(1, 102, 1.5), row(2, 101, 0.9), row(2, 102, -1)], all);
    assert.equal(p.main.unit.id, 1);
    assert.deepEqual(p.holes, []);
    assert.deepEqual([p.support.unit.id, p.supportReason], [2, 'weak_wins']);
});

test('enemy units the pair cannot beat get the best unit doing better than both, or are unanswered', () => {
    const all = units([unit(1, 20, 'Knight'), unit(2, 0, 'Spearman'), unit(3, 30, 'Archer'), unit(4, 30, 'Crossbow'),
        unit(101), unit(102), unit(103)]);
    const rows = [row(1, 101, 2), row(1, 102, -1), row(1, 103, -1),
        row(2, 101, 1), row(2, 102, -0.5), row(2, 103, -1),
        row(3, 101, -1), row(3, 102, 0.4), row(3, 103, -1),
        row(4, 101, -1), row(4, 102, 0.8), row(4, 103, -1)];
    const p = plan(rows, all);
    assert.equal(p.main.unit.id, 1);
    assert.equal(p.support.unit.id, 2);
    assert.deepEqual(p.additions.map(a => [a.entry.unit.id, a.covers]), [[4, [102]]]);
    assert.deepEqual(p.unanswered, [103]);
    // A unit that still loses but loses less than both counts as the better counter.
    const q = plan(rows.map(r => r[0] === 3 && r[1] === 103 ? row(3, 103, -0.2) : r), all);
    assert.deepEqual(q.additions.map(a => [a.entry.unit.id, a.covers]), [[4, [102]], [3, [103]]]);
    assert.deepEqual(q.unanswered, []);
});

test('the right-hand plan reads the same rows from the other side', () => {
    assert.deepEqual(invertMatchup(row(1, 101, 0.7)), [101, 1, 'b_win', 'observed', 27, 27, '', 0, 1, -0.7]);
    const all = units([unit(1), unit(101), unit(102)]);
    const plans = build([row(1, 101, 0.7), row(1, 102, -0.2)], all);
    assert.equal(plans.left.main.unit.id, 1);
    assert.equal(plans.right.main.unit.id, 102);
    assert.equal(plans.right.main.vs.get(1).value, 0.2);
});

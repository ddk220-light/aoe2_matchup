import test from 'node:test';
import assert from 'node:assert/strict';
import {buildAdvisorRecommendations as build, unitWeight, invertMatchup} from '../apps/web/src/features/advisor/model.mjs';

const unit = (id, gold = 20, name = `Unit ${id}`) => ({id, key: `unit-${id}`, name, costs: {food: 50, wood: 0, gold}});
function matrix(own, enemy, outcome) {
    return own.flatMap(a => enemy.map(b => [a.id, b.id, outcome(a.id, b.id), 'observed', 27, 19, 'source-tier', 0, 1]));
}

test('gold is 1, every zero-gold variant is 0.5, and Scorpions have no siege discount', () => {
    assert.equal(unitWeight(unit(1)), 1);
    assert.equal(unitWeight(unit(2, 0, 'Trash Crossbowman')), 0.5);
    assert.equal(unitWeight(unit(3, 75, 'Heavy Scorpion')), 1);
});

test('beating a broad enemy threat outweighs collecting more harmless wins', () => {
    const own = [unit(1), unit(2), unit(3), unit(4), unit(5), unit(6, 0)];
    const enemy = [unit(101), unit(102), unit(103)];
    const rows = matrix(own, enemy, (a, b) => (a === 1) === (b === 101) ? 'a_win' : 'b_win');
    const plan = build(rows, [...own, ...enemy]).left;
    assert.equal(plan.main.unit.id, 1);
    assert.equal(plan.main.wins.length, 1);
    assert.equal(plan.threats.get(101), 5.5);
    assert.equal(plan.main.score, 5.5);
    assert.equal(plan.alternatives[0].score, 4);
});

test('an enemy with no wins still has its basic resource weight', () => {
    const own = [unit(1), unit(2, 0)], enemy = [unit(101), unit(102, 0)];
    const plan = build(matrix(own, enemy, () => 'a_win'), [...own, ...enemy]).left;
    assert.equal(plan.threats.get(101), 1);
    assert.equal(plan.threats.get(102), 0.5);
    assert.equal(plan.main.score, 1.5);
    assert.equal(plan.uncovered.length, 0);
});

test('trash support prioritizes dangerous counters to its main over more cheap counters', () => {
    const own = [unit(1), unit(2, 0), unit(3, 0), unit(4)], enemy = [unit(101), unit(102, 0), unit(103, 0), unit(104)];
    const wins = new Set(['1:104', '2:101', '3:102', '3:103', '4:102', '4:103']);
    const rows = matrix(own, enemy, (a,b) => wins.has(`${a}:${b}`) ? 'a_win' : 'b_win');
    const plan = build(rows, [...own, ...enemy]).left;
    assert.equal(plan.main.unit.id, 1);
    assert.equal(plan.sidekick.unit.id, 2);
    assert.equal(plan.sidekick.coverScore, 3.5);
    assert.deepEqual(plan.sidekick.covers.map(row => row[1]), [101]);
    assert.deepEqual(plan.uncovered.map(row => row[1]), [102, 103]);
    assert.ok(plan.alternatives.every(entry => ![1,2].includes(entry.unit.id)));
});

test('a close result cannot be counted as a winning sidekick counter', () => {
    const own = [unit(1), unit(2, 0)], enemy = [unit(101), unit(102)];
    const rows = matrix(own, enemy, (a,b) => b === 101 ? (a === 1 ? 'b_win' : 'close_uncertain') : a === 1 ? 'a_win' : 'b_win');
    const plan = build(rows, [...own, ...enemy]).left;
    assert.equal(plan.sidekick.covers.length, 0);
    assert.equal(plan.sidekick.holdsClose.length, 1);
    assert.equal(plan.sidekick.coverScore, 0);
    assert.deepEqual(plan.uncovered.map(row => row[1]), [101]);
});

test('main prefers viable gold; support stays no-gold; alternatives are three distinct winners', () => {
    const own = [unit(1,20,'A'), unit(2,0), unit(3,20,'B'), unit(4,20,'C'), unit(5,20,'D'), unit(6,20,'E'), unit(7,20,'F'), unit(8,20,'No wins')];
    const enemy = [unit(101), unit(102)];
    const rows = matrix(own, enemy, a => a === 8 ? 'b_win' : 'a_win');
    const plan = build(rows, [...own, ...enemy]).left;
    assert.equal(plan.main.unit.id, 1);
    assert.equal(plan.sidekick.unit.id, 2);
    assert.deepEqual(plan.alternatives.map(entry => entry.unit.id), [3,4,5]);
    assert.equal(new Set([plan.main, plan.sidekick, ...plan.alternatives].map(entry => entry.unit.id)).size, 5);
});

test('when no gold unit can win, use the effective no-gold main and a distinct support', () => {
    const own = [unit(1),unit(2,0),unit(3,0)], enemy = [unit(101)];
    const plan = build(matrix(own, enemy, a => a === 2 ? 'a_win' : 'b_win'), [...own,...enemy]).left;
    assert.equal(plan.main.unit.id, 2);
    assert.equal(plan.sidekick.unit.id, 3);
    assert.deepEqual(plan.alternatives, []);
});

test('swapping sides preserves directed outcomes and army counts without changing source rows', () => {
    const own = [unit(1),unit(2,0)], enemy = [unit(101),unit(102,0)];
    const rows = matrix(own,enemy,(a,b) => a === 1 && b === 102 ? 'a_win' : 'b_win');
    const original = structuredClone(rows), catalog = [...own,...enemy];
    const first = build(rows,catalog), reverse = build(rows.map(invertMatchup),catalog);
    assert.equal(first.right.main.unit.id, reverse.left.main.unit.id);
    assert.equal(first.right.main.score, reverse.left.main.score);
    assert.equal(first.right.sidekick.unit.id, reverse.left.sidekick.unit.id);
    assert.equal(reverse.left.main.matches[0][4], 19);
    assert.equal(reverse.left.main.matches[0][5], 27);
    assert.deepEqual(rows, original);
});

test('evidence labels and flags never affect recommendations or their scores', () => {
    const own = [unit(1),unit(2,0)], enemy = [unit(101),unit(102,0)];
    const rows = matrix(own,enemy,(a,b) => a === 1 || b === 101 ? 'a_win' : 'b_win');
    const changed = rows.map(row => [row[0],row[1],row[2],'predicted_unvalidated',row[4],row[5],'other-tier',3,999]);
    const a = build(rows,[...own,...enemy]), b = build(changed,[...own,...enemy]);
    for (const side of ['left','right']) {
        assert.equal(a[side].main.unit.id,b[side].main.unit.id);
        assert.equal(a[side].main.score,b[side].main.score);
        assert.equal(a[side].sidekick?.unit.id,b[side].sidekick?.unit.id);
        assert.equal(a[side].sidekick?.coverScore,b[side].sidekick?.coverScore);
    }
});

test('one additional unit can answer multiple remaining threats using winning matchups', () => {
    const own = [unit(1),unit(2,0),unit(3),unit(4),unit(5)];
    const enemy = [unit(101),unit(102,0),unit(103,0)];
    const wins = new Set(['1:101','3:102','3:103','4:102']);
    const rows = matrix(own,enemy,(a,b) => wins.has(`${a}:${b}`) ? 'a_win' : 'b_win');
    const plan = build(rows,[...own,...enemy]).left;
    assert.equal(plan.main.unit.id,1);
    assert.equal(plan.sidekick.unit.id,2);
    assert.equal(plan.additions.length,1);
    assert.equal(plan.additions[0].unit.id,3);
    assert.deepEqual(new Set(plan.additions[0].covers.map(row=>row[1])),new Set([102,103]));
    assert.ok(plan.additions[0].covers.every(row=>row[0]===3 && row[2]==='a_win'));
    assert.deepEqual(plan.unanswered,[]);
});

test('a remaining threat with no winning counter stays explicit, including close-only options', () => {
    const own = [unit(1),unit(2,0),unit(3)],enemy = [unit(101),unit(102)];
    const rows = matrix(own,enemy,(a,b) => b===101 && a===1 ? 'a_win' : b===102 && a===3 ? 'close_uncertain' : 'b_win');
    const plan = build(rows,[...own,...enemy]).left;
    assert.equal(plan.main.unit.id,1);
    assert.deepEqual(plan.additions,[]);
    assert.deepEqual(plan.unanswered.map(row=>row[1]),[102]);
});

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
            excludedMain: ['Scorpion', 'Heavy Scorpion'], supportExtra: []});
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

test('support: the no-gold unit doing best against the strongest enemy the main does not beat', () => {
    const all = units([unit(1, 20, 'Knight'), unit(2, 0, 'Spearman'), unit(3, 0, 'Skirmisher'), unit(4, 30, 'Archer'),
        unit(101), unit(102), unit(103)]);
    const rows = [row(1, 101, 1), row(1, 102, -1), row(1, 103, -1),     // only the Knight beats 101 (strongest)
        row(2, 101, -2.5), row(2, 102, -1.2), row(2, 103, 0.3),     // wins against the weaker hole
        row(3, 101, -2.5), row(3, 102, -0.5), row(3, 103, -1),      // only softens the stronger hole
        row(4, 101, -1), row(4, 102, -1), row(4, 103, -1)];     // the Archer costs gold: never support
    const p = plan(rows, all);
    assert.equal(p.main.unit.id, 1);
    assert.deepEqual(p.holes, [102, 103]);  // 102 is the stronger enemy unit
    assert.equal(p.support.unit.id, 3);
    assert.deepEqual([p.supportReason, p.supportTarget], ['threat', 102]);
    assert.deepEqual(p.additions.map(a => [a.entry.unit.id, a.covers]), [[2, [103]]]);
});

test('Scorpions are never the support, but can be an extra unit', () => {
    const all = units([unit(1, 20, 'Knight'), unit(2, 75, 'Heavy Scorpion'), unit(3, 0, 'Spearman'), unit(101), unit(102)]);
    const p = plan([row(1, 101, 1), row(1, 102, -1), row(2, 101, -1), row(2, 102, 1), row(3, 101, 0.5), row(3, 102, -1.5)], all);
    assert.equal(p.main.unit.id, 1);
    assert.equal(p.support.unit.id, 3);
    assert.deepEqual(p.additions.map(a => [a.entry.unit.id, a.covers]), [[2, [102]]]);
});

test('support: when the main beats everything, the biggest help on its weakest wins', () => {
    const all = units([unit(1, 20, 'Knight'), unit(2, 0, 'Spearman'), unit(101), unit(102)]);
    const p = plan([row(1, 101, 0.2), row(1, 102, 1.5), row(2, 101, 0.9), row(2, 102, -1)], all);
    assert.equal(p.main.unit.id, 1);
    assert.deepEqual(p.holes, []);
    assert.deepEqual([p.support.unit.id, p.supportReason], [2, 'weak_wins']);
});

test('main and support are chosen as a pair: strength of the enemy units beaten first, then pair score', () => {
    // Like Armenians vs Aztecs: the Champion scores best alone, but no support fixes its loss; the
    // Bowman's one loss (to 102) is fixed by the Light Cavalry, so that pair beats every enemy unit.
    const all = units([unit(1, 20, 'Champion'), unit(2, 45, 'Bowman'), unit(3, 0, 'Light Cavalry'),
        unit(101), unit(102), unit(103)]);
    const rows = [row(1, 101, -0.4), row(1, 102, 1.3), row(1, 103, 1),
        row(2, 101, 0.6), row(2, 102, -0.7), row(2, 103, 0.4),
        row(3, 101, -0.4), row(3, 102, 0.9), row(3, 103, -0.5)];
    const p = plan(rows, all);
    assert.ok(p.score.get(1) > p.score.get(2));
    assert.deepEqual([p.main.unit.id, p.support.unit.id, p.pairWins], [2, 3, 3]);
});

test('pairs that beat the stronger enemy units win even with the same number of wins', () => {
    // Both pairs beat two of three; Eagle + Pike leaves the strongest enemy (101) unbeaten.
    const all = units([unit(1, 50, 'Eagle'), unit(2, 30, 'Jaguar'), unit(3, 0, 'Pikeman'), unit(4, 0, 'Skirmisher'),
        unit(101), unit(102), unit(103)]);
    const rows = [row(1, 101, -0.5), row(1, 102, 1.2), row(1, 103, 1.2),
        row(2, 101, 0.5), row(2, 102, -0.4), row(2, 103, 0.4),
        row(3, 101, -0.6), row(3, 102, -0.5), row(3, 103, 0.3),
        row(4, 101, -0.7), row(4, 102, -0.3), row(4, 103, 0.4)];
    const p = plan(rows, all);
    assert.ok(p.multiplier.get(101) > p.multiplier.get(102));
    assert.equal(p.main.unit.id, 2);
    assert.equal(p.pairWins, 2);
});

test('enemy units the pair cannot beat get the best unit doing better than both, or are unanswered', () => {
    const all = units([unit(1, 20, 'Knight'), unit(2, 0, 'Spearman'), unit(3, 30, 'Archer'), unit(4, 30, 'Crossbow'),
        unit(101), unit(102), unit(103), unit(104)]);
    const rows = [row(1, 101, 2), row(1, 102, 1), row(1, 103, -1), row(1, 104, -1),
        row(2, 101, 1), row(2, 102, -0.5), row(2, 103, -1), row(2, 104, -1),
        row(3, 101, -1), row(3, 102, -2.5), row(3, 103, -0.2), row(3, 104, -1),   // still loses, but less
        row(4, 101, -1), row(4, 102, -2.5), row(4, 103, -1), row(4, 104, 0.8)];
    const p = plan(rows, all);
    assert.deepEqual([p.main.unit.id, p.support.unit.id], [1, 2]);
    assert.deepEqual(p.additions.map(a => [a.entry.unit.id, a.covers]).sort(), [[3, [103]], [4, [104]]]);
    assert.deepEqual(p.unanswered, []);
    const q = plan(rows.map(r => r[0] === 3 && r[1] === 103 ? row(3, 103, -1) : r), all);
    assert.deepEqual(q.unanswered, [103]);
});

test('siege fallback: siege-target enemies are left to the civ\'s siege, before any extra unit', () => {
    const civ = (u, c) => ({...u, civilization: c});
    const all = units([civ(unit(1, 20, 'Knight'), 'A'), civ(unit(2, 0, 'Spearman'), 'A'), civ(unit(3, 30, 'Heavy Scorpion'), 'A'),
        civ(unit(101, 20, 'Arbalester'), 'B'), civ(unit(102, 20, 'Paladin'), 'B')]);
    const rows = [row(1, 101, -1), row(1, 102, 1), row(2, 101, -1), row(2, 102, 0.5), row(3, 101, 0.4), row(3, 102, -1)];
    const siege = {targets: ['Arbalester'], civs: {A: ['Siege Onager'], B: []}};
    const p = plan(rows, all, undefined, siege);
    assert.deepEqual([p.siege, p.siegeCovers], [['Siege Onager'], [101]]);
    assert.deepEqual(p.additions, []);
    const q = plan(rows, all);  // without siege the Heavy Scorpion is the extra unit
    assert.deepEqual(q.additions.map(a => [a.entry.unit.id, a.covers]), [[3, [101]]]);
});

test('the right-hand plan reads the same rows from the other side', () => {
    assert.deepEqual(invertMatchup(row(1, 101, 0.7)), [101, 1, 'b_win', 'observed', 27, 27, '', 0, 1, -0.7]);
    const all = units([unit(1), unit(101), unit(102)]);
    const plans = build([row(1, 101, 0.7), row(1, 102, -0.2)], all);
    assert.equal(plans.left.main.unit.id, 1);
    assert.equal(plans.right.main.unit.id, 102);
    assert.equal(plans.right.main.vs.get(1).value, 0.2);
});

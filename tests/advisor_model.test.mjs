// Behaviour of the Revision 4 advisor model on small hand-made rosters. The full parity check
// against the Python reference (all 3,080 plans) is tests/advisor/rev4-parity.test.mjs.
import test from 'node:test';
import assert from 'node:assert/strict';
import {buildAdvisorRecommendations as build, cheaperToUpgrade, helpValue, invertMatchup, pyRound, rowInfo, struggles,
    WEIGHTS} from '../apps/web/src/features/advisor/model.mjs';

const unit = (id, gold = 20, name = `Unit ${id}`, full = 100) => ({id, key: `unit-${id}`, name, costs: {food: 50, wood: 0, gold}, full_research_vm: full});
const MIRROR = {dominance: 'outclassed_loss', kite: 'kited_loss', plain_win: 'plain_loss', power_win: 'cheap_loss',
    eco_win: 'power_win', cheap_loss: 'power_win', plain_loss: 'plain_win', kited_loss: 'kite', outclassed_loss: 'dominance'};
/** A served row from a's side; `cat` is a's category; hp is the winner's HP. */
function row(a, b, cat, {hp = 0.6, vmA = 100, vmB = 100, evidence = 'observed'} = {}) {
    if (cat === 'close') return [a, b, 'close_uncertain', evidence, 27, 27, '', 0, 1, 'close', 'close', null, vmA, vmB];
    if (cat === 'pending_win' || cat === 'pending_loss') return [a, b, cat === 'pending_win' ? 'a_win' : 'b_win', 'inferred', 27, 27, '', 0, 1, 'pending', 'pending', null, null, null];
    const won = ['dominance', 'kite', 'plain_win', 'power_win'].includes(cat);
    return [a, b, won ? 'a_win' : 'b_win', evidence, 27, 27, '', 0, 1, cat, MIRROR[cat], hp, vmA, vmB];
}
const plan = (own, enemy, rows) => build(rows, [...own, ...enemy]).left;

test('weights and settings are the default Revision 4 set', () => {
    assert.deepEqual({...WEIGHTS}, {dominance: 1.5, kite: 1.5, plain_win: 1, power_win: 0.6, eco_win: 0.25, close: 0,
        cheap_loss: -0.25, plain_loss: -0.5, kited_loss: -0.75, outclassed_loss: -0.75});
});

test('Scorpions are never the main; a gold main with a win is preferred over a stronger trash unit', () => {
    const own = [unit(1, 75, 'Heavy Scorpion'), unit(2, 0, 'Halberdier'), unit(3, 20, 'Knight')];
    const enemy = [unit(101), unit(102)];
    const rows = [row(1, 101, 'dominance'), row(1, 102, 'dominance'), row(2, 101, 'dominance'), row(2, 102, 'plain_win'),
        row(3, 101, 'plain_win'), row(3, 102, 'plain_loss')];
    const p = plan(own, enemy, rows);
    assert.equal(p.topOverall.unit.id, 1);
    assert.equal(p.topEligible.unit.id, 2);
    assert.equal(p.main.unit.id, 3);
});

test('opponent strength: wins over the strongest enemy count most, losses to it least', () => {
    const own = [unit(1), unit(2)], enemy = [unit(101), unit(102)];
    // Enemy 101 beats both of our units (strong), 102 loses to both (weak).
    const p = plan(own, enemy, [row(1, 101, 'plain_loss'), row(1, 102, 'plain_win'), row(2, 101, 'plain_loss'), row(2, 102, 'plain_win')]);
    assert.equal(p.strength.get(101), 1.5);
    assert.equal(p.strength.get(102), 0.5);
    // Each own unit: loss to 101 (-0.5 x (2 - 1.5)) + win over 102 (1.0 x 0.5).
    assert.equal(p.main.adv, -0.25 + 0.5);
});

test('support is trash or a Scorpion and helps where the main loses or struggles', () => {
    const own = [unit(1, 20, 'Paladin'), unit(2, 0, 'Pikeman'), unit(3, 75, 'Heavy Scorpion'), unit(4, 20, 'Arbalester')];
    const enemy = [unit(101, 20, 'Camel'), unit(102, 20, 'Archer')];
    const rows = [
        row(1, 101, 'plain_loss'), row(1, 102, 'plain_win', {hp: 0.3}),          // main loses to 101, struggles vs 102
        row(2, 101, 'plain_win'), row(2, 102, 'plain_loss'),                    // trash turns the loss into a win
        row(3, 101, 'plain_loss'), row(3, 102, 'plain_win', {hp: 0.9}),         // Scorpion: same win, more HP
        row(4, 101, 'dominance'), row(4, 102, 'dominance'),                     // gold: never support
    ];
    const p = plan(own, enemy, rows);
    assert.equal(p.main.unit.id, 4);
    const q = plan(own.filter(u => u.id !== 4), enemy, rows.filter(r => r[0] !== 4));
    assert.equal(q.main.unit.id, 1);
    assert.deepEqual(q.targets.map(t => t[1]), ['loss', 'struggle']);
    assert.equal(q.support.entry.unit.id, 2);
    assert.deepEqual(q.support.helps.map(h => [h.opp, h.why, h.value]), [[101, 'better', 1.5]]);
    const scorpion = q.supportCandidates.find(c => c.entry.unit.id === 3);
    assert.deepEqual(scorpion.helps.map(h => [h.opp, h.why, h.value]), [[102, 'more_hp', 0.25]]);
    assert.ok(q.supportCandidates.every(c => c.entry.unit.costs.gold === 0 || c.entry.unit.name.includes('Scorpion')));
});

test('same-result help: 15 HP points more or a 25% cheaper army', () => {
    const win = (hp, vm) => rowInfo(row(1, 2, 'plain_win', {hp, vmA: vm}));
    assert.deepEqual(helpValue(win(0.65, 100), win(0.5, 100)), [0.25, 'more_hp']);
    assert.deepEqual(helpValue(win(0.64, 100), win(0.5, 100)), [0, null]);
    assert.deepEqual(helpValue(win(0.5, 75), win(0.5, 100)), [0.25, 'cheaper']);
    assert.deepEqual(helpValue(win(0.5, 76), win(0.5, 100)), [0, null]);
    assert.deepEqual(helpValue(rowInfo(row(1, 2, 'cheap_loss')), rowInfo(row(1, 2, 'outclassed_loss'))), [0.5, 'better']);
});

test('struggles: close, any power win, a win below 50% HP', () => {
    assert.equal(struggles(rowInfo(row(1, 2, 'close'))), true);
    assert.equal(struggles(rowInfo(row(1, 2, 'power_win', {hp: 0.97}))), true);
    assert.equal(struggles(rowInfo(row(1, 2, 'plain_win', {hp: 0.49}))), true);
    assert.equal(struggles(rowInfo(row(1, 2, 'dominance', {hp: 0.5}))), false);
    assert.equal(struggles(rowInfo(row(1, 2, 'pending_win'))), false);
});

test('eco wins need no addition; a real loss the support does not beat gets a winning counter', () => {
    const own = [unit(1, 20, 'Main'), unit(2, 0, 'Trash'), unit(3, 20, 'Counter')];
    const enemy = [unit(101), unit(102), unit(103)];
    const rows = [row(1, 101, 'eco_win', {hp: 0.3}), row(1, 102, 'plain_loss'), row(1, 103, 'dominance'),
        row(2, 101, 'plain_loss'), row(2, 102, 'plain_loss'), row(2, 103, 'plain_loss'),
        row(3, 101, 'plain_loss'), row(3, 102, 'plain_win'), row(3, 103, 'plain_loss')];
    const p = plan(own, enemy, rows);
    assert.equal(p.main.unit.id, 1);
    assert.deepEqual(p.targets.map(t => t[0]).sort(), [101, 102]);
    assert.deepEqual(p.additions.map(a => [a.entry.unit.id, a.covers]), [[3, [102]]]);
    assert.deepEqual(p.unanswered, []);
});

test('pending (inferred) cells count as plain win / plain loss and are flagged', () => {
    assert.deepEqual(rowInfo(row(1, 2, 'pending_win')), {cat: 'plain_win', won: true, pending: true, hpOwn: null, hpWinner: null, vmOwn: null, vmOpp: null});
    assert.equal(rowInfo(row(1, 2, 'pending_loss')).cat, 'plain_loss');
    assert.equal(rowInfo(row(1, 2, 'plain_win', {evidence: 'identity'})).cat, 'close');
});

test('inverting a row swaps both sides, categories and army investment', () => {
    const r = row(1, 2, 'power_win', {hp: 0.4, vmA: 300, vmB: 150});
    r[4] = 20;
    const inv = invertMatchup(r);
    assert.deepEqual(inv, [2, 1, 'b_win', 'observed', 27, 20, '', 0, 1, 'cheap_loss', 'power_win', 0.4, 150, 300]);
    assert.deepEqual(invertMatchup(inv), r);
    assert.deepEqual(rowInfo(inv), {cat: 'cheap_loss', won: false, pending: false, hpWinner: 0.4, hpOwn: 0, vmOwn: 150, vmOpp: 300});
    // Old nine-field rows still work (plain results).
    assert.equal(rowInfo([1, 2, 'a_win', 'observed', 27, 27, '', 0, 1]).cat, 'plain_win');
});

test('the source rows are never modified', () => {
    const own = [unit(1), unit(2, 0)], enemy = [unit(101), unit(102, 0)];
    const rows = [row(1, 101, 'plain_win'), row(1, 102, 'plain_loss'), row(2, 101, 'plain_loss'), row(2, 102, 'dominance')];
    const copy = structuredClone(rows);
    const both = build(rows, [...own, ...enemy]);
    assert.deepEqual(rows, copy);
    assert.equal(build(rows.map(invertMatchup), [...own, ...enemy]).left.main.unit.id, both.right.main.unit.id);
});

test('pyRound rounds like Python round(): ties to even on the exact binary value', () => {
    assert.equal(pyRound(9.1328125, 6), 9.132812);
    assert.equal(pyRound(0.375, 2), 0.38);
    assert.equal(pyRound(2.675, 2), 2.67);
    assert.equal(pyRound(2.5, 0), 2);
    assert.equal(pyRound(-0.125, 2), -0.12);
});

test('cheaper-to-upgrade badge: own full research package at most half the opponent’s', () => {
    assert.equal(cheaperToUpgrade(unit(1, 20, 'A', 50), unit(2, 20, 'B', 100)), true);
    assert.equal(cheaperToUpgrade(unit(1, 20, 'A', 51), unit(2, 20, 'B', 100)), false);
    assert.equal(cheaperToUpgrade(unit(1, 20, 'A', null), unit(2, 20, 'B', 100)), false);
});

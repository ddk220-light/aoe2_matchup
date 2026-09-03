import { test } from "node:test";
import assert from "node:assert/strict";
import { createSimulation } from "../../../apps/website/static/js/engine/index.js";
import { readFileSync } from "node:fs";

const dicts = JSON.parse(readFileSync("tools/simjs/golden/combat_dicts.json", "utf8"));
const CHAMP = dicts["Franks|champion"];
const JAG = dicts["Aztecs|elite_jaguar_warrior_aztecs"];

function makeSim(seed) {
    return createSimulation({
        teams: [
            { combatDict: CHAMP, slug: "champion", civ: "Franks", count: 10 },
            { combatDict: JAG, slug: "elite_jaguar_warrior_aztecs", civ: "Aztecs", count: 10 },
        ],
        seed,
    });
}

test("same seed => identical hash stream for 600 ticks", () => {
    const a = makeSim(11), b = makeSim(11);
    assert.equal(a.stateHash(), b.stateHash()); // spawn state identical
    for (let i = 0; i < 600; i++) {
        a.step(); b.step();
        assert.equal(a.stateHash(), b.stateHash(), `diverged at tick ${i + 1}`);
    }
});

test("different seeds diverge within the fight", () => {
    const a = makeSim(1), b = makeSim(2);
    let diverged = a.stateHash() !== b.stateHash();
    for (let i = 0; i < 3600 && !diverged; i++) {
        a.step(); b.step();
        diverged = a.stateHash() !== b.stateHash();
    }
    assert.ok(diverged);
});

test("runToEnd finishes a melee fight with a winner and consistent survivors", () => {
    const r = makeSim(5).runToEnd(600);
    assert.ok([0, 1, 2].includes(r.winner));
    assert.ok(r.alive1 === 0 || r.alive2 === 0);
    assert.ok(r.time > 0 && r.time <= 600);
});

test("relics delta only applies to Lithuanian relic units", () => {
    const base = createSimulation({
        teams: [
            { combatDict: CHAMP, slug: "champion", civ: "Franks", count: 1, relics: 0 },
            { combatDict: JAG, slug: "elite_jaguar_warrior_aztecs", civ: "Aztecs", count: 1 },
        ],
        seed: 1,
    });
    assert.equal(base.team1[0].attack, CHAMP.attack); // non-Lithuanian: untouched
});

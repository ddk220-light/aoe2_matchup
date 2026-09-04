import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { calculateDamage } from "../src/combat/attacks.js";
import {
  estimateTimeToKill,
  summarizeMatchup,
} from "../src/combat/matchup-summary.js";


async function fixture(name) {
  return JSON.parse(await readFile(
    new URL(`../fixtures/unit_stats/${name}`, import.meta.url),
    "utf8",
  ));
}


const paladin = await fixture("paladin_spanish_imperial.json");
const arbalester = await fixture("arbalester_chinese_imperial.json");
const halberdier = await fixture("halberdier_bulgarians_imperial.json");
const urumi = await fixture("elite_urumi_swordsman_dravidians_imperial.json");
const konnik = await fixture("elite_konnik_bulgarians_imperial.json");


test("matchup damage per hit delegates to the V3 armor-class calculation", () => {
  const summary = summarizeMatchup(paladin, arbalester);
  assert.equal(summary.damagePerHit, calculateDamage(
    { mechanics: paladin, hp: paladin.hp },
    { mechanics: arbalester, hp: arbalester.hp },
  ));
  assert.ok(summary.damagePerSecond > 0);
  assert.ok(summary.timeToKillSeconds > 0);
});


test("applicable armor-class bonus is called out for this opponent", () => {
  const summary = summarizeMatchup(halberdier, paladin);
  assert.ok(summary.bonusDamage.some(({ label, damage }) => (
    label === "cavalry" && damage > 0
  )));
  assert.ok(summary.callouts.some((line) => line.includes("bonus damage vs cavalry")));
});


test("one-on-one clock includes an opening melee charge", () => {
  const charged = estimateTimeToKill(urumi, paladin);
  const ordinary = estimateTimeToKill({
    ...urumi,
    melee_charge: null,
    effects: {
      ...urumi.effects,
      charge_attack_melee: 0,
      charge_recharge_time: 0,
    },
  }, paladin);
  assert.ok(charged < ordinary);
});


test("one-on-one clock includes a target's dismounted form", () => {
  const withDismount = estimateTimeToKill(paladin, konnik);
  const mountedOnly = estimateTimeToKill(paladin, {
    ...konnik,
    dismount_form: null,
  });
  assert.ok(withDismount > mountedOnly);
});


test("an exported first-hit shield delays time to kill generically", () => {
  const unshielded = estimateTimeToKill(paladin, arbalester);
  const shielded = estimateTimeToKill(paladin, {
    ...arbalester,
    effects: { ...arbalester.effects, block_first_melee: true },
  });
  assert.ok(shielded > unshielded);
});

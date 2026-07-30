import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { runTapeFight } from "../../tools/simjs/tape_runner.mjs";
import { buildFight, STEP } from "../../tools/simjs/headless.mjs";

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const dicts = JSON.parse(readFileSync(path.join(REPO, "data/validation/tape_combat_dicts.json"), "utf8"));
const plan = JSON.parse(readFileSync(path.join(REPO, "data/validation/tape_plan.json"), "utf8")).rows;

test("runTapeFight returns a complete, well-formed record", () => {
    const r = runTapeFight({ dicts, plan_row: plan[0], scale: "tape", seed: 1, maxSeconds: 600 });
    for (const k of ["winner", "end_reason", "game_time_s", "team1_hp_pct",
                     "team1_survivors", "team2_hp_pct", "team2_survivors",
                     "signed_score", "wall_ms"]) {
        assert.ok(r[k] !== undefined, `missing ${k}`);
    }
    assert.ok([0, 1, 2].includes(r.winner), `winner must be adjudicated, got ${r.winner}`);
    assert.ok(["eliminated", "time_cap"].includes(r.end_reason));
    assert.ok(r.team1_hp_pct >= 0 && r.team1_hp_pct <= 1);
    assert.ok(r.team2_hp_pct >= 0 && r.team2_hp_pct <= 1);
});

test("same seed is deterministic; seed 0 aliases seed 1", () => {
    const a = runTapeFight({ dicts, plan_row: plan[0], scale: "tape", seed: 3, maxSeconds: 600 });
    const b = runTapeFight({ dicts, plan_row: plan[0], scale: "tape", seed: 3, maxSeconds: 600 });
    assert.equal(a.game_time_s, b.game_time_s);
    assert.equal(a.signed_score, b.signed_score);

    const s0 = runTapeFight({ dicts, plan_row: plan[0], scale: "tape", seed: 0, maxSeconds: 600 });
    const s1 = runTapeFight({ dicts, plan_row: plan[0], scale: "tape", seed: 1, maxSeconds: 600 });
    assert.equal(s0.game_time_s, s1.game_time_s, "seed 0 must alias seed 1 (rng.js `|| 1`)");
});

test("signed_score is the hp%-difference fallback the Python rig used", () => {
    const r = runTapeFight({ dicts, plan_row: plan[0], scale: "tape", seed: 1, maxSeconds: 600 });
    const expected = (r.team1_hp_pct - r.team2_hp_pct) * 100.0;
    assert.ok(Math.abs(r.signed_score - expected) < 1e-9);
});

// Added in response to code review: the three tests above (plan-mandated,
// left unmodified) never exercise the "denominator includes corpses"
// semantic -- they only recompute `expected` from the same team*_hp_pct the
// implementation already returned, so they'd still pass even if hpPct's
// `max` accumulator skipped dead units. This test drives the identical fight
// independently via buildFight/STEP (NOT via runTapeFight, and NOT by
// calling the unexported hpPct) so it fails if that denominator regresses.
test("team_hp_pct denominator includes corpses, not just survivors", () => {
    const plan_row = plan.find(
        (pr) => pr.plan_id === "elite_blackwood_archer_tupi__vs__Bengalis_elite_elephant",
    );
    const scale = "tape";
    const seed = 1;

    const r = runTapeFight({ dicts, plan_row, scale, seed, maxSeconds: 600 });

    // Independently replay the same spawn + tick loop tape_runner.mjs uses
    // internally, so we get our own copy of the post-fight sim state without
    // going through the function under test.
    const [n1, n2] = plan_row.counts[scale];
    const row = {
        civ1: plan_row.subject_civ, slug1: plan_row.subject_slug, n1,
        civ2: plan_row.opp_civ, slug2: plan_row.opp_slug, n2,
    };
    const sim = buildFight({ dicts, row, seed });
    const maxTicks = Math.round(600 * 60);
    let ticks = 0;
    while (sim.winner === null && ticks < maxTicks) {
        sim.step(STEP);
        ticks++;
    }

    const team1 = sim.team1;
    const living1 = team1.filter((u) => u.state !== "dead");
    // This plan row + seed is known (from the smoke run) to have team1 win
    // while losing units: confirm the fixture still has that shape so the
    // test doesn't silently pass vacuously if the fixture ever changes.
    assert.ok(living1.length > 0, "winning side must have survivors");
    assert.ok(living1.length < team1.length, "winning side must have taken at least one casualty");

    const livingHp = living1.reduce((s, u) => s + u.currentHp, 0);
    const livingMaxHp = living1.reduce((s, u) => s + u.maxHp, 0);
    const totalMaxHp = team1.reduce((s, u) => s + u.maxHp, 0); // includes corpses

    // The real (corpse-inclusive) percentage must equal living hp over the
    // WHOLE team's maxHp, computed here independently of tape_runner.mjs.
    const expectedCorpseInclusivePct = livingHp / totalMaxHp;
    assert.ok(
        Math.abs(r.team1_hp_pct - expectedCorpseInclusivePct) < 1e-9,
        `team1_hp_pct (${r.team1_hp_pct}) should equal living hp / whole-team maxHp ` +
        `(${expectedCorpseInclusivePct})`,
    );

    // And it must be strictly smaller than the survivors-only ratio, because
    // corpses inflate the denominator. If hpPct's `max` accumulator were
    // changed to skip dead units, team1_hp_pct would equal survivorsOnlyPct
    // instead (living/living == 1 when survivors are undamaged) and this
    // assertion would fail.
    const survivorsOnlyPct = livingHp / livingMaxHp;
    assert.ok(
        r.team1_hp_pct < survivorsOnlyPct,
        `team1_hp_pct (${r.team1_hp_pct}) should be strictly less than the survivors-only ` +
        `ratio (${survivorsOnlyPct}) because corpses are still counted in the denominator`,
    );
});

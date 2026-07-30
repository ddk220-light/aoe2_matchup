import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { runTapeFight } from "../../tools/simjs/tape_runner.mjs";

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

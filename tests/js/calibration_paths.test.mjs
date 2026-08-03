import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";

import { calibrationPaths } from "../../tools/simjs/calibration_paths.mjs";

test("calibration paths stay under the supplied repository", () => {
    const repo = path.resolve("C:/tmp/repo");
    const p = calibrationPaths(repo);
    assert.equal(p.root, path.join(repo, "calibration"));
    assert.equal(p.manifest, path.join(repo, "calibration/fixtures/manifest.json"));
    assert.equal(p.combatDicts, path.join(repo, "calibration/fixtures/combat_dicts.json"));
    assert.equal(p.spawns, path.join(repo, "calibration/fixtures/spawns.json"));
    assert.equal(p.fightSets, path.join(repo, "calibration/fixtures/fight_sets.json"));
    assert.equal(p.runs, path.join(repo, "calibration/runs"));
});

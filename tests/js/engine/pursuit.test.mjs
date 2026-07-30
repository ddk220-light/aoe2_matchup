// Target-thrash fix (docs/superpowers/specs/2026-07-29-target-thrash-design.md).
// Tests are added incrementally, one section per commit of the four-part fix:
//   (a) STUCK_PROGRESS_RATE -- the rate expression is a no-op at dt=1/60.
//   (b) the pursuing/receding exemption.
//   (c) the stale lastDistToTarget baseline re-stamp.
//   (d) the reachability swap.
import { test } from "node:test";
import assert from "node:assert/strict";
import { STUCK_PROGRESS_RATE } from "../../../apps/website/static/js/engine/constants.js";

// ---- (a): the rate expression must be an EXACT no-op at the current tick
// rate. This is the load-bearing IEEE-754 fact the whole step (a) rests on:
// if this ever stops being exactly 0.5, moveTowardTarget's stuck bar has
// silently changed behavior at 60fps and the calib byte-identity check
// (tools/simjs/calib_runner.mjs before/after, see task-10-report.md) would
// have caught it -- this test pins the same fact at the unit level.
test("STUCK_PROGRESS_RATE * dt(1/60) is bit-exact today's historical 0.5 literal", () => {
    const dt = 1 / 60;
    assert.equal(STUCK_PROGRESS_RATE * dt, 0.5);
    // Belt-and-braces: also confirm the rate itself is 1.0 tile/s (30px / 30px-per-tile).
    assert.equal(STUCK_PROGRESS_RATE, 30);
});

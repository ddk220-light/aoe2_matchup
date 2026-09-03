// THE PARITY GATE: proves the extracted engine (apps/website/static/js/engine/)
// reproduces tools/simjs/golden/panel.json — captured from the UNMODIFIED
// simulate.js — bit for bit, for all 205 fights.
//
//     node tools/simjs/parity_check.mjs            # the gate: exit 0 = bit-exact
//     node tools/simjs/parity_check.mjs --id champ-v-jaguar --seed 3   # one fight
//     node tools/simjs/parity_check.mjs --quiet    # only the verdict line
//
// This is the entire justification for calling the extraction "zero behaviour
// change". A mismatch is ALWAYS a bug in engine/ (or in headless.mjs's format) —
// never in the golden. Editing panel.json, adding a tolerance, rounding, or
// comparing "close enough" defeats the only check that the refactor was faithful.
// Legacy oddities (the CANVAS_WIDTH clamp that ignores this.W, etc.) are
// correct-by-parity: reproduce them, do not fix them.
//
// The comparison is JSON.stringify equality on { snapshots, final }, which is
// exact for doubles (JSON round-trips at full precision) and also catches key
// order, array length and null-vs-0 differences. On failure it walks the fight to
// the first divergent snapshot, unit and field and prints both values.
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { runFight, loadDicts, MAX_SECONDS } from "./headless.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIELDS = ["team", "idx", "x", "y", "hp", "state"];

const argv = process.argv.slice(2);
const flag = (name) => {
    const i = argv.indexOf(name);
    return i >= 0 && i + 1 < argv.length ? argv[i + 1] : null;
};
const onlyId = flag("--id");
const onlySeed = flag("--seed") != null ? Number(flag("--seed")) : null;
const quiet = argv.includes("--quiet");

const golden = JSON.parse(
    readFileSync(path.join(HERE, "golden/panel.json"), "utf8"),
);
const dicts = loadDicts();

// ---- the gate must not be silently weakenable ---------------------------------
// Without this, a truncated or re-captured-smaller panel.json still prints
// "PARITY OK — 5 fights bit-exact" and exits 0: fewer fights compared, same green
// verdict. panel.meta.json is the capture's own provenance record, so cross-check
// the panel against it before comparing anything. Failures exit 2 (a broken gate),
// never 1 (a genuine divergence) — the two must stay distinguishable in CI.
const meta = JSON.parse(
    readFileSync(path.join(HERE, "golden/panel.meta.json"), "utf8"),
);
const fail = (msg) => {
    console.error(`GATE BROKEN: ${msg}`);
    console.error("  the golden is the immutable baseline — do not edit it to make this pass");
    process.exit(2);
};
if (MAX_SECONDS !== meta.maxSeconds) {
    fail(
        `time cap mismatch — headless.mjs runs ${MAX_SECONDS}s, the golden was ` +
        `captured at ${meta.maxSeconds}s`,
    );
}
// Skipped when a filter is active: --id/--seed deliberately compare a subset.
if (onlyId == null && onlySeed == null && golden.length !== meta.fightCount) {
    fail(
        `panel.json holds ${golden.length} fights, panel.meta.json says the capture ` +
        `wrote ${meta.fightCount} — the golden is truncated or stale`,
    );
}

// Pinpoint where two fights first differ. Returns a printable multi-line report.
function describeDivergence(g, r) {
    const out = [];
    const n = Math.max(g.snapshots.length, r.snapshots.length);
    for (let s = 0; s < n; s++) {
        const gs = g.snapshots[s];
        const rs = r.snapshots[s];
        if (JSON.stringify(gs) === JSON.stringify(rs)) continue;
        if (!gs || !rs) {
            out.push(
                `  first difference at snapshot index ${s}: golden has ` +
                `${g.snapshots.length} snapshots, engine has ${r.snapshots.length}` +
                (gs ? ` (golden tick ${gs.tick}, engine ended earlier)` :
                      ` (engine tick ${rs.tick}, golden ended earlier)`),
            );
            return out.join("\n");
        }
        const prev = s > 0 ? g.snapshots[s - 1].tick : 0;
        out.push(
            `  first divergent snapshot: index ${s}, tick ${gs.tick} ` +
            `(engine tick ${rs.tick}) — diverged somewhere in ticks ${prev + 1}..${gs.tick}`,
        );
        if (gs.tick !== rs.tick) {
            out.push(`  tick mismatch: golden ${gs.tick} vs engine ${rs.tick}`);
            return out.join("\n");
        }
        if (gs.units.length !== rs.units.length) {
            out.push(
                `  unit-count mismatch: golden ${gs.units.length} vs engine ${rs.units.length}`,
            );
            return out.join("\n");
        }
        let shown = 0;
        for (let u = 0; u < gs.units.length; u++) {
            const gu = gs.units[u];
            const ru = rs.units[u];
            if (JSON.stringify(gu) === JSON.stringify(ru)) continue;
            const diffs = [];
            for (let f = 0; f < FIELDS.length; f++) {
                if (Object.is(gu[f], ru[f])) continue;
                const delta =
                    typeof gu[f] === "number" && typeof ru[f] === "number"
                        ? ` (delta ${ru[f] - gu[f]})`
                        : "";
                diffs.push(`${FIELDS[f]}: golden ${JSON.stringify(gu[f])} vs engine ${JSON.stringify(ru[f])}${delta}`);
            }
            out.push(`  unit ${u} (team ${gu[0]} idx ${gu[1]}): ${diffs.join("; ")}`);
            out.push(`    golden: ${JSON.stringify(gu)}`);
            out.push(`    engine: ${JSON.stringify(ru)}`);
            if (++shown >= 3) {
                out.push("    …(further units on this tick omitted)");
                break;
            }
        }
        return out.join("\n");
    }
    // Snapshots all matched — the difference is in the final block.
    const keys = ["winner", "time", "alive1", "alive2", "hp1", "hp2"];
    out.push("  snapshots are identical; final block differs:");
    for (const k of keys) {
        if (Object.is(g.final[k], r.final[k])) continue;
        out.push(`    ${k}: golden ${JSON.stringify(g.final[k])} vs engine ${JSON.stringify(r.final[k])}`);
    }
    return out.join("\n");
}

const started = Date.now();
let checked = 0;
let skipped = 0;
for (const g of golden) {
    if (onlyId != null && g.id !== onlyId) { skipped++; continue; }
    if (onlySeed != null && g.seed !== onlySeed) { skipped++; continue; }
    const r = runFight({ dicts, row: g, seed: g.seed, maxSeconds: MAX_SECONDS });
    const a = JSON.stringify({ snapshots: r.snapshots, final: r.final });
    const b = JSON.stringify({ snapshots: g.snapshots, final: g.final });
    if (a !== b) {
        console.error(`DIVERGED: ${g.id} seed ${g.seed}`);
        console.error(
            `  ${g.n1}x ${g.civ1}/${g.slug1} vs ${g.n2}x ${g.civ2}/${g.slug2}`,
        );
        console.error(describeDivergence(g, r));
        console.error(
            `  reproduce: node tools/simjs/parity_check.mjs --id ${g.id} --seed ${g.seed}`,
        );
        console.error(`  (${checked} fights matched before this one)`);
        process.exit(1);
    }
    checked++;
    if (!quiet && checked % 25 === 0) {
        console.log(`  …${checked}/${golden.length - skipped} fights matched`);
    }
}

const secs = (Date.now() - started) / 1000;
if (checked === 0) {
    console.error("no fights selected — check --id / --seed");
    process.exit(2);
}
console.log(`PARITY OK — ${checked} fights bit-exact`);
if (!quiet) console.log(`(${secs.toFixed(1)}s)`);

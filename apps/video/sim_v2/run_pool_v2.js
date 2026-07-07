// run_pool_v2.js — run the ALTERNATE MODEL v2 (position-aware + randomness) for
// the SUBJECT unit vs each opponent in the pool, at ARENA counts (equal-resources,
// cap 21 — the in-game/video convention). Team1 = subject, team2 = opponent.
//
// Escalation: 5 seeds; if |mean margin S| < ESCALATE_ABS run 10 more (total 15) so
// contested matchups get more samples and clearly-decided ones stay cheap.
//
// Inputs (written by build_v2_categorization.py, read from --workdir):
//   combat_dicts_all.json : {"Civ/slug": <combat dict>} for subject + all opponents.
//   pool_meta.json        : per-opponent metadata incl. n_subject / n_opp arena counts.
// Output: v2_slice_<START>.json (a slice of the results; START/COUNT allow parallel drivers).
//
// Usage:
//   SUBJECT="Muisca/elite_temple_guard_muisca" WORKDIR=/path START=0 COUNT=75 node run_pool_v2.js
const fs = require("fs");
const path = require("path");
const { runFight } = require("./sim_v2_model");   // frozen config baked in

const WORKDIR = process.env.WORKDIR || __dirname;
const SUBJECT = process.env.SUBJECT;              // "Civ/slug"
if (!SUBJECT) { console.error("!! SUBJECT env required (e.g. Muisca/elite_temple_guard_muisca)"); process.exit(2); }
const [subjCiv, subjSlug] = SUBJECT.split("/");

const combat = JSON.parse(fs.readFileSync(path.join(WORKDIR, "combat_dicts_all.json"), "utf8"));
const meta = JSON.parse(fs.readFileSync(path.join(WORKDIR, "pool_meta.json"), "utf8"));
const cdS = combat[SUBJECT];
if (!cdS) { console.error(`!! subject ${SUBJECT} not in combat_dicts_all.json`); process.exit(2); }

const START = parseInt(process.env.START || "0", 10);
const COUNT = parseInt(process.env.COUNT || String(meta.length), 10);
const BASE = 1000;
const ESCALATE_ABS = parseFloat(process.env.ESCALATE_ABS || "33");   // |mean S| below this -> +10 more seeds

async function runN(m, nSeeds, seed0) {
    const cdO = combat[`${m.civ}/${m.slug}`];
    const out = [];
    for (let s = 0; s < nSeeds; s++) {
        const r = await runFight(cdS, subjSlug, subjCiv, m.n_subject,
            cdO, m.slug, m.civ, m.n_opp, seed0 + s);
        out.push(r);
    }
    return out;
}

function summarize(rs) {
    const S = rs.map((r) => r.margin);
    const mean = S.reduce((a, b) => a + b, 0) / S.length;
    const sd = Math.sqrt(S.reduce((a, b) => a + (b - mean) ** 2, 0) / S.length);
    const subjWins = rs.filter((r) => r.winner === 1).length;
    const oppWins = rs.filter((r) => r.winner === 2).length;
    const winHp = rs.map((r) => 100 * Math.max(r.h1, r.h2));
    return {
        n: rs.length, subject_winrate: subjWins / rs.length,
        subject_wins: subjWins, opp_wins: oppWins,
        mean_S: +mean.toFixed(1), sd_S: +sd.toFixed(1),
        subject_hp: +(100 * rs.reduce((a, r) => a + r.h1, 0) / rs.length).toFixed(1),
        opp_hp: +(100 * rs.reduce((a, r) => a + r.h2, 0) / rs.length).toFixed(1),
        winner_hp: +(winHp.reduce((a, b) => a + b, 0) / winHp.length).toFixed(1),
        bimodal: subjWins > 0 && oppWins > 0,
        S_list: S.map((x) => +x.toFixed(1)),
    };
}

(async () => {
    const slice = meta.slice(START, START + COUNT);
    const results = [];
    for (let i = 0; i < slice.length; i++) {
        const m = slice[i];
        let rs = await runN(m, 5, BASE);
        let sum = summarize(rs);
        let escalated = false;
        if (Math.abs(sum.mean_S) < ESCALATE_ABS) {
            const more = await runN(m, 10, BASE + 5);
            rs = rs.concat(more);
            sum = summarize(rs);
            escalated = true;
        }
        results.push({ civ: m.civ, slug: m.slug, name: m.name, cat: m.cat,
            ranged: m.ranged, n_subject: m.n_subject, n_opp: m.n_opp,
            escalated, ...sum });
        console.error(`[v2 ${START + i + 1}/${meta.length}] ${m.slug.padEnd(36)} ` +
            `n=${sum.n} win%=${(100 * sum.subject_winrate).toFixed(0)} S=${sum.mean_S}±${sum.sd_S} ` +
            `${sum.bimodal ? "BIMODAL" : ""}`);
    }
    fs.writeFileSync(path.join(WORKDIR, `v2_slice_${START}.json`), JSON.stringify(results, null, 1));
    console.error(`wrote v2_slice_${START}.json (${results.length} matchups)`);
})();

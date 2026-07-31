# paladin__vs__elite_steppe — live-round forensics (r19–r30)

**Date:** 2026-07-31 · **Engine:** `968886a` (improved-simulation HEAD, engine tree clean) ·
**Scope:** measurement only — no repo code touched. All engine probes ran from a scratchpad
mirror whose default output was verified **byte-identical** to the repo runner on all 36
(fight, seed) files before any flag was flipped.

Corpus: the 12 position-valid v3 recordings ingested 2026-07-31 (`ingest_0731.md`),
run_ids `paladin__vs__elite_steppe_r19`..`_r30`. Owner 2 = Paladin (Spanish, 15),
owner 3 = Elite Steppe Lancer (Cumans, 21). Companion data:
`data/calibration/analysis/ps_live_forensics.json`.

Conventions: concurrency window 2.5 s (same as `v2_melee_rebaseline.md` §6c); reach —
steppe 1.5 tiles (1.0 range + 2×0.25 mounted radius), paladin in-reach threshold 0.7
tiles; "moving" = >0.05 tiles per 0.1 s sample; kill-curve marks are 10 s steps from
first blood; cross-round aggregates are medians. Tape times are from the damage stream's
**last blow**, never the truth card's `duration_s`.

---

## 0. Headline

| Question | Answer |
|---|---|
| Truth | Paladin wins **11/12** (steppe's one win is r19). Winner survivors med **5**/15 at **530 HP = 19.6%** of army max; steppe wiped (0/21) in every paladin win. Last blow med **46.2 s**. |
| Engine at shipped defaults | **Steppe in 36/36 seeds — and every seed of every round is the IDENTICAL fight** (see §1): 3 steppe survivors, 135/2100 HP (6.4%), 55.1 s, in all 36. |
| What diverges first | Paladin **re-engagement**, not the opening and not overcrowding. First-10 s concurrency and early paladin deaths are on-tape; the paladin kill curve is already 3 kills behind at +10 s and the deficit compounds (§3). |
| Steppe-attackers-per-paladin | **Matches exactly** — tape med 2 / p90 4 / max 6, engine med 2 / p90 4 / max 6. The ring is not overcrowded. |
| The lane rule (E15b R2) | **Refuted again, now on position-valid truth.** Lane OFF makes steppe *stronger* (3 → 5 survivors, 135 → 395 HP) and flips nothing. Same direction as the v2 A/B. |
| Any single melee rule? | **No config flips any round.** Steppe wins 36/36 in all 12 configs, including all melee rules off at once (which is *worse*: 6 steppe survivors). The cause is below the rule stack — in the movement/collision layer. |

---

## 1. A structural note the runner surfaced: this family is n=1 for the engine

Two facts compound:

1. **All 12 live recordings start from byte-identical first-frame spawns** — the
   recorder places the same half-tile formation every round (`spawns.json` entries for
   r19–r30 are equal; verified against the raw tapes).
2. **A pure-melee fight consumes no rng.** Seeds 1–3 produce identical records minus
   the `seed` field (verified). Accuracy rolls are the engine's only stochastic draw
   and there are none here.

So the engine's 36 "samples" are one deterministic trajectory, while the game, from the
*same* initial condition, produces outcomes spanning steppe-wins-with-6 (r19) to
paladin-wins-with-8 (r29). Real melee outcome variance from identical starts is large;
a deterministic engine can at best land on the distribution's center — and it is
currently on the wrong side of it. Any scoring of this family should know its effective
engine sample size is 1.

---

## 2. Part 1 — how the paladins actually win on tape

**Opening (0–10 s from first blood).** Steppe get nearly their whole army swinging
almost instantly — concurrency 15.5 of 21 in the first 10 s (peak 18.5) against the
paladins' 8.0 of 15. Ranks work as advertised: each living paladin has mean **2.98**
steppe bodies within the 1.5-tile lancer reach (p90 6, max 9 — the deepest stack a
paladin faces). The paladins eat this: 5 paladins are dead by ~17 s.

**But the trade is never even.** Paladins land 15-damage blows on 100 HP targets with
help from spread — median 3 distinct victims per paladin, hits/kill 7.0 — and their
kill curve runs 3 / 8.5 / 14 / 18.5 / 21 at +10/20/30/40/50 s. Steppe kills run
1 / 5.5 / 8 / 9.5 / 10. Half the steppe army (10) is dead by **+22.4 s**, at which
point the steppe side's own concurrency has collapsed while the surviving paladins
keep **6.19** units swinging in steady state (of ~7–10 alive — near-total engagement).

**Movement is the engine of that engagement.** Living paladins are in motion in
**29.8%** of samples (state decomposition: 65.5% swinging, 22.8% walking, only 6.8%
standing idle out of reach). Steppe cycle in and out of contact 0.72 exits/unit.
The paladin centroid pushes *into* the steppe blob: centroid separation 1.67 tiles in
the first 10 s → 0.94 late. The scrum churns; nobody stands around.

**Endgame.** The last steppe dies at +45.0 s median. Winning paladins finish with
med 110/180 HP per survivor — hurt but healthy. In r19 (the steppe win) the same
early phase goes the other way slightly and the paladins never recover — i.e. the
family genuinely is a margin fight, 11/12 not 12/12.

---

## 3. Part 2 — engine anatomy at shipped defaults, and where it diverges first

Tape med vs engine med (full table in the JSON):

| metric | tape | engine | verdict |
|---|---|---|---|
| concurrency, paladin first-10s | 8.03 | 7.15 | close |
| concurrency, paladin steady | **6.19** | **4.24** | **0.69× — the miss** |
| concurrency, steppe steady | 8.17 | 8.03 | match |
| hit rate steady, paladin (/s) | **2.99** | **2.14** | **0.72×** |
| hit rate steady, steppe (/s) | 3.97 | 3.89 | match |
| steppe-attackers-per-paladin med/p90/max | 2 / 4 / 6 | 2 / 4 / 6 | **exact match** |
| steppe-in-reach-of-paladin mean / max | 2.98 / 9 | 2.85 / 6 | close |
| paladin hits total | 147 | 137 | close |
| steppe hits total | 221.5 | **270** | +22% — all from extra fight length, not rate |
| kills by side | 21 / 10 | 18 / 15 | paladins can't finish; steppe never stop |
| last blow | 46.2 s | 55.1 s | engine grinds 1.19× long |
| moving share, paladin | **0.298** | **0.094** | **3.2× too static** |
| moving share, steppe | 0.144 | 0.034 | 4× too static |
| steppe contact exits/unit | 0.72 | 0.48 | tape churns more |

State decomposition of living-paladin frames (median):

| state | tape | engine |
|---|---|---|
| swinging (landed hit in trailing 2.5 s) | 0.655 | 0.633 |
| walking | **0.228** | **0.057** |
| idle, enemy in reach | 0.042 | 0.023 |
| **idle, NO enemy in reach** | **0.068** | **0.288** |

Attrition ordering: paladin deaths #3/#5/#8 land at 12.5/16.5/24.6 s engine vs
13.2/17.2/27.3 s tape — the engine's paladins die *on schedule*. Steppe deaths lag from
the start (#3 at 12.2 vs 9.8 s) and the gap compounds: steppe death #15 at 37.8 vs
31.2 s, #21 **never** (engine max 18 kills). Kill curves: engine paladins 0 / 8 / 12 /
16 / 18 at the same marks the tape runs 3 / 8.5 / 14 / 18.5 / 21.

**First-divergence verdict.** The opening is right: contact timing, first-10s
concurrency, ring density, attackers-per-victim, swing cadence and the paladin death
schedule all match. What diverges first — visible inside the first 10 s and never
recovered — is **paladin kill pace, caused by re-engagement failure**: an engine
paladin that loses its reachable victim goes and stands **out of reach doing nothing**
(28.8% of living-paladin frames vs 6.8% on tape) instead of walking around the scrum to
the next body (5.7% walking vs 22.8%). Aggregate paladin engagement decays to 0.69× of
tape; the fight stretches 9 s longer; the steppe side — whose per-second output the
engine reproduces exactly — banks +48.5 extra hits ≈ the 485 HP of paladins that
should have survived. This is the same signature E15's walk forensics measured
corpus-wide on the old tapes (`micro_follow` occupancy 41.2% vs 20.9% for paladins;
scrum "moves as a slab", individual speed 0.256 vs 0.401 tiles/s; `travel_livebreak`
≈ 0.00 in the engine) — now tied directly to a flipped outcome on live positions.

---

## 4. Part 3 — flag attribution (12 rounds × 3 seeds each config)

CLI coverage note: `calib_runner.mjs` exposes `--r5b/--r5d1/--r5d/--b2/--r5f/--c2a/
--c2b/--c2c/--c3/--d2/--e1` **only**. The E14/E15b melee constants
(`MELEE_TARGET_LOCK`, `MELEE_CONTACT_SLOTS`, `MELEE_LANE_REACQUIRE`,
`MELEE_BUMP_RETARGET`) are bare `export const`s with **no runtime toggle** — the CLI
cannot disable the lane rule. Those probes used the same method as
`v2_melee_rebaseline.md` §6b: an out-of-repo scratch mirror with one constant flipped,
byte-verified as a control before flipping. No repo file was modified.

| config | steppe seed-wins | med steppe surv | med steppe HP | vs default |
|---|---|---|---|---|
| shipped defaults | 36/36 | 3 | 135 | — |
| `--b2 off` (resolver contact bump) | 36/36 | 3 | 135 | **byte-identical — rule never fires here** |
| `--c2b off` | 36/36 | 3 | 135 | byte-identical (C2B already ships off) |
| `--c2b committedSwingLands` | 36/36 | 3 | 135 | byte-identical — inert |
| `--c3 postSwingPlant` (ON) | 36/36 | 3 | 135 | byte-identical — no ranged victims |
| mirror: `MELEE_BUMP_RETARGET=false` | 36/36 | 3 | 135 | byte-identical — **bump retarget never fires in this scrum** |
| `--c2b stopToSwing` (ON) | 36/36 | 5 | 260 | worse |
| mirror: **lane OFF** (`MELEE_LANE_REACQUIRE=false`) | 36/36 | **5** | **395** | **worse — refutes lane-rule-as-cause on live truth** |
| mirror: lock OFF (`MELEE_TARGET_LOCK=false`) | 36/36 | 2 | 125 | slightly better, no flip |
| mirror: `MELEE_CONTACT_SLOTS` 4→2 | 36/36 | 2 | 125 | slightly better, no flip |
| mirror: lane+lock OFF | 36/36 | 6 | 405 | worse |
| mirror: lane/lock/bump OFF + `--b2 off --c2b off` | 36/36 | 6 | 405 | worse — the pre-E14 engine loses HARDER |
| TAPE TRUTH | steppe 1/12 rounds | 0 (in pal wins) | 0 | — |

Reading: the rules landed while the bad truth was in force are **not** the cause. The
lane rule and target lock each *help* the paladins (removing them adds steppe
survivors); the bump valve literally never triggers in this fight (the parked paladins
are behind their own allies, not in cross-team contact — consistent with E15
forensics' "1.55 allies in reach of the lock, median 1 — they are not waiting behind a
full ring"). Nothing exposed or flippable moves the winner. The residual lives below
the target-selection layer.

---

## 5. Ranked mechanism candidates

1. **Scrum flow for the blocked melee attacker (the unbuilt "contact loss →
   re-engagement walk" mechanism the E15b notes already name).** A melee unit whose
   lock is out of reach and whose straight lane is blocked currently stands (28.8% of
   living-paladin frames). Tape says it should be *walking* (arc ratio 1.278, E15 §5)
   around the blockers — tangential drift along the scrum face instead of a radial
   stand. Target metrics for any fix, from this report: paladin steady concurrency
   4.24 → ~6.2, walking share 5.7% → ~23%, idle-out-of-reach 28.8% → ~7%, last blow
   55 s → ~46 s. Must NOT break (the melee gate is 95 fights): steppe steady
   concurrency 8.03 ≈ 8.17 (already right), attackers-per-victim ceiling 2/4/6
   (already exact — a flow rule must route paladins to *open* faces, not deepen
   rings past `MELEE_CONTACT_SLOTS`), swing cadence 1.92/2.02 s, and
   `champion__vs__paladin` (v2 board: the outnumbered side there is also 0.73×
   engaged, and its margin is 24.6 pts too fat — more engagement for the small side
   should *improve* it; verify, don't assume).
2. **Victim-side churn (contact breaks).** Tape opens contact 0.95% per in-reach
   sample, 90% by the victim walking away; the engine has 5× too few breaks and its
   steppe exit contact 0.48 vs 0.72 exits/unit. Churn frees paladin victims and
   creates the re-engagement walks in (1). Riskier: it touches every melee family and
   the tape's own micro-follow measurement (E15 §2) forbids implementing it as
   between-swing drift; it has to come from target switching, which E15 §4 calls "a
   targeting question, not a collision-physics question".
3. **Tuning mitigations only — not causes.** Lock-off and slots-2 both trim the
   steppe margin (3 → 2 survivors) by letting parked paladins re-pick sooner, but
   neither flips a single seed, and E14's measurements behind them still stand. At
   most, revisit `MELEE_CONTACT_SLOTS` *after* (1) exists, since a flow mechanism
   changes what "queueing behind a full ring" means.

Non-candidate worth recording: **do not re-litigate E15b's lane rule off this
family** — twice refuted (v2 outcome truth, now live-position truth), and it moves
the residual the wrong way both times.

---

## Artifacts

| what | where |
|---|---|
| combined metrics (per-round + aggregates + config board) | `data/calibration/analysis/ps_live_forensics.json` |
| scratch scripts (tape/engine anatomy, track dumper, config scorer) | `C:\Users\ddk22\AppData\Local\Temp\claude\D--AI-aoe2-matchup\a9df76fd-3235-4257-bba6-2fabfe9e152e\scratchpad\{anatomy.py, anatomy2.py, melee_tracks.mjs, score_configs.py, build_deliverable.py}` |
| engine runs, all 12 configs (36 seed files each) | `<scratchpad>\runs\<config>\` |
| engine 10 Hz position tracks, shipped defaults | `<scratchpad>\tracks\default\` |
| snapshot mirror (engine + runner, commit + control noted inside) | `<scratchpad>\mirror\` (`SNAPSHOT_COMMIT.txt` = `968886a`, clean) |

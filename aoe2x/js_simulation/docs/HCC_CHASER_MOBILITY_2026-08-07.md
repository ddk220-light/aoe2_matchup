# HCA vs Champion 12v21 — chaser mobility forensics (2026-08-07)

> **2026-08-08, round 3 — the victim side, measured: `AOE2X_EXP_STEP=kited`
> (default OFF).** With routing in place, the next mirrored measurement moved
> from the chaser to the CAUGHT KITER. Post-swing forensics: the attacker's
> hold is already exact (move-delay after swing start p50 tape 1.54 s / sim
> 1.52 s) — the difference is that the tape's victim ESCAPES during that hold
> (gap to attacker 0.55 → 1.0–1.3 within a second) while the sim's victim
> stays pressed (0.55 → 0.6). And the escape is not a flee mechanic: the tape
> victim moves exactly WITH its ball (1 s displacement 0.50–0.67 vs ball-mates
> 0.55–0.66) — it executes the scripted move THROUGH attacker contact, where
> the sim's kiter grinds on the pressing body (0.13–0.39, below even its own
> mates). `STEP=kited` extends the chaser steer to the kiting side's
> move-ordered units (no target exclusion — a kiter's target is who it
> shoots, often the very champion pressing it).
>
> Results: `kited`+`grid` takes 12v21 to **5/6 HCA wins, mean −33.6 vs the
> tape's −36.5** (the tape itself has 1 champion win in 14) with every
> mechanism metric moving toward tape (swings 89→47 vs 61, duty 0.29 vs 0.26,
> own-target contact −30%). But the corpus pays: 695.7 / 4 wrong winners —
> the free escape re-flips kac 5v10 (whose tape shows the AMBUSHED arbs
> failing exactly this escape), esc 10v5 and hcp 20v15. A directional gate
> (steer only away from the nearest enemy) was measured and rejected: 12v21
> falls to 2/6 and hcc 5v10 + avf 15v20 flip (551.5 / 3).
>
> So the victim mechanism is REAL and demonstrated sufficient to close 12v21;
> what is missing is the discriminator the game gets from actual clearance
> pathing — an escape must fail exactly when the tape's ambushes make it fail.
> Candidates for the next round: clearance margin on the kiter steer (a body
> cannot slip a gap narrower than its own box plus margin), or extending the
> grid planner to the kiting side's move execution. The flag stays OFF;
> default and `grid` behavior are bit-identical with it unset.
>
> The clearance-margin candidate was probed at 0.25 tiles (one body
> half-width) and rejected: it overshoots the other way -- fleeing kiters
> wall in, 12v21 drops to 1/6 and kac 15v20 / avf 20v20 flip TOWARD the
> chasers (638.4 / 3). With pad 0 the escape is too free, with 0.25 too
> hard; threading a pad between two wrong-winner cliffs would be fitting to
> the outcome, so the remaining honest lever is the grid planner executing
> the kited side's moves (clearance emerges from the plan, not a constant).

> **2026-08-08, round 2 — per-unit pathing exists: `AOE2X_EXP_CHASE_PATH=grid`
> (default OFF, candidate for the next pin).** The "next real lever" below is
> built: `src/combat/chase-path.js` plans a coarse per-unit A\* route (0.25-tile
> cells, 8-connected, deterministic ties, best-effort on unreachable targets)
> from each kited-world chaser to its own target around the ACTUAL unit bodies,
> on the existing 0.5 s repath cadence; straight-line-clear falls through to
> live tracking, unreachable-with-no-progress stands still. Corpus, one
> playback per recorded ratio:
>
> | config | sum band err | wrong winners |
> |---|---:|---:|
> | pinned default (`step=chaser`) | 423.0 | 2 (cvp 6v3, avf 15v20) |
> | + tangent-disc router (`ball`) | 576.3 | 3 — REJECTED, deleted |
> | + per-unit grid A\* (`grid`) | 522.7 | **1 (cvp 6v3 only)** |
>
> `grid` is the first configuration with **zero kited wrong winners** — it
> fixes arbalester_vs_firelancer 15v20, wrong under every prior engine — and
> every one of its band-error regressions (concentrated in 10v5/5v10/15v20
> catching ratios, worst +30) keeps the tape's winner. hcc 12v21 improves to
> 3/6 HCA (band −69..+9, samples −26..+44) but is not solidly fixed: the
> residual own-target contact (2970 frames vs tape 671) happens AFTER arrival
> — per-tick tracking through the catch — not in routing. Not pinned yet:
> the winner gate improves but the band gate regresses, and the pin decision
> should follow a fresh look at the post-arrival glue. All non-kited ratios
> bit-identical under the flag; default config and test-failure set unchanged.

> **2026-08-08 recalibration round — `chaser` is now the committed default.**
> The scoped rule below (steer around NON-target enemy bodies, else stop;
> ally blocks and the mover's own target keep the baseline solver) landed in
> `engine-config.js` as `step: "chaser"` after the full-corpus round:
> scoreboard **444.0 → 423.0** summed band error, wrong winners unchanged
> (both pre-existing: champion_vs_paladin 6v3, arbalester_vs_firelancer
> 15v20 — the latter improves 58.3 → 38.4 but stays wrong), esc columns
> improve (20v15 13.9 → 6.5, 10v5 4.6 → 0.0), kac intact, **all 131
> non-kited recorded ratios bit-identical**, test-suite failure set
> identical before/after. `AOE2X_EXP_STEP=none` restores the pre-round
> solver (PowerShell-safe sentinel, like engagement's `free`).
>
> Also in this round: `matchup-playback` now passes `chaseCapture` from the
> truth fixtures (it had only ever been wired into the sweep harness;
> corpus effect +1.2 band error, no winner changes), capture rates were
> re-measured under `chaser` (kac 30 and hcc 26 events/fight against the
> tape's ~0 and ~8 genuine contacts — both stay OFF; esc 40 / esp 12 /
> avp 22 against tape 46 / 43 / 38 — all stay ON), and
> `AOE2X_EXP_MINRANGE=shooter` was re-tested (423.0 → 475.1, still
> over-suppresses because chaser exposure remains above tape — stays OFF).
>
> **What did NOT land: the 12v21 wrong winner is still open.** Six rule
> variants were measured (the ladder below, plus ally-queue forms: stop on
> any ally block / on stationary allies / steer around stationary allies /
> stop behind frustrated held allies). Every variant that restores the
> tape's 12v21 queue lag (champion→own-target p50 1.8–2.85 tiles, own-target
> contact 2–15% of frames) also strands a catching column (esc 10v5,
> hcst 20v20, or kac 5v10 flip), and every variant that preserves the
> catches collapses back to target-hugging at 12v21 (p50 ~1.0, contact
> 25–50%). The tape's lag is produced by obstacle-aware pathing around the
> ball with clearance margin — the pathfinding this engine deliberately
> does not have (see arena.js "documented infidelity"). Local per-tick
> collision rules cannot express both regimes at once; further variants
> are curve-fitting. Next real lever: a coarse flow-field / clearance path
> around the kiting ball for pursuers, then re-run this ladder.

The standard-units corpus's one genuine measured-cause wrong winner
(`STANDARD_UNITS_SUMMARY_2026-08-07.md`: tape −36.5 over 14 repeats, sim +24.5,
champions winning 22/25 sampled orders) is root-caused here from the full-rate
`frames.bin` decode of all 14 recordings, and a scoped candidate rule is landed
behind `AOE2X_EXP_STEP=chaser` (default OFF). The rule fixes this matchup
dead-on and leaves every non-kited fight bit-identical, but it moves the
calibrated kited columns — whose constants were fitted on the defective
mobility — so landing it as default requires a recalibration round, not a
flag flip. Numbers below.

## Evidence source

`aoe2_golden_STANDARD_UNITS_WITH_TAPES.zip` — the raw-`frames.bin` build of the
locked FINAL corpus. Identity to the authority was verified before use: the
decoded streams for the fights used here are byte-identical (SHA-256) to
`aoe2_golden_STANDARD_UNITS_FINAL.zip`, whose own hash was verified against
`calibration/source/source_of_truth.json` first. Decoder:
`tools/decode_tape_frames.py` (~59.9 Hz per-unit position + Action state/target).

Both sides of every comparison go through the same two metric scripts
(mirrored-measurement rule): full-rate speed histograms, swing starts
(Action.state 7 rising edge / windup+swing timers), Chebyshev contact, kiter
duty cycle, ball revolutions about map centre.

## What the tape shows (14 recordings, 12 HCA vs 21 Champion)

HCA win 13/14. The kiting layer itself is NOT the story — the sim's ball laps
the ring at the tape's own cadence:

| metric | tape (median over repeats) | sim (6 sampled orders) |
|---|---|---|
| HCA duty cycle | 0.26 (0.23–0.30) | 0.19–0.28 |
| ball revolutions per fight | ~1.0 | 0.5–2.5 |
| champion speed stopped/partial/full % | 27 / **0.7** / 72 | 47–57 / **7.5–15.4** / 34–41 |
| champion → nearest-HCA gap p50 | **1.42–2.06 tiles** | **0.67–0.81** |
| champion contact (≤0.5 cheb) % of frames | **3.1–6.2** | **23–31** |
| kiter exposure (champ ≤1.0) | 23–49% | 72–82% |
| contact-window mean length | **0.42–0.69 s** | **1.49–3.16 s** |
| champion swings per fight | 32–95, tracks duration | ~90–96 regardless |
| swings per contact-second | 1.7–2.6 | 0.36–0.65 |

Genie chaser movement is bimodal (the camel histogram again, now confirmed on
champions): stopped or full speed, 0.6–0.8% in between. The sim's constraint
solver (`constrainPair` → `distributeEqualMassRemoval`) manufactures a
partial-speed grinding population that keeps a chaser glued to the ball
surface: median gap 0.75 vs the tape's 1.6, six-times the contact, windows of
seconds instead of a touch. Tape contact is a brief catch → swing → release;
sim contact is standing pressure. At 12 shooters vs 21 chasers that pressure
decides the fight, so the winner inverts.

Why this matchup and not the neighbours: HCA vs Champion is the corpus's one
kite pairing with both a decisive speed gap (1.54 vs 1.06) and a low-damage
chaser, so the catch rate is the whole outcome. Against Paladin/Hussar/Camel/
Steppe the chaser is fast enough that standing pressure is *correct*-ish, and
against Halberdier the +32 cavalry bonus wins regardless.

The sim construction used for all of this (tape reference ids, tape spawns,
measured hcc kiteProfile, chaseCapture OFF, 25→6 sampled acquisition orders)
reproduces the committed sweep's inversion: 5/6 champion wins at baseline.

## Candidate rules, all measured (sum band error / wrong winners over the
## 192-recorded-ratio corpus scoreboard; baseline = 442.9 / 2)

| rule | corpus | hcc 12v21 (6 orders) | verdict |
|---|---|---|---|
| `AOE2X_EXP_STEP=bimodal` (blanket) | 924.8 / 5 | 6/6 HCA, mean −37.5 | melee ratios flip; kite block strands |
| `AOE2X_EXP_STEP=steer` (blanket) | 666.7 / 4 + 1 timeout | 6/6 HCA, −33.8 | kac collapses, kiter side escapes forever |
| `chaser` as stop-only | 911.3 / 6 | 6/6 HCA, −61.0 | fast chasers that SHOULD catch stop dead (esc/hcp die) |
| **`chaser` = steer-then-stop (landed)** | **592.6 / 3** | **6/6 HCA, −42.7 (tape −36.5)** | best; kac 5v10 flips, see below |
| `chaser` + enemy-only steer | 650.9 / 5 | 5/6 HCA | ally-block steering matters for crowded catches |

The landed `chaser` mode: in a kited world (`world.kiteState` present), the
chasing side's blocked steps first search a nearby clear full-speed heading
(the camel tape's route-around-at-full-speed), and a step that still cannot
run clean is cancelled to a stop (the bimodal histogram). The kiting side and
every non-kited scenario keep the baseline solver — verified bit-identical:
0 of 131 non-kited ratios moved, and the default-config corpus and test suite
are unchanged with the flag off.

## Why this cannot land as default yet

The kited columns were calibrated ON the grinding engine, and their
per-scenario constants compensate for it — explicitly so for contact capture
(`CONTACT_CAPTURE_2026-08-07.md` records kac/hcc OFF "until block-escape
pathing improves"; this flag IS the block-escape pathing improving) and for
the dwell/beat models fitted per column. Under `chaser` the seesaw moves:
esc columns improve (20v15 12.4→1.9, 10v5 10.3→0), kac regresses
(5v10 flips winner, 20v20 0→40 err), hcp/avp shuffle by single digits.

So the recorded order of operations from the camel work still stands, now one
step further along:

1. ~~fix chaser mobility~~ — this flag;
2. re-measure engulfment + contact rates per column under `chaser`;
3. re-derive the per-scenario `chaseCapture` settings (the kac/hcc OFFs exist
   only because of the grinding) and re-land min-range suppression, whose
   cost scales with exposure (45.7% → measured anew under `chaser`);
4. re-verify the kiting corpus + svc/svp, then pin `chaser` into
   `engine-config.js` and re-sweep the standard-units archive.

Until that round runs, the committed default stays grinding, and the
standard-units summary's HCA-vs-Champion row stays a known wrong winner with
its cause measured and its fix staged.

## Reproducing

Scratch tooling for this round (tape decode → mirrored metrics → corpus A/B)
is session-scratchpad only by design; the decode path and both metric
definitions are fully specified above and in `tools/decode_tape_frames.py`.
The corpus scoreboard is one deterministic playback per recorded ratio via
`src/matchup-playback.js`, signed winner-HP% against the tape runs' min–max
band, wrong winner = sim winner absent from every tape repeat.

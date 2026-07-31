# V2 melee re-baseline — measurement report

**Date:** 2026-07-31 · **Base:** `0c5c38c` (improved-simulation) · **Scope:** measurement only, no engine change.

The melee-vs-melee corpus was re-recorded after a flaw was found in the recorder
setup (drop `aoe2_golden_melee_v2_palsteppe12.zip`, 67 recordings, ingested as
`_rN` run ids). This report measures the landed engine against that new truth,
diffs the new truth against the old, and tests the standing hypothesis that the
melee rule stack was fitted to a bad capture.

Everything below is measured. No design conclusions are drawn — that is the main
session's call.

---

## 0. Headline

| Question | Answer |
|---|---|
| Is the old melee corpus broadly fake? | **No.** 27 of 28 overlapping families agree on the winner. |
| Which old family was miscaptured? | **`paladin__vs__elite_steppe`, and only that one.** Old: steppe 83%. V2: paladin 75%. |
| Is the melee stack overfitted to the fake truth? | **Not at the corpus level.** The engine scores *better* against v2 truth (27/28 families, 4.16 pts mean HP error) than against old truth (26/28, 5.31 pts). |
| Did E15b's lane rule cause the paladin/steppe miss? | **No — refuted.** With `MELEE_LANE_REACQUIRE=false` the engine still picks steppe 240/240 seeds, and the HP error gets *worse*. |
| Is the engine's melee "too fast"? | **No — that was an artifact.** Against the tape's actual wipe the sim runs at 0.98x, not the 0.53–0.72x the truth cards imply. |
| What *is* wrong, then? | One family. The engine under-engages the outnumbered melee side; see §6. |

**The one real miss:** `paladin__vs__elite_steppe`. Tape says paladin 9/12 at 15% HP;
the engine says steppe in 240 of 240 seeds with the paladins wiped. Nothing else on
the melee board flips.

---

## 1. Geometry check — the v2 recorder changed, and its position channel is dead

The v2 setup is materially different from the old one, and one difference is a
data defect that constrains what v2 can be used for.

### 1a. Spawn geometry (first frame, from the tapes)

| | old corpus (155) | v2 corpus (67) |
|---|---|---|
| position envelope, all samples | x/y `[1.20, 14.80]` — a 13.6-tile square | x `[1.50, 8.50]` y `[3.50, 10.50]` — 7.0 x 7.0 |
| centroid separation | min 7.63 / med 8.12 / max 9.84 tiles | min 3.56 / **med 4.04** / max 4.32 tiles |
| nearest cross-army pair | 4.00–6.08 tiles | **exactly 2.00 tiles, every tape** |
| blob shape | ~6 wide x 3 deep | ~6 wide x 2 deep |
| separation axis | \|dx\| 2.30 / \|dy\| 7.69 | \|dx\| 0.88 / \|dy\| 3.87 |
| coordinate values | continuous (3 338 distinct fractional parts in one tape) | **only ever `*.5`** — one distinct fractional part |

The v2 armies start **half as far apart** as the old ones and are placed on an
exact half-tile grid. `dump_calib_spawns.py` extracts all 67 cleanly (222/222
total, zero count mismatches against the manifest).

### 1b. The v2 position channel never updates — DEFECT

Every unit in every v2 tape has **exactly one distinct position for the entire
recording**. Old tapes carry 94–138 distinct positions per unit; v2 carries 1.0.

Proof that this is stale data and not a genuinely stationary fight: in
`paladin__vs__elite_steppe_r7`, **90% of the 371 melee damage events (334) occur
between units the tape places more than 2.5 tiles apart, up to 8.49 tiles**. Melee
units cannot reach that far. The fighters moved; the recorder kept reporting their
spawn tile. `meta.json` still advertises `position_sample_hz: 10.0`, and samples do
arrive at 10 Hz — they just never change.

The HP/damage/kill channel is intact (real `victim_hp_after`, `kill` flags, sane
event counts), so **outcome truth is sound**.

### 1c. What this means for the tapebox spec — REPORTED, NOT CHANGED

`TAPEBOX_MIN_TILE = 1.2` / `TAPEBOX_MAX_TILE = 14.8` (`arena.js`) is documented as
"measured over every unit-position sample in all 155 recordings". That derivation
**cannot be repeated for v2**: with positions frozen at spawn, the v2 tapes contain
no evidence of where the walls are. The 7x7 envelope measured above is the *spawn
footprint*, not the map.

So, for the main session to decide:

* The v2 walls are **unknown**, not "7x7". Do not narrow the box to the spawn
  footprint — that would invent a constraint the recordings do not attest.
* The current `[1.2, 14.8]` box does contain every v2 spawn (which centre around
  ~(4.5, 7.5), i.e. off-centre in the box), so v2 fights run without clipping. It
  is unverified for v2, not known-wrong.
* **A v2 tapebox variant should not be authored from this data.** If the walls
  matter, the position channel needs fixing and a re-record.

### 1d. Consequence for scoring

Only **outcome-level** metrics are valid against v2: winner, survivors,
hp_remaining, kills, hits, swing cadence, duration. **Any positional calibration —
approach, pursuit, standoff distance, walk paths, lane geometry — cannot be scored
against the v2 corpus at all.** The old corpus remains the only source of
positional truth.

---

## 2. Run configuration

```
python tools/simjs/dump_calib_spawns.py                       # 222/222 tapes, counts verified
node tools/simjs/calib_runner.mjs --tags <67> --seeds 20 --workers 8 \
     --out-dir D:/AI/aoe2_golden/simruns_v2melee               # 1340 files
python -m aoe2x.calibration.score --tags <67> --seeds 20 \
     --sim-runs-dir D:/AI/aoe2_golden/simruns_v2melee --label v2melee-baseline
python tools/simjs/melee_hp_report.py --sim-runs-dir D:/AI/aoe2_golden/simruns_v2melee
python tools/simjs/v2_family_board.py --sim-runs-dir D:/AI/aoe2_golden/simruns_v2melee
```

Arena `tapebox` (default), v2 spawns from the regenerated `spawns.json`.

Per-recording scoreboard: 67 scored, 0 failures, **15 PASS / 52 MISMATCH**, winner
agreement 54/67, mean per-seed agreement 0.806. All 13 winner mismatches sit in four
families, and **9 of the 13 are `paladin__vs__elite_steppe`** (every one at
`seed_agreement = 0.0`).

Two tooling fixes were needed and are included:

* `aoe2x/calibration/score.py` — a `--tags` list of 67 built a ~2 000-character
  filename and threw `FileNotFoundError` *after* computing the whole board. The
  filename filter fragment is now capped at 60 chars with an 8-hex digest; the full
  filter still goes to `subset.filter` in the payload.
* `tools/simjs/v2_family_board.py` — new. The per-recording scorer cannot answer
  "does the engine pick the right side?" for a stochastic family; this aggregates
  both sides of the comparison to the family level and diffs old vs new truth.

---

## 3. The family board — tape vs engine (v2, 20 seeds)

`tapeW` = fights this slug won / recordings. `engW` = seeds won / (recordings x 20).
HP% is of that side's army max. `wipe` is the tape's **last damage event**, not the
truth card's `duration_s` (see §5).

```
family                                   n            side   tapeW    engW  tapeHP%   simHP%     dHP    wipe_s   sim_s
----------------------------------------------------------------------------------------------------------------------
champion__vs__elite_elephant             1        champion      0%      0%      0.0      0.0    +0.0      33.8    39.2
                                            elite_elephant    100%    100%     49.2     34.5   -14.7
champion__vs__elite_fire_lancer          1        champion    100%    100%     58.2     61.2    +3.0      20.5    15.8
champion__vs__elite_steppe               1        champion    100%    100%     40.7     46.7    +6.0      24.6    21.5
champion__vs__halberdier                 1        champion    100%    100%     72.6     68.6    -4.0      25.0    21.7
champion__vs__heavy_camel                1        champion    100%    100%     71.0     81.0   +10.0      26.1    24.0
champion__vs__hussar                     1        champion    100%    100%     42.9     48.6    +5.7      34.9    31.8
champion__vs__paladin                    7        champion     86%    100%     19.2     43.8   +24.6      34.6    29.4
                                                   paladin     14%      0%      2.0      0.0    -2.0
elite_fire_lancer__vs__elite_elephant    1  elite_fire_lan    100%    100%     63.1     58.5    -4.6      23.5    21.1
elite_fire_lancer__vs__elite_steppe      1  elite_fire_lan    100%    100%     46.5     63.0   +16.5      22.2    14.8
elite_fire_lancer__vs__heavy_camel       1  elite_fire_lan    100%    100%     71.7     84.2   +12.5      25.1    21.3
elite_fire_lancer__vs__hussar            3  elite_fire_lan    100%    100%     68.9     72.8    +3.9      21.8    18.3
elite_fire_lancer__vs__paladin           1  elite_fire_lan    100%    100%     50.3     63.8   +13.6      24.9    21.5
elite_steppe__vs__elite_elephant         3    elite_steppe      0%      0%      0.0      0.0    +0.0      39.8    50.2
                                            elite_elephant    100%    100%     57.8     45.2   -12.6
halberdier__vs__elite_elephant           1      halberdier    100%    100%     78.6     71.7    -6.9      11.8    10.4
halberdier__vs__elite_fire_lancer        1      halberdier      0%      0%      0.0      0.0    +0.0      38.0    36.4
                                            elite_fire_lan    100%    100%     34.7     42.5    +7.8
halberdier__vs__elite_steppe             1      halberdier    100%    100%     68.6     75.2    +6.7      11.8    10.4
halberdier__vs__heavy_camel              3      halberdier    100%    100%     84.6     86.7    +2.1      14.3    14.1
halberdier__vs__hussar                   3      halberdier    100%    100%     81.2     76.5    -4.7      14.5    12.6
halberdier__vs__paladin                  1      halberdier    100%    100%     77.4     76.2    -1.2      13.8    10.9
heavy_camel__vs__elite_elephant          7     heavy_camel     86%    100%     18.9      9.1    -9.8      47.5    57.4
                                            elite_elephant     14%      0%      2.1      0.0    -2.1
heavy_camel__vs__elite_steppe            1     heavy_camel    100%    100%     40.8     41.0    +0.2      25.4    24.4
hussar__vs__elite_elephant               3          hussar      0%      0%      0.0      0.0    +0.0      38.4    44.1
                                            elite_elephant    100%    100%     64.0     67.0    +3.0
hussar__vs__elite_steppe                 7          hussar     71%    100%     10.7     11.8    +1.1      41.8    49.4
                                              elite_steppe     29%      0%      5.4      0.0    -5.4
hussar__vs__heavy_camel                  1          hussar      0%      0%      0.0      0.0    +0.0      23.0    29.4
                                               heavy_camel    100%    100%     63.4     46.8   -16.6
paladin__vs__elite_elephant              1         paladin      0%      0%      0.0      0.0    +0.0      56.4    61.7
                                            elite_elephant    100%    100%     43.8     47.1    +3.3
paladin__vs__elite_steppe               12         paladin     75%      0%     15.3      0.0   -15.3      45.6    55.1  <== WINNER FLIP
                                              elite_steppe     25%    100%      5.8      6.4    +0.7
paladin__vs__heavy_camel                 1         paladin      0%      0%      0.0      0.0    +0.0      30.3    29.9
                                               heavy_camel    100%    100%     55.7     50.5    -5.2
paladin__vs__hussar                      1         paladin    100%    100%     33.0     40.0    +7.0      43.1    49.5
```

### The four families the brief flagged

* **`paladin__vs__elite_steppe` (n=12) — the one genuine miss.** Tape: paladin 75%
  (9/12) at 15.3% HP. Engine: **elite_steppe in 240/240 seeds**, paladins at 0% HP.
  The engine still picks steppe. Not a marginal disagreement — a unanimous one.
* **`hussar__vs__elite_steppe` (n=7) — right answer, right margin.** Tape hussar 71%
  (5/7) at 10.7% HP; engine hussar 100% at 11.8%. HP error +1.1 pts. The engine is
  over-confident on the *share* (100% vs 71%) but the surviving-HP margin is nearly
  exact, which is what a 71/29 coin-flip family should look like.
* **`heavy_camel__vs__elite_elephant` (n=7) — right answer, thin margin under-called.**
  Tape camel 86% (6/7) at 18.9% HP; engine camel 100% at 9.1%. Camel HP −9.8 pts:
  the engine wins the same fight with about half the army left over.
* **`champion__vs__paladin` (n=7) — right answer, margin badly inflated.** Tape
  champion 86% (6/7) at **19.2%** HP; engine champion 100% at **43.8%**. **+24.6 pts**
  — the largest side error on the board. The engine's champions win far too cheaply.

Corpus-level (`melee_hp_report.py`, 58 pure-melee fights): all_melee n=116 sides,
mean \|err\| 7.07 pts, median 3.91; ≤10 pts on 86/116; basic_melee n=40 mean 6.44,
median 0.79; winners 45/58, basic 19/20.

---

## 4. Old vs new truth — which recordings were miscaptured

Tape against tape; no engine involved. `HP%` is the winning side's mean remaining HP.

```
family                             oldn      old winner   shr   HP%  newn      new winner   shr   HP%  verdict
--------------------------------------------------------------------------------------------------------------
champion__vs__elite_elephant          1  elite_elephant  100%    51     1  elite_elephant  100%    49  agrees
champion__vs__elite_fire_lancer       1        champion  100%    52     1        champion  100%    58  agrees
champion__vs__elite_steppe            1        champion  100%    33     1        champion  100%    41  agrees
champion__vs__halberdier              1        champion  100%    67     1        champion  100%    73  agrees
champion__vs__heavy_camel             1        champion  100%    72     1        champion  100%    71  agrees
champion__vs__hussar                  1        champion  100%    43     1        champion  100%    43  agrees
champion__vs__paladin                 6        champion   83%    31     7        champion   86%    22  agrees
elite_fire_lancer__vs__elite_eleph    1 elite_fire_lanc  100%    68     1 elite_fire_lanc  100%    63  agrees
elite_fire_lancer__vs__elite_stepp    1 elite_fire_lanc  100%    60     1 elite_fire_lanc  100%    46  agrees
elite_fire_lancer__vs__heavy_camel    1 elite_fire_lanc  100%    83     1 elite_fire_lanc  100%    72  agrees
elite_fire_lancer__vs__hussar         1 elite_fire_lanc  100%    70     3 elite_fire_lanc  100%    69  agrees
elite_fire_lancer__vs__paladin        1 elite_fire_lanc  100%    63     1 elite_fire_lanc  100%    50  agrees
elite_steppe__vs__elite_elephant      1  elite_elephant  100%    53     3  elite_elephant  100%    58  agrees
halberdier__vs__elite_elephant        1      halberdier  100%    76     1      halberdier  100%    79  agrees
halberdier__vs__elite_fire_lancer     1 elite_fire_lanc  100%    62     1 elite_fire_lanc  100%    35  margin moved +27pts
halberdier__vs__elite_steppe          1      halberdier  100%    68     1      halberdier  100%    69  agrees
halberdier__vs__heavy_camel           1      halberdier  100%    85     3      halberdier  100%    85  agrees
halberdier__vs__hussar                1      halberdier  100%    82     3      halberdier  100%    81  agrees
halberdier__vs__paladin               1      halberdier  100%    70     1      halberdier  100%    77  agrees
heavy_camel__vs__elite_elephant       1     heavy_camel  100%    14     7     heavy_camel   86%    22  agrees
heavy_camel__vs__elite_steppe         1     heavy_camel  100%    22     1     heavy_camel  100%    41  margin moved -19pts
hussar__vs__elite_elephant            1  elite_elephant  100%    75     3  elite_elephant  100%    64  agrees
hussar__vs__elite_steppe              1          hussar  100%    11     7          hussar   71%    15  agrees
hussar__vs__heavy_camel               1     heavy_camel  100%    62     1     heavy_camel  100%    63  agrees
paladin__vs__elite_elephant           1  elite_elephant  100%    58     1  elite_elephant  100%    44  agrees
paladin__vs__elite_steppe             6    elite_steppe   83%    20    12         paladin   75%    20  *** MISCAPTURED
paladin__vs__heavy_camel              1     heavy_camel  100%    62     1     heavy_camel  100%    56  agrees
paladin__vs__hussar                   1         paladin  100%     5     1         paladin  100%    33  margin moved -28pts
```

**27 of 28 overlapping families agree on the winner.** The old melee corpus was not
broadly fake — one family was.

### Quarantine recommendations (measurement-backed; the call is the main session's)

1. **Quarantine — `paladin__vs__elite_steppe`, the 6 old recordings**
   (`paladin__vs__elite_steppe` and `_r2`..`_r6`). Old says steppe 83%, v2 says
   paladin 75% over twice the sample. Directly contradicted; 12 v2 recordings
   supersede them.
2. **Re-record before trusting — 3 families whose winner held but whose margin moved
   ≥15 pts.** A margin is what every HP constant is fitted against:
   `halberdier__vs__elite_fire_lancer` (+27 pts), `paladin__vs__hussar` (−28 pts),
   `heavy_camel__vs__elite_steppe` (−19 pts). Each is old n=1 vs new n=1, so neither
   side is well sampled; treat both as provisional rather than quarantining either.
3. **Down-weight, do not quarantine — `hussar__vs__elite_steppe`.** V2 shows it as a
   71%-at-15%-HP coin flip; the old corpus has n=1 calling it 100%. The old
   recording agreeing is luck, not confirmation. Weight the family by the v2 share.
4. **Keep — the other 23 overlapping families,** including `champion__vs__paladin`
   (old champion 83% / new 86%; the brief's expectation that this capture was fine
   is confirmed).
5. **No v2 evidence either way — the 64 old families with no re-recording** (every
   ranged and mixed pairing). Nothing here speaks to them. They were recorded with
   the same setup as the melee families that turned out fine, and the one confirmed
   defect is matchup-specific, so a blanket quarantine is not supported by this data.

---

## 5. Duration — the "melee is too fast" signal is a recorder artifact

A truth card's `duration_s` is the **recorder segment length**, not the fight's. The
capture keeps running after the last unit falls. Across the 28 v2 families the mean
card duration is **46.9 s** while the mean actual wipe (last damage event in the
tape's own stream) is **29.0 s** — a ~18 s tail of nothing.

| sim duration measured against | mean ratio | median ratio |
|---|---|---|
| truth-card `duration_s` | 0.595 | 0.570 |
| **tape actual wipe** | **0.975** | **0.915** |

`melee_hp_report.py` reports "duration ratio (sim/tape): basic 0.525, all 0.716" —
that is the first row, and it is comparing against the tail. **Against the real wipe
the engine's melee pacing is essentially correct.** Worst outliers are
`elite_fire_lancer__vs__elite_steppe` 0.67x and `hussar__vs__heavy_camel` 1.28x; the
paladin/steppe family runs 1.21x long (55.1 s vs 45.6 s), consistent with the engine
grinding out a fight the game had already decided.

Any melee-pacing constant fitted against truth-card `duration_s` was fitted against
a ~1.6x inflated target.

---

## 6. Overfit audit

### 6a. Corpus level — the melee stack is *not* fitted to the fake truth

The engine was run on both corpora, each fight from its own first-frame spawns and
scored against its own recording's outcome — 38 old-corpus fights in the 28
overlapping families, and the 67 v2 fights.

| | vs OLD truth | vs V2 truth |
|---|---|---|
| families where the engine picks the tape's majority winner | 26 / 28 | **27 / 28** |
| mean \|HP error\| per family (pts of army max) | 5.31 | **4.16** |

**The engine agrees with the new truth more than with the old.** If the melee stack
had been fitted to the bad capture, this would run the other way.

Only one family shows the overfit signature (engine matches old, contradicts v2):
`paladin__vs__elite_steppe`. Two families move the *other* way — the engine picked
the **wrong** winner on the old recordings and the **right** one on v2, with the HP
error collapsing: `heavy_camel__vs__elite_elephant` (16.6 → 6.0 pts) and
`hussar__vs__elite_steppe` (18.8 → 3.2 pts).

### 6b. The lane-rule A/B — hypothesis refuted

The brief's hypothesis was that E15b's lane rule flipped `paladin__vs__elite_steppe`
toward the fake truth.

`MELEE_LANE_REACQUIRE` is a bare `export const` in `constants.js` with **no runtime
toggle** — `calib_runner.mjs --r5b` only reaches the R5b ranged rules via `setR5B`.
So the A/B was run from an **out-of-repo scratch mirror** of
`apps/website/static/js/engine/` + `tools/simjs/` + `data/calibration/`, with that
one line flipped. **No repo file was modified.** The mirror was first validated as a
control: run unflipped, it reproduced all 1 340 baseline seed files **byte-identically**,
and `diff -r` against the repo engine shows exactly one differing line.

| | lane ON (landed) | lane OFF |
|---|---|---|
| per-seed agreement with the family's tape winner (n=1340) | 82.1% | **82.1%** |
| mean \|HP error\| per family | **4.16** | 4.28 |
| `paladin__vs__elite_steppe` seed wins | steppe **240/240** | steppe **240/240** |
| ...elite_steppe HP error | **+0.7 pts** | **+13.1 pts** |
| families whose winner the rule flips | — | **none** |

**The lane rule is not what makes steppe beat paladin.** Switching it off changes no
family's winner, leaves corpus agreement identical, and makes the paladin/steppe HP
error 19x worse. E15b's lane rule is **genuinely supported**, not fitted to the bad
capture.

### 6c. What is actually wrong — the outnumbered side is under-engaged

Per-metric, over the 12 `paladin__vs__elite_steppe` recordings:

| metric | paladin (15) tape → sim | elite_steppe (21) tape → sim |
|---|---|---|
| hits_landed | 138.3 → 137.0 (**0.99x**) | 228.7 → 270.0 (**1.18x**) |
| damage_dealt | 1979 → 1965 (**0.99x**) | 2287 → 2700 (**1.18x**) |
| swing_interval_median | 1.92 → 1.92 (**1.00x**) | 2.02 → 2.02 (**1.00x**) |
| kills | 19.2 → 18.0 | 11.0 → 15.0 |
| hp_remaining | 413 → **0** | 121 → 135 |

The paladins' offence is reproduced almost exactly. The steppe lancers land **18%
more hits than the game gives them**, and the surplus (+413 damage) is precisely the
paladin HP the tape says should have survived (413). Swing cadence matches to the
millisecond on both sides, so this is **not** attack speed and **not** damage or
armour — it is *how many bodies are swinging*.

Measuring concurrent attackers directly (distinct units of a side landing a hit in a
2.5 s sliding window; sim = 5 seeds/recording):

| family / side | army | tape | sim | ratio |
|---|---|---|---|---|
| paladin__vs__elite_steppe / **paladin** | 15 | 6.74 | 5.07 | **0.75x** |
| paladin__vs__elite_steppe / elite_steppe | 21 | 11.12 | 10.12 | 0.91x |
| champion__vs__paladin / champion | 21 | 8.86 | 9.05 | 1.02x |
| champion__vs__paladin / **paladin** | 9 | 5.55 | 4.05 | **0.73x** |
| hussar__vs__elite_steppe / hussar | 21 | 7.92 | 6.46 | 0.82x |
| hussar__vs__elite_steppe / elite_steppe | 12 | 7.79 | 6.11 | 0.78x |
| heavy_camel__vs__elite_elephant / heavy_camel | 20 | 9.06 | 7.14 | 0.79x |
| heavy_camel__vs__elite_elephant / elite_elephant | 14 | 6.56 | 5.36 | 0.82x |

The engine gets fewer bodies into contact than the game does across the board. What
matters is the **asymmetry**: in the two families with the largest HP errors, the
*outnumbered* side is the one that loses engagement.

* `paladin__vs__elite_steppe`: paladin (15, outnumbered) **0.75x** vs steppe (21) 0.91x → paladins wiped.
* `champion__vs__paladin`: paladin (9, outnumbered) **0.73x** vs champion (21) 1.02x → champions win at 43.8% instead of 19.2% HP.

In the two families where both sides lose engagement roughly equally
(`hussar__vs__elite_steppe` 0.82/0.78, `heavy_camel__vs__elite_elephant` 0.79/0.82),
the winner and margin come out close to the tape.

**Stated carefully:** this is a correlation over four families, not a proven
mechanism. What is established is that the paladin/steppe miss lives entirely in the
steppe side's hit *count* while every rate matches, and that the engine's contact
concurrency for the outnumbered side is the metric that tracks the error. The engine
appears to let a numerically superior melee side surround and shut out the smaller
one harder than the game does.

### 6d. Verdict per behaviour

| melee behaviour | status against v2 |
|---|---|
| E15b lane re-acquisition (`MELEE_LANE_REACQUIRE`) | **Genuinely supported.** A/B shows off is strictly worse; flips nothing. |
| Swing cadence / recovery | **Genuinely supported.** `swing_interval_median` matches to 1.00x on both sides of the worst family. |
| Damage / armour resolution | **Genuinely supported.** Paladin hits and damage reproduce at 0.99x. |
| Melee pacing (fight duration) | **Supported once measured correctly** (0.98x vs actual wipe). Any constant fitted to truth-card `duration_s` was fitted to a 1.6x inflated target. |
| E11 collision radii + contact/engagement capacity | **Not supported for asymmetric army sizes.** The one flipped family and the largest margin error both trace to the outnumbered side getting too few units into contact. |
| E14 target lock | **Untested here.** Target selection is a positional behaviour and v2's position channel is dead (§1b); nothing in this run isolates it. |

---

## 7. What this run cannot tell you

* **Anything positional about v2** — the position channel is frozen (§1b). Approach,
  standoff, pursuit, walk paths and lane geometry are unscoreable against these 67
  recordings.
* **The v2 arena walls** — unknown, not measured. Do not author a tapebox variant
  from the spawn footprint.
* **The 64 old families with no v2 counterpart** — untouched by this evidence.
* **Whether the engagement asymmetry in §6c is causal** — it is a correlation across
  four families with a clean mechanistic story, not an isolated experiment.

---

## Artifacts

| what | where |
|---|---|
| regenerated spawns (222 tapes, +67 v2) | `data/calibration/spawns.json` |
| v2 truth cards (67, verified reproducible via `aoe2x.calibration.extract`) | `data/calibration/truth/*_r*.json` |
| per-recording scoreboard | `data/calibration/runs/20260731T064907Z-v2melee-baseline-*.json` |
| family board tool (new) | `tools/simjs/v2_family_board.py` |
| baseline sim runs | `D:/AI/aoe2_golden/simruns_v2melee` (1340 files) |
| lane-off A/B sim runs | `D:/AI/aoe2_golden/simruns_v2melee_nolane` |
| old-corpus counterpart runs | `D:/AI/aoe2_golden/simruns_oldmelee` (760 files) |

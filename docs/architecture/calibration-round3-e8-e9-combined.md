# Calibration Round 3 — E8 (density) x E9 (fire cycle) combined: HOLD, do not land

**Verdict: neither combined variant is a net win. The merge is NOT landed.**
It sits on the local branch `r3-combined-hold` (merge commit `4a480dc`, tests
76/76 green). Only the four scoreboard JSONs and this note are on
`improved-simulation`.

## What was run

Four full corpus runs, all on the **same 155-fight manifest** (the corpus grew
mid-experiment when the arb-vs-steppe and HCA-vs-camel rerun families landed in
`0eda317`; every run below was re-done at 155 so the comparison is
corpus-consistent), 20 seeds each, scored with
`python -m aoe2x.calibration.score --all --sim-runs-dir <dir>`.

| run | engine | scoreboard |
|---|---|---|
| `r3-baseline` | `improved-simulation` @ `0eda317` (no E8, no E9) | `20260730T192903Z-r3-baseline.json` |
| `r3-combined-global` | E8+E9, `COMBAT_PACK_RANGED = true` | `20260730T192916Z-r3-combined-global.json` |
| `r3-combined-meleeonly` | E8+E9, `COMBAT_PACK_RANGED = false` | `20260730T192924Z-r3-combined-meleeonly.json` |
| `r3-e8only-supplementary` | E8 alone (global), no E9 | `20260730T193543Z-r3-e8only-supplementary.json` |

The E8-only run was not in the original mandate. It was added because neither
combined variant passed the landing gate, and without it the report could only
say "hold everything" — with it, there is an actionable next step.

## Aggregate

|  | baseline | **E8 only** | combined global | combined melee-only |
|---|---|---|---|---|
| winner match / 155 | 127 | **130** | 128 | 127 |
| winner flips | 28 | **25** | 27 | 28 |
| mean per-seed agreement | 0.7935 | 0.8181 | **0.8232** | 0.8135 |
| gated MISMATCH rows | 855 | **831** | 891 | 942 |
| verdict PASS | 10 | **12** | **12** | 10 |
| verdict INCONCLUSIVE | 2 | 1 | 2 | 4 |
| median sim/tape duration ratio† | 0.748 | 0.761 | 0.668 | 0.645 |

† over the 151 fights where no variant hit the 600 s tick cap. Tape mean 62.9 s.

**Global beats melee-only on every single axis** — winners, agreement, gated
MISMATCH, PASS, INCONCLUSIVE, and net family-share movement (+0.97 vs +0.18 summed
over families). If the combination is ever landed it should be with
`COMBAT_PACK_RANGED = true`. Melee-only is not a live option.

## Why global still fails the landing gate

Winner ledger vs baseline, grouped by family:

```
combined-global   fixed 13 / broke 12  =  net +1
  + halberdier__vs__heavy_cav_archer   6   (tape 6/6 halbs — full fix, E9's target)
  + champion__vs__paladin              5   (tape 5/6 champs — now matches the majority)
  + champion__vs__heavy_cav_archer     1
  + hussar__vs__elite_steppe           1
  - champion__vs__heavy_cav_archer     8   (tape 8/9 HCA — now 1/9. WRONG direction)
  - arbalester__vs__elite_elephant     3   (tape 3/3 elephants — now 0/3)
  - champion__vs__paladin              1   (r4, the tape's own 1-in-6 upset)
```

The +1 headline is arithmetic, not progress: it is bought by taking the
**largest family in the corpus** from 8/9 correct to 1/9. Two families that were
solid in the baseline are broken, and the error metric E8's own author treated
as headline (gated MISMATCH) goes **855 -> 891**. That fails the gate on both
"without breaking currently-solid families" and on the error metric, so the
merge is held.

## Per-family scorecard vs tape share (mean per-seed agreement WITH the tape winner)

| family | n | tape share | base | E8 only | global | melee |
|---|---|---|---|---|---|---|
| halberdier__vs__heavy_cav_archer | 6 | halbs 6/6 | 0.00 | 0.00 | **1.00** | 1.00 |
| champion__vs__heavy_cav_archer | 9 | HCA 8/9 | 0.62 | **0.81** | 0.15 | 0.11 |
| hand_cannoneer__vs__heavy_camel | 6 | HC 6/6 | 0.30 | **0.70** | 0.15 | 0.00 |
| champion__vs__paladin | 6 | champs 5/6 | 0.40 | **0.67** | 0.67 | 0.67 |
| hand_cannoneer__vs__paladin | 6 | paladin 5/6 | 0.83 | 0.80 | 0.83 | 0.83 |
| hand_cannoneer__vs__hussar | 6 | hussar 4/6 | 0.67 | 0.67 | 0.67 | 0.67 |
| heavy_cav_archer__vs__elite_steppe | 6 | steppe 6/6 | 0.80 | 0.95 | **1.00** | 1.00 |
| heavy_cav_archer__vs__heavy_camel | 6 | camels 6/6 | 0.60 | 0.15 | **1.00** | 1.00 |
| paladin__vs__elite_steppe | 6 | steppe 5/6 | 0.17 | 0.33 | 0.33 | 0.33 |
| champion__vs__arbalester | 6 | arbs 6/6 | 1.00 | 1.00 | 1.00 | 1.00 |
| arbalester__vs__elite_steppe | 6 | steppe 6/6 | 1.00 | 1.00 | 1.00 | 1.00 |
| elite_steppe__vs__arbalester | 1 | arbs 1/1 | 0.00 | 0.00 | 0.00 | 0.00 |
| arbalester__vs__elite_elephant | 3 | elephants 3/3 | 1.00 | 0.95 | 0.10 | 0.10 |

By fight class:

| class | n | base agr / gMM / wins | global agr / gMM / wins |
|---|---|---|---|
| melee-vs-melee | 31 | 0.692 / 104 / 20 | **0.795 / 64 / 25** |
| ranged-vs-melee | 79 | 0.728 / 418 / 62 | 0.786 / 481 / 61 |
| elephant / trample | 14 | **0.964 / 86 / 14** | 0.704 / 104 / 11 |
| scorpion (untuned) | 13 | 0.965 / 118 / 13 | **1.000 / 112 / 13** |
| onager | 12 | 0.996 / 115 / 12 | **1.000 / 113 / 12** |
| ranged-vs-ranged | 6 | 1.000 / 14 / 6 | 1.000 / 17 / 6 |

Scorpion, reported separately as always: E8 takes the 13 scorpion fights to a
clean 1.000 agreement, 13/13 winners, and sheds 6 gated mismatches. No variant
harms it.

## The two mechanics genuinely interact — in both directions

This is the one real discovery of Round 3, and it is why the combination is
worth keeping alive rather than discarding:

* **E9 repairs E8's worst regression.** E8 alone breaks
  `heavy_cav_archer__vs__heavy_camel` (tape camels 6/6) from 0.60 to 0.15 — all
  six recordings flip to HCA. E9's slowed fire cycle restores it to a perfect
  **1.00** in the combination. E8-only cannot ship past this family; E8+E9 can.
* **E8 partly cushions E9's.** E9 alone zeroes `hand_cannoneer__vs__heavy_camel`
  (tape HC 6/6, 0.30 -> 0.00); density recovers it to 0.15 global (and 0.00
  melee-only — another reason melee-only is dead).
* **They do not help each other at all on champion-vs-HCA.** The Round 3
  hypothesis was that density plus cadence together might land HCA-majority on
  that knife-edge family. It does not: E8 alone *improves* it (0.62 -> 0.81),
  E9 alone destroys it (-> 0.15), and the combination sits at E9's number, 0.15.
  Density does not rescue it, and the two effects are not additive here.

## Attribution of every notable move (E8 alone vs E9 alone vs combined)

| family | base | E8 alone | E9 alone | combined-global | owner |
|---|---|---|---|---|---|
| halberdier__vs__heavy_cav_archer | 0.00 | 0.00 | 1.00 | 1.00 | E9 |
| champion__vs__heavy_cav_archer | 0.62 | 0.81 | 0.15 | 0.15 | E9 (regression) |
| hand_cannoneer__vs__heavy_camel | 0.30 | 0.70 | 0.00 | 0.15 | E9 (regression) |
| champion__vs__paladin | 0.40 | 0.67 | 0.35 | 0.67 | E8 |
| heavy_cav_archer__vs__heavy_camel | 0.60 | 0.15 | 1.00 | 1.00 | E8 breaks, E9 fixes |
| hussar__vs__elite_steppe | 0.05 | 0.70 | 0.05 | 0.70 | E8 |
| paladin__vs__elite_steppe | 0.17 | 0.33 | — | 0.33 | E8 |
| arbalester__vs__elite_elephant | 1.00 | 0.95 | 0.10 | 0.10 | E9 (regression) |
| elite_steppe__vs__elite_elephant | 1.00 | 0.55 | 1.00 | 0.55 | E8 (regression) |

(E8-alone / E9-alone columns are each branch's own scoreboard on the 125- and
140-fight corpora respectively; only families present in both are listed.)

### Caveat on arbalester__vs__elite_elephant

The baseline's 1.00 there is a **tick-cap artifact, not a solid result**: all
three recordings run the full 600 s cap in the baseline (tape duration 116 s)
and the winner is decided by who is ahead on survivors when the cap hits — 2
arbalesters vs 9 elephants. Under the combination the fight actually resolves
(~512 s, still 4.4x too long) and resolves the wrong way: 13 arbalesters
survive and all 9 elephants die. The family is wrong in both configurations;
the baseline was merely flattered. It is still counted as a flip above.

## Duration: the combination makes the "too fast" problem worse

The sim already ends fights at 0.748 of tape length. E8 alone is neutral
(0.761). E9 drags it down to **0.668** (global) / 0.645 (melee-only) — the
target families move the wrong way (halberdier-vs-HCA 35.7 s -> 26.4 s against a
tape 55.1 s; arbalester-vs-steppe 36.8 -> 30.2 against a tape 70.6). So the
open "fights end too fast" thread is aggravated, not relieved, by the fire-cycle
work in its current form.

## Recommendation

1. **Do not land E8+E9 as-is.** Held on `r3-combined-hold`.
2. **E8 alone is the strongest single candidate on this corpus** — the only
   variant that improves winners (130), gated MISMATCH (831) and PASS
   simultaneously, and the only one that does not aggravate the duration gap.
   It is blocked on one thing: it breaks `heavy_cav_archer__vs__heavy_camel`
   (6 recordings, 0.60 -> 0.15, tape camels 6/6). Landing E8 means fixing or
   accepting that family.
3. **E9 is measured truth with a mis-attributed cost.** Its fire-cycle law is
   read directly off 21,296 tape gaps and its cadence metrics are decisively
   better; the outcome damage it does is concentrated in exactly the fights the
   E9 report already identified as blocked on kite-ball dispersion. E9 should
   not be re-tuned to fit — the blocker is the dispersion fix (E5a cohesion
   territory), and E9 should be re-scored after it.

## Open threads (unchanged by Round 3)

* **champion-vs-heavy_cav_archer is blocked on kite-ball dispersion.** Neither
  density nor cadence moves it in the right direction; E8 improves it only by
  leaving the kiters where they were. E5a cohesion territory.
* **hand_cannoneer-vs-heavy_camel needs the approach damage race**
  (targeting/overkill during the camels' charge), not spacing and not cadence:
  every knob tried so far moves it as a side effect and none addresses the
  mechanism.
* **Fights still end too fast** — and E9 currently makes it worse.
* **elite_steppe__vs__arbalester stays at 0.00 in all four runs.** The bimodal
  pair is unmoved: `arbalester__vs__elite_steppe` is 1.00 everywhere and its
  mirror is 0.00 everywhere, so the sim is picking steppe in both directions.
* `parity_check.mjs` was deliberately not run (campaign-wide deferral, as on
  the E8 and E9 branches themselves); both are intentional behaviour changes
  and would fail it. `node --test tests/js/engine/` is **76/76** on the merge
  (59 base + 10 E8 + 7 E9).

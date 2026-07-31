# Phase C — the melee-chaser-vs-kiter cadence

Measurement only. No engine file is touched, no rule is proposed, nothing is
enabled. This document measures the one defect E12 named and never explained,
and produces the two enable ledgers the campaign has been blocked on.

E12's finding, corpus-wide: a melee unit's swing-interval ratio tape/engine is
**1.001 in melee-vs-melee** but **1.29 when the melee unit is CHASING a RANGED
one** (mean 1.493, p90 2.11). The tape's chasers keep losing and re-winning
contact with their kiting victims in a way the engine does not model. Two
tape-true mechanics are shipped OFF behind it — `R5D1.trailingWindowLead`
("P2") and `R5D1.reducedDamageHits` ("P1") — and it owns most of the remaining
ranged-vs-melee misses.

| | question |
|---|---|
| **M1** | Does the 1.29 hold on the current engine and the tapebox rig, and WHERE does the extra time in a tape chaser's cycle go? |
| **M2** | When a tape chaser loses contact, what happened — victim burst, chaser overshoot, collision? Is this a phase race that should EMERGE from a correct kiter rhythm? |
| **M3** | Where do the engine chaser's extra hits come from — the kiter fleeing too late, standing too long, or the chaser reaching farther / swinging in windows the tape has not got? |
| **M4** | Do tape chasers stick to the chase, and what does the engine's PURSUIT_BAR/blacklist actually do in these fights today? |
| **M5** | With P2 ON, where exactly does the champion-vs-HCA flip come from, and what must a correct chaser-cadence model produce for P2 to be safe? |
| **M6** | Under the current engine, what is the hand cannoneer's land rate per family, and what is the precise P1 flip criterion? |

## The six answers, one line each

- **M1** — Confirmed and sharpened: **T/E median 1.22** over 29 melee-swing
  families (min 0.93, max 1.95), and the decomposition says the tape chaser is
  **in reach for 0.66 s of its cycle against the engine's 1.81 s** while
  **97.2 % of tape cycles lose contact against the engine's 54.1 %**. The
  tape's melee unit is not reload-limited, it is CONTACT-limited; the engine's
  is reload-limited and never leaves.
- **M2** — Not a rhythm race and not a chaser-side failure. The tape kiter
  **breaks contact with the unit that just hit it in a median 0.08 s** and runs
  **almost straight away from that unit (cos 0.88)**; the engine's takes
  **0.42 s** and runs at **cos 0.61** (median over the 29 melee-swing
  families), netting **0.05 tiles** of radial
  separation against the tape's **1.03**. For the Heavy Cavalry Archer the
  engine's stop/move DUTY CYCLE is already right (0.688 vs 0.659) — so this is
  a flee-DIRECTION and flee-LATENCY defect on the kiter, not a duty-cycle one.
  For the three slow shooters (HC / skirmisher / arbalester) the duty cycle is
  wrong too, by up to 2.2x.
- **M3** — The engine chaser out-hits the tape's on **all 29 families**, median
  **1.44x** per chaser-second, and every route is measurable: it lands
  **55.2 %** of its blows on a STOPPED victim against the tape's **9.9 %**; it
  lands **19.8 %** of them while itself moving, which the tape does **0.0 %**
  of the time in **every single family**; and it hits at **0.99x its own
  reach** where the tape hits at **1.43x**.
- **M4** — Neither corpus shows a chaser that walks away from a reachable
  victim more than the other; the tape actually abandons MORE in the slow-kiter
  families (HC-vs-camel 54.3 % vs 0.4 %). The engine's pursuit bar is loud and
  inert: in the fast-kiter families it blacklists **16–52 times per
  chaser-minute** (the lock is structurally unavailable — `meleeTargetLock()`
  returns false when `target.isRanged()`), yet **null-target time is 0.0–1.5 %**
  and the median re-acquire gap is **0.02 s**. It re-picks the same class of
  victim immediately.
- **M5** — Measured, not assumed: ENG agrees with the tape on **8/9**
  recordings, ENG+P2 on **1/9**. The flip is not because P2 makes the HCA worse
  at shooting (its land rate goes 96.6 → 97.8 %); it is because **the engine's
  champions already deliver 98.2 % of the HCA army's max HP per run against the
  tape's 62.8 %**, so the fight is knife-edge and P2's 28 % cut in HCA output
  tips it. The enable criterion is a number: **champion damage per run must
  fall from 943 to ~603 (0.64x), i.e. hits per chaser-second from 0.1352 to
  0.0772 (0.57x)**.
- **M6** — The HC's land rate is NOT the blocker any more: in the family that
  flips (`hand_cannoneer__vs__heavy_camel`) the engine already lands **86.8 %**
  against the tape's **86.1 %**, and its damage per resolvable shot is **10.84
  vs 10.47** (+3.5 %). The blocker is on the CHASER side of the same fight:
  the engine's camels deliver **70.3 % of the HC army's max HP per run against
  the tape's 32.5 %** (2.16x). P1 costs the HC 6.9 % of its damage per shot and
  that is enough to flip **6/6 → 0/6**.

---

## How this was measured

```
# the corpus is DERIVED, not listed -- the same filter feeds both tools
PYTHONPATH=. python tools/simjs/c1_chaser_cadence.py --print-tags > tags.txt

node tools/simjs/c1_chase_probe.mjs --tags-file tags.txt \
     --seeds 20 --out-dir D:/AI/aoe2_golden/simruns_c1
node tools/simjs/c1_chase_probe.mjs --tags-file <champion x9> --seeds 20 \
     --r5d1 trailingWindowLead --out-dir D:/AI/aoe2_golden/simruns_c1_p2
node tools/simjs/c1_chase_probe.mjs --tags-file <hand cannoneer x29> --seeds 20 \
     --r5d1 reducedDamageHits --out-dir D:/AI/aoe2_golden/simruns_c1_p1

PYTHONPATH=. python tools/simjs/c1_chaser_cadence.py --section all --seeds 20
```

(`--print-tags --families <matchup,...>` narrows it; the P2 and P1 lists above
are `champion__vs__heavy_cav_archer` and every fight with a hand cannoneer on
either side.)

**Corpus.** Every non-quarantined recording with exactly one non-siege ranged
side and one melee side: **86 recordings, 33 families**. Siege is excluded by
construction (`heavy_scorpion`, `siege_onager` have a minimum-range dead zone,
their own repositioning path and are gated out of group-kite, so a melee unit
walking at one is a different mechanic). Quarantined fights are dropped by
`loadManifest` on both the JS and the Python side.

**Engine.** `improved-simulation` HEAD (`0e2dbc5`), `tapebox` arena, 20 seeds
per recording, all rule flags at their shipped defaults except where a column
says otherwise. `T` = tape, `E` = engine pooled over seeds.

**The probe.** `tools/simjs/c1_chase_probe.mjs` installs four prototype
wrappers (`fireProjectile` / `update` / `meleeTargetLock` /
`meleeBumpRetarget`) from `tools/`, each of which calls straight through and
only reads state around it. `--verify-identity` re-runs every (fight, seed)
with the wrappers removed and diffs the damage stream and duration: **PASS on
every run**. It writes the same `seed-N.shots.json` schema
`ranged_shot_dump.mjs` writes, so `ranged_fire_forensics.load_engine` reads it
unchanged, plus a `seed-N.chase.json` chaser ledger the tape cannot produce.

**One implementation, two sources.** Everything except Table 4b is computed by
the same Python function over a normalised `Fight` — 10 Hz positions with
interpolation, damage stream, missile stream, engine-equivalent wipe-time cut —
built either from a recording's three `.jsonl.gz` streams or from the engine
dump. Reach is `ranged_fire_forensics.engine_reach`, i.e. `BattleUnit.inRange()`
itself (`attack_range*TILE + MELEE_RANGE_BUFFER + both physics radii`),
validated in E15 to within 0.02 tiles of the observed contact distance on all
42 class pairs of the melee corpus.

**Excluded from pooled headlines** (printed, not pooled): the four
`elite_fire_lancer`-as-chaser families. Its damage comes from a charge
projectile with a blast radius — measured median attacker-victim distance at a
landed hit is **5.06 tiles on tape against a 0.57-tile melee reach** — so its
damage events arrive in bursts and would read as a 0.12 s "swing cycle".

---

## M1. Chaser swing anatomy

An inter-hit interval is `reload` seconds of unavoidable cooldown plus EXCESS.
The decomposition below splits every interval over the 10 Hz samples inside it
into **in reach** (at least one living kiter inside the chaser's own reach —
"could have swung at somebody", the engine's own predicate, taken against ANY
living kiter so that an honest switch to a nearer body is not scored as lost
contact), **oorC** (nothing in reach, closing) and **oorF** (nothing in reach,
not closing).

```
======================================================================================================================
TABLE 1 -- CHASER SWING ANATOMY. Inter-hit intervals of the melee side against the kiting side, and where the
time in each interval goes. `T/E` is the tape/engine ratio of the MEDIAN interval (E12's 1.29 headline, per family).
Decomposition columns are MEAN SECONDS PER INTERVAL: rl = the unit's own reload, oorC/oorF = out of reach while
closing / while not closing, inR = in reach and not swinging. `lost%` = intervals that left reach at all.
======================================================================================================================
family                                 src       n    med   mean    p90   /rl   T/E  lost%   oorC   oorF    inR
---------------------------------------------------------------------------------------------------------------
champion__vs__heavy_cav_archer         T       319   2.77   3.70   7.04  1.39  1.38   97.2   1.29   1.75   0.66
                                       E     10800   2.02   3.05   6.29  1.01         63.3   0.50   0.54   2.02
champion__vs__arbalester               T         9   2.46   2.43   2.94  1.23  1.22  100.0   0.52   1.46   0.46
                                       E       120   2.02   2.02   2.02  1.01          0.0   0.00   0.00   2.02
halberdier__vs__heavy_cav_archer       T        89   3.32   4.19   6.78  1.11  0.93   98.9   1.47   1.72   1.00
                                       E      1320   3.57   4.30   6.02  1.19         90.9   1.17   1.06   2.07
arbalester__vs__elite_steppe           T       386   2.03   3.22   6.46  1.02  1.01   77.5   0.93   1.07   1.23
                                       E      8280   2.02   2.29   3.48  1.01         71.0   0.29   0.25   1.75
hand_cannoneer__vs__hussar             T       307   2.88   3.89   7.93  1.51  1.50   99.0   1.71   1.82   0.36
                                       E      8340   1.92   2.24   2.35  1.01         41.5   0.22   0.24   1.79
hand_cannoneer__vs__paladin            T       245   3.21   4.06   7.42  1.69  1.67   97.6   1.81   1.78   0.47
                                       E      6198   1.92   2.25   2.92  1.01         59.4   0.26   0.25   1.74
heavy_cav_archer__vs__elite_steppe     T       842   2.02   2.78   4.76  1.01  1.00   65.8   0.51   0.70   1.57
                                       E     17640   2.02   2.23   2.27  1.01         58.5   0.22   0.23   1.79
heavy_cav_archer__vs__heavy_camel      T       365   2.03   2.99   5.36  1.01  1.01   93.4   0.78   1.41   0.80
                                       E      7920   2.02   2.46   3.13  1.01         68.2   0.34   0.33   1.79
hand_cannoneer__vs__heavy_camel        T       138   2.51   3.80   7.38  1.26  1.25   95.7   1.57   1.74   0.49
                                       E      8184   2.02   2.54   3.58  1.01         61.2   0.36   0.45   1.72
arbalester__vs__elite_elephant         T       103   3.30   3.85   6.21  1.65  1.64   95.1   1.63   1.63   0.60
                                       E      2220   2.02   2.78   6.50  1.01         54.1   0.32   0.29   2.17
arbalester__vs__paladin                T       126   2.50   3.64   7.06  1.32  1.30   97.6   1.42   1.78   0.45
                                       E      3120   1.92   2.31   3.83  1.01         61.5   0.25   0.26   1.80
hand_cannoneer__vs__elite_elephant     T        63   3.54   4.33   7.43  1.77  1.76   95.2   1.95   1.72   0.66
                                       E      1258   2.02   2.55   2.98  1.01         50.1   0.29   0.24   2.02
elite_steppe__vs__arbalester           T        53   2.02   2.91   5.08  1.01  1.00   73.6   0.70   0.85   1.35
                                       E      1380   2.02   2.29   3.48  1.01         71.0   0.29   0.25   1.75
champion__vs__hand_cannoneer           T         3   3.93   3.40   4.14  1.97  1.95  100.0   1.54   1.72   0.14
                                       E       150   2.02   2.74   5.53  1.01         45.3   0.38   0.30   2.06
champion__vs__imp_elite_skirm          T        42   3.20   4.21   7.91  1.60  1.59   97.6   1.83   1.65   0.73
                                       E       720   2.02   2.42   2.60  1.01         33.3   0.22   0.25   1.95
halberdier__vs__arbalester             T         2   3.65   3.65   4.15  1.22  1.02  100.0   1.68   1.75   0.23
                                       E        40   3.59   3.59   4.17  1.20         50.0   0.60   0.66   2.33
halberdier__vs__imp_elite_skirm        T        23   3.03   4.06   5.67  1.01  1.00   95.7   1.65   1.30   1.11
                                       E       660   3.02   3.40   3.08  1.01         30.3   0.30   0.29   2.81
arbalester__vs__elite_fire_lancer      T        14   0.23   2.60   8.47  0.12  0.11   64.3   1.68   0.59   0.33
                                       E       520   2.08   3.96   9.55  1.04         73.1   1.76   0.47   1.73
halberdier__vs__hand_cannoneer         T         5   3.97   4.62   6.37  1.32  1.20  100.0   2.05   1.90   0.67
                                       E       113   3.30   5.07   9.19  1.10         67.3   1.04   1.01   3.02
arbalester__vs__heavy_camel            T        19   2.53   3.15   4.55  1.27  1.26  100.0   1.19   1.70   0.26
                                       E       800   2.02   2.79   4.60  1.01         75.0   0.51   0.46   1.81
arbalester__vs__hussar                 T        58   2.34   3.58   7.72  1.23  1.22   96.6   1.35   1.76   0.48
                                       E      1440   1.92   2.37   3.83  1.01         50.0   0.20   0.21   1.97
elite_fire_lancer__vs__heavy_cav_archer T        67   2.47   3.73   8.31  1.23  1.17   85.1   1.66   1.56   0.50
                                       E       980   2.12   3.23   6.65  1.06         91.8   1.31   0.60   1.32
imp_elite_skirm__vs__elite_fire_lancer T        73   2.75   3.47   7.58  1.37  1.36   86.3   1.63   1.38   0.46
                                       E       960   2.02   2.82   8.98  1.01         43.8   1.33   0.42   1.07
imp_elite_skirm__vs__elite_steppe      T        52   2.10   3.46   7.74  1.05  1.04   67.3   1.06   0.94   1.46
                                       E       960   2.02   2.56   3.45  1.01         85.4   0.77   0.14   1.65
imp_elite_skirm__vs__heavy_camel       T        90   2.75   4.17   9.32  1.38  1.37   98.9   1.89   1.74   0.54
                                       E      1880   2.02   2.33   3.95  1.01         51.1   0.33   0.21   1.80
imp_elite_skirm__vs__hussar            T        73   2.58   3.71   7.83  1.36  1.35   97.3   1.49   1.73   0.50
                                       E      1660   1.92   2.25   2.70  1.01         44.6   0.31   0.24   1.70
imp_elite_skirm__vs__elite_elephant    T        27   3.23   4.25   7.89  1.62  1.60  100.0   2.29   1.54   0.43
                                       E       520   2.02   2.39   2.02  1.01         46.2   0.39   0.14   1.86
imp_elite_skirm__vs__paladin           T        46   2.98   3.62   6.02  1.57  1.55   97.8   1.58   1.68   0.37
                                       E      1060   1.92   2.22   2.28  1.01         58.5   0.40   0.18   1.64
elite_fire_lancer__vs__hand_cannoneer  T        19   0.12   1.64   4.35  0.06  0.06   47.4   0.72   0.45   0.47
                                       E       361   2.12   3.89   9.05  1.06         62.6   2.33   0.46   1.10
heavy_cav_archer__vs__elite_elephant   T        77   2.24   3.19   5.90  1.12  1.11   94.8   0.98   1.42   0.78
                                       E      1360   2.02   2.35   3.03  1.01         51.5   0.16   0.18   2.01
heavy_cav_archer__vs__hussar           T       127   1.93   2.95   5.68  1.01  1.00   90.6   0.76   1.36   0.84
                                       E      2920   1.92   2.12   1.95  1.01         26.7   0.09   0.11   1.92
heavy_cav_archer__vs__paladin          T       115   2.04   3.03   5.85  1.07  1.06   87.8   0.81   1.44   0.78
                                       E      2580   1.92   2.12   2.23  1.01         45.0   0.16   0.19   1.77
hand_cannoneer__vs__elite_steppe       T        60   2.14   3.44   6.76  1.07  1.06   90.0   1.06   1.22   1.16
                                       E      1313   2.02   2.40   3.38  1.01         68.2   0.33   0.26   1.81
---------------------------------------------------------------------------------------------------------------
29 melee-swing families (4 charge-attack families excluded from the headline: arbalester__vs__elite_fire_lancer, elite_fire_lancer__vs__hand_cannoneer, elite_fire_lancer__vs__heavy_cav_archer, imp_elite_skirm__vs__elite_fire_lancer)
  median-of-family-medians  T 2.58s  E 2.02s   median T/E 1.22  (min 0.93 max 1.95)
  cycles that lose contact  T 97.2%  E 54.1%     mean seconds IN REACH per cycle  T 0.66s  E 1.81s
```

**Verdict.** E12's 1.29 survives the current engine and the tapebox rig at
**1.22 median** (29 melee-swing families; 28 of 29 above 1.0, the single
exception `halberdier__vs__heavy_cav_archer` at 0.93 where the engine's
halberdier is already slower than the tape's).

The decomposition is the finding, not the ratio:

| | tape | engine |
|---|---|---|
| cycles that lose contact at all | **97.2 %** | 54.1 % |
| mean seconds IN REACH per cycle | **0.66 s** | 1.81 s |
| median interval | 2.58 s | 2.02 s = reload |

The engine's chaser sits in reach for essentially its entire reload
(`inR` 1.81 s against a 1.9–2.0 s reload) and its cycle length IS the reload
(`/rl` = 1.01 in 25 of 29 families). The tape's chaser is in reach for a
**quarter** of its cycle and spends the other three quarters out of contact,
half of that closing and half of it losing ground. Its reload finishes while
it is still out of reach, so the tape's melee unit is **contact-limited**, not
reload-limited, and swings the moment it re-touches.

That reframes the target. A correct model does not slow the chaser's reload
down; it has to make the chaser spend ~1.15 s per cycle **out of reach and
closing** and ~1.5 s **out of reach without closing**, where today it spends
0.4 s and 0.4 s.

---

## M2. The contact-loss mechanism

Two tables. 2a is the reload window that FOLLOWS every chaser hit; 2b is the
phase question and the kiters' own rhythm measured with no reference to any
hit.

```
==========================================================================================================================
TABLE 2a -- THE RELOAD WINDOW AFTER A CHASER HIT. Displacement in TILES over [hit, hit+reload]; `vRad`/`cRad` are the
victim's and the chaser's displacement PROJECTED on the attacker->victim line (positive = away from / toward the victim).
`dGap` = change in separation. `lose%` = windows in which the victim left reach, `tLose` = median seconds until it did.
`vOpen/cOpen/static` = of the windows that opened a gap, the share the VICTIM opened / the CHASER opened / neither.
==========================================================================================================================
family                                 src       n  vDisp  cDisp   vRad   cRad   dGap  lose%  tLose  vOpen%  cOpen%  stat%
--------------------------------------------------------------------------------------------------------------------------
champion__vs__heavy_cav_archer         T       312   0.97   0.75   0.80   0.60   0.20   99.7   0.07    88.5     1.6    9.8
                                       E     10440   0.71   0.43   0.27   0.27  -0.01   72.4   0.79    85.7     0.0   14.3
champion__vs__arbalester               T        29   1.19   1.03   1.09   1.00   0.29  100.0   0.07    94.1     0.0    5.9
                                       E       720   0.90   0.60   0.22   0.25  -0.02   83.3   0.60   100.0     0.0    0.0
halberdier__vs__heavy_cav_archer       T        52   1.27   0.92   0.98   0.86   0.42  100.0   0.10    89.5     0.0   10.5
                                       E       240   1.73   1.33   0.94   1.15   0.27  100.0   0.72     0.0     0.0  100.0
arbalester__vs__elite_steppe           T       242   1.18   0.85   0.94   0.72   0.18   92.1   0.08    81.8     0.7   17.5
                                       E      3360   0.04   0.06   0.00   0.06  -0.01   35.7   0.06       -       -      -
hand_cannoneer__vs__hussar             T       308   1.40   0.97   1.15   0.86   0.51  100.0   0.07    85.3     0.9   13.8
                                       E      6738   0.09   0.12   0.01   0.05   0.00   50.6   0.21    67.4    26.8    5.8
hand_cannoneer__vs__paladin            T       181   1.47   1.12   1.20   1.03   0.28  100.0   0.07    84.9     0.8   14.3
                                       E      3270   0.13   0.14   0.05   0.08  -0.01   52.8   0.08    58.9     6.8   34.2
heavy_cav_archer__vs__elite_steppe     T       653   0.91   0.62   0.72   0.47   0.12   86.8   0.12    87.6     0.6   11.8
                                       E     11160   0.69   0.27   0.21   0.23   0.00   53.8   0.64    70.0     0.0   30.0
heavy_cav_archer__vs__heavy_camel      T       248   0.91   0.56   0.68   0.46   0.25   97.2   0.07    78.3     0.7   21.1
                                       E      4440   0.69   0.34   0.38   0.28   0.00   59.5   0.72    77.8     0.0   22.2
hand_cannoneer__vs__heavy_camel        T       173   1.42   1.06   1.29   0.97   0.50   98.8   0.07    86.1     0.0   13.9
                                       E      6840   0.82   0.72   0.44   0.46   0.01   73.1   0.08    68.1     8.9   23.0
arbalester__vs__elite_elephant         T       119   1.20   0.58   0.92   0.45   0.41   95.8   0.09    79.8     5.3   14.9
                                       E      2760   0.10   0.16   0.00   0.05  -0.01   65.2   0.07    77.8     0.0   22.2
arbalester__vs__paladin                T        95   1.10   0.78   0.96   0.69   0.29   97.9   0.07    95.1     0.0    4.9
                                       E      1620   0.60   0.52   0.34   0.40   0.03   70.4   0.08   100.0     0.0    0.0
hand_cannoneer__vs__elite_elephant     T        82   1.46   0.55   1.04   0.50   0.64   97.6   0.10    77.0     1.4   21.6
                                       E      2260   0.18   0.14   0.00   0.02  -0.01   63.8   0.08    68.2     9.2   22.6
elite_steppe__vs__arbalester           T        37   1.09   0.86   0.93   0.73   0.26   86.5   0.07    76.2     0.0   23.8
                                       E       560   0.04   0.06   0.00   0.06  -0.01   35.7   0.06       -       -      -
champion__vs__hand_cannoneer           T         5   1.62   1.27   1.58   1.26   0.38  100.0   0.03   100.0     0.0    0.0
                                       E       128   0.46   0.26   0.05   0.08   0.00   57.0   0.58    69.4     5.6   25.0
champion__vs__imp_elite_skirm          T        33   1.41   0.69   1.17   0.51   0.58  100.0   0.08    85.7     0.0   14.3
                                       E       720   0.19   0.07   0.00   0.03  -0.00   38.9   1.27    33.3    11.1   55.6
halberdier__vs__arbalester             T         3   1.72   1.01   1.16   0.75   0.76  100.0   0.20    66.7     0.0   33.3
                                       E       100   1.26   0.96   0.15   0.05   0.20   80.0   0.52    50.0     0.0   50.0
halberdier__vs__imp_elite_skirm        T        25   2.05   1.04   1.77   1.01   0.71  100.0   0.08    71.4     0.0   28.6
                                       E       500   0.05   0.03   0.00   0.02  -0.01   28.0   1.05    25.0     0.0   75.0
arbalester__vs__elite_fire_lancer      T        49   1.23   1.38   0.58   1.31  -0.55  100.0   0.07     0.0     0.0  100.0
                                       E       560   0.72   1.04   0.53   0.94  -0.20   96.4   0.08    60.0     0.0   40.0
halberdier__vs__hand_cannoneer         T         9   1.86   1.72   1.82   1.65   0.10  100.0   0.05   100.0     0.0    0.0
                                       E       156   1.44   0.94   0.14   0.11   0.08   76.3   0.90    47.3    24.3   28.4
arbalester__vs__heavy_camel            T        18   1.23   0.99   1.03   0.88   0.55  100.0   0.08    73.3     0.0   26.7
                                       E       620   1.01   0.81   0.72   0.60   0.00   83.9   0.08    75.0     0.0   25.0
arbalester__vs__hussar                 T        57   1.16   0.85   1.03   0.64   0.44  100.0   0.07    95.0     0.0    5.0
                                       E      1040   0.62   0.36   0.25   0.22   0.02   61.5   0.64    61.5     7.7   30.8
elite_fire_lancer__vs__heavy_cav_archer T        98   0.91   1.29   0.18   1.22  -0.83  100.0   0.07    73.9     0.0   26.1
                                       E       820   0.92   0.94   0.60   0.86  -0.00   92.7   0.09    50.0     0.0   50.0
imp_elite_skirm__vs__elite_fire_lancer T        72   1.25   1.15   0.82   1.04   0.06  100.0   0.07    77.8     2.8   19.4
                                       E      1080   0.16   1.42   0.02   0.46  -0.02   68.5   0.07    54.5     9.1   36.4
imp_elite_skirm__vs__elite_steppe      T        27   1.66   0.83   0.94   0.66   0.35   96.3   0.08    90.0     5.0    5.0
                                       E       240   0.71   0.28   0.17   0.27   0.00   50.0   0.97   100.0     0.0    0.0
imp_elite_skirm__vs__heavy_camel       T        74   1.55   0.88   1.12   0.74   0.68  100.0   0.08    78.8     0.0   21.2
                                       E      1400   0.20   0.16   0.00   0.02  -0.00   47.1   0.08    63.6     0.0   36.4
imp_elite_skirm__vs__hussar            T        65   1.40   0.71   1.08   0.59   0.71  100.0   0.07    82.7     0.0   17.3
                                       E      1240   0.33   0.19   0.02   0.05   0.00   41.9   0.70    40.0    13.3   46.7
imp_elite_skirm__vs__elite_elephant    T        17   1.57   1.03   1.17   1.01   0.65  100.0   0.08    86.7     0.0   13.3
                                       E       620   0.10   0.15   0.00   0.01   0.00   58.1   0.07    71.4    28.6    0.0
imp_elite_skirm__vs__paladin           T        27   1.39   1.06   1.16   0.86   0.51  100.0   0.07    77.3     0.0   22.7
                                       E       580   0.01   0.02   0.00   0.02  -0.01   34.5   0.07     0.0     0.0  100.0
elite_fire_lancer__vs__hand_cannoneer  T        49   1.30   1.36   0.71   1.24  -0.44  100.0   0.06    57.1     0.0   42.9
                                       E       496   0.99   2.26   0.47   2.17  -0.62   93.3   0.07    64.8     9.9   25.4
heavy_cav_archer__vs__elite_elephant   T        91   0.98   0.53   0.75   0.39   0.34   97.8   0.12    89.4     1.5    9.1
                                       E      2940   0.58   0.17   0.10   0.05   0.03   79.6   0.10    67.8    11.9   20.3
heavy_cav_archer__vs__hussar           T       133   0.84   0.53   0.64   0.28   0.27   94.7   0.08    90.8     1.1    8.0
                                       E      2760   0.10   0.05   0.02   0.02  -0.00   29.7   0.42    75.0     0.0   25.0
heavy_cav_archer__vs__paladin          T       106   0.85   0.54   0.66   0.31   0.26   95.3   0.08    82.5     4.8   12.7
                                       E      2160   0.11   0.09   0.02   0.03   0.00   48.1   0.73    84.6     7.7    7.7
hand_cannoneer__vs__elite_steppe       T        38   1.29   0.89   1.01   0.88   0.31   97.4   0.10    96.2     0.0    3.8
                                       E       348   0.99   0.43   0.16   0.26  -0.01   56.3   0.05    66.7     0.0   33.3
```

```
========================================================================================================
TABLE 2b -- THE PHASE RACE. `hitStop%` = chaser hits landed on a victim that was NOT moving; `onset` = median
seconds from such a hit to the victim's next step. Then the KITERS' OWN rhythm, measured with no reference to
any hit: stop-run and move-run durations, stopped duty cycle, stops per kiter-minute.
========================================================================================================
`cosAtt`/`cosCen` = cosine of the just-hit victim's displacement with 'away from the unit that hit it' and with
'away from the chasing side's centroid' -- WHICH WAY the kiter runs, not how often.
family                                 src   hitStop%  onset  stopMed  stopP90  moveMed  stopFrac  stops/min  cosAtt  cosCen
----------------------------------------------------------------------------------------------------------------------------
champion__vs__heavy_cav_archer         T         42.0   0.72     1.26     1.90     0.74     0.654       28.6    0.93    0.89
                                       E         74.1   0.67     1.10     1.30     0.70     0.655       35.0    0.61    0.57
champion__vs__arbalester               T         17.2   0.43     0.62     0.66     1.38     0.338       31.7    0.93    0.88
                                       E          0.0      -     0.60     0.78     1.10     0.407       37.4    0.27    0.12
halberdier__vs__heavy_cav_archer       T         53.8   0.73     1.26     1.93     0.74     0.654       28.5    0.89    0.42
                                       E        100.0   0.67     1.10     1.28     0.70     0.637       34.7    0.54    0.66
arbalester__vs__elite_steppe           T         26.0   0.23     0.62     0.71     1.37     0.341       31.4    0.85    0.71
                                       E         60.7   0.23     0.60     0.80     1.10     0.495       34.2    0.84    0.78
hand_cannoneer__vs__hussar             T          9.7   0.39     0.62     0.72     3.36     0.179       16.4    0.91    0.88
                                       E         56.6   0.43     0.60     1.90     0.40     0.462       22.3    0.67    0.85
hand_cannoneer__vs__paladin            T          9.9   0.27     0.62     0.74     3.35     0.185       17.0    0.90    0.84
                                       E         47.9   0.40     0.60     1.40     0.70     0.379       22.9    0.89    0.91
heavy_cav_archer__vs__elite_steppe     T         63.6   0.69     1.27     1.97     0.74     0.682       27.0    0.86    0.74
                                       E         64.5   0.70     1.18     1.30     0.66     0.688       33.1    0.70    0.77
heavy_cav_archer__vs__heavy_camel      T         51.6   0.83     1.26     1.97     0.74     0.670       27.6    0.85    0.39
                                       E         75.7   0.71     1.18     1.30     0.70     0.693       32.3    0.78    0.81
hand_cannoneer__vs__heavy_camel        T          5.8   0.32     0.62     0.85     3.35     0.195       18.1    0.92    0.72
                                       E         26.5   0.38     0.60     1.10     0.32     0.371       26.8    0.77    0.66
arbalester__vs__elite_elephant         T         15.1   0.17     0.62     0.65     1.38     0.319       30.9    0.79    0.78
                                       E         58.7   0.37     0.60     1.00     0.80     0.518       37.5    0.45    0.26
arbalester__vs__paladin                T         17.9   0.26     0.62     0.65     1.37     0.325       31.1    0.93    0.83
                                       E         40.7   0.45     0.60     0.90     0.92     0.467       37.1    0.77    0.94
hand_cannoneer__vs__elite_elephant     T          7.3   0.50     0.63     0.65     3.36     0.178       16.5    0.80    0.78
                                       E         38.0   0.35     0.60     1.00     0.30     0.355       30.0    0.02    0.64
elite_steppe__vs__arbalester           T         18.9   0.17     0.63     0.68     1.36     0.345       31.1    0.86    0.84
                                       E         60.7   0.23     0.60     0.80     1.10     0.495       34.2    0.84    0.78
champion__vs__hand_cannoneer           T          0.0      -     0.62     1.08     3.35     0.196       17.7    0.96    0.86
                                       E         26.6   0.40     0.60     0.90     0.40     0.321       28.0    0.32    0.12
champion__vs__imp_elite_skirm          T          6.1   1.15     0.61     1.14     2.72     0.190       16.6    0.88    0.73
                                       E         52.8   0.40     0.60     1.50     0.70     0.385       25.1    0.17    0.26
halberdier__vs__arbalester             T          0.0      -     0.63     0.66     1.38     0.336       31.6    0.69    0.38
                                       E         20.0   0.25     0.60     0.78     1.10     0.448       41.0    0.12   -0.59
halberdier__vs__imp_elite_skirm        T          4.0   0.38     0.62     0.77     2.71     0.189       17.4    0.85    0.69
                                       E         60.0   1.05     0.60     2.90     0.30     0.528       21.1    0.00   -0.95
arbalester__vs__elite_fire_lancer      T         18.4   0.50     0.62     0.66     1.39     0.339       31.7    0.41    0.51
                                       E         25.0   0.35     0.60     0.78     1.00     0.409       38.2    0.59    0.87
halberdier__vs__hand_cannoneer         T          0.0      -     0.63     0.73     3.36     0.182       17.0    0.92    0.60
                                       E         23.7   0.30     0.60     1.00     0.30     0.345       29.0    0.20   -0.12
arbalester__vs__heavy_camel            T         16.7   0.32     0.64     0.66     1.36     0.336       31.1    0.89    0.64
                                       E         32.3   0.17     0.60     0.90     0.70     0.497       40.0    0.80    0.71
arbalester__vs__hussar                 T         28.1   0.26     0.62     0.65     1.38     0.329       31.2    0.92    0.85
                                       E         48.1   0.35     0.60     0.78     1.10     0.451       36.3    0.69    0.79
elite_fire_lancer__vs__heavy_cav_archer T         63.3   0.70     1.26     1.71     0.74     0.651       29.8    0.34    0.22
                                       E         70.7   0.33     1.10     1.28     0.70     0.645       34.9    0.68    0.52
imp_elite_skirm__vs__elite_fire_lancer T          5.6   0.74     0.62     1.06     2.71     0.185       16.0    0.70    0.67
                                       E         50.0   0.69     0.60     2.31     1.10     0.395       21.5    0.77    0.83
imp_elite_skirm__vs__elite_steppe      T          7.4   0.21     0.62     1.06     2.71     0.197       17.6    0.80    0.33
                                       E         58.3   0.44     0.50     1.20     0.90     0.360       24.5    0.76    0.96
imp_elite_skirm__vs__heavy_camel       T          8.1   1.07     0.62     1.07     2.72     0.183       16.3    0.88    0.84
                                       E         50.0   0.77     0.59     1.70     0.30     0.469       28.2    0.51    0.67
imp_elite_skirm__vs__hussar            T          3.1   0.20     0.62     0.72     2.71     0.170       16.0    0.88    0.84
                                       E         41.9   0.23     0.50     1.10     0.30     0.389       29.1    0.45    0.98
imp_elite_skirm__vs__elite_elephant    T          0.0      -     0.62     0.64     2.72     0.177       16.7    0.82    0.85
                                       E         64.5   0.37     0.60     1.80     1.30     0.406       20.0    0.54    0.25
imp_elite_skirm__vs__paladin           T          3.7   0.40     0.61     0.91     2.71     0.173       16.4    0.87    0.79
                                       E         55.2   0.88     0.50     1.50     0.30     0.473       31.2    0.77    0.98
elite_fire_lancer__vs__hand_cannoneer  T          8.2   0.37     0.61     1.08     3.38     0.187       17.4    0.56    0.51
                                       E         29.8   0.27     0.60     0.82     0.40     0.298       26.5    0.54    0.53
heavy_cav_archer__vs__elite_elephant   T         63.7   0.51     1.27     1.90     0.74     0.645       28.6    0.85    0.89
                                       E         65.3   0.69     1.10     1.28     0.60     0.656       35.0    0.28    0.65
heavy_cav_archer__vs__hussar           T         57.1   0.78     1.27     2.00     0.73     0.680       27.0    0.88    0.91
                                       E         64.5   0.67     1.20     1.60     0.20     0.739       36.5    0.47    0.45
heavy_cav_archer__vs__paladin          T         54.7   0.96     1.27     1.95     0.74     0.659       27.1    0.90    0.73
                                       E         74.1   0.71     1.10     1.30     0.60     0.719       31.5    0.77    0.78
hand_cannoneer__vs__elite_steppe       T          5.3   0.34     0.62     1.15     3.33     0.185       16.9    0.84    0.78
                                       E         40.8   0.18     0.60     0.80     0.80     0.324       23.8    0.74    0.77
```

**2a — who opens the gap.** Overwhelmingly the victim: over the 29 melee-swing
families **the VICTIM opened the gap in 66.7–100 % of the tape's gap-opening
windows** (median 85.7) and **the chaser opened it in 0.0–5.3 %**. Collision
displacement (`static`, neither party moved much yet the gap grew) is
0–33 %, and the two families at the top of that range are the two- and
five-recording singles. So contact loss is **not** chaser overshoot and **not**
a body shove — the kiter runs.

The engine's kiter runs too, in a similar share of windows. What differs is
how far and how soon:

| pooled median over 29 families | tape | engine |
|---|---|---|
| windows that lose reach | **100.0 %** | 57.0 % |
| seconds until reach is lost | **0.08 s** | 0.42 s |
| victim's RADIAL displacement over one reload | **1.03 tiles** | 0.05 tiles |
| chaser's radial displacement over one reload | 0.73 tiles | 0.05 tiles |
| net change in separation | **+0.38 tiles** | 0.00 tiles |

The tape's kiter is gone **0.08 s** after being hit — one sample. The engine's
lingers for **0.42 s**, and over a full reload window it nets **0.05 tiles** of
radial separation against the tape's **1.03**. The engine's chaser is not
chasing because there is nothing to chase.

**2b — the phase question, answered and refuted.** "Does the tape chaser land
its hit predominantly at the kiter's STOP moments?" **No — the opposite.**
Pooled, the tape lands **9.9 %** of its blows on a stopped victim while the
kiters are stopped **31.9 %** of the time; the engine lands **55.2 %** on a
stopped victim at a **46.7 %** stopped duty cycle. The tape's chaser
systematically catches its victim *mid-move* (it connects as the kiter passes);
the engine's systematically catches it *parked*.

So the cadence loss is **not** emergent from a stop-shoot-flee phase race. Two
independent kiter-side quantities are wrong, and they separate cleanly by
kiter class:

| kiter | stopped duty T → E | median move-run T → E | cos(flee, away-from-toucher) T → E |
|---|---|---|---|
| heavy_cav_archer (1.54 t/s) | 0.659 → **0.688** | 0.74 → **0.66 s** | 0.88 → **0.61** |
| arbalester (0.96 t/s) | 0.336 → 0.481 | 1.37 → 1.10 s | 0.87 → 0.73 |
| hand_cannoneer (0.96 t/s) | 0.185 → **0.355** | 3.35 → **0.40 s** | 0.91 → 0.67 |
| imp_elite_skirm (0.96 t/s) | 0.183 → **0.406** | 2.71 → **0.30 s** | 0.87 → 0.51 |

1. **Flee DIRECTION is wrong for every kiter class.** `cosAtt` — the cosine of
   the just-hit victim's displacement with "straight away from the unit that
   just hit it" — is **0.69–0.96 on tape over the 29 melee-swing families**
   (median 0.88; 28 of 29 at or above 0.79, the exception being the
   two-recording `halberdier__vs__arbalester` at 0.69) and **0.00–0.89 in the
   engine (median 0.61)**. The tape's kiter breaks contact
   with its *toucher*. The engine's runs somewhere else; `cosCen` (away from
   the chasing side's centroid) is not systematically better either
   (0.78 → 0.67), so it is not simply "the engine flees the centroid instead" —
   the engine's flee vector is less aligned with BOTH bases.
2. **Flee RHYTHM is right for the fast kiter and wrong for the slow ones.**
   The HCA's stopped duty cycle and move-run length are already within a few
   percent of the tape's, yet its cadence gift to the chaser is one of the
   largest in the corpus. The three 0.96 t/s shooters are the opposite: the
   engine parks them ~2x too much and moves them in 0.3–0.4 s dribbles where
   the tape runs 2.7–3.4 s at a stretch.

**Spec-grade statement.** The unmodelled quantity is the kiter's **contact
break**, not the chaser's pursuit. After taking a melee hit, a tape kiter (a)
starts moving within ~0.1 s, (b) moves along the vector away from the unit that
hit it (cos ≈ 0.88), and (c) converts that into ~1.0 tile of radial separation
inside the chaser's reload — enough to leave a 0.6-tile reach immediately and
force a re-close. The engine's kiter does none of the three (0.42 s, cos 0.61,
0.05 tiles). Separately, and only for kiters slower than their chaser, the
engine's stop-to-fire duty cycle is ~2x too high and its runs are ~8x too
short.

---

## M3. Where the engine's extra chaser hits come from

Every landed hit classified by the victim's and the chaser's movement state at
the instant it landed, as a RATE per chaser-alive-second so the excess is
attributable rather than merely redistributed. `cStep`/`vStep` are the actual
displacement of each party across the same window the moving/stopped flag is
decided over — a unit being shoved by `resolveCollisions` while it stands and
swings registers as "moving" under a 0.02-tile bar, and these two medians
separate walking from body jitter.

```
======================================================================================================================
TABLE 3 -- WHERE THE ENGINE'S EXTRA CHASER HITS COME FROM. `hits/cs` = chaser landed hits per chaser-ALIVE-second
(a dead chaser stops paying cadence). The four cells are every landed hit by (victim moving?, chaser moving?) at the
instant it landed, as a RATE per chaser-second, so the excess is attributable rather than merely redistributed.
`dHit` = attacker-victim distance at the landed hit; `reach` = the engine's own inRange() for the pair.
======================================================================================================================
family                                 src     hits    armyS  hits/cs   E/T  V.mov  V.stop  both.mov  cStep  vStep   dHit    p90  reach
---------------------------------------------------------------------------------------------------------------------------------------
champion__vs__heavy_cav_archer         T        453     5865   0.0772       0.0411  0.0361    0.0000  0.000  0.129   0.91   1.52   0.62
                                       E      14580   107874   0.1352  1.75 0.0334  0.1018    0.0234  0.058  0.000   0.61   0.62       
champion__vs__arbalester               T         52     2388   0.0218       0.0155  0.0063    0.0000  0.000  0.255   0.88   1.30   0.57
                                       E       1200    44556   0.0269  1.24 0.0189  0.0081    0.0189  0.160  0.080   0.56   0.57       
halberdier__vs__heavy_cav_archer       T        162     2955   0.0548       0.0230  0.0318    0.0000  0.000  0.000   0.69   1.26   0.62
                                       E       3240    38942   0.0832  1.52 0.0154  0.0678    0.0154  0.235  0.000   0.61   0.62       
arbalester__vs__elite_steppe           T        504     2989   0.1686       0.1194  0.0492    0.0000  0.000  0.209   1.63   1.94   1.62
                                       E      10080    43830   0.2300  1.36 0.1150  0.1150    0.0548  0.055  0.020   1.60   1.76       
hand_cannoneer__vs__hussar             T        483     5423   0.0891       0.0769  0.0122    0.0000  0.000  0.268   0.93   1.15   0.62
                                       E      10080    85605   0.1178  1.32 0.0519  0.0659    0.0278  0.036  0.016   0.59   0.68       
hand_cannoneer__vs__paladin            T        372     3854   0.0965       0.0841  0.0125    0.0000  0.000  0.248   1.03   1.26   0.62
                                       E       7560    49096   0.1540  1.60 0.0772  0.0767    0.0306  0.046  0.023   0.60   0.75       
heavy_cav_archer__vs__elite_steppe     T       1008     5373   0.1876       0.0646  0.1230    0.0000  0.000  0.000   1.62   1.99   1.67
                                       E      20160    92214   0.2186  1.17 0.0716  0.1470    0.0247  0.023  0.000   1.65   1.77       
heavy_cav_archer__vs__heavy_camel      T        504     3959   0.1273       0.0538  0.0735    0.0000  0.000  0.000   0.77   1.37   0.67
                                       E      10080    65696   0.1534  1.21 0.0438  0.1096    0.0237  0.008  0.000   0.65   0.75       
hand_cannoneer__vs__heavy_camel        T        237     2458   0.0964       0.0895  0.0069    0.0000  0.000  0.287   0.93   1.16   0.62
                                       E      10542    58493   0.1802  1.87 0.1307  0.0495    0.0465  0.036  0.083   0.61   0.82       
arbalester__vs__elite_elephant         T        206     2695   0.0764       0.0605  0.0160    0.0000  0.000  0.240   0.69   1.03   0.62
                                       E       4800    23544   0.2039  2.67 0.0841  0.1198    0.0153  0.033  0.013   0.62   0.77       
arbalester__vs__paladin                T        189     1864   0.1014       0.0864  0.0150    0.0000  0.000  0.240   0.91   1.27   0.62
                                       E       3780    22331   0.1693  1.67 0.0967  0.0725    0.0322  0.045  0.087   0.61   0.71       
hand_cannoneer__vs__elite_elephant     T        140     2033   0.0689       0.0634  0.0054    0.0000  0.000  0.215   0.65   1.03   0.62
                                       E       3714    21854   0.1699  2.47 0.1003  0.0696    0.0249  0.034  0.030   0.60   0.80       
elite_steppe__vs__arbalester           T         68      408   0.1669       0.1251  0.0417    0.0000  0.000  0.223   1.74   1.95   1.62
                                       E       1680     7305   0.2300  1.38 0.1150  0.1150    0.0548  0.055  0.020   1.60   1.76       
champion__vs__hand_cannoneer           T          7      384   0.0182       0.0156  0.0026    0.0000  0.000  0.243   0.93   1.22   0.57
                                       E        304     6004   0.0506  2.78 0.0376  0.0130    0.0303  0.141  0.073   0.55   0.57       
champion__vs__imp_elite_skirm          T         63     1240   0.0508       0.0468  0.0040    0.0000  0.000  0.240   0.97   1.26   0.57
                                       E       1260    19858   0.0635  1.25 0.0272  0.0363    0.0232  0.130  0.024   0.56   0.57       
halberdier__vs__arbalester             T          6      353   0.0170       0.0170  0.0000    0.0000  0.000  0.291   0.81   1.14   0.57
                                       E        160     4534   0.0353  2.08 0.0221  0.0132    0.0176  0.222  0.129   0.56   0.57       
halberdier__vs__imp_elite_skirm        T         42      707   0.0594       0.0538  0.0057    0.0000  0.000  0.240   0.86   1.14   0.57
                                       E        920    12616   0.0729  1.23 0.0238  0.0491    0.0159  0.034  0.014   0.55   0.57       
arbalester__vs__elite_fire_lancer      T         57      302   0.1885       0.1554  0.0331    0.0033  0.000  0.240   5.06   6.14   0.57
                                       E       1280     5944   0.2153  1.14 0.1548  0.0606    0.1144  0.338  0.160   3.37   3.94       
halberdier__vs__hand_cannoneer         T         16      444   0.0361       0.0361  0.0000    0.0000  0.000  0.283   0.79   1.06   0.57
                                       E        302     5820   0.0519  1.44 0.0409  0.0110    0.0387  0.175  0.108   0.56   0.57       
arbalester__vs__heavy_camel            T         34      309   0.1100       0.0906  0.0194    0.0000  0.000  0.235   0.88   1.19   0.62
                                       E       1120     5384   0.2080  1.89 0.1374  0.0706    0.0520  0.048  0.121   0.66   0.86       
arbalester__vs__hussar                 T         90      961   0.0937       0.0666  0.0271    0.0000  0.000  0.241   0.85   1.08   0.62
                                       E       1800    14165   0.1271  1.36 0.0649  0.0621    0.0367  0.060  0.051   0.59   0.67       
elite_fire_lancer__vs__heavy_cav_archer T        147      705   0.2086       0.0780  0.1305    0.0071  0.000  0.000   2.08   5.69   0.62
                                       E       2200     9138   0.2408  1.15 0.0832  0.1576    0.0547  0.112  0.000   0.72   3.90       
imp_elite_skirm__vs__elite_fire_lancer T        131      706   0.1856       0.1743  0.0113    0.0014  0.000  0.258   2.06   5.29   0.57
                                       E       2320    17534   0.1323  0.71 0.0605  0.0719    0.0548  0.325  0.043   1.52   4.10       
imp_elite_skirm__vs__elite_steppe      T         63      365   0.1724       0.1533  0.0192    0.0000  0.000  0.280   1.58   1.93   1.62
                                       E       1260     6390   0.1972  1.14 0.0876  0.1095    0.0376  0.042  0.022   1.60   1.77       
imp_elite_skirm__vs__heavy_camel       T        105      647   0.1622       0.1514  0.0108    0.0000  0.000  0.268   0.92   1.15   0.62
                                       E       2100     9364   0.2243  1.38 0.1068  0.1175    0.0406  0.037  0.034   0.60   0.85       
imp_elite_skirm__vs__hussar            T        105     1286   0.0817       0.0786  0.0031    0.0000  0.000  0.263   0.89   1.16   0.62
                                       E       2100    15840   0.1326  1.62 0.0732  0.0593    0.0354  0.050  0.036   0.60   0.69       
imp_elite_skirm__vs__elite_elephant    T         44      707   0.0622       0.0622  0.0000    0.0000  0.000  0.250   0.90   1.07   0.62
                                       E       1180    17518   0.0674  1.08 0.0194  0.0480    0.0023  0.049  0.013   0.61   0.77       
imp_elite_skirm__vs__paladin           T         63      499   0.1262       0.1182  0.0080    0.0000  0.000  0.249   1.06   1.25   0.62
                                       E       1260     6160   0.2045  1.62 0.0649  0.1396    0.0195  0.033  0.010   0.59   0.74       
elite_fire_lancer__vs__hand_cannoneer  T         68      334   0.2038       0.1829  0.0210    0.0000  0.000  0.286   4.94   6.06   0.57
                                       E       1141     5414   0.2108  1.03 0.1542  0.0565    0.1202  0.346  0.146   3.53   3.99       
heavy_cav_archer__vs__elite_elephant   T        130     1262   0.1030       0.0444  0.0586    0.0000  0.000  0.000   0.71   1.27   0.67
                                       E       3660    15080   0.2427  2.36 0.0769  0.1658    0.0292  0.016  0.000   0.65   0.84       
heavy_cav_archer__vs__hussar           T        168     1241   0.1354       0.0580  0.0774    0.0000  0.000  0.013   0.76   1.39   0.67
                                       E       3360    19961   0.1683  1.24 0.0621  0.1062    0.0210  0.005  0.009   0.62   0.67       
heavy_cav_archer__vs__paladin          T        147     1125   0.1307       0.0524  0.0782    0.0000  0.000  0.000   0.82   1.51   0.67
                                       E       2940    18348   0.1602  1.23 0.0458  0.1145    0.0120  0.015  0.004   0.63   0.68       
hand_cannoneer__vs__elite_steppe       T         84      672   0.1250       0.1116  0.0134    0.0000  0.000  0.246   1.75   2.11   1.62
                                       E       1680     9037   0.1859  1.49 0.1097  0.0762    0.0433  0.046  0.107   1.61   1.75
```

**Verdict.** The engine chaser out-hits the tape's in **29 of 29** melee-swing
families, median **1.44x**, range 1.08x–2.78x. Three routes, all measured:

1. **Hitting a parked victim.** The `V.stop` cell is **52.4 %** of the engine's
   hits against **14.3 %** of the tape's (median of the per-family shares over
   the 29 melee-swing families). Table 2b's independent count of the same
   thing, restricted to hits with a full reload window after them, gives
   **55.2 % vs 9.9 %**.
   In `champion__vs__heavy_cav_archer` the engine's stopped-victim hit rate is
   0.1018/chaser-s against the tape's 0.0361 — a **2.8x** excess in that cell
   alone, which is the whole 1.75x family excess and more.
2. **Swinging while walking.** `both.mov` — a hit landed while BOTH parties
   were moving — is **0.0000/chaser-s on tape in every single family**
   (the tape's `cStep` at the hit is **0.000 tiles**, i.e. the recorded melee
   unit is *always* stationary when its blow lands). The engine takes
   **19.8 %** of its hits this way, with a median `cStep` of 0.046 tiles. This
   is not collision jitter: 0.046 tiles per 0.3 s is a walking unit, and in the
   champion families it reaches 0.13–0.24 tiles.
3. **Reaching farther — the tape does, not the engine.** The engine's hits land
   at **0.99x its own reach** (`dHit` ≈ `reach` to two digits, in every
   family) — it applies damage exactly at the inRange() boundary and never past
   it. The **tape's** land at **1.43x reach** (median 0.91 tiles against a
   0.62-tile reach for a champion, p90 1.52), including for `champion` and
   `halberdier`, whose `attack_delay` is **0** in the dat. So the recorded
   melee swing commits at contact and resolves ~0.2 s later, after the victim
   has walked off; the engine's requires the victim to be in reach at the
   moment of application. This route makes the tape's *effective* reach LARGER,
   so it does not explain the engine's excess — it means the engine's excess is
   even larger than the raw hit-rate ratio suggests once you account for the
   tape's more generous application rule.

Route 3 is worth flagging separately: it says the two engines disagree about
*when a swing is resolved*, not only about *where the units are*. The engine
never lands a hit past its reach; the tape does so on roughly half of them.

---

## M4. Blacklist and retarget

Two halves. 4a is decided from the damage stream alone so tape and engine are
the same statistic; 4b is the engine's own ledger, which the tape has no field
for.

```
========================================================================================================================
TABLE 4a -- DOES THE CHASER STICK? Both columns from the DAMAGE stream alone, so tape and engine are the same statistic.
`switch%` = consecutive landed hits by one chaser that changed victim. `abandon%` = of those, the ones where the old
victim was still ALIVE and still within 3.0 tiles. `run` = median consecutive hits on one victim.
========================================================================================================================
family                                 src     hits   pairs  switch%  abandon%  runMed  distinct
------------------------------------------------------------------------------------------------
champion__vs__heavy_cav_archer         T        453     319     41.1      18.8     1.0       2.0
                                       E      14580   10800     36.7      18.3     2.0       2.0
champion__vs__arbalester               T         52       9     33.3      33.3     1.0       1.0
                                       E       1200     120      0.0       0.0     1.0       1.0
halberdier__vs__heavy_cav_archer       T        162      89     64.0      11.2     1.0       2.0
                                       E       3240    1320    100.0       9.1     1.0       2.0
arbalester__vs__elite_steppe           T        504     386     52.1       3.1     1.0       3.0
                                       E      10080    8280     69.6       0.0     1.0       4.0
hand_cannoneer__vs__hussar             T        483     307     61.9      29.0     1.0       3.0
                                       E      10080    8340     30.6       0.1     2.0       2.0
hand_cannoneer__vs__paladin            T        372     245     81.6      25.7     1.0       4.0
                                       E       7560    6198     54.4       0.0     1.0       3.0
heavy_cav_archer__vs__elite_steppe     T       1008     842     38.2       4.0     2.0       3.0
                                       E      20160   17640     47.6       4.8     2.0       4.0
heavy_cav_archer__vs__heavy_camel      T        504     365     54.0       8.8     1.0       3.0
                                       E      10080    7920     59.1       6.1     1.0       2.0
hand_cannoneer__vs__heavy_camel        T        237     138     65.2      54.3     1.0       2.0
                                       E      10542    8184     28.6       0.4     2.0       2.0
arbalester__vs__elite_elephant         T        206     154     83.8      48.7     1.0       5.0
                                       E       4800    4320     79.2      45.8     1.0       5.0
arbalester__vs__paladin                T        189     126     65.9      12.7     1.0       4.0
                                       E       3780    3120     57.7       0.0     1.0       3.0
hand_cannoneer__vs__elite_elephant     T        140     101     89.1      55.4     1.0       5.0
                                       E       3714    3234     86.8      58.9     1.0       6.0
elite_steppe__vs__arbalester           T         68      53     45.3       5.7     1.0       2.0
                                       E       1680    1380     69.6       0.0     1.0       4.0
champion__vs__hand_cannoneer           T          7       3     33.3      33.3     1.0       1.0
                                       E        304     150     58.0      16.0     1.0       1.0
champion__vs__imp_elite_skirm          T         63      42     76.2      26.2     1.0       4.0
                                       E       1260     720     41.7      16.7     1.0       3.0
halberdier__vs__arbalester             T          6       2     50.0      50.0     1.0       1.0
                                       E        160      40     50.0      50.0     1.0       1.0
halberdier__vs__imp_elite_skirm        T         42      23     78.3      47.8     1.0       2.0
                                       E        920     660     39.4       6.1     2.0       1.0
arbalester__vs__elite_fire_lancer      T         57      36     52.8       5.6     1.0       2.0
                                       E       1280     920     60.9      17.4     1.0       3.0
halberdier__vs__hand_cannoneer         T         16       5     40.0      40.0     1.0       1.0
                                       E        302     113     59.3      38.9     1.0       1.0
arbalester__vs__heavy_camel            T         34      19     63.2      36.8     1.0       2.0
                                       E       1120     800     47.5       2.5     1.0       3.0
arbalester__vs__hussar                 T         90      58     63.8      25.9     1.0       3.0
                                       E       1800    1440     40.3       0.0     2.0       3.0
elite_fire_lancer__vs__heavy_cav_archer T        147     113     54.0      16.8     1.0       4.0
                                       E       2200    1640     45.1       6.1     1.0       3.0
imp_elite_skirm__vs__elite_fire_lancer T        131     104     69.2      22.1     1.0       9.0
                                       E       2320    1680     53.6      25.0     1.0       6.0
imp_elite_skirm__vs__elite_steppe      T         63      52     63.5       3.8     1.0       5.0
                                       E       1260     960     81.2       0.0     1.0       5.0
imp_elite_skirm__vs__heavy_camel       T        105      90     80.0      45.6     1.0      10.5
                                       E       2100    1880     31.9       1.1     2.0       4.0
imp_elite_skirm__vs__hussar            T        105      73     68.5      28.8     1.0       5.0
                                       E       2100    1660     41.0       0.0     2.0       3.0
imp_elite_skirm__vs__elite_elephant    T         44      29     93.1      31.0     1.0       5.0
                                       E       1180     880     75.0      43.2     1.0       5.0
imp_elite_skirm__vs__paladin           T         63      46     89.1      30.4     1.0       7.0
                                       E       1260    1060     52.8       0.0     1.0       6.0
elite_fire_lancer__vs__hand_cannoneer  T         68      42     66.7      16.7     1.0       2.0
                                       E       1141     760     59.7       7.6     1.0       2.0
heavy_cav_archer__vs__elite_elephant   T        130     104     65.4      44.2     1.0       6.5
                                       E       3660    3340     92.2      78.4     1.0       6.0
heavy_cav_archer__vs__hussar           T        168     127     32.3      17.3     2.0       3.0
                                       E       3360    2920     17.8       4.8     3.0       2.0
heavy_cav_archer__vs__paladin          T        147     115     38.3      13.0     2.0       6.0
                                       E       2940    2580     33.3       7.8     2.0       3.0
hand_cannoneer__vs__elite_steppe       T         84      60     45.0       1.7     1.0       2.0
                                       E       1680    1313     80.0       0.0     1.0       4.0
```

```
====================================================================================================================
TABLE 4b -- THE ENGINE'S OWN PURSUIT-BAR LEDGER (probe-only; the tape has no target field). Rates per CHASER-MINUTE.
A melee unit chasing a RANGED target can never be lock-protected (meleeTargetLock returns false when target.isRanged()),
so every stuck-bar trip blacklists. `null%` = share of chaser-time with no target at all; `gap` = median seconds to
re-acquire; `dAband` = median distance to the victim at the moment it was blacklisted; `span` = median seconds held.
====================================================================================================================
family                                  blk/min  stuck/min  lockHeld  clr/min  bump/min  null%    gap  dAband   span
--------------------------------------------------------------------------------------------------------------------
champion__vs__heavy_cav_archer             26.8       26.8         0      2.1       0.0    0.7   0.02    1.43   1.33
champion__vs__arbalester                   37.5       37.5         0      0.8       0.0    1.0   0.02    1.71   1.28
halberdier__vs__heavy_cav_archer           16.6       16.6         0      8.3       0.0    0.5   0.02    1.40   1.52
arbalester__vs__elite_steppe                0.3        0.3         0      0.3       0.0    0.0   0.02    2.41   2.55
hand_cannoneer__vs__hussar                  0.5        0.5         0      0.3       0.0    0.0   0.02    1.20   5.75
hand_cannoneer__vs__paladin                 0.3        0.3         0      0.2       0.0    0.0   0.02    1.19   3.27
heavy_cav_archer__vs__elite_steppe          4.1        4.1         0      3.2       0.0    0.1   0.02    2.27   4.03
heavy_cav_archer__vs__heavy_camel           6.1        6.1         0      4.6       0.0    0.2   0.02    1.26   3.13
hand_cannoneer__vs__heavy_camel             0.5        0.5         0      0.2       0.0    0.0   0.02    1.02   7.01
arbalester__vs__elite_elephant             47.4       47.9         0      8.7       0.0    1.3   0.02    1.67   0.82
arbalester__vs__paladin                     1.3        1.3         0      1.1       0.0    0.1   0.02    1.04   3.10
hand_cannoneer__vs__elite_elephant         45.5       45.6         0      5.4       0.0    1.3   0.02    1.77   0.83
elite_steppe__vs__arbalester                0.3        0.3         0      0.3       0.0    0.0   0.02    2.41   2.55
champion__vs__hand_cannoneer               32.5       32.5         0      1.2       0.0    0.9   0.02    2.71   1.06
champion__vs__imp_elite_skirm              27.4       27.5         0      3.1       0.0    0.8   0.02    3.64   1.18
halberdier__vs__arbalester                 26.3       26.3         0      0.0       0.0    0.7   0.02    3.37   1.60
halberdier__vs__imp_elite_skirm            18.3       18.3         0      0.0       0.0    0.5   0.02    4.00   1.37
arbalester__vs__elite_fire_lancer          24.1       24.1         0      1.8       0.0    0.7   0.02    1.44   1.48
halberdier__vs__hand_cannoneer             33.4       33.4         0      1.7       0.0    0.9   0.02    3.05   1.03
arbalester__vs__heavy_camel                 0.9        0.9         0      0.4       0.0    0.0   0.02    0.96   6.07
arbalester__vs__hussar                      0.8        0.8         0      0.6       0.0    0.1   0.02    1.43   4.23
elite_fire_lancer__vs__heavy_cav_archer     15.3       15.3         0      9.4       0.0    0.4   0.02    1.14   1.78
imp_elite_skirm__vs__elite_fire_lancer     21.5       21.5         0      4.7       0.0    0.6   0.02    5.72   1.22
imp_elite_skirm__vs__elite_steppe           0.0        0.0         0      0.0       0.0    0.0      -       -   2.02
imp_elite_skirm__vs__heavy_camel            0.9        0.9         0      0.8       0.0    0.0   0.02    0.69   6.05
imp_elite_skirm__vs__hussar                 0.8        0.8         0      0.7       0.0    0.0   0.02    1.00   3.83
imp_elite_skirm__vs__elite_elephant        44.6       44.7         0     10.5       0.0    1.2   0.02    6.35   0.78
imp_elite_skirm__vs__paladin                0.2        0.2         0      0.2       0.0    0.0   0.02    1.20   2.83
elite_fire_lancer__vs__hand_cannoneer      28.7       28.7         0      0.1       0.0    0.8   0.02    3.03   1.13
heavy_cav_archer__vs__elite_elephant       51.9       52.4         0      5.4       0.0    1.5   0.02    1.81   0.78
heavy_cav_archer__vs__hussar                6.4        6.4         0      2.9       0.0    0.2   0.02    1.44   4.59
heavy_cav_archer__vs__paladin              10.5       10.5         0      3.7       0.0    0.3   0.02    1.37   2.87
hand_cannoneer__vs__elite_steppe            0.1        0.1         0      0.0       0.0    0.0   0.02    2.63   2.05
```

**4a — do tape chasers stick?** There is no general "the tape sticks and the
engine churns" effect, and in several families the sign is reversed:

- `champion__vs__heavy_cav_archer`: switch 41.1 % vs 36.7 %, abandon 18.8 % vs
  18.3 % — indistinguishable.
- `hand_cannoneer__vs__heavy_camel`: tape switch **65.2 %** / abandon **54.3 %**
  against engine **28.6 % / 0.4 %**. The tape's camels give up a living,
  in-range hand cannoneer more than half the time; the engine's essentially
  never do.
- `hand_cannoneer__vs__hussar`, `__vs__paladin`, `arbalester__vs__hussar`,
  `imp_elite_skirm__vs__*`: same direction, tape abandon 25–46 % vs engine
  0–1 %.
- `heavy_cav_archer__vs__elite_elephant`: reversed again — engine abandon
  78.4 % vs tape 44.2 %.

Read with M1, this is consistent: the tape's chaser has a 3–4 s cycle in which
it is out of contact for 3 s, so by the time it swings again the nearest body
is often a different one. Its "abandonment" is a *consequence* of the contact
loss, not a targeting policy. Nothing here says the tape chaser is stickier.

**4b — what the pursuit bar actually does today.** The audit the brief asked
for, and the answer is that the mechanism is loud and inert:

- **The lock is structurally unavailable.** `meleeTargetLock()` returns false
  when `target.isRanged()`, so `lockHeld` is **0 in every family** and every
  stuck-bar trip blacklists and nulls the target. `blk/min == stuck/min` to a
  rounding digit throughout.
- **The trip rate splits exactly on `PURSUIT_MIN_ADVANTAGE`.** The relaxed bar
  applies only while the target is `kiting` AND the chaser's speed advantage is
  at least 7.5 px/s (0.25 tiles/s); otherwise the bar stays at the flat
  30 px/s. Chasers below that threshold — champion 1.06 and halberdier 1.10
  against HCA 1.54 (negative), champion against arbalester 0.96 (+0.10 t/s =
  3 px/s), elite_elephant 0.99 against arbalester (+0.03 t/s = 0.9 px/s) —
  trip **15.3–51.9 times per chaser-minute**. Chasers above it (camel 1.60,
  hussar 1.65, paladin 1.49, steppe 1.68 against a 0.96 t/s shooter) trip
  **0.0–1.3 /min**. There is no family in between.
- **And it changes almost nothing.** Median re-acquire gap **0.02 s** (one
  tick), null-target residency **0.0–1.5 %** of chaser-time, `bump/min` **0.0**
  everywhere (the bump is melee-vs-melee scoped and correctly never fires here),
  median distance to the victim at the moment it was blacklisted **0.69–6.35
  tiles**, median chase span **0.78–7.01 s**. The unit blacklists, re-picks
  another archer on the next tick, and keeps walking. The `clr/min` column
  shows the all-blocked reset firing 0.0–10.5 /min to keep it supplied with
  targets.

So the engine's chasers are not "abandoning the chase" in any way that costs
them contact, and the tape gives no evidence they should stick harder. **The
pursuit bar / blacklist is not the lever.**

---

## M5. The P2 counterfactual, measured

`--r5d1 trailingWindowLead`, 9 recordings x 20 seeds, against the same engine
with the flag at its shipped default (off).

```
============================================================================================================
TABLE 5 -- champion__vs__heavy_cav_archer (9 recordings x 20 seeds).
P2 = R5D1.trailingWindowLead, shipped OFF. TAPE is the recording; ENG is HEAD defaults; ENG+P2 is --r5d1 trailingWindowLead.
============================================================================================================
metric                                                    TAPE           ENG        ENG+P2
------------------------------------------------------------------------------------------
runs pooled                                              9           180           180
fight duration, median s                             54.39         53.72         36.93
champion wipes the heavy_cav_archer side, % of runs          11.1           0.0         100.0
winner agreement vs tape, % of seeds                     -          88.9          11.1
  ... recordings won on a seed majority (of 9)             -             8             1
champion HP points left (median)                       0.0           0.0          28.2
heavy_cav_archer HP points left (median)              45.2           1.8           0.0
champion swing interval, median s                     2.77          2.02          2.02
champion landed hits PER RUN                          50.3          81.0          84.0
champion damage landed per run                         603           943           960
  ... vs heavy_cav_archer army max HP (960)          62.8%         98.2%        100.0%
champion hits per chaser-second                     0.0772        0.1352        0.1410
heavy_cav_archer damage landed per run                1456          1470          1056
  ... vs champion army max HP (1470)                 99.0%        100.0%         71.8%
heavy_cav_archer shots (total)                        2402         46980         32940
heavy_cav_archer land rate, % of resolvable shots          93.5          96.6          97.8
heavy_cav_archer land rate vs a MOVING champion, %          91.2          94.7          96.3
heavy_cav_archer landed hits per kiter-second        0.4009        0.5269        0.5289
heavy_cav_archer damage per resolvable shot           5.45          5.63          5.77
champions alive at t=10s, % of start                  85.2          85.7          85.7
champions alive at t=20s, % of start                  66.7          66.7          76.2
champions alive at t=30s, % of start                  47.1          47.6          66.7
champions alive at t=40s, % of start                  32.8          28.6          57.1
champions alive at t=50s, % of start                  19.0           9.5          57.1

per-recording winner (tape) and seed agreement:
tag                                         tape winner  ENG agree   ENG+P2 agree
champion__vs__heavy_cav_archer                   chaser    0/20        20/20    
champion__vs__heavy_cav_archer_r2                 kiter   20/20         0/20    
champion__vs__heavy_cav_archer_r3                 kiter   20/20         0/20    
champion__vs__heavy_cav_archer_r4                 kiter   20/20         0/20    
champion__vs__heavy_cav_archer_r5                 kiter   20/20         0/20    
champion__vs__heavy_cav_archer_r6                 kiter   20/20         0/20    
champion__vs__heavy_cav_archer_r7                 kiter   20/20         0/20    
champion__vs__heavy_cav_archer_r8                 kiter   20/20         0/20    
champion__vs__heavy_cav_archer_r9                 kiter   20/20         0/20
```

**Where the flip comes from.** Not from the kiter getting worse at shooting:
with P2 the HCA's land rate goes **96.6 → 97.8 %**, its land rate against a
MOVING champion **94.7 → 96.3 %**, and its landed hits per HCA-second are flat
(**0.5269 → 0.5289**). Its damage per resolvable shot rises (5.63 → 5.77). Per
unit of life, P2 makes the HCA *better*.

The flip comes from the fight being knife-edge in the first place:

| per run | tape | ENG | ENG+P2 |
|---|---|---|---|
| champion damage landed, % of the HCA army's max HP | **62.8 %** | **98.2 %** | 100.0 % |
| HCA damage landed, % of the champion army's max HP | 99.0 % | 100.0 % | 71.8 % |

The engine's champions already deliver **98.2 %** of exactly enough damage to
wipe the HCA side — the outcome is decided by a margin of under two percent of
one army's HP — while the tape's deliver **62.8 %**, i.e. the tape's HCA wins
with a third of its army still standing (median 45.2 HP points remaining
against the engine's 1.8). P2 shortens the fight (53.7 → 36.9 s median) and
cuts total HCA output by 28 % because the HCAs die sooner, and a 2 % margin
does not survive that. **ENG 8/9 → ENG+P2 1/9.**

That the engine reproduces the tape's WINNER on 8/9 today is therefore
accidental: it gets the right answer from two large errors of opposite sign
(champion output +56 %, HCA army-lifetime too short), and any correct change to
either side exposes it. The champion survival curve says the same thing —
tape and ENG agree at t=10/20/30 s and only diverge at t=40–50 s, i.e. the
engine's error is not in the opening exchange but in how the endgame resolves.

### The P2-enable ledger

P2 is safe to enable when the chaser-cadence model produces, on
`champion__vs__heavy_cav_archer` (9 recordings x 20 seeds, tapebox, HEAD
otherwise):

| quantity | today | required (tape) | factor |
|---|---|---|---|
| champion landed hits per run | 81.0 | **50.3** | 0.62 |
| champion damage per run | 943 | **603** | 0.64 |
| ... as % of the HCA army's max HP | 98.2 % | **62.8 %** | — |
| champion hits per chaser-alive-second | 0.1352 | **0.0772** | 0.57 |
| champion swing interval, median | 2.02 s | **2.77 s** | 1.37 |
| champion cycles that lose contact | 63.3 % | **97.2 %** | — |
| champion seconds in reach per cycle | 2.02 s | **0.66 s** | 0.33 |
| HCA HP points remaining, median | 1.8 | **45.2** | — |

and the guard rails that must NOT move while it happens:

- HCA landed hits per HCA-second must stay near **0.4009** (today 0.5269 —
  itself 31 % high, so the kiter side is not clean either, but it is a second
  order error next to the chaser's 75 %);
- champions alive at t=10 s must stay at **85 %** (all three columns already
  agree there — the opening is not broken);
- the tape's champion HP points remaining is **0.0** in the median: the
  champions are supposed to die. A model that saves them is wrong even if it
  fixes the winner.

The single sufficient statistic to watch is **champion damage per run as a
fraction of the HCA army's max HP: 98.2 % must become ~63 %.** Once it does,
the fight stops being knife-edge and P2's 28 % trim to HCA total output cannot
flip it.

---

## M6. Hand cannoneer land rate, and the P1 criterion

```
============================================================================================================================
TABLE 6 -- HAND CANNONEER LAND RATE under the CURRENT engine (post R5d/B2). `land%` = HIT / every shot that had time
to land. `mov%` = share of those shots whose aim target was moving at launch; `hitMov`/`hitStd` = land rate within each.
The gap is decomposed shift-share: MIX = the engine aiming at a different moving/standing mix at the tape's own
per-cell rates; RATE = the engine hitting the tape's mix less often. `+P1` is --r5d1 reducedDamageHits.
============================================================================================================================
family                                 src      shots   land%  whiff%  dodge%  scat%  wast%   mov%  hitMov  hitStd   rng    MIX   RATE
--------------------------------------------------------------------------------------------------------------------------------------
hand_cannoneer__vs__hussar             T         1157    91.8     2.1     2.7    0.4    1.4   44.2    89.4    93.7   0.4      -      -
                                       E        11598    91.3     6.6     1.3    0.8    0.1   55.8    88.2    95.1   0.8   -0.5   -0.0
                                       E+P1     12180    92.1     5.5     1.2    0.9    0.2   57.4    88.5    96.9   0.9   -0.6    0.8
hand_cannoneer__vs__paladin            T         1476    93.0     2.6     2.7    0.3    0.9   54.3    93.8    92.1   0.6      -      -
                                       E        14484    90.1     6.5     1.0    2.0    0.4   59.6    87.2    94.3   1.2    0.1   -3.1
                                       E+P1     14808    90.9     5.4     0.9    2.2    0.5   62.5    89.2    93.8   1.2    0.1   -2.2
hand_cannoneer__vs__heavy_camel        T         1364    86.1     1.7     3.5    0.1    2.8   50.4    89.8    82.4   0.8      -      -
                                       E        26820    86.8     9.4     1.3    2.0    0.6   54.3    82.0    92.4   1.1    0.3    0.3
                                       E+P1     27090    90.3     6.7     0.8    2.0    0.2   46.2    86.0    94.0   1.0   -0.3    4.5
hand_cannoneer__vs__elite_elephant     T          718    97.4     0.6     0.4    0.4    0.1   67.4    97.7    96.6   0.6      -      -
                                       E         9796    91.6     5.4     1.6    1.4    0.0   78.4    91.2    93.2   1.1    0.1   -5.8
                                       E+P1      9610    92.8     4.1     1.5    1.4    0.1   77.6    92.2    94.9   1.0    0.1   -4.6
champion__vs__hand_cannoneer           T          137    64.2     5.8     9.5    1.5   14.6   81.8    63.4    68.0   1.1      -      -
                                       E         1996    87.3     8.0     1.8    0.8    2.0   82.3    86.4    91.4   1.4   -0.0   23.1
                                       E+P1      2052    88.5     7.0     1.6    0.7    2.2   82.9    88.2    89.6   1.3   -0.1   24.3
halberdier__vs__hand_cannoneer         T          105    61.0    14.3     8.6    2.9    8.6   68.6    61.1    60.6   1.1      -      -
                                       E         1514    88.5     7.9     1.5    0.6    1.4   77.5    87.7    91.6   1.3    0.0   27.5
                                       E+P1      1541    88.4     7.0     1.3    0.6    2.7   76.8    88.2    89.1   1.3    0.0   27.4
elite_fire_lancer__vs__hand_cannoneer  T          161    57.1     5.6    10.6    1.9   13.0   61.5    56.6    58.1   1.8      -      -
                                       E         2174    83.4    10.4     1.9    0.8    3.3   80.4    82.0    89.1   1.7   -0.3   26.5
                                       E+P1      2371    85.5     8.7     1.1    1.1    3.6   76.8    83.8    91.2   1.5   -0.2   28.6
hand_cannoneer__vs__elite_steppe       T          190    92.6     1.1     4.2    0.0    1.1   28.9    92.7    92.6   1.1      -      -
                                       E         1933    89.6     6.8     2.7    0.6    0.2   44.2    81.9    95.7   2.2    0.0   -3.1
                                       E+P1      1920    90.3     5.8     3.2    0.6    0.1   45.5    83.2    96.3   2.2    0.0   -2.3
```

```
================================================================================================
TABLE 6b -- the same shots split by LAUNCH RANGE instead (`near` = within 0.6 x attack_range, rff.accuracy()'s own cut),
plus `landD` = median distance from the victim at which a NON-landing shot arrived (the arrival resolution).
================================================================================================
family                                 src      near%  hitNear  hitFar   landD
------------------------------------------------------------------------------
hand_cannoneer__vs__hussar             T         96.3     93.4    48.8    0.58
                                       E         89.8     91.1    92.4    0.38
                                       E+P1      90.2     92.0    92.4    0.40
hand_cannoneer__vs__paladin            T         95.5     95.9    31.8    0.48
                                       E         87.6     90.0    90.7    0.41
                                       E+P1      87.8     91.0    90.7    0.42
hand_cannoneer__vs__heavy_camel        T         94.3     88.6    46.2    0.93
                                       E         93.2     86.4    91.3    0.39
                                       E+P1      93.4     90.2    91.9    0.40
hand_cannoneer__vs__elite_elephant     T         97.6     97.9    76.5    0.52
                                       E         90.4     92.2    86.1    0.42
                                       E+P1      90.3     93.6    86.1    0.43
champion__vs__hand_cannoneer           T         94.2     64.3    62.5    0.54
                                       E         82.9     87.3    87.1    0.39
                                       E+P1      83.5     88.7    87.3    0.38
halberdier__vs__hand_cannoneer         T         92.4     63.9    25.0    0.41
                                       E         86.9     88.6    88.2    0.37
                                       E+P1      87.4     88.4    88.6    0.39
elite_fire_lancer__vs__hand_cannoneer  T         84.5     60.3    40.0    0.52
                                       E         79.7     86.8    70.2    0.34
                                       E+P1      82.2     86.5    80.8    0.37
hand_cannoneer__vs__elite_steppe       T         94.2     95.5    45.5    1.56
                                       E         84.4     90.4    85.4    0.40
                                       E+P1      84.3     91.0    86.7    0.42
```

```
================================================================================================================
TABLE 6c -- THE P1 FLIP CRITERION. Land rate is not the quantity P1 moves: P1 turns a failed accuracy roll from
'pays full' into 'pays half if the displaced landing point still overlaps a body', so it raises land% and lowers
DAMAGE PER SHOT at once. `d/shot` is HC damage landed per resolvable shot; `agree` is winner agreement with the tape
(seeds, and recordings won on a majority of seeds).
================================================================================================================
family                                  n_rec  d/shot T  d/shot E  d/shot E+P1          agree E       agree E+P1
----------------------------------------------------------------------------------------------------------------
hand_cannoneer__vs__hussar                  6      9.37      9.62         8.68       66.7%  4/6       66.7%  4/6
hand_cannoneer__vs__paladin                 6      8.98      8.93         8.10       83.3%  5/6       83.3%  5/6
hand_cannoneer__vs__heavy_camel             6     10.47     10.84        10.09      100.0%  6/6       50.0%  0/6
hand_cannoneer__vs__elite_elephant          2      7.68      7.28         6.66      100.0%  2/2      100.0%  2/2
champion__vs__hand_cannoneer                1     10.73     15.30        14.99       95.0%  1/1      100.0%  1/1
halberdier__vs__hand_cannoneer              1     12.00     17.71        17.22      100.0%  1/1      100.0%  1/1
elite_fire_lancer__vs__hand_cannoneer       1     11.09     17.42        15.86      100.0%  1/1      100.0%  1/1
hand_cannoneer__vs__elite_steppe            1      9.20      9.39         8.65      100.0%  1/1      100.0%  1/1
```

```
============================================================================================================
TABLE 6d -- hand_cannoneer__vs__heavy_camel (6 recordings x 20 seeds).
P1 = R5D1.reducedDamageHits, shipped OFF because enabling it flips this family. TAPE is the recording; ENG is HEAD defaults; ENG+P1 is --r5d1 reducedDamageHits.
============================================================================================================
metric                                                    TAPE           ENG        ENG+P1
------------------------------------------------------------------------------------------
runs pooled                                              6           120           120
fight duration, median s                             42.51         52.83         69.28
heavy_camel wipes the hand_cannoneer side, % of runs           0.0           0.0          50.0
winner agreement vs tape, % of seeds                     -         100.0          50.0
  ... recordings won on a seed majority (of 6)             -             6             0
heavy_camel HP points left (median)                    0.0           0.0           1.3
hand_cannoneer HP points left (median)                68.8          28.5           1.3
heavy_camel swing interval, median s                  2.51          2.02          2.02
heavy_camel landed hits PER RUN                       39.5          87.8         116.0
heavy_camel damage landed per run                      273           591           775
  ... vs hand_cannoneer army max HP (840)            32.5%         70.3%         92.3%
heavy_camel hits per chaser-second                  0.0964        0.1802        0.1939
hand_cannoneer damage landed per run                  2380          2380          2264
  ... vs heavy_camel army max HP (2380)             100.0%        100.0%         95.1%
hand_cannoneer shots (total)                          1364         26820         27090
hand_cannoneer land rate, % of resolvable shots          86.1          86.8          90.3
hand_cannoneer land rate vs a MOVING heavy_camel, %          89.8          82.0          86.0
hand_cannoneer landed hits per kiter-second         0.2301        0.2486        0.2594
hand_cannoneer damage per resolvable shot            10.47         10.84         10.09
heavy_camels alive at t=10s, % of start               84.3          89.4          91.2
heavy_camels alive at t=20s, % of start               63.7          67.1          72.9
heavy_camels alive at t=30s, % of start               40.2          44.1          52.6
heavy_camels alive at t=40s, % of start               12.7          25.0          35.6
heavy_camels alive at t=50s, % of start                0.0           8.2          25.6

per-recording winner (tape) and seed agreement:
tag                                         tape winner  ENG agree   ENG+P1 agree
hand_cannoneer__vs__heavy_camel                   kiter   20/20        10/20    
hand_cannoneer__vs__heavy_camel_r2                kiter   20/20        10/20    
hand_cannoneer__vs__heavy_camel_r3                kiter   20/20        10/20    
hand_cannoneer__vs__heavy_camel_r4                kiter   20/20        10/20    
hand_cannoneer__vs__heavy_camel_r5                kiter   20/20        10/20    
hand_cannoneer__vs__heavy_camel_r6                kiter   20/20        10/20    

wrote C:\Users\ddk22\AppData\Local\Temp\claude\D--AI-aoe2-matchup\a9df76fd-3235-4257-bba6-2fabfe9e152e\scratchpad\c1.json
```

**The land rate is no longer the problem.** R5c measured the tape's HC at
78–81 % against the engine's 72–83 % — but that was over the six
ranged-vs-ranged recordings. Over the HC-vs-melee families, under the current
post-R5d/B2 engine:

| family | tape land% | engine land% | Δ | MIX | RATE |
|---|---|---|---|---|---|
| `hand_cannoneer__vs__hussar` | 91.8 | 91.3 | −0.5 | −0.5 | −0.0 |
| `hand_cannoneer__vs__paladin` | 93.0 | 90.1 | −2.9 | +0.1 | −3.1 |
| `hand_cannoneer__vs__heavy_camel` | 86.1 | 86.8 | **+0.7** | +0.3 | +0.3 |
| `hand_cannoneer__vs__elite_elephant` | 97.4 | 91.6 | −5.8 | +0.1 | −5.8 |
| `hand_cannoneer__vs__elite_steppe` | 92.6 | 89.6 | −3.0 | +0.0 | −3.1 |

The shift-share says the residual is almost entirely a RATE effect (the engine
hits the tape's own mix of moving/standing targets less often), not a MIX
effect — the engine's target mix is 4–11 points more mover-heavy but that costs
under a point of land rate. And the RATE gap is concentrated on MOVERS
(`hitMov` 82.0–92.2 engine against 89.8–97.7 tape) while the engine is
consistently BETTER than the tape on standers (`hitStd` 92.4–95.7 against
82.4–96.6). Table 6b adds the geometry: the tape's HC loses badly at long range
(`hitFar` 31.8–76.5 %) where the engine is flat across range (86–92 %), but
under 5 % of these shots are long — these fights are fought at a median launch
range of **0.4–2.2 tiles**, point blank, with the melee already on top of the
guns.

The three rows where the HC is the CHASED side (`champion__vs__hand_cannoneer`,
`halberdier__vs__`, `elite_fire_lancer__vs__`) are the visible R5c-style gap:
tape 57–64 % against engine 83–89 %, RATE +23 to +28 points. All three are
single recordings with 105–161 tape shots, so they are direction, not
magnitude — and they say the engine's HC is *too accurate* there, not too
inaccurate.

**The P1 flip criterion.** Land rate is the wrong quantity to gate on: P1 turns
a failed accuracy roll from "pays full" into "pays half if the displaced
landing point still overlaps a body", which RAISES the land rate and LOWERS the
damage per shot at once. On `hand_cannoneer__vs__heavy_camel`:

| | tape | ENG | ENG+P1 |
|---|---|---|---|
| HC land rate | 86.1 % | 86.8 % | 90.3 % |
| **HC damage per resolvable shot** | **10.47** | **10.84** (+3.5 %) | **10.09** (−3.6 %) |
| HC damage per run, % of the camel army's max HP | 100.0 % | 100.0 % | 95.1 % |
| **camel damage per run, % of the HC army's max HP** | **32.5 %** | **70.3 %** | **92.3 %** |
| camel hits per chaser-second | 0.0964 | 0.1802 | 0.1939 |
| winner agreement | — | **6/6** | **0/6** (10/20 seeds each) |

The HC's own output is *already correct to within 3.5 %* and P1 moves it by
6.9 %, landing 3.6 % on the other side of the tape. That is not what flips the
family. What flips it is that **the engine's camels already deliver 2.16x the
tape's damage** (70.3 % of the HC army's max HP per run against 32.5 %), so the
fight sits on a razor and a 5 % trim to the guns decides it — every one of the
six recordings goes to exactly 10/20 seeds, the definition of a coin flip.

**P1 is enabled when**, on `hand_cannoneer__vs__heavy_camel` (6 recordings x 20
seeds):

| quantity | today | required (tape) | factor |
|---|---|---|---|
| heavy camel landed hits per run | 87.8 | **39.5** | 0.45 |
| heavy camel damage per run | 591 | **273** | 0.46 |
| ... as % of the HC army's max HP | 70.3 % | **32.5 %** | — |
| camel hits per chaser-alive-second | 0.1802 | **0.0964** | 0.53 |
| camel cycles that lose contact | 61.2 % | **95.7 %** | — |
| camel seconds in reach per cycle | 1.72 s | **0.49 s** | 0.28 |
| HC HP points remaining, median | 28.5 | **68.8** | — |

with the HC side's own numbers held inside their present accuracy: land rate
within ~1 point of 86.1 %, damage per resolvable shot within ~5 % of 10.47.
Once the camel's damage per run comes down to ~273, P1's −6.9 % on HC damage
per shot cannot decide anything, and the flip test becomes meaningful rather
than a coin toss. The same criterion should then be re-run on
`hand_cannoneer__vs__hussar` (4/6 today, unchanged by P1) and
`hand_cannoneer__vs__paladin` (5/6 today, unchanged by P1), whose chaser excess
is 1.32x and 1.60x respectively.

---

## What this does and does not license

**Established.**

1. The chaser-cadence defect is real on the current engine, is 1.22x median
   across 29 families, and is a **contact-duration** defect: 0.66 s in reach
   per cycle on tape against 1.81 s in the engine.
2. The proximate cause sits on the **kiter**, not the chaser: after being hit,
   the tape's kiter leaves reach in 0.08 s, runs at cos 0.88 away from the unit
   that hit it, and opens 1.03 tiles of radial separation inside one reload.
   The engine's takes 0.42 s, runs at cos 0.61, and opens 0.05 tiles.
3. Two further kiter-side errors are separable and class-specific: the three
   0.96 t/s shooters are parked ~2x too often and move in 0.3–0.4 s dribbles
   against the tape's 2.7–3.4 s runs; the 1.54 t/s HCA's duty cycle is already
   correct.
4. The engine also lands 19.8 % of chaser hits while the chaser is walking,
   which the tape does 0.0 % of the time in **every** family, and resolves
   every hit exactly at its own reach where the tape resolves half of them
   past it.
5. The pursuit bar / blacklist is not implicated: it fires 16–52 times per
   chaser-minute in the fast-kiter families and costs 0.02 s and 1 % of
   chaser-time each time.

**Not established, and deliberately not attempted here.**

- Which of (2), (3) or (4) is the largest single contributor. They are measured
  separately but not decomposed against each other, because doing that
  honestly needs an A/B of candidate rules, which is a design step.
- Whether fixing the kiter's contact break would leave ranged-vs-ranged
  (R5/R5c/R5e) unchanged. The E9-successor stop-to-fire and the E5a/E10 group
  kite are shared with those fights, and this document measured only the
  melee-chasing-ranged corpus.
- Anything about the `elite_fire_lancer` families, whose charge projectile
  makes "swing interval" meaningless; and the eleven single-recording families,
  whose tape samples are 2–49 intervals and are printed for direction only.

**Threats to validity, stated.**

- Positions are 10 Hz on both sides (the recorder's own rate; the engine dump
  matches it deliberately). A 0.02-tile-per-sample "moving" bar is the
  campaign's standing choice; `cStep`/`vStep` are reported alongside every
  movement-state split so a reader can see whether a flag is walking or jitter.
- `hits per chaser-alive-second` uses summed living-unit seconds cut at the
  wipe, so a side that dies early is not credited with idle time. Tape and
  engine use the identical computation.
- Winner is `(survivors, hp_remaining)` rank, the same ordering the campaign's
  scorer and `melee_hp_report.py` use. The stricter "wiped the other side"
  predicate gives the same 8/9 → 1/9 on the P2 family.

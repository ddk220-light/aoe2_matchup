# Standard units — full matchup summary (2026-08-06)

> **SUPERSEDED by [`STANDARD_UNITS_SUMMARY_2026-08-07.md`](STANDARD_UNITS_SUMMARY_2026-08-07.md)**, which re-runs the same sweep on the
> engine after `e4730558` and `31df43ae`. The numbers below are the engine as of
> `fd16ec3e` and are kept for the before/after comparison.

Every standard-unit matchup in the authorized archive, run on the current
engine. Three things are derived **independently of the tape** and only then
compared against it: the purchase (how many of each unit), the starting
layout, and the AI order script. Nothing here is fitted to the outcome.

The archive holds 339 recorded fights under 122 labels, but 21 of those labels
are the same scenario written both ways round (`A vs B` and `B vs A` have
byte-identical rosters and positions). Merged on the roster, that is
**101 distinct matchups**; each one's repeats are pooled. The sim's 25 samples
come out bit-identical for every merged pair, which is also a determinism check.

## Metric

**Signed winner-HP%** = winner's remaining HP / winner's own starting HP pool
x 100, signed **+ when side 3 wins** and **- when side 2 wins**. One axis, so
tape and sim subtract cleanly even when the two disagree about the winner.

- **Tape mean** — mean over that matchup's recorded repeats.
- **Sim mean** — mean over 25 runs that differ only in acquisition order
  (the one thing the recorder cannot observe); everything else is deterministic.
- **delta = sim mean - tape mean.** This is the headline number.

## What is derived, and how

| stage | rule | checked against the tape |
|---|---|---|
| **Purchase** | dat base costs, `c = food + wood + 1.5 x gold`; cheaper side buys `min(21, floor(3000/c))`; other side spends the same weighted budget | starting counts: **122/122 exact** (all 122 labels) |
| **Layout** | the generator's deterministic block placement for that pair of counts | starting positions reproduce |
| **Orders** | exactly one *mobile* ranged side -> that side kites on a beat derived from its dat reload; siege ranged and melee fight on native aiOrder waves | recorded command signature: **119/122** |

Kite beats are measured from tape for Arbalester, Elite Skirmisher and Heavy Cav Archer;
for **Hand Cannoneer** the beat is *constructed* from its reload (no tape column for it
yet), which is the most likely cause of the four large hand-cannoneer deltas below.

## Engine configuration

Current engine, `AOE2X_EXP_ENGAGEMENT=pursuit AOE2X_EXP_ORDERS=1` (the config the whole
calibrated corpus runs under), 9000-tick cap, acquisition orders drawn from a fixed
mulberry32 seed so the run reproduces exactly.

## Headline

| | matchups | mean \|delta\| | median \|delta\| | winner agrees |
|---|---:|---:|---:|---:|
| **All** | 101 | 14.7 | 9.4 | 96/101 |
| **Modeled only** (excl. ranged-vs-ranged) | 80 | 14.3 | 9.2 | 77/80 |
| Kite (mobile ranged vs melee) | 32 | 19.1 | 12.3 | 30/32 |
| Native waves (melee/siege vs melee) | 48 | 11.1 | 7.3 | 47/48 |
| Ranged vs ranged (order script UNMODELED) | 21 | 16.3 | 9.7 | 19/21 |

**Purchase solution: 101/101 exact.** Derived from dat base costs with
`c = food + wood + 1.5 x gold`; the cheaper side buys `min(21, floor(3000/c))`,
the other side spends the same weighted budget. Every predicted pair of counts
equals what the tape actually started with.

The ranged-vs-ranged group is listed for completeness but is **not modeled** —
those tapes are driven by a scripted duel we have not decoded, so the sim runs
them natively and the deltas there measure a missing feature, not a wrong one.

## Kite (mobile ranged vs melee) — 32 matchups

| matchup | side 2 buys | side 3 buys | weighted spend<br><sub>side 2 / side 3</sub> | kiter | tape mean (n) | sim mean (n) | delta |
|---|---|---|---:|---|---:|---:|---:|
| Elite Skirmisher vs Paladin | 21x Elite Skirmisher | 7x Paladin | 1260 / 1208 | side 2 <br><sub>measured</sub> | +87.4 (4) <br><sub>+85.6..+89.0</sub> | +86.9 (25) <br><sub>sd 1.3</sub> | **-0.5** |
| Hand Cannoneer vs Elite Fire Lancer | 19x Hand Cannoneer | 21x Elite Fire Lancer | 2280 / 2362 | side 2 <br><sub>constructed</sub> | -60.9 (1) | -62.1 (25) <br><sub>sd 3.4</sub> | **-1.2** |
| Elite Skirmisher vs Elite Steppe Lancer | 21x Elite Skirmisher | 9x Elite Steppe Lancer | 1260 / 1170 | side 2 <br><sub>measured</sub> | +85.9 (3) <br><sub>+84.6..+86.8</sub> | +87.9 (25) <br><sub>sd 0.6</sub> | **+2.1** |
| Arbalester vs Halberdier | 13x Arbalester | 21x Halberdier | 1202 / 1260 | side 2 <br><sub>measured</sub> | -92.9 (4) <br><sub>-96.0..-89.2</sub> | -95.4 (25) <br><sub>sd 2.0</sub> | **-2.5** |
| Arbalester vs Elite Fire Lancer | 21x Arbalester | 17x Elite Fire Lancer | 1942 / 1912 | side 2 <br><sub>measured</sub> | -72.4 (2) <br><sub>-72.6..-72.3</sub> | -69.6 (25) <br><sub>sd 4.0</sub> | **+2.8** |
| Elite Skirmisher vs Elite Fire Lancer | 21x Elite Skirmisher | 11x Elite Fire Lancer | 1260 / 1238 | side 2 <br><sub>measured</sub> | +59.0 (1) | +62.9 (25) <br><sub>sd 3.2</sub> | **+3.9** |
| Elite Skirmisher vs Hussar | 21x Elite Skirmisher | 15x Hussar | 1260 / 1200 | side 2 <br><sub>measured</sub> | +85.4 (3) <br><sub>+84.7..+86.3</sub> | +89.9 (25) <br><sub>sd 0.8</sub> | **+4.4** |
| Heavy Cav Archer vs Paladin | 21x Heavy Cav Archer | 15x Paladin | 2730 / 2588 | side 2 <br><sub>measured</sub> | +36.9 (11) <br><sub>+27.7..+50.2</sub> | +30.0 (24) <br><sub>sd 12.9</sub> | **-6.9** |
| Elite Skirmisher vs Elite Battle Elephant | 21x Elite Skirmisher | 6x Elite Battle Elephant | 1260 / 1230 | side 2 <br><sub>measured</sub> | +84.5 (4) <br><sub>+83.1..+85.9</sub> | +92.6 (25) <br><sub>sd 0.5</sub> | **+8.0** |
| Heavy Cav Archer vs Heavy Camel Rider | 21x Heavy Cav Archer | 18x Heavy Camel Rider | 2730 / 2610 | side 2 <br><sub>measured</sub> | +36.3 (10) <br><sub>+30.0..+41.4</sub> | +27.7 (25) <br><sub>sd 16.4</sub> | **-8.6** |
| Arbalester vs Paladin | 21x Arbalester | 11x Paladin | 1942 / 1898 | side 2 <br><sub>measured</sub> | +41.8 (14) <br><sub>+33.2..+58.0</sub> | +50.9 (25) <br><sub>sd 4.1</sub> | **+9.1** |
| Heavy Cav Archer vs Elite Steppe Lancer | 21x Heavy Cav Archer | 21x Elite Steppe Lancer | 2730 / 2730 | side 2 <br><sub>measured</sub> | +28.0 (10) <br><sub>+15.5..+38.1</sub> | +37.4 (25) <br><sub>sd 7.1</sub> | **+9.4** |
| Hand Cannoneer vs Halberdier | 10x Hand Cannoneer | 21x Halberdier | 1200 / 1260 | side 2 <br><sub>constructed</sub> | -76.5 (1) | -66.6 (25) <br><sub>sd 11.4</sub> | **+9.9** |
| Arbalester vs Elite Battle Elephant | 21x Arbalester | 9x Elite Battle Elephant | 1942 / 1845 | side 2 <br><sub>measured</sub> | +79.8 (7) <br><sub>+75.8..+81.9</sub> | +90.3 (25) <br><sub>sd 1.0</sub> | **+10.6** |
| Heavy Cav Archer vs Elite Battle Elephant | 21x Heavy Cav Archer | 13x Elite Battle Elephant | 2730 / 2665 | side 2 <br><sub>measured</sub> | +74.4 (3) <br><sub>+71.7..+78.3</sub> | +85.3 (25) <br><sub>sd 1.5</sub> | **+10.9** |
| Hand Cannoneer vs Champion | 14x Hand Cannoneer | 21x Champion | 1680 / 1680 | side 2 <br><sub>constructed</sub> | -76.6 (4) <br><sub>-82.5..-73.2</sub> | -64.6 (25) <br><sub>sd 10.2</sub> | **+12.0** |
| Heavy Cav Archer vs Halberdier | 9x Heavy Cav Archer | 21x Halberdier | 1170 / 1260 | side 2 <br><sub>measured</sub> | +18.0 (10) <br><sub>-6.8..+34.0</sub> | +30.5 (25) <br><sub>sd 25.4</sub> | **+12.5** |
| Arbalester vs Heavy Camel Rider | 21x Arbalester | 13x Heavy Camel Rider | 1942 / 1885 | side 2 <br><sub>measured</sub> | -62.3 (2) <br><sub>-67.6..-57.1</sub> | -75.2 (25) <br><sub>sd 3.9</sub> | **-12.9** |
| Elite Skirmisher vs Halberdier | 21x Elite Skirmisher | 21x Halberdier | 1260 / 1260 | side 2 <br><sub>measured</sub> | -60.0 (1) | -73.6 (25) <br><sub>sd 2.5</sub> | **-13.6** |
| Heavy Cav Archer vs Hussar | 12x Heavy Cav Archer | 21x Hussar | 1560 / 1680 | side 2 <br><sub>measured</sub> | +35.3 (5) <br><sub>+29.8..+44.1</sub> | +51.4 (25) <br><sub>sd 5.6</sub> | **+16.1** |
| Arbalester vs Champion | 18x Arbalester | 21x Champion | 1665 / 1680 | side 2 <br><sub>measured</sub> | -81.8 (8) <br><sub>-84.7..-75.7</sub> | -65.1 (25) <br><sub>sd 12.0</sub> | **+16.7** |
| Heavy Cav Archer vs Elite Fire Lancer | 18x Heavy Cav Archer | 21x Elite Fire Lancer | 2340 / 2362 | side 2 <br><sub>measured</sub> | +31.9 (5) <br><sub>+24.7..+45.1</sub> | +15.1 (25) <br><sub>sd 19.4</sub> | **-16.8** |
| Elite Skirmisher vs Champion | 21x Elite Skirmisher | 15x Champion | 1260 / 1200 | side 2 <br><sub>measured</sub> | +54.2 (4) <br><sub>+47.4..+60.8</sub> | +72.6 (25) <br><sub>sd 4.4</sub> | **+18.4** |
| Hand Cannoneer vs Heavy Camel Rider | 21x Hand Cannoneer | 17x Heavy Camel Rider | 2520 / 2465 | side 2 <br><sub>constructed</sub> | -67.5 (6) <br><sub>-73.6..-61.3</sub> | -42.8 (25) <br><sub>sd 9.8</sub> | **+24.7** |
| Arbalester vs Hussar | 18x Arbalester | 21x Hussar | 1665 / 1680 | side 2 <br><sub>measured</sub> | +29.7 (5) <br><sub>+26.4..+35.2</sub> | +55.6 (25) <br><sub>sd 5.4</sub> | **+25.9** |
| Arbalester vs Elite Steppe Lancer | 21x Arbalester | 14x Elite Steppe Lancer | 1942 / 1820 | side 2 <br><sub>measured</sub> | +9.2 (10) <br><sub>-27.1..+24.0</sub> | +42.4 (25) <br><sub>sd 3.7</sub> | **+33.2** |
| Hand Cannoneer vs Paladin | 21x Hand Cannoneer | 14x Paladin | 2520 / 2415 | side 2 <br><sub>constructed</sub> | +15.4 (10) <br><sub>-9.0..+32.1</sub> | +53.2 (25) <br><sub>sd 5.2</sub> | **+37.8** |
| Elite Skirmisher vs Heavy Camel Rider | 21x Elite Skirmisher | 8x Heavy Camel Rider | 1260 / 1160 | side 2 <br><sub>measured</sub> | +39.8 (1) | -2.0 (23) <br><sub>sd 22.4</sub> | **-41.8** ! |
| Heavy Cav Archer vs Champion | 12x Heavy Cav Archer | 21x Champion | 1560 / 1680 | side 2 <br><sub>measured</sub> | -36.5 (14) <br><sub>-68.9..+8.8</sub> | +15.8 (25) <br><sub>sd 21.3</sub> | **+52.2** ! |
| Hand Cannoneer vs Elite Steppe Lancer | 21x Hand Cannoneer | 19x Elite Steppe Lancer | 2520 / 2470 | side 2 <br><sub>constructed</sub> | +8.0 (1) | +61.3 (25) <br><sub>sd 2.4</sub> | **+53.3** |
| Hand Cannoneer vs Hussar | 14x Hand Cannoneer | 21x Hussar | 1680 / 1680 | side 2 <br><sub>constructed</sub> | +5.6 (6) <br><sub>-18.8..+17.9</sub> | +59.4 (25) <br><sub>sd 8.0</sub> | **+53.8** |
| Hand Cannoneer vs Elite Battle Elephant | 21x Hand Cannoneer | 12x Elite Battle Elephant | 2520 / 2460 | side 2 <br><sub>constructed</sub> | +2.4 (5) <br><sub>-38.3..+32.3</sub> | +80.0 (25) <br><sub>sd 2.5</sub> | **+77.6** |

## Native waves (melee/siege vs melee) — 48 matchups

| matchup | side 2 buys | side 3 buys | weighted spend<br><sub>side 2 / side 3</sub> | tape mean (n) | sim mean (n) | delta |
|---|---|---|---:|---:|---:|---:|
| Elite Battle Elephant vs Champion | 8x Elite Battle Elephant | 21x Champion | 1640 / 1680 | -40.5 (4) <br><sub>-51.6..-34.7</sub> | -40.4 (25) <br><sub>sd 5.2</sub> | **+0.1** |
| Heavy Scorpion vs Heavy Camel Rider | 15x Heavy Scorpion | 20x Heavy Camel Rider | 2812 / 2900 | +56.6 (2) <br><sub>+54.5..+58.8</sub> | +56.9 (25) <br><sub>sd 5.0</sub> | **+0.3** |
| Halberdier vs Champion | 21x Halberdier | 15x Champion | 1260 / 1200 | +70.5 (1) | +71.2 (25) <br><sub>sd 1.6</sub> | **+0.7** |
| Halberdier vs Heavy Camel Rider | 21x Halberdier | 8x Heavy Camel Rider | 1260 / 1160 | -83.8 (1) | -82.7 (25) <br><sub>sd 1.2</sub> | **+1.1** |
| Heavy Scorpion vs Paladin | 15x Heavy Scorpion | 17x Paladin | 2812 / 2932 | +79.0 (5) <br><sub>+68.1..+87.1</sub> | +77.5 (25) <br><sub>sd 3.0</sub> | **-1.5** |
| Elite Fire Lancer vs Heavy Camel Rider | 21x Elite Fire Lancer | 16x Heavy Camel Rider | 2362 / 2320 | -74.1 (1) | -72.1 (25) <br><sub>sd 2.4</sub> | **+2.0** |
| Elite Steppe Lancer vs Paladin | 21x Elite Steppe Lancer | 15x Paladin | 2730 / 2588 | +28.9 (4) <br><sub>+19.3..+39.6</sub> | +26.8 (25) <br><sub>sd 8.7</sub> | **-2.1** |
| Hussar vs Champion | 21x Hussar | 21x Champion | 1680 / 1680 | +39.8 (4) <br><sub>+31.9..+43.8</sub> | +37.1 (25) <br><sub>sd 7.7</sub> | **-2.6** |
| Halberdier vs Paladin | 21x Halberdier | 7x Paladin | 1260 / 1208 | -73.8 (1) | -71.2 (25) <br><sub>sd 2.3</sub> | **+2.6** |
| Elite Steppe Lancer vs Elite Battle Elephant | 21x Elite Steppe Lancer | 13x Elite Battle Elephant | 2730 / 2665 | +56.5 (1) | +59.2 (25) <br><sub>sd 4.7</sub> | **+2.7** |
| Heavy Camel Rider vs Champion | 11x Heavy Camel Rider | 21x Champion | 1595 / 1680 | +65.2 (1) | +68.5 (25) <br><sub>sd 2.0</sub> | **+3.3** |
| Halberdier vs Elite Battle Elephant | 21x Halberdier | 6x Elite Battle Elephant | 1260 / 1230 | -79.2 (1) | -75.8 (25) <br><sub>sd 2.3</sub> | **+3.4** |
| Elite Battle Elephant vs Paladin | 14x Elite Battle Elephant | 17x Paladin | 2870 / 2932 | -48.7 (1) | -45.1 (25) <br><sub>sd 5.1</sub> | **+3.6** |
| Elite Fire Lancer vs Elite Battle Elephant | 21x Elite Fire Lancer | 11x Elite Battle Elephant | 2362 / 2255 | -47.2 (1) | -42.9 (25) <br><sub>sd 4.9</sub> | **+4.3** |
| Heavy Camel Rider vs Paladin | 20x Heavy Camel Rider | 16x Paladin | 2900 / 2760 | -51.6 (1) | -46.8 (25) <br><sub>sd 3.5</sub> | **+4.8** |
| Elite Fire Lancer vs Elite Steppe Lancer | 21x Elite Fire Lancer | 18x Elite Steppe Lancer | 2362 / 2340 | -53.8 (1) | -58.7 (25) <br><sub>sd 2.8</sub> | **-4.9** |
| Heavy Scorpion vs Elite Steppe Lancer | 14x Heavy Scorpion | 21x Elite Steppe Lancer | 2625 / 2730 | +69.3 (2) <br><sub>+63.5..+75.1</sub> | +63.9 (25) <br><sub>sd 3.3</sub> | **-5.4** |
| Paladin vs Elite Battle Elephant | 17x Paladin | 14x Elite Battle Elephant | 2932 / 2870 | +41.4 (4) <br><sub>+36.2..+45.8</sub> | +46.8 (25) <br><sub>sd 4.2</sub> | **+5.4** |
| Elite Steppe Lancer vs Heavy Camel Rider | 21x Elite Steppe Lancer | 18x Heavy Camel Rider | 2730 / 2610 | +47.8 (1) | +53.3 (25) <br><sub>sd 4.8</sub> | **+5.5** |
| Heavy Scorpion vs Hussar | 8x Heavy Scorpion | 21x Hussar | 1500 / 1680 | +81.1 (4) <br><sub>+75.2..+91.4</sub> | +75.2 (25) <br><sub>sd 3.3</sub> | **-5.9** |
| Heavy Scorpion vs Halberdier | 6x Heavy Scorpion | 21x Halberdier | 1125 / 1260 | +66.3 (2) <br><sub>+63.8..+68.8</sub> | +59.9 (25) <br><sub>sd 4.3</sub> | **-6.4** |
| Elite Fire Lancer vs Halberdier | 11x Elite Fire Lancer | 21x Halberdier | 1238 / 1260 | -49.0 (1) | -42.3 (25) <br><sub>sd 4.8</sub> | **+6.7** |
| Hussar vs Elite Battle Elephant | 21x Hussar | 8x Elite Battle Elephant | 1680 / 1640 | +65.8 (1) | +59.1 (25) <br><sub>sd 3.5</sub> | **-6.7** |
| Elite Fire Lancer vs Champion | 14x Elite Fire Lancer | 21x Champion | 1575 / 1680 | +54.8 (1) | +62.0 (25) <br><sub>sd 1.6</sub> | **+7.2** |
| Champion vs Elite Battle Elephant | 21x Champion | 8x Elite Battle Elephant | 1680 / 1640 | +33.3 (7) <br><sub>+24.5..+47.8</sub> | +40.6 (25) <br><sub>sd 5.2</sub> | **+7.3** |
| Hussar vs Paladin | 21x Hussar | 9x Paladin | 1680 / 1552 | +33.4 (4) <br><sub>+22.2..+46.3</sub> | +25.9 (25) <br><sub>sd 7.8</sub> | **-7.5** |
| Elite Steppe Lancer vs Halberdier | 9x Elite Steppe Lancer | 21x Halberdier | 1170 / 1260 | +67.6 (1) | +75.5 (25) <br><sub>sd 1.4</sub> | **+7.9** |
| Elite Fire Lancer vs Paladin | 21x Elite Fire Lancer | 13x Paladin | 2362 / 2242 | -45.9 (1) | -37.8 (25) <br><sub>sd 5.6</sub> | **+8.1** |
| Heavy Camel Rider vs Hussar | 11x Heavy Camel Rider | 21x Hussar | 1595 / 1680 | -55.6 (1) | -46.7 (25) <br><sub>sd 3.7</sub> | **+8.9** |
| Heavy Camel Rider vs Elite Battle Elephant | 20x Heavy Camel Rider | 14x Elite Battle Elephant | 2900 / 2870 | -8.2 (4) <br><sub>-43.4..+12.7</sub> | -17.6 (25) <br><sub>sd 10.1</sub> | **-9.4** |
| Heavy Scorpion vs Elite Fire Lancer | 12x Heavy Scorpion | 21x Elite Fire Lancer | 2250 / 2362 | +61.5 (2) <br><sub>+58.8..+64.3</sub> | +52.0 (25) <br><sub>sd 6.1</sub> | **-9.5** |
| Elite Fire Lancer vs Hussar | 14x Elite Fire Lancer | 21x Hussar | 1575 / 1680 | -67.6 (1) | -57.7 (25) <br><sub>sd 3.5</sub> | **+9.9** |
| Elite Steppe Lancer vs Champion | 12x Elite Steppe Lancer | 21x Champion | 1560 / 1680 | +42.2 (4) <br><sub>+37.1..+47.5</sub> | +53.7 (25) <br><sub>sd 3.5</sub> | **+11.5** |
| Heavy Scorpion vs Elite Battle Elephant | 16x Heavy Scorpion | 14x Elite Battle Elephant | 3000 / 2870 | +63.1 (3) <br><sub>+61.2..+64.1</sub> | +51.4 (25) <br><sub>sd 8.4</sub> | **-11.7** |
| Halberdier vs Hussar | 21x Halberdier | 15x Hussar | 1260 / 1200 | -83.2 (1) | -70.3 (25) <br><sub>sd 2.7</sub> | **+12.9** |
| Heavy Scorpion vs Champion | 8x Heavy Scorpion | 21x Champion | 1500 / 1680 | +73.6 (3) <br><sub>+61.2..+87.5</sub> | +57.7 (25) <br><sub>sd 4.4</sub> | **-15.8** |
| Paladin vs Champion | 9x Paladin | 21x Champion | 1552 / 1680 | -0.2 (4) <br><sub>-21.2..+21.9</sub> | +15.7 (25) <br><sub>sd 13.5</sub> | **+15.8** ! |
| Paladin vs Elite Steppe Lancer | 15x Paladin | 21x Elite Steppe Lancer | 2588 / 2730 | -16.1 (12) <br><sub>-31.5..+17.9</sub> | -33.6 (25) <br><sub>sd 6.9</sub> | **-17.5** |
| Siege Onager vs Hussar | 4x Siege Onager | 21x Hussar | 1450 / 1680 | +38.5 (2) <br><sub>+36.6..+40.3</sub> | +57.6 (25) <br><sub>sd 13.9</sub> | **+19.1** |
| Siege Onager vs Elite Fire Lancer | 6x Siege Onager | 21x Elite Fire Lancer | 2175 / 2362 | +56.1 (1) | +35.9 (25) <br><sub>sd 9.7</sub> | **-20.2** |
| Elite Steppe Lancer vs Hussar | 12x Elite Steppe Lancer | 21x Hussar | 1560 / 1680 | +21.3 (4) <br><sub>+5.3..+32.6</sub> | +42.7 (25) <br><sub>sd 6.1</sub> | **+21.4** |
| Siege Onager vs Heavy Camel Rider | 8x Siege Onager | 20x Heavy Camel Rider | 2900 / 2900 | +62.8 (2) <br><sub>+61.5..+64.1</sub> | +38.8 (25) <br><sub>sd 20.7</sub> | **-24.0** |
| Siege Onager vs Champion | 4x Siege Onager | 21x Champion | 1450 / 1680 | +36.8 (1) | +61.9 (25) <br><sub>sd 5.7</sub> | **+25.1** |
| Champion vs Paladin | 21x Champion | 9x Paladin | 1680 / 1552 | -28.5 (3) <br><sub>-35.2..-19.0</sub> | -1.6 (25) <br><sub>sd 10.3</sub> | **+26.9** |
| Siege Onager vs Elite Steppe Lancer | 7x Siege Onager | 21x Elite Steppe Lancer | 2538 / 2730 | +63.0 (1) | +33.7 (25) <br><sub>sd 7.8</sub> | **-29.3** |
| Siege Onager vs Halberdier | 3x Siege Onager | 21x Halberdier | 1088 / 1260 | +78.3 (2) <br><sub>+76.7..+79.9</sub> | +48.5 (25) <br><sub>sd 9.2</sub> | **-29.8** |
| Siege Onager vs Paladin | 8x Siege Onager | 17x Paladin | 2900 / 2932 | +33.7 (1) | +75.0 (25) <br><sub>sd 5.9</sub> | **+41.3** |
| Siege Onager vs Elite Battle Elephant | 7x Siege Onager | 14x Elite Battle Elephant | 2538 / 2870 | +14.7 (1) | +67.7 (25) <br><sub>sd 6.2</sub> | **+53.0** |

## Ranged vs ranged (order script UNMODELED) — 21 matchups

| matchup | side 2 buys | side 3 buys | weighted spend<br><sub>side 2 / side 3</sub> | tape mean (n) | sim mean (n) | delta |
|---|---|---|---:|---:|---:|---:|
| Elite Skirmisher vs Hand Cannoneer | 21x Elite Skirmisher | 10x Hand Cannoneer | 1260 / 1200 | -76.7 (1) | -76.2 (25) <br><sub>sd 3.0</sub> | **+0.5** |
| Elite Skirmisher vs Arbalester | 21x Elite Skirmisher | 13x Arbalester | 1260 / 1202 | -73.3 (1) | -74.0 (25) <br><sub>sd 1.5</sub> | **-0.7** |
| Arbalester vs Elite Skirmisher | 13x Arbalester | 21x Elite Skirmisher | 1202 / 1260 | +76.5 (1) | +77.8 (25) <br><sub>sd 2.0</sub> | **+1.3** |
| Arbalester vs Hand Cannoneer | 21x Arbalester | 16x Hand Cannoneer | 1942 / 1920 | -59.8 (1) | -62.0 (25) <br><sub>sd 2.8</sub> | **-2.2** |
| Elite Skirmisher vs Heavy Cav Archer | 21x Elite Skirmisher | 9x Heavy Cav Archer | 1260 / 1170 | -77.5 (2) <br><sub>-77.6..-77.4</sub> | -80.4 (25) <br><sub>sd 0.7</sub> | **-2.9** |
| Arbalester vs Siege Onager | 21x Arbalester | 5x Siege Onager | 1942 / 1812 | +22.3 (1) | +17.0 (25) <br><sub>sd 6.8</sub> | **-5.3** |
| Heavy Cav Archer vs Siege Onager | 21x Heavy Cav Archer | 7x Siege Onager | 2730 / 2538 | +57.3 (1) | +51.9 (25) <br><sub>sd 5.8</sub> | **-5.4** |
| Hand Cannoneer vs Heavy Cav Archer | 21x Hand Cannoneer | 19x Heavy Cav Archer | 2520 / 2470 | +56.7 (4) <br><sub>+51.8..+66.1</sub> | +48.1 (25) <br><sub>sd 3.1</sub> | **-8.6** |
| Heavy Scorpion vs Arbalester | 10x Heavy Scorpion | 21x Arbalester | 1875 / 1942 | +16.1 (4) <br><sub>+6.6..+25.0</sub> | +25.5 (25) <br><sub>sd 2.6</sub> | **+9.4** |
| Heavy Cav Archer vs Heavy Scorpion | 21x Heavy Cav Archer | 14x Heavy Scorpion | 2730 / 2625 | -12.0 (5) <br><sub>-23.4..+25.7</sub> | -2.4 (25) <br><sub>sd 11.0</sub> | **+9.6** |
| Heavy Scorpion vs Heavy Cav Archer | 14x Heavy Scorpion | 21x Heavy Cav Archer | 2625 / 2730 | +30.5 (4) <br><sub>+26.0..+35.0</sub> | +40.2 (25) <br><sub>sd 2.0</sub> | **+9.7** |
| Heavy Cav Archer vs Hand Cannoneer | 19x Heavy Cav Archer | 21x Hand Cannoneer | 2470 / 2520 | -32.2 (1) | -43.2 (25) <br><sub>sd 3.6</sub> | **-11.0** |
| Hand Cannoneer vs Heavy Scorpion | 21x Hand Cannoneer | 13x Heavy Scorpion | 2520 / 2438 | +44.7 (5) <br><sub>+37.3..+52.7</sub> | +33.4 (25) <br><sub>sd 9.8</sub> | **-11.3** |
| Hand Cannoneer vs Arbalester | 16x Hand Cannoneer | 21x Arbalester | 1920 / 1942 | +47.2 (1) | +62.5 (25) <br><sub>sd 2.9</sub> | **+15.3** |
| Hand Cannoneer vs Siege Onager | 21x Hand Cannoneer | 6x Siege Onager | 2520 / 2175 | +30.1 (2) <br><sub>+29.0..+31.2</sub> | +5.9 (25) <br><sub>sd 20.8</sub> | **-24.2** |
| Arbalester vs Heavy Scorpion | 21x Arbalester | 10x Heavy Scorpion | 1942 / 1875 | +44.4 (2) <br><sub>+38.0..+50.7</sub> | +19.3 (25) <br><sub>sd 5.6</sub> | **-25.0** |
| Heavy Cav Archer vs Arbalester | 14x Heavy Cav Archer | 21x Arbalester | 1820 / 1942 | +26.0 (4) <br><sub>+15.7..+33.3</sub> | -0.8 (25) <br><sub>sd 15.1</sub> | **-26.9** ! |
| Heavy Scorpion vs Siege Onager | 16x Heavy Scorpion | 8x Siege Onager | 3000 / 2900 | +53.8 (1) | +22.5 (25) <br><sub>sd 3.8</sub> | **-31.3** |
| Elite Skirmisher vs Heavy Scorpion | 21x Elite Skirmisher | 6x Heavy Scorpion | 1260 / 1125 | +69.8 (2) <br><sub>+68.9..+70.8</sub> | +32.0 (25) <br><sub>sd 4.9</sub> | **-37.9** |
| Arbalester vs Heavy Cav Archer | 21x Arbalester | 14x Heavy Cav Archer | 1942 / 1820 | +19.7 (5) <br><sub>+11.8..+31.1</sub> | -24.8 (25) <br><sub>sd 5.3</sub> | **-44.5** ! |
| Elite Skirmisher vs Siege Onager | 21x Elite Skirmisher | 3x Siege Onager | 1260 / 1088 | +78.3 (3) <br><sub>+77.6..+78.6</sub> | +19.7 (25) <br><sub>sd 1.5</sub> | **-58.6** |

## Winner disagreements

| matchup | category | purchase | tape mean | sim mean | sim side-3 win rate | tape side-3 win rate |
|---|---|---|---:|---:|---:|---:|
| Heavy Cav Archer vs Champion | kite | 12v21 | -36.5 | +15.8 | 76% | 7% |
| Arbalester vs Heavy Cav Archer | rvr* | 21v14 | +19.7 | -24.8 | 0% | 100% |
| Elite Skirmisher vs Heavy Camel Rider | kite | 21v8 | +39.8 | -2.0 | 57% | 100% |
| Heavy Cav Archer vs Arbalester | rvr* | 14v21 | +26.0 | -0.8 | 44% | 100% |
| Paladin vs Champion | waves | 9v21 | -0.2 | +15.7 | 84% | 50% |

## Largest deltas with the winner correct

| matchup | category | purchase | tape mean | sim mean | delta |
|---|---|---|---:|---:|---:|
| Hand Cannoneer vs Elite Battle Elephant | kite | 21v12 | +2.4 | +80.0 | +77.6 |
| Elite Skirmisher vs Siege Onager | rvr* | 21v3 | +78.3 | +19.7 | -58.6 |
| Hand Cannoneer vs Hussar | kite | 14v21 | +5.6 | +59.4 | +53.8 |
| Hand Cannoneer vs Elite Steppe Lancer | kite | 21v19 | +8.0 | +61.3 | +53.3 |
| Siege Onager vs Elite Battle Elephant | waves | 7v14 | +14.7 | +67.7 | +53.0 |
| Siege Onager vs Paladin | waves | 8v17 | +33.7 | +75.0 | +41.3 |
| Elite Skirmisher vs Heavy Scorpion | rvr* | 21v6 | +69.8 | +32.0 | -37.9 |
| Hand Cannoneer vs Paladin | kite | 21v14 | +15.4 | +53.2 | +37.8 |
| Arbalester vs Elite Steppe Lancer | kite | 21v14 | +9.2 | +42.4 | +33.2 |
| Heavy Scorpion vs Siege Onager | rvr* | 16v8 | +53.8 | +22.5 | -31.3 |
| Siege Onager vs Halberdier | waves | 3v21 | +78.3 | +48.5 | -29.8 |
| Siege Onager vs Elite Steppe Lancer | waves | 7v21 | +63.0 | +33.7 | -29.3 |
| Champion vs Paladin | waves | 21v9 | -28.5 | -1.6 | +26.9 |
| Arbalester vs Hussar | kite | 18v21 | +29.7 | +55.6 | +25.9 |
| Siege Onager vs Champion | waves | 4v21 | +36.8 | +61.9 | +25.1 |

## Per-unit bias

Every matchup contributes twice — once for each side — with the sign flipped so
that **+ means the unit is stronger in the sim than on tape**. A unit's number
mixes its own model with its opponents', so read it as a pointer, not a verdict.

| unit | matchups | mean bias | median bias |
|---|---:|---:|---:|
| Hussar | 13 | +14.1 | +9.9 |
| Elite Battle Elephant | 15 | +10.1 | +4.3 |
| Elite Skirmisher | 14 | +8.6 | +0.6 |
| Champion | 15 | +7.4 | +7.2 |
| Paladin | 16 | +7.0 | +3.1 |
| Heavy Scorpion | 15 | +0.2 | +5.4 |
| Elite Steppe Lancer | 14 | -0.4 | -5.2 |
| Arbalester | 17 | -0.6 | -0.7 |
| Halberdier | 13 | -2.8 | -2.5 |
| Heavy Camel Rider | 13 | -4.7 | -3.3 |
| Heavy Cav Archer | 16 | -5.1 | -5.8 |
| Elite Fire Lancer | 13 | -5.7 | -6.7 |
| Siege Onager | 13 | -12.3 | -19.1 |
| Hand Cannoneer | 15 | -16.8 | -11.0 |

## What the residuals point at

1. **Hand Cannoneer is the largest single bias, and it is entirely a kiting
   problem.** Split by category its bias is **-33.5 across the 8 kite matchups**
   but **+2.3 across the 7 ranged-vs-ranged ones**, where it simply stands and
   shoots. The 75%-accuracy + half-damage-stray damage model is therefore *not*
   implicated; the constructed kite beat is. Within the kite group the deficit
   also tracks fight length — small against champions and halberdiers (-12, -10),
   huge against battle elephants and hussars (-78, -54) — which is what a wrong
   beat looks like as the error compounds over cycles. A hand-cannoneer kiting
   tape would close it.
2. **Siege Onager is the second-largest bias (-12.3) and it is two-signed.** In the
   native-waves group it is too weak against champion, hussar, paladin and battle
   elephant (-19 to -53) and too strong against halberdier, steppe lancer, fire
   lancer and camel (+20 to +30), with no monotone in count, HP or unit class —
   so this is not a flat damage error. The remaining -25.0 comes from the
   ranged-vs-ranged rows, which have no order script at all. Both need a siege
   tape column; today's blast model was measured against mangonel-class evidence
   only, and it fixed the winners without fixing the magnitudes.
3. **Elite Skirmisher vs Heavy Camel Rider** remains the one matchup whose winner
   is wrong for a known, measured reason (the kiter flow deficit) — see the
   diagnosis recorded with the camel work; it is the open item.
4. **Heavy Cav Archer vs Champion** is calibrated separately in its own tape
   column and is left as-is here.
5. **Paladin vs Champion** is a genuine knife's edge: the tape itself splits 50/50
   across its repeats (-21.2 to +21.9), so a sign disagreement there carries
   little information.

## Runs that did not resolve

A run is unresolved when neither side is wiped within the 9000-tick cap
(600 s). Those runs are dropped from the mean rather than scored as a draw.

| matchup | resolved | unresolved |
|---|---:|---:|
| Elite Skirmisher vs Heavy Camel Rider | 23 | 2 |
| Heavy Cav Archer vs Paladin | 24 | 1 |

## Reproducing

Per-matchup data, including all 25 raw sim samples and every tape repeat, is in
[`data/standard_units_2026-08-06.json`](data/standard_units_2026-08-06.json).

The run is: derive counts and orders from the rules above -> build each roster
from the recorded start positions -> 25 runs per matchup under
`AOE2X_EXP_ENGAGEMENT=pursuit AOE2X_EXP_ORDERS=1`, shuffling only acquisition
rank from a fixed seed -> pool tape repeats per scenario -> subtract the means.

Companion documents: [`STANDARD_UNITS_GAP_REPORT_2026-08-06.md`](STANDARD_UNITS_GAP_REPORT_2026-08-06.md) is the earlier blind evaluation of the
same archive, scored differently (median of 5 runs vs the tape's min-max band).
It answers "is the sim inside the tape's spread?"; this document answers "how far
apart are the two averages?" Neither supersedes the other.


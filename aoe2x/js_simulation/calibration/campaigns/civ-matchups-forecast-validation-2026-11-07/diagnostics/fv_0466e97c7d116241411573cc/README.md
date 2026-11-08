# Exhausted Cuman Elite Skirmisher / Malay Light Cavalry

Job `fv_0466e97c7d116241411573cc`, counts 27 / 23, exhausted all four normal seed-0 watchdogs. No seed completed. The frozen role key `Malay|hussar` retains the actual mechanics upgrade Light Cavalry. All four saved timelines have long suffixes with unchanged survivors and HP: one skirmisher at 11 HP and sixteen cavalry at 777 combined HP. The suffixes contain 4, 18, 58 and 118 snapshots respectively. Every sampled survivor is idle with a null attack target.

Positions and pursuit targets continue changing. Eleven movement/pursuit/reservation/blocked counters grow while combat counters stay fixed. The longest constant-HP suffix has 118 distinct sampled position/action/target states. This is continuing movement/replanning without HP progress; it is not a fixed-position diagnosis. The exact cause and real-game outcome remain unknown.

No native winner, draw, review or correction is assigned. No simulation or replay was executed for this diagnosis. Keep this case blocked pending separate recovery review; no further retry, physics change or imported winner is authorized. The ordinary queue continues.

Source `819e95bb2ed89e3ff5619fcbcee8c5c75f868a92`, exact physical context, original evidence and all attempt-line/progress hashes are retained in `REVIEW.json`. Reproduce into a new directory:

```sh
python aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07/diagnostics/fv_0466e97c7d116241411573cc/analyze.py --output <new-directory>
```

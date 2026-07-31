# E1 — Engine kite geometry (engine-side measurement)

**Question.** The tape agent measured how real-game kiters move
(docs/calibration/e1_kite_orbit_tapes.md): tangential clockwise orbits,
tan/rad ≈ 1.77, radius held (r-slope −0.030 t/s), cornering rare (0.24).
This is the same board computed on the JS engine at CURRENT SHIPPED
DEFAULTS (no flag overrides), tapebox arena (walls at tiles 1.2 / 14.8),
tape first-frame spawns, seeds 1–3 per fight — is engine kiting radial,
how fast does it corner, and where do the kiters die?

Producer: `tools/simjs/dump_kite_tracks.mjs` (uncommitted; imports the same
loaders as calib_runner.mjs, samples every unit at 10 Hz, read-only).
Machine-readable metrics: `data/calibration/analysis/e1_kite_orbit_engine.json`.

## Conventions (identical to the tape board)

- Positions in tile coordinates (TapeBox.worldToTile), sampled at 10 Hz.
- **C** = midpoint of the two sides' unit centroids at the first frame.
- **θ(t)** = `atan2(ky − Cy, kx − Cx)` of the kiter side's alive-unit
  centroid, unwrapped. Positive Δθ = rotation from +x toward +y in tile
  space = **clockwise on the game screen** (same convention as the tape
  board; both agents use increasing atan2 in game tile coordinates).
- **sign cons** = fraction of non-overlapping 1 s windows whose Δθ carries
  the majority sign.
- **r(t)** = kiter-centroid distance from C; slope least-squares, tiles/s.
- **tan/rad** = Σ|tangential| / Σ|radial| of frame-to-frame kiter-centroid
  displacement about C. Extra engine-side splits: **free** = both frames >2
  tiles from every wall, **wall** = both frames within 2 tiles of a wall
  (separates true orbiting from wall-slide).
- **t→wall** = seconds until the kiter centroid first comes within 2 tiles
  of a tapebox wall (walls at 1.2 / 14.8 on both axes — exact, not the
  tape board's bbox proxy).
- **corner** = fraction of the final 25 % of kiter-alive frames with the
  kiter centroid within 2 tiles of a wall.
- **min wd** = min distance from any alive kiter unit to a wall, any frame.
- **wall deaths** = fraction of kiter deaths within 2 tiles of a wall
  (pooled over the 3 seeds).
- **gap/reload** = mean change in a kiter unit's nearest-enemy distance
  between its own consecutive fires (volleys collapsed at 0.2 s; cycles
  filtered to 0.5–2× the fight's median inter-fire dt — the tape board's
  exact recipe). Same caveat as the tape board: this is NOT the C1 +0.383
  KPI (that one is per CHASER reload window after a landed hit).
- **reuse** = fraction of kiter-centroid frames within 2 tiles of an enemy
  centroid position from >3 s earlier.

**Corpus.** Same 78 fights as the tape board (kiter = hand_cannoneer /
arbalester / heavy_cav_archer vs a melee side; siege and ranged-vs-ranged
excluded; quarantined manifest entries dropped). 3 seeds each = 234 runs.

Two determinism notes, so nobody mistakes them for bugs:

- **Repeat recordings (`_rN`) produce identical engine rows.** The scripted
  scenario resets units to the same tile spots every round, so
  `spawns.json` is byte-identical across e.g. the three
  `arbalester__vs__elite_elephant` tapes — same spawns + same seed = the
  same deterministic fight. The tape rows differ per `_rN` (real-game
  variance); the engine rows cannot. Effectively the engine board has one
  distinct fight per (matchup, spawn-layout).
- **Some fights are seed-invariant.** With tape spawns there is no spawn
  jitter, so the rng is only consumed by in-combat probability rolls. Fights
  where no roll is ever consulted (e.g. `arbalester__vs__elite_elephant`:
  100 % accuracy against a slow, large target) are bit-identical across
  seeds 1–3; fights with real rolls (all hand-cannoneer fights at 65 %
  accuracy, and e.g. `champion__vs__arbalester`) differ per seed. Verified
  by hashing the track files. Per-seed triplets in the table reflect this.

## Per-fight metrics

Per-seed values (s1/s2/s3) for Δθ and gap/reload; other columns are the
3-seed mean. r s/m/e = kiter-centroid radius at start / midpoint / end.

| fight | kiter | enemy | dur s | Δθ rev s1/s2/s3 | sign cons | tan/rad | t/r free | t/r wall | r s/m/e | r slope | t→wall s | corner | min wd | wall deaths | gap/reload s1/s2/s3 | reuse |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arbalester__vs__elite_elephant | arbalester | elite_elephant | 43.7 | -0.16/-0.16/-0.16 | 0.81 | 1.53 | 0.39 | 1.87 | 4.1 / 7.2 / 8.3 | +0.084 | 4.9 | 1.00 | 0.00 | 1.00 | -0.35/-0.35/-0.35 | 0.48 |
| arbalester__vs__elite_elephant_r2 | arbalester | elite_elephant | 43.7 | -0.16/-0.16/-0.16 | 0.81 | 1.53 | 0.39 | 1.87 | 4.1 / 7.2 / 8.3 | +0.084 | 4.9 | 1.00 | 0.00 | 1.00 | -0.35/-0.35/-0.35 | 0.48 |
| arbalester__vs__elite_elephant_r3 | arbalester | elite_elephant | 43.7 | -0.16/-0.16/-0.16 | 0.81 | 1.53 | 0.39 | 1.87 | 4.1 / 7.2 / 8.3 | +0.084 | 4.9 | 1.00 | 0.00 | 1.00 | -0.35/-0.35/-0.35 | 0.48 |
| arbalester__vs__elite_fire_lancer | arbalester | elite_fire_lancer | 33.2 | -0.09/-0.09/-0.09 | 0.52 | 1.47 | 0.47 | 1.68 | 3.9 / 7.9 / 6.1 | +0.053 | 3.3 | 1.00 | 0.00 | 0.67 | -0.31/-0.31/-0.31 | 0.52 |
| arbalester__vs__elite_steppe | arbalester | elite_steppe | 32.6 | +0.09/+0.09/+0.09 | 0.66 | 0.86 | 0.27 | 0.97 | 4.1 / 9.7 / 11.1 | +0.235 | 4.8 | 1.00 | 0.00 | 0.86 | -0.46/-0.46/-0.46 | 0.00 |
| arbalester__vs__elite_steppe_r2 | arbalester | elite_steppe | 32.6 | +0.09/+0.09/+0.09 | 0.66 | 0.86 | 0.27 | 0.97 | 4.1 / 9.7 / 11.1 | +0.235 | 4.8 | 1.00 | 0.00 | 0.86 | -0.46/-0.46/-0.46 | 0.00 |
| arbalester__vs__elite_steppe_r3 | arbalester | elite_steppe | 32.6 | +0.09/+0.09/+0.09 | 0.66 | 0.86 | 0.27 | 0.97 | 4.1 / 9.7 / 11.1 | +0.235 | 4.8 | 1.00 | 0.00 | 0.86 | -0.46/-0.46/-0.46 | 0.00 |
| arbalester__vs__elite_steppe_r4 | arbalester | elite_steppe | 32.6 | +0.09/+0.09/+0.09 | 0.66 | 0.86 | 0.27 | 0.97 | 4.1 / 9.7 / 11.1 | +0.235 | 4.8 | 1.00 | 0.00 | 0.86 | -0.46/-0.46/-0.46 | 0.00 |
| arbalester__vs__elite_steppe_r5 | arbalester | elite_steppe | 32.6 | +0.09/+0.09/+0.09 | 0.66 | 0.86 | 0.27 | 0.97 | 4.1 / 9.7 / 11.1 | +0.235 | 4.8 | 1.00 | 0.00 | 0.86 | -0.46/-0.46/-0.46 | 0.00 |
| arbalester__vs__elite_steppe_r6 | arbalester | elite_steppe | 32.6 | +0.09/+0.09/+0.09 | 0.66 | 0.86 | 0.27 | 0.97 | 4.1 / 9.7 / 11.1 | +0.235 | 4.8 | 1.00 | 0.00 | 0.86 | -0.46/-0.46/-0.46 | 0.00 |
| arbalester__vs__heavy_camel | arbalester | heavy_camel | 34.9 | +0.09/+0.09/+0.09 | 0.74 | 0.95 | 0.34 | 1.07 | 4.1 / 9.5 / 10.3 | +0.199 | 4.9 | 1.00 | 0.00 | 0.89 | -0.32/-0.32/-0.32 | 0.43 |
| arbalester__vs__hussar | arbalester | hussar | 37.3 | +0.09/+0.09/+0.09 | 0.68 | 1.02 | 0.53 | 1.12 | 3.8 / 8.2 / 10.5 | +0.188 | 4.8 | 1.00 | 0.00 | 0.94 | -0.41/-0.41/-0.41 | 0.33 |
| arbalester__vs__paladin | arbalester | paladin | 35.9 | +0.08/+0.08/+0.08 | 0.74 | 0.81 | 0.30 | 0.92 | 4.2 / 9.1 / 11.3 | +0.216 | 5.0 | 1.00 | 0.00 | 0.86 | -0.54/-0.54/-0.54 | 0.33 |
| arbalester__vs__paladin_r2 | arbalester | paladin | 35.9 | +0.08/+0.08/+0.08 | 0.74 | 0.81 | 0.30 | 0.92 | 4.2 / 9.1 / 11.3 | +0.216 | 5.0 | 1.00 | 0.00 | 0.86 | -0.54/-0.54/-0.54 | 0.33 |
| arbalester__vs__paladin_r3 | arbalester | paladin | 35.9 | +0.08/+0.08/+0.08 | 0.74 | 0.81 | 0.30 | 0.92 | 4.2 / 9.1 / 11.3 | +0.216 | 5.0 | 1.00 | 0.00 | 0.86 | -0.54/-0.54/-0.54 | 0.33 |
| champion__vs__arbalester | arbalester | champion | 30.0 | -0.06/-0.06/-0.06 | 0.53 | 1.46 | 0.46 | 1.74 | 3.8 / 7.4 / 6.4 | +0.086 | 5.0 | 1.00 | 0.00 | 1.00 | -0.26/-0.26/-0.26 | 0.51 |
| champion__vs__arbalester_r2 | arbalester | champion | 30.0 | -0.06/-0.06/-0.06 | 0.53 | 1.46 | 0.46 | 1.74 | 3.8 / 7.4 / 6.4 | +0.086 | 5.0 | 1.00 | 0.00 | 1.00 | -0.26/-0.26/-0.26 | 0.51 |
| champion__vs__arbalester_r3 | arbalester | champion | 30.0 | -0.06/-0.06/-0.06 | 0.53 | 1.46 | 0.46 | 1.74 | 3.8 / 7.4 / 6.4 | +0.086 | 5.0 | 1.00 | 0.00 | 1.00 | -0.26/-0.26/-0.26 | 0.51 |
| champion__vs__arbalester_r4 | arbalester | champion | 30.0 | -0.06/-0.06/-0.06 | 0.53 | 1.46 | 0.46 | 1.74 | 3.8 / 7.4 / 6.4 | +0.086 | 5.0 | 1.00 | 0.00 | 1.00 | -0.26/-0.26/-0.26 | 0.51 |
| champion__vs__arbalester_r5 | arbalester | champion | 30.0 | -0.06/-0.06/-0.06 | 0.53 | 1.46 | 0.46 | 1.74 | 3.8 / 7.4 / 6.4 | +0.086 | 5.0 | 1.00 | 0.00 | 1.00 | -0.26/-0.26/-0.26 | 0.51 |
| champion__vs__arbalester_r6 | arbalester | champion | 30.0 | -0.06/-0.06/-0.06 | 0.53 | 1.46 | 0.46 | 1.74 | 3.8 / 7.4 / 6.4 | +0.086 | 5.0 | 1.00 | 0.00 | 1.00 | -0.26/-0.26/-0.26 | 0.51 |
| elite_steppe__vs__arbalester | arbalester | elite_steppe | 32.6 | +0.09/+0.09/+0.09 | 0.66 | 0.86 | 0.27 | 0.97 | 4.1 / 9.7 / 11.1 | +0.235 | 4.8 | 1.00 | 0.00 | 0.86 | -0.46/-0.46/-0.46 | 0.00 |
| halberdier__vs__arbalester | arbalester | halberdier | 19.7 | -0.09/-0.09/-0.09 | 0.74 | 1.25 | 0.27 | 1.88 | 3.8 / 6.8 / 6.9 | +0.156 | 4.7 | 1.00 | 0.00 | -- | -0.39/-0.39/-0.39 | 0.26 |
| champion__vs__hand_cannoneer | hand_cannoneer | champion | 28.4 | -0.04/-0.16/-0.14 | 0.65 | 1.50 | 0.31 | 1.82 | 3.9 / 7.4 / 7.5 | +0.107 | 3.2 | 1.00 | 0.00 | 1.00 | -0.52/-0.79/-0.72 | 0.28 |
| elite_fire_lancer__vs__hand_cannoneer | hand_cannoneer | elite_fire_lancer | 26.0 | +0.09/-0.03/+0.09 | 0.64 | 1.07 | 0.37 | 1.23 | 3.8 / 8.0 / 8.5 | +0.200 | 3.0 | 1.00 | 0.00 | 0.65 | -0.71/-0.81/-0.76 | 0.36 |
| halberdier__vs__hand_cannoneer | hand_cannoneer | halberdier | 27.4 | -0.10/+0.09/-0.14 | 0.69 | 1.33 | 0.42 | 1.66 | 3.8 / 7.3 / 8.5 | +0.153 | 3.4 | 1.00 | 0.00 | 1.00 | -0.74/-0.71/-0.63 | 0.33 |
| hand_cannoneer__vs__elite_elephant | hand_cannoneer | elite_elephant | 57.4 | +0.09/-0.15/+0.07 | 0.60 | 1.37 | 0.22 | 1.55 | 4.2 / 7.6 / 9.9 | +0.082 | 3.4 | 1.00 | 0.00 | 1.00 | -0.38/-0.46/-0.68 | 0.62 |
| hand_cannoneer__vs__elite_elephant_r2 | hand_cannoneer | elite_elephant | 57.4 | +0.09/-0.15/+0.07 | 0.60 | 1.37 | 0.22 | 1.55 | 4.2 / 7.6 / 9.9 | +0.082 | 3.4 | 1.00 | 0.00 | 1.00 | -0.38/-0.46/-0.68 | 0.62 |
| hand_cannoneer__vs__elite_steppe | hand_cannoneer | elite_steppe | 27.4 | +0.10/+0.10/+0.10 | 0.67 | 0.98 | 0.38 | 1.09 | 4.0 / 9.4 / 10.9 | +0.275 | 3.3 | 1.00 | 0.00 | 0.86 | -1.16/-1.11/-1.11 | 0.01 |
| hand_cannoneer__vs__heavy_camel | hand_cannoneer | heavy_camel | 52.8 | +0.31/+0.30/+0.28 | 0.85 | 1.73 | 0.41 | 1.90 | 3.9 / 10.0 / 9.6 | +0.067 | 3.3 | 1.00 | 0.00 | 1.00 | -0.53/-0.52/-0.45 | 0.38 |
| hand_cannoneer__vs__heavy_camel_r2 | hand_cannoneer | heavy_camel | 52.8 | +0.31/+0.30/+0.28 | 0.85 | 1.73 | 0.41 | 1.90 | 3.9 / 10.0 / 9.6 | +0.067 | 3.3 | 1.00 | 0.00 | 1.00 | -0.53/-0.52/-0.45 | 0.38 |
| hand_cannoneer__vs__heavy_camel_r3 | hand_cannoneer | heavy_camel | 52.8 | +0.31/+0.30/+0.28 | 0.85 | 1.73 | 0.41 | 1.90 | 3.9 / 10.0 / 9.6 | +0.067 | 3.3 | 1.00 | 0.00 | 1.00 | -0.53/-0.52/-0.45 | 0.38 |
| hand_cannoneer__vs__heavy_camel_r4 | hand_cannoneer | heavy_camel | 52.8 | +0.31/+0.30/+0.28 | 0.85 | 1.73 | 0.41 | 1.90 | 3.9 / 10.0 / 9.6 | +0.067 | 3.3 | 1.00 | 0.00 | 1.00 | -0.53/-0.52/-0.45 | 0.38 |
| hand_cannoneer__vs__heavy_camel_r5 | hand_cannoneer | heavy_camel | 52.8 | +0.31/+0.30/+0.28 | 0.85 | 1.73 | 0.41 | 1.90 | 3.9 / 10.0 / 9.6 | +0.067 | 3.3 | 1.00 | 0.00 | 1.00 | -0.53/-0.52/-0.45 | 0.38 |
| hand_cannoneer__vs__heavy_camel_r6 | hand_cannoneer | heavy_camel | 52.8 | +0.31/+0.30/+0.28 | 0.85 | 1.73 | 0.41 | 1.90 | 3.9 / 10.0 / 9.6 | +0.067 | 3.3 | 1.00 | 0.00 | 1.00 | -0.53/-0.52/-0.45 | 0.38 |
| hand_cannoneer__vs__hussar | hand_cannoneer | hussar | 39.3 | +0.09/+0.09/+0.09 | 0.67 | 0.91 | 0.29 | 1.02 | 3.9 / 9.8 / 10.6 | +0.154 | 3.1 | 1.00 | 0.00 | 1.00 | -0.79/-0.80/-0.87 | 0.57 |
| hand_cannoneer__vs__hussar_r2 | hand_cannoneer | hussar | 39.3 | +0.09/+0.09/+0.09 | 0.67 | 0.91 | 0.29 | 1.02 | 3.9 / 9.8 / 10.6 | +0.154 | 3.1 | 1.00 | 0.00 | 1.00 | -0.79/-0.80/-0.87 | 0.57 |
| hand_cannoneer__vs__hussar_r3 | hand_cannoneer | hussar | 39.3 | +0.09/+0.09/+0.09 | 0.67 | 0.91 | 0.29 | 1.02 | 3.9 / 9.8 / 10.6 | +0.154 | 3.1 | 1.00 | 0.00 | 1.00 | -0.79/-0.80/-0.87 | 0.57 |
| hand_cannoneer__vs__hussar_r4 | hand_cannoneer | hussar | 39.3 | +0.09/+0.09/+0.09 | 0.67 | 0.91 | 0.29 | 1.02 | 3.9 / 9.8 / 10.6 | +0.154 | 3.1 | 1.00 | 0.00 | 1.00 | -0.79/-0.80/-0.87 | 0.57 |
| hand_cannoneer__vs__hussar_r5 | hand_cannoneer | hussar | 39.3 | +0.09/+0.09/+0.09 | 0.67 | 0.91 | 0.29 | 1.02 | 3.9 / 9.8 / 10.6 | +0.154 | 3.1 | 1.00 | 0.00 | 1.00 | -0.79/-0.80/-0.87 | 0.57 |
| hand_cannoneer__vs__hussar_r6 | hand_cannoneer | hussar | 39.3 | +0.09/+0.09/+0.09 | 0.67 | 0.91 | 0.29 | 1.02 | 3.9 / 9.8 / 10.6 | +0.154 | 3.1 | 1.00 | 0.00 | 1.00 | -0.79/-0.80/-0.87 | 0.57 |
| hand_cannoneer__vs__paladin | hand_cannoneer | paladin | 34.4 | +0.09/+0.09/+0.09 | 0.67 | 0.93 | 0.34 | 1.05 | 4.1 / 10.3 / 11.1 | +0.209 | 3.3 | 1.00 | 0.00 | 1.00 | -1.04/-1.05/-1.16 | 0.50 |
| hand_cannoneer__vs__paladin_r2 | hand_cannoneer | paladin | 34.4 | +0.09/+0.09/+0.09 | 0.67 | 0.93 | 0.34 | 1.05 | 4.1 / 10.3 / 11.1 | +0.209 | 3.3 | 1.00 | 0.00 | 1.00 | -1.04/-1.05/-1.16 | 0.50 |
| hand_cannoneer__vs__paladin_r3 | hand_cannoneer | paladin | 34.4 | +0.09/+0.09/+0.09 | 0.67 | 0.93 | 0.34 | 1.05 | 4.1 / 10.3 / 11.1 | +0.209 | 3.3 | 1.00 | 0.00 | 1.00 | -1.04/-1.05/-1.16 | 0.50 |
| hand_cannoneer__vs__paladin_r4 | hand_cannoneer | paladin | 34.4 | +0.09/+0.09/+0.09 | 0.67 | 0.93 | 0.34 | 1.05 | 4.1 / 10.3 / 11.1 | +0.209 | 3.3 | 1.00 | 0.00 | 1.00 | -1.04/-1.05/-1.16 | 0.50 |
| hand_cannoneer__vs__paladin_r5 | hand_cannoneer | paladin | 34.4 | +0.09/+0.09/+0.09 | 0.67 | 0.93 | 0.34 | 1.05 | 4.1 / 10.3 / 11.1 | +0.209 | 3.3 | 1.00 | 0.00 | 1.00 | -1.04/-1.05/-1.16 | 0.50 |
| hand_cannoneer__vs__paladin_r6 | hand_cannoneer | paladin | 34.4 | +0.09/+0.09/+0.09 | 0.67 | 0.93 | 0.34 | 1.05 | 4.1 / 10.3 / 11.1 | +0.209 | 3.3 | 1.00 | 0.00 | 1.00 | -1.04/-1.05/-1.16 | 0.50 |
| champion__vs__heavy_cav_archer | heavy_cav_archer | champion | 53.7 | +0.20/+0.20/+0.20 | 0.57 | 1.21 | 1.52 | 0.92 | 3.8 / 8.6 / 4.9 | +0.044 | 16.3 | 0.23 | 0.00 | 0.60 | -0.21/-0.21/-0.21 | 0.43 |
| champion__vs__heavy_cav_archer_r2 | heavy_cav_archer | champion | 53.7 | +0.20/+0.20/+0.20 | 0.57 | 1.21 | 1.52 | 0.92 | 3.8 / 8.6 / 4.9 | +0.044 | 16.3 | 0.23 | 0.00 | 0.60 | -0.21/-0.21/-0.21 | 0.43 |
| champion__vs__heavy_cav_archer_r3 | heavy_cav_archer | champion | 53.7 | +0.20/+0.20/+0.20 | 0.57 | 1.21 | 1.52 | 0.92 | 3.8 / 8.6 / 4.9 | +0.044 | 16.3 | 0.23 | 0.00 | 0.60 | -0.21/-0.21/-0.21 | 0.43 |
| champion__vs__heavy_cav_archer_r4 | heavy_cav_archer | champion | 53.7 | +0.20/+0.20/+0.20 | 0.57 | 1.21 | 1.52 | 0.92 | 3.8 / 8.6 / 4.9 | +0.044 | 16.3 | 0.23 | 0.00 | 0.60 | -0.21/-0.21/-0.21 | 0.43 |
| champion__vs__heavy_cav_archer_r5 | heavy_cav_archer | champion | 53.7 | +0.20/+0.20/+0.20 | 0.57 | 1.21 | 1.52 | 0.92 | 3.8 / 8.6 / 4.9 | +0.044 | 16.3 | 0.23 | 0.00 | 0.60 | -0.21/-0.21/-0.21 | 0.43 |
| champion__vs__heavy_cav_archer_r6 | heavy_cav_archer | champion | 53.7 | +0.20/+0.20/+0.20 | 0.57 | 1.21 | 1.52 | 0.92 | 3.8 / 8.6 / 4.9 | +0.044 | 16.3 | 0.23 | 0.00 | 0.60 | -0.21/-0.21/-0.21 | 0.43 |
| champion__vs__heavy_cav_archer_r7 | heavy_cav_archer | champion | 53.7 | +0.20/+0.20/+0.20 | 0.57 | 1.21 | 1.52 | 0.92 | 3.8 / 8.6 / 4.9 | +0.044 | 16.3 | 0.23 | 0.00 | 0.60 | -0.21/-0.21/-0.21 | 0.43 |
| champion__vs__heavy_cav_archer_r8 | heavy_cav_archer | champion | 53.7 | +0.20/+0.20/+0.20 | 0.57 | 1.21 | 1.52 | 0.92 | 3.8 / 8.6 / 4.9 | +0.044 | 16.3 | 0.23 | 0.00 | 0.60 | -0.21/-0.21/-0.21 | 0.43 |
| champion__vs__heavy_cav_archer_r9 | heavy_cav_archer | champion | 53.7 | +0.20/+0.20/+0.20 | 0.57 | 1.21 | 1.52 | 0.92 | 3.8 / 8.6 / 4.9 | +0.044 | 16.3 | 0.23 | 0.00 | 0.60 | -0.21/-0.21/-0.21 | 0.43 |
| elite_fire_lancer__vs__heavy_cav_archer | heavy_cav_archer | elite_fire_lancer | 25.5 | +0.30/+0.30/+0.30 | 0.92 | 2.88 | 2.74 | 8.38 | 3.8 / 5.8 / 5.5 | +0.080 | 16.3 | 0.00 | 1.26 | 0.11 | -0.58/-0.58/-0.58 | 0.10 |
| halberdier__vs__heavy_cav_archer | heavy_cav_archer | halberdier | 22.6 | +0.26/+0.26/+0.26 | 0.91 | 2.18 | 2.30 | 2.03 | 4.0 / 5.6 / 8.5 | +0.219 | 12.8 | 1.00 | 0.00 | 0.56 | -0.62/-0.62/-0.62 | 0.06 |
| halberdier__vs__heavy_cav_archer_r2 | heavy_cav_archer | halberdier | 22.6 | +0.26/+0.26/+0.26 | 0.91 | 2.18 | 2.30 | 2.03 | 4.0 / 5.6 / 8.5 | +0.219 | 12.8 | 1.00 | 0.00 | 0.56 | -0.62/-0.62/-0.62 | 0.06 |
| halberdier__vs__heavy_cav_archer_r3 | heavy_cav_archer | halberdier | 22.6 | +0.26/+0.26/+0.26 | 0.91 | 2.18 | 2.30 | 2.03 | 4.0 / 5.6 / 8.5 | +0.219 | 12.8 | 1.00 | 0.00 | 0.56 | -0.62/-0.62/-0.62 | 0.06 |
| halberdier__vs__heavy_cav_archer_r4 | heavy_cav_archer | halberdier | 22.6 | +0.26/+0.26/+0.26 | 0.91 | 2.18 | 2.30 | 2.03 | 4.0 / 5.6 / 8.5 | +0.219 | 12.8 | 1.00 | 0.00 | 0.56 | -0.62/-0.62/-0.62 | 0.06 |
| halberdier__vs__heavy_cav_archer_r5 | heavy_cav_archer | halberdier | 22.6 | +0.26/+0.26/+0.26 | 0.91 | 2.18 | 2.30 | 2.03 | 4.0 / 5.6 / 8.5 | +0.219 | 12.8 | 1.00 | 0.00 | 0.56 | -0.62/-0.62/-0.62 | 0.06 |
| halberdier__vs__heavy_cav_archer_r6 | heavy_cav_archer | halberdier | 22.6 | +0.26/+0.26/+0.26 | 0.91 | 2.18 | 2.30 | 2.03 | 4.0 / 5.6 / 8.5 | +0.219 | 12.8 | 1.00 | 0.00 | 0.56 | -0.62/-0.62/-0.62 | 0.06 |
| heavy_cav_archer__vs__elite_elephant | heavy_cav_archer | elite_elephant | 58.0 | +0.15/+0.15/+0.15 | 0.57 | 1.60 | 0.73 | 2.00 | 4.1 / 7.0 / 9.1 | +0.079 | 12.5 | 1.00 | 0.00 | 0.95 | -0.23/-0.23/-0.23 | 0.48 |
| heavy_cav_archer__vs__elite_steppe | heavy_cav_archer | elite_steppe | 44.3 | +0.10/+0.10/+0.10 | 0.61 | 1.04 | 0.35 | 1.19 | 3.9 / 9.5 / 10.8 | +0.166 | 5.5 | 1.00 | 0.00 | 0.86 | -0.27/-0.27/-0.27 | 0.06 |
| heavy_cav_archer__vs__elite_steppe_r2 | heavy_cav_archer | elite_steppe | 44.3 | +0.10/+0.10/+0.10 | 0.61 | 1.04 | 0.35 | 1.19 | 3.9 / 9.5 / 10.8 | +0.166 | 5.5 | 1.00 | 0.00 | 0.86 | -0.27/-0.27/-0.27 | 0.06 |
| heavy_cav_archer__vs__elite_steppe_r3 | heavy_cav_archer | elite_steppe | 44.3 | +0.10/+0.10/+0.10 | 0.61 | 1.04 | 0.35 | 1.19 | 3.9 / 9.5 / 10.8 | +0.166 | 5.5 | 1.00 | 0.00 | 0.86 | -0.27/-0.27/-0.27 | 0.06 |
| heavy_cav_archer__vs__elite_steppe_r4 | heavy_cav_archer | elite_steppe | 44.3 | +0.10/+0.10/+0.10 | 0.61 | 1.04 | 0.35 | 1.19 | 3.9 / 9.5 / 10.8 | +0.166 | 5.5 | 1.00 | 0.00 | 0.86 | -0.27/-0.27/-0.27 | 0.06 |
| heavy_cav_archer__vs__elite_steppe_r5 | heavy_cav_archer | elite_steppe | 44.3 | +0.10/+0.10/+0.10 | 0.61 | 1.04 | 0.35 | 1.19 | 3.9 / 9.5 / 10.8 | +0.166 | 5.5 | 1.00 | 0.00 | 0.86 | -0.27/-0.27/-0.27 | 0.06 |
| heavy_cav_archer__vs__elite_steppe_r6 | heavy_cav_archer | elite_steppe | 44.3 | +0.10/+0.10/+0.10 | 0.61 | 1.04 | 0.35 | 1.19 | 3.9 / 9.5 / 10.8 | +0.166 | 5.5 | 1.00 | 0.00 | 0.86 | -0.27/-0.27/-0.27 | 0.06 |
| heavy_cav_archer__vs__heavy_camel | heavy_cav_archer | heavy_camel | 37.5 | +0.10/+0.10/+0.10 | 0.65 | 0.86 | 0.27 | 0.99 | 4.0 / 9.2 / 10.9 | +0.208 | 5.5 | 1.00 | 0.00 | 0.86 | -0.44/-0.44/-0.44 | 0.38 |
| heavy_cav_archer__vs__heavy_camel_r2 | heavy_cav_archer | heavy_camel | 37.5 | +0.10/+0.10/+0.10 | 0.65 | 0.86 | 0.27 | 0.99 | 4.0 / 9.2 / 10.9 | +0.208 | 5.5 | 1.00 | 0.00 | 0.86 | -0.44/-0.44/-0.44 | 0.38 |
| heavy_cav_archer__vs__heavy_camel_r3 | heavy_cav_archer | heavy_camel | 37.5 | +0.10/+0.10/+0.10 | 0.65 | 0.86 | 0.27 | 0.99 | 4.0 / 9.2 / 10.9 | +0.208 | 5.5 | 1.00 | 0.00 | 0.86 | -0.44/-0.44/-0.44 | 0.38 |
| heavy_cav_archer__vs__heavy_camel_r4 | heavy_cav_archer | heavy_camel | 37.5 | +0.10/+0.10/+0.10 | 0.65 | 0.86 | 0.27 | 0.99 | 4.0 / 9.2 / 10.9 | +0.208 | 5.5 | 1.00 | 0.00 | 0.86 | -0.44/-0.44/-0.44 | 0.38 |
| heavy_cav_archer__vs__heavy_camel_r5 | heavy_cav_archer | heavy_camel | 37.5 | +0.10/+0.10/+0.10 | 0.65 | 0.86 | 0.27 | 0.99 | 4.0 / 9.2 / 10.9 | +0.208 | 5.5 | 1.00 | 0.00 | 0.86 | -0.44/-0.44/-0.44 | 0.38 |
| heavy_cav_archer__vs__heavy_camel_r6 | heavy_cav_archer | heavy_camel | 37.5 | +0.10/+0.10/+0.10 | 0.65 | 0.86 | 0.27 | 0.99 | 4.0 / 9.2 / 10.9 | +0.208 | 5.5 | 1.00 | 0.00 | 0.86 | -0.44/-0.44/-0.44 | 0.38 |
| heavy_cav_archer__vs__hussar | heavy_cav_archer | hussar | 55.5 | +0.02/+0.02/+0.02 | 0.58 | 0.92 | 0.27 | 1.17 | 3.8 / 7.6 / 7.6 | +0.054 | 5.5 | 1.00 | 0.00 | 1.00 | -0.24/-0.24/-0.24 | 0.81 |
| heavy_cav_archer__vs__paladin | heavy_cav_archer | paladin | 66.3 | +0.09/+0.09/+0.09 | 0.64 | 0.83 | 0.44 | 0.93 | 4.0 / 10.2 / 11.0 | +0.099 | 7.4 | 1.00 | 0.00 | 0.86 | -0.25/-0.25/-0.25 | 0.62 |

## Aggregates by kiter type (fight-level means)

| kiter | n | Δθ rev | sign cons | tan/rad | t/r free | t/r wall | r slope | t→wall s | corner | min wd | wall deaths* | gap/reload | reuse | mean r s/m/e |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arbalester | 23 | +0.003 | 0.658 | 1.15 | 0.36 | 1.36 | +0.159 | 4.8 | 1.00 | 0.00 | 0.89 | -0.39 | 0.31 | 4.0 / 8.4 / 9.1 |
| hand_cannoneer | 24 | +0.120 | 0.709 | 1.21 | 0.34 | 1.36 | +0.145 | 3.2 | 1.00 | 0.00 | 0.99 | -0.78 | 0.46 | 4.0 / 9.5 / 10.1 |
| heavy_cav_archer | 31 | +0.164 | 0.672 | 1.34 | 1.14 | 1.49 | +0.138 | 10.7 | 0.74 | 0.04 | 0.75 | -0.36 | 0.29 | 3.9 / 8.2 / 8.3 |
| **all** | 78 | +0.103 | 0.679 | 1.25 | 0.66 | 1.41 | +0.146 | 6.7 | 0.90 | 0.02 | 0.86 | -0.50 | 0.35 | 3.9 / 8.7 / 9.1 |

\* wall deaths pooled over all kiter deaths in all seeds of the group.

## Engine vs tape, side by side (corpus means, same 78 matchups)

| metric | tape | engine | read |
|---|---|---|---|
| Δθ (revolutions about C) | +1.33 | +0.103 | engine barely rotates (13× less sweep) |
| sign consistency | 0.941 | 0.679 | tape is direction-locked; engine Δθ is drift, not orbit |
| tan/rad (whole fight) | 1.77 | 1.25 | see split below — engine number is wall-slide, not orbit |
| tan/rad, free phase (>2 t from walls) | n/a | 0.66 | radial-dominated retreat while room remains |
| r slope (tiles/s) | -0.030 | +0.146 | tape holds/tightens radius; engine drives OUTWARD to the wall |
| cornering (final 25 %) | 0.24 | 0.90 | engine ends fights pinned; tape does not |
| kiter deaths within 2 t of wall | n/a (tape kiters rarely die at walls) | 0.86 | engine kiters die against the wall |
| gap/reload (at-fire sampling) | -0.28 | -0.50 | engine loses ~2× more ground per reload cycle |
| reuse of enemy's old ground | 0.54 | 0.35 | engine never circles back over enemy ground as much |

## Verdict

**1. Engine kiting is radial, not tangential — the hypothesis is confirmed.**
While the kiter still has room (free phase, >2 tiles from every wall) the
displacement about C is radial-dominated: mean tan/rad = 0.66 (vs the tape's whole-fight 1.77). The
whole-fight engine ratio (1.25) LOOKS tangential but is an
artifact of wall-pinning: within 2 tiles of a wall the outward component is
clamped by the arena constraint, so what movement remains is forced
sideways (wall-phase tan/rad = 1.41). Rotation about C
is negligible either way: mean total sweep +0.103 revolutions
(median +0.09) vs the tape's +1.33; not one of the 78 fights reaches even
half a revolution (tape: 75/78 reach half, 46/78 a full circle), and the
sweep direction is unfixed (65/78 positive vs the tape's 78/78) with
mean sign consistency 0.68 vs the tape's 0.94 — the
small engine Δθ is noise around a radial flight line, not an orbit.
The one partial exception is heavy_cav_archer (free-phase tan/rad 1.14):
it outruns every chaser, so its dodging while free has some lateral
component — but its r-slope is still +0.138 t/s outward, it still corners
(t→wall 10.7 s, corner 0.74) and 75 % of its deaths are still at a wall;
arbalester and hand_cannoneer are flatly radial (free-phase 0.36 / 0.34).

**2. The engine kiter flees outward and corners fast.**
Mean r-slope is +0.146 tiles/s — positive (outward) in
78/78 fights — where the tape holds radius at −0.030 t/s (only 10/78
tapes drift outward at all). Radius runs 3.9 → 8.7 → 9.1 tiles (tape: 4.0 → 3.5 → 2.7). The kiter centroid first
touches the 2-tile wall band after a median 5.0 s (mean
6.7 s) — one reload-and-a-bit into the fight — and stays
there: 0.90 of final-quarter frames are within 2 tiles
of a wall (68/78 fights above 0.5, 68/78 at 1.00; tape mean 0.24).

**3. Kiters die against the wall.**
Min kiter-unit wall distance is ≤ 0.001 tiles in 77/78 fights — units
literally on the clamp line. Pooled over all seeds, 86% of kiter deaths happen
within 2 tiles of a wall. The kiting side wins a seed in only
27/78 fights.

**4. Per-reload gap: the engine kiter loses ground every cycle.**
Mean at-fire gap/reload = -0.497 tiles
(negative in 78/78 fights) vs the tape's −0.28 on the identical
metric. Note both boards' at-fire figures are negative by construction
(fights contract); the diagnostic is the DIFFERENCE — the engine loses
~0.22 tiles/cycle more than the tape, and the tape's escape-phase KPI
(+0.383 net gap per chaser reload) has no engine counterpart because the
engine kiter has no escape phase once pinned (0.35 reuse vs 0.54:
it never comes back over the enemy's old ground, it runs out of new ground).

**Bottom line.** Engine retreat is radial (free-phase tan/rad 0.66, outward r-slope +0.146),
reaches a wall in ~5 s, and converts the fight into a
wall-grind where 86% of kiter
deaths occur. To match the tapes the retreat bearing needs a dominant
tangential component about the fight centre with a fixed turn direction
(tape: clockwise on screen, sign consistency 0.94), holding radius rather
than growing it.

### Per-seed spread

Seeds agree closely: the per-seed Δθ and gap/reload triplets above rarely
differ by more than the fight-to-fight spread, and every corpus-level
conclusion holds per seed:
- seed 1: Δθ +0.11 rev, tan/rad 1.25, r-slope +0.144 t/s, corner 0.90, gap/reload -0.49
- seed 2: Δθ +0.10 rev, tan/rad 1.25, r-slope +0.144 t/s, corner 0.90, gap/reload -0.50
- seed 3: Δθ +0.10 rev, tan/rad 1.23, r-slope +0.150 t/s, corner 0.90, gap/reload -0.51


# E1 — Do tape kiters orbit tangentially? (tape-side measurement)

**Question.** The engine's kiters retreat radially, hit the arena wall, and get
pinned (net gap per reload 0.000 vs the tape's +0.383). Hypothesis from
watching fights: the scripted AI kites TANGENTIALLY — it orbits the middle of
the fight area (clockwise on screen, around the central obstruction) instead
of fleeing straight away, so it never runs out of room. This report measures
the tapes only; a parallel agent runs the identical metrics on the JS engine.

## Conventions (shared with the engine-side agent)

- Positions are game tile coordinates from the tape `units` channel (10 Hz).
- Reference center **C** = midpoint of the two sides' unit centroids at the
  first frame where both sides are present.
- **θ(t)** = `atan2(ky − Cy, kx − Cx)` of the kiting side's centroid, unwrapped.
  With the isometric screen mapping `sx = x − y`, `sy = (x + y)/2` (screen y
  down), increasing θ — counterclockwise in game-coord math convention — is
  **clockwise on the game screen**. All Δθ below use POSITIVE = clockwise on
  screen.
- **Sign consistency** = fraction of 1-second windows (10 frames) whose Δθ has
  the majority sign.
- **r(t)** = kiter-centroid distance from C; slope is least-squares, tiles/s.
- **tan/rad** = Σ|tangential| / Σ|radial| of the kiter centroid's
  frame-to-frame displacement about C.
- **corner** = fraction of the final 25 % of kiter-alive frames where the kiter
  centroid is within 2 tiles of the bounding box of ALL unit samples in the
  tape (usable-area proxy; mean bbox ≈ 10.7 × 11.0 tiles).
- **gap/reload** = mean change in a kiter unit's nearest-enemy distance between
  its own consecutive missile fires (multi-projectile volleys collapsed at
  0.2 s; inter-fire dt filtered to 0.5–2× the tape median). NOTE: this is NOT
  the C1 “+0.383” KPI — that one is net separation per CHASER reload window
  following a landed hit; this one samples at kiter fire times over the whole
  fight, including the closing phase. See §Reload-gap caveat.
- **reuse** = fraction of kiter-centroid frames within 2 tiles of some enemy
  centroid position from >3 s earlier (does the orbit pass through ground the
  enemy blob previously held?).

**Corpus.** All non-quarantined manifest fights where exactly one side is a
ranged non-siege kiter (hand_cannoneer, arbalester, heavy_cav_archer) against
a melee side (champion, halberdier, hussar, paladin, heavy_camel, elite_steppe,
elite_elephant, elite_fire_lancer). Siege and ranged-vs-ranged (incl. all
imp_elite_skirm pairings) excluded. **N = 78 tapes** (23 arbalester,
24 hand_cannoneer, 31 heavy_cav_archer as kiter). All 78 parsed cleanly.

## Per-tape metrics

r s/m/e = r at fight start / midpoint / last frame (tiles).

| tape | kiter | enemy | dur s | Δθ rev | sign cons | tan/rad | r s/m/e | r slope | corner | gap/reload | reuse |
|---|---|---|---|---|---|---|---|---|---|---|---|
| arbalester__vs__elite_elephant | arbalester | elite_elephant | 101.66 | +2.52 | 0.99 | 1.38 | 4.1 / 6.0 / 0.5 | -0.011 | 0.40 | -0.13 | 0.75 |
| arbalester__vs__elite_elephant_r2 | arbalester | elite_elephant | 102.4 | +1.49 | 0.94 | 1.20 | 4.1 / 6.3 / 0.7 | -0.006 | 0.46 | -0.10 | 0.76 |
| arbalester__vs__elite_elephant_r3 | arbalester | elite_elephant | 95.05 | +1.37 | 0.94 | 1.31 | 4.1 / 6.0 / 2.9 | -0.005 | 0.44 | -0.15 | 0.73 |
| arbalester__vs__elite_fire_lancer | arbalester | elite_fire_lancer | 49.65 | +0.81 | 0.97 | 1.83 | 3.9 / 2.7 / 1.1 | -0.104 | 0.00 | 0.03 | 0.53 |
| arbalester__vs__elite_steppe | arbalester | elite_steppe | 51.32 | +1.20 | 0.98 | 1.70 | 4.1 / 2.6 / 5.0 | -0.015 | 0.63 | -0.03 | 0.39 |
| arbalester__vs__elite_steppe_r2 | arbalester | elite_steppe | 46.56 | +1.12 | 0.91 | 1.20 | 4.1 / 3.5 / 5.3 | -0.047 | 0.00 | -0.09 | 0.55 |
| arbalester__vs__elite_steppe_r3 | arbalester | elite_steppe | 55.88 | +1.28 | 0.98 | 1.48 | 4.1 / 2.0 / 3.5 | -0.010 | 0.24 | -1.23 | 0.57 |
| arbalester__vs__elite_steppe_r4 | arbalester | elite_steppe | 53.67 | +1.26 | 0.98 | 1.65 | 4.1 / 2.5 / 4.7 | -0.008 | 0.48 | -0.26 | 0.53 |
| arbalester__vs__elite_steppe_r5 | arbalester | elite_steppe | 58.15 | +1.37 | 0.98 | 1.40 | 4.1 / 0.9 / 2.5 | -0.013 | 0.22 | -1.22 | 0.55 |
| arbalester__vs__elite_steppe_r6 | arbalester | elite_steppe | 60.16 | +1.35 | 0.98 | 1.48 | 4.1 / 1.4 / 2.7 | -0.012 | 0.49 | -0.71 | 0.54 |
| arbalester__vs__heavy_camel | arbalester | heavy_camel | 47.7 | +0.92 | 0.94 | 1.57 | 4.1 / 3.4 / 1.7 | -0.097 | 0.00 | -0.08 | 0.50 |
| arbalester__vs__hussar | arbalester | hussar | 64.48 | +1.41 | 0.95 | 2.02 | 3.9 / 1.7 / 2.8 | -0.004 | 0.00 | -0.18 | 0.58 |
| arbalester__vs__paladin | arbalester | paladin | 59.77 | +1.37 | 0.96 | 1.31 | 4.2 / 0.2 / 2.0 | -0.010 | 0.52 | -0.23 | 0.59 |
| arbalester__vs__paladin_r2 | arbalester | paladin | 61.7 | +1.42 | 0.97 | 1.26 | 4.2 / 0.5 / 0.6 | -0.016 | 0.32 | -0.23 | 0.50 |
| arbalester__vs__paladin_r3 | arbalester | paladin | 64.49 | +1.39 | 0.97 | 1.21 | 4.2 / 1.1 / 0.5 | -0.019 | 0.32 | -0.21 | 0.62 |
| champion__vs__arbalester | arbalester | champion | 46.56 | +0.58 | 0.88 | 2.15 | 3.9 / 4.3 / 0.8 | -0.098 | 0.00 | -0.19 | 0.40 |
| champion__vs__arbalester_r2 | arbalester | champion | 59.04 | +0.80 | 0.89 | 2.13 | 3.9 / 2.5 / 1.0 | -0.083 | 0.00 | -0.23 | 0.53 |
| champion__vs__arbalester_r3 | arbalester | champion | 51.66 | +0.78 | 0.91 | 2.02 | 3.9 / 2.8 / 1.3 | -0.085 | 0.00 | -0.23 | 0.50 |
| champion__vs__arbalester_r4 | arbalester | champion | 54.13 | +0.62 | 0.91 | 2.12 | 3.9 / 3.0 / 0.8 | -0.094 | 0.00 | -0.25 | 0.49 |
| champion__vs__arbalester_r5 | arbalester | champion | 45.42 | +0.55 | 0.91 | 2.20 | 3.9 / 4.9 / 1.0 | -0.091 | 0.00 | -0.26 | 0.37 |
| champion__vs__arbalester_r6 | arbalester | champion | 57.22 | +0.81 | 0.91 | 2.14 | 3.9 / 2.7 / 1.1 | -0.081 | 0.00 | -0.22 | 0.51 |
| elite_steppe__vs__arbalester | arbalester | elite_steppe | 71.14 | +1.19 | 0.98 | 1.54 | 4.1 / 1.6 / 5.5 | +0.019 | 1.00 | -0.18 | 0.67 |
| halberdier__vs__arbalester | arbalester | halberdier | 47.68 | +0.84 | 0.97 | 2.00 | 3.8 / 2.6 / 1.5 | -0.093 | 0.00 | 0.02 | 0.52 |
| champion__vs__hand_cannoneer | hand_cannoneer | champion | 49.73 | +1.01 | 0.91 | 2.22 | 3.9 / 2.2 / 3.8 | -0.020 | 1.00 | -0.62 | 0.58 |
| elite_fire_lancer__vs__hand_cannoneer | hand_cannoneer | elite_fire_lancer | 46.23 | +0.93 | 0.93 | 1.89 | 3.8 / 2.6 / 2.1 | -0.073 | 0.00 | -0.03 | 0.55 |
| halberdier__vs__hand_cannoneer | hand_cannoneer | halberdier | 53.67 | +1.18 | 0.97 | 2.14 | 3.8 / 1.7 / 5.0 | +0.019 | 1.00 | -0.65 | 0.48 |
| hand_cannoneer__vs__elite_elephant | hand_cannoneer | elite_elephant | 141.27 | +4.66 | 1.00 | 1.45 | 4.2 / 5.4 / 0.5 | -0.005 | 0.18 | -0.25 | 0.85 |
| hand_cannoneer__vs__elite_elephant_r2 | hand_cannoneer | elite_elephant | 117.2 | +4.02 | 0.98 | 1.48 | 4.2 / 0.9 / 3.5 | -0.011 | 0.23 | -0.21 | 0.81 |
| hand_cannoneer__vs__elite_steppe | hand_cannoneer | elite_steppe | 62.62 | +1.95 | 0.97 | 1.77 | 4.0 / 1.3 / 2.1 | -0.031 | 0.12 | -0.53 | 0.62 |
| hand_cannoneer__vs__heavy_camel | hand_cannoneer | heavy_camel | 64.93 | +1.16 | 0.98 | 1.70 | 3.9 / 1.7 / 5.5 | +0.027 | 1.00 | -0.39 | 0.64 |
| hand_cannoneer__vs__heavy_camel_r2 | hand_cannoneer | heavy_camel | 57.86 | +1.17 | 0.95 | 1.83 | 3.9 / 1.0 / 5.5 | +0.022 | 1.00 | -0.38 | 0.60 |
| hand_cannoneer__vs__heavy_camel_r3 | hand_cannoneer | heavy_camel | 59.85 | +1.21 | 0.95 | 1.74 | 3.9 / 1.5 / 5.2 | +0.024 | 1.00 | -0.34 | 0.65 |
| hand_cannoneer__vs__heavy_camel_r4 | hand_cannoneer | heavy_camel | 52.58 | +1.10 | 0.97 | 1.67 | 3.9 / 1.4 / 5.3 | +0.011 | 0.00 | -0.34 | 0.57 |
| hand_cannoneer__vs__heavy_camel_r5 | hand_cannoneer | heavy_camel | 55.79 | +1.14 | 0.97 | 1.61 | 3.9 / 0.9 / 5.4 | +0.027 | 1.00 | -0.38 | 0.63 |
| hand_cannoneer__vs__heavy_camel_r6 | hand_cannoneer | heavy_camel | 52.39 | +1.12 | 0.97 | 1.62 | 3.9 / 1.1 / 5.3 | +0.019 | 0.97 | -0.48 | 0.60 |
| hand_cannoneer__vs__hussar | hand_cannoneer | hussar | 107.78 | +3.13 | 0.96 | 2.16 | 3.9 / 1.9 / 5.1 | +0.004 | 0.47 | -0.27 | 0.81 |
| hand_cannoneer__vs__hussar_r2 | hand_cannoneer | hussar | 91.8 | +2.24 | 0.96 | 2.13 | 3.9 / 5.0 / 4.6 | +0.004 | 0.17 | -0.24 | 0.75 |
| hand_cannoneer__vs__hussar_r3 | hand_cannoneer | hussar | 82.74 | +2.58 | 0.96 | 2.17 | 3.9 / 5.0 / 1.1 | -0.008 | 0.29 | -0.31 | 0.75 |
| hand_cannoneer__vs__hussar_r4 | hand_cannoneer | hussar | 78.93 | +2.48 | 0.96 | 2.24 | 3.9 / 5.0 / 2.3 | -0.006 | 0.40 | -0.31 | 0.74 |
| hand_cannoneer__vs__hussar_r5 | hand_cannoneer | hussar | 78.19 | +2.31 | 0.95 | 2.15 | 3.9 / 4.9 / 3.3 | -0.005 | 0.07 | -0.30 | 0.74 |
| hand_cannoneer__vs__hussar_r6 | hand_cannoneer | hussar | 80.71 | +2.44 | 0.96 | 2.16 | 3.9 / 5.1 / 2.3 | -0.004 | 0.35 | -0.27 | 0.75 |
| hand_cannoneer__vs__paladin | hand_cannoneer | paladin | 101.91 | +2.45 | 0.99 | 1.57 | 4.1 / 3.7 / 2.0 | -0.018 | 0.03 | -0.23 | 0.78 |
| hand_cannoneer__vs__paladin_r2 | hand_cannoneer | paladin | 75.24 | +2.26 | 0.99 | 1.57 | 4.1 / 5.1 / 4.6 | -0.004 | 0.28 | -0.30 | 0.69 |
| hand_cannoneer__vs__paladin_r3 | hand_cannoneer | paladin | 80.88 | +2.53 | 0.99 | 1.55 | 4.1 / 5.7 / 1.1 | -0.011 | 0.48 | -0.47 | 0.73 |
| hand_cannoneer__vs__paladin_r4 | hand_cannoneer | paladin | 63.57 | +1.98 | 0.97 | 1.62 | 4.1 / 2.7 / 2.2 | -0.029 | 0.07 | -0.37 | 0.66 |
| hand_cannoneer__vs__paladin_r5 | hand_cannoneer | paladin | 69.13 | +2.09 | 0.98 | 1.56 | 4.1 / 3.8 / 5.3 | -0.020 | 0.01 | -0.44 | 0.69 |
| hand_cannoneer__vs__paladin_r6 | hand_cannoneer | paladin | 84.68 | +2.86 | 0.97 | 1.50 | 4.1 / 5.6 / 1.3 | -0.016 | 0.38 | -0.32 | 0.75 |
| champion__vs__heavy_cav_archer | heavy_cav_archer | champion | 74.45 | +1.15 | 0.90 | 2.18 | 3.8 / 4.2 / 5.1 | -0.021 | 0.02 | -0.18 | 0.41 |
| champion__vs__heavy_cav_archer_r2 | heavy_cav_archer | champion | 72.67 | +0.95 | 0.93 | 2.00 | 3.8 / 3.1 / 2.4 | -0.050 | 0.00 | -0.15 | 0.47 |
| champion__vs__heavy_cav_archer_r3 | heavy_cav_archer | champion | 76.64 | +1.05 | 0.92 | 1.88 | 3.8 / 2.6 / 4.5 | -0.017 | 0.85 | -0.19 | 0.51 |
| champion__vs__heavy_cav_archer_r4 | heavy_cav_archer | champion | 69.89 | +0.99 | 0.93 | 1.82 | 3.8 / 2.8 / 3.4 | -0.034 | 0.00 | -0.10 | 0.50 |
| champion__vs__heavy_cav_archer_r5 | heavy_cav_archer | champion | 98.11 | +1.26 | 0.95 | 2.17 | 3.8 / 1.7 / 4.5 | -0.003 | 0.00 | -0.17 | 0.60 |
| champion__vs__heavy_cav_archer_r6 | heavy_cav_archer | champion | 71.62 | +0.93 | 0.93 | 1.96 | 3.8 / 3.1 / 2.5 | -0.050 | 0.00 | -0.18 | 0.51 |
| champion__vs__heavy_cav_archer_r7 | heavy_cav_archer | champion | 77.78 | +1.02 | 0.92 | 1.92 | 3.8 / 2.5 / 4.0 | -0.019 | 1.00 | -0.18 | 0.55 |
| champion__vs__heavy_cav_archer_r8 | heavy_cav_archer | champion | 68.04 | +0.69 | 0.91 | 2.14 | 3.8 / 4.0 / 1.4 | -0.068 | 0.00 | -0.18 | 0.41 |
| champion__vs__heavy_cav_archer_r9 | heavy_cav_archer | champion | 65.23 | +0.87 | 0.93 | 2.10 | 3.8 / 4.0 / 2.3 | -0.058 | 0.00 | -0.15 | 0.41 |
| elite_fire_lancer__vs__heavy_cav_archer | heavy_cav_archer | elite_fire_lancer | 46.6 | +0.49 | 0.87 | 1.79 | 3.9 / 5.6 / 2.1 | -0.018 | 0.00 | -0.30 | 0.10 |
| halberdier__vs__heavy_cav_archer | heavy_cav_archer | halberdier | 41.85 | +0.59 | 0.94 | 1.99 | 4.0 / 5.1 / 1.7 | -0.049 | 0.00 | -0.35 | 0.44 |
| halberdier__vs__heavy_cav_archer_r2 | heavy_cav_archer | halberdier | 46.58 | +0.77 | 0.91 | 1.90 | 4.0 / 4.8 / 1.6 | -0.066 | 0.00 | -0.31 | 0.46 |
| halberdier__vs__heavy_cav_archer_r3 | heavy_cav_archer | halberdier | 33.95 | +0.35 | 0.92 | 1.95 | 4.0 / 5.2 / 3.2 | -0.009 | 0.02 | -0.36 | 0.36 |
| halberdier__vs__heavy_cav_archer_r4 | heavy_cav_archer | halberdier | 46.12 | +0.89 | 0.95 | 1.92 | 4.0 / 4.8 / 2.2 | -0.063 | 0.00 | -0.32 | 0.26 |
| halberdier__vs__heavy_cav_archer_r5 | heavy_cav_archer | halberdier | 40.4 | +0.63 | 0.88 | 2.00 | 4.0 / 4.8 / 1.6 | -0.062 | 0.00 | -0.38 | 0.24 |
| halberdier__vs__heavy_cav_archer_r6 | heavy_cav_archer | halberdier | 44.22 | +0.62 | 0.94 | 1.77 | 4.0 / 4.9 / 1.7 | -0.053 | 0.00 | -0.29 | 0.36 |
| heavy_cav_archer__vs__elite_elephant | heavy_cav_archer | elite_elephant | 97.18 | +1.80 | 0.95 | 1.72 | 4.1 / 1.5 / 1.4 | -0.019 | 0.16 | -0.09 | 0.65 |
| heavy_cav_archer__vs__elite_steppe | heavy_cav_archer | elite_steppe | 69.93 | +1.11 | 0.93 | 1.84 | 3.9 / 4.4 / 5.1 | -0.030 | 0.00 | -0.20 | 0.42 |
| heavy_cav_archer__vs__elite_steppe_r2 | heavy_cav_archer | elite_steppe | 60.75 | +0.95 | 0.94 | 1.91 | 3.9 / 5.1 / 1.8 | -0.061 | 0.00 | -0.18 | 0.30 |
| heavy_cav_archer__vs__elite_steppe_r3 | heavy_cav_archer | elite_steppe | 63.49 | +0.95 | 0.93 | 1.67 | 3.9 / 5.5 / 1.6 | -0.058 | 0.00 | -0.16 | 0.42 |
| heavy_cav_archer__vs__elite_steppe_r4 | heavy_cav_archer | elite_steppe | 59.96 | +0.82 | 0.92 | 1.68 | 3.9 / 5.8 / 1.8 | -0.056 | 0.01 | -0.24 | 0.32 |
| heavy_cav_archer__vs__elite_steppe_r5 | heavy_cav_archer | elite_steppe | 60.15 | +0.93 | 0.89 | 1.58 | 3.9 / 5.5 / 2.0 | -0.057 | 0.00 | -0.25 | 0.26 |
| heavy_cav_archer__vs__elite_steppe_r6 | heavy_cav_archer | elite_steppe | 74.73 | +1.15 | 0.92 | 1.78 | 3.9 / 3.1 / 5.2 | -0.021 | 0.00 | -0.20 | 0.54 |
| heavy_cav_archer__vs__heavy_camel | heavy_cav_archer | heavy_camel | 48.27 | +0.51 | 0.89 | 1.52 | 4.0 / 5.9 / 1.7 | -0.040 | 0.00 | -0.36 | 0.43 |
| heavy_cav_archer__vs__heavy_camel_r2 | heavy_cav_archer | heavy_camel | 49.66 | +0.64 | 0.93 | 1.46 | 4.0 / 6.0 / 0.4 | -0.065 | 0.00 | -0.32 | 0.32 |
| heavy_cav_archer__vs__heavy_camel_r3 | heavy_cav_archer | heavy_camel | 52.5 | +0.96 | 0.82 | 1.39 | 4.0 / 5.7 / 1.7 | -0.072 | 0.00 | -0.26 | 0.40 |
| heavy_cav_archer__vs__heavy_camel_r4 | heavy_cav_archer | heavy_camel | 48.26 | +0.48 | 0.88 | 1.53 | 4.0 / 5.9 / 2.2 | -0.042 | 0.00 | -0.23 | 0.35 |
| heavy_cav_archer__vs__heavy_camel_r5 | heavy_cav_archer | heavy_camel | 46.72 | +0.56 | 0.92 | 1.53 | 4.0 / 5.7 / 0.7 | -0.037 | 0.00 | -0.21 | 0.41 |
| heavy_cav_archer__vs__heavy_camel_r6 | heavy_cav_archer | heavy_camel | 51.12 | +0.80 | 0.93 | 1.68 | 4.0 / 5.7 / 1.6 | -0.070 | 0.00 | -0.27 | 0.43 |
| heavy_cav_archer__vs__hussar | heavy_cav_archer | hussar | 87.75 | +1.26 | 0.90 | 1.93 | 3.8 / 2.9 / 4.3 | -0.010 | 0.33 | -0.14 | 0.54 |
| heavy_cav_archer__vs__paladin | heavy_cav_archer | paladin | 87.16 | +1.34 | 0.96 | 1.48 | 4.0 / 0.9 / 2.9 | -0.006 | 0.01 | -0.08 | 0.65 |
## Aggregates by kiter type

| kiter | n | mean Δθ rev | sign cons | tan/rad | r slope (t/s) | corner | reuse | mean r s/m/e |
|---|---|---|---|---|---|---|---|---|
| arbalester | 23 | +1.15 | 0.947 | 1.67 | −0.043 | 0.24 | 0.55 | 4.0 / 2.8 / 2.2 |
| hand_cannoneer | 24 | +2.08 | 0.966 | 1.81 | −0.004 | 0.44 | 0.69 | 4.0 / 3.1 / 3.5 |
| heavy_cav_archer | 31 | +0.89 | 0.916 | 1.81 | −0.041 | 0.08 | 0.42 | 3.9 / 4.3 / 2.5 |
| **all** | **78** | **+1.33** | **0.941** | **1.77** | **−0.030** | **0.24** | **0.54** | **4.0 / 3.5 / 2.7** |

## Verdict

**1. Tangential orbiting is the dominant tape behavior — unanimously.**
78 of 78 tapes have tan/rad > 1 (min 1.20, mean 1.77): the kiting centroid's
motion about the fight center is mostly tangential, not radial. 75/78 tapes
sweep at least half a revolution; 46/78 complete a full circle or more (max
+4.66 revolutions, hand_cannoneer__vs__elite_elephant_r2 family). Median sweep
+1.13 revolutions.

**2. The direction is consistent — always clockwise on screen.**
78 of 78 tapes have positive total Δθ (clockwise in screen coordinates,
i.e. increasing atan2 in game tile coordinates), and every single tape has
sign consistency ≥ 0.825 (mean 0.941): within any given tape, ~94 % of
1-second windows rotate the same way. There is not one counterclockwise tape
in the corpus. This matches the "orbits clockwise around the central
obstruction" hypothesis exactly and suggests a hardcoded turn preference in
the scripted AI, not a symmetric obstacle-avoidance outcome.

**3. The kiter holds radius rather than fleeing outward.**
Mean r-slope is −0.030 tiles/s (slightly inward); 38/78 tapes hold radius to
within |0.02| tiles/s and only 10/78 drift outward at all (max +0.027).
Mean radius goes 4.0 → 3.5 → 2.7 tiles over the fight — the orbit slowly
tightens as the melee blob dissolves, it never balloons outward. This is the
signature of orbiting (radius roughly conserved) rather than radial flight
(radius growing until the wall stops it).

**4. Cornering is rare.**
On average only 24 % of the final-quarter frames put the kiter centroid within
2 tiles of the usable-area bounding-box edge, and for heavy_cav_archer — the
fastest kiter — it is 8 %. The tape kiter does not end fights pinned against
a wall. (The tapes with corner = 1.0, e.g. champion__vs__hand_cannoneer,
hand_cannoneer__vs__heavy_camel, are slow hand-cannoneer fights whose whole
late-fight orbit hugs the boundary ring — but they hug it while STILL
revolving at sign consistency ≥ 0.91, i.e. sliding along the wall
tangentially, not stuck in a corner.)

**5. The orbit passes through ground the enemy previously held.**
Mean reuse = 0.54 (73/78 tapes above 0.30): more than half of all kiter-
centroid frames sit within 2 tiles of a spot the enemy centroid occupied
earlier in the fight. The kiter circles AROUND and comes back over the
enemy's old ground — it does not reverse away into virgin territory. Combined
with Δθ sweeps beyond ±π in 75/78 tapes, this is direct evidence of
circling rather than back-and-forth reversal.

### Reload-gap caveat

The gap/reload column is NEGATIVE in every tape (corpus mean −0.28 tiles).
This does not contradict the C1 "+0.383" figure — the two metrics measure
different things. This one samples nearest-enemy distance at the kiter's own
fire times across the whole fight: archers fire at maximum range whenever
free, so the at-fire distance starts near max range and drifts down as the
fight contracts and stragglers get caught, producing a small negative mean.
The +0.383 KPI is net separation change per CHASER reload window immediately
following a landed hit — i.e. it isolates the escape phase after contact,
which is precisely where the tape kiter gains ground and ours doesn't. The
missiles channel supports the fire-time segmentation cleanly, but isolating
post-hit chaser windows to reproduce the +0.383 definition exactly belongs to
the C1 tooling (tools/simjs/c1_chaser_cadence.py), so it is not duplicated
here.

### Counterexamples (weakest cases, not contradictions)

- **heavy_cav_archer__vs__heavy_camel_r3** — the overall weakest orbit: sign
  consistency 0.825 (corpus min), tan/rad 1.39, and an inward slope of −0.072
  tiles/s. Still +0.96 revolutions clockwise.
- **halberdier__vs__heavy_cav_archer_r3** — smallest total sweep, +0.35
  revolutions; but tan/rad 1.95 and sign consistency 0.923, so the motion is
  still tangential-dominant and unidirectional, just a short fight arc.
- **elite_fire_lancer__vs__heavy_cav_archer** — +0.49 revolutions with sign
  consistency 0.868; fire-lancer charges force brief direction breaks, yet the
  majority direction remains clockwise.

No tape contradicts the pattern: there is no tape with tan/rad < 1, none with
a counterclockwise majority, and none where the kiter drives outward into a
wall and stalls (max outward slope +0.027 tiles/s with corner 1.0 comes with
sign consistency 0.98 — wall-sliding orbit, not pinning).

### Implication for the engine

The engine-side failure mode (radial retreat → wall → 0.000 gap/reload) is
absent from all 78 tapes. The tape AI's kite step is tangential-first
(tan/rad ≈ 1.8), direction-locked (clockwise on screen), and
radius-conserving. Matching it means biasing the retreat bearing ~60° toward
the tangent (clockwise about the fight center) rather than 180° away from the
threat.

Machine-readable metrics: `data/calibration/analysis/e1_kite_orbit_tapes.json`.

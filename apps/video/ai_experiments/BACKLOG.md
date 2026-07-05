# Micro-AI backlog (2026-07-02, user request: "try different angles, versions to test")

Each item ships as its OWN fresh-named .per (game caches parses by filename) with its own
pre-wired test scenario(s) (AI picked inside the file — load in editor, hit Test).
`ddkImmortalCoreG` stays untouched as the flat-ground baseline; every variant derives from it
by generator script + structural validator (only whitelisted rules may differ from the base).

| # | Version | Angle | Test scenario(s) | Status |
|---|---------|-------|------------------|--------|
| 0 | ddkImmortalCoreG | flat-ground kite baseline (per-unit W_fire/dwell/tiers) | ddk TEST <unit> ×7 + Blank | **awaiting user test** |
| 1 | ddkImmortalCoreH | obstacle + map-edge handling: probe the issued kite point with `up-point-contains` (tree 915 / wall 927 / gate 939) + `up-path-distance == 65535` + pinned-against-edge check → flip strafe direction (2.5s cooldown) + 1.6s lateral-evade boost | ddk TEST Obst Line / Block / Pillars / Choke / Pocket (all pre-pick CoreH) | built |
| 2 | ddkImmortalCoreI | ranged-vs-ranged stutter-strafe: when NOT out-ranging, volley stays the fight but between volleys take a short alternating LATERAL hop (step 180%, dwell 400) — dodge arrows without losing DPS | ddk TEST RvR Strafe (arbs vs arbs) | built |
| 3 | ddkMeleeV1 | melee spread-engagement: sort own + enemies left→right, assign each melee unit its own enemy (k → k mod m) on a 2s beat → the charge fans out (surround) and mirror fights engage 1:1 without bumping; keeps scenario aggressive stance (no de-aggro) so pursuit/auto-acquire stay native | ddk TEST Melee vs Archers, ddk TEST Melee Mirror | built |
| 4 | ddkImmortalCoreS | siege micro: CoreG pipeline + siege classes (913 mangonel line, 955 scorpions) in the finds + DB W_fire rows (mangonel delay 0 → 60) — long dwell (reload 6s → 2200) gives snap volleys + slow repositioning; kite machine backs mangonels away from chargers | ddk TEST Siege (mangonels vs arbs) | built |

## Later (need in-game feedback first)

- **Kite-feel tuning A/B**: re-order beat 1200→900, strafe weave (periodic sign flips), step scale —
  only worth iterating against the user's eye vs Immortal side-by-side.
- **Obstacle fan-out v2**: if CoreH's single flip isn't enough in Pocket, add the Illuminati
  alternating-offset retry (≤5 growing cross offsets, keep first reachable) before ordering.
  Note: `up-point-contains`/`up-path-distance` point-units (tile vs precise) are unverified in our
  context — CoreH converts precise→tile (/100); if "FLIP" never chats when balls hit walls, try
  passing the precise point instead.
- **Melee v2**: strip already-on-target before re-assign (windup churn), 2-rank surround points
  (front stop + wrap flanks), target the enemy BALL edges first (cut off kite direction).
- **Siege v2**: ground-attack leading (`up-target-point` volley at predicted position), friendly-fire
  spacing (don't fire at enemies within blast of own melee), scorpion line-fire alignment.
- **Mixed-army coordination**: ranged ball + melee screen + siege behind — three tag groups, shared
  enemy scan, per-group state machines (the Immortal architecture already supports multi-group).
- **Ranged-vs-ranged v2**: focus-fire the enemy's CLOSEST slice during strafes (current volley is
  farthest-first, tuned for melee chasers), and use `gEnemySync` (Immortal var146) to time hops
  against the enemy's volley rhythm.

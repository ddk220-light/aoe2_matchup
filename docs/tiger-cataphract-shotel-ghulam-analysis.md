# Tiger Cavalry vs Cataphract, Shotel and Ghulam: mismatch diagnosis

September 7, 2026. Analysis uses the existing recordings, archived gRPC state and seed 1 from the unchanged V3 baseline. The six campaign workers continue on that baseline. Diagnostic variants run separately with in-memory mechanics overrides; none is an approved gameplay fix.

## Attack timing: installed game data, then recorded confirmation

Installed source: `C:/Program Files (x86)/Steam/steamapps/common/AoE2DE/resources/_common/dat/empires2_x2_p1.dat`, SHA-256 `ce3530df36cf0b333a9751cb0ff94460fe904f811feecec8ae9794701622b4cf`.

| Elite unit | Master / graphic | Raw frame delay | Animation frames × seconds/frame | Effective delay | Recorded examples |
|---|---|---:|---|---:|---|
| Tiger Cavalry | 1951 / 2836 | 0 | 60 × .0266666673 | .800 s | .806, .808, .812, .816 s |
| Cataphract | 553 / 1512 | 0 | 30 × .0516666658 | .775 s | .780, .790 s |
| Shotel Warrior | 1018 / 2860 | 0 | 30 × .0500000007 | .750 s | .758, .760 s |
| Ghulam | 1749 / 2916 | 12 | 30 × .0333333351 | .400 s | .406, .418 s |

The effective values already in the fixtures agree with the game observations. Raw frame delay zero does **not** mean instant melee damage. For these three zero-frame units, the observed hit is halfway through their specific DAT attack animation; Ghulam hits at frame 12. The Shotel zero-delay ablation changed the winner but is a deliberately incorrect counterfactual, **not a fix or evidence of a windup bug**. Earlier suspicion of its .750-second delay is withdrawn.

Method: decode archived entity sprite changes, HP changes, positions and action records. Match normal-size nonfatal HP drops to the single nearby opponent displaying its attack graphic. Dense fights still produce some ambiguous/outlier pairs, so the audit retains every candidate, not just the modal cluster. Timing clusters agree within a typical 16–20 ms capture sample. The first Shotel example changes to graphic 2860 at 4.426 game seconds and the nearby Tiger loses 16 HP at 5.186 seconds (.760 s); the second is 4.690 → 5.448 (.758 s). Ghulam: 4.432 → 4.838 (.406 s). This supports the DAT-derived values rather than tuning delay to reproduce a winner.

## Mechanics and mismatch evidence

### Cataphract

The runtime already applies `flatDamage=5` directly, independently of melee armor; it does not apply the elephant-style post-armor percentage. Archived nonfatal Tiger HP decrements show 298 isolated 5-point drops and 295 isolated 8-point direct-hit drops. Tiger's ordinary hit on Cataphract is 12, matching both implementations.

This is not a missing flat-trample mechanic. At 20 seconds after each run's first HP loss, the recording retains 24 Tigers versus 21 Cataphracts; seed 1 retains 19 Tigers versus 22 Cataphracts. V3's early engagement and distribution of hits differs. Reducing radius .5 → .25 reverses the winner in a sensitivity test, but .25 is not established by game evidence and must not be substituted just to match the result. We have not isolated the full causal share of trample geometry, engagement order and Tiger growth.

### Shotel Warrior

Royal Heirs' three-point reduction against mounted attacks is present and working. Tiger carries the mounted marker; its starting hit is `17 - 3 melee armor - 3 mounted reduction = 11`. Recorded drops show 11, then 12/13 as Tiger earns kill bonuses. Shotel hits Tiger for `22 - 6 = 16`; this also agrees.

The first five seconds after contact expose the discrepancy: recorded Tigers deal 121 effective damage across seven Shotels and kill none. Seed 1 deals 266 across six Shotels and kills four. By ten seconds the game has 12 Tigers / 25 Shotels; V3 has 14 / 20. V3 gains earlier concentrated kills, activating Tiger bonuses and changing subsequent exchanges. The missing resistance and incorrect .750-second windup hypotheses are ruled out; formation and engagement scheduling are the stronger leads. No unsupported timing change was applied.

### Ghulam

Damage magnitude is correct: 9 direct damage and 4.5 secondary damage against Tiger. The recording contains 127 isolated nonfatal 9-point drops and 22 isolated 4.5-point drops. Seed 1 emits 174 direct and 171 secondary damage events (769.5 secondary damage). These counters are not exactly equivalent—recorded frames can combine hits and the raw histogram excludes fatal/combined drops—but the excess secondary exposure is substantial, especially early in combat.

The current implementation tests a forward rectangle, extending one tile from the attacker and widening each side by the Ghulam collision radius plus the victim radius. This produces a nominal .9-tile-wide eligible strip against Tigers. It is an implementation choice that has not been calibrated to this recorded attack geometry.

Keeping movement, targeting, stats, plan and seed unchanged, disabling secondary damage gives a Tiger win with 802 HP; shortening only the line length to .5 gives a Tiger win with 624 HP. Baseline seed 1 loses. These establish sensitivity to the pass-through area, not the correct replacement dimensions. Fit the geometry to isolated recorded primary/secondary strikes before changing the production profile.

## The movement premise needs correction

All three matchups have exactly matching initial unit positions. Matching each archived entity to the simulated entity at the same starting coordinate, however, shows roughly 1.8–2.2 tiles RMS trajectory separation at game second 3, before first damage. The game visibly rearranges units while entering patrol; the simulator's trajectories differ.

One Shotel-match Tiger starts at (12.5, 5.5). At game second 2 it is at about (12.902, 3.989) in the recording, while V3 places it at (11.271, 6.378), a 2.89-tile separation. Therefore initial placements are correct, but movement/formation, overlap exposure and first targeting cannot be assumed equivalent. Group reformation is a strong candidate; it is not yet proven to explain every downstream hit.

## Additional confirmed Tiger discrepancy

V3's kill handler heals Tiger but clamps it to its existing 145 max HP and never increases max HP. Archived per-entity own-master data shows max HP increasing to 155, and the Ghulam recording contains a Tiger with 150.5 current HP. That state is impossible in the current simulator. This can disadvantage Tiger in Cataphract/Ghulam fights, but cannot by itself explain V3 incorrectly favoring Tiger against Shotel.

## Recommended repair sequence

1. Preserve the verified per-unit hit timing; do not set Shotel windup to zero.
2. Reproduce recorded patrol reformation before first contact; compare trajectories and first targets, not just final winners.
3. Calibrate Ghulam's actual secondary-hit shape on archived positions and isolated hits, then test held-out seeds/recordings.
4. Correct Tiger's per-kill maximum-HP growth and verify the cap and heal semantics from the game data.
5. Re-evaluate Cataphract splash recipients after formation and growth corrections; keep the verified flat five damage.

Evidence files are in `aoe2x/js_simulation/calibration/lab/analysis/tiger-special-mechanics/`. The game raw bundles and original simulation seeds are retained unchanged. No experiment was promoted into the ongoing comparison campaign.

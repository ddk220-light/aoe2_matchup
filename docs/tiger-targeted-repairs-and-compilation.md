# Tiger campaign: compilation and targeted simulation repairs

September 7, 2026. The compilation and Ghulam/Flaming Camel changes are implemented and validated. **Shotel Warrior is still unresolved.** The original campaign comparisons remain the baseline; the new seed artifacts are separate.

## Video delivery

`aoe2x/js_simulation/calibration/lab/compilations/tiger-unique-units/tiger-cavalry-all-completed-overlays.mp4`

- 59 completed overlay clips, in campaign civilization order, with 59 embedded chapters.
- Duration 2027.840333 seconds (33:47.84), 2560×1440, H.264 plus AAC audio; approximately 3.64 GB.
- This includes every completed overlay, not the 14 overlays still held for timing review. `manifest.json` lists both included and omitted jobs.
- Missionary ends just after the last ownership conversion: gRPC game time 41.210 seconds, mapped video time 19.858333 seconds. The exclusive cut is frame 1193 at 60 fps (19.883333 seconds).
- The standalone Missionary link now uses this cut. Its longer overlay is preserved as `battle-with-unit-hp-before-final-conversion-trim.mp4`; the raw video and gRPC frames are untouched.
- All 118 chapter boundary samples decoded at the expected resolution. FFprobe found all 59 chapters. The final concat log is empty. Audio is encoded as a continuous stream to avoid timestamp overlaps between independent clips.
- `chapters.txt`, `validation.json`, and `missionary-trim.json` accompany the video. The final Missionary frame was visually checked: zero Player 2 survivors and 44 Player 3 survivors.

## Elite Ghulam

The former mode-130 implementation added the victim's collision radius to a lateral strip that was already defined by the attacking Ghulam's collision size. This admitted extra sideways recipients. Its longitudinal cutoff also substituted a simple forward distance for the blast distance to the victim's collision box.

The repaired directional test uses the DAT one-tile blast distance to the nearest point of the victim's axis-aligned collision box, a forward-facing test, and the existing DAT-derived 0.2-tile half-width without extra victim padding. The secondary damage remains half that victim's normal post-armor damage: 4.5 against the opening Tiger profile. The 0.400-second attack delay is unchanged.

The follow-up Shotel investigation found that the original diagnostic retained mutable action references. That target attribution audit has been superseded by deep-copied per-frame action models. The corrected audit contains 345 neighbouring hit/miss candidates. The geometry agrees with 344; the positive event at 22.882 game seconds remains ambiguous in crowded combat. The former 20.172-second ambiguity disappears with corrected target attribution. Tests retain all evidence and exclude the entire remaining ambiguous event: **340 checks** pass, split across early and late portions of the recording. This is validation against one recording, not an independent matchup holdout or proof of the complete AoE2 shape.

Five reruns now give the recorded winner, Tiger, instead of Ghulam. They leave 396.5 Tiger HP versus 1047.5 in the recording: signed HP delta improves from -54.30 to **-32.07 percentage points**, still outside the requested 20-point tolerance. The known Tiger max-HP growth discrepancy and formation differences remain separate leads; no compensating damage or timing tuning was applied.

## Flaming Camel

Two corrections:

1. Blast mode 66 uses distance falloff, rather than full damage everywhere inside the radius. Distance is from the explosion centre to the nearest point of the victim's axis-aligned collision box. Inside the DAT two-tile radius, damage is `max(1, normalDamage × (1 - distance / radius))`; outside, it is zero. This reproduces **135 recorded nonfatal damage/no-damage observations within 0.0001 HP**, including the one-point minimum. Existing hostile-only filtering and single explosion/death handling remain in place.
2. The zero-frame self-destruct shares its attack graphic with its death graphic (10497). All 19 observed deaths follow entry into that graphic by the next 14–18 ms capture sample. This is not an ordinary melee swing whose unset frame delay should use the animation midpoint. The exporter now emits an immediate self-destruct boundary only when those DAT conditions hold. The Flaming Camel fixture was regenerated; its only non-provenance change is attack delay .250000013 → 0 seconds. Tiger, Ghulam, Shotel and Cataphract timing is untouched.

Five final reruns agree with the recorded Flaming Camel winner. They retain 375 Camel HP versus 600 in the recording; signed HP delta is **+11.11 points**, down in magnitude from 33.33 points and within the requested 20-point tolerance. The earlier falloff-only experiment produced a smaller aggregate error but retained the contradicted midpoint delay; it is preserved separately and was not chosen over the observed timing to fit the final HP.

## Shotel Warrior: no speculative fix promoted

The recorded starting damage remains 11 from Tiger to Shotel and 16 from Shotel to Tiger. Royal Heirs' three-point mounted reduction and Shotel's .750-second windup are already correct. Existing baseline V3 favours Tiger; the recording favours Shotel.

The pre-contact positions differ visibly. At three seconds, the recorded armies have reformed into narrow moving groups, while V3 still approaches in its original broad arrangement. The first five seconds after contact contain 121 Tiger damage and no Shotel deaths in the recording, versus 266 damage and four early kills in baseline seed 1. Early focus and engagement exposure are therefore stronger leads than a missing damage mechanic.

Two isolated opening-target alternatives, ordinary nearest-target selection and exposing all opening lanes, still produce the wrong Tiger winner (360 and 376 HP). Neither was promoted. Restarting from the recorded three-second positions without the game's continuing formation/overlap state stalls at the engine tick cap, while restarting from baseline positions completes. That restart is not a valid reproduction of the complete game state and cannot establish a corrected outcome or a causal percentage. It does show why substituting recorded positions alone is not a safe production repair.

Further work must model and validate the initial formation transition and its overlap/target acquisition state. Changing Shotel stats, making its windup zero, or adding a matchup-specific outcome adjustment would contradict the evidence.

## Validation and artifacts

- 29 focused engine tests pass, including existing unique mechanics and the new recorded blast regressions.
- All 74 roster profiles and Golden inputs pass preflight; this verifies coverage, not accuracy.
- The ten final seed artifacts, input/source hashes and `comparison-summary.json` are in `aoe2x/js_simulation/calibration/lab/analysis/targeted-repair-validation/`.
- Seeds 1–5 give identical outcomes within each of these two matchups. They are reproducibility checks, not five independent statistical observations.
- Archived samples with raw-frame SHA-256 provenance are in `aoe2x/js_simulation/fixtures/recorded-special-blast-samples.json`.
- Original campaign results, Golden scenarios, raw recordings, and ambiguous overlays are retained.

Reproduction helpers used for this local delivery are `.tools/build-tiger-compilation.py`, `.tools/run-targeted-repair-seeds.py`, `.tools/audit-targeted-mechanics.py`, `.tools/diagnose-shotel-opening.mjs`, and `.tools/isolate-shotel-formation.mjs`.


## Shotel follow-up: recovery correction and missing patrol regrouping

See `docs/shotel-patrol-followup.md` for the corrected immutable-action audit. A generic melee bystander recovery bug is repaired, but the Shotel winner remains wrong. The earlier seed outputs above predate this recovery change; they are preserved historical results, not reruns of the current source. No speculative column-slot or engagement-capacity changes were promoted.

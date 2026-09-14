# Elite Monaspa video production

Completed September 13, 2026: full video and all ten Shorts uploaded and remotely processed, 11/11 COMPLETE. Full video: https://www.youtube.com/watch?v=5gRrdmf9r24. Receipt: `aoe2x/js_simulation/calibration/lab/compilations/elite-monaspa-unique-units/upload-completion.json`. Current visibility is preserved from Studio. Use the [complete runbook](VIDEO_PRODUCTION_RUNBOOK.md) for a new episode. The stage notes below retain the production sequence; the upload-in-progress note is superseded by this completion receipt.

73 recorded matchups against the approved unique-unit roster, excluding itself. Corrected Imperial purchase costs per physical unit, equal resources, 27-unit cap, existing Golden Hussar screen for melee versus ranged. Captures completed and verified with no remaining failures after resuming from the operator pause; original raw video and frames remain under D:/AoE2 Renders/elite-monaspa/captures.

The user explicitly authorized the full video and ten Shorts upload. Default private visibility, preserve Studio owner changes. Sequential offline pipeline: overlays, Georgian intro, full compilation, ten selected Shorts, actual visual review, uploads and remote processing verification.

Georgian artwork uses the installed Tamar campaign background cscam3/tamar_background.dds. The new mounted Monaspa sketch derives from the installed game sprite; final generated asset is apps/video/intro/assets/elite-monaspa-campaign.png. Intro text derives from installed Mountain Affinity help 13403 and Georgian civilization help 120194. Two untitled pages use game font, narration-aligned letter reveals, and a narrower text column (x=865, width=465) to clear this background's foreground artwork.

Music: Georgian theme media 700657755 from installed Base.pck. Narrator: Tamar PLAY_GEO1S1, media 83034689 in English DLC4.pck. User authorized replacing the completed Burgundian ElevenLabs profile; metadata is retired and all prior audio is preserved. New voice metadata: apps/video/intro/georgians-voice-clone.json. Secrets are never stored in project files.

Production supervisor: apps/video/finish_elite_monaspa_production.py. State: data/local/elite_monaspa-production-status.json. Overlays use eight workers. Supervisor checks thermal status every fifteen minutes; existing CPU sensor unavailability remains documented, GPU readings remain available. Final visual-qa.json must only be written after inspecting actual compiled and Shorts outputs.

All 73 overlays completed. Flaming Camel initially lacked enough visible HP bars (23); increasing the observation rate to 15 Hz produced 66 bars, 0.0204 RMS fraction error and 21.6 alternative-error ratio, passing unchanged validation thresholds. No recapture or threshold relaxation was needed.

## Upload released

The 26:49 full compilation passed full decoding, and all ten Shorts passed rendering validation. Final representative frames for the compilation and every Short, encoded intro, both thumbnails, and chapter description were visually reviewed. The final visual-qa.json gate is passed. The supervisor is uploading the full video first, then ten Shorts, and will verify remote processing for all eleven. State keys use elite-monaspa-full-cost-v2 and elite-monaspa-short-NN-cost-v2; retries reuse these keys to avoid duplicate uploads.

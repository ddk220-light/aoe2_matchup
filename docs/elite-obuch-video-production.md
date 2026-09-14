# Elite Obuch episode

[Start with the complete production runbook](VIDEO_PRODUCTION_RUNBOOK.md). This episode uses the same approved capture, overlay, intro, Shorts and private-upload workflow. Read live receipts for progress; this file describes the inputs and restart commands.

## Captures and media

The subject is **Elite Obuch**, Poles, `elite_obuch_poles`, master 1703. Its audited Imperial purchase cost is 55 food + 20 gold per physical unit. [The capture manifest](../aoe2lab.recorder.elite-obuch-all-unique.json) contains 73 opponents and excludes itself. The capture campaign completed all 73 recordings with verified counts and raw/frame bundles.

Rules remain equal resources, at most 5,000 resources and 27 main units per side, with whole-unit rounding. Mixed ranged/melee battles retain the normal Golden's nine Spanish Hussars outside the budget. The five-Hussar change belongs only to the [Blackwood experiment](blackwood-five-hussars-experiment.md). P2 is Obuch; P1 matches P3's civilization for game music.

`LAB` means `aoe2x/js_simulation/calibration/lab` below. Canonical paths:

| Artifact | Location |
| --- | --- |
| Capture receipt | `LAB/campaigns/elite-obuch-all-unique/status.json` |
| Canonical verified-source receipt | `LAB/campaigns/elite-obuch-canonical/status.json` |
| Overlay jobs/status | `LAB/campaigns/elite-obuch-final-overlays/` |
| Full compilation | `LAB/compilations/elite-obuch-unique-units/final-cost-v2/` |
| Narration audio and timings | `LAB/compilations/elite-obuch-unique-units/narration-v1/` |
| Intro video | `LAB/compilations/elite-obuch-unique-units/intro-v1/` |
| Ten Shorts | `LAB/shorts/elite-obuch-selected-10/` |
| Processing/upload receipt | `LAB/compilations/elite-obuch-unique-units/upload-completion.json` |
| Supervisor status | `data/local/elite-obuch-production-status.json` |

On this workstation the capture, compilation and Shorts paths are junctions into `D:\AoE2 Renders\elite-obuch\`. Preserve the raw frame streams, plans, scenarios, full master, narration, QA and upload receipts.

## Polish intro provenance

- Background: the installed Jadwiga `eecam2/jadwiga_background.dds`; the campaign catalog's first-scenario P1 identifies Poles.
- Unit copy: installed English help strings 26559, 120187 and `IDS_CIVTIPS_38_2`, paraphrased into two untitled pages about the infantry unit and its armor-stripping ability.
- Sketch: [generated campaign illustration](../apps/video/intro/assets/elite-obuch-campaign.png), with exact reference and prompt in [provenance](../apps/video/intro/assets/elite-obuch-campaign.provenance.json).
- Music: Base.pck bank 1638387902, **embedded** media 841251286; 12-second stereo Polish theme. The extractor reads `DIDX`/`DATA` when no streamed entry exists. The plan records the decoded WAV hash.
- Narrator: Jadwiga event `PLAY_POL1_INTRO`, English DLC2.pck media 743418006. A 90-second clean sample was taken from the approximately 170-second source. [Clone metadata](../apps/video/intro/poles-voice-clone.json) retains the sample hash and source IDs.
- Slot replacement: completed Monaspa/Tamar narration and all eleven videos were verified before retiring its cloud profile. The owner's [standing replacement policy](../apps/video/intro/voice-profile-policy.json) applies to future completed campaign clones too.

[The base plan](../apps/video/intro/elite-obuch.json) and [narrated plan](../apps/video/intro/elite-obuch-cloned.json) preserve the two-page layout. Speech occupies about 17.65 and 24.15 seconds; lead-in and final reading holds yield a 46.63-second intro. The actual character timestamps drive the letter reveal. Narration and extracted music are local files; regenerate/remap their absolute paths on another machine.

## Resume the authorized package

Set up `$Py`, `$Lab`, FFmpeg and `PYTHONPATH` using the main runbook. For this already-authorized episode, the single supervisor is:

```powershell
& $Py apps/video/finish_elite_obuch_production.py --upload-authorized
```

Run only one supervisor; it holds the final-production lock. This particular wrapper first waits for the local Blackwood master, then processes Obuch's overlays, battles, covers, ten Shorts, narrated intro and full compilation. It waits for an actual visual-QA receipt before uploading. After all eleven Obuch videos complete YouTube processing, it calls the separate Blackwood publisher. The cross-episode wait/order is specific to the owner's current request, not a default for every future episode.

The media adapters are [full builder](../apps/video/build_elite_obuch_final.py), [Shorts selector](../apps/video/prepare_elite_obuch_final_shorts.py), [overlay manifest](../aoe2lab.overlays.elite-obuch-final.json), and [supervisor](../apps/video/finish_elite_obuch_production.py). The selector uses recorded results and effective per-unit costs, includes Missionary and Flaming Camel, and records a substitute reason if one of the six cost-based win/loss categories is unavailable.

Upload to `@aoe2matchup` remains private. Use stable keys `elite-obuch-full-cost-v2` and `elite-obuch-short-01-cost-v2` through `-10-`. Reuse these identities on retries. Completion requires all eleven processing results to succeed, not just transfer completion. Final visual/audio QA must describe checks actually performed and any limitations; never manufacture a listening or viewing claim from file existence.

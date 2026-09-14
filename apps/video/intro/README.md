# Campaign intros: current entry point

Use the [complete production runbook](../../../docs/VIDEO_PRODUCTION_RUNBOOK.md) and its [intro/narration reference](../../../docs/video-production/MEDIA_AND_PUBLICATION.md) for new units. Approved format: two untitled pages, civilization campaign backdrop, reviewed unit sketch, narration-aligned letter reveal, and quiet music. The Wei, Burgundian and Georgian voice profiles were later retired; their saved audio remains valid, but those profile IDs cannot generate new speech. The owner's [standing replacement policy](voice-profile-policy.json) covers completed campaign clones when a slot is needed. Regenerate/remap machine-local audio paths on another workstation. Extracted music is local and is restored using the media reference's verified IDs/provenance.

The remaining notes preserve the original Tiger prototype history; earlier “current,” “pending,” and library-voice descriptions are superseded.

Latest Tiger version: `intro-v4/tiger-cavalry-intro.mp4` uses the saved, user-authorized Wei campaign instant-clone narration. Prior versions remain for comparison. See NARRATION-OPTIONS.md and wei-voice-clone.json for historical provenance.

Current narrated version: `intro-v3/tiger-cavalry-intro.mp4`, 32.633 seconds, two untitled pages with letter reveal synchronized to ElevenLabs character timestamps. It uses the closest library-voice result from an approved Wei campaign sample search, with quiet Chinese-theme music. See NARRATION-OPTIONS.md for provenance and reproduction. Previous intro-v1 and intro-v2 remain available.

# Campaign intro draft

The current Tiger Cavalry draft has two untitled pages and lasts 42 seconds: historical background, then promotions and anti-archer ability. Text appears one character at a time (15 characters/second), with stable word wrapping and final reading holds. No headings or page numbers appear. Introduction, rules, and chapter navigation now live in the description. The Chinese civilization theme plays quietly throughout with fades; narration is pending a voice choice. See NARRATION-OPTIONS.md.

Output: `aoe2x/js_simulation/calibration/lab/compilations/tiger-unique-units/intro-v2/tiger-cavalry-intro.mp4` (1920×1080, 30 fps). The directory also contains full-page PNGs, a manifest, validation results, and a description with all 59 completed compilation chapters and their recorded winners. Description timestamps assume this intro is prepended; the existing full compilation has not been replaced by this draft.

## Reuse

From the repository root, set `PYTHONPATH=apps/video;.` and run:

```powershell
apps/video/.venv/Scripts/python.exe apps/video/build_campaign_catalog.py
apps/video/.venv/Scripts/python.exe apps/video/build_campaign_intro.py --plan apps/video/intro/tiger-cavalry.json
```

To revise explicit art associations without parsing scenarios again:

```powershell
apps/video/.venv/Scripts/python.exe apps/video/build_campaign_catalog.py --refresh-themes
```

The catalog retains the first-scenario Player 1 evidence separately from the chosen art association. Each scenario is parsed in a separate process because the parser keeps version-specific global state. Only the first embedded scenario is considered; failures are not silently replaced by later scenarios. GPV archives and parse failures receive explicit curated associations where known. Collections have no single civilization. Any unmapped civilization uses a labeled Art of War fallback.

Important exceptions: Babur begins with Tatars but uses Hindustani campaign art; Dracula begins with Turks but is a curated Slavic art choice. The three Three Kingdoms campaigns share installed art. Wei deliberately uses Art of War, as requested. The overrides distinguish these judgments from extracted scenario facts.

## Artwork

The Art of War DDS is read from the installation; it is not copied into the source tree. Typography uses the existing GameFont atlas renderer. The original generated illustration is stored at `assets/tiger-cavalry-campaign.png` and composited with multiply blending so white paper disappears against the game parchment.

Generation used the built-in image tool, with `apps/website/static/img/units/Elite_Tiger_Cavalry.png` as reference. Prompt: "Create an original full-body Elite Tiger Cavalry rider and horse. Preserve the pale tiger-head pelt headdress over a human rider, lamellar armor, shoulder guards, long spear, and armored horse. Three-quarter profile facing right, calm advancing pose. Refined monochrome graphite and dark sepia pen-and-ink engraving, fine crosshatching, hand-drawn historical campaign sketch, soft unfinished edges. No scenery, frame, or text. Keep the complete horse and spear in the canvas." The first generation depicted a checkerboard rather than real transparency; the final edit replaced it with uniform white for reliable multiply compositing. No checkerboard remains in the rendered intro.

## Content and recording facts

Copy is original paraphrase, with source links in the plan and generated description. Historical context is based on the Tiger and Leopard Cavalry under Cao Cao. Gameplay text describes promotion on military kills and bonus damage against archers without listing stat numbers.

The archived ranged matchup used nine Spanish cavalry screen units. The Armenian capture's initial gRPC snapshot contains nine Player 4 entities, master 448, each with 95 HP; the Golden fixture identifies Player 4 as Spanish. The intro therefore says "nine Spanish cavalry" rather than the recalled ten Huskarls. It does not change future recording rules or claim the screen is charged to the resource budget.

The first renderer layout is designed for the Art of War parchment. The catalog can select other civilization backgrounds, but different parchment shapes may need their own layout profiles before bulk intro rendering. This is a reusable, editable first draft, not a validated layout for every campaign background.

Music can be re-extracted with `apps/video/.venv/Scripts/python.exe apps/video/extract_intro_music.py --decoder .tools/vgmstream/vgmstream-cli.exe`. The decoder is from the official vgmstream r2117 release. Run the renderer where the installed FFmpeg is accessible. The original intro-v1 remains available.

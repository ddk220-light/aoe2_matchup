# YouTube video and thumbnail defaults

The user selected thumbnail option 2, the campaign intro parchment, as the default for Tiger Cavalry and future unit videos. The style is recorded in `apps/video/thumbnail-style.json`.

## Thumbnail

- Reuse the same civilization campaign background as the video's intro. Use the campaign catalog mapping; Wei uses the Art of War fallback.
- Center the approved unit sketch on the parchment. Put the unit name and “Matchup” below it in dark brown historical serif lettering.
- Preserve the quiet game campaign aesthetic, parchment, background frame, and generous margins. Do not add flashy effects, counters, stats or extra slogans.
- The approved Tiger example is `aoe2x/js_simulation/calibration/lab/compilations/tiger-unique-units/thumbnails/options-v1/02-original-intro.png`. It was generated from the actual intro frame and approved sketch. For future units, reuse the installed background and that unit's approved intro artwork.
- Upload JPEG at 1280 × 720, below 2 MB. Keep the full-resolution source and original options.

## Tiger Cavalry upload

The user explicitly authorized starting the upload after selecting the thumbnail. Target channel: `@aoe2matchup`, channel ID `UCKYN-pN4AZ3w4LpRxcdSciA`. The earlier `@ddk220` authorization was the wrong channel and must not be used.

Use the approved 34:31 compilation containing 59 matchup chapters plus the intro. The prepared title is “Elite Tiger Cavalry vs 59 Unique-Unit Matchups | AoE2 DE”. The upload description includes rules, the Hussars screen wording, chapter results and remaining HP, the preselected website link, and hashtags.

Initial visibility is private. Other settings: Gaming, English, not made for kids, Standard YouTube license, embedding enabled, realistic synthetic-media disclosure enabled for the cloned intro narration. No publication schedule was requested. A future public release requires its own user instruction and may be restricted by Google's API project audit rules.

## Authorization and reliable transfer

`apps/video/authorize_youtube.py` starts a localhost OAuth/PKCE flow. It does not upload. Tokens are encrypted with Windows DPAPI and kept in ignored `data/local/youtube/`; never commit credentials, tokens, or resumable session URLs.

`apps/video/upload_youtube.py` requires the preparation and settings files to record explicit authorization. It verifies the live channel handle and ID, resumes 16 MB chunks using the existing server session, and saves the returned video ID before applying the thumbnail. Re-running after an interruption must resume that session or use the saved ID, never blindly create another video. Metadata/source identity changes require review before resuming.

The local progress record is `data/local/youtube/tiger-upload-status.json`. Public-safe upload responses, thumbnail response and processing status are saved beside the final compilation. Do not describe the upload as complete until the returned ID, selected thumbnail and processing result have been checked.

Description copy: omit the narration-disclosure paragraph, the one-recorded-battle disclaimer, and the phrase stating Tiger Cavalry is already selected. Keep the actual preselected website link with the label “Try your own matchup:”. Apply this to future unit uploads too; see apps/video/youtube-description-style.json. The separate synthetic-media setting remains enabled.

## Reusable Shorts covers and batch uploads

Use one vertical campaign-parchment cover per subject, not one per opponent. The 1080x1920 Tiger and Xianbei covers and 1280x720 Xianbei full cover are under `apps/video/intro/thumbnails/`; prompts and references are saved in `apps/video/intro/thumbnail-prompts-v2.json` (built-in image generation). Existing Short `rzxCxUX-Rzs` received the vertical Tiger cover without another upload.

The approved batch is `aoe2x/js_simulation/calibration/lab/youtube-batch-tiger-xianbei/manifest.json`: 20 selected Shorts (10 per subject) plus the full 73-match Xianbei compilation. The earlier Composite Bowman Short is additional to these 20. Settings are private, gaming, not made for kids; synthetic-media flag applies to the narrated full intro, not gameplay-only Shorts. Descriptions retain matchup conditions, results, relevant tags and the correct preselected website URL.

`upload_youtube_batch.py` uses two transfer workers, unique `--state-key` values, and then polls processing. Every upload has a separate durable response and resumable session. Reuse the manifest to resume; do not create replacement identities for already uploaded videos. Batch status and a linked local HTML index remain next to the manifest. Preserve owner changes made in Studio. An uploaded file is not called processed until the processing API succeeds; verify Studio SD/HD status as well.

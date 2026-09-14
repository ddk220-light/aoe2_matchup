# Campaign intro, media QA, and publication

[Return to the complete runbook](../VIDEO_PRODUCTION_RUNBOOK.md).

## Campaign background and copy

The game already supplies the surrounding painted scene, parchment, and border as a single clean DDS. Text, drawings and buttons are separate layers. Use the clean asset, not a screenshot with old text or navigation controls baked in.

Sources under the game root:

- `widgetui/textures/campaign/`: campaign backgrounds and slide illustrations.
- `resources/_common/campaign/`: campaign/slideshow definitions, narration events and string IDs.
- `widgetui/scenarioslideshow.json`: logical slideshow layout.
- `resources/_common/fonts/combined.txt` and `combined_0000.png` etc.: the glyph atlas read by `GameFont`.
- English localized strings: unit/civ help and campaign text.
- `wwise/` and language-specific packages: music/narration sound banks.

[Campaign catalog builder](../../apps/video/build_campaign_catalog.py) examines the first embedded scenario's P1 civilization in a separate parser process. Some campaigns are mixed-civ, unsupported/GPV, or parse-ambiguous. [campaign_overrides.json](../../apps/video/intro/campaign_overrides.json) records curated art associations; [scenario_civilization_overrides.json](../../apps/video/intro/scenario_civilization_overrides.json) identifies particular historical battles. [campaign_catalog.json](../../apps/video/intro/campaign_catalog.json) keeps evidence separate from the preferred civilization theme.

```powershell
& $Py apps/video/build_campaign_catalog.py
# If only the curated theme associations changed, reuse parsed scenario evidence:
& $Py apps/video/build_campaign_catalog.py --refresh-themes
```

Use one command appropriate to the change, not both by habit. The catalog embeds the game-root path as provenance; set `AOE2_GAME_DIR` and rebuild on a different installation if necessary. For an unmapped civilization, use an explicitly recorded Art of War fallback rather than invent a campaign association.

Examples: Wei's requested visual theme is Art of War even though a Wei campaign narrator exists; Georgians use Tamar; Burgundians use the Dukes; Koreans and Magyars use the specific Noryang/Honfoglalas scenario associations rather than assigning their whole collection to one civilization. Do not assume the first-scenario P1 is always the best artistic mapping.

### Unit artwork

Look first for an appropriate unit illustration in the installation. If absent, generate a new campaign-style sketch from the exact unit portrait/sprite. The approved look is monochrome graphite/dark sepia ink, crosshatching, a complete readable unit silhouette, and softened/unfinished edges. Preserve distinctive armor, equipment, rider/horse anatomy and weapon. Avoid extra decorative lettering, borders, invented emblems, modern objects, or an unrelated historical portrait.

Save the reference path, generation prompt, selected output, and review notes. Committed generated illustrations live in `apps/video/intro/assets/<key>-campaign.png`. Use genuine RGBA transparency or plain white for multiply compositing. A checkerboard drawn into the pixels is not transparency. Inspect the final composite on parchment, including shadows and white margins.

Suggested starting prompt (adapt to the actual unit):

> Create an original campaign illustration of this exact AoE2 unit from the reference sprite. Keep its identifying equipment and silhouette. Full figure in three-quarter view, facing toward the text. Monochrome graphite and dark sepia pen-and-ink drawing, fine crosshatching, hand-drawn historical illustration, soft unfinished edges. Plain white background for multiply compositing. No text, border, paper rectangle, scenery, or checkerboard.

The illustration prompt is an asset instruction; it does not authorize external publication or a different video campaign. Review it before use.

### Editorial plan

Base plan path: `apps/video/intro/<key>.json`. Example minimal structure:

```json
{
  "civilization": "INCAS",
  "unit": "Elite Kamayuk",
  "art": "assets/elite-kamayuk-campaign.png",
  "sources": ["Exact installed unit-help string or supporting source URL"],
  "voiceSelection": "Previously authorized relevant campaign narrator",
  "slides": [
    {"duration": 25, "paragraphs": ["Reviewed unit overview and background."]},
    {"duration": 25, "paragraphs": ["Reviewed unique abilities in plain language.", "A short connection to the matchup experiment."]}
  ],
  "videoFilename": "elite-kamayuk-intro.mp4",
  "music": {
    "file": "assets/incas-theme.wav",
    "identity": "Incas civilization theme",
    "source": "Installed Base.pck media 1032387344"
  },
  "textX": 875,
  "textWidth": 550
}
```

The sample prose is a schema illustration, not publishable copy. Source historical facts separately from gameplay mechanics. Prefer installed unit/civ help for abilities; use primary or reliably attributed historical sources where necessary. Paraphrase in two short pages: overview/background, then what makes the unit special. Do not copy a whole wiki paragraph or list attack/armor numbers instead of explaining the ability.

The first prototype's extra intro/rules/chapters pages were removed by user review. Current pages have no headings or page numbers. Rules and chapter details go in the description. Update spelling/pronunciation before synthesis; text changes invalidate the narration alignment.

### Music extraction and restoration

Extract the selected stream from the installed package using the [music extractor](../../apps/video/extract_intro_music.py), then decode with the locally installed [vgmstream CLI](https://github.com/vgmstream/vgmstream/releases). Media IDs must be verified against this game build and by listening; an undocumented ID is not proof of civilization identity.

```powershell
& $Py apps/video/extract_intro_music.py --media-id 1032387344 `
    --output apps/video/intro/assets/incas-theme.wem `
    --decoder .tools/vgmstream/vgmstream-cli.exe
```

Default package is `$env:AOE2_GAME_DIR/wwise/Base.pck`; override with `--package <actual-package>` where needed. `--output` points to the WEM; the decoder creates the adjacent WAV. Extracted music and WEM binaries are ignored in Git. Recreate them from this mapping/episode provenance on a fresh clone:

| Theme | Base.pck media ID | Expected local stem |
| --- | ---: | --- |
| Chinese / established Art of War fallback | 784299781 | `chinese-theme` |
| Incas | 1032387344 | `incas-theme` |
| Koreans | 491516321 | `koreans-theme` |
| Spanish | 406743514 | `spanish-theme` |
| Tatars | 667441127 | `tatars-theme` |
| Magyars | 260189988 | `magyars-theme` |
| Burgundians | 487359100 | `burgundians-theme` |
| Georgians | 700657755 | `georgians-theme` |

Mapuche, Tupi, and Muisca episode plans contain the historical theme-source URLs/asset provenance rather than a verified Base.pck ID. For those, obtain the documented source through the authorized asset workflow, verify any recorded source hash, and decode the local OGG into the plan's WAV with `ffmpeg -i <source.ogg> <theme.wav>`. Do not silently label the Chinese fallback as one of these civs. A future civ may need a newly researched/verified music mapping; record that choice in its plan.

Campaign narration and music are separate: do not use a speech event as a music bed. With speech, the current renderer targets approximately -17 LUFS for narration and -31 LUFS for music, with fades and a limiter. Without speech it uses a different music level. Listen to the resulting encode; a loudness command does not ensure musical/editorial quality.

## Narration and character-by-character text

The approved approach uses a user-authorized clone of the campaign narrator, not a “closely matched” library voice. Existing permission from the owner applies where its scope covers the source; preserve that provenance. A new operator/account/source must have the corresponding authority. Do not claim permission merely because a script's default description says so.

### Find and extract the correct narrator

Check the selected campaign/scenario's narration event in the installed config/catalog. [extract_intro_reference.py](../../apps/video/extract_intro_reference.py) resolves a direct Wwise Event → Play Action → streamed Sound → media ID from the English packages. It fails explicitly on unsupported compound structures instead of guessing a clip.

```powershell
$VoiceDir = Join-Path $Repo '.tools\intro-voice\new-campaign'
& $Py apps/video/extract_intro_reference.py --event PLAY_GEO1S1 `
    --output $VoiceDir --decoder .tools/vgmstream/vgmstream-cli.exe
```

This event is a **Georgian example**, not a default for every unit. Past verified events include Wei `PLAY_WEI1S1`, Art of War fallback `PLAY_CM_01`, Tamar `PLAY_GEO1S1`, and Burgundian `PLAY_BRG1_INTRO`. Other civs' voice metadata/plans retain their exact events. The extractor writes WEM, WAV, and JSON mapping evidence. Listen for the expected language/speaker, clean speech, and correct clip.

Prepare a clean bounded sample without other audio layered in:

```powershell
ffmpeg -y -i "$VoiceDir\PLAY_GEO1S1.wav" -t 90 -ac 1 -ar 22050 "$VoiceDir\reference90.wav"
```

Do not trim a shorter source as though it contains 90 seconds. Probe the resulting file and retain source hashes/event/package IDs. The previous Georgian source was about 148 seconds; a 90-second sample was selected.

### Clone or reuse an active voice

Set `ELEVENLABS_API_KEY` through a trusted secret input or session environment. Do not paste the actual value into source, commands recorded in project files, plans, screenshots, commit messages, or docs. A PowerShell prompt can avoid storing the key in shell history:

```powershell
$SecureKey = Read-Host 'ElevenLabs API key' -AsSecureString
$env:ELEVENLABS_API_KEY = [Net.NetworkCredential]::new('', $SecureKey).Password
```

The plaintext necessarily exists in the process environment while requests are made; don't print it. Clear it when finished.

First inspect the relevant `*-voice-clone.json` metadata and verify that the voice remains active in the account. A metadata file can outlive a deleted profile. The clone helper now rejects `retired: true` even if the sample hash matches. Existing generated audio remains reusable after cloud profile retirement.

If a new authorized clone is necessary:

```powershell
& $Py apps/video/create_intro_voice_clone.py --sample "$VoiceDir\reference90.wav" `
    --output apps/video/intro/new-campaign-voice-clone.json `
    --campaign 'Actual campaign name' --source-event ACTUAL_EVENT --source-media-id 123456789
```

Replace the illustrative event/media ID with the **extracted JSON evidence**, not a guessed ID. This command uploads the sample to ElevenLabs and can consume account capacity. Reuse an existing active authorized voice when appropriate. The account previously had ten voice slots; the owner authorized specific Wei→Burgundian and Burgundian→Georgian replacements. Those do not authorize deleting an arbitrary future profile. If full, show the actual replaceable profile and preserve its saved narration before requesting a specific replacement/increased capacity.

### Generate narration and timings

```powershell
$Voice = Get-Content 'apps/video/intro/new-campaign-voice-clone.json' -Raw | ConvertFrom-Json
if ($Voice.retired) { throw 'Select an active voice' }
& $Py apps/video/generate_intro_narration.py --plan "apps/video/intro/$Key.json" `
    --output "$Lab\compilations\$Key-unique-units\narration-v1" `
    --voice-id $Voice.voice_id --voice-kind instant_clone
Remove-Item Env:ELEVENLABS_API_KEY
```

The generator calls ElevenLabs's timestamped speech API using `eleven_multilingual_v2`. Current settings: stability 0.65, similarity 0.75, style 0.15, speaker boost true, speed 0.9. It caches identical request/voice payloads, validates that returned characters reconstruct the requested script, adds a 0.4-second lead and 2-second final hold, and rounds page durations to the 30 fps timeline.

Keep page MP3s, timestamp JSON, padded WAVs, combined `narration.wav`, and request/provenance files. It writes `<key>-cloned.json` beside the base plan so relative art/music references remain valid. That generated plan may contain machine-local absolute paths; regenerate or deliberately remap them after migration. Cloud voice deletion does not delete the saved files, but it can prevent future speech generation with that ID.

Render preview pages before the full letter animation:

```powershell
& $Py apps/video/build_campaign_intro.py --plan "apps/video/intro/$Key-cloned.json" `
    --output "$Lab\compilations\$Key-unique-units\intro-preview" --preview-only
```

Check title-free copy, line lengths, complete illustration, safe parchment rectangle, and all special glyphs. Then render the actual intro into `intro-v1` as in the main runbook. The renderer pre-wraps complete text so words don't jump when letters appear, matches visible characters to synthesis timings, and requires a final reading hold. Intermediate letter PNGs can use gigabytes; remove only those exact derivatives after successful encode/review and retained source/narration.

## Covers and Shorts

The default is the user-approved campaign-parchment design: same background as the intro, centered unit illustration, dark historical-serif unit title and “Matchup” below. The implementation reads the same game glyph atlas. It does not assert that a guessed desktop font is identical to the game font.

[build_campaign_thumbnail.py](../../apps/video/build_campaign_thumbnail.py) creates `<key>-long.jpg` at 1280×720 and `<key>-shorts.jpg` at 1080×1920, each under 2 MiB. One vertical cover is reused for that subject's ten Shorts. Review the complete design on a phone-size preview; a valid file size does not establish legibility.

The upload API submits the cover and stores its response. YouTube cover behavior depends on the particular Shorts surface/account eligibility; verify the actual Studio/channel presentation. Do not claim an API thumbnail response proves the cover is visible everywhere. Consult [current YouTube thumbnail guidance](https://support.google.com/youtube/answer/72431) rather than old blanket claims about Shorts support.

## Release review record

Full output directory: `LAB/compilations/<key>-unique-units/final-cost-v2/`.

Expected files:

```text
<key>-complete-corrected-costs.mp4
manifest.json
youtube-description.txt
chapters.ffmeta
concat.txt
render.log
qa/full-contact.jpg
qa/shorts-contact.jpg
qa/individual frame files
visual-qa.json                       created only after real review
youtube/youtube-upload-preparation.json
youtube/youtube-proposed-settings.json
```

The builder's `reviewStatus` wording and `fullDecode: "passed"` are automated/template facts, not final approval. Use an explicit QA receipt such as:

```json
{
  "passed": true,
  "reviewedAt": "ACTUAL ISO-8601 UTC TIME",
  "reviewer": "ACTUAL REVIEWER",
  "fullVideoSha256": "ACTUAL SHA-256 OF THE REVIEWED MASTER",
  "scope": [
    "Full encode decoded successfully",
    "Encoded intro viewed and listened to",
    "Full first/middle/last battle frames inspected",
    "All ten Shorts viewed for crop, panels, HP queues and audio",
    "Special endings and identified anomalies inspected",
    "Both covers and final chapter description inspected"
  ],
  "evidence": ["qa/full-contact.jpg", "qa/shorts-contact.jpg"],
  "limitations": ["Representative full-video visual review, not every-frame human review"]
}
```

Do not copy the sample's `passed: true` until those statements are true. The supervisor currently checks existence and the `passed` flag; it does **not** independently authenticate the reviewer or enforce every evidence hash. That is why truthful review and invalidation are part of the operating procedure. Record owner review separately when requested; Taildrop is a delivery action, not approval by itself.

Full decode command for an individual final video:

```powershell
ffmpeg -v warning -xerror -threads 8 -i 'ABSOLUTE_FINAL_VIDEO.mp4' -f null -
```

Check process exit, media streams/duration, and logs. Some concatenations can emit timestamp warnings while completing; review those rather than calling the whole file corrupt or pretending no warning occurred. A final MP4 can appear stationary in size while `faststart` relocates metadata; inspect CPU/disk/log progress before interrupting it.

Chapter results use P2/P3 main-army ownership/HP at the terminal battle sample; screen units are excluded. Conversions may add originally opposing entities to the winner. The full description lists `WIN/LOSS` from the featured unit's perspective and the winning army's HP. Verify actual timestamp links and chapter UI in Studio: short battle segments may not all meet the platform's current automatic-chapter rules.

## YouTube OAuth and channel verification

YouTube uploads require an **OAuth Desktop client** with `installed` JSON configuration. A project API key alone cannot authorize uploads to a channel. ElevenLabs credentials do not authorize YouTube. The branch's uploader is intentionally pinned to the `@aoe2matchup` channel; using a different channel requires a reviewed code/settings change.

Owner setup:

1. In Google Cloud, enable YouTube Data API v3 for the project.
2. Configure OAuth consent/audience and required test users if the project is in testing.
3. Create/download a Desktop OAuth client JSON.
4. Store it at a stable private local location, e.g. `data/local/youtube/client.json`. Tokens retain that path for refresh; don't leave the only copy in a disposable attachment/download folder.
5. Run the authorization helper as the Windows user who will upload:

```powershell
& $Py apps/video/authorize_youtube.py --client 'data/local/youtube/client.json' `
    --output 'data/local/youtube'
```

That process waits for browser consent. In a separate terminal, open the URL in `data/local/youtube/authorization.json`. Choose the account/Brand Account that owns **@aoe2matchup**, not the earlier wrong personal channel. The loopback listener is temporary at `127.0.0.1:<random-port>` and expires after 30 minutes; keep the process alive through the callback.

The helper uses PKCE and state verification, requests `youtube.upload` and `youtube.readonly`, and encrypts tokens with Windows DPAPI. It never uploads a video. Inspect `data/local/youtube/status.json`: authorization complete, refresh token available, and channel ID `UCKYN-pN4AZ3w4LpRxcdSciA`. The uploader also verifies the live authorized channel/handle before transferring media.

On a new computer/user, perform consent again; copied DPAPI ciphertext is not portable. Refresh needs the stable client JSON path. For `invalid_grant`, revoked access, or expired testing consent, reauthorize with the same intended channel and preserve upload state/IDs. Do not reinsert already uploaded videos just to repair tokens.

Official references: [OAuth for desktop apps](https://developers.google.com/identity/protocols/oauth2/native-app), [upload implementation](https://developers.google.com/youtube/v3/guides/implementation/videos), [videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert). Unverified API projects can have private-upload restrictions; inspect the current project/account rather than promising public release.

## Concrete upload preparation

The single-subject supervisor generates two files alongside the upload target. They contain no OAuth token or API key.

`youtube-upload-preparation.json`:

```json
{
  "uploadAuthorized": true,
  "targetChannelVerified": true,
  "targetChannel": {"id": "UCKYN-pN4AZ3w4LpRxcdSciA", "handle": "@aoe2matchup"},
  "video": "ABSOLUTE PATH TO REVIEWED MP4"
}
```

`youtube-proposed-settings.json`:

```json
{
  "uploadAuthorized": true,
  "title": "ACTUAL UNIT vs ACTUAL COUNT Unique Units | AoE2 DE",
  "descriptionFile": "ABSOLUTE PATH TO REVIEWED DESCRIPTION",
  "thumbnail": "ABSOLUTE PATH TO COVER JPEG",
  "tags": ["Age of Empires II", "AoE2 DE", "unit matchup", "battle simulation"],
  "categoryId": "20",
  "defaultLanguage": "en",
  "defaultAudioLanguage": "en",
  "privacyStatus": "private",
  "selfDeclaredMadeForKids": false,
  "containsSyntheticMedia": true,
  "license": "youtube",
  "embeddable": true
}
```

These are schema examples, not actual approval. Use the real reviewed title, description and source. The full-video title must fit YouTube's limit; the description is checked ≤5,000 characters. Shorts have their own titles/descriptions, vertical subject cover, `#Shorts`, and `containsSyntheticMedia: false` for gameplay-only footage.

The earlier cost-audit hold may still be present globally. The supervisor adds the exact approved preparation path to `correctedMedia.approvedUploadPreparations`, allowing that validated package through the hold. Do not clear the whole audit hold or allowlist unrelated old media. A user pause blocks upload before API access.

### Transfer, retry, and completion

Manual upload/retry for a reviewed and authorized preparation:

```powershell
& $Py apps/video/upload_youtube.py --preparation $Preparation `
    --state-key "$Key-full-cost-v2" --processing-wait-seconds 0
```

The source/metadata identity includes path, bytes, modification time, metadata and channel. Keep those stable during a resumable upload. The uploader encrypts the resumable URL, queries server progress, transfers 16 MiB chunks, and saves the returned video ID **before** setting the thumbnail. A saved ID prevents a subsequent retry from creating another video.

`STARTING_SESSION` without a saved session is an uncertainty requiring inspection, not a reason to clear state. A 404/expired session, mismatched identity, quota problem, or `NEEDS_ATTENTION` needs the logged specific remedy. Preserve the state and check existing channel content/video ID before intentionally making a new upload identity.

Read-only processing refresh:

```powershell
& $Py apps/video/check_youtube_upload.py `
    --state "data/local/youtube/$Key-full-cost-v2-upload-status.json" `
    --preparation $Preparation
```

`PROCESSING` means bytes may already be fully transferred. `COMPLETE` requires remote processing `succeeded`. The package supervisor checks all eleven videos and writes an aggregate receipt, preserving current owner-modified visibility. It waits up to an hour in the final processing loop; if that expires, perform a later status check rather than another upload.

Studio may show delayed progress, quality processing, or pending checks. Distinguish transfer from processing, copyright/checks, and public publication. Verify the stored ID/channel, transfer byte counts, remote processing status, and actual Studio outcome. Never tell the user “public” merely because the transfer finished.

## Delivery and cleanup boundaries

Taildrop only when requested and to the exact named device. Find current devices with `tailscale status`, then use `tailscale file cp <file> <device>:`. Confirm command success and report what was sent; do not automatically send every batch video. The standard ongoing workflow stores locally and uploads privately.

Keep the full master, original gRPC frame streams with their plan/scenario/metadata, narration audio/timings, final descriptions/results, QA, and upload receipts. Copies of extracted music can be regenerated; generated unit art should remain in Git. Original voice narration cannot necessarily be regenerated after a profile is retired. Use the [verified archive procedure](OPERATIONS_AND_RECOVERY.md#storage-and-archive) before deleting local evidence.

# YouTube video, artwork, thumbnail and description handoff

Use this guide after selecting existing recorded matchups. It connects the
approved full-video presentation, generated unit artwork, cover composition,
chapter/results description and upload workflow. Updated September 24, 2026.

The default landscape cover is the approved **campaign intro parchment**:
same background as the intro, the unit illustration centered, and the unit name
with "Matchup" underneath. This is recorded in
[thumbnail-style.json](../../apps/video/thumbnail-style.json). Do not infer a new
cover style from an experimental preview or a Shorts treatment.

## 1. Inputs and workflow boundaries

Start from the selected archive's named raw MP4s, frames and `run.json` metadata.
Keep exact source job IDs and correction precedence. Rendering a new overlay,
thumbnail or description does not require another game capture. Distinguish
results available as metadata from footage available for rebuilding.

For civilization comparisons, use the
[comparison/ranking handoff](CIVILIZATION_COMPARISON_GUIDE.md) to select chapters.
Its three top-25 lists can be presented as top 10. Those editorial lists are
different from the per-chapter best-winner tally and from the full video's
chronological chapter list.

One prepared package needs: the selected chapter order; source results/counts;
reviewed intro text and art; campaign background/font/music references; narration
and alignment if used; assembly manifest; thumbnail; description; all chapter
results; QA evidence; and upload preparation/settings. Credentials remain private
and are not part of the reproducible asset bundle.

## 2. Generate or reuse the unit illustration

1. Look for suitable installed campaign artwork and an already approved asset in
   `apps/video/intro/assets/`. Reuse correct artwork before generating another.
2. If needed, supply the exact unit portrait/sprite as the image-generation
   reference. Verify the upgraded version, weapon, helmet, armor, pose, mount and
   complete silhouette. Do not invent equipment from the civilization's name.
3. Generate the illustration independently of the title and background. Use the
   established monochrome graphite/dark-sepia crosshatched campaign style, soft
   unfinished edges, and genuine transparency or white for multiply compositing.
4. Save reference identity, exact prompt, selected output and review notes. Check
   anatomy and equipment against the reference, then inspect it on the parchment.
   A drawn checkerboard is not transparency. Keep the full figure inside the art
   area; repair an incorrect head/weapon before building the final cover.

Reusable starting prompt, to be adapted to the actual reference:

> Draw this exact AoE2 unit as a complete campaign illustration, preserving the
> reference equipment, pose, helmet, weapon and mount. Monochrome graphite and
> dark sepia ink, fine crosshatching and soft unfinished edges. Plain white or
> transparent background for compositing. No lettering, border, paper rectangle,
> scenery or checkerboard. Keep the whole unit visible.

The image-generation step is separate from `build_campaign_thumbnail.py`; that
script **composes an existing illustration**, not an AI-generated new unit.
See [artwork and campaign selection](MEDIA_AND_PUBLICATION.md#campaign-background-and-copy)
and the historical [saved thumbnail prompts](../../apps/video/intro/thumbnail-prompts-v2.json).
Those prompts contain old reference paths: relocate retained references rather
than treating an unavailable path as a reason to regenerate approved art.

## 3. Build the thumbnail from the approved intro assets

Resolve the civilization theme through `campaign_catalog.json`, including any
explicit `backgroundTheme` in the intro plan. Use the actual clean installed
campaign background, not a screenshot containing old text or buttons. Wei's
approved visual fallback is Art of War. Record an explicit fallback for a new
unmapped civilization. The same choice must appear in the intro and cover.

The [thumbnail composer](../../apps/video/build_campaign_thumbnail.py) reads the
plan's `civilization` and `art`, the adjacent campaign catalog, the game background
and `GameFont` glyph atlas. It multiplies the artwork onto parchment while
respecting alpha, centers the illustration, and fits the title below it. Its
fixed placement needs visual review for each new parchment shape or long title.

Example command, with a real reviewed plan and an unused output prefix:

```powershell
$env:PYTHONPATH='apps/video;.'
apps/video/.venv/Scripts/python.exe apps/video/build_campaign_thumbnail.py --plan 'apps/video/intro/elite-obuch.json' --prefix 'data/local/cover-review/elite-obuch' --title 'Elite Obuch' --subtitle 'Matchup'
```

Use the corresponding plan/art for a different subject. The installed game/font
paths must resolve on the rendering machine. The composer writes both
`<prefix>-long.jpg` (1280 x 720) and `<prefix>-shorts.jpg` (1080 x 1920), and checks
each is below 2 MiB. It overwrites those outputs, so do not target an approved
archive copy while experimenting. A comparison cover may use "Four Civilizations
Compared" as the subtitle, as in the knight package builder.

Review at small viewing size: recognizable unit, correct equipment, readable
title, generous parchment margins, no cropped head/weapon, no stats or counters,
and no flashy effects. Keep the selected cover and underlying art/plan. One
vertical cover per subject can be reused; do not promise the thumbnail API makes
a Shorts cover visible on every surface. Verify its actual presentation when
publishing. The latest Short video treatment is documented separately in
[SHORTS_APPROVED_WORKFLOW.md](SHORTS_APPROVED_WORKFLOW.md).

## 4. Assemble the full video and measure its timeline

For the approved four-civilization comparison format:

1. Render the selected battle chapters with the accepted crop and overlay. Show
   starting counts, the result/remaining HP and cumulative tally. Preserve game
   sound and music. Reuse valid renders whose inputs and renderer match.
2. Intro page 1 uses generic unit background/ability text, campaign art, spoken
   narration, character-aligned text reveal and quiet music.
3. Intro page 2 begins with civilization emblems. Reveal each full civilization
   column as its short observation is spoken. Cards show relevant stats, named
   unique technologies and effective civ/team bonuses; the observation sentence
   need not be printed. Hold three seconds after speech before the battles.
4. End with the matching parchment and sketched YouTube emblem, thanking viewers
   and asking them to like and subscribe. The established ending lasts five seconds.
5. Concatenate the two intro pages, battle series and ending. Verify codec,
   resolution, frame rate and audio compatibility before stream-copying video.
   Normalize audio timestamps to avoid discontinuities at AAC joins.

Use [the overlay guide](CHAMPI_COMPARISON_OVERLAY.md),
[approved refinements](CHAMPI_UI_REFRESH.md), and
[intro/ending commands and timing](CHAMPI_COMPARISON_BOOKENDS.md).
Single-subject episodes have their own two-page intro described in
[MEDIA_AND_PUBLICATION.md](MEDIA_AND_PUBLICATION.md); do not substitute the
four-civilization layout into every episode.

The comparison `assembly-manifest.json` records `firstPageSeconds`,
`matchupStartSeconds`, `endingStartSeconds`, the actual final duration and part
paths. Each series chapter retains its rendered file and results. Obtain chapter
starts from **encoded durations**, not guessed narration length, raw capture
time or an old intro offset:

```text
first battle start = measured page-1 duration + measured page-2 duration
next battle start = current battle start + measured encoded chapter duration
ending start = first battle start + sum(encoded chapter durations)
```

The existing `stamp()` floors seconds for description timestamps. Keep full
precision while accumulating, then format each displayed timestamp once. Verify
the sum against the assembly's ending start and inspect the actual transitions.
Any changed intro, order or chapter length invalidates downstream timestamps,
description and QA. MP4 chapter metadata and YouTube description timestamps are
separate deliverables; embedding one does not generate the other automatically.

## 5. Description: rules, links, winners, losers and HP

Build it from the final assembly and selected recorded results. Include:

- A short explanation of the featured unit/family and actual opponent count.
- The **saved capture rules**: count/cost balance, cap, discounts, buffer and any
  special settings such as four relics. Use [BALANCE_POLICY.md](BALANCE_POLICY.md)
  for new v3 captures; never relabel old recordings with the latest formula.
- `Try your own matchup:` and the website link with the intended civilization,
  exact unit slug and age selected. Check the URL values against the source plan.
- `00:00 Introduction`, any later intro section, chronological battle timestamps,
  opponent names, result/remaining HP, and the ending timestamp.
- Relevant tags such as `#AoE2 #AoE2DE #RTS #BattleSimulation #UnitCounters`, plus
  the actual subject/civilizations. Use `#Shorts` for Shorts, not by default here.

For new v3 footage, appropriate rules text states that the cheaper main army gets
27 physical units, the other count uses geometric weighted-cost balance, food /
wood / gold weights are 1 / 0.9 / 1.1, and discounts count fully. Ranged units
receive a small Hussar front line against melee, scaled from their actual fielded
weighted cost. This is **not equal spending**. Historical episodes keep their
actual rules, including fixed buffers where applicable.

Result semantics must be explicit:

- W/L is from the tested unit's perspective. Main owners are P2/P3; exclude the
  support screen. For W, remaining HP belongs to the tested army; for L, it
  belongs to the surviving opponent. Preserve conversion-aware ownership.
- Keep HP totals and starting-HP denominators in the result data. Where using a
  percentage, normalize to the survivor's own starting army. Do not describe
  the opponent's HP after a loss as the tested army's remaining HP.
- The historical comparison upload helpers list **the best per-chapter result**
  and all tied best civilizations in the public description. They save **every
  civilization's result and starting counts** in `chapter-results.json`.
  They do not currently print a complete four-civilization W/L matrix per chapter.
- The report's under-10% draw adjustment is a ranking convention. Existing video
  result helpers consume the rendered chapter results; they do not automatically
  apply that adjustment. Keep the legend consistent with the displayed video.

Illustrative formatting only, not real results or timestamps:

```text
01:12 Composite Bowman | Incas W 43%
01:50 Teutonic Knight | Mapuche/Muisca L 22%
```

The second line means the tied best tested civilizations still lost and the
opponent retained 22%. A single-subject description can instead name its opponent
and WIN/LOSS plus remaining HP directly. If a new presentation requires every
civilization's results in the description, derive them from `chapter-results.json`,
use an explicit compact legend, and check the final length. That is an adaptation,
not something the existing best-result summary already does.

The builders enforce a description of at most 5,000 characters and title of at
most 100. Shorten prose or use agreed abbreviations before dropping required
chapter details; never silently truncate the final list. Check resulting links
and chapter behavior on the actual upload.

Apply [youtube-description-style.json](../../apps/video/youtube-description-style.json):
omit the narration-disclosure paragraph, the single-trial disclaimer, and the
phrase saying the unit is already selected. Keep the actual selected-unit URL
under "Try your own matchup:". The separate synthetic-media upload setting is
independent of those prose omissions. Historical builders do not all load this
style JSON automatically; inspect the generated text instead of assuming they do.

## 6. Known helper limits, review and upload

[prepare_champi_comparison_upload.py](../../apps/video/prepare_champi_comparison_upload.py)
and [prepare_knight_comparison_upload.py](../../apps/video/prepare_knight_comparison_upload.py)
are working **episode-specific examples**. They contain fixed 74-chapter checks,
historical policy wording, profiles/paths and authorization prose. Before adapting
them, derive the roster count, rule text, selected-unit link and result semantics
from the intended package. Do not merely rename a unit or remove an assertion.
The thumbnail helper composes approved art but does not generate it. These limits
are also noted in the code comments.

Preparation writes the description, all chapter results, thumbnail/settings
references and the final video path. It is not an upload or a review approval.
Inspect the actual encoded opening, transitions, battle crop/results, closing
page, audio and cover; decode the completed video and verify chapter coverage.
Record what was actually reviewed, including limitations, against that final
master. Do not fabricate approval from a template's `passed` field.

The [publication guide](MEDIA_AND_PUBLICATION.md#youtube-oauth-and-channel-verification)
documents OAuth setup, private upload settings, channel verification, resumable
uploads and processing checks. YouTube needs OAuth; an API key alone is insufficient.
The uploader verifies `@aoe2matchup` and saves the returned video ID before setting
the cover. Preserve its state on retry to avoid duplicate uploads. Do not report
completion merely because bytes transferred; verify processing and the actual
thumbnail/description. New machines must obtain their own authorized credentials.

Retain the raw MP4/frames and reconstruction metadata, approved art/prompts,
intro plans, generated narration/alignment, final master, chapter/results data,
cover, description, QA and upload receipts. See
[RECORDING_RETENTION.md](RECORDING_RETENTION.md). Rendering derivatives can be
regenerated; approved art and retired-voice narration may not be reproducible
identically. Never delete source evidence or external-drive contents just to
rebuild a thumbnail or description.

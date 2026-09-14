# Installed campaign intro assets

Verified locally on 2026-09-08. Installation root: `C:/Program Files (x86)/Steam/steamapps/common/AoE2DE`.

All three user references have matching installed backgrounds and independent illustrations. The backgrounds are opaque 5672 × 2160 DDS files containing the painted environment, parchment, and border together. They contain neither narration text nor navigation buttons. The illustrations are 2000 × 1048 PNGs with transparency.

Paths below are relative to the installation root.

| Reference | Background | Matching illustration |
|---|---|---|
| Tamerlane, Indian elephant army | `widgetui/textures/campaign/kcam1/tamerlane_background.dds` | `widgetui/textures/campaign/kcam1/4/outro/1.png` |
| Le Loi, Dai Viet introduction | `widgetui/textures/campaign/rcam4/leloi_background.dds` | `widgetui/textures/campaign/rcam4/1/intro/1.png` |
| Jadwiga, return toward Krakow | `widgetui/textures/campaign/eecam2/jadwiga_background.dds` | `widgetui/textures/campaign/eecam2/1/intro/11.png` |

The corresponding files in `resources/_common/campaign/` are `kcam1.json`, `rcam4.json`, and `eecam2.json`. They provide background references, illustration sequences, text rectangles, slide durations, fade durations, and audio event names. The screenshot text is stored separately as English string IDs 225451, 224101, and 233111 respectively. Some campaign JSON files contain comments or nonstandard numeric literals; strict JSON parsers need to accommodate that.

`widgetui/scenarioslideshow.json` defines separate Background, SlideImage, SlideText, and navigation widgets on a 3840 × 2160 logical canvas. Its background image viewport is 5120 × 2160 and centered; the source DDS dimensions differ, so the compositor must follow viewport placement rather than stretching the whole source directly into 16:9.

## Font resources

The SlideText widget specifies FontIndex 0, PointSize 60, Style Normal, and ink RGBA (57,28,27,255). English string 213 is explicitly documented as the campaign slideshow font size and is also 60. These are logical game units, not necessarily output video pixels.

The installed serif glyph atlas is `resources/_common/fonts/combined.txt` plus `combined_0000.png` through `combined_0005.png` (DDS versions also present). It contains 7,697 glyphs generated at a source pixel size of 64. The existing `GameFont` renderer in `apps/video/overlay/static_stats.py` already reads these assets, so we can reuse the game's glyphs without substituting a visually similar desktop font. The exact runtime FontIndex-to-atlas binding and final screenshot rasterization have not yet been independently traced; no specific TTF family is claimed as an exact match.

The installation also contains Century, Georgia, Lucida Bright, Times New Roman Bold, and Trajan font files. Their presence alone does not identify the campaign font.

## Intro construction implications

- Use the clean background directly; its blank parchment is ready for custom text.
- Add the unit illustration as a separate layer. Existing historical character sketches can be reused as appropriate; a Tiger Cavalry-specific campaign sketch has not been identified in this audit.
- Render custom narration/title text separately using the installed glyph renderer.
- Omit navigation widgets and retain the supplied frame/environment artwork.
- Preserve the source assets in the game installation. Preview conversions are stored in `aoe2x/js_simulation/calibration/lab/analysis/campaign-intro-assets/`.

There are 44 DDS filenames containing "background" under `widgetui/textures/campaign`, so the three references are not the only available visual themes. This audit identifies source assets; it does not yet create or prepend the final intro video.

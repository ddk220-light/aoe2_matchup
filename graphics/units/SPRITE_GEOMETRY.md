# Native unit sizing

The simulator now uses the original game artwork’s relative pixel scale, with
Halberdier’s existing displayed height as the reference. It does not normalize
people by the height of a bounding box that includes their weapons.

## Extracted evidence

`unit_sprite_geometry.json` covers all **223 published unit sprites**. It records
source graphic names and hashes, resolved unit IDs (or the existing asset
resolver’s explicit overrides), frame indices, native canvas dimensions,
hotspots, tight crop rectangles, and the published web dimensions.

Source installation used for this extraction:

- Steam app 813780, installed Steam build ID `24094652` (not a game balance patch ID).
- `AoE2DE/AgeOfEmpires2Data/resources/_common/dat/empires2_x2_p1.dat`.
- Graphics from `resources/_common/drs/graphics/*.sld` in that same installation.
- Exact DAT and individual source file hashes are stored with the evidence.

The extractor mirrors the existing idle asset pipeline: first nonempty frame
of direction 06, with the shadow composited at 55% before tight cropping.
Measurements use x1 pixels; x2 sources are divided by two when available.
This Mac installation provided x1 sources. The published web artwork was made
from upscaled source graphics, so minor edge/crop differences remain: the largest
native-to-web aspect ratio difference in this extraction is **5.2%**. A difference
above 10% fails extraction and requires checking the source asset/pose.

| Sprite | Native crop height | Image-height multiplier vs Halberdier |
| --- | ---: | ---: |
| Halberdier | 48 px | 1.00 |
| Archer | 46 px | 0.96 |
| Champion | 54 px | 1.13 |
| Elite Kamayuk | 95 px | 1.98 |
| Paladin | 74 px | 1.54 |
| Elite Battle Elephant | 104 px | 2.17 |
| Hussite Wagon | 102 px | 2.13 |
| War Wagon | 116 px | 2.42 |

These are **full image crop heights, not anatomical body heights**. The Kamayuk
is not a person twice as tall: its pike makes the image taller. Using one common
scale for native pixels preserves the person’s proportions beneath that pike.
Small differences in human height and pose remain as drawn by the game artists.

## Renderer behavior

The generated `aoe2x/js_simulation/viewer/unit-sprite-geometry.js` provides native
heights without adding a runtime dependency on a game installation. The renderer
multiplies its existing reference height by `nativeHeight / 48`. Published image
height is then used only to undo the image exporter’s resizing.

The same correction applies to idle sprites and the existing calibrated attack
sheets. Attack-sheet crop compensation is retained; this extraction does not
replace or revalidate the attack asset pipeline. Ground offsets are also retained.
Hotspots are recorded for future alignment work but do not change placement in
this update. HP bar and additional ground-shadow sizes remain independent of
weapon height. Collision sizes, reach, movement and combat outcomes are unchanged.
Unrecognized future units retain the previous visual-class fallback until their
sprite metadata is regenerated.

## Regenerate

Install `genieutils-py`, `Pillow`, and `numpy` in a tools environment, then run:

```sh
python graphics/units/extract_sprite_geometry.py --game-data /path/to/AgeOfEmpires2Data
```

On Windows, pass the AoE2DE folder containing `resources` directly. No image
upscaling or image export is required. Regenerate after changing source sprites
or the published sprite manifest; review the evidence and runtime module together.

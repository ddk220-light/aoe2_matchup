# graphics/units — Per-unit reference assets (player-2 red)

Each unit folder holds exactly **6 finalized, git-tracked files** — the red (player 2)
reference set. No subfolders or intermediate frames are kept.

```
graphics/units/<slug>/
  icon.png                              256px game UI icon, opaque
  icon_transparent.png                  same icon, background removed
  <slug>_idle_dir06.png                 native red idle pose (dir06)
  <slug>_idle_dir06_dat4x.png           4x idle pose — DAT (red + shadow, supersampled)
  <slug>_idle_dir06_ultrasharp4x.png    4x idle pose — UltraSharp
  <slug>_attack_dir06_dat4x.gif         transparent DAT-4x attack animation (single pass)
```

## Workflow — produce the 6 files for any unit

1. **Find the unit's SLD stub + icon_id.** The elite idle sprite is
   `graphics/game_raw_files/<stub>_idleA_x2.sld` (or under the AoE2:DE install at
   `resources/_common/drs/graphics/`); `<stub>` is e.g. `u_cav_kona_elite`. The `icon_id`
   comes from the dat via genieutils (conda `python`):
   ```python
   from genieutils.datfile import DatFile
   df = DatFile.parse('D:/SteamLibrary/steamapps/common/AoE2DE/resources/_common/dat/empires2_x2_p1.dat')
   for uid, u in enumerate(df.civs[0].units):
       if u and 'EKONA' in (u.name or '').upper():   # match the ELITE unit (often E-prefixed)
           print(uid, u.name, u.icon_id)              # icon DDS = <icon_id>_50730.DDS
   ```

2. **Register it** in the `UNITS` dict in `build_unit_assets.py`:
   `'slug': ('<elite SLD stub>', <icon_id>)`.

3. **Run the finalizer** (visomaster env — torch + spandrel + scipy; upscale models in
   `.scratch/tools/models/`):
   ```bash
   C:/Users/ddk22/miniconda3/envs/visomaster/python.exe graphics/units/finalize_units.py --slugs <slug>
   ```
   It produces all 6 files and deletes everything else, skipping work already done (existing
   idle refs, an already-transparent attack GIF) — safe to re-run. Foot units finish in a
   minute or two; large mounted units take longer (the per-frame DAT upscale dominates).

**Facing convention: dir06** of the 16-direction wheel is the canonical reference facing
(verified per-unit against the icon — see [[aoe2-unit-art-pipeline]]).

### Pipeline scripts (building blocks the finalizer orchestrates)

| Script | Role |
|---|---|
| `build_unit_assets.py`    | `UNITS` registry; icons (opaque + transparent); native idle pose; `decode_red` / `decode_shadow` / `enhanced_pose_ref` helpers |
| `upscale_refs.py`         | the two upscaled idle PNGs (DAT + UltraSharp); `upscale_rgba` (supersampled) / `upscale_rgba_single` |
| `build_gifs.py`           | native-res animation GIFs (matte) — diagnostics |
| `build_gifs_upscaled.py`  | upscaled animation GIFs / transparent WebP |
| `finalize_units.py`       | **the one command** — emits the 6-file set + cleanup |

### Upscaling (idle refs + attack GIF)

The idle refs composite the SLD **shadow layer** (soft BC4 ground shadow, `decode_shadow`)
under the red main, then upscale **halo-free + supersampled**: edge-bleed RGB → model 4x
twice (16x) → Lanczos down to 4x → recombine with Lanczos-upscaled alpha. Supersampling
matters for small (<128px) foot sprites where a single pass amplifies BC1 block artifacts.
The attack **GIF** uses a **single** DAT pass (faster, fine for a GIF). Model bake-off
(2026-06-12, on Kona): **UltraSharp 4x** = crispest, **DAT 4x** = most natural; Remacri
over-sharpens, Real-ESRGAN x4plus too smooth, Lanczos = soft baseline. The SLD UNK(0x04)
layer is an offset table, not pixels — nothing usable there.

---

## How AoE2:DE encodes player color (discovered 2026-06-12)

### Icons — the alpha channel IS the player-color mask

Unit icons live at `AoE2DE/widgetui/textures/ingame/units/<icon_id>_50730.DDS` (256×256).
They look grey/washed-out and Windows thumbnails render them as black silhouettes. Reason:

- **RGB** = the full detailed render, with player-color cloth as shaded grey placeholder.
- **Alpha** = NOT transparency. It is the **player-color mask** the game shader uses:
  low alpha (≈0–200) marks team-color regions; ~255 everywhere else.

Apply a team color with:

```
m   = (255 - alpha) / 255            # mask weight
L   = luminance(rgb)                 # 0.30 R + 0.59 G + 0.11 B
out = rgb * (1 - m) + L * TINT * m   # fully opaque output
```

Validated by reconstructing the AoE2 wiki's blue icons (they're game renders, not hand-
painted) from the grey DDS to ~2.8/255 mean abs error. Measured blue tint ≈ (0.19, 0.74, 1.41);
our player-2 red is `ICON_TINT = (1.35, 0.27, 0.23)`.

Notes:
- The legacy `50730.slp` icon sheet only has 134 frames — DLC units (Kona 546, Guecha 544,
  Blackwood Archer 550) exist only as DDS.
- Grey-detection recoloring does NOT work: the placeholder grey is identical to e.g. the
  Kona's horse grey ([109,95,84] vs [113,104,95]). Only the alpha mask separates them.

### Icon background removal (icon_transparent.png)

The DDS bakes the background as **opaque black** (alpha 255, RGB 0). To remove it we
flood-fill near-black inward from the border (`_bg_alpha`): that reaches the exterior bg
but not the figure's interior dark bits (walled off by the lit silhouette). A border-zone
extension clears the faint ~1px outer frame (luminance ~16-24). The opaque `icon.png` is
kept; `icon_transparent.png` is the cut version.

Enclosed background pockets the flood can't reach (the gap **inside a drawn bow**, the wedge
between a horse's head and the rider) are then removed generally: any **continuous** near-black
component of **>= 100 px** is cut. Two things make this safe on mounted units: the threshold is
**true black (lum < 4)** so a horse's slightly-lighter dark fur (~5-7) doesn't bridge a pocket
into the body, and the 100px size floor leaves scattered dark texture (individual strands)
alone. No per-unit config needed.

### Sprites (SLD) — BC4 mask layer + multiply

SLD frames carry a separate BC4 player-color mask layer (decoded by
`graphics/sld_decode.py:_decode_player_mask`). Apply color by **multiplying** the tint into
the base pixels inside the mask — this keeps the baked cloth shading ("shadow detailing").
`SPRITE_TINT = (0.86, 0.18, 0.16)` for player-2 red.

Do NOT use `sld_decode.PLAYER_COLORS` (two-point lerp) — it produces neon, unshaded color.

### Things that are team color, not unit design

The grey placeholder hides what's actually player-colored. Caught so far:
- **Kona**: headband, cape, shield star, spear pennant, tunic trim (horse stays grey).
- **Guecha Warrior**: the entire robe (gold patterning preserved on top of it).
- **Blackwood Archer**: the dot/circle war paint and feather accents.

Unit descriptions for AI generation must treat these as red (player 2), not white/grey/blue.

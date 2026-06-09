# FLUX.2 Unit Art Workflow (Elite Unique Units)

A repeatable recipe for generating high-detail, **pose-faithful + design-accurate** character
renders of AoE2:DE elite unique units, using FLUX.2-dev (4-bit) with multi-angle sprite references
+ the in-game icon. Proven on Temple Guard, Janissary, Berserker, Paladin.

## Environment
- Diffusion env: `C:/Users/ddk22/miniconda3/envs/visomaster/python.exe` (torch 2.8 cu129, diffusers 0.38, bitsandbytes 0.49, RTX 5090).
- Model: `diffusers/FLUX.2-dev-bnb-4bit` (cached, ~32 GB). Load with `Flux2Pipeline.from_pretrained(..., torch_dtype=bfloat16)` + `enable_model_cpu_offload()`.
- rembg cut: base conda `C:/Users/ddk22/miniconda3/python.exe` (`new_session('isnet-general-use')`).
- SLD decode: `graphics/sld_decode.py` (`D.parse`, `D.decode_main(player_color=None)`, `D._finish(crop=True, margin=4)`).

## Inputs per unit
- **Sprite**: `graphics/game_raw_files/<u_*_elite_idleA_x2.sld>` (idle animation; 16 angles; `fc = len(frames)//16`).
- **Icon**: `webapp/static/img/units/Elite_<Name>.png` (256×256 canonical art — the color/identity source).

## Step 1 — Reference set (TWO references only)
- `image 1` = **dir05** idle frame (frame `5*fc + 0`) — the POSE ANCHOR; rendered at the output size.
- `image 2` = the unit **icon** (colors / markings / identity / equipment).
- Compose the sprite frame on neutral gray (RGB 70,70,74) via its **own alpha** (NOT edge-bleed — that smears).
- **Icon min size:** FLUX.2 rejects reference images smaller than 64px ("Image too small"). Some icons are 48×48 palette PNGs (e.g. Blackwood Archer, Bolas Rider, Temple Guard) — upscale them to 256px (NEAREST for pixel-art) before passing as the icon reference.
- Output canvas: from the dir05 aspect. Tall units → `H=1024, W=round16(1024*aspect*1.12)`; wide/mounted (aspect≥1) → `W=1024, H=round16(1024/aspect)` (landscape).

> **Do NOT use multi-angle references** (feeding dir01/09/13 as extra refs). It was tested on Batch 1 and made FLUX.2 emit a **turnaround/grid** (several angles in one image) and stray **emblems/nameplates**, even with anti-grid text. The clean single-figure units (Janissary, Temple Guard, Berserker, Paladin) all used **only dir05 + icon**. Keep it to two references.

## Step 2 — Two-pass prompt (the key quality lever)
**Pass 0 — RESEARCH the unit first.** Look up the unit + its weapon on the AoE2 wiki (the `aoe2onlinereference` skill) so the description is historically/visually correct. This caught: Arambai throws *feathered darts* (sharp metal point + feather tail) from a *Manipuri pony*; Bolas Rider (Mapuche) throws a *bolas* = three rope-linked stone weights; Blackwood Archer is a lean bare-chested *Tupi* foot archer. Don't guess weapons — name them precisely.

**Pass 1 — DRAFT, covering every category explicitly:**
head/helmet/hat · hair · face · shoulders · torso/armor · weapon · shield · **mount (if any)** · colors.

**Pass 2 — CRITIQUE against the reference (zoom into the icon!):**
- Verify each category against the icon (and sprite). **Fix mistakes** (e.g. "winged helmet" → "two curved horns"; vague "visored helmet" → "bascinet with pointed snouted visor + eye-slit").
- **Add missing detail** (e.g. striped collar; gold-trimmed pauldrons; horse in segmented steel-plate barding + caparison).
- Remove misleading words (FLUX has no negative prompt — describe the truth positively; if the sprite shows something different from canon, state which to follow, e.g. "broadsword, NOT a lance").
- Always zoom the helmet/head and any mount — that's where errors hide.
- **Keep weapons/equipment MINIMAL.** Over-describing accessories makes FLUX pile on clutter. Naming "a handful of darts / a fan of arrows" gave the Arambai a whole quiver of arrows; listing "barrels of spare bolts + wicker baskets" buried the Ballista Elephant in cargo. Name the ONE primary weapon, state the count ("a SINGLE slim dart, not a bundle"), and explicitly forbid the extras you don't want.

## Step 3 — Generate (FLUX.2)
```
pipe(image=[dir05, icon], prompt=PROMPT, height=H, width=W,
     num_inference_steps=44, guidance_scale=4.0,
     generator=torch.Generator('cuda').manual_seed(7))
```
Prompt skeleton (two refs; single figure + no-emblem + tone clauses are mandatory):
> "Reference image 1 is a sprite of the AoE2 <Name> unit — use it for the EXACT pose and facing. The final image is its official icon — use it for colors and equipment. The unit is <RESEARCHED + CRITIQUED DESCRIPTION>. Render **ONE SINGLE full-body figure** standing in the exact same pose, body angle and facing direction as image 1[, keeping the animal/mount and everything carried on it together as one subject]. **Plain solid neutral studio background and nothing else: no text, no logo, no emblem, no crest, no banner, no nameplate, no base or pedestal, and NO inset image, no thumbnail, no picture-in-picture, no small framed icon in any corner — just the single character.** <TONE> Sharp, highly detailed, professional game character art, one subject only, one view only."

- **No-inset clause is mandatory.** FLUX will sometimes copy the reference icon into a corner as a little picture-in-picture thumbnail (happened to Blackwood Archer). The "no inset image, no thumbnail, no picture-in-picture, no small framed icon in any corner" wording suppresses it.
- **`<TONE>` — match the game's grounded look.** Default FLUX renders come out too bright/glossy; the AoE2 icons are darker, muted, weathered. Use: *"Render it with a darker, muted, slightly desaturated historical color palette and soft realistic lighting, with weathered matte textures and natural shadows — the grounded, slightly somber, painterly look of an authentic Age of Empires 2 unit portrait. Not bright, not glossy, not neon, not cartoonish."*

- ~110–230 s/render on the 5090 (single figure, 2 refs). If anything still looks off (wrong helmet/weapon, an emblem, a second view) → tighten the description / no-emblem clause and re-run (seed 21).

## Step 4 — Cut + save
- rembg `remove(session=isnet-general-use)` → `getbbox()` crop → transparent PNG.
- Save 3 forms to `graphics/art/flux2_hybrid/`:
  - `<slug>_idle_dir05_bg.png`   — full-res WITH background (raw render)
  - `<slug>_idle_dir05_nobg.png` — full-res transparent
  - `<slug>_idle_dir05_icon.png` — 256×256 transparent, full-body centered (margin 0.96)

## Step 5 — Review delivery (Tailscale)
- Build an HTML gallery (icon vs render per unit), serve with `python -m http.server <port>` bound to the Tailscale IP (`dragonstar` = 100.123.128.35).
- Open `http://100.123.128.35:<port>/` on the phone (`iphone172`) to approve / request changes.

## Batch cadence
- 5 units per batch, alphabetical by display name.
- Skip already-done: Berserk, Janissary, Temple Guard (+ Paladin, a non-unique test).
- Exclude obvious generics (Skirmisher). Ships/mounted/elephants use the landscape canvas rule.

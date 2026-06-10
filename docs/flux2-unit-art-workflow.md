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

### PREFER A SHORT PROMPT — let the sprite carry the form (key lesson)

Over-prompting *fights* the sprite. Piling on per-element micro-descriptions and walls of "NOT this, NOT that" produced stiff, half-invented figures and needed 4+ re-runs (Woad Raider). **Trust the dir05 sprite for build/proportions/shield-shape/kit, the icon for colour, and keep the prompt to a few sentences.** A short prompt one-shot the Woad Raider better than 4 iterations of a long one — including a *more* faithful shield.

Short skeleton:
> "Image 1 is a sprite of the AoE2 `<Name>` (`<one-line who/what>`); the final image is its official color icon. Render ONE SINGLE faithful, highly detailed full-body figure of this exact unit, matching the sprite's build, `<weapon>`, `<shield>` and kit, in the same pose and three-quarter facing as image 1, using the icon for colours. One subject, one single view, plain neutral studio background, muted weathered historic tone."

- **Add LIGHT hints only for what the references can't show.** The icon is usually a bust, so legs/footwear are missing and the sprite's are tiny → name those explicitly (Woad Raider needed "long dark pinstriped braccae trousers tucked into boots"; helmet-plume colour needed "BLUE crest"). Everything the references *do* show, leave to the references.
- **Multi-angle refs are a DEAD END for a single output** (tested twice): passing dir01/09/13 as *separate* refs → 2×2 turnaround; stitching them into a 2×2 *composite* ref → still a 2×2 output (plain `diffusers` Flux2 mirrors the reference layout; the ComfyUI "Flux Klein Ref Grid" node is not equivalent). The quality people attribute to multi-angle is really just the **shorter prompt**. If you ever truly need the turnaround look as one image, render the grid and crop+upscale the best panel.

## Recurring feedback → apply these PRE-EMPTIVELY

Patterns learned from per-unit review. Bake them into the description before the first render to avoid a re-run:

1. **Hands gripping bows/blades are FLUX's #1 weak spot.** A nocked/drawn arrow almost always renders mis-aligned, and two hands on a hilt come out malformed. Defaults that dodge it:
   - **Archers:** hold the bow *at rest*, **no arrow nocked**, all arrows in the back quiver. State "ONLY the bow, no arrow on the string, no loose arrow in the hands."
   - **Swordsmen:** if a clean grip keeps failing, render the sword **sheathed at the hip** with hands relaxed at the sides (you may have to relax the "exact same pose as image 1" instruction to let the arms drop).
2. **Confirm the weapon from the SPRITE, not the icon or assumption.** Decode the dir05 sprite when a weapon is ambiguous — this caught the Leitis wielding a *spear*, not a sword. Stat-card lore can lie; the model art is truth.
3. **Match the icon's exact shield heraldry / emblem.** Generic "decorated shield" drifts. Name it: Konnik = blue field + gold dome boss + 4 gold spokes; Leitis = white double-barred cross on blue; Serjeant = white griffin; Monaspa = blue Bolnisi crosses.
4. **State every material/colour explicitly — FLUX defaults to "generic fantasy."** Horse colour (Mangudai = *dark* horse), barding metal (Leitis = *silver-iron*, not gold), "brown leather" vs "steel" chest, helmet plume colour (Mangudai = *red* plume). If you don't say it, you'll get light-brown horses and gold everything.
5. **"More gold" means naming the parts.** Under-gilding is common. Spell out gold pauldrons, gold belt/sash, gold shield-rim, gold robe trim — not just "gold trim."
6. **Low-res (48 px) icons → decode the sprite for detail, or ask the user for a hi-res pic.** Champi Warrior and Ibirapema have 48 px icons; the user-supplied 256 px Champi pic produced a far better render. The repo has no icon at all for a few (Ji Infantry) → go sprite-only (single ref).
7. **Non-humanoid subjects need their own subject clause** (the figure clause produces grids/duplicates): ships → "the whole ship, broadside, dir00"; wagons/organ guns → "the whole vehicle [+ gunner]"; chariots → "the chariot with its horses and rider as one subject"; elephants → keep howdah/mount together.
8. **Proportions:** if a foot unit comes out squat, add "TALL, full-height adult, long legs, not stocky." And don't drop footwear (Champi went barefoot until told otherwise).

## Step 3.5 — Self-analysis loop (grade the RENDER, not just the prompt)

Don't ship a render off the first generation — critique it against the reference yourself and iterate. This catches the errors the user would otherwise have to flag.

1. **Build a critique panel** (`.scratch/critique_panel.py <slug> <sld> <icon> <render> [dir]`) → a labeled side-by-side `sprite | icon | render`. View it.
   - **Then ZOOM each key element** (weapon, shield, head/helmet) — crop the same region from icon and render, upscale, view side by side. The 3-up thumbnail hides errors: a Woad Raider shield looked "fine" at thumbnail size but a zoom showed it was the wrong *shape* (round vs the icon's tall narrow oval) and wrong field. **Do not grade an element you haven't zoomed.**
2. **Grade the render against this checklist** (PASS / list FIXES) — and be ADVERSARIAL, actively hunt for mismatches; "looks close" is not PASS. If you flag a flaw, you must FIX it, never excuse it (the reference disproves most "but it needs to be X" rationalizations):
   - **head/helmet** — shape, crest/plume, mask, *specific* ornament (e.g. Teutonic gold cross + horns; Mangudai red plume)
   - **face** — visible vs covered, as the reference shows (Tiger Cavalry = hood, face shows)
   - **weapon** — type, count, and *held vs at-rest vs sheathed* (hands-on-weapon is FLUX's weak spot; bows at rest, swords sheathed if grip fails)
   - **shield + heraldry** — exact emblem (4-spoke / double-cross / griffin / Bolnisi / spirals)
   - **armor** — material (leather vs steel vs mail), gold detailing actually present
   - **mount / vehicle** — right animal; **rider present or absent as required**; horse *count* and *colour*; howdah/chariot intact
   - **palette & tone** — muted/weathered, not bright/glossy
   - **cleanliness** — single subject, no emblem/inset/text/nameplate, correct proportions, footwear present
3. **If FIXES** → patch that unit's description targeting the failed categories, regenerate (seed 7; bump seed only for an unresolved pose/grip), rebuild the panel, re-grade.
4. **Cap ~3 iterations.** Surface to the user only on convergence or a genuine stuck case. Negations ("no rider", "empty wagon") sometimes need 2 tries — verify they actually held.

## Step 4 — Cut + save
- rembg `remove(session=isnet-general-use)` → `getbbox()` crop → transparent PNG.
- Save 3 forms to `graphics/art/flux2_hybrid/`:
  - `<slug>_idle_dir05_bg.png`   — full-res WITH background (raw render)
  - `<slug>_idle_dir05_nobg.png` — full-res transparent
  - `<slug>_idle_dir05_icon.png` — 256×256 transparent, full-body centered (margin 0.96)

## Step 5 — Review delivery (Tailscale Taildrop)
- Build ONE per-batch review montage (PIL): repo icon on the left, render on the right, 5 rows stacked — easy to flick through on a phone. For an icon-less/low-res unit, compare against its upscaled sprite or the user-supplied hi-res pic.
- Deliver via **Taildrop** (NOT an http server): `tailscale file cp <montage> <renders...> iphone172:` (binary at `/c/Program Files/Tailscale/tailscale.exe`). On Windows the GUI may auto-save *received* files to `Downloads/` rather than the `tailscale file get` queue.
- User approves per-unit or requests changes; re-run just the flagged units (seed 7 keeps composition; bump seed only if a pose/grip won't resolve).

## Batch cadence
- 5 units per batch, alphabetical by display name.
- Skip already-done: Berserk, Janissary, Temple Guard (+ Paladin, a non-unique test).
- Exclude obvious generics (Skirmisher). Ships/mounted/elephants use the landscape canvas rule.

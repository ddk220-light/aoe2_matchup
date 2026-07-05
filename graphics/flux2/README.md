# graphics/flux2 — FLUX.2 Unit Art Pipeline

Generates high-quality AI unit portraits for elite unique units using FLUX.2-dev (4-bit)
and promotes them to the website icon set.

Full workflow details and hard-won lessons: [`docs/flux2-unit-art-workflow.md`](../../docs/flux2-unit-art-workflow.md)

---

## Scripts

| Script | Purpose |
|---|---|
| [`download_model.py`](download_model.py) | One-time download of `diffusers/FLUX.2-dev-bnb-4bit` (~32 GB) |
| [`generate.py`](generate.py) | Generate raw renders for a batch of units |
| [`cut_renders.py`](cut_renders.py) | Background-remove renders → save `_bg` / `_nobg` / `_icon` |
| [`critique_panel.py`](critique_panel.py) | Build side-by-side review panel (sprite \| icon \| render) |
| [`make_icons.py`](make_icons.py) | Promote finished icons to `apps/website/static/img/units/` |

Outputs live in:
- `graphics/flux2/renders/<batch>/` — raw renders (gitignored)
- `graphics/flux2/critique/` — review panels (gitignored)
- `graphics/art/flux2_hybrid/` — final `_bg` / `_nobg` / `_icon` PNGs (committed)

---

## Quick-start: adding a new batch

### 1. Setup (once)

```bash
# Download the model if not cached
C:/Users/ddk22/miniconda3/envs/visomaster/python.exe graphics/flux2/download_model.py
```

### 2. Research the units

For each new unit, look up its appearance on the AoE2 wiki before writing the description.
Use the `aoe2onlinereference` skill or browse the wiki directly.
Check the sprite with `sld_decode.py` for ambiguous weapons (the model art is truth, not the wiki lore).

### 3. Edit generate.py

Open `generate.py` and fill in the `UNITS` list at the top with your batch:

```python
UNITS = [
    # (slug, sld_filename, icon_filename, display_name, kind, dir_angle, description)
    ('boyar', 'u_cav_boyar_elite_idleA_x2.sld', 'Elite_Boyar.png', 'Boyar', 'mounted', 5,
     "a Slavic Boyar, a heavily armored cavalry warrior on a horse..."),
]
```

`kind` values:
- `'foot'` — infantry, on foot
- `'mounted'` — cavalry / elephant / camel (mount kept together with rider)
- `'ship'` — ship (uses dir00; whole ship as subject)
- `'vehicle'` — war wagon, organ gun, etc. (vehicle + horse as one subject)

### 4. Generate

```bash
# Must use the diffusion env (torch + diffusers + bitsandbytes)
C:/Users/ddk22/miniconda3/envs/visomaster/python.exe graphics/flux2/generate.py --out renders/batch13
```

### 5. Review (critique panel)

```bash
# Base conda env is fine for this
C:/Users/ddk22/miniconda3/python.exe graphics/flux2/critique_panel.py \
    boyar u_cav_boyar_elite_idleA_x2.sld Elite_Boyar.png graphics/flux2/renders/batch13/boyar.png
```

Open `graphics/flux2/critique/boyar.png`. **Zoom weapon, shield, head, mount separately** —
the thumbnail hides errors. Grade against the checklist in `docs/flux2-unit-art-workflow.md §Step 3.5`.

Fix → re-run `generate.py` (seed 7 keeps composition; bump to seed 21 only for stuck poses).
Cap at ~3 iterations.

### 6. Cut renders

```bash
# Base conda env (has rembg)
C:/Users/ddk22/miniconda3/python.exe graphics/flux2/cut_renders.py \
    --src graphics/flux2/renders/batch13 --slugs boyar cataphract
```

This saves three files per slug to `graphics/art/flux2_hybrid/`.

### 7. Promote to website icons (optional)

Add the slug -> icon mapping to `make_icons.py`'s `JOBS` dict, then:

```bash
python graphics/flux2/make_icons.py --slugs boyar
```

### 8. Deliver for review

Send to phone via Taildrop:
```bash
"C:/Program Files/Tailscale/tailscale.exe" file cp <montage.png> <render1.png> ... iphone172:
```

---

## File naming convention

| Pattern | Location | Description |
|---|---|---|
| `<slug>_idle_dir05_bg.png`   | `graphics/art/flux2_hybrid/` | Raw render with background |
| `<slug>_idle_dir05_nobg.png` | `graphics/art/flux2_hybrid/` | Transparent, tight-cropped |
| `<slug>_idle_dir05_icon.png` | `graphics/art/flux2_hybrid/` | 256×256 centered icon |

---

## Inputs

- **Sprites**: `graphics/game_raw_files/u_*_elite_idleA_x2.sld` (5,674 files)
- **Icons**: `apps/website/static/img/units/Elite_<Name>.png`

Both are available locally. The SLD files are NOT committed to git (large binary assets);
see `graphics/game_raw_files/` which is gitignored.

---

## Environment notes

| Task | Python |
|---|---|
| generate (FLUX.2) | `C:/Users/ddk22/miniconda3/envs/visomaster/python.exe` — has torch 2.8 cu129, diffusers 0.38, bitsandbytes 0.49 |
| cut (rembg) | `C:/Users/ddk22/miniconda3/python.exe` — base conda, has rembg |
| critique panel | either env |
| make_icons | either env |

# Working-roster asset completion

Scope confirmed by the owner: the existing 74-entry unique land-unit roster plus the ten new Viking Sagas land-unit entries. This does not add campaign heroes, animals, naval units, or every generic upgrade to the generated-art queue.

The current installed DAT is read directly from `D:/SteamLibrary/steamapps/common/AoE2DE/resources/_common/dat/empires2_x2_p1.dat`. Its SHA-256, unit IDs, icon IDs, and explicit idle/attack graphic records are preserved in `source-graphics.json`. `asset-manifest.json` maps each of the 84 units to its selected artwork. Generation and review status are updated as the batch completes.

## Outputs

Each scoped unit has seven standard files under `graphics/units/<slug>/`: game icon, transparent game icon, native dir06 idle, DAT 4× idle, UltraSharp 4× idle, blue DAT 4× idle, and transparent DAT 4× attack GIF. Existing files are preserved except for the two incorrect Flemish Militia icons, replaced with current DAT icon 354 (unit 1699). Their old copies remain in `.scratch/asset-completion/replaced-flemish-icons/`.

The upscales use the existing single-pass roster recipe in `graphics/units/build_idle_refs.py` and `build_attack_gifs.py`. Attack GIFs retain the established 55 ms frame duration. Graphics are selected from the DAT rather than guessed from filenames: Elite Hussite Wagon and Elite War Wagon attack records deliberately reference idle-named SLDs; Flaming Camel's attack record references its death graphic. These GIFs represent the selected base sprite sequence, not separately spawned projectiles or effects.

War Chariot Focus Fire and Barrage have the same icon, idle and attack graphic sources. Their standard assets are reused, and they share one generated artwork set.

## Local models and generation

Follow `docs/flux2-unit-art-workflow.md`: FLUX.2-dev NF4, two references (current dir05 sprite and corrected game icon), initial seed 7, 44 steps, guidance 4.0, the documented 1024-based aspect-ratio canvas rule, neutral gray background. The rule adds 12% width for portrait sprites, so near-square portraits can exceed 1024 pixels in width; each exact size is recorded. Save full background render, transparent full-resolution render, and centered 256×256 transparent generated icon. Background removal uses the existing `isnet-general-use` model via rembg. Prompt descriptions are recorded in `art-descriptions.json`; per-render parameter records accompany completed outputs.

Current executable locations are `D:/miniconda3/envs/visomaster/python.exe` for FLUX/upscaling and `D:/miniconda3/python.exe` for DAT parsing/rembg. The original documentation's `C:` Python paths have moved. The exact FLUX checkpoint was restored to ignored `.scratch/tools/models/flux2-dev-bnb-4bit/`. The cutout script sets `NUMBA_CACHE_DIR` to writable `.scratch/asset-completion/numba-cache/` before importing rembg, avoiding its attempt to compile cached code in the read-only installed package directory.

The scripts in this folder preserve the executed recipe. They use `.scratch/current-asset-dat.json` and `.scratch/asset-completion/` as working inputs/output; source metadata and prompts are preserved here. Asset presence is not user visual approval: new artwork is reviewed against its references and remains available for owner review.

See [the artwork comparisons](REVIEW.md), [recorded visual checks](visual-review.json), and [image validation](art-validation.json). The inventory links each scoped unit to its folder, seven standard assets, available generated variants, and new reference comparison.

## Unit research

- [Official Viking Sagas overview](https://www.ageofempires.com/games/aoeiide/the-viking-sagas/)
- [Official warriors overview](https://www.ageofempires.com/news/the-warriors-of-the-viking-sagas/)
- [Varangians and mounted crossbowmen](https://www.ageofempires.com/news/varangians-civilization-deep-dive/)

The current installed icon and sprite determine visual equipment, colors, and upgrade distinctions. For example, the idle Jomsviking reference carries a spear; its special torch attack does not justify changing the idle artwork to a torch bearer.

## Targeted visual corrections

The first Heavy Mounted Crossbowman render obscured the face under the visor. The first Savar render lost the spiral helmet fluting and used a straight sword. Only those two units were rerendered. Their second attempts exaggerated helmet proportions, so the final pass uses shorter descriptions and seed 21, following the workflow's bounded self-review loop. Superseded renders are preserved in `.scratch/asset-completion/superseded-first-renders/` and `.scratch/asset-completion/superseded-second-render/`. The final descriptions and per-render generation records identify the delivered settings; `rerender-fixes.json` records the initial corrections.

## Delivery status

All 84 scoped units have seven standard assets and a generated-art source. This work added 100 standard files and 21 three-file artwork sets (63 files), and corrected the two existing Flemish Militia icons. The new artwork remains pending owner approval. After three attempts, Heavy Mounted Crossbowman's helmet/crossbow details and Savar's sword shape remain flagged for visual review; neither is promoted to golden. See `completion-summary.json` for the final file and link checks.

## Git publication scope

The owner subsequently requested Git retention of these new-unit and gap-filling outputs. The publication includes exactly those 163 new media files, the two icon corrections, and this batch's source scripts and text/JSON provenance. Exact media paths and hashes are registered in [the Git asset policy](../../docs/GIT_ASSET_POLICY.md). Git retention does not change the visual-review status above.

The `review/` comparison sheets, superseded renders and scratch inputs remain local and ignored. Links to comparison sheets and external game/model paths in these historical generation records are local-machine references, not files promised by a Git clone. No unrelated landscape-video changes are part of this publication.

# Git asset retention and publication policy

## Owner-approved scope — 2026-09-22

The owner approved the complete existing per-unit reusable asset library, not only the attack GIFs: game icons, transparent icons, native and enhanced idle sprites, blue-team sprites, attack animations, and the final HD unit illustrations stored with those units.

This records approval to **retain the library in Git**. It is not a new claim that every image was individually visually reviewed. The source workflow's finalized outputs are documented in [finalize_units.py](../graphics/units/finalize_units.py), with blue-team outputs in [build_blue_sprites.py](../graphics/units/build_blue_sprites.py). Do not run the finalizer for Git cleanup: it regenerates images and deletes other files.

The original selected snapshot is `563825f43b3e7d1d71155b3b90be7d2574f106ec`: **1548 files across 223 unit folders, 1,102,507,305 bytes (1051.43 MiB)**. The table immediately below describes that original snapshot. The exact register and `.gitignore` exceptions now also include the owner's subsequent unit-completion selection described below. New files are not approved solely because their names resemble these files.

| Asset family | Files | MiB | Variant and reuse purpose |
| --- | ---: | ---: | --- |
| Game icon | 223 | 18.00 | Red, native game icon; reusable opaque game ui icon |
| Transparent icon | 223 | 18.76 | Transparent game icon; reusable background-removed game ui icon |
| Native idle pose | 223 | 4.19 | Direction 06, red, native; reusable native pose/reference sprite |
| DAT idle pose | 223 | 118.66 | Direction 06, red, DAT 4x; reusable enhanced idle sprite |
| Blue DAT idle pose | 223 | 118.99 | Direction 06, blue, DAT 4x; reusable second-team enhanced idle sprite |
| UltraSharp idle pose | 223 | 122.96 | Direction 06, red, UltraSharp 4x; reusable alternate enhanced idle sprite |
| Attack animation | 193 | 634.78 | Direction 06, red, DAT 4x; reusable transparent attack animation |
| HD unit illustration | 17 | 15.09 | FLUX HD; angle not inferred; reusable per-unit final illustration |

There were no standalone idle-animation GIFs or WebPs in the original `graphics/units/` snapshot. Idle assets here are still PNG poses. Thirty original unit folders had no attack GIF. The later completion batch fills selected gaps, not every possible unit asset. Git publication does not authorize regeneration or claim every unit has every asset type.

## Subsequent unit-completion selection — 2026-09-22

After publication of `3919b3158d37c606ba784f52eed78a9278c284a6`, the owner requested publication of the new-unit and gap-filling assets. This adds **100 standard unit files and 63 FLUX.2 artwork files**, and updates the **two Flemish Militia icons** to the current DAT-derived versions: 165 changed media paths, 116,540,919 bytes of selected working content. The exact register below now contains **1711 unique retained paths** and records the updated icon blobs.

The ten new unit entries are Mounted Crossbowman, Heavy Mounted Crossbowman, Varangian Guard, Elite Varangian Guard, Hearth Troop, Elite Hearth Troop, Jarl, Elite Jarl, Jomsviking and Elite Jomsviking. Standard-file additions also fill gaps for Elite Hussite Wagon, Elite War Wagon, Flaming Camel, Missionary and both War Chariot modes. The 21 new artwork sets each retain their background render, full-resolution transparent cutout and transparent icon in `graphics/art/flux2_hybrid/`.

The associated source scripts, generation records, inventory and text/JSON validation notes in `graphics/asset_completion_2026-09-22/` are retained for reuse and provenance. Its `review/` comparison images and all scratch/superseded renders stay local and ignored. Retention authorization is not visual golden approval: Savar and Heavy Mounted Crossbowman remain flagged for owner review, as recorded in the completion notes. No images are regenerated or promoted to golden by this publication.

## What belongs in Git

- Source code, tests, documents, workflow recipes, decisions/learnings, small manifests and reusable helper scripts.
- The explicitly selected unit library in the register below, at its existing paths.
- Already-published application assets, templates, databases and artwork remain tracked and unchanged, including `graphics/art/flux2_hybrid/`, except for the owner's subsequent exclusion of `graphics/art/temple_guard/` below. This cleanup is not a new blanket quality approval.
- Additional or updated assets only when their retention/update is within the owner's request. Add exact paths and purpose to the register and `.gitignore` exceptions; do not use a whole-family exception to approve future files automatically.

## What stays local

- Raw captures, final rendered videos, frame streams, audio extraction, model downloads, scratch images, alternative renders, intermediate frame directories, and unselected cover backups.
- The 17 images under `graphics/youtube/` from the old pending backup commit are excluded from the reconstructed commit, **not deleted from disk**.
- Following the owner's subsequent publication approval, the entire old `graphics/art/temple_guard/` collection (37 images, including its six `flux2/golden/` renders, plus the standalone HTML viewer) is removed from Git tracking and ignored, **not deleted from this machine**. Previously published copies remain recoverable from Git history. This exclusion does not affect the approved `graphics/units/temple_guard/` or `graphics/units/elite_temple_guard/` library assets.
- New scratch/generation workflows should write directly into `data/local/generated/` or an existing ignored output directory. Keep reusable source/helper scripts outside scratch so they can be committed.
- Existing generators may keep their current output paths: scoped image exclusions already cover new PNG/GIF/JPG/JPEG/WebP files in `graphics/units/`, `graphics/youtube/`, `graphics/art/`, `graphics/extracted/`, and video intro assets/thumbnails. Source files there are not blanket-ignored.

Do not overwrite a tracked approved asset to make an experiment. Save the variation in an ignored location; update the approved asset only when that update is requested. Ignore rules affect untracked files, not edits to tracked assets. Force-add bypasses them and must not be used as a shortcut. These standard Git rules are not a universal detector for arbitrary output locations.

## Consumers and local inputs

- `apps/video/build_story_short.py::attack_path` uses the selected direction-06 DAT attack GIFs as a fallback at their unchanged paths.
- `graphics/units/sync_web_sprites.py` consumes red/blue DAT idle sprites and promotes website-sized copies plus manifests. It is not automatically run during generation or this cleanup.
- Retained animations are self-contained media. Full video production still needs game/menu resources, local recordings, audio and model/runtime dependencies described in the Shorts workflow documents. A Git clone alone is not promised to contain those external inputs.
- No consumer code, sprite bytes, paths, timings, shadows, backgrounds or rendering settings are changed by this Git cleanup.

## Publication review

Before **every** Git push, an independent reviewer receives the user's current request, exact destination ref, live remote tip, all outgoing commits, changed paths, binary inventory and newly reachable object sizes. Review earlier unpushed commits as well as the latest change. Resolve scope mismatches before pushing and re-review if the candidate or destination changes.

Routine in-scope review is automatic. Ask the owner only when new authority or a material choice is needed. If independent review is unavailable, stop before pushing. This is a required agent workflow, not an installed native Git hook or a claim of tamper-proof enforcement.

Use explicit staging paths and an explicit publication target. Never publish recovery refs with `--all`, `--mirror`, or an indiscriminate ref/tag push. Large size is not itself a scope violation: this owner-selected library is intentionally about 1.03 GiB. An instruction to push a small document must not silently publish this library or any earlier unrelated commits.

## Local reconstruction scope

The cleanup is based on remote tip `251f6befa2986d04fafe8556ace4682ad253ae2a`. The original six commits remain recoverable through local-only branch `backup/local-video-recorder-v3-20260922`. All selected and excluded media stay on disk. The replacement commit retains the 38 previously reviewed source paths, this policy, the approved plan, repository instructions, and the exact asset register below.

The separate untracked `graphics/ASSET_INVENTORY_2026-09-22.md` was present when reconstruction began and was deliberately excluded from that first commit. Its initial raw Git blob hash was `041ba88dcfb5ac48a550ca4ef9b8728681c44cbd`. The completed inventory is included only under the owner's subsequent unit-completion request above.

During reconstruction validation, other work changed `graphics/units/flemish_militia/icon.png` and `graphics/units/flemish_militia/icon_transparent.png`. That first commit retained the pinned snapshot versions without overwriting the newer working files. The owner's subsequent unit-completion request now selects those two corrections, whose current blobs are recorded below.

The concurrent `graphics/asset_completion_2026-09-22/` work was likewise excluded from the reconstruction. Its completed source, manifests and notes are included only in the subsequent scoped publication; comparison images remain local. Unrelated concurrent landscape-video work is not included. Concurrent generation alone never broadens a commit's approved path/content set.

The original local reconstruction did not push or deploy. Subsequent owner-authorized pushes target only `codex/video-recorder-v3`; they do not authorize deployment, remote-history rewriting, local-object cleanup, asset relocation, Git LFS migration or older storage/CDN proposals.

## Exact retained-asset register

Paths are repository-relative. Each path's variant/purpose is specified by its family above; FLUX2 entries distinguish background source, transparent full-resolution artwork and transparent artwork icon. Bytes and Git blob IDs identify the current selected content, including the subsequent additions and two icon corrections, and support verification without regenerating media.

| Path | Family | Bytes | Git blob ID |
| --- | --- | ---: | --- |
| `graphics/units/arambai/arambai_attack_dir06_dat4x.gif` | Attack animation | 2103199 | `a2b7325688c062d2a50b11dfa0b6be291f2e2262` |
| `graphics/units/arambai/arambai_idle_dir06.png` | Native idle pose | 11170 | `6f82f43a588242a00decc6ca7440524256e740cc` |
| `graphics/units/arambai/arambai_idle_dir06_dat4x.png` | DAT idle pose | 352829 | `173416bac0bb869f51d1c931742bfc09498bc8b2` |
| `graphics/units/arambai/arambai_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 352021 | `ba6534669b73890ea29fca72419a7cb128ae2778` |
| `graphics/units/arambai/arambai_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 348219 | `b517a49700a38b87505635a7e3ae1447af94e413` |
| `graphics/units/arambai/icon.png` | Game icon | 98281 | `3f8e8f58a98fc3b642d1a052365bf24233a1c10d` |
| `graphics/units/arambai/icon_transparent.png` | Transparent icon | 102354 | `06461cf94e57adb3da6454507321acff83547df6` |
| `graphics/units/arbalester/arbalester_attack_dir06_dat4x.gif` | Attack animation | 1200322 | `be527a1df7e5530a33ebfcbd1020ea2cc57beb57` |
| `graphics/units/arbalester/arbalester_idle_dir06.png` | Native idle pose | 5038 | `636e933ba36ba868674eed61dacc33d896458702` |
| `graphics/units/arbalester/arbalester_idle_dir06_dat4x.png` | DAT idle pose | 205997 | `7faff7e1afb3b555eeb36f0dd7276fcc11261062` |
| `graphics/units/arbalester/arbalester_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 207198 | `cefa31ec29dba8caaa36aef55c940b83dc52d4b9` |
| `graphics/units/arbalester/arbalester_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 203439 | `ad3662a43a6528367cce64db2b8e3fc9552135dc` |
| `graphics/units/arbalester/icon.png` | Game icon | 73262 | `6e81db74b305228c292e1da860a23043f25a4545` |
| `graphics/units/arbalester/icon_transparent.png` | Transparent icon | 77248 | `b9f993d86b652e96a5871cbc294bbf545883f5a1` |
| `graphics/units/archer/archer_attack_dir06_dat4x.gif` | Attack animation | 759460 | `2c4141c08b1518aacfac52b5933bbd62fe1c2202` |
| `graphics/units/archer/archer_idle_dir06.png` | Native idle pose | 4780 | `29d05e2885ca2297e3e4a0cad8c36796c20f21b3` |
| `graphics/units/archer/archer_idle_dir06_dat4x.png` | DAT idle pose | 224712 | `4f7b16bbf604741bdb74b13081ce8bae3c0d8090` |
| `graphics/units/archer/archer_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 224639 | `587cafd8d578f5bfae359febb2748787c1c9295f` |
| `graphics/units/archer/archer_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 222842 | `383f2dc87863bb1cd7ce4f56df0574e5f74f7559` |
| `graphics/units/archer/icon.png` | Game icon | 67205 | `3db50a17fb31c5e3d01ead95513b35baa96b2f32` |
| `graphics/units/archer/icon_transparent.png` | Transparent icon | 70956 | `ebdb04e4b3451fb18cc9e0297ac5b7bbf83f51bc` |
| `graphics/units/armored_elephant/armored_elephant_attack_dir06_dat4x.gif` | Attack animation | 11778098 | `4a971c4113f2f0af35c662a35ffc1df78b24f237` |
| `graphics/units/armored_elephant/armored_elephant_idle_dir06.png` | Native idle pose | 36289 | `f059fbcbe0314e579814e62b1b14dde8f3a70f61` |
| `graphics/units/armored_elephant/armored_elephant_idle_dir06_dat4x.png` | DAT idle pose | 850356 | `67359c614117d88401c7b7abc802e77cbb03419b` |
| `graphics/units/armored_elephant/armored_elephant_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 862005 | `5311f88d4c6a6f254ac0c6e2809c0ba3c2200ce8` |
| `graphics/units/armored_elephant/armored_elephant_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 926735 | `695e8e71eb35a4033115c017d0e84a834baaf9c7` |
| `graphics/units/armored_elephant/icon.png` | Game icon | 112764 | `9249532431b83273ef5abce89ef853e7f2f21c5f` |
| `graphics/units/armored_elephant/icon_transparent.png` | Transparent icon | 115724 | `936100ad74771893f60d1d0df295204dda8e567f` |
| `graphics/units/ballista_elephant/ballista_elephant_attack_dir06_dat4x.gif` | Attack animation | 6550708 | `d7a979f213b917094fc24d2059721287d457b710` |
| `graphics/units/ballista_elephant/ballista_elephant_idle_dir06.png` | Native idle pose | 34622 | `02a439c19ff549a391fab077a59b897fe0342618` |
| `graphics/units/ballista_elephant/ballista_elephant_idle_dir06_dat4x.png` | DAT idle pose | 900298 | `7ca203f871343879356636216587a0e740842968` |
| `graphics/units/ballista_elephant/ballista_elephant_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 898562 | `c1c5776bcf20859fb8fdb8c9eea66e4dc029c8a1` |
| `graphics/units/ballista_elephant/ballista_elephant_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 962234 | `0583d86d6f81ca2b952fd34844dc70abdf78534e` |
| `graphics/units/ballista_elephant/icon.png` | Game icon | 91043 | `ff5658ea64ce9e61ded006e1b95bcb0e8eedeaa3` |
| `graphics/units/ballista_elephant/icon_transparent.png` | Transparent icon | 94748 | `6554c508d46d5ae1f0ba44f2890e03c5f9f92f68` |
| `graphics/units/battering_ram/battering_ram_attack_dir06_dat4x.gif` | Attack animation | 13229738 | `063e9ce54bda26e414740767f687f65dea388d53` |
| `graphics/units/battering_ram/battering_ram_idle_dir06.png` | Native idle pose | 34544 | `c8d51dac2f094dc2f78927aace6c6fbdfef3913d` |
| `graphics/units/battering_ram/battering_ram_idle_dir06_dat4x.png` | DAT idle pose | 839236 | `e2928ccdd3a12bd20e2ea85564acea81ad8aad5e` |
| `graphics/units/battering_ram/battering_ram_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 841309 | `e7efdbebe171da20a907ea12bc03fd3317467acd` |
| `graphics/units/battering_ram/battering_ram_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 913407 | `2fdddd03f142aaba191749e039627604ae27806b` |
| `graphics/units/battering_ram/icon.png` | Game icon | 136952 | `8433c1923d7df421e4ac4870563d4e2d28782d99` |
| `graphics/units/battering_ram/icon_transparent.png` | Transparent icon | 139347 | `a01ddda8a1dd5ab25c04acdf9f4c39c7a06c1b09` |
| `graphics/units/battle_elephant/battle_elephant_attack_dir06_dat4x.gif` | Attack animation | 11853679 | `9fbf6008245d66d76fdcb3bc6e0675f4bbf39d0c` |
| `graphics/units/battle_elephant/battle_elephant_idle_dir06.png` | Native idle pose | 34731 | `51ade1576661ae5fb0cd1ee9884c7fe412d7de26` |
| `graphics/units/battle_elephant/battle_elephant_idle_dir06_dat4x.png` | DAT idle pose | 864614 | `506ab9d7fa968907ab9b23f3d4c776e8240b715b` |
| `graphics/units/battle_elephant/battle_elephant_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 862531 | `4d104df46739f0c9a38e1fc1b0c8a3bac3d1aab1` |
| `graphics/units/battle_elephant/battle_elephant_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 910285 | `6bdd35a0605d428036cfc17abac65a2b26953bda` |
| `graphics/units/battle_elephant/icon.png` | Game icon | 117318 | `717a2410b2b937a2080baf7ce13a5c6f936e39bc` |
| `graphics/units/battle_elephant/icon_transparent.png` | Transparent icon | 119401 | `d7f5f4c2f4d2b6d56f81ea4ab16c9c7d4ffcd72e` |
| `graphics/units/berserk/berserk_attack_dir06_dat4x.gif` | Attack animation | 816902 | `9d1bc284d19fb2701b26706091017578d474e428` |
| `graphics/units/berserk/berserk_idle_dir06.png` | Native idle pose | 4573 | `9e6ff9daf164dee7b620787af95e8d5bd437eff1` |
| `graphics/units/berserk/berserk_idle_dir06_dat4x.png` | DAT idle pose | 153614 | `eb999047a92a28f96bbe642ea0b15194b35ac935` |
| `graphics/units/berserk/berserk_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 154518 | `e560877e86fef8769ada42c3f77c3024f064de9c` |
| `graphics/units/berserk/berserk_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 153646 | `3f4bf6d60f8076f575ae9e6461987faab5e38c58` |
| `graphics/units/berserk/icon.png` | Game icon | 103839 | `b95baeffef506ba11ad5f073c706391141338228` |
| `graphics/units/berserk/icon_transparent.png` | Transparent icon | 106875 | `d172e1e59347fbebce6662ddde2b05c70d3484be` |
| `graphics/units/blackwood_archer/blackwood_archer_attack_dir06_dat4x.gif` | Attack animation | 750631 | `47a38b6b030644115a8d9cb80103d5704218d8e2` |
| `graphics/units/blackwood_archer/blackwood_archer_idle_dir06.png` | Native idle pose | 4433 | `cfd6000b64aee74296da7faaa00064b9394acde7` |
| `graphics/units/blackwood_archer/blackwood_archer_idle_dir06_dat4x.png` | DAT idle pose | 189170 | `88520c97de13fc9c527dbee66f3e027cc9d28358` |
| `graphics/units/blackwood_archer/blackwood_archer_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 196214 | `32f679a6bdcebadaf7842534b2392760b3fbe3b6` |
| `graphics/units/blackwood_archer/blackwood_archer_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 183719 | `d4890ed3f399a77ea4ead71a050f6fccd9d74d5e` |
| `graphics/units/blackwood_archer/icon.png` | Game icon | 57762 | `b5d4b40eceb930d22f65f4f6ab41f0b923370bdb` |
| `graphics/units/blackwood_archer/icon_transparent.png` | Transparent icon | 63523 | `e463362062710f4baa50014f570286187888bb3b` |
| `graphics/units/bolas_rider/bolas_rider_attack_dir06_dat4x.gif` | Attack animation | 1867125 | `e92e0ac9631a61c5cfb039ae94f7da8e83cfc3e7` |
| `graphics/units/bolas_rider/bolas_rider_idle_dir06.png` | Native idle pose | 11007 | `e589a0cb5ed4db0e2ae15b8082fcd49f38ec5111` |
| `graphics/units/bolas_rider/bolas_rider_idle_dir06_dat4x.png` | DAT idle pose | 350280 | `717a065024e030e4e2e9376426f820b363aa304a` |
| `graphics/units/bolas_rider/bolas_rider_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 352631 | `4df6c8995b0bc4633209587b797cd3c56f9bfdb3` |
| `graphics/units/bolas_rider/bolas_rider_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 347408 | `3fa8567d57b0a9fe1641985f9fa2d03242261ded` |
| `graphics/units/bolas_rider/icon.png` | Game icon | 64352 | `c9d365eb69073ba88ed61529a631c7544ddce209` |
| `graphics/units/bolas_rider/icon_transparent.png` | Transparent icon | 68746 | `f89250e2e6ef6b81577f26aeb317917f42a421af` |
| `graphics/units/bombard_cannon/bombard_cannon_attack_dir06_dat4x.gif` | Attack animation | 2539036 | `397cbdd5ff49ff5795623557d227f031937b0cbb` |
| `graphics/units/bombard_cannon/bombard_cannon_idle_dir06.png` | Native idle pose | 7451 | `3e90c5680adb9eb1a91e88cef41a6488b9db2bcb` |
| `graphics/units/bombard_cannon/bombard_cannon_idle_dir06_dat4x.png` | DAT idle pose | 223124 | `1b1c32e5792684aed15a2c72dc2de213490862e0` |
| `graphics/units/bombard_cannon/bombard_cannon_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 223185 | `86b9fa87694e084b0c2887251410877bc262417c` |
| `graphics/units/bombard_cannon/bombard_cannon_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 231454 | `93483182fa93979e12f09c8d6aa115c4452ed5db` |
| `graphics/units/bombard_cannon/icon.png` | Game icon | 118314 | `e824b3a4e70792aa4e7caaf8fe59b57fc720380e` |
| `graphics/units/bombard_cannon/icon_transparent.png` | Transparent icon | 121621 | `1775bcaf639ca4d3f3b4548ffaacbbd9678c31b9` |
| `graphics/units/boyar/boyar_attack_dir06_dat4x.gif` | Attack animation | 2453738 | `e71385b9ab10fbe73b39245a4fdd1bd0a3762cea` |
| `graphics/units/boyar/boyar_idle_dir06.png` | Native idle pose | 14368 | `c51781a74801c208f672e7fa7127f730e535c6ec` |
| `graphics/units/boyar/boyar_idle_dir06_dat4x.png` | DAT idle pose | 440328 | `58f5e9eb2b401522e11260d3c2fb5b1a53dbef6f` |
| `graphics/units/boyar/boyar_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 436661 | `b3ee875352fb23f526b2c27f93e1d1b73bc2ef1f` |
| `graphics/units/boyar/boyar_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 439230 | `85e7837fed989fef7b36fc921c2b9b9fbdd38244` |
| `graphics/units/boyar/icon.png` | Game icon | 104714 | `ebb2bd57769ec71f2c63df25aefa62b5592de259` |
| `graphics/units/boyar/icon_transparent.png` | Transparent icon | 107371 | `a5a09d63efcc52d00024ee75633c0837f0c896f2` |
| `graphics/units/camel_archer/camel_archer_attack_dir06_dat4x.gif` | Attack animation | 2466684 | `53b2ac01bdf8a06118d4f4aebc5c66ad94a6314d` |
| `graphics/units/camel_archer/camel_archer_idle_dir06.png` | Native idle pose | 14084 | `0f6b0ad11e095dbcfc305bb6076cc91898f4faa0` |
| `graphics/units/camel_archer/camel_archer_idle_dir06_dat4x.png` | DAT idle pose | 476008 | `9759ebce8eee391828541ea071a8d34554be93d2` |
| `graphics/units/camel_archer/camel_archer_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 476114 | `0c76f8a66f8dc18aa48ecd41451c8e3135e2cd8f` |
| `graphics/units/camel_archer/camel_archer_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 479064 | `0c96b2207765919c801941a23e64283f9fc0671a` |
| `graphics/units/camel_archer/icon.png` | Game icon | 98092 | `09160a66974cbb16a8b0e45c7e406edbdc056f64` |
| `graphics/units/camel_archer/icon_transparent.png` | Transparent icon | 102389 | `1934ca43c9ac501cd4743b061a85f5e2031c7d49` |
| `graphics/units/camel_rider/camel_rider_attack_dir06_dat4x.gif` | Attack animation | 5037358 | `b9d2f965bd3178010882d20a7ebce7bfaef58f83` |
| `graphics/units/camel_rider/camel_rider_idle_dir06.png` | Native idle pose | 14976 | `3c26cf1c552cdc5feb0e162097fa2b805e7585e9` |
| `graphics/units/camel_rider/camel_rider_idle_dir06_dat4x.png` | DAT idle pose | 541551 | `4044ee899dd5e339c1a06a68591014b9aed4ccf9` |
| `graphics/units/camel_rider/camel_rider_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 541643 | `6508a7858e0ae5c9c2ae1ffe9b89fc829a852f82` |
| `graphics/units/camel_rider/camel_rider_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 542730 | `3926ede5abbafa6dd232a9ed24ca495ab22ec284` |
| `graphics/units/camel_rider/icon.png` | Game icon | 91801 | `170c438349031c6824d3a9db7f7cd3b54887135b` |
| `graphics/units/camel_rider/icon_transparent.png` | Transparent icon | 94733 | `9f8d1923f18297772b1bb26e09ef1dea86834073` |
| `graphics/units/cannon_galleon/cannon_galleon_idle_dir06.png` | Native idle pose | 52082 | `ff5c2c17ec3426f359d40c4c9ac282306ca401e0` |
| `graphics/units/cannon_galleon/cannon_galleon_idle_dir06_dat4x.png` | DAT idle pose | 1235120 | `a224b92c0e1e4f2d2d3a2b389dd5b796fe5a1799` |
| `graphics/units/cannon_galleon/cannon_galleon_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1234515 | `0baf50e93e967f777b27b041a5e351d3cc14d2ed` |
| `graphics/units/cannon_galleon/cannon_galleon_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1316130 | `e65a77fcf05b2c08c3e1c4ea203b2a7e1814e44d` |
| `graphics/units/cannon_galleon/icon.png` | Game icon | 108081 | `f9819eb7d3adfdf1073a50e2272d5752b6afd8de` |
| `graphics/units/cannon_galleon/icon_transparent.png` | Transparent icon | 109837 | `14c00d01489842d1b43f0d14356ae126e66fa29b` |
| `graphics/units/capped_ram/capped_ram_attack_dir06_dat4x.gif` | Attack animation | 13509920 | `f30ac324a8fa046a31c8fa65f8cf70495dddc80d` |
| `graphics/units/capped_ram/capped_ram_idle_dir06.png` | Native idle pose | 35572 | `f1696f35863c2349e92dce9ac57a5d20b5f82e3b` |
| `graphics/units/capped_ram/capped_ram_idle_dir06_dat4x.png` | DAT idle pose | 859508 | `6cca8e42cb96e4437298e0ad0f65559fe213e9e3` |
| `graphics/units/capped_ram/capped_ram_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 860122 | `b2e42bb5db26e044301c6961e6e5af6f4eac8d4b` |
| `graphics/units/capped_ram/capped_ram_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 933492 | `0801101644b62cfc2f433fa32d25709e495eeed2` |
| `graphics/units/capped_ram/icon.png` | Game icon | 138801 | `b2165bb639359a93825ddae9828fa93e4f3626ed` |
| `graphics/units/capped_ram/icon_transparent.png` | Transparent icon | 141736 | `2f5acf7960bb3c84079500480c759e4d780f1474` |
| `graphics/units/caravel/caravel_idle_dir06.png` | Native idle pose | 121283 | `a820452fcc1e827a0ffeac5a42f6c6c1bdc0db91` |
| `graphics/units/caravel/caravel_idle_dir06_dat4x.png` | DAT idle pose | 2975994 | `1e487ea762853d67e264f7c437a539784dc6b7db` |
| `graphics/units/caravel/caravel_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 2923817 | `b4f97e4c3e1f5e9dd0eaf09d8efdd4ec64cd97e3` |
| `graphics/units/caravel/caravel_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 3154203 | `89cfbdd998a536ed790181d5595f01fabebba678` |
| `graphics/units/caravel/icon.png` | Game icon | 144042 | `95546ec4cc2f11950ce00b5a8e0fba19c02a0233` |
| `graphics/units/caravel/icon_transparent.png` | Transparent icon | 147043 | `b90eeeb27569968f1a575930a9cc231c3d7edccf` |
| `graphics/units/carrack/carrack_idle_dir06.png` | Native idle pose | 50451 | `d6f39d78f614a87aa8eca2cf97e081275bfce53b` |
| `graphics/units/carrack/carrack_idle_dir06_dat4x.png` | DAT idle pose | 1169475 | `22c24c05d3a004e32ec91cf924468fe4824d2494` |
| `graphics/units/carrack/carrack_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1172283 | `b9e4c4a15c47e2abb98f19b1a765b38e4fd43b95` |
| `graphics/units/carrack/carrack_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1272478 | `55f306e8a7a80fe71710f7ab2cadf3f2ca32af1c` |
| `graphics/units/carrack/icon.png` | Game icon | 84382 | `a815f7ffa591b9fa4fb977c03a91d1cdcbf5c1c5` |
| `graphics/units/carrack/icon_transparent.png` | Transparent icon | 87633 | `889c5d7eda359ad0e9faa4f926322562ff3864c8` |
| `graphics/units/cataphract/cataphract_attack_dir06_dat4x.gif` | Attack animation | 2554375 | `33eb08c484ab0f9328cb3459e4a1f0b9b9c47fc1` |
| `graphics/units/cataphract/cataphract_idle_dir06.png` | Native idle pose | 14068 | `8805f582813f8f36ced512e8a5b6a64c08fe9d00` |
| `graphics/units/cataphract/cataphract_idle_dir06_dat4x.png` | DAT idle pose | 425695 | `2f7154aa38c679aa22abf0732e807a6859693f00` |
| `graphics/units/cataphract/cataphract_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 425289 | `0bfc36e3043b5b18ccf21165fa9a5d7890fc99c9` |
| `graphics/units/cataphract/cataphract_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 418920 | `2eb1dbe35a2a9eff31bad7d410d8291037f25087` |
| `graphics/units/cataphract/icon.png` | Game icon | 111305 | `4c4d40f0c20c3c7f255cdab6b0cdba73049c432f` |
| `graphics/units/cataphract/icon_transparent.png` | Transparent icon | 113626 | `6760d98281f885b9dfe5da529408b4653e78d53f` |
| `graphics/units/catapult_galleon/catapult_galleon_idle_dir06.png` | Native idle pose | 77910 | `b93992d41203b171a2bc0f49591418999b9fcbfe` |
| `graphics/units/catapult_galleon/catapult_galleon_idle_dir06_dat4x.png` | DAT idle pose | 1823864 | `57462691570eded62727bf2736c179c3c4adefb5` |
| `graphics/units/catapult_galleon/catapult_galleon_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1822481 | `1b8f899bf5635f1c27b2bfa30a93d51155a84015` |
| `graphics/units/catapult_galleon/catapult_galleon_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1972044 | `84fb60ee02694bb6617dc63e1cbb287cf2c4deef` |
| `graphics/units/catapult_galleon/icon.png` | Game icon | 72410 | `893aaa54518ae7ddfac8d16a5f4e4e9151e62e1a` |
| `graphics/units/catapult_galleon/icon_transparent.png` | Transparent icon | 76411 | `a8d286634f5218d9254dd56814f4ac561806b794` |
| `graphics/units/cavalier/cavalier_attack_dir06_dat4x.gif` | Attack animation | 3964790 | `ba14c849e2f3c31b73eb30501f9fe57b25944b3b` |
| `graphics/units/cavalier/cavalier_idle_dir06.png` | Native idle pose | 11980 | `37a07bb63aee3c3f9d08a9b7fafbf1530ca9dffc` |
| `graphics/units/cavalier/cavalier_idle_dir06_dat4x.png` | DAT idle pose | 348056 | `e8d42cec4128899f5b4dc5c949ec95914d3c5554` |
| `graphics/units/cavalier/cavalier_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 349783 | `6dd4cb4281f80dfce5b46de129c251ca72a0a28e` |
| `graphics/units/cavalier/cavalier_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 350073 | `f25f8876ec8e60cd8170d5ed911b89b48619bce8` |
| `graphics/units/cavalier/icon.png` | Game icon | 135252 | `58306132cfadb3a85d8beadcf4347277499d9251` |
| `graphics/units/cavalier/icon_transparent.png` | Transparent icon | 138333 | `3b3d69282d4298b791f24d8da6ccc200dd24a459` |
| `graphics/units/cavalry_archer/cavalry_archer_attack_dir06_dat4x.gif` | Attack animation | 3172977 | `e3d2fbd911b2558af76739b5e8bc5a84ca9f3fd4` |
| `graphics/units/cavalry_archer/cavalry_archer_idle_dir06.png` | Native idle pose | 12290 | `dc28da5be93216bc794514697dcd5d5097593d6c` |
| `graphics/units/cavalry_archer/cavalry_archer_idle_dir06_dat4x.png` | DAT idle pose | 378433 | `efa6a2e8127dd20060f0d4600370975fe5babe68` |
| `graphics/units/cavalry_archer/cavalry_archer_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 379611 | `8f94535719d00aa4610cdd725e0109c8c34cb604` |
| `graphics/units/cavalry_archer/cavalry_archer_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 375569 | `2b5e9f04f507649a11a2af4a9cc1d9de88e15346` |
| `graphics/units/cavalry_archer/icon.png` | Game icon | 101426 | `d6824e2b93afc3cd3c26748ad8f0d2ffedca46e9` |
| `graphics/units/cavalry_archer/icon_transparent.png` | Transparent icon | 104674 | `598fbe2c690b40c61e5bf4cfa7fd203c2197defc` |
| `graphics/units/centurion/centurion_attack_dir06_dat4x.gif` | Attack animation | 2635620 | `8eebbf9de5f19714f663c0a8c43b5dc30ed3804d` |
| `graphics/units/centurion/centurion_idle_dir06.png` | Native idle pose | 14000 | `cfc23c167d90d18c13aeb017b1f9b975b8562bc0` |
| `graphics/units/centurion/centurion_idle_dir06_dat4x.png` | DAT idle pose | 395686 | `3cd1105504740d06c30c6f294bd8441d9d6889fa` |
| `graphics/units/centurion/centurion_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 397509 | `181279623669d5e7b99d96c203885c7b7903a75a` |
| `graphics/units/centurion/centurion_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 394012 | `ea045d9ccdeb2c781023d6ec0e54c0b44a454074` |
| `graphics/units/centurion/icon.png` | Game icon | 98663 | `0d69e944c91cdcb6228a67aa7110be5217873511` |
| `graphics/units/centurion/icon_transparent.png` | Transparent icon | 100936 | `432cbc718d10822ba369ab1bd76ed4acd6d55414` |
| `graphics/units/chakram_thrower/chakram_thrower_attack_dir06_dat4x.gif` | Attack animation | 603151 | `0c8f95a0d1be0f073fb8b21a06058efc78448a68` |
| `graphics/units/chakram_thrower/chakram_thrower_idle_dir06.png` | Native idle pose | 4435 | `6e26e5bc75258ea904c22551c83f09a906e17c09` |
| `graphics/units/chakram_thrower/chakram_thrower_idle_dir06_dat4x.png` | DAT idle pose | 171401 | `eaaa9eab88ef726de398431d481ca8eec81dbbe3` |
| `graphics/units/chakram_thrower/chakram_thrower_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 172405 | `3dc1288c24e19be8a599f222d25973f218237785` |
| `graphics/units/chakram_thrower/chakram_thrower_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 171216 | `615dcf65dfbd4fcbdcde4dd0ef8bef942a02a9c9` |
| `graphics/units/chakram_thrower/icon.png` | Game icon | 74196 | `366947160970d36079e993a81460a84810f0edf2` |
| `graphics/units/chakram_thrower/icon_transparent.png` | Transparent icon | 77722 | `cf0b83deb56391105d9da03c0e34c79d7141c4fc` |
| `graphics/units/champi_runner/champi_runner_attack_dir06_dat4x.gif` | Attack animation | 626471 | `e964bb5fed1b2e2d5fc78424e5c9667bebcfa547` |
| `graphics/units/champi_runner/champi_runner_idle_dir06.png` | Native idle pose | 3410 | `6a652acf5ac2f1e3a140528f1939017e2559f545` |
| `graphics/units/champi_runner/champi_runner_idle_dir06_dat4x.png` | DAT idle pose | 137236 | `fda3271804d30661def757c33f8a0e79e2ce2042` |
| `graphics/units/champi_runner/champi_runner_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 136363 | `345d48bcdd51c547f49d2b80ab486473693960db` |
| `graphics/units/champi_runner/champi_runner_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 135797 | `d00596f5718e02587349be4b83a0d0841ac27f1d` |
| `graphics/units/champi_runner/icon.png` | Game icon | 50231 | `549a9297220f39dc6527491a364d1cb7743b187e` |
| `graphics/units/champi_runner/icon_transparent.png` | Transparent icon | 53256 | `73737de3e7856008d0ebb20e45937d2202e20630` |
| `graphics/units/champi_scout/champi_scout_attack_dir06_dat4x.gif` | Attack animation | 676546 | `b51e29fe3276ebb40619ea43dc085b3eb19d6a59` |
| `graphics/units/champi_scout/champi_scout_idle_dir06.png` | Native idle pose | 4068 | `a2c54c7dae8f380a2a87245dfc7c866da007da21` |
| `graphics/units/champi_scout/champi_scout_idle_dir06_dat4x.png` | DAT idle pose | 142314 | `02ec39c5ba956992897b010ea54b4ead256c119b` |
| `graphics/units/champi_scout/champi_scout_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 141144 | `217f0bc0dd717b05ec7b85aec78039b0ba3d97ea` |
| `graphics/units/champi_scout/champi_scout_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 143046 | `26dbacea8e9278ff806cd8e823bb5e6c87a05d1a` |
| `graphics/units/champi_scout/icon.png` | Game icon | 53977 | `54b6536624c2b79449404189792d266b87d2750f` |
| `graphics/units/champi_scout/icon_transparent.png` | Transparent icon | 58118 | `c9b1b6080ab1e88636a558e026a0a46ce5033227` |
| `graphics/units/champi_warrior/champi_warrior_attack_dir06_dat4x.gif` | Attack animation | 783731 | `89ba60c093d4613fcb2402bdf102cf36a0a77947` |
| `graphics/units/champi_warrior/champi_warrior_idle_dir06.png` | Native idle pose | 4577 | `5a7dea29cc390712949fdf369034ac869d034e34` |
| `graphics/units/champi_warrior/champi_warrior_idle_dir06_dat4x.png` | DAT idle pose | 152373 | `d5bdb267622684f26fcbb45574da29b8db4cb3a5` |
| `graphics/units/champi_warrior/champi_warrior_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 150721 | `50a18952e59e3c7377bb9b6671d96b7bad671f4a` |
| `graphics/units/champi_warrior/champi_warrior_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 153041 | `9a3dffe170a885c49cd8a8380fa5f7cba47b7c35` |
| `graphics/units/champi_warrior/icon.png` | Game icon | 56246 | `94b8432d534fe6147faf2154263102b983c5758e` |
| `graphics/units/champi_warrior/icon_transparent.png` | Transparent icon | 59788 | `bc6f4fd8b28096d65801113d18433b59b4796641` |
| `graphics/units/champion/champion_attack_dir06_dat4x.gif` | Attack animation | 990734 | `2df2cb28aa88f18cf1830a8b0cda484a69dd5595` |
| `graphics/units/champion/champion_idle_dir06.png` | Native idle pose | 4291 | `d7f8ed2db97a2f4372d3de801baae4b9386ecb89` |
| `graphics/units/champion/champion_idle_dir06_dat4x.png` | DAT idle pose | 200189 | `efc747e6ee8b6de4b09fb74d2438a9785402f330` |
| `graphics/units/champion/champion_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 199095 | `2f18a589fe2c1be89a397c58edbde786953325f6` |
| `graphics/units/champion/champion_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 187967 | `81202e3ddd1d7c46ea11116643ab2233e60ab6e0` |
| `graphics/units/champion/icon.png` | Game icon | 69755 | `5fb6b9c94ba1615ccf6f29a2e7a2f67ea94a9950` |
| `graphics/units/champion/icon_transparent.png` | Transparent icon | 72814 | `5974d6330bee9d528b6ba2b16cc282bd17c416e5` |
| `graphics/units/chu_ko_nu/chu_ko_nu_attack_dir06_dat4x.gif` | Attack animation | 1668770 | `4f1210388f90027f9a4bb969b3104521fff601ee` |
| `graphics/units/chu_ko_nu/chu_ko_nu_idle_dir06.png` | Native idle pose | 5128 | `d84a6382862ea9d40719576b2723219325dd03e8` |
| `graphics/units/chu_ko_nu/chu_ko_nu_idle_dir06_dat4x.png` | DAT idle pose | 196993 | `c14a8b40906693c20e7ddff710b2e191493cb752` |
| `graphics/units/chu_ko_nu/chu_ko_nu_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 197673 | `4af8ddadf68ff7c36150ed6611a668532599e118` |
| `graphics/units/chu_ko_nu/chu_ko_nu_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 192005 | `691a97c9b17ab8ec50c1a015d902b9b41459485d` |
| `graphics/units/chu_ko_nu/icon.png` | Game icon | 92972 | `c6479ee3d4b1d64165f27df913032685d8430759` |
| `graphics/units/chu_ko_nu/icon_transparent.png` | Transparent icon | 97227 | `68039f6d3e8c1cf589f7efe632ebceb746078c90` |
| `graphics/units/composite_bowman/composite_bowman_attack_dir06_dat4x.gif` | Attack animation | 858341 | `a85c6744ad2ea53c3b5c9ed419f9bbea8229426c` |
| `graphics/units/composite_bowman/composite_bowman_idle_dir06.png` | Native idle pose | 4320 | `29917bbbfef348fcc94399ef918742e0fcb0be3a` |
| `graphics/units/composite_bowman/composite_bowman_idle_dir06_dat4x.png` | DAT idle pose | 170227 | `9e3bd9e626ef1bc12878d1def5116229ee06870a` |
| `graphics/units/composite_bowman/composite_bowman_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 172883 | `de6156e7c235ae679e59aaf2f73ab9b794194b08` |
| `graphics/units/composite_bowman/composite_bowman_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 172581 | `ea8688d8eecb56ae121c5d7217ad1968aa9b5d77` |
| `graphics/units/composite_bowman/icon.png` | Game icon | 49661 | `6db5518d59532b0360d776492487af59575eda03` |
| `graphics/units/composite_bowman/icon_transparent.png` | Transparent icon | 53657 | `7fb91b276500ab017b6fa696dca1f9c13e9ee779` |
| `graphics/units/condottiero/condottiero_attack_dir06_dat4x.gif` | Attack animation | 829427 | `fe399e961e4ba64b3f07de43e1310c000762b55f` |
| `graphics/units/condottiero/condottiero_idle_dir06.png` | Native idle pose | 5441 | `cb50efd66c568e64220814c4475df2b5c7623912` |
| `graphics/units/condottiero/condottiero_idle_dir06_dat4x.png` | DAT idle pose | 211431 | `6687513f566b7965c0f41b785dee5f145b929c10` |
| `graphics/units/condottiero/condottiero_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 212479 | `057bab28e1d91834665ad397f0ab509b55b544a7` |
| `graphics/units/condottiero/condottiero_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 208306 | `8ff7a0b44671289a07cd42a5b871e1973593ab89` |
| `graphics/units/condottiero/icon.png` | Game icon | 89083 | `6a77bbdf03ad2fb992ff65b4cd530cc2a0ab354c` |
| `graphics/units/condottiero/icon_transparent.png` | Transparent icon | 91702 | `f7bd66beb2a7ccf35a321afb86ab8525fa89cefb` |
| `graphics/units/conquistador/conquistador_attack_dir06_dat4x.gif` | Attack animation | 3129026 | `0a32578ffd4f399c442fa0568235f01c656662e0` |
| `graphics/units/conquistador/conquistador_idle_dir06.png` | Native idle pose | 11258 | `c88c0770a502f4e7acad176effaea91db791f6af` |
| `graphics/units/conquistador/conquistador_idle_dir06_dat4x.png` | DAT idle pose | 344929 | `c7a7782537256df4bc326fa8a9a155c4a2b8c6cc` |
| `graphics/units/conquistador/conquistador_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 342084 | `8af01d7e0a5b5c49a017a72955eab57cffe0dcc7` |
| `graphics/units/conquistador/conquistador_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 345605 | `563d617e481946d248c11a2f87c219203d120de2` |
| `graphics/units/conquistador/icon.png` | Game icon | 103820 | `add3c6fbd08685950b447b6ce028554253957b04` |
| `graphics/units/conquistador/icon_transparent.png` | Transparent icon | 106144 | `7724c74aee7013c3388478cb8c239caac4130f9f` |
| `graphics/units/coustillier/coustillier_attack_dir06_dat4x.gif` | Attack animation | 1990204 | `4dd197f20c02a8fb505c71a3b657b7f1c92f2d32` |
| `graphics/units/coustillier/coustillier_idle_dir06.png` | Native idle pose | 12143 | `2cf497979a47e4320b376f8f05357a94ae1dddc5` |
| `graphics/units/coustillier/coustillier_idle_dir06_dat4x.png` | DAT idle pose | 486840 | `8baf72e1737ee72373ce38ad62c7fc61f914412e` |
| `graphics/units/coustillier/coustillier_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 487091 | `ce4ed2821a3052cbca223487faf74ba071ee319c` |
| `graphics/units/coustillier/coustillier_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 473483 | `08425beb6658f7b589ce0a4af022eed56f7da01c` |
| `graphics/units/coustillier/icon.png` | Game icon | 96257 | `831a3c79709eed6651f744931007fb11d0002fa7` |
| `graphics/units/coustillier/icon_transparent.png` | Transparent icon | 99307 | `1dcc71680195662522940c4e297c5a2b73d1d8ad` |
| `graphics/units/crossbowman/crossbowman_attack_dir06_dat4x.gif` | Attack animation | 669987 | `f0bc01717193fa96bc9140fe6d12048b8aa44e31` |
| `graphics/units/crossbowman/crossbowman_idle_dir06.png` | Native idle pose | 4279 | `ae8421b6aa77abd996e945c1902140dec6e0d5de` |
| `graphics/units/crossbowman/crossbowman_idle_dir06_dat4x.png` | DAT idle pose | 167757 | `225c3a0be6980037c01e1b7f82992929523cf769` |
| `graphics/units/crossbowman/crossbowman_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 169041 | `79b23ada7be0eb4113549199231a6a428003e610` |
| `graphics/units/crossbowman/crossbowman_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 171263 | `c3054445fa21610ad62c4f7e03127660788e23b4` |
| `graphics/units/crossbowman/icon.png` | Game icon | 76732 | `fdb3508e2f5035c4b584450228c523635410db48` |
| `graphics/units/crossbowman/icon_transparent.png` | Transparent icon | 80827 | `8189e76ffc86088d2de700f3577a8be3fbc5b737` |
| `graphics/units/demo_raft/demo_raft_idle_dir06.png` | Native idle pose | 17817 | `d524992b417f0add03a0b1a87537e2a53a9f1629` |
| `graphics/units/demo_raft/demo_raft_idle_dir06_dat4x.png` | DAT idle pose | 529333 | `cd6b809958fe1c737595f4be892ebb53c6b3aeff` |
| `graphics/units/demo_raft/demo_raft_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 534064 | `d8e9aff532a676aa90abb4385186a222399a2ec8` |
| `graphics/units/demo_raft/demo_raft_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 541802 | `54269888d6bc991e5e15cd5b7243cc7f7a6669fa` |
| `graphics/units/demo_raft/icon.png` | Game icon | 109545 | `d820d0ca0ddc31c42ffc721633798f7f424acee4` |
| `graphics/units/demo_raft/icon_transparent.png` | Transparent icon | 110835 | `9f3a2079a247137b304be57d3e3b5d689932b197` |
| `graphics/units/demo_ship/demo_ship_idle_dir06.png` | Native idle pose | 28509 | `3b91f702965f3027353f17205d6cc710a77c698c` |
| `graphics/units/demo_ship/demo_ship_idle_dir06_dat4x.png` | DAT idle pose | 734179 | `c4eb44650938cd234491fdca522c746edae3e8cf` |
| `graphics/units/demo_ship/demo_ship_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 731718 | `12f9b1211e1194aa332bd6f0405823316ff57253` |
| `graphics/units/demo_ship/demo_ship_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 771640 | `8c4d186054583fb9c5080d87c1447ad0756fceaa` |
| `graphics/units/demo_ship/icon.png` | Game icon | 127307 | `eb942ce02b146476f7d5a4acd22cbebc6531e27a` |
| `graphics/units/demo_ship/icon_transparent.png` | Transparent icon | 128409 | `f96cf4c662a9852ee29f8efcb8608b2304c5a426` |
| `graphics/units/dromon/dromon_idle_dir06.png` | Native idle pose | 89031 | `e77d4ac4ba91ee036290e51ebc90115d9b089d5b` |
| `graphics/units/dromon/dromon_idle_dir06_dat4x.png` | DAT idle pose | 2555964 | `19f99cb4a818cb3bf387f54bf5732eeb8868fd96` |
| `graphics/units/dromon/dromon_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 2563696 | `afa39335fb888541b7c6a7bebe7ac0df7beee412` |
| `graphics/units/dromon/dromon_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 2680359 | `91872c6e77e0d01bb46ce1aac9aa9605d0df96f4` |
| `graphics/units/dromon/icon.png` | Game icon | 124722 | `d778df3b308114c1cff80baec0874748f95bd53f` |
| `graphics/units/dromon/icon_transparent.png` | Transparent icon | 128297 | `e8edb0d4f42b2740d0a316820653e19258f5fbf8` |
| `graphics/units/eagle_scout/eagle_scout_attack_dir06_dat4x.gif` | Attack animation | 809862 | `d64129e4c0177a7f8308b359f8b66c790dd0af34` |
| `graphics/units/eagle_scout/eagle_scout_idle_dir06.png` | Native idle pose | 5028 | `f69ab6c2d414b9f441e77299970e4a3a14d3b7b2` |
| `graphics/units/eagle_scout/eagle_scout_idle_dir06_dat4x.png` | DAT idle pose | 196955 | `91d6538af98579172840ec7151aa5d8855747701` |
| `graphics/units/eagle_scout/eagle_scout_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 196894 | `557c3e0072654609ac28a45a282e894ea1d23e2d` |
| `graphics/units/eagle_scout/eagle_scout_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 193655 | `8101b42d58c3474bfe4487fd0ed7617907edfc4e` |
| `graphics/units/eagle_scout/icon.png` | Game icon | 84756 | `942e2c2b05721db605e717d244efd4a023ded2cb` |
| `graphics/units/eagle_scout/icon_transparent.png` | Transparent icon | 88076 | `c2f517edde9147fdae6a952eb32e0f357a90fcae` |
| `graphics/units/eagle_warrior/eagle_warrior_attack_dir06_dat4x.gif` | Attack animation | 704150 | `d23ccafb707eda0fd353167e83bf7ead86462ce5` |
| `graphics/units/eagle_warrior/eagle_warrior_idle_dir06.png` | Native idle pose | 4374 | `3fb6b2f6fb7a8be9a6de70356478f0b47684359c` |
| `graphics/units/eagle_warrior/eagle_warrior_idle_dir06_dat4x.png` | DAT idle pose | 168424 | `92fc34da67cd7313aafc6c32aed1a4606df8ea31` |
| `graphics/units/eagle_warrior/eagle_warrior_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 169111 | `4a2779a033765b946697de004f9e3e912a60afad` |
| `graphics/units/eagle_warrior/eagle_warrior_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 166940 | `7d60e71a43bdc378fdec93abbe6c26c2f3aff205` |
| `graphics/units/eagle_warrior/icon.png` | Game icon | 86773 | `bba429721dbe0897442a5a9f15749b60a0ec1b91` |
| `graphics/units/eagle_warrior/icon_transparent.png` | Transparent icon | 89721 | `cae111de12906f530a304575645a58720f9961aa` |
| `graphics/units/elephant_archer/elephant_archer_attack_dir06_dat4x.gif` | Attack animation | 7620800 | `c5640334a04817529e852257c49323343b5a4242` |
| `graphics/units/elephant_archer/elephant_archer_idle_dir06.png` | Native idle pose | 40953 | `d9dfc9e68b4da74f35b1be54b51ff76a2fd9c715` |
| `graphics/units/elephant_archer/elephant_archer_idle_dir06_dat4x.png` | DAT idle pose | 1043382 | `b182de0ed84e2a5e4a151ca6eb0a20bdf272406f` |
| `graphics/units/elephant_archer/elephant_archer_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1041556 | `c5b848c37a6a81cd0fb3e15b36d509a3cb705311` |
| `graphics/units/elephant_archer/elephant_archer_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1122449 | `018c4caefd68636dcfdb3646f577f8f693584705` |
| `graphics/units/elephant_archer/icon.png` | Game icon | 128924 | `f26971c4d7fe89ca988b2814fa6473c78bf0d49f` |
| `graphics/units/elephant_archer/icon_transparent.png` | Transparent icon | 130744 | `56e0bb3ede05481d29f3c8232ea127cd2e1713ad` |
| `graphics/units/elite_arambai/elite_arambai_attack_dir06_dat4x.gif` | Attack animation | 2234636 | `b8e154cda0c192402ef8ca27214ae2c6fc20a97d` |
| `graphics/units/elite_arambai/elite_arambai_idle_dir06.png` | Native idle pose | 11966 | `bd2a2fc735bd8d1b8cd91bde449b0cf58b44b610` |
| `graphics/units/elite_arambai/elite_arambai_idle_dir06_dat4x.png` | DAT idle pose | 357462 | `e4ef17d66ecb4167b30ff3777b9a1ce1044026c1` |
| `graphics/units/elite_arambai/elite_arambai_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 357034 | `f104558a6312d090b14a104e5730d06dfe30d28e` |
| `graphics/units/elite_arambai/elite_arambai_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 354749 | `326c34c6f21e2ff420a506d884f90e254befbff7` |
| `graphics/units/elite_arambai/icon.png` | Game icon | 68872 | `3aca45187a00a9a5a02f1aeee758386457e739f5` |
| `graphics/units/elite_arambai/icon_transparent.png` | Transparent icon | 73634 | `00fd4037e7e613779342c0f3772e89a870b35253` |
| `graphics/units/elite_ballista_elephant/elite_ballista_elephant_attack_dir06_dat4x.gif` | Attack animation | 6672460 | `6b124c7f1d0c401b1ec9b5d33cb96312ccc93a48` |
| `graphics/units/elite_ballista_elephant/elite_ballista_elephant_idle_dir06.png` | Native idle pose | 36079 | `79027a413b62b987f7be047c6956e99c21272735` |
| `graphics/units/elite_ballista_elephant/elite_ballista_elephant_idle_dir06_dat4x.png` | DAT idle pose | 958642 | `1ad00e11ff6587e2ceccadb57948cb7582d7d9ea` |
| `graphics/units/elite_ballista_elephant/elite_ballista_elephant_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 950728 | `41a97a9d6c0284fe74a477aa6586fd0ec45292e2` |
| `graphics/units/elite_ballista_elephant/elite_ballista_elephant_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1011530 | `b874c9794b4f99ccac0df59b7c9a3bae27b2c522` |
| `graphics/units/elite_ballista_elephant/icon.png` | Game icon | 124425 | `958541a572df783967e54201b20d222839f86413` |
| `graphics/units/elite_ballista_elephant/icon_transparent.png` | Transparent icon | 126981 | `a97ccb9e59d0fd9a78f34db1f08a1abdf0d37677` |
| `graphics/units/elite_battle_elephant/elite_battle_elephant_attack_dir06_dat4x.gif` | Attack animation | 6502098 | `7797aa8469045d129beb01a784b8aa5fee5fe3d6` |
| `graphics/units/elite_battle_elephant/elite_battle_elephant_idle_dir06.png` | Native idle pose | 36989 | `5c9167e05fb226dafbd72240197c922004ea12f5` |
| `graphics/units/elite_battle_elephant/elite_battle_elephant_idle_dir06_dat4x.png` | DAT idle pose | 927407 | `d8735d52539dcee43a93d21e3aba8238eb421199` |
| `graphics/units/elite_battle_elephant/elite_battle_elephant_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 922955 | `5336a4790c661caba727dd88b7862560f43c4409` |
| `graphics/units/elite_battle_elephant/elite_battle_elephant_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 960504 | `05ead932b6f9165bb31017b6d5b62ce1acd6fb7a` |
| `graphics/units/elite_battle_elephant/icon.png` | Game icon | 114097 | `9850ef1f639eb143875261c04106d745ac866a40` |
| `graphics/units/elite_battle_elephant/icon_transparent.png` | Transparent icon | 116670 | `5ad83ac106e3a571a03b236801f532d88eb63702` |
| `graphics/units/elite_berserk/elite_berserk_attack_dir06_dat4x.gif` | Attack animation | 827273 | `a1e22d75a362a1944418b57e500fc1010711669b` |
| `graphics/units/elite_berserk/elite_berserk_idle_dir06.png` | Native idle pose | 4997 | `f5837621eab98b6258676496c0fad82c7a58bfbd` |
| `graphics/units/elite_berserk/elite_berserk_idle_dir06_dat4x.png` | DAT idle pose | 167072 | `61485a078a6e2c8b190dd134ff7b26f8e484788d` |
| `graphics/units/elite_berserk/elite_berserk_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 168726 | `d652fa29b7cb546ed5f3ae4394ef745262ecf4f8` |
| `graphics/units/elite_berserk/elite_berserk_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 169317 | `b71376783e72d273189283cc63604ef0b1108be6` |
| `graphics/units/elite_berserk/icon.png` | Game icon | 74219 | `d963110627f2a03957bc2afb656d4c914589fc72` |
| `graphics/units/elite_berserk/icon_transparent.png` | Transparent icon | 78335 | `ffa6bdb412c35e3f7f88989e5a0457e4ac414cee` |
| `graphics/units/elite_blackwood_archer/elite_blackwood_archer_attack_dir06_dat4x.gif` | Attack animation | 839593 | `020e64f0abd89c953233177dceb4f460ed9245fa` |
| `graphics/units/elite_blackwood_archer/elite_blackwood_archer_flux_hd.png` | HD unit illustration | 1080007 | `e12f850b203b91ab0502c609a90cf43b190518b8` |
| `graphics/units/elite_blackwood_archer/elite_blackwood_archer_idle_dir06.png` | Native idle pose | 5601 | `2a0267057235cc9aa5a1946ac72ebcf79cc65091` |
| `graphics/units/elite_blackwood_archer/elite_blackwood_archer_idle_dir06_dat4x.png` | DAT idle pose | 208074 | `8bcfca7192cfc5a5bc15c8528ab7052857087eb4` |
| `graphics/units/elite_blackwood_archer/elite_blackwood_archer_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 215610 | `35944a33ac57b7a7637939b44df6163360937cfc` |
| `graphics/units/elite_blackwood_archer/elite_blackwood_archer_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 204591 | `17eecf3cface0392491836c500fc6309b97cc63c` |
| `graphics/units/elite_blackwood_archer/icon.png` | Game icon | 69477 | `31a92e59ac46ecbaca0fd4317de4abedcf5f57fc` |
| `graphics/units/elite_blackwood_archer/icon_transparent.png` | Transparent icon | 76400 | `da3c9a819eec6e77166e450df55eec9f5c573cc4` |
| `graphics/units/elite_bolas_rider/elite_bolas_rider_attack_dir06_dat4x.gif` | Attack animation | 1939225 | `8cf8185275a4c2e68cab8c6f40f0ad270f9d6508` |
| `graphics/units/elite_bolas_rider/elite_bolas_rider_flux_hd.png` | HD unit illustration | 937476 | `309a81d62704f05da00fdee9d1dbfe61ecd42e71` |
| `graphics/units/elite_bolas_rider/elite_bolas_rider_idle_dir06.png` | Native idle pose | 11486 | `13012334d4f0c24ad7948ba74b168cc74d11c6a4` |
| `graphics/units/elite_bolas_rider/elite_bolas_rider_idle_dir06_dat4x.png` | DAT idle pose | 365455 | `70a2b37f3b4df1a92e564217da3be8ac6bed99df` |
| `graphics/units/elite_bolas_rider/elite_bolas_rider_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 368184 | `95c7eba56037db744159d17c273c6771959d50b0` |
| `graphics/units/elite_bolas_rider/elite_bolas_rider_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 362173 | `cc12980a98ffe66d7f1ef4e83d181f0203d7c589` |
| `graphics/units/elite_bolas_rider/icon.png` | Game icon | 72676 | `a4a7cad2aa5fc1127ea6da0e485adfa0b080e0d6` |
| `graphics/units/elite_bolas_rider/icon_transparent.png` | Transparent icon | 76891 | `cdb3b49443e251465f030f088d13e0980221dd9c` |
| `graphics/units/elite_boyar/elite_boyar_attack_dir06_dat4x.gif` | Attack animation | 2498603 | `0b818973a60a11e738e0ddf3b3254ce88275e91c` |
| `graphics/units/elite_boyar/elite_boyar_idle_dir06.png` | Native idle pose | 14945 | `97acc2c47de02a5c45165f4f60c9e3219ad165fd` |
| `graphics/units/elite_boyar/elite_boyar_idle_dir06_dat4x.png` | DAT idle pose | 458261 | `03bd149ef0f618c2f04034e27082eab568b6b6be` |
| `graphics/units/elite_boyar/elite_boyar_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 454461 | `44301dcd61e742b873ce27effd1f5dd765b1a2da` |
| `graphics/units/elite_boyar/elite_boyar_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 455358 | `6dfae33abf663a897c836758cc02777c5e9a3edd` |
| `graphics/units/elite_boyar/icon.png` | Game icon | 83077 | `f07f96ce32395747501ec68eb30065963df88a5d` |
| `graphics/units/elite_boyar/icon_transparent.png` | Transparent icon | 86863 | `b83088e142b7af874c865566c91b9b3143e12f98` |
| `graphics/units/elite_camel_archer/elite_camel_archer_attack_dir06_dat4x.gif` | Attack animation | 2694939 | `ed618e874061d276ef8b7e3234a933708111db1d` |
| `graphics/units/elite_camel_archer/elite_camel_archer_idle_dir06.png` | Native idle pose | 14584 | `c6b92971f8e273f8ab9600c2bf8a263ad3faad74` |
| `graphics/units/elite_camel_archer/elite_camel_archer_idle_dir06_dat4x.png` | DAT idle pose | 489292 | `8fd8867d8e1c0901fb89cc6fb3ce8138dea0094a` |
| `graphics/units/elite_camel_archer/elite_camel_archer_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 487920 | `dc244da94dc1b4ffc0f0a1d3fc4345f8cdf9228f` |
| `graphics/units/elite_camel_archer/elite_camel_archer_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 492632 | `27ede9a9e39834dc08091028145a781ff0862b68` |
| `graphics/units/elite_camel_archer/icon.png` | Game icon | 73854 | `5b28c81038527d1f6221d1f2a17ae836f7cede5b` |
| `graphics/units/elite_camel_archer/icon_transparent.png` | Transparent icon | 78870 | `df7c2afdd7ba63ed11e5fda04c2ae81eb96872b2` |
| `graphics/units/elite_cannon_galleon/elite_cannon_galleon_idle_dir06.png` | Native idle pose | 53620 | `9b70ce47f9531fcc25a035c89288dee4990ef276` |
| `graphics/units/elite_cannon_galleon/elite_cannon_galleon_idle_dir06_dat4x.png` | DAT idle pose | 1273093 | `515c877db140f9dbe31b3f48fc188d6d5da742af` |
| `graphics/units/elite_cannon_galleon/elite_cannon_galleon_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1272755 | `b5d5cf7878efd976297e75c2763b90acf782bb66` |
| `graphics/units/elite_cannon_galleon/elite_cannon_galleon_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1344887 | `c8e19e9aa02be584c9de1dc6ffcc5ca5ce783d96` |
| `graphics/units/elite_cannon_galleon/icon.png` | Game icon | 109635 | `6c6cf718d1116df7b135cbca8295413b9c96d3d4` |
| `graphics/units/elite_cannon_galleon/icon_transparent.png` | Transparent icon | 111459 | `cf8cce912498152a52828c686b3795827b753855` |
| `graphics/units/elite_caravel/elite_caravel_idle_dir06.png` | Native idle pose | 123356 | `f6a30f1cb94c993559075d576eaf11e3f47deb49` |
| `graphics/units/elite_caravel/elite_caravel_idle_dir06_dat4x.png` | DAT idle pose | 2986724 | `12ae76755d9be792f37695ed0b69cac1635e8213` |
| `graphics/units/elite_caravel/elite_caravel_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 2961776 | `f36a8cc37daae553813b85c7dd2f0bcc094f8574` |
| `graphics/units/elite_caravel/elite_caravel_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 3187290 | `11640a9646512bbc073d8759af7fcdad1533ed94` |
| `graphics/units/elite_caravel/icon.png` | Game icon | 109271 | `c9486a0396f05e1fb344998c03eaec14f0edfb01` |
| `graphics/units/elite_caravel/icon_transparent.png` | Transparent icon | 112334 | `6d8746ef3655fbb3678895ec23e0a5e76f28c2d4` |
| `graphics/units/elite_cataphract/elite_cataphract_attack_dir06_dat4x.gif` | Attack animation | 2705731 | `8893fca06aa6226907053bb97e15e46d79c8ee03` |
| `graphics/units/elite_cataphract/elite_cataphract_idle_dir06.png` | Native idle pose | 14282 | `a93a41ea88a1ff723b253a7aedc9bcafb6d392bd` |
| `graphics/units/elite_cataphract/elite_cataphract_idle_dir06_dat4x.png` | DAT idle pose | 436016 | `2ba7e739766d0bb70d02a1adcd9c34676cbe0d60` |
| `graphics/units/elite_cataphract/elite_cataphract_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 435542 | `eb54472775c5c72738b7ef670be063390c37c139` |
| `graphics/units/elite_cataphract/elite_cataphract_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 426805 | `3befb03d891290f9ee6f395faea219675bc51a7a` |
| `graphics/units/elite_cataphract/icon.png` | Game icon | 78389 | `e3674fe5a7510270a09d07f41a6e14b0fe43ce09` |
| `graphics/units/elite_cataphract/icon_transparent.png` | Transparent icon | 81974 | `dc4c825760664268ba5fa1b813c1eae498c83846` |
| `graphics/units/elite_centurion/elite_centurion_attack_dir06_dat4x.gif` | Attack animation | 2599850 | `6c54cc2a7c528c368f54ed67df3e86ef18d7e330` |
| `graphics/units/elite_centurion/elite_centurion_idle_dir06.png` | Native idle pose | 14275 | `3e2f569ba61a95bec0b3bed3bad42acc075241c3` |
| `graphics/units/elite_centurion/elite_centurion_idle_dir06_dat4x.png` | DAT idle pose | 409157 | `af0d623a351d19c920c8efcbe74f53e77fecbefb` |
| `graphics/units/elite_centurion/elite_centurion_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 412584 | `dec8d914294c49ae8b0bc9a1f86073a7ca47cc24` |
| `graphics/units/elite_centurion/elite_centurion_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 406910 | `5fd3ddb475a702cd83ce27e09cc56d53e9b3b5a8` |
| `graphics/units/elite_centurion/icon.png` | Game icon | 78576 | `0f8a306c3e0a06777e911a730c9e4840ff96d4af` |
| `graphics/units/elite_centurion/icon_transparent.png` | Transparent icon | 82037 | `2095aa2e0c46bb4c32d346c0164b927609b68ee5` |
| `graphics/units/elite_chakram_thrower/elite_chakram_thrower_attack_dir06_dat4x.gif` | Attack animation | 722377 | `5e3b6811015c95fb5d3964c3e76c0def87c23016` |
| `graphics/units/elite_chakram_thrower/elite_chakram_thrower_idle_dir06.png` | Native idle pose | 5067 | `92e8f2eac0ab1fc92b359b0a85a9fcd04ab00c21` |
| `graphics/units/elite_chakram_thrower/elite_chakram_thrower_idle_dir06_dat4x.png` | DAT idle pose | 180257 | `458fb82136d231290d7282adc1b1924ce004fde4` |
| `graphics/units/elite_chakram_thrower/elite_chakram_thrower_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 181416 | `5cd5c45a0153f0438515f401232dcbd2d6202cdd` |
| `graphics/units/elite_chakram_thrower/elite_chakram_thrower_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 180086 | `267015fa60935cca63037ba50c2eddc056e6a866` |
| `graphics/units/elite_chakram_thrower/icon.png` | Game icon | 56053 | `ea70969b7499404de598944cb4128e245a1cd692` |
| `graphics/units/elite_chakram_thrower/icon_transparent.png` | Transparent icon | 60105 | `de0a52ad623a189ac08874fe31d99271f3cd0a70` |
| `graphics/units/elite_champi_warrior/elite_champi_warrior_attack_dir06_dat4x.gif` | Attack animation | 876491 | `5fa609ce5f016b6b7fcb2d0e1e790cbc454ea7b0` |
| `graphics/units/elite_champi_warrior/elite_champi_warrior_flux_hd.png` | HD unit illustration | 724916 | `fbf67feee55590840fe9b3da747bd993ff15b257` |
| `graphics/units/elite_champi_warrior/elite_champi_warrior_idle_dir06.png` | Native idle pose | 5331 | `54eb3abd993d651654c310111fba6bb775526b4e` |
| `graphics/units/elite_champi_warrior/elite_champi_warrior_idle_dir06_dat4x.png` | DAT idle pose | 169462 | `41a5c80c7277739747729c2f787cfe24fe96e704` |
| `graphics/units/elite_champi_warrior/elite_champi_warrior_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 169001 | `6f7b25112ff199f3be0e742ef4052072869456cf` |
| `graphics/units/elite_champi_warrior/elite_champi_warrior_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 171509 | `59ac629a02a199674243b747697ed4ebf7b4c94a` |
| `graphics/units/elite_champi_warrior/icon.png` | Game icon | 61364 | `7699fa7dc86c4b3c9bd9040d62993a55d337d8aa` |
| `graphics/units/elite_champi_warrior/icon_transparent.png` | Transparent icon | 65127 | `1f845a08c6877ae8dbd65521f4b4045f4edd7746` |
| `graphics/units/elite_chu_ko_nu/elite_chu_ko_nu_attack_dir06_dat4x.gif` | Attack animation | 1783102 | `7b4203e1fc1ae7ea115437d360ac09132ac4eb0c` |
| `graphics/units/elite_chu_ko_nu/elite_chu_ko_nu_idle_dir06.png` | Native idle pose | 5387 | `2df35054184be20e32f24ffbdac4394f44e0a087` |
| `graphics/units/elite_chu_ko_nu/elite_chu_ko_nu_idle_dir06_dat4x.png` | DAT idle pose | 209456 | `53a788149b3de9b4b2f68bf87e365150110c1f9a` |
| `graphics/units/elite_chu_ko_nu/elite_chu_ko_nu_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 210421 | `92e651471fa178db26ec1c25b63e010f250320c0` |
| `graphics/units/elite_chu_ko_nu/elite_chu_ko_nu_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 207751 | `1fee928595c0eaecf85dff3113c6ac5297f5dd79` |
| `graphics/units/elite_chu_ko_nu/icon.png` | Game icon | 75979 | `921259e238c8bb5f92cdd7ad86bb49f051f63277` |
| `graphics/units/elite_chu_ko_nu/icon_transparent.png` | Transparent icon | 81243 | `90726c75544a3a7d6c10f79f4e521a37f2d31ff5` |
| `graphics/units/elite_composite_bowman/elite_composite_bowman_attack_dir06_dat4x.gif` | Attack animation | 903796 | `667a3596f48dd01676d36e5b169c0e0f9162aee8` |
| `graphics/units/elite_composite_bowman/elite_composite_bowman_idle_dir06.png` | Native idle pose | 4730 | `ceb2e430e03915ad2d5c106bf43db4d9f6de7568` |
| `graphics/units/elite_composite_bowman/elite_composite_bowman_idle_dir06_dat4x.png` | DAT idle pose | 186744 | `5d9c78fe814cebcb1d9ba50a7759b51eac0a405c` |
| `graphics/units/elite_composite_bowman/elite_composite_bowman_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 189781 | `e9b9a43ac4fa91220094ae55dffbb081ebcae780` |
| `graphics/units/elite_composite_bowman/elite_composite_bowman_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 187853 | `561f86023f745d4b97a1641959a05817476aebd2` |
| `graphics/units/elite_composite_bowman/icon.png` | Game icon | 48736 | `55a81f6f361efa3dac4b5c966b38b02885905620` |
| `graphics/units/elite_composite_bowman/icon_transparent.png` | Transparent icon | 52969 | `ce1fa0f3180b66d79a63195c3d85a27e3ff2707a` |
| `graphics/units/elite_conquistador/elite_conquistador_attack_dir06_dat4x.gif` | Attack animation | 3462442 | `4af5abea03836d022dbd65a68825a333609998af` |
| `graphics/units/elite_conquistador/elite_conquistador_idle_dir06.png` | Native idle pose | 11912 | `4df243458ce546cc153abbe7a9f1fabed47aae78` |
| `graphics/units/elite_conquistador/elite_conquistador_idle_dir06_dat4x.png` | DAT idle pose | 350222 | `f00348a584d1cb5aa310059497878f94d9cc33d4` |
| `graphics/units/elite_conquistador/elite_conquistador_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 351884 | `87edf512cf4a6cdcb14c779e2d4b0d95e31ae84e` |
| `graphics/units/elite_conquistador/elite_conquistador_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 351829 | `9a0cd91e797007c236accf970eb43bb9bd23b7fb` |
| `graphics/units/elite_conquistador/icon.png` | Game icon | 74453 | `0436082c324a0a4e597e51f8dab2f5b95b5b4123` |
| `graphics/units/elite_conquistador/icon_transparent.png` | Transparent icon | 77687 | `fbda3c024ea85ba2ff5cb37a272060f4c570b367` |
| `graphics/units/elite_coustillier/elite_coustillier_attack_dir06_dat4x.gif` | Attack animation | 2254601 | `a24d4cff278a16feecc210879708899c9843f853` |
| `graphics/units/elite_coustillier/elite_coustillier_idle_dir06.png` | Native idle pose | 13135 | `39098f1bea959f4bc743583af779db636e24355f` |
| `graphics/units/elite_coustillier/elite_coustillier_idle_dir06_dat4x.png` | DAT idle pose | 492322 | `a9701be38a3d2798ca50b3aafce82c427f779921` |
| `graphics/units/elite_coustillier/elite_coustillier_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 492513 | `c73c14b3df90dfb5c8a2d42675c83df395f6c95a` |
| `graphics/units/elite_coustillier/elite_coustillier_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 478269 | `f49bd01f13d487adf95d16c675ca5740f18b3200` |
| `graphics/units/elite_coustillier/icon.png` | Game icon | 69735 | `2d698a34019dfa49e0514280eed3862525b36a1b` |
| `graphics/units/elite_coustillier/icon_transparent.png` | Transparent icon | 73902 | `f847cb85c607d6b5444c4d8d687654be0f3def83` |
| `graphics/units/elite_eagle_warrior/elite_eagle_warrior_attack_dir06_dat4x.gif` | Attack animation | 886924 | `51efabaf3cf855815126ac20c344cc284904d5b4` |
| `graphics/units/elite_eagle_warrior/elite_eagle_warrior_idle_dir06.png` | Native idle pose | 5620 | `90b10bd74a14f61911261539ccc9b25833e50db3` |
| `graphics/units/elite_eagle_warrior/elite_eagle_warrior_idle_dir06_dat4x.png` | DAT idle pose | 189334 | `eca41034506f2986aa891f4866cd8a78fa0fc828` |
| `graphics/units/elite_eagle_warrior/elite_eagle_warrior_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 190393 | `25531d8dbf162310953d982a965fdc7cdd588c96` |
| `graphics/units/elite_eagle_warrior/elite_eagle_warrior_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 188222 | `fe398dd0b74528d0951a2273ceeff2bedcebe389` |
| `graphics/units/elite_eagle_warrior/icon.png` | Game icon | 104198 | `eae08bf03a0357296510b2ed35c97ddc4238c282` |
| `graphics/units/elite_eagle_warrior/icon_transparent.png` | Transparent icon | 108040 | `8d10adcca125619bc61c21421f8bee5b7f8e319b` |
| `graphics/units/elite_elephant_archer/elite_elephant_archer_attack_dir06_dat4x.gif` | Attack animation | 16134625 | `c19eb95940123d02739211ec3ed9b482f081ade8` |
| `graphics/units/elite_elephant_archer/elite_elephant_archer_idle_dir06.png` | Native idle pose | 44413 | `e2d1aa56aa2b47cda19c83b8e121ef8fdfde26bb` |
| `graphics/units/elite_elephant_archer/elite_elephant_archer_idle_dir06_dat4x.png` | DAT idle pose | 1152419 | `b1cb645af9acf8dc221a94a00784d0beb12596b3` |
| `graphics/units/elite_elephant_archer/elite_elephant_archer_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1156049 | `06b0ab4cac099f37d453e9d72c69024ac9279daa` |
| `graphics/units/elite_elephant_archer/elite_elephant_archer_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1204196 | `5c963edd87e64a055a6414c9789c95c737501962` |
| `graphics/units/elite_elephant_archer/icon.png` | Game icon | 148448 | `a30c9fafb49e7afaa358a71b7a852c139e89143b` |
| `graphics/units/elite_elephant_archer/icon_transparent.png` | Transparent icon | 151025 | `ecc67d372176dc73208f49f0e05279e516f911b3` |
| `graphics/units/elite_fire_archer/elite_fire_archer_attack_dir06_dat4x.gif` | Attack animation | 865863 | `e5440bf44d157e4a514d80ca6d42d227a190d8aa` |
| `graphics/units/elite_fire_archer/elite_fire_archer_flux_hd.png` | HD unit illustration | 864727 | `933ee5c4ae6d771090fa517b203fae1c129c8c6c` |
| `graphics/units/elite_fire_archer/elite_fire_archer_idle_dir06.png` | Native idle pose | 5342 | `9a627d865411aa16c20feaf3d46815049ec7ea61` |
| `graphics/units/elite_fire_archer/elite_fire_archer_idle_dir06_dat4x.png` | DAT idle pose | 223142 | `83c334c9c30408a0078e9be0a1876bbcd3f6e992` |
| `graphics/units/elite_fire_archer/elite_fire_archer_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 224515 | `ce82ee6cb15964ff53b74a41f6ae45964f7b30c6` |
| `graphics/units/elite_fire_archer/elite_fire_archer_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 216269 | `7d47f03eaa093ff24cc2b3b3d75e85265eb806c8` |
| `graphics/units/elite_fire_archer/icon.png` | Game icon | 52562 | `fa05b3968dc8d7b141afd0d359560a8201d65e1c` |
| `graphics/units/elite_fire_archer/icon_transparent.png` | Transparent icon | 57679 | `aed6881fdaddeb3a1f963ae901c92e06805ba15a` |
| `graphics/units/elite_fire_lancer/elite_fire_lancer_attack_dir06_dat4x.gif` | Attack animation | 1300153 | `8f92ffb7198e47781d46f74fc0b9dd8ab7abc818` |
| `graphics/units/elite_fire_lancer/elite_fire_lancer_idle_dir06.png` | Native idle pose | 8166 | `2479f8a78162974ac80559726de76f8a7406356c` |
| `graphics/units/elite_fire_lancer/elite_fire_lancer_idle_dir06_dat4x.png` | DAT idle pose | 320786 | `c7de8e004e382aaf0ddff42256e06127b194b847` |
| `graphics/units/elite_fire_lancer/elite_fire_lancer_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 321786 | `094d09e45c3988870153e5bf19cfd360e70e7097` |
| `graphics/units/elite_fire_lancer/elite_fire_lancer_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 315510 | `c7f903e56b17b36f851b11484e480515171b0d11` |
| `graphics/units/elite_fire_lancer/icon.png` | Game icon | 60354 | `a7f50c857634d4ae8fe4bf90516ddb1d433b725f` |
| `graphics/units/elite_fire_lancer/icon_transparent.png` | Transparent icon | 65126 | `6b9c9973c79254c3ce9d416c46614eefd548af03` |
| `graphics/units/elite_gbeto/elite_gbeto_attack_dir06_dat4x.gif` | Attack animation | 1740116 | `d05c10f50ad1dd3dc2f1ca30c62ddd9cef6d6be9` |
| `graphics/units/elite_gbeto/elite_gbeto_idle_dir06.png` | Native idle pose | 4681 | `24d1735cffd5fa9a50c9b6044acfbf67ca90180f` |
| `graphics/units/elite_gbeto/elite_gbeto_idle_dir06_dat4x.png` | DAT idle pose | 135709 | `b918c8bd67e845ee2a49362f3e732519fa7d3296` |
| `graphics/units/elite_gbeto/elite_gbeto_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 137166 | `d9fbc0db83afca20056f2deeacd040f12bca850a` |
| `graphics/units/elite_gbeto/elite_gbeto_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 137146 | `56001c4d8a8f44c208348a4c4d9fd1683f2e4559` |
| `graphics/units/elite_gbeto/icon.png` | Game icon | 58215 | `d267739b32fd980acbc8f4170b396fe5ea083d44` |
| `graphics/units/elite_gbeto/icon_transparent.png` | Transparent icon | 62809 | `487a46378d3b47e1f022ba2fc377c85ebc453ab3` |
| `graphics/units/elite_genitour/elite_genitour_attack_dir06_dat4x.gif` | Attack animation | 2027299 | `377d2cbb3d279663d5181008967ffc192e1f1ad1` |
| `graphics/units/elite_genitour/elite_genitour_idle_dir06.png` | Native idle pose | 12531 | `fe8f31be0e4ce27b58ae200e4377af4f97075fcd` |
| `graphics/units/elite_genitour/elite_genitour_idle_dir06_dat4x.png` | DAT idle pose | 531545 | `1abf7fe16bfe554f36e03694db136b864a558d67` |
| `graphics/units/elite_genitour/elite_genitour_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 529516 | `59c1ed87369d1a6da6ed07b672dbbe6c1da5c2f6` |
| `graphics/units/elite_genitour/elite_genitour_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 523639 | `897966b9acf9548c514b1d081967b0373c347645` |
| `graphics/units/elite_genitour/icon.png` | Game icon | 74587 | `a74f95c7dc808a866decdffb6dae4ead15f74473` |
| `graphics/units/elite_genitour/icon_transparent.png` | Transparent icon | 79149 | `dc0c2879015b4e128bb9bda0cb73857f29a6f64e` |
| `graphics/units/elite_genoese_crossbowman/elite_genoese_crossbowman_attack_dir06_dat4x.gif` | Attack animation | 980622 | `079cbfe56d51a29dded4ec174cd7378701b851d6` |
| `graphics/units/elite_genoese_crossbowman/elite_genoese_crossbowman_idle_dir06.png` | Native idle pose | 5943 | `4e619c6a27791207a655f96885650d6b9852eaa9` |
| `graphics/units/elite_genoese_crossbowman/elite_genoese_crossbowman_idle_dir06_dat4x.png` | DAT idle pose | 190661 | `56dcd2b9362ef11e6db2efb4c5867b63237e1105` |
| `graphics/units/elite_genoese_crossbowman/elite_genoese_crossbowman_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 191829 | `405514889149cd8d2500982b6574b069a6aee460` |
| `graphics/units/elite_genoese_crossbowman/elite_genoese_crossbowman_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 199560 | `2db48b9f1cd733204d726371b0cb10201bf8edd8` |
| `graphics/units/elite_genoese_crossbowman/icon.png` | Game icon | 74058 | `386ebd588ceb394871ba7f69f9c5f1d97817f481` |
| `graphics/units/elite_genoese_crossbowman/icon_transparent.png` | Transparent icon | 80439 | `b75fdfcefc89f2c1761e777b5213dd1b68eaf5ce` |
| `graphics/units/elite_ghulam/elite_ghulam_attack_dir06_dat4x.gif` | Attack animation | 722942 | `a4b32006197484b19c8abba3b0fb2d550f0205b6` |
| `graphics/units/elite_ghulam/elite_ghulam_idle_dir06.png` | Native idle pose | 4043 | `3efd74bafa4c91e4844fa788597164da285da9d9` |
| `graphics/units/elite_ghulam/elite_ghulam_idle_dir06_dat4x.png` | DAT idle pose | 193793 | `833a69b246f88edab5eb7339576443d444a9acae` |
| `graphics/units/elite_ghulam/elite_ghulam_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 193890 | `4d0fc2298a47d6084d215d326b6de7479c1b1000` |
| `graphics/units/elite_ghulam/elite_ghulam_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 172961 | `d73e06f03aa60132e66eafb5690b513cbbe501af` |
| `graphics/units/elite_ghulam/icon.png` | Game icon | 49545 | `9c4f68bd2a8d28c470309f69d43971fae6ba7474` |
| `graphics/units/elite_ghulam/icon_transparent.png` | Transparent icon | 52307 | `7b04418677e70c741a0146bac980170e50f145d1` |
| `graphics/units/elite_guecha_warrior/elite_guecha_warrior_attack_dir06_dat4x.gif` | Attack animation | 1830991 | `6f4fd9c4a2e52478927d9c420f92879e3422237c` |
| `graphics/units/elite_guecha_warrior/elite_guecha_warrior_flux_hd.png` | HD unit illustration | 785717 | `be6fde4b1190787b9aeee208a489ad24d443ea4b` |
| `graphics/units/elite_guecha_warrior/elite_guecha_warrior_idle_dir06.png` | Native idle pose | 5663 | `74f278c7116103226fa7702ec05bb3d3b0a73d05` |
| `graphics/units/elite_guecha_warrior/elite_guecha_warrior_idle_dir06_dat4x.png` | DAT idle pose | 230297 | `fd0ff8eff1bfd82c6892a7f52ba6b8fcca61a289` |
| `graphics/units/elite_guecha_warrior/elite_guecha_warrior_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 239833 | `1559333cb60087261ee02a915c2412e5e4af56d9` |
| `graphics/units/elite_guecha_warrior/elite_guecha_warrior_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 219111 | `01468de4a892e1def86bb7912d194293b220be41` |
| `graphics/units/elite_guecha_warrior/icon.png` | Game icon | 62782 | `31a29ad2feb393904b41806474d8afeb069ec06d` |
| `graphics/units/elite_guecha_warrior/icon_transparent.png` | Transparent icon | 65329 | `fe8353d9527ae81af4e261a48450ee3e907ae59d` |
| `graphics/units/elite_huskarl/elite_huskarl_attack_dir06_dat4x.gif` | Attack animation | 896958 | `993f9f6159ec84f5d7b3f8eaea4463f4d5fc8a0c` |
| `graphics/units/elite_huskarl/elite_huskarl_idle_dir06.png` | Native idle pose | 5498 | `2c7f05ac541101e54abcc2f898abe2226b23a596` |
| `graphics/units/elite_huskarl/elite_huskarl_idle_dir06_dat4x.png` | DAT idle pose | 187712 | `50c6203ca17d9cb1434aa921f7483c60eb5ad895` |
| `graphics/units/elite_huskarl/elite_huskarl_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 188093 | `8f04fa25c7c601b5e88fca376faef5317726a8b6` |
| `graphics/units/elite_huskarl/elite_huskarl_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 186690 | `375cacec73f36899d9ecb3a778f570b062741369` |
| `graphics/units/elite_huskarl/icon.png` | Game icon | 62528 | `ffc79d84c721cd04f5fdf0143ea3a6daaf40140f` |
| `graphics/units/elite_huskarl/icon_transparent.png` | Transparent icon | 65978 | `b1bc792989257c28b2eb06e9748840e65c4125c8` |
| `graphics/units/elite_hussite_wagon/elite_hussite_wagon_idle_dir06.png` | Native idle pose | 46518 | `bea11777cb17f6750ece45a3402984fc1e1ba75c` |
| `graphics/units/elite_hussite_wagon/elite_hussite_wagon_idle_dir06_dat4x.png` | DAT idle pose | 1094267 | `1e445d7630edcf9b110d93c252fd9a6b760294c9` |
| `graphics/units/elite_hussite_wagon/elite_hussite_wagon_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1099771 | `a2e9a65851cd955107024ac8da7c8d5e70389a0b` |
| `graphics/units/elite_hussite_wagon/elite_hussite_wagon_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1205681 | `c17332f02304fb5867b369ab06d933cac67d53b8` |
| `graphics/units/elite_hussite_wagon/icon.png` | Game icon | 100124 | `0ee80800caf8d5fde8e45231dc3c7dd228098a35` |
| `graphics/units/elite_hussite_wagon/icon_transparent.png` | Transparent icon | 103861 | `b8bda365c669478e6c9edcbae7154af67940cb95` |
| `graphics/units/elite_ibirapema_warrior/elite_ibirapema_warrior_attack_dir06_dat4x.gif` | Attack animation | 1211276 | `cf9199a2903a71e3fa333f815ec28ffb8732ec5a` |
| `graphics/units/elite_ibirapema_warrior/elite_ibirapema_warrior_flux_hd.png` | HD unit illustration | 987930 | `3dd5be5982d764e49bfa82a900f537f4a7613786` |
| `graphics/units/elite_ibirapema_warrior/elite_ibirapema_warrior_idle_dir06.png` | Native idle pose | 4988 | `cbfed59da87952fa523c03ce46baa3d5db1f3e6e` |
| `graphics/units/elite_ibirapema_warrior/elite_ibirapema_warrior_idle_dir06_dat4x.png` | DAT idle pose | 171865 | `df88a196715fdf8d839796c3121660d6ef1b3ee9` |
| `graphics/units/elite_ibirapema_warrior/elite_ibirapema_warrior_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 177127 | `e776f417cca9330c7f5657e41a83125e9f9e6d67` |
| `graphics/units/elite_ibirapema_warrior/elite_ibirapema_warrior_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 173041 | `77c69b3987a93978b875801a43c7a231fe9ba28f` |
| `graphics/units/elite_ibirapema_warrior/icon.png` | Game icon | 71186 | `a956a731fd12b2dcfcc47db45dbe1038e50c942e` |
| `graphics/units/elite_ibirapema_warrior/icon_transparent.png` | Transparent icon | 76909 | `92b17b78a12f4a6be63c80069f48692807ec0e7d` |
| `graphics/units/elite_iron_pagoda/elite_iron_pagoda_attack_dir06_dat4x.gif` | Attack animation | 4062959 | `dfc6fc47e93e2731af4707f32ba14a2ffabeff5b` |
| `graphics/units/elite_iron_pagoda/elite_iron_pagoda_flux_hd.png` | HD unit illustration | 988635 | `82bbd40d66047ac7fe1c5829ddabdbc4e6091c0e` |
| `graphics/units/elite_iron_pagoda/elite_iron_pagoda_idle_dir06.png` | Native idle pose | 15442 | `52710c7160e6cc46ba28eb27c07985ed71d3dd49` |
| `graphics/units/elite_iron_pagoda/elite_iron_pagoda_idle_dir06_dat4x.png` | DAT idle pose | 497594 | `b20d37addc8a17c279a6d84c25b689c3fb46a657` |
| `graphics/units/elite_iron_pagoda/elite_iron_pagoda_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 498350 | `dd6e83d02f5ff7b87dae62cb1b37fd34c3e85845` |
| `graphics/units/elite_iron_pagoda/elite_iron_pagoda_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 486942 | `f19cf69a69963d6ba98857280ed2cfe029339382` |
| `graphics/units/elite_iron_pagoda/icon.png` | Game icon | 73114 | `fd0b35a3cfa85d3734296af95149e5c478855010` |
| `graphics/units/elite_iron_pagoda/icon_transparent.png` | Transparent icon | 76694 | `563efe47b7572ba8411aae4e1e2d138771313ba9` |
| `graphics/units/elite_jaguar_warrior/elite_jaguar_warrior_attack_dir06_dat4x.gif` | Attack animation | 1110834 | `b3f8f22f4ab3c0c6fb5c8d79471ecbbae13a006d` |
| `graphics/units/elite_jaguar_warrior/elite_jaguar_warrior_idle_dir06.png` | Native idle pose | 7077 | `327aa659d850c3324924fd6830ee6c7dcdd26f3f` |
| `graphics/units/elite_jaguar_warrior/elite_jaguar_warrior_idle_dir06_dat4x.png` | DAT idle pose | 265398 | `70ae3d41683bceeacb1ea2a041e38532ef92b188` |
| `graphics/units/elite_jaguar_warrior/elite_jaguar_warrior_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 261380 | `e7ed9765278e0a593c13a99065a108eb06be5e45` |
| `graphics/units/elite_jaguar_warrior/elite_jaguar_warrior_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 252247 | `a4ce5b2ec154cadd815430b67b629b25229f5c0f` |
| `graphics/units/elite_jaguar_warrior/icon.png` | Game icon | 60183 | `9c70eb717e82887e91d47497d0ff945d65aade9c` |
| `graphics/units/elite_jaguar_warrior/icon_transparent.png` | Transparent icon | 64495 | `09ea0d5d8d0f51f5d0f87d4b571cc4638e814799` |
| `graphics/units/elite_janissary/elite_janissary_attack_dir06_dat4x.gif` | Attack animation | 810087 | `fe81dcc955d7ac0e36ece4767b518bd315097cd2` |
| `graphics/units/elite_janissary/elite_janissary_idle_dir06.png` | Native idle pose | 4956 | `639dccb7701b93b66cb9c7ff3964a296c750e755` |
| `graphics/units/elite_janissary/elite_janissary_idle_dir06_dat4x.png` | DAT idle pose | 163386 | `ea3c00b28995ed3246fb7c90699bd77048a54e6a` |
| `graphics/units/elite_janissary/elite_janissary_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 165590 | `0d770f0f7f2d418caa48ebbf7ac73223b655f0f2` |
| `graphics/units/elite_janissary/elite_janissary_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 170400 | `5343cd4832a776582b2d07bba465a234133e9fef` |
| `graphics/units/elite_janissary/icon.png` | Game icon | 56029 | `d3313af4b36789a5023ff59f14ea66613f92cf6b` |
| `graphics/units/elite_janissary/icon_transparent.png` | Transparent icon | 58760 | `c479855364843937ba9fcff991492a556ebedc86` |
| `graphics/units/elite_kamayuk/elite_kamayuk_attack_dir06_dat4x.gif` | Attack animation | 2700219 | `c0c8d02f844c07a61479aaaf09486cfd41e6521d` |
| `graphics/units/elite_kamayuk/elite_kamayuk_idle_dir06.png` | Native idle pose | 6636 | `a450f8551b5add8aac806719f9321807447b2fcb` |
| `graphics/units/elite_kamayuk/elite_kamayuk_idle_dir06_dat4x.png` | DAT idle pose | 283855 | `a23c038860c789fb902cfba3dba1972a86fbb8ff` |
| `graphics/units/elite_kamayuk/elite_kamayuk_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 286360 | `a8ba9b526e926c4c6cfc1a32caa2a56db69ffa51` |
| `graphics/units/elite_kamayuk/elite_kamayuk_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 274918 | `2f9ad7f12fa73b83191e8877fe8569e6faf87ffb` |
| `graphics/units/elite_kamayuk/icon.png` | Game icon | 78748 | `1b138c3eea68399605d9663cf55d3a4fdf1310b1` |
| `graphics/units/elite_kamayuk/icon_transparent.png` | Transparent icon | 83795 | `ac7bf95193e402812ddfb4aa9cf97073eea04241` |
| `graphics/units/elite_karambit_warrior/elite_karambit_warrior_attack_dir06_dat4x.gif` | Attack animation | 750248 | `aae61a8e910c6de9b9339e9c9f9c6ca45c732fff` |
| `graphics/units/elite_karambit_warrior/elite_karambit_warrior_idle_dir06.png` | Native idle pose | 5414 | `f9e6c55b685f3a3ef96aeaf39aecb7b7548de57b` |
| `graphics/units/elite_karambit_warrior/elite_karambit_warrior_idle_dir06_dat4x.png` | DAT idle pose | 210224 | `166045b8a9e8eced2177d7118adad8835ee4eef3` |
| `graphics/units/elite_karambit_warrior/elite_karambit_warrior_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 210582 | `02d32b893222d67eee4cf130f8759c9eacce7eaf` |
| `graphics/units/elite_karambit_warrior/elite_karambit_warrior_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 210136 | `dafefac2f164b74167cbb556f792f450ddca1299` |
| `graphics/units/elite_karambit_warrior/icon.png` | Game icon | 57551 | `6c91ae6cb823777bbd54cfc689a71131c34d6c44` |
| `graphics/units/elite_karambit_warrior/icon_transparent.png` | Transparent icon | 63108 | `1e3877e76ca85311f5be2c8841a0036d3a60e37e` |
| `graphics/units/elite_keshik/elite_keshik_attack_dir06_dat4x.gif` | Attack animation | 3046159 | `6d03d6d0442d5ecf6a1723ff464002e6b2c7322b` |
| `graphics/units/elite_keshik/elite_keshik_idle_dir06.png` | Native idle pose | 16853 | `129412b47ab8889dcca941c11b7e41935c5703cd` |
| `graphics/units/elite_keshik/elite_keshik_idle_dir06_dat4x.png` | DAT idle pose | 497474 | `a58a9f40a51f399ba7d72c3baae8e88015dc3fa9` |
| `graphics/units/elite_keshik/elite_keshik_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 497937 | `1459aa3d66dc41f218f009b8a46a7630a3c30187` |
| `graphics/units/elite_keshik/elite_keshik_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 496533 | `fd192b40bb38b5d3cccf2c9679795dc0c387d4aa` |
| `graphics/units/elite_keshik/icon.png` | Game icon | 74627 | `8af98b232d1c778f5eb01fc9536a4b5c507477e1` |
| `graphics/units/elite_keshik/icon_transparent.png` | Transparent icon | 78118 | `b8b982bfad52a52a87780a47abcab43fcbf3ff2f` |
| `graphics/units/elite_kipchak/elite_kipchak_attack_dir06_dat4x.gif` | Attack animation | 4941161 | `2f8654773c556e9ca981a0d24a054aad7c6fdada` |
| `graphics/units/elite_kipchak/elite_kipchak_idle_dir06.png` | Native idle pose | 13309 | `77c47121fc00721a2e89cf27560a44c032b0bbc5` |
| `graphics/units/elite_kipchak/elite_kipchak_idle_dir06_dat4x.png` | DAT idle pose | 387603 | `3f7fe6fbe7242d313c7fb8a9d2fb36644161c775` |
| `graphics/units/elite_kipchak/elite_kipchak_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 385842 | `17eb853b3c7e64eef6510f1585c37572a20a02f9` |
| `graphics/units/elite_kipchak/elite_kipchak_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 395225 | `10a0247826e00203ae17e9b1b13885701adcf291` |
| `graphics/units/elite_kipchak/icon.png` | Game icon | 69118 | `293c297438f45ee5bb9f16c1aab0e3b46e3d7384` |
| `graphics/units/elite_kipchak/icon_transparent.png` | Transparent icon | 74686 | `aa00fb8beb7ea0b7b3f48b24f571b04d0c2d251e` |
| `graphics/units/elite_kona/elite_kona_attack_dir06_dat4x.gif` | Attack animation | 2835060 | `65ad9b9fa8159135e20d6975fbf7999d2f08bcfc` |
| `graphics/units/elite_kona/elite_kona_flux_hd.png` | HD unit illustration | 819070 | `67155029c23d97fd514f985f8b308dc088e14cc0` |
| `graphics/units/elite_kona/elite_kona_idle_dir06.png` | Native idle pose | 12063 | `8a1e7f0ac9227fb63cec3e1d7711e54e5eb745bf` |
| `graphics/units/elite_kona/elite_kona_idle_dir06_dat4x.png` | DAT idle pose | 399105 | `feedeb14a012a243d3da67451e8b2dfeaa8c7ff4` |
| `graphics/units/elite_kona/elite_kona_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 401905 | `ff537521086bd967a23f1809d08c9689ca2d7519` |
| `graphics/units/elite_kona/elite_kona_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 376445 | `402bf53f3631fea1a6823635671bb5c93214e9d4` |
| `graphics/units/elite_kona/icon.png` | Game icon | 64051 | `756e2adf8c3ca095c5a3d75f9ff5f3d039a5e41d` |
| `graphics/units/elite_kona/icon_transparent.png` | Transparent icon | 67076 | `9978c4928c55447aaacc12bd65349cedad2a1a9b` |
| `graphics/units/elite_konnik/elite_konnik_attack_dir06_dat4x.gif` | Attack animation | 2114792 | `72043108e3ea0334d47dec1e120fb73805cd809b` |
| `graphics/units/elite_konnik/elite_konnik_idle_dir06.png` | Native idle pose | 11741 | `fdb694a0399dda1066d86b93a59f9578f299a71e` |
| `graphics/units/elite_konnik/elite_konnik_idle_dir06_dat4x.png` | DAT idle pose | 358416 | `6b792c0966ead4f2aabed208d052f89d679a687b` |
| `graphics/units/elite_konnik/elite_konnik_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 357161 | `26530af2c436400767d5b072e6a2a529bb3f4624` |
| `graphics/units/elite_konnik/elite_konnik_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 354547 | `51e9465cef4740524b0ccbf347f984f55d57dcc2` |
| `graphics/units/elite_konnik/icon.png` | Game icon | 74930 | `7748c1d2fd3eb07a43ef460df8ed552f4b79159d` |
| `graphics/units/elite_konnik/icon_transparent.png` | Transparent icon | 79815 | `6576817da4c06e9659d8cbeb849df7ce39f1e441` |
| `graphics/units/elite_konnik_dismounted/elite_konnik_dismounted_attack_dir06_dat4x.gif` | Attack animation | 1177045 | `bd06b9a9edc1a242f9f93f50f3c657db42873b6d` |
| `graphics/units/elite_konnik_dismounted/elite_konnik_dismounted_idle_dir06.png` | Native idle pose | 4392 | `33fb5081fb5ee2706ab7a4a13bdd8771bdc2d6c3` |
| `graphics/units/elite_konnik_dismounted/elite_konnik_dismounted_idle_dir06_dat4x.png` | DAT idle pose | 156687 | `573418c277fb2e7dcae35c901d89f269c90b9efa` |
| `graphics/units/elite_konnik_dismounted/elite_konnik_dismounted_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 158273 | `fbeca5619e6fdbd8823f2d5c39b1ea26d8937c03` |
| `graphics/units/elite_konnik_dismounted/elite_konnik_dismounted_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 159042 | `766d1910fab04e1ebc58ef2e963dc3fbb76f661a` |
| `graphics/units/elite_konnik_dismounted/icon.png` | Game icon | 53975 | `65b249c2f3cae793a66901c88a7ea22c5fc2d7ac` |
| `graphics/units/elite_konnik_dismounted/icon_transparent.png` | Transparent icon | 59031 | `42e7bfa9c30bb93a9828e8918eb046f91c1c3f4f` |
| `graphics/units/elite_leitis/elite_leitis_attack_dir06_dat4x.gif` | Attack animation | 4996825 | `f430a4a2276c36dd4d0ddb4fb423877e1fd674d5` |
| `graphics/units/elite_leitis/elite_leitis_idle_dir06.png` | Native idle pose | 13887 | `0eac88c2e90020ef1c3776b37e5eb70b98423e72` |
| `graphics/units/elite_leitis/elite_leitis_idle_dir06_dat4x.png` | DAT idle pose | 425570 | `eda03d3daabfce415b8ac652a578064cf476fb2f` |
| `graphics/units/elite_leitis/elite_leitis_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 425363 | `d25be17e0f049c0cfd427b9087d82a5bc966383f` |
| `graphics/units/elite_leitis/elite_leitis_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 412546 | `62861cff0c6f27c6f49109587b1d75afa0dfad75` |
| `graphics/units/elite_leitis/icon.png` | Game icon | 70734 | `52015d000925c5cd2e0c3ea2f9c82f6cb3ddf919` |
| `graphics/units/elite_leitis/icon_transparent.png` | Transparent icon | 73632 | `8ab3a4bf54866dbb0873faf34f406c14e440c8e6` |
| `graphics/units/elite_liao_dao/elite_liao_dao_attack_dir06_dat4x.gif` | Attack animation | 1393990 | `5f55f4c3c99d4227767d3d63f637cf4be92dc7e8` |
| `graphics/units/elite_liao_dao/elite_liao_dao_idle_dir06.png` | Native idle pose | 5433 | `42b278e0ed1ac67918456c6e3bf2461af8e5ff2c` |
| `graphics/units/elite_liao_dao/elite_liao_dao_idle_dir06_dat4x.png` | DAT idle pose | 200165 | `a7a84e67bf8a234e747c8fc16ccca8b191070c7d` |
| `graphics/units/elite_liao_dao/elite_liao_dao_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 200418 | `75bba1894c961fb941c6f8b36979dc4a196ee56c` |
| `graphics/units/elite_liao_dao/elite_liao_dao_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 195813 | `57e24007a73413b910724b5a3b0e2d584daa8c67` |
| `graphics/units/elite_liao_dao/icon.png` | Game icon | 58601 | `542471257eba045877c99ec1547205335a34c91a` |
| `graphics/units/elite_liao_dao/icon_transparent.png` | Transparent icon | 63240 | `9da7877dbcbe213ae3a1830eaa4fbdcc27bddaec` |
| `graphics/units/elite_longboat/elite_longboat_idle_dir06.png` | Native idle pose | 53778 | `80f293b1704409e8eeb0e214286ca5ce4363a7f4` |
| `graphics/units/elite_longboat/elite_longboat_idle_dir06_dat4x.png` | DAT idle pose | 1343165 | `ab2f58c0450156b8ea604db7dbd6089e6ac844e3` |
| `graphics/units/elite_longboat/elite_longboat_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1391042 | `4c6eeb45163918f6f5edf014a0010387856fb278` |
| `graphics/units/elite_longboat/elite_longboat_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1485256 | `bfafcdc9421ea3b15c5890ce06fcbc02aa6c51bf` |
| `graphics/units/elite_longboat/icon.png` | Game icon | 84603 | `f8efe54b21a0661f85e279c8844d53a6faaf0ded` |
| `graphics/units/elite_longboat/icon_transparent.png` | Transparent icon | 88578 | `8de4b8c1f95da0593403466d627a17ea21fc3a04` |
| `graphics/units/elite_longbowman/elite_longbowman_attack_dir06_dat4x.gif` | Attack animation | 856714 | `9793b67182674efc0159b748c4e49027a7a284f3` |
| `graphics/units/elite_longbowman/elite_longbowman_idle_dir06.png` | Native idle pose | 5672 | `72eb5d3207918228431151a6ced7229638beb77b` |
| `graphics/units/elite_longbowman/elite_longbowman_idle_dir06_dat4x.png` | DAT idle pose | 199192 | `91032d9df45fb9e04678a5de2fa25601dde7f428` |
| `graphics/units/elite_longbowman/elite_longbowman_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 199426 | `ffd76b6bce69bf33e0d416428fe248717dbc3aa9` |
| `graphics/units/elite_longbowman/elite_longbowman_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 200511 | `a9781a64825db1e5889c0a8881a2b2591b68bf22` |
| `graphics/units/elite_longbowman/icon.png` | Game icon | 55884 | `1f132ac30dc4dd488deb53291bb23d8b589ca1f8` |
| `graphics/units/elite_longbowman/icon_transparent.png` | Transparent icon | 61440 | `ea13b16a033b31ed2098a275cd75a8352adfb5e9` |
| `graphics/units/elite_magyar_huszar/elite_magyar_huszar_attack_dir06_dat4x.gif` | Attack animation | 5842771 | `6264aaa0da3e276c0bbdbc15ced77957e7a71b48` |
| `graphics/units/elite_magyar_huszar/elite_magyar_huszar_idle_dir06.png` | Native idle pose | 17200 | `36ab0d0079d86a547eeaf63b8c0c4fc70669bb5a` |
| `graphics/units/elite_magyar_huszar/elite_magyar_huszar_idle_dir06_dat4x.png` | DAT idle pose | 677667 | `d166d5bf0512a8150b719ad83c66d32b4e5fdbb5` |
| `graphics/units/elite_magyar_huszar/elite_magyar_huszar_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 681223 | `32457d38719d902b7f22cf0c64562bbe2f49ce3b` |
| `graphics/units/elite_magyar_huszar/elite_magyar_huszar_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 649352 | `48b3ea980a85a3e5d77f292ff7c67d508559520a` |
| `graphics/units/elite_magyar_huszar/icon.png` | Game icon | 91787 | `c54a91e94e109624110f241c8d113c1bd15089f5` |
| `graphics/units/elite_magyar_huszar/icon_transparent.png` | Transparent icon | 98605 | `801588c34cc35a0391f8511c77b9cc13eccf0e9c` |
| `graphics/units/elite_mameluke/elite_mameluke_attack_dir06_dat4x.gif` | Attack animation | 5779152 | `dc4ecfec726ef998077f5bafd30c1f3e398ec5df` |
| `graphics/units/elite_mameluke/elite_mameluke_idle_dir06.png` | Native idle pose | 17148 | `f59f01093d7aaa87d8fbe3daa1a235ae5049a8df` |
| `graphics/units/elite_mameluke/elite_mameluke_idle_dir06_dat4x.png` | DAT idle pose | 485137 | `b1128657e2884d9f029de80cff7f3d523e1ce523` |
| `graphics/units/elite_mameluke/elite_mameluke_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 482766 | `c0e869017821e239190fd8159331cf290c8417e4` |
| `graphics/units/elite_mameluke/elite_mameluke_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 502153 | `c5d326e0101e2f97dc1a63e33b14b753a1f68df1` |
| `graphics/units/elite_mameluke/icon.png` | Game icon | 74546 | `75d517b7ea90a87b23ae5528b0071e20637dd62e` |
| `graphics/units/elite_mameluke/icon_transparent.png` | Transparent icon | 81112 | `aa691a8e43a85b25f9b569f40609bb7c82e06682` |
| `graphics/units/elite_mangudai/elite_mangudai_attack_dir06_dat4x.gif` | Attack animation | 4470589 | `8aeeb0f1988179c59b82a6b3b6260556dd06cefc` |
| `graphics/units/elite_mangudai/elite_mangudai_idle_dir06.png` | Native idle pose | 11535 | `2697717e5e2632f55e4c7c435d3aeedbfd088366` |
| `graphics/units/elite_mangudai/elite_mangudai_idle_dir06_dat4x.png` | DAT idle pose | 349813 | `6f6938cf275c1bacf97b564c8fd0750fc24f07a0` |
| `graphics/units/elite_mangudai/elite_mangudai_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 352607 | `f94234d311320f7107e1d2465904b1b56af6f3a1` |
| `graphics/units/elite_mangudai/elite_mangudai_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 351883 | `eb5f6c4b974ff5250ad6a227f3583685d7faa546` |
| `graphics/units/elite_mangudai/icon.png` | Game icon | 69399 | `abcaae94ee7c804470133cbd977e23d76cfedc14` |
| `graphics/units/elite_mangudai/icon_transparent.png` | Transparent icon | 74862 | `84141c8f114881206008244bf70e5347a723954d` |
| `graphics/units/elite_monaspa/elite_monaspa_attack_dir06_dat4x.gif` | Attack animation | 2388301 | `757f1c18687de60908a846210775896a315a759e` |
| `graphics/units/elite_monaspa/elite_monaspa_idle_dir06.png` | Native idle pose | 13858 | `c91f194052eb283d90c6c093de3e15a7322f18f6` |
| `graphics/units/elite_monaspa/elite_monaspa_idle_dir06_dat4x.png` | DAT idle pose | 446773 | `41537a9850aa5d73d2c8a71b5d8697d823b08446` |
| `graphics/units/elite_monaspa/elite_monaspa_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 441847 | `5def9bf667fc9fc6fe103802bf0cb045e1a85f8f` |
| `graphics/units/elite_monaspa/elite_monaspa_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 438137 | `73abf57021ce3c8f068f027227bb600a3333716d` |
| `graphics/units/elite_monaspa/icon.png` | Game icon | 69942 | `322ea9bc55d89f8eec83ad5a7a9fae116583eec9` |
| `graphics/units/elite_monaspa/icon_transparent.png` | Transparent icon | 74466 | `043c13bf3b15901692a0554d51106dea388aa9b1` |
| `graphics/units/elite_obuch/elite_obuch_attack_dir06_dat4x.gif` | Attack animation | 750069 | `0d9a66c7041437d517bfd19b8e2f5f22da6e4036` |
| `graphics/units/elite_obuch/elite_obuch_idle_dir06.png` | Native idle pose | 4973 | `ae67e4239e76721878723f2e38575cf38c2686d5` |
| `graphics/units/elite_obuch/elite_obuch_idle_dir06_dat4x.png` | DAT idle pose | 192856 | `e717c4bf31976525c0946ab98e1dc29c4f5bbaac` |
| `graphics/units/elite_obuch/elite_obuch_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 193999 | `1880e97a5fc0ecb5414e2a71745e829747a17429` |
| `graphics/units/elite_obuch/elite_obuch_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 190561 | `ec2625218045121a7f04b956609b939b23c5da0d` |
| `graphics/units/elite_obuch/icon.png` | Game icon | 60049 | `d92920aa64b9e33f1503d9113763634cf4948710` |
| `graphics/units/elite_obuch/icon_transparent.png` | Transparent icon | 66322 | `9ef29f8c253735babe59db408cc03910e018d78c` |
| `graphics/units/elite_organ_gun/elite_organ_gun_attack_dir06_dat4x.gif` | Attack animation | 3885023 | `8ff86b79b1ea46a9548d3f46c07067f17873930a` |
| `graphics/units/elite_organ_gun/elite_organ_gun_idle_dir06.png` | Native idle pose | 10372 | `6a4f7eb79d36d339828b0b8a2d26403aee99098d` |
| `graphics/units/elite_organ_gun/elite_organ_gun_idle_dir06_dat4x.png` | DAT idle pose | 320994 | `2ea687df542f88de3ecc7a1831bee5146013d7b4` |
| `graphics/units/elite_organ_gun/elite_organ_gun_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 319375 | `a7e1da32b8f5b37ed1810de46e69aa6fea0b404c` |
| `graphics/units/elite_organ_gun/elite_organ_gun_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 323857 | `df1630c4fbeb4bbb80bbf36d230285a05ffbdd6d` |
| `graphics/units/elite_organ_gun/icon.png` | Game icon | 82149 | `4459754af061f04c20f58ec4a155856f912ca3b8` |
| `graphics/units/elite_organ_gun/icon_transparent.png` | Transparent icon | 85788 | `59ec2e064b6e719733abeb46615233593b7fa128` |
| `graphics/units/elite_plumed_archer/elite_plumed_archer_attack_dir06_dat4x.gif` | Attack animation | 1305530 | `722ef6ffc62b7c7e7ca7aeb05590943ef32ffcc4` |
| `graphics/units/elite_plumed_archer/elite_plumed_archer_idle_dir06.png` | Native idle pose | 5534 | `0185fe67bf6c0a669c43940e0d781aff233acdfc` |
| `graphics/units/elite_plumed_archer/elite_plumed_archer_idle_dir06_dat4x.png` | DAT idle pose | 204969 | `246d3a42451749580b98b02671454dcee2e99481` |
| `graphics/units/elite_plumed_archer/elite_plumed_archer_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 205556 | `04436f5921234610ece072bcfd7ac412db0085be` |
| `graphics/units/elite_plumed_archer/elite_plumed_archer_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 199846 | `a44ebe5a83ccb54254cbc3517b7d30a0e760ce59` |
| `graphics/units/elite_plumed_archer/icon.png` | Game icon | 54037 | `4327e4caf005f98388db4d05327c176944e13f2e` |
| `graphics/units/elite_plumed_archer/icon_transparent.png` | Transparent icon | 57933 | `32b964dd325b18c992b0f2eaffa8bcd811b94f1e` |
| `graphics/units/elite_ratha_melee/elite_ratha_melee_attack_dir06_dat4x.gif` | Attack animation | 5904739 | `59c4c454b587f070ca28039094e6c18967a126cd` |
| `graphics/units/elite_ratha_melee/elite_ratha_melee_idle_dir06.png` | Native idle pose | 34411 | `34722d3d1592256d079864833b8bb399705c5e60` |
| `graphics/units/elite_ratha_melee/elite_ratha_melee_idle_dir06_dat4x.png` | DAT idle pose | 971587 | `3d25d15996c0063a8fd35a8bfb83d1783552a4c6` |
| `graphics/units/elite_ratha_melee/elite_ratha_melee_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 975722 | `89feafcc6b1192a3afce212b7ef454d67c78da5c` |
| `graphics/units/elite_ratha_melee/elite_ratha_melee_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 968073 | `41192663ea15b68c6e8c73e20622e2d78c167ba7` |
| `graphics/units/elite_ratha_melee/icon.png` | Game icon | 74430 | `2b8e1c3fe2d31001875766e316afe002779a8632` |
| `graphics/units/elite_ratha_melee/icon_transparent.png` | Transparent icon | 77981 | `596f90f16f9f8adb27cb3e29af0775ae3f1b1179` |
| `graphics/units/elite_ratha_ranged/elite_ratha_ranged_attack_dir06_dat4x.gif` | Attack animation | 6148679 | `e4f0aafbaf79b1d1f8d19ddefed5bb332d838b2d` |
| `graphics/units/elite_ratha_ranged/elite_ratha_ranged_idle_dir06.png` | Native idle pose | 35106 | `a4bdeac43394266ed9ec40e579123bc023157179` |
| `graphics/units/elite_ratha_ranged/elite_ratha_ranged_idle_dir06_dat4x.png` | DAT idle pose | 990548 | `3f796f17b7c2fb31f893c8801454463c200b7182` |
| `graphics/units/elite_ratha_ranged/elite_ratha_ranged_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 988586 | `1f62aec99e3c9d10c03d128a3d78e1ce9cc13f5c` |
| `graphics/units/elite_ratha_ranged/elite_ratha_ranged_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 988025 | `d4fbd10c077af94ad9026b35bab01297f5384f00` |
| `graphics/units/elite_ratha_ranged/icon.png` | Game icon | 73962 | `adca3d19082f6a543cf17848f9b3a7364322047e` |
| `graphics/units/elite_ratha_ranged/icon_transparent.png` | Transparent icon | 78508 | `5973d839a8dc0d667a5cc9ec93fbe5091c2cbfa8` |
| `graphics/units/elite_rattan_archer/elite_rattan_archer_attack_dir06_dat4x.gif` | Attack animation | 1385284 | `e71f9e06d75bb78e06e27ec432630e0f876bc642` |
| `graphics/units/elite_rattan_archer/elite_rattan_archer_idle_dir06.png` | Native idle pose | 5113 | `41c5a74ce6c774d2cf5642e371a1f306b1833b97` |
| `graphics/units/elite_rattan_archer/elite_rattan_archer_idle_dir06_dat4x.png` | DAT idle pose | 165878 | `5abcb1acb46b5223fdd5ac9e50ab499091dae04b` |
| `graphics/units/elite_rattan_archer/elite_rattan_archer_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 166901 | `995d75db26ea3f2b5eb9c6d577e71d6e31f6e6d1` |
| `graphics/units/elite_rattan_archer/elite_rattan_archer_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 165697 | `a6ca818ebf01ddbcad47028aa032558dc083c2c5` |
| `graphics/units/elite_rattan_archer/icon.png` | Game icon | 53410 | `721d297da4ef21d536ef9e54eaf8a65224b93f0e` |
| `graphics/units/elite_rattan_archer/icon_transparent.png` | Transparent icon | 57365 | `b1a9652fe4b7f70075263412f1dcdd0bd6727c16` |
| `graphics/units/elite_samurai/elite_samurai_attack_dir06_dat4x.gif` | Attack animation | 1440754 | `41f08357c1448e68afe89ac5cb69d9a10bd171a4` |
| `graphics/units/elite_samurai/elite_samurai_idle_dir06.png` | Native idle pose | 6291 | `4fd656b0628145d33dfb6796e96fda249f51188f` |
| `graphics/units/elite_samurai/elite_samurai_idle_dir06_dat4x.png` | DAT idle pose | 208897 | `4321ba5a4a6e67ea69cd1c4d198f518c998a3c13` |
| `graphics/units/elite_samurai/elite_samurai_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 210180 | `4ce8ce0a58cb935ab3a1ef1f4fd66579c46a1a98` |
| `graphics/units/elite_samurai/elite_samurai_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 205706 | `1447281ea667fac92698f63c214ca377d12949b5` |
| `graphics/units/elite_samurai/icon.png` | Game icon | 65852 | `99ed3226f8078b01e5f1236451511693f977f124` |
| `graphics/units/elite_samurai/icon_transparent.png` | Transparent icon | 69853 | `916a1cdeda9bb607b5ac39146eeb0e3fbd964c86` |
| `graphics/units/elite_serjeant/elite_serjeant_attack_dir06_dat4x.gif` | Attack animation | 931405 | `9a1f34e92e1aac6725c6910804576e04b9da71a1` |
| `graphics/units/elite_serjeant/elite_serjeant_idle_dir06.png` | Native idle pose | 5420 | `d381208a5d56455999b8ad99c505ccb08dbdf0fd` |
| `graphics/units/elite_serjeant/elite_serjeant_idle_dir06_dat4x.png` | DAT idle pose | 184646 | `012125dba58af30abc22e1d9c0a956da679d662b` |
| `graphics/units/elite_serjeant/elite_serjeant_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 186733 | `918803bd1206f3d19a9caec6798120893bd316ff` |
| `graphics/units/elite_serjeant/elite_serjeant_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 183040 | `4e69664896e73c7ff08ad9be9ee8b0b3b7b16a97` |
| `graphics/units/elite_serjeant/icon.png` | Game icon | 61922 | `db2355073d8347a49ec972099724d2453559ca71` |
| `graphics/units/elite_serjeant/icon_transparent.png` | Transparent icon | 66048 | `c60e5df6f9db482dce8e6e3b07b63f8de357ddee` |
| `graphics/units/elite_shotel_warrior/elite_shotel_warrior_attack_dir06_dat4x.gif` | Attack animation | 776081 | `e4f6809c7ee4cf52a332564861f669dac1058551` |
| `graphics/units/elite_shotel_warrior/elite_shotel_warrior_idle_dir06.png` | Native idle pose | 4590 | `4f6b5441167aa83dc13bbdfdf94d4d7bdc723ac2` |
| `graphics/units/elite_shotel_warrior/elite_shotel_warrior_idle_dir06_dat4x.png` | DAT idle pose | 179282 | `018844061ff87a918a1dfadaa2d34fd59efa48e5` |
| `graphics/units/elite_shotel_warrior/elite_shotel_warrior_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 181808 | `886aaf34813b7268d359b7fdc5c328c9588dd588` |
| `graphics/units/elite_shotel_warrior/elite_shotel_warrior_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 176836 | `b60417160863a8064faaf96698f0722ec3274ed4` |
| `graphics/units/elite_shotel_warrior/icon.png` | Game icon | 85624 | `5d80e0c8a128ec8b3cf3d6c90c9f6eeffd5968c7` |
| `graphics/units/elite_shotel_warrior/icon_transparent.png` | Transparent icon | 88383 | `e198a63ecf4ecb0d3222b5d5f9e44b84746819ed` |
| `graphics/units/elite_shrivamsha_rider/elite_shrivamsha_rider_attack_dir06_dat4x.gif` | Attack animation | 1906141 | `28852e39395971088741806d67ba2dd9630216c5` |
| `graphics/units/elite_shrivamsha_rider/elite_shrivamsha_rider_idle_dir06.png` | Native idle pose | 11471 | `cf44b041dd9c60920374bbe118c0b0402d502d97` |
| `graphics/units/elite_shrivamsha_rider/elite_shrivamsha_rider_idle_dir06_dat4x.png` | DAT idle pose | 367167 | `af76692fc1124809e31309583f97e3d1671be016` |
| `graphics/units/elite_shrivamsha_rider/elite_shrivamsha_rider_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 366651 | `50a93b56ab68a8383dc4b373460f4387afa688f8` |
| `graphics/units/elite_shrivamsha_rider/elite_shrivamsha_rider_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 368238 | `91a56b6f9fe6890af437177eab28b4ae7e33117a` |
| `graphics/units/elite_shrivamsha_rider/icon.png` | Game icon | 66335 | `7e26a27448db75b3be0984662ec47fee1ee03d64` |
| `graphics/units/elite_shrivamsha_rider/icon_transparent.png` | Transparent icon | 69642 | `09b66f3bce5495d23ba87a863479fa39c74cc99e` |
| `graphics/units/elite_skirmisher/elite_skirmisher_attack_dir06_dat4x.gif` | Attack animation | 1001483 | `3a48fde398a04d2ce343265487832fff886ef9ff` |
| `graphics/units/elite_skirmisher/elite_skirmisher_idle_dir06.png` | Native idle pose | 3723 | `67ae0929294b5fd51d658c47f526c9978a0f47ed` |
| `graphics/units/elite_skirmisher/elite_skirmisher_idle_dir06_dat4x.png` | DAT idle pose | 171797 | `59535cefd2d4f42beb205e139f59c172d569c113` |
| `graphics/units/elite_skirmisher/elite_skirmisher_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 172356 | `217b4e356d21db2c7cd00e4cbcd24e7024c85d30` |
| `graphics/units/elite_skirmisher/elite_skirmisher_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 162968 | `18269114d2f3cbd2d8e35bb9bf60301b730c17ef` |
| `graphics/units/elite_skirmisher/icon.png` | Game icon | 86370 | `70622f2469ac4d34404840c43c5d80a8769f6eb7` |
| `graphics/units/elite_skirmisher/icon_transparent.png` | Transparent icon | 88821 | `cf7925f6fd223737777ca357b677f08f5f493d03` |
| `graphics/units/elite_steppe_lancer/elite_steppe_lancer_attack_dir06_dat4x.gif` | Attack animation | 4914275 | `98fe839990f08db4519161a488695e26308d8c18` |
| `graphics/units/elite_steppe_lancer/elite_steppe_lancer_idle_dir06.png` | Native idle pose | 13957 | `9beead646c8afbce56b7f7b72a9e28f4f5f291dd` |
| `graphics/units/elite_steppe_lancer/elite_steppe_lancer_idle_dir06_dat4x.png` | DAT idle pose | 493039 | `31889dccaa9a77dddcc31e5577e6022363174566` |
| `graphics/units/elite_steppe_lancer/elite_steppe_lancer_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 493608 | `0ac524dd23d98cd1dd7315b1e88ca91510206b4a` |
| `graphics/units/elite_steppe_lancer/elite_steppe_lancer_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 477034 | `76ad77f3130ddc28a7465ecb06b8a39b412b2154` |
| `graphics/units/elite_steppe_lancer/icon.png` | Game icon | 104714 | `ebb2bd57769ec71f2c63df25aefa62b5592de259` |
| `graphics/units/elite_steppe_lancer/icon_transparent.png` | Transparent icon | 107371 | `a5a09d63efcc52d00024ee75633c0837f0c896f2` |
| `graphics/units/elite_tarkan/elite_tarkan_attack_dir06_dat4x.gif` | Attack animation | 2281562 | `735aa5dbd34f11fe75fa839aaa1bb3d897504cad` |
| `graphics/units/elite_tarkan/elite_tarkan_idle_dir06.png` | Native idle pose | 12754 | `01f26962064236ae987ff543b177690e78c78b7d` |
| `graphics/units/elite_tarkan/elite_tarkan_idle_dir06_dat4x.png` | DAT idle pose | 402259 | `5bb96e6ba7f8e44cffa4cf2b888a2df78e8df865` |
| `graphics/units/elite_tarkan/elite_tarkan_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 403380 | `416b22e3c17101fa4a36ef190875c374aac48933` |
| `graphics/units/elite_tarkan/elite_tarkan_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 398411 | `2d2539f3625d70314081e1b2661d7c7929f00b05` |
| `graphics/units/elite_tarkan/icon.png` | Game icon | 80023 | `fd1331ed81dfc24e43ba57f5bc75d59e8cdbeaa4` |
| `graphics/units/elite_tarkan/icon_transparent.png` | Transparent icon | 84856 | `329cf7313f97e7cb1f6322843d1a06baf7784051` |
| `graphics/units/elite_temple_guard/elite_temple_guard_attack_dir06_dat4x.gif` | Attack animation | 1454130 | `1cce24055f0aa443d5a72db5bbc4d195d22639bb` |
| `graphics/units/elite_temple_guard/elite_temple_guard_flux_hd.png` | HD unit illustration | 772255 | `2acb78293a8f0aaef7588bb92cd2a5e18a1e87c5` |
| `graphics/units/elite_temple_guard/elite_temple_guard_idle_dir06.png` | Native idle pose | 5951 | `78df2a7ed9c247bbd0a022536faea5263d85b124` |
| `graphics/units/elite_temple_guard/elite_temple_guard_idle_dir06_dat4x.png` | DAT idle pose | 239145 | `bd5945901eb8811056dbcf14a9864774bc6854bb` |
| `graphics/units/elite_temple_guard/elite_temple_guard_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 241760 | `ab747756a3fe58f90526bdcd8d165b74ddf93f96` |
| `graphics/units/elite_temple_guard/elite_temple_guard_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 228567 | `d16e93c79ed8f6e9a1ee4c142fcdea73e2883449` |
| `graphics/units/elite_temple_guard/icon.png` | Game icon | 70039 | `add183bceb79fb1bb4079301290c47603c552993` |
| `graphics/units/elite_temple_guard/icon_transparent.png` | Transparent icon | 74736 | `8709939f2b4177b11293b7f05d83470a39d2ee1e` |
| `graphics/units/elite_teutonic_knight/elite_teutonic_knight_attack_dir06_dat4x.gif` | Attack animation | 1881520 | `27763c0df4ada5c59d917813e9b228b3f7952cb1` |
| `graphics/units/elite_teutonic_knight/elite_teutonic_knight_idle_dir06.png` | Native idle pose | 4729 | `71b1525d9454f384a07cc309f8c86dee9f128a06` |
| `graphics/units/elite_teutonic_knight/elite_teutonic_knight_idle_dir06_dat4x.png` | DAT idle pose | 167253 | `cef53dc9aace97bb0a3a56be72a71613af787661` |
| `graphics/units/elite_teutonic_knight/elite_teutonic_knight_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 167295 | `08a3d4eb79d05012c2466d76764a35e71d4c74e2` |
| `graphics/units/elite_teutonic_knight/elite_teutonic_knight_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 165136 | `48389afe41f5d0bafdf45d2c8b5acf7476678b64` |
| `graphics/units/elite_teutonic_knight/icon.png` | Game icon | 71982 | `6760f64cdf001e1055f262fb591bd17eb4eff3b0` |
| `graphics/units/elite_teutonic_knight/icon_transparent.png` | Transparent icon | 75726 | `b6fc102b1ec7c94aa94a26d7518276697df6232a` |
| `graphics/units/elite_throwing_axeman/elite_throwing_axeman_attack_dir06_dat4x.gif` | Attack animation | 1450305 | `14a153837647aa5b1c78b348ff2e7a609bc62d83` |
| `graphics/units/elite_throwing_axeman/elite_throwing_axeman_idle_dir06.png` | Native idle pose | 6216 | `b0cfeb5be27438d7df1cb3d75fba3032ee64f487` |
| `graphics/units/elite_throwing_axeman/elite_throwing_axeman_idle_dir06_dat4x.png` | DAT idle pose | 214741 | `37ca33640a053e801279cd44fb282c228f368e2b` |
| `graphics/units/elite_throwing_axeman/elite_throwing_axeman_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 216243 | `bc7fbfe0027cdbfae29a880f47ddde46ab2c59f2` |
| `graphics/units/elite_throwing_axeman/elite_throwing_axeman_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 210608 | `49e189b051d7cfe355bdd394c68a0b22761e4c5a` |
| `graphics/units/elite_throwing_axeman/icon.png` | Game icon | 72306 | `abcf1c4ba86161f0d3558dc3afec5bafa30d1906` |
| `graphics/units/elite_throwing_axeman/icon_transparent.png` | Transparent icon | 76900 | `e4c1532a563c710e2aacc1fb1dd8b2c92a58b488` |
| `graphics/units/elite_tiger_cavalry/elite_tiger_cavalry_attack_dir06_dat4x.gif` | Attack animation | 5557777 | `8f0c9a2cfe2f1848614e4ca0547b56f427db9297` |
| `graphics/units/elite_tiger_cavalry/elite_tiger_cavalry_flux_hd.png` | HD unit illustration | 993319 | `b6f0b849a3a742383dbb9ddee038889a6c35f526` |
| `graphics/units/elite_tiger_cavalry/elite_tiger_cavalry_idle_dir06.png` | Native idle pose | 16190 | `1e22c94f1333969a5a071c47a9c0ab184f37eb19` |
| `graphics/units/elite_tiger_cavalry/elite_tiger_cavalry_idle_dir06_dat4x.png` | DAT idle pose | 474922 | `151d147a8a8c191b07f3820ec2efc373c22f2882` |
| `graphics/units/elite_tiger_cavalry/elite_tiger_cavalry_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 477875 | `838d3f3f25473357b41fd0bada54b94ee61de96d` |
| `graphics/units/elite_tiger_cavalry/elite_tiger_cavalry_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 472171 | `12514f6d4c8d8de4e7f6c49ba370e359411d8d3f` |
| `graphics/units/elite_tiger_cavalry/icon.png` | Game icon | 75169 | `7b3eaf695cc6189614e2f4ea1ed3bd951fa2e3da` |
| `graphics/units/elite_tiger_cavalry/icon_transparent.png` | Transparent icon | 79362 | `da89418001730ee92c8ccc193db8c41ba462e94b` |
| `graphics/units/elite_turtle_ship/elite_turtle_ship_idle_dir06.png` | Native idle pose | 124508 | `e7cccc80f3a5cbcd10f73fcfe30e476a5d49eb76` |
| `graphics/units/elite_turtle_ship/elite_turtle_ship_idle_dir06_dat4x.png` | DAT idle pose | 3281458 | `64013e1a254d2de523f8292215aca673502712f0` |
| `graphics/units/elite_turtle_ship/elite_turtle_ship_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 3284274 | `74f5a3d8c806e8d179bdbc750c4ba04f9facfaf4` |
| `graphics/units/elite_turtle_ship/elite_turtle_ship_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 3375931 | `9afdd792fa3e95128bc5657d84e33c9e71294e94` |
| `graphics/units/elite_turtle_ship/icon.png` | Game icon | 86556 | `eede6e57162326541c60cdd9e9e7787711e351ca` |
| `graphics/units/elite_turtle_ship/icon_transparent.png` | Transparent icon | 90057 | `bedf3aef542c66ecfeb7ad7a8f13fd95414ffc87` |
| `graphics/units/elite_urumi_swordsman/elite_urumi_swordsman_attack_dir06_dat4x.gif` | Attack animation | 1078503 | `b1975464c909a4ff209c8cc30d7e37470b130017` |
| `graphics/units/elite_urumi_swordsman/elite_urumi_swordsman_idle_dir06.png` | Native idle pose | 3809 | `9d6b4589e5cb81bb9c95c98342da48c807300205` |
| `graphics/units/elite_urumi_swordsman/elite_urumi_swordsman_idle_dir06_dat4x.png` | DAT idle pose | 157739 | `3ff2dcb44b0393d260f41850bf8d76d8ac6dfe34` |
| `graphics/units/elite_urumi_swordsman/elite_urumi_swordsman_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 159247 | `358b1a49e1cddf15f885b482d286e2ffff1f0a1e` |
| `graphics/units/elite_urumi_swordsman/elite_urumi_swordsman_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 156809 | `340b92ee1d66b3cb1967a67ab179eafeba682ea2` |
| `graphics/units/elite_urumi_swordsman/icon.png` | Game icon | 44273 | `8de6aaec1de50651864c06929dc76a8826f8e61f` |
| `graphics/units/elite_urumi_swordsman/icon_transparent.png` | Transparent icon | 49506 | `18c9a7f143853a025f5175611618824bc85b4b0d` |
| `graphics/units/elite_war_chariot/elite_war_chariot_attack_dir06_dat4x.gif` | Attack animation | 6392331 | `0ed2df95190dde57189b9c026e0f740131e8bacb` |
| `graphics/units/elite_war_chariot/elite_war_chariot_idle_dir06.png` | Native idle pose | 34152 | `32e89d613669e3076e449e0d02b8c2a945fd8632` |
| `graphics/units/elite_war_chariot/elite_war_chariot_idle_dir06_dat4x.png` | DAT idle pose | 996921 | `90f85751b378a50a0160ce4e239a2fea3c10d6b9` |
| `graphics/units/elite_war_chariot/elite_war_chariot_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1002920 | `2e793cd7bdb9207359bf5a04f0536ab7e20bb237` |
| `graphics/units/elite_war_chariot/elite_war_chariot_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1028359 | `961cdf2c9fab9488fd189112fda99f9ec5649154` |
| `graphics/units/elite_war_chariot/icon.png` | Game icon | 81094 | `e803bad6e987fa6fa68f3a5c47f7864578bfc343` |
| `graphics/units/elite_war_chariot/icon_transparent.png` | Transparent icon | 83218 | `12a26be099285ea3ba1880390b25cbc544785849` |
| `graphics/units/elite_war_dog/elite_war_dog_attack_dir06_dat4x.gif` | Attack animation | 1179756 | `9d3141e05cea7152ff94fa10da7726341134d9fb` |
| `graphics/units/elite_war_dog/elite_war_dog_idle_dir06.png` | Native idle pose | 4775 | `1f141112bd1ef4a546b01e391caf80c3a06981f9` |
| `graphics/units/elite_war_dog/elite_war_dog_idle_dir06_dat4x.png` | DAT idle pose | 168250 | `e74c71305b42ad6f9b0ace42cc31c7839935c9a1` |
| `graphics/units/elite_war_dog/elite_war_dog_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 168107 | `86cd2bcd81479955f08fbc45b79e21e84adf1d11` |
| `graphics/units/elite_war_dog/elite_war_dog_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 164933 | `d5b128b2a40bcdc213a24260a8a0163084cf0fe5` |
| `graphics/units/elite_war_dog/icon.png` | Game icon | 41620 | `1a56b9bc6fbae93895c6a5407e346d4f852787a9` |
| `graphics/units/elite_war_dog/icon_transparent.png` | Transparent icon | 45958 | `83dadef5d5c1c559c25c60afddfeed95818cfc46` |
| `graphics/units/elite_war_elephant/elite_war_elephant_attack_dir06_dat4x.gif` | Attack animation | 12797641 | `03495ab7a5491f518894c01d84b74b66779cb492` |
| `graphics/units/elite_war_elephant/elite_war_elephant_idle_dir06.png` | Native idle pose | 37618 | `4bd3a98dac59ac14b576bd17480219fd8accf513` |
| `graphics/units/elite_war_elephant/elite_war_elephant_idle_dir06_dat4x.png` | DAT idle pose | 950651 | `28b82d146394d25c7f1d968bb8d0f1baddf292ad` |
| `graphics/units/elite_war_elephant/elite_war_elephant_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 959224 | `cfc428a84a7cff72ce65bf27d8b19c9223e5c078` |
| `graphics/units/elite_war_elephant/elite_war_elephant_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1008100 | `13caf2b6a70157729f198119390111ae18a1f86b` |
| `graphics/units/elite_war_elephant/icon.png` | Game icon | 106412 | `71fe9978cd5e0520e7e18cf2e872b4851c6df8dd` |
| `graphics/units/elite_war_elephant/icon_transparent.png` | Transparent icon | 110075 | `3356eb94edb196aff01bed7bf29562451a5bb9d5` |
| `graphics/units/elite_war_wagon/elite_war_wagon_idle_dir06.png` | Native idle pose | 59685 | `5c31b634845af06d9ebe70be1158a4ac6965036e` |
| `graphics/units/elite_war_wagon/elite_war_wagon_idle_dir06_dat4x.png` | DAT idle pose | 1519853 | `d566455fc88dba239004a1e6be47c9efd5aa01e4` |
| `graphics/units/elite_war_wagon/elite_war_wagon_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1525008 | `e76241771b81747f8f6dd33e95f30e2699f27a3a` |
| `graphics/units/elite_war_wagon/elite_war_wagon_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1629590 | `34785194f8a06752d93b8aea64077c9f7cef90e7` |
| `graphics/units/elite_war_wagon/icon.png` | Game icon | 84994 | `db82330327f4b315e19d09b93d62eec5d55d5393` |
| `graphics/units/elite_war_wagon/icon_transparent.png` | Transparent icon | 89103 | `33d8422b77bbdf32098f093829f8260d44f19036` |
| `graphics/units/elite_white_feather_guard/elite_white_feather_guard_attack_dir06_dat4x.gif` | Attack animation | 1619057 | `a651d283c08981b745322f121d52f1a115f3321a` |
| `graphics/units/elite_white_feather_guard/elite_white_feather_guard_flux_hd.png` | HD unit illustration | 965432 | `72653662b99668185294713093c0218e65b58d37` |
| `graphics/units/elite_white_feather_guard/elite_white_feather_guard_idle_dir06.png` | Native idle pose | 6388 | `3699ab4417d90b5ae981f28c12e0b361583361fb` |
| `graphics/units/elite_white_feather_guard/elite_white_feather_guard_idle_dir06_dat4x.png` | DAT idle pose | 281950 | `6dccdafe9ac16638afbcb53a88fbff6c5f57d586` |
| `graphics/units/elite_white_feather_guard/elite_white_feather_guard_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 284622 | `a7186d505ac64d24a1146bd5a8138b2219a776d2` |
| `graphics/units/elite_white_feather_guard/elite_white_feather_guard_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 277133 | `06adb9586a95cb84418f34c76af70bcd177ab0c4` |
| `graphics/units/elite_white_feather_guard/icon.png` | Game icon | 69547 | `3ef76513a07568cd35b7c0298c55c6ce2f7dac7e` |
| `graphics/units/elite_white_feather_guard/icon_transparent.png` | Transparent icon | 73760 | `dc879f644938a32ffe8ed3b97249a00f152c2b22` |
| `graphics/units/elite_woad_raider/elite_woad_raider_attack_dir06_dat4x.gif` | Attack animation | 1257529 | `18430b575d5798b2bdb3ee3f0b20a58ed76f27b7` |
| `graphics/units/elite_woad_raider/elite_woad_raider_idle_dir06.png` | Native idle pose | 5156 | `437a44c5a75b52b1aa1481e6e39429059b1363c1` |
| `graphics/units/elite_woad_raider/elite_woad_raider_idle_dir06_dat4x.png` | DAT idle pose | 157341 | `a693f9c7ca2ae62ef73e5f1ef2ec15afd13b9321` |
| `graphics/units/elite_woad_raider/elite_woad_raider_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 159710 | `1168061f244794468f95870e23d187da63946417` |
| `graphics/units/elite_woad_raider/elite_woad_raider_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 158994 | `0a5432e5202483596c893f8b9acc2f5d5e0f00bb` |
| `graphics/units/elite_woad_raider/icon.png` | Game icon | 62418 | `ffb0514f6865e519c30eb0e1708152d4e794b278` |
| `graphics/units/elite_woad_raider/icon_transparent.png` | Transparent icon | 66703 | `7cacddab2296c817fd2cbd116442337c34d67617` |
| `graphics/units/fast_fire_ship/fast_fire_ship_idle_dir06.png` | Native idle pose | 46120 | `77a4a49a0f98b4f4e5347975d663b76a33061ffc` |
| `graphics/units/fast_fire_ship/fast_fire_ship_idle_dir06_dat4x.png` | DAT idle pose | 1150759 | `19f99588f134020fa3afe45401de2deaa18dbadc` |
| `graphics/units/fast_fire_ship/fast_fire_ship_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1150759 | `19f99588f134020fa3afe45401de2deaa18dbadc` |
| `graphics/units/fast_fire_ship/fast_fire_ship_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1216949 | `0cdbeaca2361cfef3e077d94ee639264bb497330` |
| `graphics/units/fast_fire_ship/icon.png` | Game icon | 88485 | `cf1cc547abca22a603ca3b3bcab72f84504c1ca9` |
| `graphics/units/fast_fire_ship/icon_transparent.png` | Transparent icon | 90958 | `d4062e710d809e2e465b0a99999cce628cfd47a8` |
| `graphics/units/fire_archer/fire_archer_attack_dir06_dat4x.gif` | Attack animation | 695895 | `7ebfd9c4957a51c0c6029a537ad67633af5a2b88` |
| `graphics/units/fire_archer/fire_archer_idle_dir06.png` | Native idle pose | 4486 | `3b4baa7d1999292789640645aa5eb53a4076e28b` |
| `graphics/units/fire_archer/fire_archer_idle_dir06_dat4x.png` | DAT idle pose | 184378 | `1f3e544deb16d60af49f765eab3ffa973aae46f8` |
| `graphics/units/fire_archer/fire_archer_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 184570 | `a5d28fc02827af150795291b3958171fc69eb1dd` |
| `graphics/units/fire_archer/fire_archer_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 178428 | `61fb556950764ec9f439a99a41e29e14e44c7d48` |
| `graphics/units/fire_archer/icon.png` | Game icon | 44456 | `553341ae2d698156f5ba8cc874002c33884aba0f` |
| `graphics/units/fire_archer/icon_transparent.png` | Transparent icon | 48454 | `05107b65ad4c138e743f663d042308777cfbc980` |
| `graphics/units/fire_galley/fire_galley_idle_dir06.png` | Native idle pose | 28796 | `9b059203bca8b3fe91572cf07579000d8474e02e` |
| `graphics/units/fire_galley/fire_galley_idle_dir06_dat4x.png` | DAT idle pose | 867775 | `faa9900434916bbe6a15141afa93ffc01cc5c81f` |
| `graphics/units/fire_galley/fire_galley_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 881922 | `e4a35a0d76cd96c97cc3a56426fde980560f070f` |
| `graphics/units/fire_galley/fire_galley_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 901365 | `f3c4f41270fcde5bf144650eac9e0b9533d7b0e7` |
| `graphics/units/fire_galley/icon.png` | Game icon | 57265 | `1d58ccf7463f58e19555c82ceebaf2e0bb300415` |
| `graphics/units/fire_galley/icon_transparent.png` | Transparent icon | 58735 | `bc179aa5f5df961c3da400ef2b330faf5f8c7db3` |
| `graphics/units/fire_lancer/fire_lancer_attack_dir06_dat4x.gif` | Attack animation | 1151177 | `ca2f3d4c453aef70717088c3e8b8b8a8308ca646` |
| `graphics/units/fire_lancer/fire_lancer_idle_dir06.png` | Native idle pose | 7320 | `73284bb086ef081bba44dee396c090732db1e38f` |
| `graphics/units/fire_lancer/fire_lancer_idle_dir06_dat4x.png` | DAT idle pose | 300183 | `24e9fdc18e7e3208d1301de1b820f0dd3abd71dd` |
| `graphics/units/fire_lancer/fire_lancer_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 300851 | `49c2a913752654bf800bb2213346ebc6af1d0a88` |
| `graphics/units/fire_lancer/fire_lancer_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 286837 | `60d870abb0a52dba2a2269ee14f424d4e2f5ee41` |
| `graphics/units/fire_lancer/icon.png` | Game icon | 56272 | `a85f14307ee31f6f148ba9b518c44ed4d0e4fdac` |
| `graphics/units/fire_lancer/icon_transparent.png` | Transparent icon | 60343 | `09adf3dcfe485d8087214d0e8ef7bf85e2cecb27` |
| `graphics/units/fire_ship/fire_ship_idle_dir06.png` | Native idle pose | 41579 | `254f9e2d131df346abdca5937dc5e999fec5cd2c` |
| `graphics/units/fire_ship/fire_ship_idle_dir06_dat4x.png` | DAT idle pose | 1084846 | `3d9e354d05417fcffc2661c63df9f2d1176657f5` |
| `graphics/units/fire_ship/fire_ship_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1084846 | `3d9e354d05417fcffc2661c63df9f2d1176657f5` |
| `graphics/units/fire_ship/fire_ship_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1129731 | `962dbaf710c1befdf6df8bcd0ac764bfbd2d33a7` |
| `graphics/units/fire_ship/icon.png` | Game icon | 77532 | `012e6c9ecf8b10cc6a038252a7efc5dd9fb06c35` |
| `graphics/units/fire_ship/icon_transparent.png` | Transparent icon | 79967 | `a1a676dfd09f36b5b6c1fc6c7ce1b2263f51175b` |
| `graphics/units/flemish_militia/flemish_militia_attack_dir06_dat4x.gif` | Attack animation | 756496 | `1353e08b5d7501308d18df08ef40484d9df3f9fb` |
| `graphics/units/flemish_militia/flemish_militia_idle_dir06.png` | Native idle pose | 4874 | `1d78e29ea2c11951ab56b30848cee82bf00698b2` |
| `graphics/units/flemish_militia/flemish_militia_idle_dir06_dat4x.png` | DAT idle pose | 192669 | `b056368d649d93c4aae855825962063dfb346175` |
| `graphics/units/flemish_militia/flemish_militia_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 191573 | `bf27ded02b75d7719fc4fe7c97fe369a920096c3` |
| `graphics/units/flemish_militia/flemish_militia_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 189272 | `4d161220c5deb4cfa936c06dc6dec376cfe8d33d` |
| `graphics/units/flemish_militia/icon.png` | Game icon | 68033 | `9294ff156d39b47c492221fa972f00824c7ba4a9` |
| `graphics/units/flemish_militia/icon_transparent.png` | Transparent icon | 70936 | `a7338a51d6fa7c9509d159771fcacff8227f39eb` |
| `graphics/units/galleon/galleon_idle_dir06.png` | Native idle pose | 61644 | `c2ad4d9fe426fcc19b0c945e81af16159a6e2dea` |
| `graphics/units/galleon/galleon_idle_dir06_dat4x.png` | DAT idle pose | 1500109 | `e5a85e9d52f084e422f20c97f521088a56ce06f4` |
| `graphics/units/galleon/galleon_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1500109 | `e5a85e9d52f084e422f20c97f521088a56ce06f4` |
| `graphics/units/galleon/galleon_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1615576 | `ba85d3a79cdd2633688211cf578e0ace4a1dfc50` |
| `graphics/units/galleon/icon.png` | Game icon | 123001 | `cd6a50c9b6c740273b3659124b92341f22e99265` |
| `graphics/units/galleon/icon_transparent.png` | Transparent icon | 128109 | `8cacfd78dd87b72f6e5b0e3f4d87bb8facc94bf9` |
| `graphics/units/galley/galley_idle_dir06.png` | Native idle pose | 23936 | `d58fb0937325efeebef5610b08f09c05704eb02b` |
| `graphics/units/galley/galley_idle_dir06_dat4x.png` | DAT idle pose | 646804 | `a1d123658026ac66c76810128d4150dc52b8756f` |
| `graphics/units/galley/galley_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 653804 | `d103fe85cb544d9108a6a5ac658dd9c31d3ce4d4` |
| `graphics/units/galley/galley_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 684527 | `f01a30a3a47f923d3a8c5d1f355098153ca66df2` |
| `graphics/units/galley/icon.png` | Game icon | 137970 | `580c3852bf696d3c6982d5467675bba9d44ba5ee` |
| `graphics/units/galley/icon_transparent.png` | Transparent icon | 138908 | `c64147bfe33b1dd251aeddb045ecd19fefa78961` |
| `graphics/units/gbeto/gbeto_attack_dir06_dat4x.gif` | Attack animation | 1485333 | `cd086adf1b1d18682890ba44bc89f5db089cec0f` |
| `graphics/units/gbeto/gbeto_idle_dir06.png` | Native idle pose | 4333 | `23fa820a617a26b60b99f1c7c174372bc221c684` |
| `graphics/units/gbeto/gbeto_idle_dir06_dat4x.png` | DAT idle pose | 136674 | `59193a0a3a12f213572ff2c5af9b83c827173934` |
| `graphics/units/gbeto/gbeto_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 136873 | `ddb6fce3cbea8942870fdb666e7c9c76c27b8832` |
| `graphics/units/gbeto/gbeto_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 134426 | `101e63d589ad254c0d94a61d90385fa17a3921c6` |
| `graphics/units/gbeto/icon.png` | Game icon | 55088 | `3f7a906fefde5754d65d7734e8928b7c64f8a899` |
| `graphics/units/gbeto/icon_transparent.png` | Transparent icon | 59133 | `91c41c0f2c7a15004cf72063e8797bfda8a8c004` |
| `graphics/units/genitour/genitour_attack_dir06_dat4x.gif` | Attack animation | 1868758 | `5e8259e5154eeb616da8a5c94b24bbd1beb73b83` |
| `graphics/units/genitour/genitour_idle_dir06.png` | Native idle pose | 12449 | `e6f9db9e43bbb26542d817f0c91e46fff1c909b7` |
| `graphics/units/genitour/genitour_idle_dir06_dat4x.png` | DAT idle pose | 525830 | `d32e37ad1495c06465a3722f930e88865b3fab48` |
| `graphics/units/genitour/genitour_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 524276 | `eb4150f02932c91107c0c27437a36505d9722830` |
| `graphics/units/genitour/genitour_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 507931 | `fac6b6672cd0f2109f0cb381de705131128b62f6` |
| `graphics/units/genitour/icon.png` | Game icon | 97739 | `af671814814abaf5aca7921701f9dd5ccba8821d` |
| `graphics/units/genitour/icon_transparent.png` | Transparent icon | 100186 | `4b1477560b83903eeac4734817ff2d4da3014a81` |
| `graphics/units/genoese_crossbowman/genoese_crossbowman_attack_dir06_dat4x.gif` | Attack animation | 889806 | `90e8a812227104933e5ed6db7f6a8a2ff85ea98a` |
| `graphics/units/genoese_crossbowman/genoese_crossbowman_idle_dir06.png` | Native idle pose | 5464 | `ca627d3371423b9081a9582d9ad742021568849d` |
| `graphics/units/genoese_crossbowman/genoese_crossbowman_idle_dir06_dat4x.png` | DAT idle pose | 187322 | `683573c71e190842565830f9be653dc50ebec0ff` |
| `graphics/units/genoese_crossbowman/genoese_crossbowman_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 187558 | `5a1ad9ed80d27e44ba95f71d7011659d50fad892` |
| `graphics/units/genoese_crossbowman/genoese_crossbowman_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 194598 | `16ee6c1c6a18a22a81d2f5b2b99c05e85da5d3a1` |
| `graphics/units/genoese_crossbowman/icon.png` | Game icon | 103503 | `0de2639ad794e8bc229c03cfc70c0812763a7510` |
| `graphics/units/genoese_crossbowman/icon_transparent.png` | Transparent icon | 107028 | `300f1c14072d14b5b053425f77860f406ad88506` |
| `graphics/units/ghulam/ghulam_attack_dir06_dat4x.gif` | Attack animation | 723093 | `817835b7c376d3ab47adecdb38fa444ab5523465` |
| `graphics/units/ghulam/ghulam_idle_dir06.png` | Native idle pose | 3890 | `610d80b3f91cb8238313e3df691a7072756c1ceb` |
| `graphics/units/ghulam/ghulam_idle_dir06_dat4x.png` | DAT idle pose | 191950 | `ab6cceafa9058147145e823005d79ef04bca28f5` |
| `graphics/units/ghulam/ghulam_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 189442 | `1c8d05aef8be490c8f06c947f4985ef74084b830` |
| `graphics/units/ghulam/ghulam_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 173826 | `30897e518fdc4b761a083e2dd382765eb6ad3fc8` |
| `graphics/units/ghulam/icon.png` | Game icon | 67541 | `82cd516b637734291aac7355c8f96070625415ea` |
| `graphics/units/ghulam/icon_transparent.png` | Transparent icon | 69917 | `fdfb4770a109a18d393c2e9869eba7d967503be8` |
| `graphics/units/grenadier/grenadier_attack_dir06_dat4x.gif` | Attack animation | 724701 | `9346ae3f05505e7d58cc9d9657313620bbc0927c` |
| `graphics/units/grenadier/grenadier_idle_dir06.png` | Native idle pose | 4218 | `4667e15faa8242eb8d59b431c551db8a1c2851e8` |
| `graphics/units/grenadier/grenadier_idle_dir06_dat4x.png` | DAT idle pose | 141807 | `6eae15799c59ae84e75c700b4799ed131113760d` |
| `graphics/units/grenadier/grenadier_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 142873 | `51127a455f7e56d1d27ad7e9ce271c28ecaaba38` |
| `graphics/units/grenadier/grenadier_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 146672 | `9bf789f853ad811892a5183a1147867e2178f293` |
| `graphics/units/grenadier/icon.png` | Game icon | 50165 | `b7c73729d1bc078fc2eb3ed93aea78051b974fc7` |
| `graphics/units/grenadier/icon_transparent.png` | Transparent icon | 54414 | `cdfd9a92816bd6b1c31b04d4e9830ce8d670d0e8` |
| `graphics/units/guecha_warrior/guecha_warrior_attack_dir06_dat4x.gif` | Attack animation | 1596645 | `a10b12d15d39c12732716e669294c12d145c14bd` |
| `graphics/units/guecha_warrior/guecha_warrior_idle_dir06.png` | Native idle pose | 5163 | `85309028c2b177a7eaacf15b39f91a4ddcdf952f` |
| `graphics/units/guecha_warrior/guecha_warrior_idle_dir06_dat4x.png` | DAT idle pose | 228522 | `f2bb3e663a54fc17606c97b9c8015cea41843362` |
| `graphics/units/guecha_warrior/guecha_warrior_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 237896 | `d015ef1f721422a0ef79648c551c0b342bb0e4d1` |
| `graphics/units/guecha_warrior/guecha_warrior_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 211939 | `f5aea3f5eeb9598dd2ab4c029fbf7bc2b3bee324` |
| `graphics/units/guecha_warrior/icon.png` | Game icon | 58874 | `a27e4020bd33f80a0e27a7b4c5d9ce7c0c3cac1b` |
| `graphics/units/guecha_warrior/icon_transparent.png` | Transparent icon | 62079 | `c140d2c6c6eafebb7e0740a2ad1f43fb1d312d4a` |
| `graphics/units/halberdier/halberdier_attack_dir06_dat4x.gif` | Attack animation | 907726 | `16feebb622945ff7dcdadfbb1963b911b5f5321a` |
| `graphics/units/halberdier/halberdier_idle_dir06.png` | Native idle pose | 5756 | `1b070ff57a77d096eece5c764242ad399eb5601a` |
| `graphics/units/halberdier/halberdier_idle_dir06_dat4x.png` | DAT idle pose | 250530 | `fcbb91051016e366371c5407859b7d7f6b77ef55` |
| `graphics/units/halberdier/halberdier_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 251802 | `9a69993de8f942277b9e5df4cd6209728c7cdf48` |
| `graphics/units/halberdier/halberdier_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 243935 | `5155861dd8d71b8fe0cc4ebebb701233e8feab1c` |
| `graphics/units/halberdier/icon.png` | Game icon | 85162 | `dda8615783776a46e73d5cf3c713c61511e38c3d` |
| `graphics/units/halberdier/icon_transparent.png` | Transparent icon | 88584 | `b0bf591a87fafb94a9c04464180cc51fd2d9d5ee` |
| `graphics/units/hand_cannoneer/hand_cannoneer_attack_dir06_dat4x.gif` | Attack animation | 588265 | `4842af93ee7632d85fa7ee04d4966ea0f76189f3` |
| `graphics/units/hand_cannoneer/hand_cannoneer_idle_dir06.png` | Native idle pose | 4126 | `25c96fd723276f3ca867a5960d18eecc80ee6a62` |
| `graphics/units/hand_cannoneer/hand_cannoneer_idle_dir06_dat4x.png` | DAT idle pose | 154041 | `1938f4f3f98c530e533b7170e5e6e2b6c7900d06` |
| `graphics/units/hand_cannoneer/hand_cannoneer_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 154430 | `288aaeac3427d37905f51c8fe442a0d2b8a04d9d` |
| `graphics/units/hand_cannoneer/hand_cannoneer_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 151574 | `5a4ba6865952966ffbf940c4ef2f938a60ce1332` |
| `graphics/units/hand_cannoneer/icon.png` | Game icon | 73348 | `b41f0fa9092478110cab462abfb295229daa7aa9` |
| `graphics/units/hand_cannoneer/icon_transparent.png` | Transparent icon | 75887 | `d04490af3557b910f2f108159be9ffa534803ece` |
| `graphics/units/heavy_camel_rider/heavy_camel_rider_attack_dir06_dat4x.gif` | Attack animation | 5199142 | `7a36d8c23af8423f0ce884dfea4fe5c6351438d0` |
| `graphics/units/heavy_camel_rider/heavy_camel_rider_idle_dir06.png` | Native idle pose | 15578 | `18ad9770ebaf32ef0e78667e8c90ddd3abe5958d` |
| `graphics/units/heavy_camel_rider/heavy_camel_rider_idle_dir06_dat4x.png` | DAT idle pose | 537929 | `498f689733c492d5918589eadbd3f01e44fbbabe` |
| `graphics/units/heavy_camel_rider/heavy_camel_rider_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 537893 | `2741c7c8684fa7874451ed53bfd3d2538d90cc84` |
| `graphics/units/heavy_camel_rider/heavy_camel_rider_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 541651 | `0ffa5b339e9f7272e853ad5ab88cffd55f0fa4b9` |
| `graphics/units/heavy_camel_rider/icon.png` | Game icon | 98551 | `9f8738a3e11018a2a90d6ac48e9bc5d0bd3c567b` |
| `graphics/units/heavy_camel_rider/icon_transparent.png` | Transparent icon | 101408 | `e9fbe1f2516a466ef757cecb0f13aa2e1e7a3151` |
| `graphics/units/heavy_cavalry_archer/heavy_cavalry_archer_attack_dir06_dat4x.gif` | Attack animation | 4636335 | `0293bf078c482d7674c47d305573cf29296acab5` |
| `graphics/units/heavy_cavalry_archer/heavy_cavalry_archer_idle_dir06.png` | Native idle pose | 13286 | `667470ad62d3f033b4c6b6f29a93ed7ed798767c` |
| `graphics/units/heavy_cavalry_archer/heavy_cavalry_archer_idle_dir06_dat4x.png` | DAT idle pose | 407822 | `4075a545af640b1c995c2548550d57d2bba5e297` |
| `graphics/units/heavy_cavalry_archer/heavy_cavalry_archer_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 407616 | `3d71683704d30caf53ceaa83c1169f32fde4cefc` |
| `graphics/units/heavy_cavalry_archer/heavy_cavalry_archer_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 404754 | `5ec77bcc8a1b9a156a0b41f7278ea455fa9d7dd9` |
| `graphics/units/heavy_cavalry_archer/icon.png` | Game icon | 111679 | `296127a9fa30f3f0e9e5637fb23a3bf553562a89` |
| `graphics/units/heavy_cavalry_archer/icon_transparent.png` | Transparent icon | 115077 | `cbbdbb78cc4dc5a9eb6908d6c7f2f2c3b2f5a1ec` |
| `graphics/units/heavy_demo_ship/heavy_demo_ship_idle_dir06.png` | Native idle pose | 39466 | `0e3032351bafa2352c9aff17454ba5211522129f` |
| `graphics/units/heavy_demo_ship/heavy_demo_ship_idle_dir06_dat4x.png` | DAT idle pose | 1054320 | `b4f402ea7f42682d60f3ef41226ce8100891ccdb` |
| `graphics/units/heavy_demo_ship/heavy_demo_ship_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1052818 | `26b4019b251c4a48bb980f2f8699ced22a878a61` |
| `graphics/units/heavy_demo_ship/heavy_demo_ship_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1128128 | `1b6e108deec0ebc6ad072a202d9809c8c5723385` |
| `graphics/units/heavy_demo_ship/icon.png` | Game icon | 117170 | `aa838dc44ec6339d897a1d05ec7cbc19bcc3f6ce` |
| `graphics/units/heavy_demo_ship/icon_transparent.png` | Transparent icon | 118723 | `4af5f74df46d242f484df78efa03240cf50e8ea2` |
| `graphics/units/heavy_hei_kuang_cavalry/heavy_hei_kuang_cavalry_attack_dir06_dat4x.gif` | Attack animation | 4379502 | `8a7032228bfdaecdc7c5cf71ce978e39eb24be4d` |
| `graphics/units/heavy_hei_kuang_cavalry/heavy_hei_kuang_cavalry_flux_hd.png` | HD unit illustration | 985169 | `86b2585faf2b189d0e2eeda43fc2009a22820791` |
| `graphics/units/heavy_hei_kuang_cavalry/heavy_hei_kuang_cavalry_idle_dir06.png` | Native idle pose | 17043 | `948cd74402045f1afb7b47d0240cb7cb2c5f8332` |
| `graphics/units/heavy_hei_kuang_cavalry/heavy_hei_kuang_cavalry_idle_dir06_dat4x.png` | DAT idle pose | 512774 | `1b9e146e1153a428704715b64912d2c89531ce01` |
| `graphics/units/heavy_hei_kuang_cavalry/heavy_hei_kuang_cavalry_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 516359 | `0c74672eecb5bd18f57c9c923d02db3a32f62cf4` |
| `graphics/units/heavy_hei_kuang_cavalry/heavy_hei_kuang_cavalry_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 509198 | `89fe3508ec35662489960b712d2cc6d35a55b26f` |
| `graphics/units/heavy_hei_kuang_cavalry/icon.png` | Game icon | 77537 | `98932cf2e52e51956e9e7fa4b09306b12f75d923` |
| `graphics/units/heavy_hei_kuang_cavalry/icon_transparent.png` | Transparent icon | 83137 | `b050ff1e726842845a48fb00e99914722f0f25c5` |
| `graphics/units/heavy_rocket_cart/heavy_rocket_cart_attack_dir06_dat4x.gif` | Attack animation | 10430879 | `772de4c75457fc4f4cccd5c634dbeb19a65bbd80` |
| `graphics/units/heavy_rocket_cart/heavy_rocket_cart_idle_dir06.png` | Native idle pose | 26594 | `62c74fc531fd1d3bb38f9bfd41ec9e1462b0a88f` |
| `graphics/units/heavy_rocket_cart/heavy_rocket_cart_idle_dir06_dat4x.png` | DAT idle pose | 745545 | `c81243ee5a351558d28694d15bfbc238fb5be45a` |
| `graphics/units/heavy_rocket_cart/heavy_rocket_cart_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 747806 | `cd6a44d900bcaad0106fc5bb6b8a11116e78b388` |
| `graphics/units/heavy_rocket_cart/heavy_rocket_cart_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 780280 | `a3ed48b25452e7a65e798d13da05694a00d3e840` |
| `graphics/units/heavy_rocket_cart/icon.png` | Game icon | 63160 | `7b68b0cf6d113138a40157d74d674c6cad7956d3` |
| `graphics/units/heavy_rocket_cart/icon_transparent.png` | Transparent icon | 67165 | `ab3693f1964aecbbf03c757dbde1210e61c01bb6` |
| `graphics/units/heavy_scorpion/heavy_scorpion_attack_dir06_dat4x.gif` | Attack animation | 2083528 | `c416fc47eff0bdd2056f20b4c49a8ecdf40311f9` |
| `graphics/units/heavy_scorpion/heavy_scorpion_idle_dir06.png` | Native idle pose | 12221 | `c030060c4aa2eaac51f69cb43eb6c84b86f9b091` |
| `graphics/units/heavy_scorpion/heavy_scorpion_idle_dir06_dat4x.png` | DAT idle pose | 377565 | `8c6f9dec9148aeecdf6ba0903cd6c7e67d16efd2` |
| `graphics/units/heavy_scorpion/heavy_scorpion_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 377724 | `8899dafb3f43ab5f33669d26aa1ddbc2c7b5402e` |
| `graphics/units/heavy_scorpion/heavy_scorpion_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 390042 | `d8079d03b9e964c3011fab30f799f043133a3c95` |
| `graphics/units/heavy_scorpion/icon.png` | Game icon | 73416 | `cd3e09069e80988a5b68ad43db21cdcffc25887a` |
| `graphics/units/heavy_scorpion/icon_transparent.png` | Transparent icon | 77470 | `75e1b8eb99cee5af0e9bd8fbd9eda802e4afcd16` |
| `graphics/units/hei_kuang_cavalry/hei_kuang_cavalry_attack_dir06_dat4x.gif` | Attack animation | 3819826 | `02fdb55109d5f1cf08741566bb536cd189efb85d` |
| `graphics/units/hei_kuang_cavalry/hei_kuang_cavalry_idle_dir06.png` | Native idle pose | 14506 | `0e74e3a1866a58530210b38c0cf0b7f263822af5` |
| `graphics/units/hei_kuang_cavalry/hei_kuang_cavalry_idle_dir06_dat4x.png` | DAT idle pose | 434803 | `9f8222e3bbc69e37a8581e8da1d5c9b273d1894b` |
| `graphics/units/hei_kuang_cavalry/hei_kuang_cavalry_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 435157 | `bfb273047f772691777a53c24b24e468d13837c7` |
| `graphics/units/hei_kuang_cavalry/hei_kuang_cavalry_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 427658 | `6e66e4a915ef25f72b25bb4b01c0f208d0c2b671` |
| `graphics/units/hei_kuang_cavalry/icon.png` | Game icon | 70458 | `27fa06d67c927cba730b34678e02a58cc6dea1c3` |
| `graphics/units/hei_kuang_cavalry/icon_transparent.png` | Transparent icon | 74647 | `9cf49f7e329965c8e2ec970f2ff185d04114cc73` |
| `graphics/units/houfnice/houfnice_attack_dir06_dat4x.gif` | Attack animation | 2578597 | `43ed1d9814121ea822eca1aa89a3d560c157a36e` |
| `graphics/units/houfnice/houfnice_idle_dir06.png` | Native idle pose | 7574 | `68b608e3eb43ffceee2ec521a757af89ea9b9ff8` |
| `graphics/units/houfnice/houfnice_idle_dir06_dat4x.png` | DAT idle pose | 228245 | `973a609d09e4195362b66dce4d2d46953e218927` |
| `graphics/units/houfnice/houfnice_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 228425 | `4a6f679b1345b141695d7b86f551500daca9572f` |
| `graphics/units/houfnice/houfnice_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 238394 | `9d0e937e3afa8e944d224af2795c22f4555da70c` |
| `graphics/units/houfnice/icon.png` | Game icon | 120992 | `3616f3fcd0821989a1713e292aa6519ceaa87825` |
| `graphics/units/houfnice/icon_transparent.png` | Transparent icon | 124254 | `21c6ddd7ac6ae9923a26f51cd30cf8e9f695f8a3` |
| `graphics/units/hulk/hulk_idle_dir06.png` | Native idle pose | 28055 | `7f0e8a406749d0cce9722c2c43966fa873cd7a83` |
| `graphics/units/hulk/hulk_idle_dir06_dat4x.png` | DAT idle pose | 709333 | `08777cbd49d94b920575dcc769fa38dea0a88459` |
| `graphics/units/hulk/hulk_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 708848 | `c9fbeddfab33ecc9ab28d1551df8cc56e3727efb` |
| `graphics/units/hulk/hulk_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 748310 | `ba93b31f6f7351e8e548436b0890d7e4b0a9e53c` |
| `graphics/units/hulk/icon.png` | Game icon | 69841 | `370764d187d6908316bdcd15ea6879905871ab0d` |
| `graphics/units/hulk/icon_transparent.png` | Transparent icon | 73239 | `eb9379badafa87f5b00ec3ac97bbcccff5462aad` |
| `graphics/units/huskarl/huskarl_attack_dir06_dat4x.gif` | Attack animation | 874225 | `08ea46478d28aa9439737e4aedaf070aa62c7c41` |
| `graphics/units/huskarl/huskarl_idle_dir06.png` | Native idle pose | 5214 | `3e23a6c7e7455b3e9d6f0f9687b860b63d573aa7` |
| `graphics/units/huskarl/huskarl_idle_dir06_dat4x.png` | DAT idle pose | 186417 | `2ecdb5ce937e9d207f711691cb88baf9899c4800` |
| `graphics/units/huskarl/huskarl_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 187736 | `40739248fd723a9eada048ee994f4338d0dbb2c9` |
| `graphics/units/huskarl/huskarl_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 185286 | `fafdd58ed225069044ed0b0cb5579d700bdbcf1a` |
| `graphics/units/huskarl/icon.png` | Game icon | 85268 | `b145a3ffe371e8e9d2efdb52d24f3098346ff1f8` |
| `graphics/units/huskarl/icon_transparent.png` | Transparent icon | 87586 | `9b598442c00a1333e142264a4c131977af21f15a` |
| `graphics/units/hussar/hussar_attack_dir06_dat4x.gif` | Attack animation | 2316321 | `3cfd7ce71b63a80a58ca2f63ab5babc562b6d409` |
| `graphics/units/hussar/hussar_idle_dir06.png` | Native idle pose | 15004 | `c643a7a8816a52c5a49acf9691b2345aff362fac` |
| `graphics/units/hussar/hussar_idle_dir06_dat4x.png` | DAT idle pose | 532944 | `0e992ce1fdaf51c15fe9e1e0073931647b35ab2b` |
| `graphics/units/hussar/hussar_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 532193 | `07ef3d1ede2da9df4da81e01c902804222152987` |
| `graphics/units/hussar/hussar_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 522372 | `cba9b6e31e7dbed7f87b472fd87c760871659e9f` |
| `graphics/units/hussar/icon.png` | Game icon | 119495 | `482d255da3c76705e95fb5d2ec9e754264e8e0e7` |
| `graphics/units/hussar/icon_transparent.png` | Transparent icon | 123013 | `b2865aed88219c2d8129e05a8562dd49c8692209` |
| `graphics/units/hussite_wagon/hussite_wagon_idle_dir06.png` | Native idle pose | 45568 | `df39809814c16e06cc0bc8146c73191196997926` |
| `graphics/units/hussite_wagon/hussite_wagon_idle_dir06_dat4x.png` | DAT idle pose | 1095310 | `ff79742fbd7162ca82db95283b7e47bbdbe5fa7f` |
| `graphics/units/hussite_wagon/hussite_wagon_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1096885 | `1ab2a7bfe92335874653f8ffa6b28e3385a99e58` |
| `graphics/units/hussite_wagon/hussite_wagon_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1202411 | `08e8d85c23ef7027c51973ceaefa479aa39613cd` |
| `graphics/units/hussite_wagon/icon.png` | Game icon | 137686 | `c98028ca0820607e0e2d7ae0b54694deaf73df72` |
| `graphics/units/hussite_wagon/icon_transparent.png` | Transparent icon | 140708 | `48c5d35277ecefd6cf62f03edd3d535fffff593d` |
| `graphics/units/ibirapema_warrior/ibirapema_warrior_attack_dir06_dat4x.gif` | Attack animation | 986607 | `e379e595296cdaaa1505232a278a0ce0f2b508f4` |
| `graphics/units/ibirapema_warrior/ibirapema_warrior_idle_dir06.png` | Native idle pose | 4428 | `9d9175c42c97d71ea7b19b90064bb23e4f7f79a4` |
| `graphics/units/ibirapema_warrior/ibirapema_warrior_idle_dir06_dat4x.png` | DAT idle pose | 158989 | `2b2169cfe44c53180a39cca156b67f72726a4fc8` |
| `graphics/units/ibirapema_warrior/ibirapema_warrior_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 162032 | `4ccb7a0fafafd74e6724475115f0b497a069450f` |
| `graphics/units/ibirapema_warrior/ibirapema_warrior_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 161021 | `1c24650db48dd6b277d78004b6fdcdd304c0028a` |
| `graphics/units/ibirapema_warrior/icon.png` | Game icon | 61025 | `e0cb9d2fe151fa4677bbb026b096e480d00169c0` |
| `graphics/units/ibirapema_warrior/icon_transparent.png` | Transparent icon | 65134 | `c3ef9d0818ac278ec1edc897f23123af1e11ccbf` |
| `graphics/units/imperial_camel_rider/icon.png` | Game icon | 94704 | `37c2143fb5bdbfc4394f103e1b6a1e0b6f16ec8d` |
| `graphics/units/imperial_camel_rider/icon_transparent.png` | Transparent icon | 97580 | `90085ff256db164655197c9df7de8efe52bbda30` |
| `graphics/units/imperial_camel_rider/imperial_camel_rider_attack_dir06_dat4x.gif` | Attack animation | 5359058 | `fd57f373ab55965106fa7533fd5eb225f5b3e1ad` |
| `graphics/units/imperial_camel_rider/imperial_camel_rider_idle_dir06.png` | Native idle pose | 16181 | `8bc1545b54f693b25a2e005c5f6c72001e62b2c1` |
| `graphics/units/imperial_camel_rider/imperial_camel_rider_idle_dir06_dat4x.png` | DAT idle pose | 536049 | `4fd7a1f3ccdb9d788c6fdb605e83df0a21daa967` |
| `graphics/units/imperial_camel_rider/imperial_camel_rider_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 534513 | `294a3aba2d702aab6dfb8ee04c53ae00d27d3ff7` |
| `graphics/units/imperial_camel_rider/imperial_camel_rider_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 540185 | `794a088d7761e25f0e64fa3613bbff5ab16e9028` |
| `graphics/units/imperial_skirmisher/icon.png` | Game icon | 72915 | `2f08f15e3ccdb3eba929bc7443f88f8cbb9e3ff1` |
| `graphics/units/imperial_skirmisher/icon_transparent.png` | Transparent icon | 75202 | `b3609fa0a226aa44855f97a97c4d369eda45a5ef` |
| `graphics/units/imperial_skirmisher/imperial_skirmisher_attack_dir06_dat4x.gif` | Attack animation | 999498 | `a342e9b45fefa3ea091173c41373b2d120cd2a83` |
| `graphics/units/imperial_skirmisher/imperial_skirmisher_idle_dir06.png` | Native idle pose | 4021 | `f152b3aff4924595a7dd708938e7db3fda53067a` |
| `graphics/units/imperial_skirmisher/imperial_skirmisher_idle_dir06_dat4x.png` | DAT idle pose | 165678 | `592e7a6fb6b9823f48191cf6b8ae6fb608d09b29` |
| `graphics/units/imperial_skirmisher/imperial_skirmisher_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 167666 | `2c0198f5d6c2e33ae61d2564e019c740d941fe16` |
| `graphics/units/imperial_skirmisher/imperial_skirmisher_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 159239 | `82e148e71ab1043677b3b11064940078101516e4` |
| `graphics/units/iron_pagoda/icon.png` | Game icon | 69695 | `81f5dcc71b882cc3d35ac5be91f4394ff2b6e484` |
| `graphics/units/iron_pagoda/icon_transparent.png` | Transparent icon | 73708 | `58dec2273ce721b1d465ed2e2119d0aac58c6590` |
| `graphics/units/iron_pagoda/iron_pagoda_attack_dir06_dat4x.gif` | Attack animation | 4065481 | `809d82b9217833b72195b8165b325a9f4a9bb87a` |
| `graphics/units/iron_pagoda/iron_pagoda_idle_dir06.png` | Native idle pose | 14336 | `8f86e00e314ec5a9dfcddceaf8bdd376e5f21430` |
| `graphics/units/iron_pagoda/iron_pagoda_idle_dir06_dat4x.png` | DAT idle pose | 471166 | `c28c1da7ef5550642df8d531d86df6550dab8885` |
| `graphics/units/iron_pagoda/iron_pagoda_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 474146 | `9c889eb6a84d816aac700ade7aa6f46d2b372a5d` |
| `graphics/units/iron_pagoda/iron_pagoda_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 476411 | `644853010c89dcba2b7fcb7d0e24930d5c2b317e` |
| `graphics/units/jaguar_warrior/icon.png` | Game icon | 88180 | `6893acca4c6dfda6df841c7089b8672fd3a62463` |
| `graphics/units/jaguar_warrior/icon_transparent.png` | Transparent icon | 90542 | `f7a6271d38d8382925ffafb44574b6254ba28639` |
| `graphics/units/jaguar_warrior/jaguar_warrior_attack_dir06_dat4x.gif` | Attack animation | 750468 | `f10aec5dd07f345692549a2050da6d005d1f3e13` |
| `graphics/units/jaguar_warrior/jaguar_warrior_idle_dir06.png` | Native idle pose | 4528 | `c4affa0447a184d36c78d2d1151ca45b7284e57b` |
| `graphics/units/jaguar_warrior/jaguar_warrior_idle_dir06_dat4x.png` | DAT idle pose | 160024 | `d315120b08379a8a7781582d5f9b461761e33540` |
| `graphics/units/jaguar_warrior/jaguar_warrior_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 162069 | `e5e4ea5f36c12db541370736f62c9dd87048df7e` |
| `graphics/units/jaguar_warrior/jaguar_warrior_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 163591 | `179cf32789f5b7620dfea135f32d1d738d3cc868` |
| `graphics/units/janissary/icon.png` | Game icon | 72922 | `860654211cf21ed980ad2e87f1a4a3247b3fa5d5` |
| `graphics/units/janissary/icon_transparent.png` | Transparent icon | 74678 | `9ea744d5a18da2027605d88092118b2c344019ac` |
| `graphics/units/janissary/janissary_attack_dir06_dat4x.gif` | Attack animation | 680982 | `d01887905e15e2e56915810978ae430bfe1c102d` |
| `graphics/units/janissary/janissary_idle_dir06.png` | Native idle pose | 4111 | `79829ffecf39a3831dbc1277f8f0aba34002bda6` |
| `graphics/units/janissary/janissary_idle_dir06_dat4x.png` | DAT idle pose | 140415 | `470379d02d143846d8084765fa78385ac95c4585` |
| `graphics/units/janissary/janissary_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 141269 | `1a9a24f2778f126f520bda4b85cec5c0c467d212` |
| `graphics/units/janissary/janissary_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 144971 | `3aabdcec716fab1b0444b1e9156859582236904d` |
| `graphics/units/jian_swordsman/icon.png` | Game icon | 49863 | `e98aba6dc9295568161e09b03e3fd2f3ecf705fe` |
| `graphics/units/jian_swordsman/icon_transparent.png` | Transparent icon | 53317 | `445a7f5e87a2b4ac79c14bba940214c385c38d03` |
| `graphics/units/jian_swordsman/jian_swordsman_attack_dir06_dat4x.gif` | Attack animation | 1255156 | `edade891b48260e776a78806304ab157f4df0fe1` |
| `graphics/units/jian_swordsman/jian_swordsman_flux_hd.png` | HD unit illustration | 1357493 | `4e461930b85b5d07a98cea238eb57e80b9d151d7` |
| `graphics/units/jian_swordsman/jian_swordsman_idle_dir06.png` | Native idle pose | 4694 | `7a4d6ecbd9773797cace77f9cc879a3a287d7048` |
| `graphics/units/jian_swordsman/jian_swordsman_idle_dir06_dat4x.png` | DAT idle pose | 162336 | `67c1402f1059397d401e8e0a838d40f5139407bb` |
| `graphics/units/jian_swordsman/jian_swordsman_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 163991 | `2dac750f511bece726b4bb2dd3c7197fd744ce82` |
| `graphics/units/jian_swordsman/jian_swordsman_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 161207 | `26fef88b4709011ab0c778a4ffd37d34a95c49ce` |
| `graphics/units/jian_swordsman_transformed/icon.png` | Game icon | 51663 | `34a3a73e920e77e96c0855f2136ba1e55b974763` |
| `graphics/units/jian_swordsman_transformed/icon_transparent.png` | Transparent icon | 56297 | `ee9e5795b24ace9d99282b765e143a2f9d4225b2` |
| `graphics/units/jian_swordsman_transformed/jian_swordsman_transformed_attack_dir06_dat4x.gif` | Attack animation | 1166885 | `8bd8e1e901345e43d8ffac7b432472ceefbdf75b` |
| `graphics/units/jian_swordsman_transformed/jian_swordsman_transformed_idle_dir06.png` | Native idle pose | 5181 | `86891520626db3a1a6c5247103c962794d5ab699` |
| `graphics/units/jian_swordsman_transformed/jian_swordsman_transformed_idle_dir06_dat4x.png` | DAT idle pose | 195366 | `ad392d0b1a46489185af6a9e221ba01f1615b6d0` |
| `graphics/units/jian_swordsman_transformed/jian_swordsman_transformed_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 195154 | `85c2ac86abb3af958da0deab06e3adb97ac76eee` |
| `graphics/units/jian_swordsman_transformed/jian_swordsman_transformed_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 192582 | `e0eb95e88ec7c234cd25ac3b9bb99a363df654bf` |
| `graphics/units/kamayuk/icon.png` | Game icon | 66243 | `3a310cab2b50bd395b6396e56bd23340d14ad29d` |
| `graphics/units/kamayuk/icon_transparent.png` | Transparent icon | 70954 | `68600b5c08085d06400e0d4f6cff8f67af6b8f66` |
| `graphics/units/kamayuk/kamayuk_attack_dir06_dat4x.gif` | Attack animation | 1615121 | `29e447e2a84b22a82e31d822d2315c37d31abf40` |
| `graphics/units/kamayuk/kamayuk_idle_dir06.png` | Native idle pose | 4424 | `c74724f93a775f4cfc53fb1631f8b7b0913d3720` |
| `graphics/units/kamayuk/kamayuk_idle_dir06_dat4x.png` | DAT idle pose | 222067 | `b9cc29611115129b215b8937a0ad320e81435c60` |
| `graphics/units/kamayuk/kamayuk_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 225499 | `7c6d881d17a5bdf94ce6cb955a1fcd277e1c4fd2` |
| `graphics/units/kamayuk/kamayuk_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 190198 | `a50d9d1903d22c0c43b6f2a9a94de07d7b4d49c9` |
| `graphics/units/karambit_warrior/icon.png` | Game icon | 73310 | `6e47a2af3542fdf46d762067d293bab389da74fc` |
| `graphics/units/karambit_warrior/icon_transparent.png` | Transparent icon | 76724 | `fcdedc3d25e6552dd50055d6c1ad80ed833366f1` |
| `graphics/units/karambit_warrior/karambit_warrior_attack_dir06_dat4x.gif` | Attack animation | 621907 | `e6a257a451ab56f39e81d155de205e869b7aa5f0` |
| `graphics/units/karambit_warrior/karambit_warrior_idle_dir06.png` | Native idle pose | 4607 | `cc8eadf83dc40a2e1be6b1a22e1e739b4887f4c7` |
| `graphics/units/karambit_warrior/karambit_warrior_idle_dir06_dat4x.png` | DAT idle pose | 194705 | `96585c2c2a5f2de6b5b2562c53461444867ef152` |
| `graphics/units/karambit_warrior/karambit_warrior_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 195109 | `b836ec5f1f9b5f7e2382517ed75998e57b96dad6` |
| `graphics/units/karambit_warrior/karambit_warrior_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 193662 | `735e6a81140b8bf1e0276a8c5bbac264bbd5a0b4` |
| `graphics/units/keshik/icon.png` | Game icon | 99291 | `6071700dad6f451b667608c4d45acbd26c6696ee` |
| `graphics/units/keshik/icon_transparent.png` | Transparent icon | 102073 | `84712b92ba38128750b9859ed8b165545c4ace02` |
| `graphics/units/keshik/keshik_attack_dir06_dat4x.gif` | Attack animation | 2715690 | `b7a5848bb309f3ca6f1762536644fc03790f4a6b` |
| `graphics/units/keshik/keshik_idle_dir06.png` | Native idle pose | 15501 | `6224cd84c5c836ef0427a1969110e3cf14fd15e2` |
| `graphics/units/keshik/keshik_idle_dir06_dat4x.png` | DAT idle pose | 499236 | `fe934b500f45a39982454d2a571db9ac602bdb23` |
| `graphics/units/keshik/keshik_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 502156 | `d6e5c71f885401ddb22008b74eef16d54c6e9c1f` |
| `graphics/units/keshik/keshik_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 498921 | `35c95c48f3e432a28ba28acaff6e8d411fa29146` |
| `graphics/units/kipchak/icon.png` | Game icon | 95135 | `47131670ddb5db385a4a0d7a4185e16f61282ff6` |
| `graphics/units/kipchak/icon_transparent.png` | Transparent icon | 99348 | `ba9328ae9890bfe7280de8e71d82ff805aeb8087` |
| `graphics/units/kipchak/kipchak_attack_dir06_dat4x.gif` | Attack animation | 4261291 | `c420290a407a1d6766192f63aa3ea8392f14c474` |
| `graphics/units/kipchak/kipchak_idle_dir06.png` | Native idle pose | 12668 | `66a626f3c56319f00d66cd7750587c987c00eb7d` |
| `graphics/units/kipchak/kipchak_idle_dir06_dat4x.png` | DAT idle pose | 375256 | `03e5552a7bf8870521d4a3b905588732ce000dd4` |
| `graphics/units/kipchak/kipchak_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 374241 | `7c463db75fa033a9527ef361c8dd860b9f94c782` |
| `graphics/units/kipchak/kipchak_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 380708 | `d5e58d2f602eac8955d4e84140c17d06ab3e31a3` |
| `graphics/units/knight/icon.png` | Game icon | 102914 | `4923508ce81096c8730847d9585dd4af713cd357` |
| `graphics/units/knight/icon_transparent.png` | Transparent icon | 105625 | `1add0ba24d92c39865fdab40daccf00a77afa200` |
| `graphics/units/knight/knight_attack_dir06_dat4x.gif` | Attack animation | 1933622 | `238f90818bc4fcca0b22607e01b00f128fcf0dae` |
| `graphics/units/knight/knight_idle_dir06.png` | Native idle pose | 11185 | `b3b251990417d24db50ac54523bbcf1e85528ccb` |
| `graphics/units/knight/knight_idle_dir06_dat4x.png` | DAT idle pose | 369728 | `993a67adc8b71698b6c3f0840a04d2b353081743` |
| `graphics/units/knight/knight_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 369533 | `68ffa0c78c1b88ee9fd72529bb6324739b0ccbf4` |
| `graphics/units/knight/knight_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 363351 | `63f98f9069c2c64289e4a0bdd9a67a7cb5228745` |
| `graphics/units/kona/icon.png` | Game icon | 59144 | `de56c2088097e947cc9efe4cc7ac4eddf56cc708` |
| `graphics/units/kona/icon_transparent.png` | Transparent icon | 62482 | `0e4b0f466bfe02f02883e05905a13d6e01e2cbf4` |
| `graphics/units/kona/kona_attack_dir06_dat4x.gif` | Attack animation | 3046761 | `7e5253f850e25a11ade5649e0a9303d1179b526c` |
| `graphics/units/kona/kona_flux_hd.png` | HD unit illustration | 765919 | `f26022224b8ac0290e04ef8f6c932a7fb30b2125` |
| `graphics/units/kona/kona_idle_dir06.png` | Native idle pose | 11639 | `c6b69a7415ebaebea3eab866aef40bf6ac17125d` |
| `graphics/units/kona/kona_idle_dir06_dat4x.png` | DAT idle pose | 398846 | `c61a76b46b0d695a1d2d2f9c3ba3f55d5c60a162` |
| `graphics/units/kona/kona_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 399115 | `d05aedd3e4924e0bb3784d7045f1806859524f6e` |
| `graphics/units/kona/kona_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 376199 | `2d038daba568e8042b11b8a0a9c6b6c93b81a8a1` |
| `graphics/units/konnik/icon.png` | Game icon | 101237 | `77bfa0cacdbf93c67bb017d72f74ec21cf061800` |
| `graphics/units/konnik/icon_transparent.png` | Transparent icon | 104592 | `fea91a31da70553ae053f9b0ac6823841e3b23be` |
| `graphics/units/konnik/konnik_attack_dir06_dat4x.gif` | Attack animation | 1930454 | `150bfdd1c3a14583fef71019615101d00e143131` |
| `graphics/units/konnik/konnik_idle_dir06.png` | Native idle pose | 11494 | `a30c3e499c0d7ba611782290442fea3fa04bfd10` |
| `graphics/units/konnik/konnik_idle_dir06_dat4x.png` | DAT idle pose | 372573 | `9eded539153a97fc91f0a96b2412f47eacdbf828` |
| `graphics/units/konnik/konnik_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 372016 | `2afc6bbdc08d1fa7d79a69b3c85a1a07555813a9` |
| `graphics/units/konnik/konnik_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 364965 | `dc0bfe8553559d3b0ca922535237c9454d1a93fd` |
| `graphics/units/konnik_dismounted/icon.png` | Game icon | 124806 | `87c2c29d56e3271c0085b40575409c25978cdff8` |
| `graphics/units/konnik_dismounted/icon_transparent.png` | Transparent icon | 125579 | `05d0eb12cbef84a5bcec3c3af40cd22616e88fbf` |
| `graphics/units/konnik_dismounted/konnik_dismounted_attack_dir06_dat4x.gif` | Attack animation | 1075272 | `0cce72353fd4358bf76744912a0d2ae96461c791` |
| `graphics/units/konnik_dismounted/konnik_dismounted_idle_dir06.png` | Native idle pose | 3915 | `f44ed6f317007f94ccc7c301c74dca671ce463ae` |
| `graphics/units/konnik_dismounted/konnik_dismounted_idle_dir06_dat4x.png` | DAT idle pose | 153721 | `1eafdcfd663fdf190952e8d2a6a810caa2c8d142` |
| `graphics/units/konnik_dismounted/konnik_dismounted_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 153851 | `a27f3ce18c1c7554cad75fd4ff3b268c7180c050` |
| `graphics/units/konnik_dismounted/konnik_dismounted_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 147995 | `ef4e5fdd3b9a8ba5c33eb564c755cf4ed76724c9` |
| `graphics/units/legionary/icon.png` | Game icon | 92731 | `aaf01bdcaef8b0cd5dc6968974f475a3de70cb7a` |
| `graphics/units/legionary/icon_transparent.png` | Transparent icon | 95740 | `b8235f3773eb1b8de23047328a7626d207bf8251` |
| `graphics/units/legionary/legionary_attack_dir06_dat4x.gif` | Attack animation | 1004517 | `c4329f82ea74634c97c75ed6a7d51c7b1c7354ec` |
| `graphics/units/legionary/legionary_idle_dir06.png` | Native idle pose | 4728 | `cacfd5641fb20bd55610c84565cf0891f26d6843` |
| `graphics/units/legionary/legionary_idle_dir06_dat4x.png` | DAT idle pose | 158661 | `fe2b82db38d8b3771668026719eddd97f1755443` |
| `graphics/units/legionary/legionary_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 161219 | `af5d28479e0e882f770ffc37b15bfd5bfdbfbb83` |
| `graphics/units/legionary/legionary_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 155173 | `493a849b5e19d67022875ae81cc2a4dadde6f95d` |
| `graphics/units/leitis/icon.png` | Game icon | 87349 | `c45d66d80e614159184631baf28e08831989fd9c` |
| `graphics/units/leitis/icon_transparent.png` | Transparent icon | 89634 | `010e9bc041c09c20f5505d94af8024da234b6a6d` |
| `graphics/units/leitis/leitis_attack_dir06_dat4x.gif` | Attack animation | 4284651 | `b87c8950f37f0e2b725daf00e7bd42c18542a13e` |
| `graphics/units/leitis/leitis_idle_dir06.png` | Native idle pose | 12342 | `60acb0113dc92ff4cc374018e7760e1b98810922` |
| `graphics/units/leitis/leitis_idle_dir06_dat4x.png` | DAT idle pose | 403439 | `7039733e6f8d7f265a52f3c68816794b3e96c251` |
| `graphics/units/leitis/leitis_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 402149 | `6f0e85131fc91be7ea20b242c8ae20402780f484` |
| `graphics/units/leitis/leitis_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 387747 | `1408f8e21f8e95f0da01a077bf3104490c7385cd` |
| `graphics/units/liao_dao/icon.png` | Game icon | 57527 | `114649ec42065a6dffc5d776970cce28ea52d6f0` |
| `graphics/units/liao_dao/icon_transparent.png` | Transparent icon | 63045 | `27249bae7cee27b077a0d3a737ad71ab95c865e4` |
| `graphics/units/liao_dao/liao_dao_attack_dir06_dat4x.gif` | Attack animation | 1304284 | `7e02a69bf40bbd238adb1605c4c497fb1bd7ce87` |
| `graphics/units/liao_dao/liao_dao_idle_dir06.png` | Native idle pose | 4418 | `3a56953369eb0f66fbb7593a92d999497de00a95` |
| `graphics/units/liao_dao/liao_dao_idle_dir06_dat4x.png` | DAT idle pose | 192491 | `8ab10c5454b4169c9bc38ea6b6e75b67fb0f860a` |
| `graphics/units/liao_dao/liao_dao_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 194385 | `a1fe64ddead941e4cb5e23989d3f343aebe58d81` |
| `graphics/units/liao_dao/liao_dao_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 188043 | `537075e88e9aeb9f32fe01a66378006c934a6593` |
| `graphics/units/light_cavalry/icon.png` | Game icon | 106203 | `388ddf9a375ab944c4c0fb6d1d9072593efe994d` |
| `graphics/units/light_cavalry/icon_transparent.png` | Transparent icon | 108552 | `0322a1dbd285a6ccd806ee680f3d9e37e4fb3277` |
| `graphics/units/light_cavalry/light_cavalry_attack_dir06_dat4x.gif` | Attack animation | 1918342 | `046fbd882a69c1198e89d78d2bfdadcb436faf17` |
| `graphics/units/light_cavalry/light_cavalry_idle_dir06.png` | Native idle pose | 11283 | `695e6d5d8e936fef1e0bd4ff9d77c1929f004e4e` |
| `graphics/units/light_cavalry/light_cavalry_idle_dir06_dat4x.png` | DAT idle pose | 375727 | `48c6e83c5c5a1ed3a4c16a6749ef3f4791f00c82` |
| `graphics/units/light_cavalry/light_cavalry_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 373581 | `bb0ddf1cf0c960919700e49224c67cdd5dcd94dd` |
| `graphics/units/light_cavalry/light_cavalry_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 373212 | `abf155ab9d4e611095da870c4c7ae4de156ef7ac` |
| `graphics/units/long_swordsman/icon.png` | Game icon | 89808 | `40daf0d771f6c47be4b89e0df4aa324a4d671443` |
| `graphics/units/long_swordsman/icon_transparent.png` | Transparent icon | 92572 | `3bc208ddf22912c84d1b6375832bda30d3419f47` |
| `graphics/units/long_swordsman/long_swordsman_attack_dir06_dat4x.gif` | Attack animation | 653670 | `b41c382f65acc2b6c31cb1eb859dd1ebff42c90f` |
| `graphics/units/long_swordsman/long_swordsman_idle_dir06.png` | Native idle pose | 4006 | `6ae2799f1ec27a2af9f1ea391727aab9ef6aa4a6` |
| `graphics/units/long_swordsman/long_swordsman_idle_dir06_dat4x.png` | DAT idle pose | 159186 | `89e514e0f329ddb4e17b0cf258ce938369f5b78c` |
| `graphics/units/long_swordsman/long_swordsman_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 159509 | `7045c6fe66675540d5862c8da38dbbedc51f0ff3` |
| `graphics/units/long_swordsman/long_swordsman_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 153081 | `cc21c836ca9e3a0fa8b9b93f8ec36989bc66bce8` |
| `graphics/units/longboat/icon.png` | Game icon | 110846 | `ba8e502bf2d83fb91bdd2cea5f81e58312a9fa3f` |
| `graphics/units/longboat/icon_transparent.png` | Transparent icon | 113626 | `ef8054b7ce21254e2b76e0bf8e9407e67785df24` |
| `graphics/units/longboat/longboat_idle_dir06.png` | Native idle pose | 51660 | `50ae3eab98fcca1431683a6093e40e57e9d66c91` |
| `graphics/units/longboat/longboat_idle_dir06_dat4x.png` | DAT idle pose | 1266931 | `deba65ec9e0fdabf1c8fe37a34615578e07131b5` |
| `graphics/units/longboat/longboat_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1317197 | `23e6428446e5be731146bc6b8b7e408ebbb96ce0` |
| `graphics/units/longboat/longboat_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1410978 | `e55cd95e60c4715f1de6c417b4c09454aa0106c4` |
| `graphics/units/longbowman/icon.png` | Game icon | 51728 | `1c3e003cc5db885dd239b123f3be00499083bc29` |
| `graphics/units/longbowman/icon_transparent.png` | Transparent icon | 57056 | `c4b7002cda8678abd3f1b562a66693abe3ff9f35` |
| `graphics/units/longbowman/longbowman_attack_dir06_dat4x.gif` | Attack animation | 789633 | `47d5dc283988e5dd6dfc8e090eef9db52bd807e3` |
| `graphics/units/longbowman/longbowman_idle_dir06.png` | Native idle pose | 5244 | `c204c72fd27d94c0083282425891afe421e4e46d` |
| `graphics/units/longbowman/longbowman_idle_dir06_dat4x.png` | DAT idle pose | 202652 | `af385100da0fa4b0f1c175e49b2e19f0586275ae` |
| `graphics/units/longbowman/longbowman_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 203176 | `bca18166946d8a4f24f9a3dfa5361d735b140808` |
| `graphics/units/longbowman/longbowman_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 200725 | `c8f1298be5acefe5707b2e762af6be7633a60e34` |
| `graphics/units/lou_chuan/icon.png` | Game icon | 97305 | `f8f500d1c1b1c00ab264744476a4e6e7bc32f947` |
| `graphics/units/lou_chuan/icon_transparent.png` | Transparent icon | 102314 | `5b5519a44b9ab4deb61b6dcfa9b3778d04b1d7bd` |
| `graphics/units/lou_chuan/lou_chuan_idle_dir06.png` | Native idle pose | 121165 | `a3a9c8b0023a4ddf6aa3bfb23d817d8ccdfa2711` |
| `graphics/units/lou_chuan/lou_chuan_idle_dir06_dat4x.png` | DAT idle pose | 3074618 | `9802152deb1653558ed316a6d6ff2ae8fe8c69b9` |
| `graphics/units/lou_chuan/lou_chuan_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 3095249 | `ae09dcf7afee7c26fc874ce7805c8be19a8b688e` |
| `graphics/units/lou_chuan/lou_chuan_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 3442707 | `8525c9a0f093a4dab0d070ed858588258393748a` |
| `graphics/units/magyar_huszar/icon.png` | Game icon | 115423 | `a3af27f60be75843b309f954f5516dc68123d07f` |
| `graphics/units/magyar_huszar/icon_transparent.png` | Transparent icon | 122349 | `6e20af778001e123f086d564acb88a9c4cbe0481` |
| `graphics/units/magyar_huszar/magyar_huszar_attack_dir06_dat4x.gif` | Attack animation | 5627072 | `8b3b924cf619e34bf512151f8f1acdd98e4da488` |
| `graphics/units/magyar_huszar/magyar_huszar_idle_dir06.png` | Native idle pose | 16473 | `70fa53e28264ea90d363878f99d38ac9a2a48d83` |
| `graphics/units/magyar_huszar/magyar_huszar_idle_dir06_dat4x.png` | DAT idle pose | 644127 | `2ed129603d37c10a44b6b6c4a49805ba746a69ee` |
| `graphics/units/magyar_huszar/magyar_huszar_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 643489 | `eee23482fac9e3d0dd89870eb5dfb0ede8555991` |
| `graphics/units/magyar_huszar/magyar_huszar_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 610106 | `c0d63a2d4048d2b3cf47bd6391e9628fe4d85091` |
| `graphics/units/mameluke/icon.png` | Game icon | 97435 | `f6a5986fc53915d653849b600c06b55d70f1169f` |
| `graphics/units/mameluke/icon_transparent.png` | Transparent icon | 101670 | `be6550583ca61ae8c2b35a2245daffc7b132c211` |
| `graphics/units/mameluke/mameluke_attack_dir06_dat4x.gif` | Attack animation | 5376682 | `e4247d18aec072917e0cd10bab63d818f273695e` |
| `graphics/units/mameluke/mameluke_idle_dir06.png` | Native idle pose | 15947 | `9cc7ee395c1f9a3cd10b9610dc20f3dace5648ee` |
| `graphics/units/mameluke/mameluke_idle_dir06_dat4x.png` | DAT idle pose | 467365 | `db10208b39f5b9aedeb64e8643da2f624e54557c` |
| `graphics/units/mameluke/mameluke_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 467049 | `2f8a9df204660a75ab2161d5c388ca5449d86588` |
| `graphics/units/mameluke/mameluke_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 477677 | `0d7180d5b36c1b1b642935b2059c0c315cbdc77f` |
| `graphics/units/man_at_arms/icon.png` | Game icon | 81839 | `abaa26ab0cb63a4d39f533290269315d25ded0d0` |
| `graphics/units/man_at_arms/icon_transparent.png` | Transparent icon | 85238 | `691b779de5f9365b4cd5a11b3f475ae7f5dc9759` |
| `graphics/units/man_at_arms/man_at_arms_attack_dir06_dat4x.gif` | Attack animation | 724648 | `282bcdb33cef878df7539cac00fd796d6a0a4894` |
| `graphics/units/man_at_arms/man_at_arms_idle_dir06.png` | Native idle pose | 4002 | `f169b340f41faf169306f6195dc7eb3ceebd1316` |
| `graphics/units/man_at_arms/man_at_arms_idle_dir06_dat4x.png` | DAT idle pose | 148278 | `38468918b7ba7c595b37071ea7252caef489e9ec` |
| `graphics/units/man_at_arms/man_at_arms_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 149937 | `3366a30888a8ed1c9649416db0ec6a48e4a2ac82` |
| `graphics/units/man_at_arms/man_at_arms_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 148311 | `ae52a2358abcd338630c0201ae69f8fe957b3341` |
| `graphics/units/mangonel/icon.png` | Game icon | 128240 | `2561550312073397c3c79bc0db2a3e58b87fb767` |
| `graphics/units/mangonel/icon_transparent.png` | Transparent icon | 133402 | `d2a9729ea17fee16ae856a17ad61f523f2b6930e` |
| `graphics/units/mangonel/mangonel_attack_dir06_dat4x.gif` | Attack animation | 10627861 | `ab115fc11c4b38b1fe496d723d61aa879d257a31` |
| `graphics/units/mangonel/mangonel_idle_dir06.png` | Native idle pose | 26544 | `e1ee68adc8095398b107dcc2051b858516ed5d0a` |
| `graphics/units/mangonel/mangonel_idle_dir06_dat4x.png` | DAT idle pose | 716686 | `d9e9d993ee11580a3b1fe9f876221b797ea14553` |
| `graphics/units/mangonel/mangonel_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 716156 | `0d40f697e290ea5a8dd4e2d36151fefb3e18d8a4` |
| `graphics/units/mangonel/mangonel_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 763801 | `ab8ef61ba0107c42487cb1c29b674ca2c8a2e8ca` |
| `graphics/units/mangudai/icon.png` | Game icon | 99469 | `51df588bd92bc1694781495c9e3ebcac8de831c3` |
| `graphics/units/mangudai/icon_transparent.png` | Transparent icon | 102435 | `849a5c59b47f238e83cc633678563ea69d017d13` |
| `graphics/units/mangudai/mangudai_attack_dir06_dat4x.gif` | Attack animation | 3961276 | `28442b15e81bc31cfa52fe4e344c893eb4490f81` |
| `graphics/units/mangudai/mangudai_idle_dir06.png` | Native idle pose | 10405 | `9bea3fa82e5ef7c35074780ad1b11eda8dd599ab` |
| `graphics/units/mangudai/mangudai_idle_dir06_dat4x.png` | DAT idle pose | 328346 | `6e4c147190c4ab9c1533fa058229388e52a9d649` |
| `graphics/units/mangudai/mangudai_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 328840 | `1a909cfec51ece68fb7f2c3768fc765f1ec96289` |
| `graphics/units/mangudai/mangudai_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 324860 | `c3b70c5659157043a1c8a02305773b13195bee05` |
| `graphics/units/militia/icon.png` | Game icon | 70375 | `071997877b75f1125f019f96f23939eee0b8f9e5` |
| `graphics/units/militia/icon_transparent.png` | Transparent icon | 73865 | `cf5c28c9c3cc0e76e9c18fa7534bf1b881699982` |
| `graphics/units/militia/militia_attack_dir06_dat4x.gif` | Attack animation | 646158 | `ced0cdedfecc97ac3cb2bf82e7b2c5f822872e98` |
| `graphics/units/militia/militia_idle_dir06.png` | Native idle pose | 4000 | `792d6a20f7a81a047a24dc295ace9e0c68d0f8d5` |
| `graphics/units/militia/militia_idle_dir06_dat4x.png` | DAT idle pose | 138777 | `24ddf37ec206403d5ddaa4f6288c5f6464401d73` |
| `graphics/units/militia/militia_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 139986 | `9bf5acd4cebc8fe85c247fb99b615199dde7bcd8` |
| `graphics/units/militia/militia_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 142071 | `05c61b693b8bc955c58a4662927146e2bddbfc74` |
| `graphics/units/monaspa/icon.png` | Game icon | 72237 | `47359fdc2d56deb045bf24122932615f295941a3` |
| `graphics/units/monaspa/icon_transparent.png` | Transparent icon | 75859 | `f21519aac91da3a21578465abd37d979bc4f2732` |
| `graphics/units/monaspa/monaspa_attack_dir06_dat4x.gif` | Attack animation | 2386533 | `fcc33a28f6d85d5e2625ab727f6913b39a423fc3` |
| `graphics/units/monaspa/monaspa_idle_dir06.png` | Native idle pose | 13643 | `5254663b51c4af861b5bbcfcb32428404436e917` |
| `graphics/units/monaspa/monaspa_idle_dir06_dat4x.png` | DAT idle pose | 442102 | `2dae1d882c5d405c9b94e162cf70a66203112e56` |
| `graphics/units/monaspa/monaspa_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 437671 | `7439b0c839534debdd4426dbe1920cf6e8253ffb` |
| `graphics/units/monaspa/monaspa_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 440057 | `8c57c6d7ce44c82377cff306d9379d6d55610ca8` |
| `graphics/units/mounted_trebuchet/icon.png` | Game icon | 71151 | `26e3b4ac68ff42fe8457834ce63b3f21e49e2663` |
| `graphics/units/mounted_trebuchet/icon_transparent.png` | Transparent icon | 77025 | `51f9b946b875593a7c3f426b58654f739320d652` |
| `graphics/units/mounted_trebuchet/mounted_trebuchet_attack_dir06_dat4x.gif` | Attack animation | 10666367 | `2aed45d4678e2f17316bf866ffc518b759ac56d8` |
| `graphics/units/mounted_trebuchet/mounted_trebuchet_idle_dir06.png` | Native idle pose | 26806 | `b179075658bcd50ba6d78dcabd047275955de348` |
| `graphics/units/mounted_trebuchet/mounted_trebuchet_idle_dir06_dat4x.png` | DAT idle pose | 696491 | `fc51f0d52023a0a7b3ce187b903db3c486b79629` |
| `graphics/units/mounted_trebuchet/mounted_trebuchet_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 695509 | `d51018434b3fa398322e382699b7ca98de53ec5c` |
| `graphics/units/mounted_trebuchet/mounted_trebuchet_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 756103 | `69fc0e85e3efd07a99eec3a597273ba9da9780f4` |
| `graphics/units/obuch/icon.png` | Game icon | 58358 | `78471a8327ecc15668f82ba2f0c9d16fa0a99b9c` |
| `graphics/units/obuch/icon_transparent.png` | Transparent icon | 63728 | `1c06a34c3d3068b2fc2573dd39cb364713b39f54` |
| `graphics/units/obuch/obuch_attack_dir06_dat4x.gif` | Attack animation | 700560 | `dbd5b6088cbbbe6794352ebe1b0e8042713a1507` |
| `graphics/units/obuch/obuch_idle_dir06.png` | Native idle pose | 4739 | `550afcb3037cc207f3a7d8d0b571ce0006add750` |
| `graphics/units/obuch/obuch_idle_dir06_dat4x.png` | DAT idle pose | 199554 | `a10cfccf37fdfa5f15ed61c546175b48bee733b1` |
| `graphics/units/obuch/obuch_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 200789 | `e9183998f033335d7dbaee9893f6400cfb00ea77` |
| `graphics/units/obuch/obuch_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 199831 | `8117f228d5d6736f3665e938a820c0437c3ce47d` |
| `graphics/units/onager/icon.png` | Game icon | 127908 | `a8e57c19b695c0e698f122ea1169fbfcd7763935` |
| `graphics/units/onager/icon_transparent.png` | Transparent icon | 131471 | `407a04a781de7d0aa048320950943cec52d05e71` |
| `graphics/units/onager/onager_attack_dir06_dat4x.gif` | Attack animation | 12577644 | `80ebb8823cd4d1d281a62dbed56e0efc205b8c8b` |
| `graphics/units/onager/onager_idle_dir06.png` | Native idle pose | 30986 | `5936263951af3226f9dabdf480cf36129e8c6dad` |
| `graphics/units/onager/onager_idle_dir06_dat4x.png` | DAT idle pose | 789645 | `80b6f35ffb7ef6da2486467ca41631f72ed0a248` |
| `graphics/units/onager/onager_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 789844 | `93439368659a42d5a17f9f8c468478cf360df43d` |
| `graphics/units/onager/onager_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 850814 | `73752229d2bca8bc81e0c22f0c73253f93d33726` |
| `graphics/units/organ_gun/icon.png` | Game icon | 112248 | `08d6c9fa05fbf98ef6165ac1287f5f16bdde936c` |
| `graphics/units/organ_gun/icon_transparent.png` | Transparent icon | 115058 | `9850c048194bde005fac9732e9839dc5115fae53` |
| `graphics/units/organ_gun/organ_gun_attack_dir06_dat4x.gif` | Attack animation | 3215196 | `1fd8f314e2943f6db3566bf1646027d2028a462f` |
| `graphics/units/organ_gun/organ_gun_idle_dir06.png` | Native idle pose | 9797 | `d63f9a6c8eea5240cc0279ece57c8fa79220a087` |
| `graphics/units/organ_gun/organ_gun_idle_dir06_dat4x.png` | DAT idle pose | 315814 | `6ba7378859c76a558ca62d93b4e1291f1a7fbc39` |
| `graphics/units/organ_gun/organ_gun_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 316036 | `db4d92fc30165300b1def7dde061e13a3ee43d8d` |
| `graphics/units/organ_gun/organ_gun_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 319266 | `4b5b3483455f9757bdb8e04d0e44087a3f82195b` |
| `graphics/units/paladin/icon.png` | Game icon | 104229 | `29d071de8cecb21c78b30e47d4648e2aaf3b2057` |
| `graphics/units/paladin/icon_transparent.png` | Transparent icon | 107305 | `14bd8d11a276644f4b03cd596c6038314cea88a1` |
| `graphics/units/paladin/paladin_attack_dir06_dat4x.gif` | Attack animation | 2360013 | `ec60af7dbe0e47f9b642f78121306aa13354fc0c` |
| `graphics/units/paladin/paladin_idle_dir06.png` | Native idle pose | 14161 | `ccc0d09bae55e0699ff40cb817c94fa968eb88d4` |
| `graphics/units/paladin/paladin_idle_dir06_dat4x.png` | DAT idle pose | 421729 | `5dcd02141482f5fc992fb633266f894217ee9867` |
| `graphics/units/paladin/paladin_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 419503 | `faa202e403d69ff16676d844e537820623f46b27` |
| `graphics/units/paladin/paladin_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 417498 | `52e44f8597f2ab0bf5e5a68e869d1ed79d23468c` |
| `graphics/units/pikeman/icon.png` | Game icon | 75130 | `c8cd78a7c4e0ddb78a7f1862749a0140d9f7169d` |
| `graphics/units/pikeman/icon_transparent.png` | Transparent icon | 78087 | `255f2ef2efb97c3ff9913117df1a50f704e85291` |
| `graphics/units/pikeman/pikeman_attack_dir06_dat4x.gif` | Attack animation | 720814 | `8c527121e4a30a8ef8c3fc99cf09dabb794068c9` |
| `graphics/units/pikeman/pikeman_idle_dir06.png` | Native idle pose | 4144 | `e8f83de0f641e2123a47ba9c0260c3785bc762ff` |
| `graphics/units/pikeman/pikeman_idle_dir06_dat4x.png` | DAT idle pose | 194130 | `03246ee0bb124e7638a5b3cd58a1164e04a496d5` |
| `graphics/units/pikeman/pikeman_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 193064 | `15018a06761a9eab8f4774d70a10db1ac67a4f45` |
| `graphics/units/pikeman/pikeman_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 179610 | `b181e7591751ff3fc4594efaee89827460a13e2c` |
| `graphics/units/plumed_archer/icon.png` | Game icon | 44060 | `ac27d5a953927d34ca338f03d4fa269805f05a1d` |
| `graphics/units/plumed_archer/icon_transparent.png` | Transparent icon | 47750 | `db1c3ee812b28cdad9033bc123afcbd8a6f55d97` |
| `graphics/units/plumed_archer/plumed_archer_attack_dir06_dat4x.gif` | Attack animation | 1133458 | `8428a2557818c19964a323ad3715f12430b639da` |
| `graphics/units/plumed_archer/plumed_archer_idle_dir06.png` | Native idle pose | 4545 | `b53a65c1008eb72f952a2b5139a92aff4f2bc662` |
| `graphics/units/plumed_archer/plumed_archer_idle_dir06_dat4x.png` | DAT idle pose | 184686 | `95f8889417d7c7648421fe508004e8f12952e15c` |
| `graphics/units/plumed_archer/plumed_archer_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 185428 | `7f267d2b09718a38adfde4a9f794447fa3a4eaf8` |
| `graphics/units/plumed_archer/plumed_archer_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 179019 | `214307169b06a8a467b620fdde94b4fe3ad7cf1a` |
| `graphics/units/ratha_melee/icon.png` | Game icon | 100710 | `3cd963714d1ace9256d4930a4c932072530cbd54` |
| `graphics/units/ratha_melee/icon_transparent.png` | Transparent icon | 103763 | `96667c8ad91d58f41e9edee9c73c0687331a7003` |
| `graphics/units/ratha_melee/ratha_melee_attack_dir06_dat4x.gif` | Attack animation | 5906085 | `741b842285418b6bc145a844a9f32f19f1c0504c` |
| `graphics/units/ratha_melee/ratha_melee_idle_dir06.png` | Native idle pose | 32313 | `838bc3f87eb6fbdf120b468370bcdd1c3acc3f93` |
| `graphics/units/ratha_melee/ratha_melee_idle_dir06_dat4x.png` | DAT idle pose | 919063 | `6a57faf61ecb20ca7d4c3216d1384af44e6dcaac` |
| `graphics/units/ratha_melee/ratha_melee_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 915536 | `f20383554364490093458009717a00bf9f39cb4b` |
| `graphics/units/ratha_melee/ratha_melee_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 935186 | `89376980947ec4d2228f6d94d938085042c6be6b` |
| `graphics/units/ratha_ranged/icon.png` | Game icon | 99518 | `38e17ef73d546e3514f9aa5f11181b18f2299398` |
| `graphics/units/ratha_ranged/icon_transparent.png` | Transparent icon | 103625 | `e5e02949edec7d28686df2ca7ed9514de3c2a6cb` |
| `graphics/units/ratha_ranged/ratha_ranged_attack_dir06_dat4x.gif` | Attack animation | 6106000 | `7d25293c22ff9411790889321287401c7028c5c1` |
| `graphics/units/ratha_ranged/ratha_ranged_idle_dir06.png` | Native idle pose | 33161 | `143b478b900bf736e43e993aae33a7228d028b59` |
| `graphics/units/ratha_ranged/ratha_ranged_idle_dir06_dat4x.png` | DAT idle pose | 937979 | `c963307cc4d31871c81c88cd758de4bc7fea3795` |
| `graphics/units/ratha_ranged/ratha_ranged_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 939476 | `5cc773c26f14d15b5151f57efbbfcf12a568e17c` |
| `graphics/units/ratha_ranged/ratha_ranged_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 963787 | `3e3eefbb3455c6f8321ded70116e27f6b4a09af5` |
| `graphics/units/rattan_archer/icon.png` | Game icon | 68142 | `139d7dc6dc445ffe2221a96ea5e9147e2e132403` |
| `graphics/units/rattan_archer/icon_transparent.png` | Transparent icon | 71631 | `0b24991b59fe2996f7d70e59c242cbaec04686db` |
| `graphics/units/rattan_archer/rattan_archer_attack_dir06_dat4x.gif` | Attack animation | 1167040 | `8aa48cd0527dbce8607de2e90d1bb2a3d68efc69` |
| `graphics/units/rattan_archer/rattan_archer_idle_dir06.png` | Native idle pose | 4720 | `ab27f907a2a308cd75165f331e2ccf0f3cb17087` |
| `graphics/units/rattan_archer/rattan_archer_idle_dir06_dat4x.png` | DAT idle pose | 164960 | `24f997ddb7c9d2ffe09058c2d399cbc06c7f1a5e` |
| `graphics/units/rattan_archer/rattan_archer_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 165902 | `a78da1471439680075d0eed46fd1ad3da1642049` |
| `graphics/units/rattan_archer/rattan_archer_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 165239 | `89c412380fda7006e8b4a32540886d2b6b9825b7` |
| `graphics/units/rocket_cart/icon.png` | Game icon | 46090 | `bfeeb53da3e251744cce92b5c3c4fed79bdae205` |
| `graphics/units/rocket_cart/icon_transparent.png` | Transparent icon | 49137 | `d499d161efbef6dbd6c200e19ffeea87787ade0f` |
| `graphics/units/rocket_cart/rocket_cart_attack_dir06_dat4x.gif` | Attack animation | 8258089 | `a08871e1615c0abbed9f6bad7953b0b8cf79d2ef` |
| `graphics/units/rocket_cart/rocket_cart_idle_dir06.png` | Native idle pose | 19658 | `e4ea5775e91eee73b6e1f9bba6fbcf2527d84e94` |
| `graphics/units/rocket_cart/rocket_cart_idle_dir06_dat4x.png` | DAT idle pose | 567205 | `921997094d284de70a480993f11d53b092c0ea9f` |
| `graphics/units/rocket_cart/rocket_cart_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 568853 | `19c40e7a0e993c4dcf7d2c36897341bc379777d0` |
| `graphics/units/rocket_cart/rocket_cart_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 585912 | `d14005cbc0aa5042931b15b528d9c4194c86b464` |
| `graphics/units/samurai/icon.png` | Game icon | 79594 | `2fb230b58fc98ae03cbbf3388495a8a11a1fd0f4` |
| `graphics/units/samurai/icon_transparent.png` | Transparent icon | 82285 | `9371d63afe095aaa511004603d84be15297fddcd` |
| `graphics/units/samurai/samurai_attack_dir06_dat4x.gif` | Attack animation | 1064746 | `d606669acb8a8a31b6f8a33964248c75ee01dfa1` |
| `graphics/units/samurai/samurai_idle_dir06.png` | Native idle pose | 4512 | `ce4ef3bf77b198dd02cf4ef5747030003d2fd54a` |
| `graphics/units/samurai/samurai_idle_dir06_dat4x.png` | DAT idle pose | 147522 | `b9f430b106a6a3d964df03ecb4ac5cdd30ef7865` |
| `graphics/units/samurai/samurai_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 147839 | `6350e483b1f67ab5bed27f8bc76da11d00ed6b6a` |
| `graphics/units/samurai/samurai_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 151742 | `79284a310030830926d23e75dab59ca0325b151b` |
| `graphics/units/savar/icon.png` | Game icon | 86554 | `8d089a38debde4e2d88325683b36f87d237a2819` |
| `graphics/units/savar/icon_transparent.png` | Transparent icon | 91476 | `faf356915ec989460ddab5003e9b86077c546883` |
| `graphics/units/savar/savar_attack_dir06_dat4x.gif` | Attack animation | 2821139 | `818d28d7511f8441e365d6877401898e6b45a431` |
| `graphics/units/savar/savar_idle_dir06.png` | Native idle pose | 15721 | `85f713260058781a1da8f872ea1e2c9d1aad8222` |
| `graphics/units/savar/savar_idle_dir06_dat4x.png` | DAT idle pose | 425370 | `5ac8e6851e464c900bc2c07f4ac58d6c4185a015` |
| `graphics/units/savar/savar_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 426490 | `d321e22e709fd2e46d8cec93507b619bcf66f368` |
| `graphics/units/savar/savar_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 427823 | `f8ad1b5d4240bc1dcab5343410db94d948946c5c` |
| `graphics/units/scorpion/icon.png` | Game icon | 63105 | `e5ec336acc1ba03f328001623fa3e97d15351192` |
| `graphics/units/scorpion/icon_transparent.png` | Transparent icon | 67022 | `9b8c5304983bc01b9a5e1702306574df2eb2bc96` |
| `graphics/units/scorpion/scorpion_attack_dir06_dat4x.gif` | Attack animation | 4060804 | `910b83f5664109732b3afe3ee5ba15841ce6a2e6` |
| `graphics/units/scorpion/scorpion_idle_dir06.png` | Native idle pose | 10858 | `ee4035175b1966eef1d5f2837a40ba8e46a6d035` |
| `graphics/units/scorpion/scorpion_idle_dir06_dat4x.png` | DAT idle pose | 343256 | `e2fb07c18605e14bfcd78ec8e143928a5b6231c8` |
| `graphics/units/scorpion/scorpion_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 344474 | `e7e614a450230843485b88c023c0c41cbb28ac0c` |
| `graphics/units/scorpion/scorpion_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 354845 | `afc13cdd3e0dabaeba02ab17104afec1c73c7d90` |
| `graphics/units/scout_cavalry/icon.png` | Game icon | 99067 | `5ff4e6bfafb4518d5ec78737bed9d2094c587977` |
| `graphics/units/scout_cavalry/icon_transparent.png` | Transparent icon | 101697 | `9334cec3b983090e75ab36f7b73a05a5537b9243` |
| `graphics/units/scout_cavalry/scout_cavalry_attack_dir06_dat4x.gif` | Attack animation | 1726430 | `b900604a0550a1fd62003b90588e699e11ce21fd` |
| `graphics/units/scout_cavalry/scout_cavalry_idle_dir06.png` | Native idle pose | 10380 | `b39c1438993293b64386c0995c2a66e35abc1e35` |
| `graphics/units/scout_cavalry/scout_cavalry_idle_dir06_dat4x.png` | DAT idle pose | 362864 | `e4d655864e11bde90b09332d052eaee72800d36f` |
| `graphics/units/scout_cavalry/scout_cavalry_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 362724 | `1fe7d63efb2b617d6f1bf5dcd724303dc9b71536` |
| `graphics/units/scout_cavalry/scout_cavalry_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 359174 | `9050e2d94987eed7e49419b62b7cb984caec7e50` |
| `graphics/units/serjeant/icon.png` | Game icon | 78367 | `a83d5defe3852207ae7d59bc93b09d80a7f5ff49` |
| `graphics/units/serjeant/icon_transparent.png` | Transparent icon | 80898 | `a506b6b2c566fd93e21e83f3570294e7ff73cb35` |
| `graphics/units/serjeant/serjeant_attack_dir06_dat4x.gif` | Attack animation | 831077 | `f466bd4c0b80c07de449dd10c6719c4c55e20767` |
| `graphics/units/serjeant/serjeant_idle_dir06.png` | Native idle pose | 4868 | `f9fe03ede977c54d2828c937cb074b2dd4cfd328` |
| `graphics/units/serjeant/serjeant_idle_dir06_dat4x.png` | DAT idle pose | 163627 | `4816f6a0e2ac397c1c93c182e43f59f0928d7271` |
| `graphics/units/serjeant/serjeant_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 165776 | `bbb00683f622cd1cb2f07a13998b7cdf2d4d4f20` |
| `graphics/units/serjeant/serjeant_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 164421 | `c06c288747229c401f8c00641e459d0aedb34773` |
| `graphics/units/shotel_warrior/icon.png` | Game icon | 60670 | `1298773fae16f28cb88e48439fe380355ba54a87` |
| `graphics/units/shotel_warrior/icon_transparent.png` | Transparent icon | 64620 | `220b44797ccc7904a39c88418642665b1a0c8b1b` |
| `graphics/units/shotel_warrior/shotel_warrior_attack_dir06_dat4x.gif` | Attack animation | 777963 | `e774d29f53bfe0f6315b5f9705a43ca8c26a2ab1` |
| `graphics/units/shotel_warrior/shotel_warrior_idle_dir06.png` | Native idle pose | 4776 | `876265aae4e537ad624eff58512a8962d5dabf67` |
| `graphics/units/shotel_warrior/shotel_warrior_idle_dir06_dat4x.png` | DAT idle pose | 188178 | `eb880d31a8c92f28ae46e179c2aea62e2b5fc760` |
| `graphics/units/shotel_warrior/shotel_warrior_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 191290 | `72b8294db744d47f875f7323f20867ce186feaa6` |
| `graphics/units/shotel_warrior/shotel_warrior_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 185958 | `3cca3dde76343a700ec2f8601b6e42c8dc0cff3c` |
| `graphics/units/shrivamsha_rider/icon.png` | Game icon | 86593 | `58663578dd4ba5cde67be9896af30825ef58f281` |
| `graphics/units/shrivamsha_rider/icon_transparent.png` | Transparent icon | 88643 | `2dd8fac656817f8311b1e25be8d842861ec46b75` |
| `graphics/units/shrivamsha_rider/shrivamsha_rider_attack_dir06_dat4x.gif` | Attack animation | 1724523 | `2479f5f3aaa1822bd2f7f71e1367fc9d38f6add5` |
| `graphics/units/shrivamsha_rider/shrivamsha_rider_idle_dir06.png` | Native idle pose | 10797 | `82ff8a7ce2e24bea3db32d96332ba97ccb92c9d6` |
| `graphics/units/shrivamsha_rider/shrivamsha_rider_idle_dir06_dat4x.png` | DAT idle pose | 361454 | `ec8dc87df4eae23d42716e3546686cd78f6753c7` |
| `graphics/units/shrivamsha_rider/shrivamsha_rider_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 360645 | `6999c89c4b26c5555c9e079cfb4f4bef123165a2` |
| `graphics/units/shrivamsha_rider/shrivamsha_rider_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 362434 | `097e1451e9bc1e813642c97fef73ccc966e5c957` |
| `graphics/units/siege_elephant/icon.png` | Game icon | 119992 | `2d012c9ea2d8037873985338e3ff8ec83f7e47e2` |
| `graphics/units/siege_elephant/icon_transparent.png` | Transparent icon | 122795 | `1e0e63ca905268d81727116bab1391453218428e` |
| `graphics/units/siege_elephant/siege_elephant_attack_dir06_dat4x.gif` | Attack animation | 13245845 | `c3704e654f59430b0a591f5ec5882846f141d958` |
| `graphics/units/siege_elephant/siege_elephant_idle_dir06.png` | Native idle pose | 38468 | `c511a5db70460494df9a019584d1664302be9da2` |
| `graphics/units/siege_elephant/siege_elephant_idle_dir06_dat4x.png` | DAT idle pose | 930433 | `09fcaaa09737b402122a0a759658ea294bdd928e` |
| `graphics/units/siege_elephant/siege_elephant_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 945507 | `779319903b5f5424e794b880a2152d236904f7be` |
| `graphics/units/siege_elephant/siege_elephant_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 982323 | `7de47fa190de4818473becf9d76fbb31a7034aa9` |
| `graphics/units/siege_onager/icon.png` | Game icon | 128471 | `454d3a4885081f2f40f804d2494c9c35a17a1793` |
| `graphics/units/siege_onager/icon_transparent.png` | Transparent icon | 131805 | `af954acbd4463f4083bccb143f87335a7f721267` |
| `graphics/units/siege_onager/siege_onager_attack_dir06_dat4x.gif` | Attack animation | 12612202 | `0a33bf80be71d61d67457b9de33fd5230f741644` |
| `graphics/units/siege_onager/siege_onager_idle_dir06.png` | Native idle pose | 33516 | `9e3df1858df85c80b9a947f7b3aaf0bc473c6e06` |
| `graphics/units/siege_onager/siege_onager_idle_dir06_dat4x.png` | DAT idle pose | 835266 | `f57522e67da897099105ff1c8303efebf8200c0e` |
| `graphics/units/siege_onager/siege_onager_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 835312 | `9f03c13e4c4b16440faee968b9c94987cd628316` |
| `graphics/units/siege_onager/siege_onager_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 907397 | `984e19154e8d53c49be1c6d66015d2b090ecd335` |
| `graphics/units/siege_ram/icon.png` | Game icon | 136299 | `1302a19143ae2a1f464035c65ae9bbd60c700021` |
| `graphics/units/siege_ram/icon_transparent.png` | Transparent icon | 138755 | `546aab2aed1edf47141e901b904601b8ead7e463` |
| `graphics/units/siege_ram/siege_ram_attack_dir06_dat4x.gif` | Attack animation | 13499050 | `7ec83d477c1763af6aad52cd85f81ffc1495f2a1` |
| `graphics/units/siege_ram/siege_ram_idle_dir06.png` | Native idle pose | 34416 | `a5a749818181e3005114417d785742abae0a25c7` |
| `graphics/units/siege_ram/siege_ram_idle_dir06_dat4x.png` | DAT idle pose | 862134 | `14818a938c1b839beb6b07a6d01dd1f89878d062` |
| `graphics/units/siege_ram/siege_ram_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 863038 | `9df4bcbabcac0d92c7609266d4f0fb8203a260d7` |
| `graphics/units/siege_ram/siege_ram_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 897918 | `04061ff5d23913c0fc380933a7c4f66416669326` |
| `graphics/units/siege_tower/icon.png` | Game icon | 132738 | `b1971db8068bcdeb6e5e014bcff413261b936910` |
| `graphics/units/siege_tower/icon_transparent.png` | Transparent icon | 136126 | `5e1d99fca375333018c6343f2b4c3ea2f889f36a` |
| `graphics/units/siege_tower/siege_tower_attack_dir06_dat4x.gif` | Attack animation | 17230314 | `434edd7b6c98c5b76c065085b9391f25b9b2ec2c` |
| `graphics/units/siege_tower/siege_tower_idle_dir06.png` | Native idle pose | 74799 | `62a0c42fb7670cfdb964a429bd07e0aaba1d95fc` |
| `graphics/units/siege_tower/siege_tower_idle_dir06_dat4x.png` | DAT idle pose | 1793916 | `e9b110dfdc1cb8e22c2f93ea2c419b270ba042e4` |
| `graphics/units/siege_tower/siege_tower_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1805271 | `856bcbcd7fb73cc560a043c1f9da2b9bf42ba0be` |
| `graphics/units/siege_tower/siege_tower_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1961697 | `3e9ddd556cbc465156a152fe4e17e0e7af8382a7` |
| `graphics/units/skirmisher/icon.png` | Game icon | 88088 | `bc66ccb2a86f083862ff3e783dac8ee895ee0b82` |
| `graphics/units/skirmisher/icon_transparent.png` | Transparent icon | 91165 | `d32e4567d50ec957e3cf7c5903b647f90384be10` |
| `graphics/units/skirmisher/skirmisher_attack_dir06_dat4x.gif` | Attack animation | 1009791 | `4be1e0f9ac4bc1f9f77845036b205e98dea2df4a` |
| `graphics/units/skirmisher/skirmisher_idle_dir06.png` | Native idle pose | 4169 | `b471b9af3369b2ecfa18706e7af8c13c7a44331e` |
| `graphics/units/skirmisher/skirmisher_idle_dir06_dat4x.png` | DAT idle pose | 188884 | `5215d4e4ab982f006ecb1e318a277b00fd57394d` |
| `graphics/units/skirmisher/skirmisher_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 188741 | `3f20d6b3b7f5efba221327f03b84d3b1895dc6f4` |
| `graphics/units/skirmisher/skirmisher_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 186034 | `9703be0c28375d80f070d1578e0b9dcb28496dcd` |
| `graphics/units/slinger/icon.png` | Game icon | 63020 | `a95a4291c9faf174483417878f7d0ebdaa29cf5d` |
| `graphics/units/slinger/icon_transparent.png` | Transparent icon | 65290 | `e1e92706bbd4bba64d6a1796e5abf54ce0af09c9` |
| `graphics/units/slinger/slinger_attack_dir06_dat4x.gif` | Attack animation | 764457 | `135b0a4c9714ce72b931f08773a6196e6a17655a` |
| `graphics/units/slinger/slinger_flux_hd.png` | HD unit illustration | 736313 | `6f6c0f146eb8d116b578ca5beca62a71f220c9c2` |
| `graphics/units/slinger/slinger_idle_dir06.png` | Native idle pose | 3681 | `91dc8f7937c10dab569902ad538b4f7822a66289` |
| `graphics/units/slinger/slinger_idle_dir06_dat4x.png` | DAT idle pose | 127090 | `cf61a1f2559c750110a3b75777232e2d33200d66` |
| `graphics/units/slinger/slinger_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 126874 | `6fbb8f0d4b2dfbb5e13bfa6e1a48d2010e61bf84` |
| `graphics/units/slinger/slinger_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 128068 | `5624121f66c9621d8b7a41d5a31b01e6daa654d5` |
| `graphics/units/spearman/icon.png` | Game icon | 79982 | `9148ab0b51c90bfb87836a995675cbe512b913d8` |
| `graphics/units/spearman/icon_transparent.png` | Transparent icon | 82863 | `028aae270373a61c1ddeed9d9fbbeb2e5a381e50` |
| `graphics/units/spearman/spearman_attack_dir06_dat4x.gif` | Attack animation | 641170 | `c1d4d57521647c6568ef2d3361cf1159e2b00e76` |
| `graphics/units/spearman/spearman_idle_dir06.png` | Native idle pose | 3954 | `27101a7987dd8883be011fdef4622103f017ea17` |
| `graphics/units/spearman/spearman_idle_dir06_dat4x.png` | DAT idle pose | 193067 | `3a178aa23f2b7c942f4fc0d83e06f463b36e19ee` |
| `graphics/units/spearman/spearman_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 191353 | `732be0445b609cfa0060127135710406bd155dea` |
| `graphics/units/spearman/spearman_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 180338 | `817611c4675cbea904ebf8a315e713fcf9152a74` |
| `graphics/units/steppe_lancer/icon.png` | Game icon | 136952 | `8433c1923d7df421e4ac4870563d4e2d28782d99` |
| `graphics/units/steppe_lancer/icon_transparent.png` | Transparent icon | 139347 | `a01ddda8a1dd5ab25c04acdf9f4c39c7a06c1b09` |
| `graphics/units/steppe_lancer/steppe_lancer_attack_dir06_dat4x.gif` | Attack animation | 2424352 | `1350588432815266c9ab54d33ea4a13976dde9f2` |
| `graphics/units/steppe_lancer/steppe_lancer_idle_dir06.png` | Native idle pose | 13522 | `2475a6f66c33ae3fc859fcd241d7efbec9914ad9` |
| `graphics/units/steppe_lancer/steppe_lancer_idle_dir06_dat4x.png` | DAT idle pose | 501981 | `0c1b52698f90a0bbcbcea9ab4301537addfc1072` |
| `graphics/units/steppe_lancer/steppe_lancer_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 493324 | `ba00c980f81338f429e3755d0e4546d98b5233bf` |
| `graphics/units/steppe_lancer/steppe_lancer_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 469353 | `d5896c5928affef28bd2e012f92f8f114377eb0e` |
| `graphics/units/tarkan/icon.png` | Game icon | 121646 | `00ae10ba15f6e24f92e8f792bc3cbfbac58c6786` |
| `graphics/units/tarkan/icon_transparent.png` | Transparent icon | 124898 | `39f56a7232bb78d8067baf83cf7a139ef1aba761` |
| `graphics/units/tarkan/tarkan_attack_dir06_dat4x.gif` | Attack animation | 2193644 | `3f5b7cc44abdca76d44fde4ca112b4ac43904277` |
| `graphics/units/tarkan/tarkan_idle_dir06.png` | Native idle pose | 12369 | `461ad119e80a0a4652f2767141a31fe4bd665a19` |
| `graphics/units/tarkan/tarkan_idle_dir06_dat4x.png` | DAT idle pose | 401587 | `ed794890524b68174817b7d33b51c8f8bdb64ec5` |
| `graphics/units/tarkan/tarkan_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 402642 | `7026b02ecce2c8acc2a933549a5d3b0bfa6b19c9` |
| `graphics/units/tarkan/tarkan_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 398448 | `f67a322ccce0cc47be1208dc8351b67ebd7a215a` |
| `graphics/units/temple_guard/icon.png` | Game icon | 62083 | `c6c0f4bcd168e08bb2bbef23396d70822b95bc1c` |
| `graphics/units/temple_guard/icon_transparent.png` | Transparent icon | 65762 | `c87ee611e6f7b8f51152e29decbb0483594c1e42` |
| `graphics/units/temple_guard/temple_guard_attack_dir06_dat4x.gif` | Attack animation | 1226239 | `d500f146fe77401a2c33340f0c0d8cb2e9f65c54` |
| `graphics/units/temple_guard/temple_guard_idle_dir06.png` | Native idle pose | 4713 | `8a46189e5a7c73c134325a5312ae6ca4b990ee35` |
| `graphics/units/temple_guard/temple_guard_idle_dir06_dat4x.png` | DAT idle pose | 196703 | `3e617c4beeb4524c230f53d05e823a2e384a1083` |
| `graphics/units/temple_guard/temple_guard_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 198604 | `c98ce9046210f33ad82c7d0fb807f13145cc0de8` |
| `graphics/units/temple_guard/temple_guard_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 189285 | `aeb00170e14334e6103fdc99bb5efd6580ec5819` |
| `graphics/units/teutonic_knight/icon.png` | Game icon | 83981 | `ef017f24a3335d9c6092dcb7a7bfb5bf88063a20` |
| `graphics/units/teutonic_knight/icon_transparent.png` | Transparent icon | 86413 | `ce886e4bdccd827c2f6f7f009a9ccf4ef5373303` |
| `graphics/units/teutonic_knight/teutonic_knight_attack_dir06_dat4x.gif` | Attack animation | 1680631 | `3aafb8c5a28450377fef53b2f2cb7788af744f32` |
| `graphics/units/teutonic_knight/teutonic_knight_idle_dir06.png` | Native idle pose | 3846 | `5bf3dee5059f21f36f94993a85b3310a162780a4` |
| `graphics/units/teutonic_knight/teutonic_knight_idle_dir06_dat4x.png` | DAT idle pose | 139933 | `ae245c7701a9eda75d9c7661c86545ea9db0bafe` |
| `graphics/units/teutonic_knight/teutonic_knight_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 143503 | `d5299eb964cc2bf1a545033b1081118a035c4408` |
| `graphics/units/teutonic_knight/teutonic_knight_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 138431 | `998f070c61efe4bede879d1b0c85ad8c71f550f0` |
| `graphics/units/thirisadai/icon.png` | Game icon | 116342 | `70943c7883273e9c88aa96fec110f496e604ef07` |
| `graphics/units/thirisadai/icon_transparent.png` | Transparent icon | 121780 | `3b60ac392e79d9456d9dddb75a9dc1a39a0f2d99` |
| `graphics/units/thirisadai/thirisadai_idle_dir06.png` | Native idle pose | 223148 | `da25276e2c098d0c46746473636a006ed49fecdf` |
| `graphics/units/thirisadai/thirisadai_idle_dir06_dat4x.png` | DAT idle pose | 5376199 | `7ae335e137c3f0d65f346838e387be4860c3c9ca` |
| `graphics/units/thirisadai/thirisadai_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 5420470 | `9bfaeee0a7623f9674ba17ec2eb21fab82bc4a4d` |
| `graphics/units/thirisadai/thirisadai_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 5912070 | `a97ad87bfd0899dd76f85772d5f85f7da957764b` |
| `graphics/units/throwing_axeman/icon.png` | Game icon | 97538 | `67def0692002b449bfc4c2b292bbb6c0aa7463bc` |
| `graphics/units/throwing_axeman/icon_transparent.png` | Transparent icon | 101017 | `69da096b4b8e9917f75831efd2f7c6b2e9464dbe` |
| `graphics/units/throwing_axeman/throwing_axeman_attack_dir06_dat4x.gif` | Attack animation | 1195627 | `6ae2c3f1ad584008f7a6433aaa866ae7693de123` |
| `graphics/units/throwing_axeman/throwing_axeman_idle_dir06.png` | Native idle pose | 5580 | `ff89437c0e3a92a119a6bb9b55510a0b48034398` |
| `graphics/units/throwing_axeman/throwing_axeman_idle_dir06_dat4x.png` | DAT idle pose | 215945 | `7b2a3212a7705ac2ffe8ca11ca1a8ad7abcf4d01` |
| `graphics/units/throwing_axeman/throwing_axeman_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 217372 | `9828d9391b44bcb930a472f175ce866e01a45346` |
| `graphics/units/throwing_axeman/throwing_axeman_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 208201 | `8bc6adfff7c469e5b7a6734e453473369175bfea` |
| `graphics/units/tiger_cavalry/icon.png` | Game icon | 71860 | `10912592cd912999d9a985258d83dcdb7c739de7` |
| `graphics/units/tiger_cavalry/icon_transparent.png` | Transparent icon | 75467 | `f14553db29acc7810c883b58bda6029f7ad5b769` |
| `graphics/units/tiger_cavalry/tiger_cavalry_attack_dir06_dat4x.gif` | Attack animation | 4736895 | `3ea6bb7b940819db4dd0fb706f37eae2299a8d83` |
| `graphics/units/tiger_cavalry/tiger_cavalry_idle_dir06.png` | Native idle pose | 13889 | `7adb4326e9efda0774ea8c6f89ac82bccd2e1bf4` |
| `graphics/units/tiger_cavalry/tiger_cavalry_idle_dir06_dat4x.png` | DAT idle pose | 438825 | `2e58736a785aea6c56b3ae0b1e73273650daf7a7` |
| `graphics/units/tiger_cavalry/tiger_cavalry_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 437857 | `a3b8b4e12f29b4a3c275a582b7c60f9785a52921` |
| `graphics/units/tiger_cavalry/tiger_cavalry_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 432437 | `a13d9250e90c4c64f31fd1bbc52f61c3cbc2fa1a` |
| `graphics/units/traction_trebuchet/icon.png` | Game icon | 64719 | `a7c9eadf5705e481b950950316238b23373d018e` |
| `graphics/units/traction_trebuchet/icon_transparent.png` | Transparent icon | 71450 | `76b135f1f209a92f097b1bafb76a2fff4219d74e` |
| `graphics/units/traction_trebuchet/traction_trebuchet_attack_dir06_dat4x.gif` | Attack animation | 25131899 | `92cda302a169c8ec67a1d48ce525f812b5c6b5eb` |
| `graphics/units/traction_trebuchet/traction_trebuchet_idle_dir06.png` | Native idle pose | 45376 | `f549c71c2156761cdcc82937a81f6ea9d49823d5` |
| `graphics/units/traction_trebuchet/traction_trebuchet_idle_dir06_dat4x.png` | DAT idle pose | 1287266 | `1adb882c65f584fa59f62e8a4da99d5ebd513f88` |
| `graphics/units/traction_trebuchet/traction_trebuchet_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1286544 | `098b194e9bced889d95018c7f46d839be17a748f` |
| `graphics/units/traction_trebuchet/traction_trebuchet_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1370904 | `e75f4ae83c1b55112c90272326c1b7c48542bcbb` |
| `graphics/units/trebuchet/icon.png` | Game icon | 123333 | `89350f5c50e1bde965a36f805fe962a2fa121dbb` |
| `graphics/units/trebuchet/icon_transparent.png` | Transparent icon | 126776 | `b0a8b652456eef922466de8a41d9ca011de3264b` |
| `graphics/units/trebuchet/trebuchet_attack_dir06_dat4x.gif` | Attack animation | 50608983 | `b64b607ae970d8554cb3eb8c092e9f0c46b788c1` |
| `graphics/units/trebuchet/trebuchet_idle_dir06.png` | Native idle pose | 71594 | `463ed021d7698f75b0c0debbe64bed939ac130d3` |
| `graphics/units/trebuchet/trebuchet_idle_dir06_dat4x.png` | DAT idle pose | 1995689 | `2f42be095db17bc77a66771be237483a89c02176` |
| `graphics/units/trebuchet/trebuchet_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 2000656 | `5f01a30598174448bf10f29e782721dd6d6603bf` |
| `graphics/units/trebuchet/trebuchet_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 2136750 | `5e26f96c247f70414943065a4b78e3d0a491a0d3` |
| `graphics/units/trebuchet_packed/icon.png` | Game icon | 138456 | `a84ca85a32b85eb996659e5bbb063b25b3842c27` |
| `graphics/units/trebuchet_packed/icon_transparent.png` | Transparent icon | 140928 | `2537906dcadc683d8608fd70c7afa67ce46626c6` |
| `graphics/units/trebuchet_packed/trebuchet_packed_idle_dir06.png` | Native idle pose | 29455 | `51b979583dcc68f51afb6b177946a03c8f8dd648` |
| `graphics/units/trebuchet_packed/trebuchet_packed_idle_dir06_dat4x.png` | DAT idle pose | 786848 | `24b756f98903f3b0bae9a76195ab5f768d60f53d` |
| `graphics/units/trebuchet_packed/trebuchet_packed_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 786774 | `cfe7103b8fc520b0ddd47241b1f8935c54c06f85` |
| `graphics/units/trebuchet_packed/trebuchet_packed_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 821971 | `e94a0bd05976cb9b7ebdc8f18233474584b4d607` |
| `graphics/units/turtle_ship/icon.png` | Game icon | 126712 | `479fbc11a9174d4ecc20f1969582f34370538ed7` |
| `graphics/units/turtle_ship/icon_transparent.png` | Transparent icon | 129230 | `205702635d6ba90101cf8c7ce5eca9b13fde5a79` |
| `graphics/units/turtle_ship/turtle_ship_idle_dir06.png` | Native idle pose | 124799 | `2f5c251eb47bb801d6e8c1e6603c35ade154bc82` |
| `graphics/units/turtle_ship/turtle_ship_idle_dir06_dat4x.png` | DAT idle pose | 3224030 | `8617211234a8c8a8c5b55a8dbf5807c00f9916bf` |
| `graphics/units/turtle_ship/turtle_ship_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 3231088 | `4248d0f259f29718b3a37a6dc368809c391802bf` |
| `graphics/units/turtle_ship/turtle_ship_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 3384284 | `9ee69590a35b8f77d1dbe264e5419f63fe0a248f` |
| `graphics/units/two_handed_swordsman/icon.png` | Game icon | 70918 | `2d62c85f32362b00974f5e9f20e93ed383dcfed9` |
| `graphics/units/two_handed_swordsman/icon_transparent.png` | Transparent icon | 73568 | `68bbe1bda0ab3c6e2ef04b6aedbcdc38dd2382dc` |
| `graphics/units/two_handed_swordsman/two_handed_swordsman_attack_dir06_dat4x.gif` | Attack animation | 1045031 | `b04ad4ba7b12df6db994d417a3a6a7c211626d59` |
| `graphics/units/two_handed_swordsman/two_handed_swordsman_idle_dir06.png` | Native idle pose | 4046 | `cbc89767ed70031c533d82949a2033e723a05ed2` |
| `graphics/units/two_handed_swordsman/two_handed_swordsman_idle_dir06_dat4x.png` | DAT idle pose | 188324 | `6b9da51f4c68b4aa18bf820cfde82755a9ba9ec2` |
| `graphics/units/two_handed_swordsman/two_handed_swordsman_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 188462 | `a24c877ecd9ddef2b3c5a7ae859a74ca1d1fd688` |
| `graphics/units/two_handed_swordsman/two_handed_swordsman_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 174955 | `031dea1dbaec4c157d66d0b5cd814863c755b114` |
| `graphics/units/urumi_swordsman/icon.png` | Game icon | 55794 | `25066f3738bf1c7423878f6bb45fb6ed25f004aa` |
| `graphics/units/urumi_swordsman/icon_transparent.png` | Transparent icon | 59084 | `98484b369113a2eb1ea5bb96058af4675f05ada0` |
| `graphics/units/urumi_swordsman/urumi_swordsman_attack_dir06_dat4x.gif` | Attack animation | 884423 | `2cbd1f27683daead7543cea781cda58ff0004b42` |
| `graphics/units/urumi_swordsman/urumi_swordsman_idle_dir06.png` | Native idle pose | 3160 | `6a9b304933feffd3e5678e50139ea4fc6627b4e9` |
| `graphics/units/urumi_swordsman/urumi_swordsman_idle_dir06_dat4x.png` | DAT idle pose | 137588 | `ca20aa095ae08aa9367c3c04548542024af9a003` |
| `graphics/units/urumi_swordsman/urumi_swordsman_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 138893 | `34a395473d14e31ae1cd8abbbed8400c5b1db143` |
| `graphics/units/urumi_swordsman/urumi_swordsman_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 135754 | `775f84327d5d59d9d4964fdb06f661ecfa03393e` |
| `graphics/units/war_chariot/icon.png` | Game icon | 103927 | `ae25d643a8e1b756c7b725e7bd2f0fe1e2689b00` |
| `graphics/units/war_chariot/icon_transparent.png` | Transparent icon | 106360 | `c2d52fcd0aebd92a00c7ae4fa5fba040d6d3e8d1` |
| `graphics/units/war_chariot/war_chariot_attack_dir06_dat4x.gif` | Attack animation | 5974999 | `f7a4019f2db05863410137698f2759668d160bda` |
| `graphics/units/war_chariot/war_chariot_idle_dir06.png` | Native idle pose | 31927 | `27b0b772b7e83baa216078fddf6fb6c5966d01ad` |
| `graphics/units/war_chariot/war_chariot_idle_dir06_dat4x.png` | DAT idle pose | 938995 | `305b152c6362b3d3ea6f8284cd460c83badb0d40` |
| `graphics/units/war_chariot/war_chariot_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 946770 | `7f41a1d7060697f83063a062b75304e2c5d52b6a` |
| `graphics/units/war_chariot/war_chariot_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 962834 | `f0c2cef92c478cc2fee72f532960683514d406b1` |
| `graphics/units/war_chariot_3k/icon.png` | Game icon | 77482 | `0bb7879b230af7609929f6e0a3fdb75d55eadc4b` |
| `graphics/units/war_chariot_3k/icon_transparent.png` | Transparent icon | 80590 | `540e93c21eb6ad01f8ec48b0229aa73d27b3b499` |
| `graphics/units/war_chariot_3k/war_chariot_3k_attack_dir06_dat4x.gif` | Attack animation | 4954329 | `20216e612e34cfe0e65ddbc5e44e940342115818` |
| `graphics/units/war_chariot_3k/war_chariot_3k_idle_dir06.png` | Native idle pose | 35688 | `53d07eb9ce8591ee61fda108f2a193abf60c20c1` |
| `graphics/units/war_chariot_3k/war_chariot_3k_idle_dir06_dat4x.png` | DAT idle pose | 1043654 | `b8e51001728ca6d98d973428a884972819e64de5` |
| `graphics/units/war_chariot_3k/war_chariot_3k_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1040002 | `dd77e7d751b31a38030e79a79440221b984a102b` |
| `graphics/units/war_chariot_3k/war_chariot_3k_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1039537 | `e28ce5112fa34cf19fa561f3490b1ddca14c9269` |
| `graphics/units/war_dog/icon.png` | Game icon | 33148 | `c5a3b54f722d3e8f9d9f05c20471aa4db3162a2b` |
| `graphics/units/war_dog/icon_transparent.png` | Transparent icon | 36915 | `2fd292f58020648d611fe9088a2cdfa324b934be` |
| `graphics/units/war_dog/war_dog_attack_dir06_dat4x.gif` | Attack animation | 902242 | `8e6e3b98cd513a047e9fa7944c2a02e14c682a97` |
| `graphics/units/war_dog/war_dog_idle_dir06.png` | Native idle pose | 3718 | `b8b04dc4c0a911ad186439222720893c82c61e18` |
| `graphics/units/war_dog/war_dog_idle_dir06_dat4x.png` | DAT idle pose | 137196 | `663a64518f2ce132f573d294b13ee88b721b07d0` |
| `graphics/units/war_dog/war_dog_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 136975 | `5b1ed816c7c9131148ca383b66229d4889fd67d7` |
| `graphics/units/war_dog/war_dog_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 135639 | `99732c3a68d64ee1253fbeaec9606e078d1e2ca5` |
| `graphics/units/war_elephant/icon.png` | Game icon | 141204 | `12eb215d79261db82b070f42aa95405d2ec7f769` |
| `graphics/units/war_elephant/icon_transparent.png` | Transparent icon | 145049 | `1c2b3c7f492dfbfea3c41d6d514676ef41b3301e` |
| `graphics/units/war_elephant/war_elephant_attack_dir06_dat4x.gif` | Attack animation | 13130306 | `b0c24ae2d2efb2e7655fac0597fd3bb143a40add` |
| `graphics/units/war_elephant/war_elephant_idle_dir06.png` | Native idle pose | 37767 | `fd10a13ac7f0a664fb1512fd1f457ea6943718e0` |
| `graphics/units/war_elephant/war_elephant_idle_dir06_dat4x.png` | DAT idle pose | 955060 | `12d641805b337cee3ef18de3ba9da037efa3452c` |
| `graphics/units/war_elephant/war_elephant_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 958706 | `1ff40b8a1d64232a9dfaae293ee8c1ccacdf8035` |
| `graphics/units/war_elephant/war_elephant_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1001579 | `cbe136aac81c08b6073dcf19816d49873bc4e662` |
| `graphics/units/war_galley/icon.png` | Game icon | 114537 | `6a04991dbf79d099bf4d8726eab746d8751e7987` |
| `graphics/units/war_galley/icon_transparent.png` | Transparent icon | 116669 | `2b87b3c80d564a7303dd1882627cfbbbea542150` |
| `graphics/units/war_galley/war_galley_idle_dir06.png` | Native idle pose | 49025 | `d0c3eecae206d04326f52a423a246a6a2ccec045` |
| `graphics/units/war_galley/war_galley_idle_dir06_dat4x.png` | DAT idle pose | 1368254 | `87f75d2ca2d807abc1800837a00a05017f39eaaa` |
| `graphics/units/war_galley/war_galley_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1368254 | `87f75d2ca2d807abc1800837a00a05017f39eaaa` |
| `graphics/units/war_galley/war_galley_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1426903 | `0dae749e62e2718d45bca8236cc4318d1cd46239` |
| `graphics/units/war_hulk/icon.png` | Game icon | 74206 | `ad534317b04c23d1f4911acb529c13ca200a59ee` |
| `graphics/units/war_hulk/icon_transparent.png` | Transparent icon | 77611 | `0f874af083b87cbe380947509fd75b464e715386` |
| `graphics/units/war_hulk/war_hulk_idle_dir06.png` | Native idle pose | 38268 | `abf81dfac483669fc2ed08fbe2d0dc5ec2eead2b` |
| `graphics/units/war_hulk/war_hulk_idle_dir06_dat4x.png` | DAT idle pose | 953114 | `b531babf312ec64489d3b5f919a77143a0387467` |
| `graphics/units/war_hulk/war_hulk_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 950947 | `c5677487659dbe85f4bfb4570b180030a4b3a86b` |
| `graphics/units/war_hulk/war_hulk_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1018834 | `4c658cbcc1d827a04c04fb8b5e8ab4ccd8ca1bee` |
| `graphics/units/war_wagon/icon.png` | Game icon | 118203 | `fc75a02cfb769f9410d601dd61e59d3b3fe9e9a9` |
| `graphics/units/war_wagon/icon_transparent.png` | Transparent icon | 120542 | `9df900b5733d05ac68d66bbb9da2312199f3c933` |
| `graphics/units/war_wagon/war_wagon_idle_dir06.png` | Native idle pose | 55658 | `3231ba674a7bb1ce99c69d6674da5e533acfc249` |
| `graphics/units/war_wagon/war_wagon_idle_dir06_dat4x.png` | DAT idle pose | 1395159 | `3a296a7f933089c576429d6118ead4b44f51d757` |
| `graphics/units/war_wagon/war_wagon_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1394447 | `2c7c0e2ea310fb4629439981891bca5a9786d497` |
| `graphics/units/war_wagon/war_wagon_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1502524 | `bc663bdba9f238869fbaca2d30e126366c106330` |
| `graphics/units/warrior_priest/icon.png` | Game icon | 69398 | `d1e64b85cf9f801f4615ba9d5171f07cc33ee29c` |
| `graphics/units/warrior_priest/icon_transparent.png` | Transparent icon | 73547 | `7800344ac8340edf4025fdb763ef66282f41998c` |
| `graphics/units/warrior_priest/warrior_priest_attack_dir06_dat4x.gif` | Attack animation | 1158231 | `c59ba5ed79a8b00ad425495aefe46b50d9b85acc` |
| `graphics/units/warrior_priest/warrior_priest_flux_hd.png` | HD unit illustration | 934065 | `4e870d2915676b4dffc63545b934ef72438413d7` |
| `graphics/units/warrior_priest/warrior_priest_idle_dir06.png` | Native idle pose | 4260 | `b4686498606daa41950eea412e7561922ca421dc` |
| `graphics/units/warrior_priest/warrior_priest_idle_dir06_dat4x.png` | DAT idle pose | 138633 | `acc51be862c99d97e96b5cb4145de3adf5caf235` |
| `graphics/units/warrior_priest/warrior_priest_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 140848 | `df535576993a2275af25e71b854c0e521fd38856` |
| `graphics/units/warrior_priest/warrior_priest_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 140928 | `b9728f6267d8cbabd62b294956139bacc3b0beb6` |
| `graphics/units/white_feather_guard/icon.png` | Game icon | 59919 | `8716d0d14e22656def0d540742a1bbe440080d9a` |
| `graphics/units/white_feather_guard/icon_transparent.png` | Transparent icon | 62782 | `418c17832cb24a202d2a3729a63427b755a1cda6` |
| `graphics/units/white_feather_guard/white_feather_guard_attack_dir06_dat4x.gif` | Attack animation | 1299945 | `efd1811b2d71040fa0d79fdcc3c3a765bd883aa3` |
| `graphics/units/white_feather_guard/white_feather_guard_idle_dir06.png` | Native idle pose | 4879 | `39cf42ae4b7933be9a4c2a141854845ee3423133` |
| `graphics/units/white_feather_guard/white_feather_guard_idle_dir06_dat4x.png` | DAT idle pose | 221845 | `bbc9bd807911d6e66ee13ca7dbd91f9c92d70a04` |
| `graphics/units/white_feather_guard/white_feather_guard_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 221732 | `08b336bfe91cd1aebb65fe4d494167c541cd39a7` |
| `graphics/units/white_feather_guard/white_feather_guard_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 205880 | `78b990d1f0890ec452c505c833a790ac7786c181` |
| `graphics/units/winged_hussar/icon.png` | Game icon | 109223 | `3dbc91647cc173ef7fad4e7105821ca6a89b85ef` |
| `graphics/units/winged_hussar/icon_transparent.png` | Transparent icon | 113610 | `9d2f4982ed95d5fcfa34c3f3cbc63975aaaf3832` |
| `graphics/units/winged_hussar/winged_hussar_attack_dir06_dat4x.gif` | Attack animation | 2410779 | `0b8ae60f3a499c7f414b45b167c4a61d5b1ef1db` |
| `graphics/units/winged_hussar/winged_hussar_idle_dir06.png` | Native idle pose | 15616 | `66d958ff3f19247f580b5bba8c0328c771caa1ea` |
| `graphics/units/winged_hussar/winged_hussar_idle_dir06_dat4x.png` | DAT idle pose | 472537 | `0059f4fc4209f089a88fe6be231127d7319d9802` |
| `graphics/units/winged_hussar/winged_hussar_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 471577 | `80db069e946d942108495be4b15e36d791ca084c` |
| `graphics/units/winged_hussar/winged_hussar_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 468029 | `d813dabea849dc7c5cf545c57c1594e42e5bf2e0` |
| `graphics/units/woad_raider/icon.png` | Game icon | 49766 | `d1cf20aad3ce83ab6d6e73c62747a3a32c93647f` |
| `graphics/units/woad_raider/icon_transparent.png` | Transparent icon | 53752 | `cc78bb0f8f3adbd52744318235bedddd1bd04035` |
| `graphics/units/woad_raider/woad_raider_attack_dir06_dat4x.gif` | Attack animation | 1119986 | `78b5dfd5ed2428fe2ebb0775165c02f9c4bd71ca` |
| `graphics/units/woad_raider/woad_raider_idle_dir06.png` | Native idle pose | 4812 | `d4f5b2961ba0cd8838f2b731ce70d69eef76854e` |
| `graphics/units/woad_raider/woad_raider_idle_dir06_dat4x.png` | DAT idle pose | 145487 | `78f2c1a742f85af8e451764a5f4a90e7bea823ce` |
| `graphics/units/woad_raider/woad_raider_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 146767 | `e65ed41f29f943e9f59df91219e128320dd5b9ef` |
| `graphics/units/woad_raider/woad_raider_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 150774 | `559ca4e7ea7703bd277356e5be7895c64435a4ca` |
| `graphics/units/xebec/icon.png` | Game icon | 126055 | `63b87aa9bbb1556e03093f1e9bb33be920b640fa` |
| `graphics/units/xebec/icon_transparent.png` | Transparent icon | 126691 | `63e4a479512f0177e6b2ac13d8899be61a2e7966` |
| `graphics/units/xebec/xebec_idle_dir06.png` | Native idle pose | 53778 | `80f293b1704409e8eeb0e214286ca5ce4363a7f4` |
| `graphics/units/xebec/xebec_idle_dir06_dat4x.png` | DAT idle pose | 1343165 | `ab2f58c0450156b8ea604db7dbd6089e6ac844e3` |
| `graphics/units/xebec/xebec_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1391042 | `4c6eeb45163918f6f5edf014a0010387856fb278` |
| `graphics/units/xebec/xebec_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1485256 | `bfafcdc9421ea3b15c5890ce06fcbc02aa6c51bf` |
| `graphics/units/xianbei_raider/icon.png` | Game icon | 68510 | `271f93574462d91e4471d141e9c27249c9f6e1da` |
| `graphics/units/xianbei_raider/icon_transparent.png` | Transparent icon | 72093 | `9c74adcd0f9ec676b9b598308e7871ca50ef5e65` |
| `graphics/units/xianbei_raider/xianbei_raider_attack_dir06_dat4x.gif` | Attack animation | 3340598 | `08e10f0e9b3d92d4cfb5f90f6de1476c47b545f0` |
| `graphics/units/xianbei_raider/xianbei_raider_flux_hd.png` | HD unit illustration | 1121407 | `841078d737f4002da39477a783e020dcadbcc968` |
| `graphics/units/xianbei_raider/xianbei_raider_idle_dir06.png` | Native idle pose | 12125 | `c7d2dbb0fa65977f737964b2107ffe0282d34b02` |
| `graphics/units/xianbei_raider/xianbei_raider_idle_dir06_dat4x.png` | DAT idle pose | 351029 | `f1699e72f1013e86658636cb46cd2b2ddad4ce7a` |
| `graphics/units/xianbei_raider/xianbei_raider_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 351703 | `1af4fe668a3315976f98c5fb36a7c7d3af085935` |
| `graphics/units/xianbei_raider/xianbei_raider_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 364159 | `0f8543d5f8c76f9b14655d5a505d62f5fa1c0289` |
| `graphics/art/flux2_hybrid/condottiero_idle_dir05_bg.png` | FLUX2 background render | 963676 | `5afc55c04d4863de65148f5da9f0bdc416cebff3` |
| `graphics/art/flux2_hybrid/condottiero_idle_dir05_icon.png` | FLUX2 artwork icon | 39282 | `506c97fb1ad537bd84130c39d538268968d1c7d6` |
| `graphics/art/flux2_hybrid/condottiero_idle_dir05_nobg.png` | FLUX2 transparent artwork | 441046 | `9158f8c30947cc7f6ffb174852e45bab0d11e527` |
| `graphics/art/flux2_hybrid/elite_hearth_troop_idle_dir05_bg.png` | FLUX2 background render | 821367 | `52d99e5919fc7722f9eb486224bd0093fa7d5db6` |
| `graphics/art/flux2_hybrid/elite_hearth_troop_idle_dir05_icon.png` | FLUX2 artwork icon | 53017 | `4ca6f08132b6b16cb6252949d3fa8cef26ba6eb9` |
| `graphics/art/flux2_hybrid/elite_hearth_troop_idle_dir05_nobg.png` | FLUX2 transparent artwork | 641772 | `4d92f916fa4c4c46feb6c876299e0b4f2dae5920` |
| `graphics/art/flux2_hybrid/elite_jarl_idle_dir05_bg.png` | FLUX2 background render | 735316 | `c23aaf0e6131141d6fc9c62ea5eb5e7fa2573635` |
| `graphics/art/flux2_hybrid/elite_jarl_idle_dir05_icon.png` | FLUX2 artwork icon | 53526 | `b8699423afb6f536172fd3f03675abfa60c57161` |
| `graphics/art/flux2_hybrid/elite_jarl_idle_dir05_nobg.png` | FLUX2 transparent artwork | 520323 | `68d5e22f68733f3717594a9285fa70adb39c724b` |
| `graphics/art/flux2_hybrid/elite_jomsviking_idle_dir05_bg.png` | FLUX2 background render | 640683 | `41eeab655a47450ecb40686bd9aa42dbf8f473ce` |
| `graphics/art/flux2_hybrid/elite_jomsviking_idle_dir05_icon.png` | FLUX2 artwork icon | 38164 | `10b9e42c43cb6838bcaba18b2e6bd87937312224` |
| `graphics/art/flux2_hybrid/elite_jomsviking_idle_dir05_nobg.png` | FLUX2 transparent artwork | 474034 | `fe713a647ef45bde052c8516c574556b048e3051` |
| `graphics/art/flux2_hybrid/elite_varangian_guard_idle_dir05_bg.png` | FLUX2 background render | 673774 | `d4e8a175cba3ac0ff3a1e723ad255cae3d0916da` |
| `graphics/art/flux2_hybrid/elite_varangian_guard_idle_dir05_icon.png` | FLUX2 artwork icon | 47842 | `761e1884c2df8d1e6e42b11f299af3e27568606a` |
| `graphics/art/flux2_hybrid/elite_varangian_guard_idle_dir05_nobg.png` | FLUX2 transparent artwork | 506313 | `ebcc62e1ec429b6765ee1f295f019444260052a3` |
| `graphics/art/flux2_hybrid/flaming_camel_idle_dir05_bg.png` | FLUX2 background render | 1046888 | `811b778376d3b952271ce3a7677c9a5bc1559b3d` |
| `graphics/art/flux2_hybrid/flaming_camel_idle_dir05_icon.png` | FLUX2 artwork icon | 75774 | `6ce49dc23f85026d5115150ed0e8bc52a6b3aca8` |
| `graphics/art/flux2_hybrid/flaming_camel_idle_dir05_nobg.png` | FLUX2 transparent artwork | 967621 | `4f86db7402d6caaa4f84eea76718871035495288` |
| `graphics/art/flux2_hybrid/flemish_militia_idle_dir05_bg.png` | FLUX2 background render | 969984 | `1a15948d7ec301ce0ea5bebd92bea10714b0e96d` |
| `graphics/art/flux2_hybrid/flemish_militia_idle_dir05_icon.png` | FLUX2 artwork icon | 50919 | `48b43178fc5122161dae457118035428c3b8d064` |
| `graphics/art/flux2_hybrid/flemish_militia_idle_dir05_nobg.png` | FLUX2 transparent artwork | 653722 | `ca1d1761e5b4d23df0834b207db9571abcbc7d21` |
| `graphics/art/flux2_hybrid/grenadier_idle_dir05_bg.png` | FLUX2 background render | 680105 | `cdedb0b53392b21583ff1f3314ad763db2ce6074` |
| `graphics/art/flux2_hybrid/grenadier_idle_dir05_icon.png` | FLUX2 artwork icon | 50838 | `6eca22a68ca95aae378acee0a83ba45487f7c7c3` |
| `graphics/art/flux2_hybrid/grenadier_idle_dir05_nobg.png` | FLUX2 transparent artwork | 539885 | `b2af7d9df94a58bce4aabbc326c2cc1c52bb7241` |
| `graphics/art/flux2_hybrid/hearth_troop_idle_dir05_bg.png` | FLUX2 background render | 883835 | `5f6bcae979e29acb2fed42b691550c94b3de513b` |
| `graphics/art/flux2_hybrid/hearth_troop_idle_dir05_icon.png` | FLUX2 artwork icon | 60896 | `4ed086566910730794296c9b1c3ab067e552a821` |
| `graphics/art/flux2_hybrid/hearth_troop_idle_dir05_nobg.png` | FLUX2 transparent artwork | 789081 | `382c6a6f27d2cf05fca8dfbe9114e936afba786a` |
| `graphics/art/flux2_hybrid/heavy_mounted_crossbowman_idle_dir05_bg.png` | FLUX2 background render | 897809 | `5bb994b147b7c5dc3d0442c96b4832f5c44b3c05` |
| `graphics/art/flux2_hybrid/heavy_mounted_crossbowman_idle_dir05_icon.png` | FLUX2 artwork icon | 59342 | `cc4fc52367b3a54f45cbf805d190586c93cc152d` |
| `graphics/art/flux2_hybrid/heavy_mounted_crossbowman_idle_dir05_nobg.png` | FLUX2 transparent artwork | 698233 | `331e16a0b925e4204388b988e040ec59d0b85d98` |
| `graphics/art/flux2_hybrid/houfnice_idle_dir05_bg.png` | FLUX2 background render | 866680 | `c51fe5f30b9cb93eb5dd38441ce190db97596a71` |
| `graphics/art/flux2_hybrid/houfnice_idle_dir05_icon.png` | FLUX2 artwork icon | 93837 | `22d28e3023174ecf10cf732de5332ff3f7b5a364` |
| `graphics/art/flux2_hybrid/houfnice_idle_dir05_nobg.png` | FLUX2 transparent artwork | 570017 | `213de2e6f88632cc85874a8f2c32c99b139afb35` |
| `graphics/art/flux2_hybrid/imperial_camel_rider_idle_dir05_bg.png` | FLUX2 background render | 899600 | `84dc51b9871b66f42a33bee1a9f3fedc0f8bc06b` |
| `graphics/art/flux2_hybrid/imperial_camel_rider_idle_dir05_icon.png` | FLUX2 artwork icon | 42965 | `4c5e2f59d911043b8f3d5faa9603451a4321498b` |
| `graphics/art/flux2_hybrid/imperial_camel_rider_idle_dir05_nobg.png` | FLUX2 transparent artwork | 478023 | `a057ee47d4c4193b37458bfa2b6621b315e6015d` |
| `graphics/art/flux2_hybrid/imperial_skirmisher_idle_dir05_bg.png` | FLUX2 background render | 709187 | `003b32861d168753aecaa41493e88d3d0101e827` |
| `graphics/art/flux2_hybrid/imperial_skirmisher_idle_dir05_icon.png` | FLUX2 artwork icon | 36619 | `592cfe1ed68189100ae569372315f202abc75fa5` |
| `graphics/art/flux2_hybrid/imperial_skirmisher_idle_dir05_nobg.png` | FLUX2 transparent artwork | 410082 | `6d39709f8472c8e9e8328bdf7c11c6181d53d67a` |
| `graphics/art/flux2_hybrid/jarl_idle_dir05_bg.png` | FLUX2 background render | 705653 | `44c7a15f477236f74743c08bc06fa2e07fa8c36b` |
| `graphics/art/flux2_hybrid/jarl_idle_dir05_icon.png` | FLUX2 artwork icon | 46927 | `55159675afe259a856541f22527ce058014568aa` |
| `graphics/art/flux2_hybrid/jarl_idle_dir05_nobg.png` | FLUX2 transparent artwork | 489086 | `5afe3f28ad88365fa03d216766a9dd0234a4caa2` |
| `graphics/art/flux2_hybrid/jomsviking_idle_dir05_bg.png` | FLUX2 background render | 645220 | `c5216c1e84114b28e09f0a0822634f29fad000e8` |
| `graphics/art/flux2_hybrid/jomsviking_idle_dir05_icon.png` | FLUX2 artwork icon | 37118 | `24b0e9b8603933174e29246f1a7c07fe8f889de5` |
| `graphics/art/flux2_hybrid/jomsviking_idle_dir05_nobg.png` | FLUX2 transparent artwork | 458742 | `677d4dac9d15de4012c5e47dfdfe7368b81b13ae` |
| `graphics/art/flux2_hybrid/missionary_idle_dir05_bg.png` | FLUX2 background render | 601104 | `5bea566a7d37e33bfd3f60937886e8c756f4c9fc` |
| `graphics/art/flux2_hybrid/missionary_idle_dir05_icon.png` | FLUX2 artwork icon | 55319 | `55bf47b10290059275ce8f3fb8c0d0ae5ea87b7e` |
| `graphics/art/flux2_hybrid/missionary_idle_dir05_nobg.png` | FLUX2 transparent artwork | 475738 | `00da80ed37b81f8f439257538948e89efafb3f6d` |
| `graphics/art/flux2_hybrid/mounted_crossbowman_idle_dir05_bg.png` | FLUX2 background render | 782682 | `e3ba9138d4d2d67df9a4f21166acb4ccb179185b` |
| `graphics/art/flux2_hybrid/mounted_crossbowman_idle_dir05_icon.png` | FLUX2 artwork icon | 48374 | `32b24530c441b7766810d1f6c213e0d1b0402d5d` |
| `graphics/art/flux2_hybrid/mounted_crossbowman_idle_dir05_nobg.png` | FLUX2 transparent artwork | 578026 | `e48a8d9f0bbd0c08466ccc8b5ffd611933892bac` |
| `graphics/art/flux2_hybrid/mounted_trebuchet_idle_dir05_bg.png` | FLUX2 background render | 1287880 | `76eeb3169ae3e7295ce822971c8e83377ba9ab1e` |
| `graphics/art/flux2_hybrid/mounted_trebuchet_idle_dir05_icon.png` | FLUX2 artwork icon | 82799 | `605b5baa433d329691b1d4e96e98a1986c48ff06` |
| `graphics/art/flux2_hybrid/mounted_trebuchet_idle_dir05_nobg.png` | FLUX2 transparent artwork | 1017579 | `07a88e9255460158f89b0de5f013e26033c62832` |
| `graphics/art/flux2_hybrid/savar_idle_dir05_bg.png` | FLUX2 background render | 861945 | `0d9287c664ceae3a2df6c6d7429808f8a7e514d7` |
| `graphics/art/flux2_hybrid/savar_idle_dir05_icon.png` | FLUX2 artwork icon | 52582 | `d5086314129c662ca63fd229ed4c8c3197c8ddb9` |
| `graphics/art/flux2_hybrid/savar_idle_dir05_nobg.png` | FLUX2 transparent artwork | 671092 | `eb015a9f659a134bbe2b02b90870ee4239704bc4` |
| `graphics/art/flux2_hybrid/varangian_guard_idle_dir05_bg.png` | FLUX2 background render | 786164 | `63783ac9bc1b03311ca36027283059d5db99f036` |
| `graphics/art/flux2_hybrid/varangian_guard_idle_dir05_icon.png` | FLUX2 artwork icon | 53334 | `c8e87447e756b88347be6a2a1a260b1fb2e90730` |
| `graphics/art/flux2_hybrid/varangian_guard_idle_dir05_nobg.png` | FLUX2 transparent artwork | 651971 | `da47cf29455a4c02ffe3bd1fc1ac4dc8f285736a` |
| `graphics/art/flux2_hybrid/war_chariot_focus_fire_idle_dir05_bg.png` | FLUX2 background render | 689231 | `cbb5ce10439344100d75fe673c1acad490b83173` |
| `graphics/art/flux2_hybrid/war_chariot_focus_fire_idle_dir05_icon.png` | FLUX2 artwork icon | 46311 | `3ad15bc9a11a585516051e0676de25b6467bae65` |
| `graphics/art/flux2_hybrid/war_chariot_focus_fire_idle_dir05_nobg.png` | FLUX2 transparent artwork | 497438 | `13c3244a371e9066aca61cb39839fced46b3d896` |
| `graphics/units/elite_hearth_troop/elite_hearth_troop_attack_dir06_dat4x.gif` | Attack animation | 1480296 | `b6fd22c6a3dd91753b64d54c5eea1a63f9d9f0d7` |
| `graphics/units/elite_hearth_troop/elite_hearth_troop_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 193205 | `a1e834822aa7ab3f24e00fc70424494bab2b32d9` |
| `graphics/units/elite_hearth_troop/elite_hearth_troop_idle_dir06_dat4x.png` | DAT idle pose | 192518 | `eac3da76d055a6736c96a13e779ec10442c85f34` |
| `graphics/units/elite_hearth_troop/elite_hearth_troop_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 195634 | `c6f937f977fb80175a8798d252717e3b0baaf3a2` |
| `graphics/units/elite_hearth_troop/elite_hearth_troop_idle_dir06.png` | Native idle pose | 5659 | `6907132547e8f85ce46cafb60580c3534871c05f` |
| `graphics/units/elite_hearth_troop/icon_transparent.png` | Transparent icon | 71485 | `0db31e83bd4c06a1559e3a42719805f6442065fa` |
| `graphics/units/elite_hearth_troop/icon.png` | Game icon | 68337 | `6c6350633c3ce8ca8d3a4289ee8b6c26fc380428` |
| `graphics/units/elite_hussite_wagon/elite_hussite_wagon_attack_dir06_dat4x.gif` | Attack animation | 13959070 | `371d388679e9f838c48de94c227ae78603c7f442` |
| `graphics/units/elite_jarl/elite_jarl_attack_dir06_dat4x.gif` | Attack animation | 1788921 | `f2636b95a94034adb18127fe8dc8daf406aabe36` |
| `graphics/units/elite_jarl/elite_jarl_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 332938 | `4b822f698b3cfa70b11d26d9c6f60d4927c71ae8` |
| `graphics/units/elite_jarl/elite_jarl_idle_dir06_dat4x.png` | DAT idle pose | 332787 | `590cdfa2bff16c99741a1ffd43f4f712de212fb6` |
| `graphics/units/elite_jarl/elite_jarl_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 325672 | `6ed089bcfda0be4856da2653b1a57eb88bb40a81` |
| `graphics/units/elite_jarl/elite_jarl_idle_dir06.png` | Native idle pose | 11275 | `c06101a7bc750a779df22adc64611c60ebb057d2` |
| `graphics/units/elite_jarl/icon_transparent.png` | Transparent icon | 88534 | `a3b8a9f9d20bfcf43d1c14494567ae0924787dcd` |
| `graphics/units/elite_jarl/icon.png` | Game icon | 82465 | `85e8f574bee0b597dbcc2861ff1a36489abb98a7` |
| `graphics/units/elite_jomsviking/elite_jomsviking_attack_dir06_dat4x.gif` | Attack animation | 1379483 | `d0454c6eff8c3ebbb4b1b838ab0e149d6a7656fb` |
| `graphics/units/elite_jomsviking/elite_jomsviking_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 205067 | `7c5d72ea6050b537b3b0ec66551978271daf6385` |
| `graphics/units/elite_jomsviking/elite_jomsviking_idle_dir06_dat4x.png` | DAT idle pose | 205122 | `df109d0ae3661e91349fbf7560fa20dbee12ba2c` |
| `graphics/units/elite_jomsviking/elite_jomsviking_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 206854 | `86e5158a3de3647d5d58ddb932994e4c0bffda12` |
| `graphics/units/elite_jomsviking/elite_jomsviking_idle_dir06.png` | Native idle pose | 5371 | `cde2913a43de84efd7590a5a9d73e2eb78fd81a7` |
| `graphics/units/elite_jomsviking/icon_transparent.png` | Transparent icon | 74747 | `4262f50d76662ba6359bb0d3f1b804b9f37e08c1` |
| `graphics/units/elite_jomsviking/icon.png` | Game icon | 71039 | `c8068be73762e33ce82e39860df7a8734db7f951` |
| `graphics/units/elite_varangian_guard/elite_varangian_guard_attack_dir06_dat4x.gif` | Attack animation | 1306281 | `579548e9c53b4c0a382a2edbd04eb90aa2b491b2` |
| `graphics/units/elite_varangian_guard/elite_varangian_guard_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 153449 | `6447ec6d5296d6d9a479a88aa18adb70d0af7513` |
| `graphics/units/elite_varangian_guard/elite_varangian_guard_idle_dir06_dat4x.png` | DAT idle pose | 152597 | `9f8cdb9a18ed9f5e95b421204692b16d34c804a4` |
| `graphics/units/elite_varangian_guard/elite_varangian_guard_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 153367 | `787e34ba2c42a8bb4301e3320e59e247e8ccfaba` |
| `graphics/units/elite_varangian_guard/elite_varangian_guard_idle_dir06.png` | Native idle pose | 4726 | `0327b3577d50b80e5a5f91aa64be20c1015842a5` |
| `graphics/units/elite_varangian_guard/icon_transparent.png` | Transparent icon | 76842 | `db031a4ccaf7c94d743566459cd0ca5d4da8cb1a` |
| `graphics/units/elite_varangian_guard/icon.png` | Game icon | 72553 | `4dafe7c7368368a77a587750b9bf860ffc7ae042` |
| `graphics/units/elite_war_wagon/elite_war_wagon_attack_dir06_dat4x.gif` | Attack animation | 16545202 | `df1e76f733e0a378a9669c0ba026d485600fbb58` |
| `graphics/units/flaming_camel/flaming_camel_attack_dir06_dat4x.gif` | Attack animation | 8623299 | `f5ed4f1c9b9c02ae0b7c645e6eab2a250df979da` |
| `graphics/units/flaming_camel/flaming_camel_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 551583 | `f597bfbdfc63d87101bb9b3c049418b51fda77c2` |
| `graphics/units/flaming_camel/flaming_camel_idle_dir06_dat4x.png` | DAT idle pose | 562346 | `70057fa5ebdd3c6f690cad9b48c46d9f2528b3fb` |
| `graphics/units/flaming_camel/flaming_camel_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 584128 | `f4b220a3bc351c39da26c33ce243b06517b08cf7` |
| `graphics/units/flaming_camel/flaming_camel_idle_dir06.png` | Native idle pose | 22120 | `e070b5af0dc752686cc41952a6a395c3ce088ce5` |
| `graphics/units/flaming_camel/icon_transparent.png` | Transparent icon | 107195 | `3ecf1924efc7d44ea17a8738cc6d9c32b8ce40ac` |
| `graphics/units/flaming_camel/icon.png` | Game icon | 103553 | `2c948b7f6bf13e9465821523cae589fd248029e2` |
| `graphics/units/hearth_troop/hearth_troop_attack_dir06_dat4x.gif` | Attack animation | 1479404 | `8caff9ac516533f73d47ef6da310e0ab668e146f` |
| `graphics/units/hearth_troop/hearth_troop_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 192028 | `084a0d8a2f7249f1cab88471bf1ae5e32f174fa5` |
| `graphics/units/hearth_troop/hearth_troop_idle_dir06_dat4x.png` | DAT idle pose | 189667 | `0c873f6720b5596ba75da459cdcf7551325ab041` |
| `graphics/units/hearth_troop/hearth_troop_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 197810 | `de9f107020b00802491361b0ec936a6b86aa7f5c` |
| `graphics/units/hearth_troop/hearth_troop_idle_dir06.png` | Native idle pose | 5447 | `7d2ee9eb15836f9fd629829d5aa8b00601deeebe` |
| `graphics/units/hearth_troop/icon_transparent.png` | Transparent icon | 71042 | `8278a92f7e4eee4c1f04d68cbb557e0b93c3a7ca` |
| `graphics/units/hearth_troop/icon.png` | Game icon | 67825 | `0e599998b636897cb332a4fb56d6326c0da95ad3` |
| `graphics/units/heavy_mounted_crossbowman/heavy_mounted_crossbowman_attack_dir06_dat4x.gif` | Attack animation | 2227382 | `b8353248d5786aab5685abe3b77f3d4771ebd629` |
| `graphics/units/heavy_mounted_crossbowman/heavy_mounted_crossbowman_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 419091 | `87f56a4950d150fb7e269f04f47fca673ba12b97` |
| `graphics/units/heavy_mounted_crossbowman/heavy_mounted_crossbowman_idle_dir06_dat4x.png` | DAT idle pose | 420912 | `6a898fe53e6c7dfaa71e2feedb8139a8231e5edc` |
| `graphics/units/heavy_mounted_crossbowman/heavy_mounted_crossbowman_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 406659 | `195865fae5fa471123147cbbc34b8d36527b2abe` |
| `graphics/units/heavy_mounted_crossbowman/heavy_mounted_crossbowman_idle_dir06.png` | Native idle pose | 12758 | `2a542aedf23dcb38600a4fa41ee7bf6905743547` |
| `graphics/units/heavy_mounted_crossbowman/icon_transparent.png` | Transparent icon | 80191 | `060319bcc5a12040ba7e94c6c3955e22b627bed5` |
| `graphics/units/heavy_mounted_crossbowman/icon.png` | Game icon | 73790 | `5c97fa8d11ef3d197164ab250ec1163dd022adb2` |
| `graphics/units/jarl/icon_transparent.png` | Transparent icon | 83770 | `28c4cb7b972405ac6f614a5085073391f560e2b4` |
| `graphics/units/jarl/icon.png` | Game icon | 79932 | `277d162a84efc6ae5953ec51888636d1c9683607` |
| `graphics/units/jarl/jarl_attack_dir06_dat4x.gif` | Attack animation | 1749495 | `55019b1136b6a20ba108deca29e55b0254631cea` |
| `graphics/units/jarl/jarl_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 313182 | `c3d490887005f8ac9aeda0a4c472a71858622bec` |
| `graphics/units/jarl/jarl_idle_dir06_dat4x.png` | DAT idle pose | 312685 | `807d400de05a637c5be5dc2a1b5ba85983013a8d` |
| `graphics/units/jarl/jarl_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 312805 | `889f4b7e3e986958227e56da07481705e59d440d` |
| `graphics/units/jarl/jarl_idle_dir06.png` | Native idle pose | 10848 | `d80236d37689540982256877813380a1cbe9687c` |
| `graphics/units/jomsviking/icon_transparent.png` | Transparent icon | 77051 | `4c33aabe48a32a9d28d88b9d3503283755dea2a2` |
| `graphics/units/jomsviking/icon.png` | Game icon | 74073 | `62965414951a0fbd27fc5c5f9a22614a54db05f0` |
| `graphics/units/jomsviking/jomsviking_attack_dir06_dat4x.gif` | Attack animation | 1382258 | `d73a776b9820e0a2f8d5f18b231db1c889152a84` |
| `graphics/units/jomsviking/jomsviking_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 200597 | `ef7f6512dfa797fe505761f66d354cac89089cea` |
| `graphics/units/jomsviking/jomsviking_idle_dir06_dat4x.png` | DAT idle pose | 199917 | `a6d94422c826d4527dd3d6369b270ecd98818b06` |
| `graphics/units/jomsviking/jomsviking_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 206412 | `27ec5c1cdb74c4a45dc0950b6d6a75eca0c58048` |
| `graphics/units/jomsviking/jomsviking_idle_dir06.png` | Native idle pose | 5417 | `53ace725d631277fd42bc33c1783b91228b9a3c4` |
| `graphics/units/missionary/icon_transparent.png` | Transparent icon | 117665 | `0d34cf76e001a3d0fc9bdfa9f8ddd41101db5308` |
| `graphics/units/missionary/icon.png` | Game icon | 114978 | `f2fac61c7493da18bb5436ee0ec99116809fb574` |
| `graphics/units/missionary/missionary_attack_dir06_dat4x.gif` | Attack animation | 1486404 | `e7a17d352e8e33811f07233f9ae6c37a980d3dd7` |
| `graphics/units/missionary/missionary_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 287399 | `61f907cbab410391e027ea1d54531e6122d98f88` |
| `graphics/units/missionary/missionary_idle_dir06_dat4x.png` | DAT idle pose | 287564 | `1101f4b438ca7afc4828e9097d767822dda6ad19` |
| `graphics/units/missionary/missionary_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 292283 | `9e1e475cb470cd7f394cb717e44c429b31a17a67` |
| `graphics/units/missionary/missionary_idle_dir06.png` | Native idle pose | 8662 | `650a419717092cd2d43071e761bcfdad7785ec58` |
| `graphics/units/mounted_crossbowman/icon_transparent.png` | Transparent icon | 74289 | `a6b6af569fea790ede206e45bfa44a3511166d25` |
| `graphics/units/mounted_crossbowman/icon.png` | Game icon | 68863 | `557cea5c38e42bb96ca874acc1ee248e9eaffdd5` |
| `graphics/units/mounted_crossbowman/mounted_crossbowman_attack_dir06_dat4x.gif` | Attack animation | 2150766 | `d5fce4276cf79b8e6d34c4c251dba09d94ff4825` |
| `graphics/units/mounted_crossbowman/mounted_crossbowman_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 394161 | `0e1258859457c720a8adf45175ed40243ededc11` |
| `graphics/units/mounted_crossbowman/mounted_crossbowman_idle_dir06_dat4x.png` | DAT idle pose | 395587 | `3e340d81e2f95ed20804683dd5453d0fe8e1595b` |
| `graphics/units/mounted_crossbowman/mounted_crossbowman_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 384575 | `385431bdf7cabc8d6ca8753afd86d1657710c6a6` |
| `graphics/units/mounted_crossbowman/mounted_crossbowman_idle_dir06.png` | Native idle pose | 11739 | `ce634f436f97fc869e2d1f4775431bd95d66f909` |
| `graphics/units/varangian_guard/icon_transparent.png` | Transparent icon | 75071 | `450197cf2e176edefd915ba460bb7ceae764a5f8` |
| `graphics/units/varangian_guard/icon.png` | Game icon | 71064 | `1caf4317a217d2214da7befa2e74d929de75b1e6` |
| `graphics/units/varangian_guard/varangian_guard_attack_dir06_dat4x.gif` | Attack animation | 1235728 | `46a562113db79081dbd2f3336254e70d4a81fcbd` |
| `graphics/units/varangian_guard/varangian_guard_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 149042 | `e68a2e4dae699215937a6be881d23fd76dae8b62` |
| `graphics/units/varangian_guard/varangian_guard_idle_dir06_dat4x.png` | DAT idle pose | 148401 | `afc31f1508409aa6332ac74b5f91979dae844d7d` |
| `graphics/units/varangian_guard/varangian_guard_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 148112 | `a0a7448ef98e51183312bd5a093fde2c703ec7ae` |
| `graphics/units/varangian_guard/varangian_guard_idle_dir06.png` | Native idle pose | 4473 | `123322a098a3177af2d62584e4b74bef0187110f` |
| `graphics/units/war_chariot_barrage/icon_transparent.png` | Transparent icon | 80590 | `540e93c21eb6ad01f8ec48b0229aa73d27b3b499` |
| `graphics/units/war_chariot_barrage/icon.png` | Game icon | 77482 | `0bb7879b230af7609929f6e0a3fdb75d55eadc4b` |
| `graphics/units/war_chariot_barrage/war_chariot_barrage_attack_dir06_dat4x.gif` | Attack animation | 4954329 | `20216e612e34cfe0e65ddbc5e44e940342115818` |
| `graphics/units/war_chariot_barrage/war_chariot_barrage_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1040002 | `dd77e7d751b31a38030e79a79440221b984a102b` |
| `graphics/units/war_chariot_barrage/war_chariot_barrage_idle_dir06_dat4x.png` | DAT idle pose | 1043654 | `b8e51001728ca6d98d973428a884972819e64de5` |
| `graphics/units/war_chariot_barrage/war_chariot_barrage_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1039537 | `e28ce5112fa34cf19fa561f3490b1ddca14c9269` |
| `graphics/units/war_chariot_barrage/war_chariot_barrage_idle_dir06.png` | Native idle pose | 35688 | `53d07eb9ce8591ee61fda108f2a193abf60c20c1` |
| `graphics/units/war_chariot_focus_fire/icon_transparent.png` | Transparent icon | 80590 | `540e93c21eb6ad01f8ec48b0229aa73d27b3b499` |
| `graphics/units/war_chariot_focus_fire/icon.png` | Game icon | 77482 | `0bb7879b230af7609929f6e0a3fdb75d55eadc4b` |
| `graphics/units/war_chariot_focus_fire/war_chariot_focus_fire_attack_dir06_dat4x.gif` | Attack animation | 4954329 | `20216e612e34cfe0e65ddbc5e44e940342115818` |
| `graphics/units/war_chariot_focus_fire/war_chariot_focus_fire_idle_dir06_dat4x_blue.png` | Blue DAT idle pose | 1040002 | `dd77e7d751b31a38030e79a79440221b984a102b` |
| `graphics/units/war_chariot_focus_fire/war_chariot_focus_fire_idle_dir06_dat4x.png` | DAT idle pose | 1043654 | `b8e51001728ca6d98d973428a884972819e64de5` |
| `graphics/units/war_chariot_focus_fire/war_chariot_focus_fire_idle_dir06_ultrasharp4x.png` | UltraSharp idle pose | 1039537 | `e28ce5112fa34cf19fa561f3490b1ddca14c9269` |
| `graphics/units/war_chariot_focus_fire/war_chariot_focus_fire_idle_dir06.png` | Native idle pose | 35688 | `53d07eb9ce8591ee61fda108f2a193abf60c20c1` |

# Tiger Cavalry and Xianbei Raider Shorts

Recorded scenario weighted unit cost: food + wood + gold, excluding upgrades. Infantry follows game class; cavalry is melee combat cavalry (siege excluded); archers includes Archer and Cavalry Archer classes. Gunpowder and throwing units do not enter the archer category. Winners come from archived real-game HP/ownership, not simulation.

Twenty selected recordings rendered at 1080 x 1920 / 60 fps. Original game audio/music is retained as AAC. The source is raw gameplay with the approved civilization panels and gRPC unit HP queues. Melee/ranged fights carry the Hussars note.

Converted units keep their original portraits and move to the new owner; grids expand to accommodate conversions. Videos end at main-army elimination, including the last conversion. Tiger Flaming Camel timing was verified using dense HP-bar sampling (148 bars, 73 frames, speed 2.0).

| Subject | Opponent | Cost | Result | Selection |
|---|---|---:|---|---|
| Elite Tiger Cavalry | Elite Huskarl | 110 | WIN | Most expensive infantry defeated |
| Elite Tiger Cavalry | Flemish Militia | 55 | LOSS | Cheapest infantry loss |
| Elite Tiger Cavalry | Elite Cataphract | 145 | WIN | Most expensive melee cavalry defeated |
| Elite Tiger Cavalry | Elite Magyar Huszar | 80 | LOSS | Cheapest melee cavalry loss |
| Elite Tiger Cavalry | Elite War Wagon | 260 | WIN | Most expensive archer defeated, including mounted archers |
| Elite Tiger Cavalry | Elite Blackwood Archer | 40 | LOSS | Cheapest archer loss |
| Elite Tiger Cavalry | Missionary | 100 | LOSS | Conversion victory |
| Elite Tiger Cavalry | Flaming Camel | 105 | LOSS | Explosive anti-cavalry battle |
| Elite Tiger Cavalry | Elite War Elephant | 255 | LOSS | The most expensive melee cavalry opponent |
| Elite Tiger Cavalry | Elite Ghulam | 75 | WIN | Pass-through infantry attack |
| Xianbei Raider | Elite Teutonic Knight | 115 | WIN | Most expensive infantry defeated |
| Xianbei Raider | Flemish Militia | 55 | LOSS | Cheapest infantry loss |
| Xianbei Raider | Elite Cataphract | 145 | WIN | Most expensive melee cavalry defeated |
| Xianbei Raider | Elite Magyar Huszar | 80 | LOSS | Cheapest melee cavalry loss |
| Xianbei Raider | Elite Plumed Archer | 110 | WIN | Most expensive archer defeated |
| Xianbei Raider | Elite Blackwood Archer | 40 | LOSS | Cheapest archer loss |
| Xianbei Raider | Missionary | 100 | LOSS | Conversion victory |
| Xianbei Raider | Flaming Camel | 105 | LOSS | Explosive anti-cavalry battle |
| Xianbei Raider | Elite Tiger Cavalry | 140 | LOSS | Wei unique-unit rivalry |
| Xianbei Raider | Houfnice | 450 | WIN | Charged arrows against heavy siege |

Xianbei: all 73 recordings and overlays are complete. The full compilation includes the existing intro and every matchup; it passed full-file decoding and is ready for review (41 minutes 22 seconds, 74 chapters). 72 five-seed batches finished, but Missionary conversion is unsupported; Flaming Camel failed at a no-live-owner terminal state. Therefore 71 supported comparisons are available, and analysis is not fully complete.

Local artifacts: `aoe2x/js_simulation/calibration/lab/shorts/selected-20/index.html`, `selection.json`, per-video `manifest.json` and `validation.json`. Compilation: `lab/compilations/xianbei-unique-units/final/`.

Rebuild from the repository root with the video virtual environment and PYTHONPATH set to apps/video and the repository root: run apps/video/render_selected_shorts.py --selection aoe2x/js_simulation/calibration/lab/shorts/selected-20/selection.json --workers 2. Cache reuse requires matching renderer and source fingerprints. Each output is fully decoded and checked for video dimensions and an audio stream. The full compilation is built by apps/video/build_xianbei_compilation.py.

# Cavalier comparison: selection, intro evidence and capture

Approved September 15, 2026: **Bulgarians, Poles, Burmese, Sicilians**, in that
display order. Each faces all 74 approved unique-unit roster entries individually
using standard Golden scenarios. There are 296 captures, interleaved by opponent
so four-way comparisons become available early. Player 2 is always the Cavalier;
player 1 follows player 3's civilization. Existing authored ranged/melee Hussar
buffers are retained. No custom combat-stat triggers are needed.

## Why these four (retain for the intro)

- **Bulgarians: sustained damage.** Stirrups gives 16 attack every 1.35 game
  seconds, versus a fully upgraded Malian Cavalier's 19 every 1.8 seconds. Malian
  Farimba adds five attack, but missing Blast Furnace leaves a net three-point
  advantage over the standard 16. Bulgarian throughput leads at low/moderate
  armor; Malians can lead against high armor. These are alternatives, not
  interchangeable outcomes. Roman Comitatenses gives a five-point opening charge
  with a 20-second recharge; its sustained contribution is much smaller.
- **Poles: numbers.** Szlachta Privileges reduces the actual price to 60 food,
  30 gold. Missing Plate Barding Armor leaves 4 melee/4 pierce armor, versus the
  usual 5/6. This is the largest numerical advantage among the three candidates.
  Berbers' stronger armor means their winners cannot simply be inferred from Poles.
- **Burmese: anti-archer specialist.** Manipur Cavalry supplies four bonus damage
  against Archer armor class 15. Ordinary melee/pierce armor does not reduce this
  separate damage component, but matching bonus armor/resistance can. The effect
  includes many mounted archers and gunpowder units, not all ranged attackers.
- **Sicilians: durability.** Hauberk gives +1 melee/+2 pierce armor, reaching 6/8,
  plus the current reference's 40% reduction to incoming bonus damage. Their
  extra ordinary armor matters even when the opponent has no anti-cavalry bonus.

### Damage-per-second comparison

Idealized uninterrupted combat, fully upgraded, against ordinary melee armor;
movement, retargeting, attack windup, overkill, special defenses and charge opening
burst are excluded. This table explains selection; it is not a simulated outcome.

| Enemy melee armor | Bulgarian | Malian | Roman approximate long-run |
|---:|---:|---:|---:|
| 0 | 11.85 | 10.56 | 9.14 |
| 3 | 9.63 | 8.89 | 7.47 |
| 5 | 8.15 | 7.78 | 6.36 |
| 7 | 6.67 | 6.67 | 5.25 |
| 10 | 4.44 | 5.00 | 3.58 |

Bulgarian = max(1,16-armor)/1.35; Malian = max(1,19-armor)/1.8.
The displayed Roman approximation is max(1,16-armor)/1.8 + 5/20. Actual charge
release timing changes the average; do not present it as a measured exact DPS.
Do not say one unit has higher DPS against every opponent.

### Numerical-advantage comparison

Under [the approved balance policy](BALANCE_POLICY.md), comparison food discounts
are half effective, gold discounts fully effective, and score is comparison cost
times military population. The lower score gets 27 units; the other count is
27 sqrt(lower/higher), rounded half up. No 5,000-resource ceiling applies.

| Candidate | Actual food/gold | Comparison cost | Population | Score | Generic Cavaliers facing 27 |
|---|---:|---:|---:|---:|---:|
| Poles | 60 / 30 | 90 | 1 | 90 | 22 |
| Georgians (documented population effect) | 60 / 75 | 135 | 0.8 | 108 | 24 |
| Berbers | 48 / 60 | 114 | 1 | 114 | 25 |

Georgian 0.8 is the published Aznauri Cavalry effect. Our reference table still
lists population 1 and the base-population catalog generator does not evaluate
that technology. Georgians were not selected; verify/extend that extractor before
ever capturing them. Do not silently use population 1 or this assumption as a
captured-data claim. All four selected Cavaliers have installed base population 1
and no relevant population-changing technology.

### Manipur coverage in this opponent roster

Archer-class entries: Composite Bowman; both Ratha modes; Camel Archer; Genitour;
Longbowman; Arambai; Chu Ko Nu; Kipchak; Genoese Crossbowman; Grenadier; War Wagon;
Bolas Rider; Plumed Archer; Mangudai; Guecha Warrior; Conquistador; Blackwood Archer;
Janissary; Rattan Archer; Imperial Skirmisher; Xianbei Raider; Fire Archer.
Both Ratha modes retain Archer armor; Bengali bonus resistance reduces four to
three bonus damage. Examples without Archer armor: Throwing Axeman, Gbeto,
Mameluke, Organ Gun, War Chariot, Ballista Elephant, Hussite Wagon, Mounted Trebuchet.
Use armor class 15, never a blanket ranged-unit test.

Source: `data/golden/aoe2_reference.db` Imperial rows, including final attack,
reload, armor, cost, charge and armor-class fields; installed DAT cost-effect audit.
Published cross-checks: [Cavalier](https://ageofempires.fandom.com/wiki/Cavalier),
[Comitatenses](https://ageofempires.fandom.com/wiki/Comitatenses),
[Aznauri Cavalry](https://ageofempires.fandom.com/wiki/Aznauri_Cavalry),
[Hauberk introduction](https://www.ageofempires.com/news/aoeiide-update-51737/).
Use the installed-data snapshot for the captured game version if online balance changes.

## Capture and storage

Preparation: `apps/video/prepare_cavalier_comparison.py` audits append-only
identities, uses the current episode scaffold for requests, independently checks
every plan and freezes catalogs/stats in `data/local/cavalier-comparison`.
Never regenerate catalogs or this manifest during capture.

```powershell
$env:PYTHONPATH='apps/video;.'
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONUTF8='1'
$env:AOE2_RESOURCE_GUARD_STATUS='C:/dev/aoe2/aoe2_matchup/data/local/capture-render-governor/status.json'
apps/video/.venv/Scripts/python.exe apps/video/run_champi_comparison_capture.py --work data/local/cavalier-comparison
```

Only one recorder can hold the game's capture lock. The existing resume worker
skips verified captures, generates ten-match reports, performs temperature checks
and archives verified raw MP4/frames pairs to `D:/AoE2 Renders/cavalier-<civ>`.
SHA-256 verification precedes deleting redundant local media; compact `run.json`
preserves planning, capture and timing metadata. Failed jobs remain explicit.
Captured counts, opening HP, termination and exports must pass existing checks.

The concurrent Champi render is controlled by `capture_render_governor.py`, started
with its inspected renderer PID. It sets BelowNormal priority and half-CPU affinity,
samples load every five seconds, and suspends only the render tree after two high
samples (>80% CPU, >=80% memory, or <4 GiB free). It resumes after three samples
below 65% CPU, below 73% memory and >=5 GiB free, unless thermally paused. Persistent
pressure requests a wait between captures; it never pauses a live battle for load.
This is a sustained-load target, not a promise against instantaneous CPU spikes.
The existing 90 C CPU/85 C GPU temperature guard remains active every 15 minutes.
CPU temperature telemetry is currently stale/unavailable; do not claim it is verified.

No narration generation, render, Taildrop, or YouTube publication is authorized by
this capture command. The selection narrative above is reserved for a later intro.

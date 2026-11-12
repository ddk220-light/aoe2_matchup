# Army economics review: unit research (upgrade packages, costs, research times)

Reviewer dimension: the technologies needed to field each fully-upgraded Imperial unit, their per-civilization
cost and research time, and how the dataset turns them into "common", "exclusive" and headline research costs.
Dataset reviewed: branch `origin/matchup-timings` at commit 829c65bec (`data/golden/army_context.db`, its
source review database and the compiler/runtime code). Review only: nothing in the dataset was changed.

## Summary for the owner

**Verdict: mostly trustworthy, but there are specific gaps to fix before release.** The research numbers the
dataset has are correct. Some technologies are missing, and the way research enters the headline leaves out most
research spending.

- **The price and research time of each technology are correct.** I rebuilt every civilization's
  technology table independently, using aoe2techtree.net (same game update, 188329) and the civilization
  bonus texts. All 2,700 civilization × technology combinations the dataset uses agreed on cost, refund and
  research time, except 3 research times for one civilization (Mapuche). Every civilization discount and
  free technology was applied correctly. That includes the cheaper or free Blacksmith, Barracks, Stable,
  University and Dock technologies, Spanish +20 gold per technology, Chinese -15%, the free Thumb Ring and
  Parthian Tactics for the Tatars, the free Chemistry and Light Cavalry/Hussar for the Turks, and the free
  Conscription for the Vietnamese. Faster-research bonuses such as Conscription, Chivalry, Perfusion, Kasbah,
  the Portuguese +25% and the Bulgarian and Malian team bonuses were also applied correctly.
- **Which technologies each civilization can research matches the game.** The only exception is the
  **Winged Hussar upgrade** (600 food, 800 gold), which is missing for Poles and Lithuanians.
- **The arithmetic is correct.** I recomputed the research totals for all 1,031 unit profiles and the
  common/exclusive comparison for 365 sampled matchups (every civilization at least 8 times, every unit
  class). Every number matched, apart from the same Mapuche research-time difference.
- **Errors found: 7 missing technologies, which affect 17 unit profiles.** Winged Hussar is missing for 2 units.
  Six unique technologies that affect units are never added to any unit's package: Hamask (Danes infantry),
  Shield Wall (Saxons infantry), Ordo Cavalry (Khitans cavalry), Coiled Serpent Array (Shu Halberdier and White
  Feather Guard), Butalmapu (Mapuche Elite Kona) and Red Cliffs Tactics (Wu Demolition Ships). The game
  hardcodes their effects, so the extraction could not see them; it listed them as "needs review" and they were
  never reviewed. When both armies would share the missing technology, the headline is too low by
  **33–78 villager-minutes per side (8–37%)**. One example is Poles Winged Hussar vs Lithuanians Winged Hussar.
  For every other matchup, these units' exclusive and full research figures are too low by the same amount.
- **Two questionable additions:** Crenellations, a Teutonic castle technology (600 food, 400 stone), and Aznauri
  Cavalry, which only changes population space (550 food, 250 gold), are counted as combat upgrades for 7 units.
- **Biggest conceptual issue:** the headline counts only technologies that **both** armies research. In 20,000
  random matchups, more than half had no shared technology at all. The headline then ignores all research
  spending, including unit-line upgrades, Elite unique-unit upgrades and unique technologies. Paladin vs
  Halberdier is an example: about 4,600 vs about 2,700 weighted resources of research are left out of the score.

**Counts** (one row per compared number in `research-comparison.csv`): **56,076 compared numbers; 55,836
confirmed; 36 wrong; 204 not verifiable**. "Not verifiable" covers the deliberately excluded age-ups, one hidden
free technology, a few unit scopes that only the game engine knows, and 7 questionable additions. The 36 wrong
numbers come from 8 distinct problems (7 missing technologies and 1 research-route timing issue), including
their knock-on headline rows.

## Method and sources

Two independent sources were compared against the dataset. Each compared number was given a verdict.

| Source | What it gave | Version |
|---|---|---|
| A. aoe2techtree.net machine-readable data: `https://aoe2techtree.net/data/data.json` and `https://aoe2techtree.net/data/locales/en/strings.json` | Base cost and research time of every technology and unit-line upgrade; each civ's tech tree; each civ's bonus text | Site footer: "Age of Empires II DE Update 188329" (data.json last-modified 27 Oct 2026). Same patch the DAT contains, so differences cannot be explained by version. |
| A'. Hand-coded civ rules (`scripts/indep.py` in the scratch folder) | Per-civ discounts, free techs, work-rate and research-speed multipliers, coded from the civ texts above and checked on the AoE wiki | Wiki pages fetched 12 Nov 2026 |
| B. Raw DAT technology definitions in the restored review DB (`research_raw_technologies` / `research_raw_effects`) and the main repo's `data/golden/aoe2_reference_simulation.db` (`ref_techs_applied`, built from an independent extraction) | Base cost and time cross-check; which stat-changing techs each civ-unit receives | Same DAT for raw; the main-repo DB uses the repo's own extraction |
| Wiki (ageofempires.fandom.com) | Pages: Conscription (Age of Empires II), Careening, Carvel Hull, Siphons, Shipwright, Butalmapu, Kona, Bolas Rider, Curare, Red Cliffs Tactics, Shield Wall, Ordo Cavalry, Coiled Serpent Array; civ pages Danes, Tupi, Poles, Italians, Spanish, Chinese, Portuguese, Mapuche, Shu, Turks, Bulgarians, Burgundians, Dravidians, Khitans, Jurchens | Mostly current. Carvel Hull and Red Cliffs Tactics costs on the wiki are older than the DAT and aoe2techtree; treated as version differences. Liquipedia was not needed. |
| Earlier attempt, branch `origin/aoe2_ai_for_simulation` (`aoe2x/dbgen/investment_cost.py`) | Line-upgrade chain + Ballistics + stat techs with civ discounts (F/W/G only, no stone, no times, no refunds) | 53-civ older reference DB; used only as a context check, not for verdicts |

Steps (all mechanical, scripts in `/tmp/claude-0/-home-user-aoe2-matchup/c64ba011-deb2-5026-8014-2063b1e15df5/scratchpad/review-research/scripts/`):

1. Flattened every unit profile's `military` and `production` research packages from `army_context.db`. That gives
   8,149 unit-tech rows and 2,700 distinct civ × tech pairs (227 tech IDs), joined to the source table
   `research_civilization_upgrades` and the selected `research_research_locations`.
2. **Availability.** Compared each civ's full dataset tech list with the aoe2techtree tree (techs plus the
   unit-upgrade techs of units in the tree): 4,991 civ × tech rows.
3. **Base cost and time.** Compared each of the 2,700 rows with aoe2techtree and the raw DAT.
4. **Civ-adjusted cost, refund and time.** Recomputed independently from A + A' and compared. The time rules
   used: Conscription ×1.33 at Barracks/Archery Range/Stable/Castle/Krepost/Donjon, except Conscription itself.
   The wiki confirms Conscription also speeds research. Chivalry ×1.4, Perfusion ×2, Kasbah ×1.25 and Persian
   Dock ×1.2 also applied. Own team bonuses applied: Britons, Goths, Huns, Bulgarians, Malians, Celts and
   Portuguese. Jurchen siege upgrades ×2 and Khitan spear/skirmisher/scout upgrades ×1.15. Free techs take
   0 seconds.
5. **Package membership.** Compared with the main-repo `ref_techs_applied` (independent extraction of
   stat-changing techs). Also checked every civ unique tech that no unit links to, and checked the
   consistency of each unit name across civs.
6. **Unit package totals.** Recomputed upfront, refund, net, workload and count for all 1,031 profiles with the
   independent prices: 14,434 numbers.
7. **Pair comparisons.** 365 deterministic pairs (seed 20261112, 6 draws per civ: same-name opponents,
   same-civ pairs and random pairs, plus 2 per unit class and 10 targeted pairs). Every civ appears at least
   8 times, and all 10 unit classes are covered (infantry, cavalry, archer, cavalry archer, hand cannoneer,
   conquistador, siege, scorpion, packed siege, warship). Compared common IDs, both sides' common and
   exclusive net cost per resource, and common workload with the dataset's own `compare_research`.
8. **Headline impact of missing techs.** Re-evaluated the runtime headline (`select_investment_route` +
   `army_investment`, 20 units, compiled labor prices) with the missing technology added to the common set.

## Errors found

| # | Civ / units | Dataset | Correct | Evidence | Impact on headline (villager-minutes) |
|---|---|---|---|---|---|
| 1 | **Poles, Lithuanians: Winged Hussar** | Upgrade tech 786 is absent from the civ tech table, so the Winged Hussar package stops at Light Cavalry | Winged Hussar upgrade, Stable, 60 s base (45.1 s with Conscription). Poles pay 300F + 800G (-50% food bonus); Lithuanians pay 600F + 800G | aoe2techtree `unit_upgrades[1707]` = tech 786; raw DAT tech 786 (600F/800G, Stable); main-repo ref DB charges it | Poles vs Lithuanians WH: Poles 199.5 → 262.5 (+31.6%), Lithuanians 213.9 → 292.1 (+36.5%). Saving changes from 6.7% to 10.1%. Exclusive and full packages of every Winged Hussar matchup are too low by about 63/78 villager-minutes. |
| 2 | **Danes: Champion, Halberdier, Elite Jomsviking, Elite Varangian Guard** | Hamask (Castle, 250F + 450G) missing | Include it: "Infantry deal more damage as they lose HP" | aoe2techtree text; main-repo ref DB applies tech 1484 to these 4 units; DAT effect is an engine flag (resource 33 = 30) left as `player_resource_or_special_command_scope_needs_review` | Danes Champion vs Danes Halberdier: +37.0 per side (17–19%). +37 to the exclusive package elsewhere. |
| 3 | **Saxons: Champion, Halberdier, Elite Hearth Troop, Elite Varangian Guard** | Shield Wall (Castle, 525F + 475G) missing | Include it: infantry gain armor when massed | aoe2techtree; wiki "Shield Wall"; main-repo ref DB; same engine-flag pattern (resource 33 = 31) | Saxons Champion vs Saxons Hearth Troop: +50.5 per side (10–30%) |
| 4 | **Khitans: Hussar, Elite Steppe Lancer, Heavy Camel Rider** | Ordo Cavalry (Castle, 600F + 300G) missing | Include it for non-projectile cavalry | wiki "Ordo Cavalry" ("Non-projectile cavalry regenerate…"); engine flag (resource 33 = 3). Mounted Trebuchet and Heavy Cavalry Archer are excluded as projectile units. | Khitans Hussar vs Khitans Steppe Lancer: +44.9 per side (19–23%) |
| 5 | **Shu: Halberdier, Elite White Feather Guard** | Coiled Serpent Array (Castle, 350F + 300G) missing | Include it | aoe2techtree; wiki; engine flag (resource 33 = 6) | Shu Halberdier vs Shu WFG: +33.1 per side (8–23%) |
| 6 | **Mapuche: Elite Kona** | Butalmapu (Castle, 500F + 450G) missing; Kona price not discounted (65F + 40G) | Butalmapu: "Team **Castle unique units** and Bolas Riders cost -15%". Kona is the Mapuche Castle UU, so Elite Kona costs about 55F + 34G and Butalmapu belongs in its package. | wiki "Butalmapu", "Kona" (Building = Castle); DAT changes only Bolas Rider IDs 2569/2571 explicitly. The Castle-UU part is an engine flag (resource 33 = 51). | Research: Kona mirrors miss 500F + 450G per side. **Price: about -15% per Kona.** This is a unit-price error; it belongs to the production reviewer but is caused by the same research gap. |
| 7 | **Wu: Heavy Demolition Ship** | Red Cliffs Tactics (Castle, 400F + 250G per DAT/aoe2techtree) missing | Include it: "Demolition Ships and Fire Archers deal fire damage" | aoe2techtree; wiki (older cost 350F/300G); the dataset links it to Fire Archer only | Small; naval mirrors only |
| 8 | **Mapuche: Pikeman, Halberdier, Elite Skirmisher (research time only)** | Researched at a Settlement: 35 / 50 / 50 s | 26.3 / 37.6 / 37.6 s at Barracks or Archery Range with Conscription | The research route picks the cheapest building, and Conscription does not speed up Settlements | None on cost or headline. Only the research workload (+12.4 s) is affected. |

Total missing research for these 17 profiles is 250–1,100 resources each (≈33–78 villager-minutes). Errors
2–7 have one root cause. Unique technologies whose effect is hardcoded in the game engine (DAT "resource 33"
flags) were left as `unit_upgrade_candidates`. The runtime never reviewed them; the source README says to review
them before treating a package as exhaustive. Of the 17 such flagged technologies in civ trees, 6 affect field
units and are missing (errors 2–7). Curare and Butalmapu's Bolas part are already linked. The rest (Atheism,
Bimaristan, Stronghold, First Crusade, Cuman Mercenaries, Paper Money, Vineyards, Tuntian, Kasbah/Flemish
handled elsewhere) are reasonably excluded.

### Questionable inclusions (not counted as errors)

- **Crenellations** (Teutons, 600F + 400S): linked to Teutonic Knight, Champion and Halberdier because it lets
  garrisoned infantry shoot from Castles. It has no effect in a field battle, yet it adds 600F + 400S (1,800
  weighted) to Teuton infantry mirror headlines.
- **Aznauri Cavalry** (Georgians, 550F + 250G): only reduces population space. It is linked to Cavalier, Hussar,
  Heavy Cavalry Archer and Monaspa.
- Data-derived links that look odd but come from DAT attributes: archer Blacksmith/University techs on
  Elite Hearth Troop; Husbandry and barding on War Chariot; Lamellar Armor on Khitan Fire Lancer. Marked
  not-verifiable.

### Confirmed correct (highlights)

- Base costs and times: 2,700/2,700 match aoe2techtree and the raw DAT. The exception is the hidden free
  "Champi Scout" tech, which aoe2techtree does not list.
- Free techs, each confirmed at 0 cost and 0 s: Bulgarian militia line; Ethiopian Pikeman; Korean archer armor;
  Magyar melee attack; Malay infantry armor; Slav Arson/Gambesons; Tatar Thumb Ring/Parthian Tactics; Turkish
  Chemistry, Light Cavalry and Hussar; Vietnamese Conscription; Wu Careening/Dry Dock.
- Discounts: Bulgarians (Blacksmith/Siege Workshop -50% food), Burgundians (Stable -50%), Chinese (-15% on
  every tech), Danes (Barracks/Siege Workshop -66% gold), Dravidians (Barracks -50%), Italians (Dock/University
  -25%), Jurchens (-75% wood and ×2 speed on Heavy Scorpion, Heavy Rocket Cart and Siege Engineers; also on the
  capped/siege ram, which have no wood), Khitans (Heavy Cavalry Archer -50%), Poles (Bloodlines and Light
  Cavalry -50% food), Shu (archery techs -25%; the DAT list excludes Elite Skirmisher, which the text leaves
  ambiguous), Spanish (Blacksmith gold-free and +20 gold refund on all 51 techs), Tupi (Archery Range/Barracks
  -50% food, including Champi and Ibirapema upgrades), Turks (Elite Cannon Galleon -50%; the wiki confirms
  Artillery and Elite Janissary are not discounted).
- Naval techs: Careening, Dry Dock, Shipwright, Carvel Hull, Clinker Construction, Siphons and Incendiaries are
  researched at the University (since The Last Chieftains, per the wiki), so the Italian discount applies to
  them and the Persian Dock speed does not.
- Common = intersection of deduplicated technology IDs. Free techs stay in the set (for example, Magyar vs Turk
  Hussar shares Forging and other techs while Magyars pay 0). Every number in the 365 pairs matched, apart from
  the Mapuche route time.

## Per-civilization research differences (for the UI)

Weighted net = food + wood + 1.5 × gold + 3 × stone, from the dataset's military package, with Spanish refunds
deducted. The dataset values were confirmed independently, except the missing techs listed above. "Full
Blacksmith set" covers the civ's available Blacksmith techs at Imperial pricing.

| Civ | Research discounts / free techs (verified) | Research speed vs. base (all civs: Barracks/Range/Stable/Castle ×1.33 from Conscription; civ figures below already include it) | Full Blacksmith set, weighted net | Typical military packages (weighted net F+W+1.5G+3S) | Notable missing techs |
|---|---|---|---|---|---|
| Armenians | — | Conscription only | 4,988 (14 techs; no-bonus 4,988) | Champion: 5,632; Halberdier: 4,995; Arbalester: 4,688; Cavalier: 2,988; Light Cavalry: 2,462; Cavalry Archer: 3,838 | Plate Barding, Thumb Ring, Parthian, Paladin, Hussar, HCA, Siege Onager, Siege Engineers |
| Aztecs | — | Conscription only | 3,738 (11 techs; no-bonus 3,738) | Champion: 6,058; Pikeman: 4,220; Arbalester: 4,062 | Ring Armor, Plate Barding, Bloodlines, Husbandry, Thumb Ring, Parthian, Halberdier, Paladin, Cavalier, Hussar, HCA, Heavy Scorpion |
| Bengalis | — | Conscription only | 5,112 (14 techs; no-bonus 5,112) | Champion: 3,958; Halberdier: 3,320; Arbalester: 4,688; Light Cavalry: 3,112 | Plate Mail, Thumb Ring, Parthian, Paladin, Cavalier, Hussar, HCA, Siege Onager, Siege Ram |
| Berbers | — | Castle x1.66 (Kasbah) | 5,638 (15 techs; no-bonus 5,638) | Champion: 4,282; Pikeman: 2,645; Crossbowman: 4,262; Cavalier: 3,638; Hussar: 4,512; HCA: 6,038 | Parthian, Arbalester, Halberdier, Paladin, Siege Onager, Siege Ram, Gambesons |
| Bohemians | — | Conscription only | 4,988 (14 techs; no-bonus 4,988) | Champion: 4,282; Halberdier: 3,845; Arbalester: 4,688; Cavalier: 2,688; Light Cavalry: 2,162 | Plate Barding, Bloodlines, Thumb Ring, Parthian, Paladin, Hussar, HCA, Siege Onager, Siege Ram, Gambesons |
| Britons | — | Range x1.46 | 5,638 (15 techs; no-bonus 5,638) | Champion: 4,482; Halberdier: 3,845; Arbalester: 6,112; Cavalier: 3,338; Light Cavalry: 2,812 | Bloodlines, Thumb Ring, Parthian, Paladin, Hussar, HCA, Siege Onager, Siege Ram |
| Bulgarians | free: Long Swordsman, Two-Handed Swordsman, Man-At-Arms; Blacksmith & Siege Workshop -50% food | Blacksmith x1.8 | 3,590 (14 techs; no-bonus 5,012) | 2HS: 3,502; Halberdier: 3,222; Cavalier: 3,640; Hussar: 4,515; HCA: 5,562 | Ring Armor, Arbalester, Champion, Paladin |
| Burgundians | Stable techs -50% | Conscription only | 5,012 (14 techs; no-bonus 5,012) | Champion: 4,282; Halberdier: 3,845; Crossbowman: 3,088; Paladin: 4,100; Hussar: 3,325 | Ring Armor, Bloodlines, Thumb Ring, Parthian, Arbalester, HCA, Siege Onager, Siege Ram, Heavy Scorpion, Siege Engineers, Gambesons |
| Burmese | — | Conscription only | 4,638 (13 techs; no-bonus 4,638) | Champion: 4,482; Halberdier: 3,845; Crossbowman: 2,712; Cavalier: 4,388; Hussar: 5,262; HCA: 5,062 | Ring Armor, Thumb Ring, Arbalester, Paladin, Siege Onager, Siege Ram |
| Byzantines | — | Conscription only | 5,025 (14 techs; no-bonus 5,025) | Champion: 3,870; Halberdier: 3,232; Arbalester: 5,238; Paladin: 5,150; Hussar: 3,600; HCA: 5,738 | Blast Furnace, Bloodlines, Parthian, Siege Onager, Heavy Scorpion, Siege Engineers |
| Celts | — | Siege Workshop x1.2 | 4,388 (13 techs; no-bonus 4,388) | Champion: 4,382; Halberdier: 3,745; Crossbowman: 3,112; Paladin: 5,112; Hussar: 3,562 | Bracer, Plate Barding, Bloodlines, Thumb Ring, Parthian, Arbalester, HCA |
| Chinese | all techs -15% (Imperial price; -5%/-10% if bought in Feudal/Castle) | Conscription only | 4,792 (15 techs; no-bonus 5,638) | Champion: 3,640; Halberdier: 3,268; Arbalester: 4,452; Cavalier: 3,092; Light Cavalry: 2,646; Cavalry Archer: 3,729 | Parthian, Paladin, Hussar, HCA, Siege Onager, Siege Engineers, Gambesons |
| Cumans | — | Conscription only | 5,038 (14 techs; no-bonus 5,038) | Champion: 4,282; Halberdier: 3,845; Crossbowman: 3,662; Paladin: 5,912; Hussar: 4,362; HCA: 5,862 | Bracer, Husbandry, Arbalester, Heavy Scorpion, Siege Engineers, Gambesons |
| Danes | Barracks & Siege Workshop -66% gold | Conscription only | 5,638 (15 techs; no-bonus 5,638) | Champion: 3,809; Halberdier: 3,137; Crossbowman: 4,262; Knight: 2,888; Light Cavalry: 3,112 | Parthian, Arbalester, Paladin, Cavalier, Hussar, HCA |
| Dravidians | Barracks techs -50% | Conscription only | 4,988 (14 techs; no-bonus 4,988) | Champion: 4,785; Halberdier: 4,466; Arbalester: 5,238; Light Cavalry: 3,638 | Plate Barding, Bloodlines, Parthian, Paladin, Cavalier, Hussar, HCA, Siege Ram, Siege Engineers |
| Ethiopians | free: Pikeman | Conscription only | 4,988 (14 techs; no-bonus 4,988) | 2HS: 3,108; Halberdier: 3,550; Arbalester: 5,238; Cavalier: 2,688; Hussar: 3,562; HCA: 5,738 | Plate Barding, Bloodlines, Parthian, Champion, Paladin, Gambesons |
| Franks | — | Stable x1.86 (Chivalry) | 4,412 (13 techs; no-bonus 4,412) | Champion: 4,482; Halberdier: 3,845; Crossbowman: 2,488; Paladin: 5,762; Light Cavalry: 2,812 | Bracer, Ring Armor, Bloodlines, Thumb Ring, Parthian, Arbalester, Hussar, HCA, Siege Onager, Siege Ram |
| Georgians | — | Conscription only | 5,012 (14 techs; no-bonus 5,012) | Champion: 4,482; Halberdier: 3,845; Crossbowman: 3,088; Cavalier: 4,562; Hussar: 5,438; HCA: 6,362 | Ring Armor, Thumb Ring, Arbalester, Paladin |
| Goths | — | Barracks x3.19 (Perfusion+team) | 4,462 (13 techs; no-bonus 4,462) | Champion: 3,645; Halberdier: 3,208; Crossbowman: 3,712; Cavalier: 2,988; Hussar: 3,862; HCA: 5,488 | Plate Barding, Plate Mail, Thumb Ring, Parthian, Arbalester, Paladin, Siege Onager, Siege Ram, Siege Engineers, Gambesons |
| Gurjaras | — | Conscription only | 4,400 (13 techs; no-bonus 4,400) | 2HS: 3,570; Crossbowman: 4,812; Hussar: 5,075 | Ring Armor, Blast Furnace, Parthian, Arbalester, Champion, Halberdier, Paladin, Cavalier, HCA, Siege Onager, Siege Ram, Siege Engineers, Gambesons |
| Hindustanis | — | Conscription only | 5,112 (14 techs; no-bonus 5,112) | Champion: 3,758; Pikeman: 2,120; Crossbowman: 4,262; Hussar: 4,512; HCA: 6,038 | Plate Mail, Parthian, Arbalester, Halberdier, Paladin, Cavalier, Siege Onager, Siege Ram, Heavy Scorpion, Gambesons |
| Huns | — | Stable x1.60 | 4,488 (13 techs; no-bonus 4,488) | 2HS: 2,582; Halberdier: 3,320; Crossbowman: 3,638; Paladin: 6,062; Hussar: 4,512; HCA: 5,988 | Ring Armor, Plate Mail, Arbalester, Champion, Siege Onager, Heavy Scorpion, Siege Engineers, Gambesons |
| Incas | — | Conscription only | 4,362 (12 techs; no-bonus 4,362) | Halberdier: 3,845; Arbalester: 5,238 | Plate Barding, Bloodlines, Husbandry, Parthian, Champion, Paladin, Cavalier, Hussar, HCA, Siege Onager, Gambesons |
| Italians | Dock & University -25% | Conscription only | 5,638 (15 techs; no-bonus 5,638) | Champion: 4,282; Pikeman: 2,645; Arbalester: 4,947; Cavalier: 3,638; Hussar: 4,512 | Parthian, Halberdier, Paladin, HCA, Siege Onager, Siege Ram, Heavy Scorpion, Siege Engineers, Gambesons |
| Japanese | — | Conscription only | 4,988 (14 techs; no-bonus 4,988) | Champion: 4,482; Halberdier: 3,845; Arbalester: 5,238; Cavalier: 2,988; Light Cavalry: 2,462; HCA: 6,612 | Plate Barding, Paladin, Hussar, Siege Onager, Siege Ram |
| Jurchens | siege/fortification -75% wood | siege upgrades & Siege Engineers x2 | 5,112 (14 techs; no-bonus 5,112) | Halberdier: 3,320; Crossbowman: 3,712; Hussar: 4,512; HCA: 5,488 | Plate Mail, Thumb Ring, Parthian, Arbalester, Champion, Paladin, Cavalier, Siege Onager |
| Khitans | Heavy Cav Archer -50% | spear/skirm/scout upgrades x1.15 | 5,025 (14 techs; no-bonus 5,025) | Champion: 4,770; Pikeman: 2,932; Crossbowman: 4,262; Hussar: 3,600; HCA: 5,488 | Blast Furnace, Bloodlines, Arbalester, Halberdier, Paladin, Cavalier, Siege Onager, Heavy Scorpion |
| Khmer | — | Conscription only | 5,112 (14 techs; no-bonus 5,112) | 2HS: 2,482; Halberdier: 3,220; Arbalester: 4,688; Cavalier: 3,638; Hussar: 4,512; HCA: 6,062 | Plate Mail, Thumb Ring, Champion, Paladin, Siege Onager, Gambesons |
| Koreans | free: Padded Archer Armor, Leather Archer Armor, Ring Archer Armor | Conscription only | 3,275 (13 techs; no-bonus 4,375) | Champion: 3,670; Halberdier: 3,232; Arbalester: 4,138; Cavalier: 2,075; Hussar: 2,950; HCA: 4,638 | Plate Barding, Blast Furnace, Bloodlines, Parthian, Paladin, Siege Onager, Siege Ram, Heavy Scorpion, Gambesons |
| Lithuanians | — | Conscription only | 4,500 (13 techs; no-bonus 4,500) | Champion: 3,145; Halberdier: 3,508; Crossbowman: 4,262; Paladin: 5,450; Winged Hussar: 2,500; HCA: 6,038 | Plate Mail, Blast Furnace, Parthian, Arbalester, Siege Onager, Siege Ram, Heavy Scorpion, Siege Engineers, Gambesons |
| Magyars | free: Forging, Iron casting, Blast Furnace | Conscription only | 3,950 (14 techs; no-bonus 5,112) | Champion: 2,495; Halberdier: 2,058; Arbalester: 5,238; Paladin: 4,900; Hussar: 3,350; HCA: 7,812 | Plate Mail, Siege Onager, Siege Ram, Gambesons |
| Malay | free: Scale Mail Armor, Chain Mail Armor, Plate Mail Armor | Conscription only | 3,538 (13 techs; no-bonus 4,512) | 2HS: 3,732; Halberdier: 2,870; Arbalester: 5,238; Cavalier: 2,212; Light Cavalry: 1,688; Cavalry Archer: 4,088 | Plate Barding, Bloodlines, Parthian, Champion, Paladin, Hussar, HCA, Siege Onager, Siege Ram, Gambesons |
| Malians | — | University x1.8 | 4,425 (13 techs; no-bonus 4,425) | Champion: 3,670; Pikeman: 2,032; Arbalester: 4,638; Cavalier: 4,275; Light Cavalry: 3,750; HCA: 5,438 | Bracer, Blast Furnace, Parthian, Halberdier, Paladin, Hussar, Siege Ram, Heavy Scorpion, Siege Engineers, Gambesons |
| Mapuche | — | Conscription only | 3,762 (11 techs; no-bonus 3,762) | Halberdier: 3,745; Crossbowman: 3,112 | Bracer, Plate Barding, Bloodlines, Husbandry, Thumb Ring, Parthian, Arbalester, Champion, Paladin, Cavalier, Hussar, HCA, Siege Onager, Siege Ram, Gambesons |
| Mayans | — | Conscription only | 4,362 (12 techs; no-bonus 4,362) | 2HS: 3,108; Halberdier: 3,845; Arbalester: 5,238 | Plate Barding, Bloodlines, Husbandry, Parthian, Champion, Paladin, Cavalier, Hussar, HCA, Siege Onager, Siege Engineers, Gambesons |
| Mongols | — | Conscription only | 4,362 (13 techs; no-bonus 4,362) | Champion: 4,282; Pikeman: 2,645; Arbalester: 4,612; Cavalier: 2,988; Hussar: 3,862; HCA: 5,988 | Ring Armor, Plate Barding, Halberdier, Paladin, Gambesons |
| Muisca | — | Conscription only | 3,125 (10 techs; no-bonus 3,125) | Pikeman: 1,920; Arbalester: 5,438 | Ring Armor, Plate Barding, Blast Furnace, Bloodlines, Husbandry, Parthian, Champion, Halberdier, Paladin, Cavalier, Hussar, HCA, Siege Ram, Gambesons |
| Persians | — | Dock x1.2 | 5,038 (14 techs; no-bonus 5,038) | Long Swordsman: 2,958; Halberdier: 3,845; Crossbowman: 4,512; Hussar: 4,512; HCA: 6,012 | Bracer, Arbalester, Champion, Paladin, Siege Onager, Siege Engineers |
| Poles | Bloodlines & scout-line upgrades -50% food (Winged Hussar upgrade missing from data) | Conscription only | 4,362 (13 techs; no-bonus 4,362) | Champion: 4,282; Pikeman: 2,645; Arbalester: 4,612; Cavalier: 3,862; Winged Hussar: 3,888 | Ring Armor, Plate Barding, Parthian, Halberdier, Paladin, HCA, Siege Onager, Heavy Scorpion, Gambesons |
| Portuguese | — | all research x1.25 | 5,638 (15 techs; no-bonus 5,638) | Champion: 4,382; Halberdier: 3,745; Arbalester: 5,238; Cavalier: 3,638; Light Cavalry: 3,112 | Parthian, Paladin, Hussar, HCA, Siege Onager, Siege Ram, Heavy Scorpion |
| Romans | — | Conscription only | 4,512 (13 techs; no-bonus 4,512) | Halberdier: 3,208; Crossbowman: 3,112; Cavalier: 5,538; Light Cavalry: 3,112; HCA: 4,888 | Bracer, Plate Mail, Thumb Ring, Parthian, Arbalester, Champion, Paladin, Hussar, Siege Onager, Gambesons |
| Saracens | — | Conscription only | 5,638 (15 techs; no-bonus 5,638) | Champion: 4,482; Pikeman: 2,645; Arbalester: 5,238; Knight: 2,888; Hussar: 4,512; HCA: 6,612 | Halberdier, Paladin, Cavalier, Heavy Scorpion |
| Saxons | — | Conscription only | 4,375 (13 techs; no-bonus 4,375) | Champion: 3,870; Halberdier: 3,232; Arbalester: 5,238; Cavalier: 2,375; Hussar: 3,250 | Plate Barding, Blast Furnace, Parthian, Paladin, HCA, Siege Onager |
| Shu | archery techs at Range/Blacksmith -25% (not Elite Skirmisher) | Conscription only | 4,069 (13 techs; no-bonus 4,625) | Champion: 3,470; Halberdier: 2,832; Arbalester: 5,994; Light Cavalry: 1,800; HCA: 4,631 | Blast Furnace, Bloodlines, Parthian, Paladin, Cavalier, Hussar, Siege Onager, Heavy Scorpion |
| Sicilians | — | Conscription only | 5,012 (14 techs; no-bonus 5,012) | Champion: 4,482; Halberdier: 3,845; Arbalester: 4,062; Cavalier: 5,238; Light Cavalry: 3,112 | Ring Armor, Thumb Ring, Parthian, Paladin, Hussar, HCA |
| Slavs | free: Arson, Gambesons | Conscription only | 5,038 (14 techs; no-bonus 5,038) | Champion: 5,820; Halberdier: 5,382; Crossbowman: 3,112; Cavalier: 3,638; Hussar: 4,512; HCA: 4,888 | Bracer, Thumb Ring, Parthian, Arbalester, Paladin |
| Spanish | Blacksmith no gold; +20 gold refund per tech | Conscription only | 2,645 (15 techs; no-bonus 5,638) | Champion: 3,200; Halberdier: 2,652; Paladin: 4,720; Hussar: 3,170 | Parthian, Arbalester, HCA, Siege Onager, Heavy Scorpion, Siege Engineers |
| Tatars | free: Parthian Tactics, Thumb Ring | Conscription only | 4,762 (13 techs; no-bonus 4,762) | 2HS: 2,232; Halberdier: 2,970; Crossbowman: 3,712; Cavalier: 3,638; Hussar: 5,362; HCA: 6,338 | Plate Mail, Arbalester, Champion, Paladin, Siege Onager, Gambesons |
| Teutons | — | Conscription only | 5,038 (14 techs; no-bonus 5,038) | Champion: 6,282; Halberdier: 5,645; Crossbowman: 3,112; Paladin: 5,912 | Bracer, Husbandry, Thumb Ring, Parthian, Arbalester, Hussar, HCA, Siege Ram |
| Tupi | Range & Barracks techs -50% food | Conscription only | 3,750 (11 techs; no-bonus 3,750) | Halberdier: 2,915; Arbalester: 5,925 | Plate Barding, Blast Furnace, Bloodlines, Husbandry, Thumb Ring, Parthian, Champion, Paladin, Cavalier, Hussar, HCA, Siege Onager, Siege Engineers, Gambesons |
| Turks | free: Chemistry, Light Cavalry, Hussar; Elite Cannon Galleon -50% | Conscription only | 5,638 (15 techs; no-bonus 5,638) | Champion: 4,282; Crossbowman: 3,662; Cavalier: 3,638; Hussar: 2,888; HCA: 6,588 | Arbalester, Halberdier, Paladin, Siege Onager, Siege Engineers, Gambesons |
| Varangians | — | Conscription only | 5,638 (15 techs; no-bonus 5,638) | 2HS: 3,308; Halberdier: 3,845; Crossbowman: 3,712; Cavalier: 4,588; Hussar: 4,512 | Thumb Ring, Parthian, Arbalester, Champion, Paladin, HCA, Siege Onager |
| Vietnamese | free: Conscription | Conscription free | 5,025 (14 techs; no-bonus 5,025) | Champion: 3,670; Halberdier: 3,232; Arbalester: 5,238; Cavalier: 3,025; Light Cavalry: 2,500; HCA: 6,038 | Blast Furnace, Parthian, Paladin, Hussar, Siege Onager, Siege Ram, Heavy Scorpion, Gambesons |
| Vikings | — | Conscription only | 4,988 (14 techs; no-bonus 4,988) | Champion: 5,558; Pikeman: 3,920; Arbalester: 6,088; Cavalier: 2,538; Light Cavalry: 2,012 | Plate Barding, Bloodlines, Husbandry, Thumb Ring, Parthian, Halberdier, Paladin, Hussar, HCA, Siege Onager, Gambesons |
| Wei | — | Conscription only | 4,462 (13 techs; no-bonus 4,462) | 2HS: 2,582; Halberdier: 3,320; Crossbowman: 4,262; Hussar: 5,138 | Plate Barding, Plate Mail, Arbalester, Champion, Paladin, Cavalier, HCA, Siege Onager, Siege Engineers, Gambesons |
| Wu | free: Careening, Dry Dock | Conscription only | 5,012 (14 techs; no-bonus 5,012) | Champion: 4,282; Halberdier: 3,845; Arbalester: 4,062; Hussar: 4,512; Cavalry Archer: 3,212 | Ring Armor, Thumb Ring, Parthian, Paladin, Cavalier, HCA, Siege Onager, Siege Ram, Siege Engineers, Gambesons |

The package totals above already include all available Blacksmith, University, building and unit-line techs for
that unit. The missing technologies from the errors table are **not** included (Winged Hussar, Danish/Saxon
infantry, Khitan cavalry, Shu Halberdier).

## Conceptual issues with the accounting

1. **Only shared technologies enter the headline.** The spec takes the intersection of the two
   armies' technology IDs. Unit-line upgrades (for example Crossbowman → Arbalester), Elite UU upgrades and most
   unique technologies differ between different units. They therefore fall into the "exclusive" packages,
   which are shown but never scored.
   - In 20,000 random unit pairs, the median share of an army's military research that counts as common was
     **0%** (mean 20%). **53%** of the sides had no common research at all.
   - The median absolute difference in *exclusive* research was about 1,530 weighted resources, while the
     median difference in *common* research was 0.
   - Example: Franks Paladin vs Japanese Halberdier. The common Blacksmith set is 1,162 for each side, but the
     exclusive packages are 4,600 vs 2,682 (about 193 vs 112 villager-minutes) and do not affect "which army is
     cheaper".

   In practice the research term only measures civ discounts on shared techs, mostly the Blacksmith. It does
   not measure what it costs to get a unit to full strength.
2. **Imperial pricing for every tech.** Chinese pay -15% even on Feudal-age techs, which in a real game cost
   -5% (Feudal) or -10% (Castle). The difference is small (5–10% of those techs), is documented in the spec, and
   is optimistic for the Chinese only.
3. **Research speed assumes the speed technologies are already researched.** Conscription, Chivalry,
   Perfusion and Kasbah are in the separate "production" package, outside the headline. Their speed-up is
   still applied to every other research time. This is consistent with a "post-Imperial, everything
   researched" view, but the common workload is not what a player sees when starting from scratch. Research
   time is a summed workload, not elapsed time, as the spec says.
4. **Age-ups are excluded** (2,300 food + 1,000 gold for Feudal → Imperial). This is fair because both armies
   need the Imperial Age. However, age-up discounts are lost: Italians -15%, Byzantines -33% for Imperial,
   Muisca -50% gold, and Malay faster ages.
5. **Ballistics and Chemistry are counted for projectile units** (307 and 514 civ-unit profiles; Chemistry also as the gunpowder prerequisite). Ballistics changes
   no stat in the simulator, but it is effectively required in a real game. The previous attempt
   (`investment_cost.py`) made the same choice. This is consistent.
6. **Research is a one-time cost added to a 60-second army.** Shared research weighs the same for 2 units or 27.
   For small armies the research term can dominate the headline.
7. **The research-building choice minimizes building cost** (wood + 2 × stone), which picks Settlements for
   Mapuche. Buildings needed only for research (Castle, University) are listed as infrastructure, not scored.
   This is consistent with the spec.

## Open questions for the owner

1. **Should the headline include the full military research package, not only the shared technologies?**
   Recommendation: yes, or show two numbers ("shared upgrades" and "everything needed to field this unit").
   The current definition leaves out most research and cannot tell a ~5,800-weighted-resource Paladin package from a
   ~3,800 Halberdier package.
2. **Add the 7 missing technologies** (Winged Hussar; Hamask; Shield Wall; Ordo Cavalry; Coiled Serpent Array;
   Butalmapu for Kona, plus the -15% Kona price; Red Cliffs Tactics for Demolition Ships)? Recommendation: yes.
   Add them as a small hand-curated list of unit scopes, because the DAT cannot express them. Make the
   compiler fail if any `unit_upgrade_candidates` row stays unreviewed.
3. **Keep Crenellations and Aznauri Cavalry in combat packages?** Recommendation: move them to an "optional /
   non-combat" list, because neither changes a field fight.
4. **Mapuche research route:** should the Settlement be chosen when it is slower than the Barracks?
   Recommendation: use the building that trains the army, or the fastest one, for research time. Cost is
   unaffected.
5. **Chinese and Spanish timing assumptions** (Imperial -15%; +20 gold refund on every tech). Recommendation:
   keep them, and state in the UI that "all research priced as if bought in the Imperial Age".
6. **Age-up costs:** keep them out of the headline? Recommendation: keep them out (same for both armies), but list
   the civ age-up discounts in the per-civ notes.

## Files

- `docs/army-economics-review/research-comparison.csv`: 56,076 rows (civ, tech_or_unit, field,
  dataset_value, source_A, source_B, verdict, note). Sections: per-civ tech base cost/time and civ-adjusted
  cost/refund/time; tech-tree availability; unit package totals; missing-technology rows; questionable
  inclusions; 365 pair comparisons with headline re-evaluations.
- Scratch, not committed: the scripts `indep.py`, `verify.py` and `make_csv.py` are under
  `/tmp/claude-0/-home-user-aoe2-matchup/c64ba011-deb2-5026-8014-2063b1e15df5/scratchpad/review-research/`, together
  with `online_ref.json` (aoe2techtree extract) and the flattened dataset CSVs.

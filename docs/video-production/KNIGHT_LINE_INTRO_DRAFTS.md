# Paladin and Cavalier intro copy: approved

Approved 2026-09-15, with the owner's final edits incorporated.
Use the established campaign parchment, game font, emblems, unit cards and
sentence-aligned whole-column reveals. No comparison lines for Paladins.
All numbers below are fully upgraded totals from the installed reference snapshot.
Armor is melee/pierce; reload is game seconds. Lithuanian Paladins include the
verified four-relic attack modifier, not a second application on top of 20.
Summaries describe mechanics and intended roles, not uncomputed winner statistics.

## Paladin: page one narration and visible text

The Paladin is the final upgrade of the Knight line for many civilizations,
combining heavy armor, powerful attacks and the speed to reach vulnerable
enemies. It can anchor an army or strike at exposed archers and siege weapons,
but spearmen, camels and monks remain dangerous opponents.

We compare Frankish, Teutonic and Lithuanian Paladins with the Persian Savar,
the Persians' alternative to the Paladin. Each brings a different balance of
health, armor and damage to the same matchups, with army sizes balanced by
resource cost and population efficiency.

## Paladin: page two voiceover, one sentence per reveal

- Franks: Frankish Paladins bring the most health of these four, giving them
  extra staying power across a wide range of fights.
- Teutons: Teutonic Paladins trade movement speed for extra melee armor,
  making them especially resilient against repeated low-damage melee attacks.
- Lithuanians: With four relics, Lithuanian Paladins have the highest attack
  of these four, helping them punch through enemy armor.
- Persians: The Persian Savar combines strong armor and bonus damage against
  archers, trading some health for faster attacks and greater protection.

## Paladin: page two cards

| Civilization | Unit | HP | Attack | Armor | Reload | Speed | Food/gold |
|---|---|---:|---:|---|---:|---:|---|
| Franks | Paladin | 192 | 18 | 5/7 | 1.90 | 1.49 | 60/75 |
| Teutons | Paladin | 180 | 18 | 7/7 | 1.90 | 1.35 | 60/75 |
| Lithuanians | Paladin, four relics | 180 | 20 | 5/7 | 1.90 | 1.49 | 60/75 |
| Persians | Savar | 165 | 18 | 6/8 | 1.80 | 1.49 | 60/75 |

Franks:
- Reminder: More HP.
- Civilization bonus: Cavalry +20% base HP.
- Missing upgrade: Bloodlines (final HP: 192).
- Team bonus: Knight-line +2 line of sight.

Teutons:
- Reminder: +2 melee armor; moves slower.
- Civilization bonus: Stable units +2 melee armor in Imperial Age.
- Missing upgrade: Husbandry (slower movement).
- Team bonus: Greater conversion resistance.

Lithuanians:
- Reminder: +4 relic attack.
- Civilization bonus: +1 attack per garrisoned relic, up to +4.
- Matchup setting: Four relics.
- Missing upgrade: Blast Furnace (-2 attack; final attack with relics: 20).

Persians:
- Reminder: More armor; bonus vs. archers.
- Unique upgrade: Savar replaces Paladin.
- Unit bonus: +2 bonus damage vs. Archer-class units.
- Team bonus: +2 bonus damage vs. Archer-class units.
- Total bonus: 4 bonus damage vs. Archer-class units, before resistance.

## Cavalier: page one narration and visible text

The Cavalier is the Imperial Age upgrade of the Knight, combining mobility,
durability and strong melee attacks. Even without the Paladin upgrade,
civilization bonuses can turn it into a fast attacker, a more affordable army,
or a specialist against particular enemies.

We compare Bulgarian, Polish, Burmese and Sicilian Cavaliers against the same
opponents. These four emphasize attack speed, lower cost, anti-archer damage
and protection, with army sizes balanced by resource cost and population efficiency.

## Cavalier: page two voiceover, one sentence per reveal

- Bulgarians: Bulgarian Cavaliers attack faster, maintaining relentless
  pressure once they reach their targets.
- Poles: Polish Cavaliers trade armor for a much lower gold cost, bringing
  a numbers advantage to these matchups.
- Burmese: Burmese Cavaliers specialize in fighting archers, adding bonus
  damage against many foot archers, mounted archers and gunpowder units.
- Sicilians: Sicilian Cavaliers combine extra armor with reduced incoming
  bonus damage, helping them withstand both ordinary attacks and cavalry counters.

## Cavalier: page two cards

| Civilization | HP | Attack | Armor | Reload | Speed | Food/gold |
|---|---:|---:|---|---:|---:|---|
| Bulgarians | 140 | 16 | 5/6 | 1.35 | 1.49 | 60/75 |
| Poles | 140 | 16 | 4/4 | 1.80 | 1.49 | 60/30 |
| Burmese | 140 | 16 | 5/6 | 1.80 | 1.49 | 60/75 |
| Sicilians | 140 | 16 | 6/8 | 1.80 | 1.49 | 60/75 |

Bulgarians:
- Reminder: Attacks faster.
- Unique tech: Stirrups (33% faster attacks).
- Comparable: Malians and Romans (damage-focused cavalry).

Poles:
- Reminder: Cheaper gold; less armor.
- Unique tech: Szlachta Privileges (60% lower gold cost).
- Missing upgrade: Plate Barding Armor (-1 melee/-2 pierce armor).
- Comparable: Berbers (cheaper cavalry).

Burmese:
- Reminder: Bonus damage vs. archers.
- Unique tech: Manipur Cavalry (4 bonus damage vs. Archer-class units).

Sicilians:
- Reminder: More armor; less bonus damage.
- Unique tech: Hauberk (+1 melee/+2 pierce armor).
- Civilization bonus: 40% less incoming bonus damage.
- Unique tech: First Crusade (greater conversion resistance).

## Editorial constraints and evidence

These production notes are not displayed or narrated. Only Bulgarians
(Malians and Romans) and Poles (Berbers) have comparison lines. Do not add
Persians or Teutons, explanatory comparison caveats, or a "no comparisons"
message to the video.

Archer-class bonus damage is separate from normal attack and is not a blanket
bonus against every ranged unit; bonus armor/resistance still matters. Savar
has 4 total, including its own 2 plus Persian team 2, not 4 plus another 2.
Frankish +20% is applied to base HP; do not multiply a 180-HP Bloodlines Paladin.
No production/economy bonuses or irrelevant technologies belong in these cards.
First Crusade's Serjeant spawn is deliberately excluded; only resistance matters.

Sources:
- `data/golden/aoe2_reference.db`, Imperial `ref_units` rows.
- Installed English `key-value-strings-utf8.txt`, civilization and technology help.
- [Paladin capture and verified relic modifier](PALADIN_COMPARISON.md).
- [Cavalier selection and DPS/cost comparisons](CAVALIER_COMPARISON.md).
- [Official Sicilian 40% balance change](https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-153015/).

## Final short spoken summaries (approved September 15, 2026)

Each civilization gets one spoken sentence, synchronized to its full column reveal. Hold for three seconds after the last sentence. Keep the approved first-page narration and second-page stats/bonus text. Upload both completed episodes privately to @aoe2matchup.

### Paladin

- **Franks:** Frankish Paladins are dependable all-rounders, with extra health that helps them stay in the fight.
- **Teutons:** Teutonic Paladins use extra melee armor to absorb punishment and trade blows, giving them an edge in many close-range fights.
- **Lithuanians:** With four relics, Lithuanian Paladins hit hard enough to dispatch fragile units quickly and punch through heavily armored opponents.
- **Persians:** The Persian Savar excels against ranged armies, combining strong pierce armor with extra damage against archers.

### Cavalier

- **Bulgarians:** Bulgarian Cavaliers excel in many melee fights, using faster attacks to overwhelm their opponents.
- **Poles:** Polish Cavaliers trade armor for a much lower gold cost, bringing larger armies and a few standout melee wins.
- **Burmese:** Burmese Cavaliers are anti-archer specialists, with occasional standout wins such as their victory against Chu Ko Nu.
- **Sicilians:** Sicilian Cavaliers shine against ranged armies and cavalry counters, combining strong armor with reduced incoming bonus damage.

Cavalier subjects remain Bulgarians, Poles, Burmese and Sicilians. The owner considered replacements and decided to retain these four. The one-population-per-unit v2 benchmark applies only to future captures; these two episodes retain their recorded v1 counts.

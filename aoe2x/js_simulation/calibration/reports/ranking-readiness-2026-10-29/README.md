# Ranking readiness and provisional standings

The completed data supports a ranking preview. It cannot be imported directly into the current web app. No simulations, serving-data edits or deployment were performed for this analysis.

The preview gives each agreed opponent equal weight. For each seed, wins receive remaining own HP percentage, losses receive negative remaining opponent HP percentage, and draws receive zero. Average seeds within each opponent, then opponents within each unit. Display score = 50 + half that signed average. Scores are comparable within the same group; 50 is neutral. This is a proposal, not the existing app formula or a finalized scoring decision.

- [All 555 ranked variants](rankings-preview.csv)
- [Per-opponent breakdown](opponent-breakdown.csv)
- [Unit-line leaders](line-leaders.csv)
- [Readiness evidence, provenance and sensitivity](readiness.json)

## Integration gaps

- Choose the final scoring weights and whether mobility needs a separate score.
- Convert consolidated results to the serving battle_scores schema and preserve engine provenance.
- Replace obsolete five-seed/six-opponent/1:1:1 validation with this campaign's actual policy.
- Synchronize reference data and line registry: 44 missing variants, 11 replaced entries, one Tarkan duplicate.
- Update opponent breakdowns, methodology and build/source metadata; keep siege and naval separate.
- Check API and rendered ranking rows before publication.

The current serving snapshot is dated September 4 and tagged build 177723. Its explanation assumes five seeds, six common opponents, 1:1:1 resource weights, normalized role scores, and additional speed/range multipliers. This campaign uses three or ten seeds, different pools per group and weights 1:0.9:1.1. The old infantry composite needs Halberdier and Skirmisher results absent from the approved infantry pool; the old ranged composite needs Paladin results absent from the ranged pool. These missing matchups must not be filled with zero or silently replaced by different opponents. Cavalry has the inputs for its existing final composite, but not the old full breakdown; changing only cavalry's scoring would make the category methods inconsistent.

## Interpretation

This is a standing-combat benchmark with scripted kiting disabled. Mobility, retreat, raiding, conversion vulnerability and real-game micro are not captured as an overall strategic value. The approved count formula balances population against cost rather than equalizing army resource totals: 13 Persian War Elephants face 27 Spanish Halberdiers, with weighted army costs 3,425.5 versus 1,552.5. Heavy-unit leaders are therefore partly an intended consequence of the allocation policy.

The selected dataset contains 6768 original-engine runs and 832 corrected-engine runs. Of 704 directly comparable successful runs, 22 changed winner; median absolute margin change is 2.01 percentage points. This selected sample is not representative of the full roster. Mixing was explicitly authorized; close rankings should be treated as provisional.

Identical-army checks also show sample/side variation: Spanish Champion has a -10.37 signed margin against itself and Spanish Paladin +10.14. Three consistent initial winners do not establish a stable true win probability. This is a reason to avoid claiming tiny rank differences are decisive, not a request to rerun the campaign.

## Infantry

| Rank | Civilization | Unit | Score |
|---:|---|---|---:|
| 1 | Teutons | Elite Teutonic Knight | 83.9 |
| 2 | Incas | Elite Kamayuk | 81.6 |
| 3 | Khitans | Elite Liao Dao | 69.6 |
| 4 | Muisca | Elite Temple Guard | 69.5 |
| 5 | Khitans | Elite Fire Lancer | 68.5 |
| 6 | Aztecs | Elite Jaguar Warrior | 67.5 |
| 7 | Armenians | Champion | 65.5 |
| 8 | Danes | Elite Jomsviking | 64.6 |
| 9 | Koreans | Elite Fire Lancer | 63.3 |
| 10 | Jurchens | Elite Fire Lancer | 63.2 |
| 11 | Varangians | Elite Varangian Guard | 62.9 |
| 12 | Sicilians | Elite Serjeant | 62.5 |
| 13 | Vikings | Champion | 62.1 |
| 14 | Dravidians | Elite Urumi Swordsman | 61.5 |
| 15 | Chinese | Elite Fire Lancer | 61.4 |
| 16 | Vikings | Elite Berserk | 60.3 |
| 17 | Vikings | Elite Varangian Guard | 60.0 |
| 18 | Bulgarians | Two-Handed Swordsman | 59.7 |
| 19 | Japanese | Elite Samurai | 59.5 |
| 20 | Dravidians | Champion | 59.0 |

## Ranged

| Rank | Civilization | Unit | Score |
|---:|---|---|---:|
| 1 | Khmer | Elite Ballista Elephant | 92.1 |
| 2 | Dravidians | Elite Elephant Archer | 89.1 |
| 3 | Gurjaras | Elite Elephant Archer | 87.2 |
| 4 | Bengalis | Elite Elephant Archer | 86.1 |
| 5 | Koreans | Elite War Wagon | 85.8 |
| 6 | Bohemians | Elite Hussite Wagon | 85.4 |
| 7 | Saracens | Elite Mameluke | 84.8 |
| 8 | Celts | Heavy Scorpion | 81.2 |
| 9 | Varangians | Elite Jarl | 79.9 |
| 10 | Romans | Heavy Scorpion | 79.5 |
| 11 | Jurchens | Grenadier | 77.9 |
| 12 | Bengalis | Elite Ratha (Ranged) | 77.5 |
| 13 | Teutons | Heavy Scorpion | 71.5 |
| 14 | Magyars | Heavy Cavalry Archer | 71.4 |
| 15 | Turks | Heavy Cavalry Archer | 70.0 |
| 16 | Japanese | Heavy Cavalry Archer | 68.7 |
| 17 | Portuguese | Elite Organ Gun | 67.4 |
| 18 | Berbers | Elite Camel Archer | 66.9 |
| 19 | Slavs | Heavy Scorpion | 66.9 |
| 20 | Spanish | Elite Conquistador | 66.0 |

## Cavalry

| Rank | Civilization | Unit | Score |
|---:|---|---|---:|
| 1 | Persians | Elite War Elephant | 90.4 |
| 2 | Bengalis | Elite Battle Elephant | 82.0 |
| 3 | Burmese | Elite Battle Elephant | 80.8 |
| 4 | Vietnamese | Elite Battle Elephant | 79.6 |
| 5 | Khmer | Elite Battle Elephant | 78.9 |
| 6 | Malay | Elite Battle Elephant | 76.6 |
| 7 | Bulgarians | Elite Konnik | 74.1 |
| 8 | Lithuanians | Elite Leitis | 72.6 |
| 9 | Teutons | Paladin | 70.5 |
| 10 | Slavs | Elite Boyar | 70.2 |
| 11 | Bengalis | Elite Ratha (Melee) | 68.9 |
| 12 | Lithuanians | Paladin | 68.1 |
| 13 | Franks | Paladin | 68.0 |
| 14 | Persians | Savar | 67.8 |
| 15 | Dravidians | Battle Elephant | 67.7 |
| 16 | Hindustanis | Imperial Camel Rider | 67.2 |
| 17 | Byzantines | Elite Cataphract | 67.1 |
| 18 | Huns | Paladin | 66.2 |
| 18 | Magyars | Paladin | 66.2 |
| 18 | Spanish | Paladin | 66.2 |

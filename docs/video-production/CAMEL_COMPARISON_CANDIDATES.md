# Camel comparison candidates

Reviewed 2026-09-16 against `data/golden/aoe2_reference.db`, Imperial-age Camel Rider line rows. These are reference-database values; before recording, validate the selected variants against the installed game's scenario output, especially regeneration and Royal Heirs. No camel captures were launched during this review.

| Civilization | Variant / reason to include | Fully upgraded HP | Ordinary attack | Melee / pierce armor |
|---|---|---:|---:|---:|
| Hindustanis | Imperial Camel; attacks 20% faster | 160 | 12 | 3 / 4 |
| Gurjaras | 40% more mounted bonus damage in Imperial; Frontier Guards +4 melee armor; Kshatriyas 25% food discount | 140 | 9 | 7 / 4 |
| Berbers | 20% lower stable-unit cost in Imperial; Maghrebi Camels regeneration, 15 HP/minute | 140 | 11 | 3 / 4 |
| Byzantines | 25% lower camel cost; lacks Bloodlines and Blast Furnace | 120 | 9 | 3 / 4 |
| Ethiopians | Royal Heirs: receives 3 less damage from mounted attackers; lacks Bloodlines and Plate Barding Armor | 120 | 11 | 2 / 2 |
| Saracens | 25% more camel HP | 175 | 11 | 3 / 4 |
| Khitans | Ordo Cavalry: regenerates while fighting; reference rate 180 HP/minute (3 HP/second) for this 120-HP camel | 120 | 11 | 3 / 4 |
| Malians | Farimba; 14 ordinary attack after accounting for missing Blast Furnace | 140 | 14 | 3 / 4 |

The reference also contains Persians and Turks as fully upgraded baseline Heavy Camels; Tatars match that baseline on our flat map (hill advantage needs a separate terrain experiment); Mongols lack Plate Barding Armor; Cumans have faster Camel Riders but no Heavy Camel upgrade. These add less to the intended comparison than the eight above.

Suggested two four-civilization groups, preserving the approved overlay layout:

1. Hindustanis / Gurjaras / Malians / Ethiopians: attack and counter-damage variations.
2. Berbers / Byzantines / Saracens / Khitans: discounted numbers, HP, and regeneration.

If only one quartet is wanted, Hindustanis / Gurjaras / Saracens / Khitans covers four especially distinct mechanics, but omits both discount specialists and Royal Heirs.

## Planning rules

Use [BALANCE_POLICY.md](BALANCE_POLICY.md): 27 on the lower-comparison-cost side, geometric ratio, one comparison population per physical unit, no 5,000-resource ceiling. Shared camel food discounts are half-effective in comparison cost; gold discounts remain fully effective. Preserve actual purchase costs separately. Do not reuse historical counts under a new policy label.

Use normal golden templates and established ranged-buffer rules. Confirm the selected camel bonuses in a captured spike before launching a batch. This list is for choosing the roster; it is not a claim that all eight are already capture-ready in the cost catalog.

## Sources

- Local stat extract: `data/local/media-reuse-audit/camel-candidates.json`.
- [Official Khitan civilization page](https://www.ageofempires.com/games/aoeiide/civilizations/khitan/): Ordo Cavalry regenerates HP in combat.
- [Official update 81058](https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-81058/): Royal Heirs damage reduction against mounted units.

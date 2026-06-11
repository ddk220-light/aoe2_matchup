# AoE2 Sprite Catalog

This catalog lists all downloaded sprites for verification. Check that each sprite matches its intended unit/building type.

## Unit Sprites (38 total)

| Name | File | Preview |
|------|------|---------|
| arbalester | units/arbalester.png | ![](units/arbalester.png) |
| archer | units/archer.png | ![](units/archer.png) |
| batteringram | units/batteringram.png | ![](units/batteringram.png) |
| bombardcannon | units/bombardcannon.png | ![](units/bombardcannon.png) |
| cappedram | units/cappedram.jpg | ![](units/cappedram.jpg) |
| cavalier | units/cavalier.png | ![](units/cavalier.png) |
| cavalryarcher | units/cavalryarcher.png | ![](units/cavalryarcher.png) |
| champion | units/champion.png | ![](units/champion.png) |
| crossbowman | units/crossbowman.png | ![](units/crossbowman.png) |
| fireship | units/fireship.jpg | ![](units/fireship.jpg) |
| fishingship | units/fishingship.jpg | ![](units/fishingship.jpg) |
| galleon | units/galleon.png | ![](units/galleon.png) |
| galley | units/galley.png | ![](units/galley.png) |
| halberdier | units/halberdier.png | ![](units/halberdier.png) |
| heavyscorpion | units/heavyscorpion.jpg | ![](units/heavyscorpion.jpg) |
| hussar | units/hussar.png | ![](units/hussar.png) |
| knight | units/knight.png | ![](units/knight.png) |
| lightcavalry | units/lightcavalry.png | ![](units/lightcavalry.png) |
| longswordsman | units/longswordsman.png | ![](units/longswordsman.png) |
| manatarms | units/manatarms.png | ![](units/manatarms.png) |
| mangonel | units/mangonel.png | ![](units/mangonel.png) |
| militia | units/militia.png | ![](units/militia.png) |
| monk | units/monk.png | ![](units/monk.png) |
| onager | units/onager.png | ![](units/onager.png) |
| paladin | units/paladin.png | ![](units/paladin.png) |
| petard | units/petard.png | ![](units/petard.png) |
| pikeman | units/pikeman.png | ![](units/pikeman.png) |
| scorpion | units/scorpion.jpg | ![](units/scorpion.jpg) |
| scoutcavalry | units/scoutcavalry.png | ![](units/scoutcavalry.png) |
| siegeonager | units/siegeonager.png | ![](units/siegeonager.png) |
| siegeram | units/siegeram.jpg | ![](units/siegeram.jpg) |
| skirmisher | units/skirmisher.png | ![](units/skirmisher.png) |
| spearman | units/spearman.png | ![](units/spearman.png) |
| tradecog | units/tradecog.jpg | ![](units/tradecog.jpg) |
| transportship | units/transportship.png | ![](units/transportship.png) |
| trebuchet | units/trebuchet.png | ![](units/trebuchet.png) |
| villager | units/villager.png | ![](units/villager.png) |
| wargalley | units/wargalley.png | ![](units/wargalley.png) |

## Building Sprites (17 total)

| Name | File | Preview |
|------|------|---------|
| archeryrange | buildings/archeryrange.png | ![](buildings/archeryrange.png) |
| barracks | buildings/barracks.png | ![](buildings/barracks.png) |
| blacksmith | buildings/blacksmith.png | ![](buildings/blacksmith.png) |
| bombardtower | buildings/bombardtower.png | ![](buildings/bombardtower.png) |
| castle | buildings/castle.png | ![](buildings/castle.png) |
| farm | buildings/farm.png | ![](buildings/farm.png) |
| house | buildings/house.png | ![](buildings/house.png) |
| lumbercamp | buildings/lumbercamp.png | ![](buildings/lumbercamp.png) |
| market | buildings/market.png | ![](buildings/market.png) |
| mill | buildings/mill.png | ![](buildings/mill.png) |
| miningcamp | buildings/miningcamp.png | ![](buildings/miningcamp.png) |
| monastery | buildings/monastery.png | ![](buildings/monastery.png) |
| siegeworkshop | buildings/siegeworkshop.png | ![](buildings/siegeworkshop.png) |
| stable | buildings/stable.png | ![](buildings/stable.png) |
| towncenter | buildings/towncenter.png | ![](buildings/towncenter.png) |
| university | buildings/university.png | ![](buildings/university.png) |
| watchtower | buildings/watchtower.png | ![](buildings/watchtower.png) |

## Missing Sprites

### Units not found:
- twohandedswordsman
- demolitionship  
- king

### Buildings not found:
- dock
- guardtower
- keep

## Sprite Matching Strategy

**EXACT MATCH ONLY**: Sprites are only used when the unit/building type exactly matches a sprite filename. If no exact match exists, the original geometric shapes are used as fallback.

### Key Sprites (must have)
- `villager` - villager.png
- `archer` - archer.png  
- `knight` - knight.png
- `towncenter` - towncenter.png
- `castle` - castle.png

### No Fallbacks
Units/buildings without exact sprite matches will continue to use geometric shapes:
- Circle for villagers (if no sprite)
- Triangle for military (if no sprite)
- Diamond for buildings (if no sprite)

## Source

Sprites downloaded from: https://github.com/qwyt/aoe2-icon-resources
(Originally scraped from Age of Empires Fandom wiki)

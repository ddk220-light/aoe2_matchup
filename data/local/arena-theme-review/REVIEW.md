# Arena theme review: completed first pass

All 30 drafts were opened and visually inspected in the native scenario editor.
The 30 full-map screenshots in screenshots/ were sent to iphone172 by Taildrop;
the final Mayan and Persian deliveries completed successfully on October 1, 2026.

## Ten biomes, two versions each

Winter, Desert, Jungle, Mangrove, Coastal, Autumn, Blossom Garden, Savannah,
Andean Highlands and Mediterranean. A is Scenic; B adds ruins, roadside details
and worn battlefield terrain. Each keeps the original combat unit positions.

## Ten civilization-inspired drafts

Japanese, Chinese, Vikings, Celts, Byzantines, Saracens, Ethiopians, Incas,
Mayans and Persians. The standards are native decorative assets, not a claim
that each flag is an authentic civilization emblem. Mayan statues use the
civilization-specific native statue graphic with Mayan Gaia. Ethiopian and Inca
landmarks were reduced after visual review to avoid overwhelming the map.

## Files and checks

- scenarios/: complete, editable scenario drafts.
- variants.json and extra-variants.json: generation records and SHA-256 hashes.
- build_biome_variants.py and build_extra_variants.py: reproducible draft builders.
- winter-native-terrain.json / winter-native-gaia.json: editor-created source art.
- screenshots/: the delivered review views.

Goldens remain untouched. Surviving trees retain original coordinates; removals
create the outer clearings. Blocking decorative objects stay outside the combat
corridor. Wildlife receives a Gaia-only zero-speed trigger. Original armies,
AI, diplomacy and patrols remain unchanged. Native editor 1.59 files were not
relabelled: compatible 1.58 derivatives were reconstructed from the Goldens and
extracted scenery, then opened in the game.

For actual Norse captures, prepare_norse_standard_capture.py independently
adapts Winter Scenic to each of the four original Golden families. It validates
combat/AI/diplomacy/camera preservation, hashes its audits, and flattens an extra
mountain boundary row (x+y=21). Review drafts are not replacements for Goldens.

## Official campaign study and winter refinement

Studied two official Viking Sagas scenarios in the running game, using the
user-authorized marco/polo reveal cheats: The Exiled Prince / Blood Under a
Blackened Sky (Stiklestad) and The Hard Ruler / Kings and Cowards. Paused and
inspected riverbanks, a ford, mountain shelves, a waterfall, and woodland edges.
Six reference screenshots are in campaign-study/. The packed .gpv campaign
archives were not parsed; these observations come from native game views.

Applied lessons to `Winter Campaign Study - Mountain and Glade.aoe2scenario`:

- Join rocks with exposed rocky terrain and smaller rubble at their bases.
- Put the waterfall between cliff faces, connecting the upper water to a
  lower stream with wet gravel, stones and sparse vegetation along the bank.
- Mix green and snowy conifers with patchy snow, leaf litter and exposed grass.
- Keep the wildlife glade open, with plants clustered along its irregular edge.

`build_campaign_winter.py` reproduces this review draft. `campaign-study/winter-draft.json`
records its hash, placements and geometry checks. It retains 97 of the original
147 tree coordinates, adds no tree coordinates, preserves combat units, keeps
the protected corridor flat, and places new blocking props outside that corridor.
The Goldens and frozen capture templates remain untouched. The draft was opened
and visually reviewed in the native editor; no production battle was rerun.

Native visual revisions replaced the isolated waterfall with a connected rock
formation and changed an orange rock to snow-covered rock. A restricted 0..3
tree-frame experiment made the forest excessively bare and was reverted.

Delivered `screenshots/Winter-Campaign-Study-Full.png` and
`screenshots/Winter-Campaign-Study-Detail.png` to iphone172 by Taildrop; command
completed successfully (exit 0). The closer view intentionally crops the map's
far tips to make the landscaping readable. This is a review draft, not user
approval of a new capture template.

## Detailed battlefield and community scenario research

The separate `Winter Campaign Study - Detailed Battlefield.aoe2scenario`
adds a worn, partly snow-covered road and small nonblocking details inside the
arena. The clean Mountain and Glade version is retained. Full and close native
screenshots were sent to iphone172 successfully.

Four community campaigns were downloaded through the game, nine scenario files
were parsed, and four representative maps were opened in the native editor.
Twelve reference screenshots document paths, cliff bases, frozen streams,
shorelines and woodland edges. See
[the community study](campaign-study/COMMUNITY_STUDY.md) for sources, coverage,
file inventories, visual lessons and the final draft's checks.

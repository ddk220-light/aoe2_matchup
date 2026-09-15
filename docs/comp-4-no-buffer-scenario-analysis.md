# Comp 4 No Buffer: scenario analysis

Inspected the owner's updated `comp_4_no_buffer.aoe2scenario`, saved September 13, 2026 at 23:07:57 PDT. SHA-256: `c38252f1f99a156ae97247b685268e804c9b7e4395491b06b84b1f34b4723753`.

Source: `C:/Users/ddk22/Games/Age of Empires 2 DE/76561198690498042/resources/_common/scenario/comp_4_no_buffer.aoe2scenario`. This is a read-only inspection of the saved scenario, not an in-game execution. Parsed evidence is in `data/local/comp4-no-buffer-analysis/`, including the scenario dump and embedded AI scripts.

## Intended arrangement

The scenario appears designed for **four simultaneous, separate 8-versus-8 comparisons** in one recording. It retains the familiar 16×16 arena, divided into four compartments by a two-tile-wide cross of forest/bush terrain at columns 7–8 and rows 7–8. All terrain is level. The battle areas use dirt terrain with peripheral vegetation. Actual path isolation and camera framing still need an in-game check.

The following are the unit types physically saved in the editor. Runtime upgrades should be checked from the game frames before calling their resulting stats fully upgraded.

| Map-coordinate compartment | Main army | Opposing army | Mutual enemies |
| --- | --- | --- | --- |
| Low x, low y | P1: 8 Elite Champi Warriors, Incas, blue | P5: 8 Composite Bowmen, Armenians, red | P1 ↔ P5 |
| High x, low y | P2: 8 Elite Champi Warriors, Mapuche, green | P6: 8 Composite Bowmen, Armenians, red | P2 ↔ P6 |
| Low x, high y | P3: 8 Elite Champi Warriors, Muisca, yellow | P7: 8 Composite Bowmen, Armenians, red | P3 ↔ P7 |
| High x, high y | P4: 8 Elite Champi Warriors, Tupi, purple | P8: 8 Composite Bowmen, Armenians, red | P4 ↔ P8 |

Each army is arranged as four columns by two rows, for 64 combat units total. P1 also owns two map revealers and two invisible support objects. There are no Scout Cavalry, Hussars or other buffer units. P4 is a full combat army in this layout.

All eight players are active and start in Post-Imperial Age with zero food, wood, gold and stone. Population caps are 200; the **eight-unit roster is an authored formation**, not an engine-enforced cap. All Techs is **off**. Consequently the Champi squads under Mapuche, Muisca and Tupi are not equivalent to four identical Inca squads. If these are placeholders, generation must replace both the unit and its owning civilization together.

Players are mutually allied with every other active player except their assigned opponent. Teams are locked, and allied victory is off. Cross-compartment alliances may also share civilization team bonuses; treat that as a runtime validation point when comparing these results with isolated two-player recordings.

## Starting trigger: updated version verified

There is one enabled, non-looping trigger, `Starting`, with no conditions. It contains one camera effect and eight patrol effects. The camera moves Player 1 to **(8, 7)**, matching the centered current Golden camera.

The owner corrected the first two patrol owners from P2/P3 to **P1/P2**. Every patrol now selects all eight intended combat units, with no empty army selection.

| Player | Inclusive source tile rectangle | Patrol destination | Combat units selected |
| --- | --- | --- | ---: |
| P1 | (3,1)–(6,2) | (3,6) | 8 |
| P2 | (9,1)–(12,2) | (12,6) | 8 |
| P5 | (3,5)–(6,6) | (4,1) | 8 |
| P6 | (9,5)–(12,6) | (11,1) | 8 |
| P3 | (3,9)–(6,10) | (3,14) | 8 |
| P4 | (9,9)–(12,10) | (12,14) | 8 |
| P7 | (3,13)–(6,14) | (4,9) | 8 |
| P8 | (9,13)–(12,14) | (11,10) | 8 |

One small geometric asymmetry remains: P8 ends at y=10, whereas a translated copy of P6's order would end at y=9. It selects the correct units and points toward the correct opponent; this is not the earlier wrong-owner bug. Keep it in mind if the intent is four precisely mirrored openings.

All players have the embedded `NoneAi` script, whose only rule disables itself. P1 and P8 are marked human. The army patrols and the game's normal unit behavior drive combat, rather than a full economic AI. There are no research, resource-balancing, timed reinforcement, diplomacy-change, per-pair result or custom end-of-battle triggers. The scenario's global victory setting is Conquest.

## What this would change in AoE2 Lab

This is a promising four-battle template, but should not be substituted directly for the existing Golden files:

1. **Roster generation:** the current layout expects 27 main slots for P2/P3. This layout has eight slots per player across P1–P8. Equal-resource budgeting and civilization-adjusted per-unit costs must be computed separately for each pair; the saved scenario itself only has equal counts.
2. **Player roles:** P1 is now a fighter as well as the recording viewpoint. The current P1 spectator/P2 subject/P3 opponent/P4 buffer assumptions no longer apply. One recording also has one shared game soundtrack; the current “P1 civilization follows P3” convention cannot represent four independent opponent soundtracks.
3. **End detection:** the live end detector currently tracks owners 2 and 3, who are allies here. It must track the four explicit pairs independently, record each pair's terminal HP/ownership, and stop only once all four fights resolve or a timeout is reached. The raw gRPC frame stream can remain the source of truth; the existing two-owner decoder and result format need expansion.
4. **Overlay and editing:** derive four pair timelines from the same capture and frame file. Either display four compact result panels or crop each compartment into its own matchup clip. Existing two-side HP queues and the fixed central Shorts crop cannot be applied unchanged.
5. **Validation:** check each pair's actual spawned unit IDs, HP, costs, upgrades, player colors and ownership; confirm the divider does not create unwanted movement or range interactions. Preserve pair IDs in results and exclude P1's invisible objects/revealers from combat counts.

Relevant implementation entry points: [Golden validation and generation](../aoe2x/lab/live.py), [recording-side metadata](../aoe2x/lab/recording.py), [live gRPC end detection](../aoe2x/grpc/grpc_hp_log.py), [per-unit overlay decoding](../apps/video/overlay/unit_timeline.py), and [vertical Shorts composition](../apps/video/build_vertical_short.py).

No scenario was edited or launched during this analysis, and the new map has not been registered as a production Golden.

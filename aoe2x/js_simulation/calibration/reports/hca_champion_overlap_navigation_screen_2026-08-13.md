# 5 HCA vs 10 Champion overlap/navigation screen

## Scope and source

- Matchup: 5 Saracen Heavy Cavalry Archers (owner 2) vs 10 Chinese Champions (owner 3).
- Viewer navigation: `cohesive`.
- Golden archive: `aoe2_golden_kiting_hcavarchervschampion_2026-08-06.zip`.
- Verified SHA-256: `EB47F418B2D88BFB99D0083CF05DE153B329D531B0E179494DAE1A5CA3D921C5`.
- Tape median: Champion win, 316 Champion HP remaining, 41.08 seconds.
- Only this matchup was executed for this screen.

## Reproduced defect

The initial exclusive-pair implementation produced a deterministic collision deadlock. Champions 9507 and 9509 remained 0.142 tiles apart while idle with live HCA pursuit targets for 10.8 seconds and then 18.2 seconds. Across the run, deeply overlapped pairs accumulated 1,949 stationary pair-ticks. The result flipped to an HCA win with 203 HP.

The movement-boundary trace found two independent causes:

1. When an exclusive transit reservation ended, the ordinary collision solver tried to restore the entire allied envelope in one tick. Equal co-motion inside an inherited overlap was therefore corrected as though it were new penetration.
2. The coarse chase grid treated friendly Champions as static obstacles. It also sometimes marked a legally placed mover's own 0.25-tile start cell as blocked because the cell centre, unlike the exact unit position, lay inside inflated obstacle geometry. In the worst trace, Champion 9509 received a zero raw chase proposal for 38.8 seconds.

## Controlled options

| Option | Result | Duration | Stuck-pair observation | Decision |
|---|---:|---:|---:|---|
| Initial exclusive pair | HCA +203 HP | 57.6 s | 1,949 pair-ticks; 18.2 s longest | Reject |
| Sticky reservation until fully clear | HCA +270 HP | 50.0 s | 3,195 pair-ticks; 26.2 s longest | Reject |
| Inherited overlap, non-sticky reservation | HCA +82 HP | 59.7 s | 454 pair-ticks; 2.0 s longest | Better motion, wrong winner |
| Corrected grid, exclusive pair | Champion +156 HP | 52.3 s | no permanent raw-proposal freeze | Keep experimental only |
| Corrected grid, soft allied collision | Champion +210 HP | 50.0 s | no permanent raw-proposal freeze | Viewer default |

The final exclusive-pair option still moved away from the tape relative to soft allied collision: it reduced remaining Champion HP from 210 to 156 and extended the fight from 50.0 to 52.3 seconds. It also left Champions idle with a far target on 0.88% of live ticks versus 0.02% under soft allied collision.

## Selected physics

- Allied overlap that already exists at the start of a tick may be preserved or reduced, but a new step may not deepen it. This lets a pair co-move out of inherited overlap instead of being mutually pinned.
- The chase A* grid routes around static map geometry and enemy bodies. Friendly crowd bodies remain dynamic and are handled by local avoidance/collision.
- A pursuit planner that is boxed in only by dynamic bodies falls back to live pursuit rather than emitting a permanent stand order.
- A legally placed mover's coarse start cell is cleared for chase planning. If rasterization still cannot represent an exit, chase falls back to continuous movement rather than treating the unit as statically trapped.
- Exclusive pair transit remains available as an explicit engine experiment. New reservations require co-directed movement, release when relative closing stops, and release on reaching the melee engagement envelope. It is not enabled by the viewer default.

## Remaining tape gap

The selected run has the correct winner but remains 106 Champion HP below the tape median and 8.90 seconds longer. This turn intentionally stopped at the navigation/collision defect: no damage, speed, reload, attack-delay, or matchup-specific calibration value was changed.

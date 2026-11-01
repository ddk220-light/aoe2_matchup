# Streaming event-log hash for long civilization fights

The frozen V3 Mapuche Imperial Elite Skirmisher (27) versus Celtic Paladin
(17) fight, matchup `cm_60c2234fc6c6b02543651544` seed 0, remained active
through 2,918.5 simulated seconds at the 1,800-second wall watchdog. Its final
attempt returned from the world simulation at tick 175,193 after 1,851 wall
seconds, then failed while constructing one canonical JSON string for the full
event log: `RangeError: Invalid string length`. It has **no valid saved result**.
The V3 journal and physics source are unchanged.

The isolated branch changes only output hashing. Node now feeds canonical JSON
tokens into SHA-256 in bounded chunks; the world loop, collision rules, combat
calculations, scenario, and event log remain unchanged. The browser keeps its
existing hash path. This is a separately identifiable source version on top of
the ranged-crowding repair, not a modification to the live V3 or V2 campaigns.

Validation: the streamed hash equals the original hash for nested objects,
unicode, sparse arrays, unsupported-value errors, and a 100,000-event synthetic
log. Six completed fight replays across the five scenario families also matched
their saved winner, final-state hash, and event-log hash exactly. The isolated
`diagnose_slow_civ_pair.mjs` completed the long seed under the isolated
collision-repair plus streaming-hash source: Celtic Paladins won at tick
175,254 (2,920.9 simulated seconds), with 11 of 17 surviving and 1,293.5 of
2,720 starting HP remaining. The run took 2,013.7 wall seconds. Its
final-state hash is `bf4af0b3912023ab83f9771339aa4112d78902fdc8ebc503e73f7bc40f20a279`
and event-log hash is `7c7fd690aee9127c8900677dea991f02e42bb7de15173323daf4e6cf69da54eb`.
A second replay confirmed the exact same winner, tick count, final-state hash,
and event-log hash. Its 100-second HP samples show that 26 of 27 skirmishers
die by game second 100; one remains at its full 50 HP until after second 2,900
while slowly damaging Paladins. The event log contains 2,536,676 `blocked`
events, 1,024,647 persistent contact reservations, and 294,829 pursuit
retarget requests. A third replay with position and target samples again
matched the same winner, tick, final-state hash, and event-log hash exactly.
The last skirmisher (9009) remains at (15, 6.0101) from game second 100
through 2,900, alternating attack and reload while its HP stays at 50/50.
The nearest Paladin (9514) remains near (14.768, 5.338), targets that
skirmisher, and is idle over the same interval. The forest fixture places
0.5-radius trees at (15.5, 5.5), (14.5, 6.5), and (15.5, 6.5), creating a
narrow pocket. At the sampled positions, the Chebyshev center separation is
0.672 tiles. The Paladin's 0.4 outline plus the skirmisher's 0.2 outline puts
it within the 0.1-tile engagement envelope (outline gap 0.072), but their
0.25 + 0.2 collision extents leave a 0.222-tile physical gap, beyond the
0.1-tile stop distance required to start a range-zero swing. The Paladin
therefore retains an engagement yet cannot start an attack; trees and crowded
bodies keep it from closing. This geometry explains why one healthy
skirmisher consumes roughly 2,800 extra game seconds while the simulation
logs millions of blocked/contact events. The exact replays establish
determinism, not that the forest-pocket behavior matches the game. A pathing
or scenario change would require separate physics validation and versioning.

All three diagnostic reports are read-only evidence, not frozen campaign
records. The V3 seed remains missing. A future campaign using this output
version must record its runtime hashes, validate evidence provenance, and
handle the remaining long seeds without classifying a timeout as a result.

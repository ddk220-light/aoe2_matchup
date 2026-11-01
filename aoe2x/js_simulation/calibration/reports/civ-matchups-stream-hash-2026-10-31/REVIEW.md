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
retarget requests. A further isolated replay will sample positions and target
state to identify the prolonged movement lock. Neither diagnostic result
belongs in a frozen campaign journal. Any
later campaign using this output version must record its runtime hashes and
validate evidence provenance.

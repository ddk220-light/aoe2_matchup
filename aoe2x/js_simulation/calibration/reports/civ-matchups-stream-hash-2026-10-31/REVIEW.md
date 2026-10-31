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
`diagnose_slow_civ_pair.mjs` job is intended to check whether streaming hashing
allows the long seed to produce a complete result. Its result must not be
inserted into either frozen campaign journal. Any later campaign using this
output version must record its runtime hashes and validate evidence provenance.

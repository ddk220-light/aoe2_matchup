# Exhausted Chu Ko Nu / Mounted Trebuchet context

Diagnostic evidence only; no winner or draw is assigned.

- Context: `mv_9bc2d959cf36c2b00f7ffa75`, Chinese Elite Chu Ko Nu 27 / Khitan Mounted Trebuchet 12, seed 7.
- Frozen V3 source checkpoint: `de8dc8727477a48e26dc128e5eab5dfc27f47cd6`.
- All four prescribed wall limits (180 / 600 / 1800 / 3600 seconds) were exhausted. Final attempt ended at tick 6,303,698 (105,061.6333 game seconds).
- The final fsynced timeline has 120 snapshots. Combat counters and army HP are unchanged from game second 622.500 through 104193.867: one Chu Ko Nu at 41.100000000000506 HP and one Mounted Trebuchet at 45 HP.
- Movement, blocking and route counters continue; the Chu Ko Nu position drifts slightly. The exact pathing/acquisition/minimum-range cause remains unresolved. This does not establish a legitimate draw.
- Completed seeds 0–6 remain preserved. Required seeds 7–9 and the pair exact replay are incomplete, so the entire context stays out of correction exports.

[REVIEW.json](REVIEW.json) binds the original context, immutable source commit, exact journal lines including their newline hashes, and all four closed timeline hashes. The existing runner already records the job as blocked and continues other inventory jobs. No runner was restarted, no simulation or physics was changed, no old winner was copied, and no further retry is authorized. Production remains unchanged.

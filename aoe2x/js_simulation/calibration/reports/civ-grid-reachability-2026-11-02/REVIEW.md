# Reachability precheck experiment

This isolated version rejects an impossible pursuit route using a linear graph
traversal before the original weighted A*. It uses the same complete goal mask,
directed crowd-entry predicate and diagonal-corner checks. Reachable cases still
run the original A*, including its costs, tie breaking and waypoint selection.
Collision precision, stopping distances and attack behavior are unchanged.

All 28 targeted routing tests passed. The first 40 game seconds of the blocked
Kona seed match the frozen V2 final-state hash, event-log hash, outcome and tick
exactly. A completed Kona seed also matches its saved V2 record exactly.

The bounded run took 55.90 wall seconds versus the earlier frozen baseline's
70.10 seconds, a 1.25x ratio on a shared, busy executor. The precheck rejected
1,056 of 1,604 route searches. This is a modest experimental speedup, not a
solution to the forest-pocket combat lock. It is not installed in the live
campaigns and is not yet a certified compatibility source. Do not restart bulk
replay or relabel candidate output as a campaign measurement.

The unsuccessful exact-cache predecessor and its results remain at commit
235d1374. Original frozen campaigns were not modified by either experiment.

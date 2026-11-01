# Isolated patrol-endpoint repair candidate

This branch starts from the V2 collision repair plus the certified streaming
hash implementation. It changes `world.js` so a trigger-issued patrol reverses
between its command destination and each unit's formation origin when an
unengaged unit reaches an endpoint. Combat pursuit still suspends the patrol.
The frozen V3 campaign, V2 replay campaign, saved seeds, and source manifests
are unchanged.

The phase-019 blocked matchup `cm_d9a8fa39591693259171e783` is 27
Ethiopian Two-Handed Swordsmen (a mechanics profile also shared by Mayans)
versus 22 Muisca Elite Guecha Warriors.
Under frozen V3, seed 0 had no result after four wall limits ending at 3,600
seconds / 77,806.9 simulated seconds. The bounded V3 and V2-stream probes
match exactly through tick 6,000 and show 10 swordsmen idle at `(2, 13)` and
one Guecha idle at `(13, 2)`, the opposite patrol destinations. The source
diagnosis is in `GUECHA_PATROL_REVIEW.md` on the parent stream-hash branch.

Under this candidate repair, seeds 0, 1, and 2 all complete as swordsman wins
at ticks 4,627, 5,241, and 5,120. Seed 0 retains 10 survivors and 335 HP;
two independent isolated replays, including one after the final source edit,
matched its winner, ticks, final-state hash, and event-log hash exactly.
These files are **diagnostics only** and are not campaign records.

The patrol-specific test and the focused combat/scenario/collision suite pass
(49 tests, with the exhaustive every-registered-pair test deliberately
excluded). Four sampled previously valid fights span four scenario hashes:
two retain exact final-state and event-log hashes, while two differ. Tupi
Elite Blackwood Archer versus Teuton Paladin changes both hashes but not its
winner, ticks, or survivor HP. Khitan Mounted Trebuchet versus Dane
Halberdier also changes survivor HP (513.43 to 700.20) while retaining the
winner and ticks. V2 controls for both changed fights match frozen V3
exactly, so these differences come from the patrol repair. The repair
therefore **changes physics**, even where the winner stays the same. No
existing V3 or V2 result may be relabeled as a result from this candidate
version.

Before using the candidate for the final table, verify its late-patrol
behavior against independent game evidence, freeze a new source/fixture
manifest, and replay every eligible saved seed into a separate journal.
Then use the new version for missing seeds and future test selection. Keep
all existing V3/V2 records as historical evidence; do not mix their outcomes
with a new-version winner. The phase-015 forest-pocket reach problem is
separate and still needs its own resolution.

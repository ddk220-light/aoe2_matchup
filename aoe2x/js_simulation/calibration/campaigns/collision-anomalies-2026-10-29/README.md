# Collision and pursuit anomalies

These are behavior corrections investigated separately from the exact-preserving
collision optimization. They must not be silently mixed into the frozen ranking
campaign. Original inputs and results remain available on its original branch.

## Blocked attackers stop recovering before they can attack

The baseline Aztec Elite Skirmisher / Turk Cavalier seed 2 has one Skirmisher at
`(13, 8.010102051443365)` and an engaged Cavalier at
`(12.769599742567662, 7.330089732271936)`. Their Chebyshev separation is
`0.6800123191714293` tiles. Outline engagement reach is 0.7 tiles, but the
ordinary range-zero attack-start rule requires collision separation <=0.55.
Terrain and allied bodies prevent the remaining direct approach.

`world.js` suppressed blocked-pursuit recovery as soon as outline reach was met,
although its attack code could not start a swing from that position. The
correction keeps recovery active until the existing attack-start geometry is
satisfied. It changes neither damage nor weapon range nor collision tolerances.
Ranged and range-one attacks keep their existing reach rules; a ready area
charge retains its attack-start exception.

The synthetic regression in `tests/pursuit-attack-position.test.mjs` fails on the
unchanged engine and passes with the correction. Existing blocked-pursuit tests
also pass. The first full Aztec retry finished at 35.4 game seconds / 23.32
processing seconds; the optimization alone still reached its 120-second
processing watchdog after 419.42 game seconds. See
[aztec-recovery-candidate/result.json](aztec-recovery-candidate/result.json).

## A Scorpion overlap loses its collision surface

Burgundian Scorpion / Saracen Hand Cannoneer seed 0 fails on movement tick 836.
Allied bodies 9006 and 9010 are legitimately compressed to about 0.49155 tiles
under a ranged-crowd reservation, versus their full one-tile separation.
At tick 836, body 9010 finishes its attack animation and starts minimum-range
retreat, which ends that ranged-crowd reservation.

Body 9006 already owns a different allied lane (`9006:9008`). The new candidate
for `9006:9010` cannot obtain another lane, so the baseline drops it without
publishing release geometry. The collision solver then sees the existing
overlap as an invalid hard starting overlap and throws.

The correction uses the existing monotonic release rule for an overlapping
candidate denied a deep-contact slot, just as for an expired persistent
reservation. It grants no extra deep slot and no further compression. A
synthetic three-body regression verifies the denied pair releases at its
current separation and increases that separation as the units move apart.

Read-only evidence:

- [Tick-by-tick contact handoff](scorpion-contact/contact-history.json)
- [Exact failing reservation input](scorpion-contact/contact-input.json)
- [Baseline exception and source hashes](scorpion-contact/result.json)

The follow-up validation directory records all 37 pilot replays and retries of
remaining anomalies, including changes in final-state and event hashes. These
corrections can legitimately alter previously completed fights, so any adoption
requires a new ranking dataset version and reevaluation of affected results.

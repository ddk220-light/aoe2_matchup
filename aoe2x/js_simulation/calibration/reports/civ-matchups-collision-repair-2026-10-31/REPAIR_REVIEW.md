# Ranged crowd collision repair, isolated engine version

The frozen civilization campaign hit a repeatable geometry error in Aztec
Scorpion versus Bengali Heavy Scorpion, seed 1. A newly published allied
`ranged-crowd` reservation demanded `0.025` tiles of separation from bodies
only `0.024529046538409816` tiles apart. The old collision solver correctly
rejected that starting geometry. Longer wall limits did not help because all
four attempts failed at the same reference pair.

This branch changes **only** the general ranged-crowd reservation rule. If
the pair is already deeper than the 2.5%-of-body-size compliant core by more
than the old solver's `1e-4` publication slop, the reservation inherits its
current separation. It does not allow that pair to deepen further. Fresh
ingress still faces the core, committed Siege-class bodies retain their
existing obstruction rule, and the collision solver still checks exact final
geometry. Cases inside the former tolerance retain the old reservation.

The targeted three-seed fight now completes: all three seeds are Bengali
wins. Seed 0's final-state hash
`74f7d62fdc3e1305bd6feaec52bc575bc88bcacc4d7e302c8fa45c5b8574b2a4`
and event-log hash
`b78b36cd9c22bdbc9d138353d3ccdaeb8836598d117c79c43aae38953fcb32af`
match the frozen result exactly. The new seeds have these hashes:

| Seed | Winner | Final-state hash | Event-log hash |
| --- | --- | --- | --- |
| 1 | Bengali | `bca38123ba21697590d1e9c33cb85cf61b6876b570f1c7245ae2402498e48fec` | `5d3e2037f64e19101d60608ee6e9bc389959db1b06e15c4d1cb59099b1ffb931` |
| 2 | Bengali | `438b1775e459a21d4ee156f438a5704cc9de35a614f6fc2be6ac11ebbbd37e96` | `1edd5ec7bf18611b76af03287a18cf2f1ba5e0a418c1e99545e64da8e7886293` |

All 64 focused collision, movement, contact-reservation, and ranged-crowd
tests pass. Six completed frozen-engine seeds replayed exactly under the
repair: five representative placement/scenario families and seed 0 of this
Scorpion pair. [The replay manifest](parity.json) records IDs and both source
hashes. This is a limited compatibility check, not proof that every saved
result is interchangeable. The active campaign remains on the frozen engine;
none of these repaired-engine outcomes have been added to its journals or
inference table.

Before this repair contributes to the final civilization table, freeze a new
engine manifest and build a separately versioned dataset. Either replay and
establish exact compatibility for **every** carried completed seed, or rerun
the affected matches under the new engine. Keep source provenance per seed
and do not silently combine engine versions. Continue the current campaign's
unaffected phases while that migration is prepared.

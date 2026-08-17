# Unique-Unit Expansion Design

## Goal

Extend the clean-room JavaScript simulation from the existing fourteen-unit
standard corpus to the Imperial land-combat unique and regional roster, in four
reviewable batches of twenty unit families. Every result must remain sourced
from build 177723 unit data and an explicitly authorized golden archive; tape
evidence may validate mechanics but may not be replaced by old calibration
output or matchup-specific fitting.

## Scope

The expansion covers 63 civilization-unique land-combat unit families and one
selected civilization for each of 17 regional or civilization-specific unit
families. Naval units, heroes, non-attacking monks, campaign-only units,
buildings, and ordinary shared siege units remain outside this phase.

The first batch contains:

1. Elite Longbowman
2. Elite Throwing Axeman
3. Elite Woad Raider
4. Elite Shotel Warrior
5. Elite Gbeto
6. Elite Huskarl
7. Elite Teutonic Knight
8. Elite Boyar
9. Elite Tarkan
10. Elite Genoese Crossbowman
11. Elite Plumed Archer
12. Elite Mangudai
13. Elite Rattan Archer
14. Elite Janissary
15. Elite Conquistador
16. Elite War Wagon
17. Elite Magyar Huszar
18. Elite Keshik
19. Elite Karambit Warrior
20. Warrior Priest, combat only

## Source-of-truth rules

- Build 177723 `data/golden/aoe2_reference.db` and the matching Genie data
  provide fully upgraded statistics, armor classes, attack classes, animation
  timing, projectile properties, movement speed, and collision geometry.
- `aoe2x/dbgen/config_units.py`, `config_combat.py`, and
  `ability_registry.py` are implementation leads, not clean-room tape evidence.
- Old Python and browser engines may supply reusable algorithms, but their
  calibrated constants and approximations are not authoritative.
- Before any tape analysis, the user-designated archive must be SHA-256 hashed,
  copied byte-for-byte into `calibration/source/`, rehashed, and recorded in the
  clean-room manifest.
- A missing or mismatched archive blocks tape comparison, but does not block
  writing tests for data-sourced mechanics fixtures.

## Unit representation

Each selectable unit maps to one immutable mechanics fixture and one registry
row. A registry row names its civilization, Genie master ID, fixture, combat
family, and base purchase cost. The fixture records the exact source of every
field and derives attack delay from the attack animation rather than using the
reference database's rounded delay column.

Ranged unit control is selected by behavior rather than by unit name:

- Mobile ranged units use the existing cohesive Arbalester controller.
- Ranged attacks that deal melee damage still use mobile-ranged navigation; the
  damage-class map alone determines mitigation.
- Siege ranged units do not inherit the mobile-ranged controller unless their
  documented behavior requires it.
- Melee and one-range melee units use the existing engagement and crowding
  policies.

## Corrected mechanics contract

### Warrior Priest

The simulator exposes only the conventional melee combat unit. Healing and
healing orders are outside this phase.

### Ratha

The later Ratha task produces two selectable entries, melee mode and ranged
mode. They share identity only at the catalogue layer; each mode has its own
fixture and fixed combat behavior. Automatic in-fight switching is deferred
unless the authorized tapes demonstrate it.

### Konnik

Mounted death spawns a real dismounted form at the same position. The foot
form's complete fully upgraded stat block is derived through the Bulgarian
infantry technology chain. It receives its own maximum HP, attack and armor
classes, movement, attack animation, reload, collision, and target state.

### Arambai

Accuracy remains the low sourced value (20% regular, 30% elite). It does not
receive Thumb Ring accuracy. A missed projectile follows its physical scatter
path and may deliver full damage when it intersects another target.

### Shotel Warrior

Royal Heirs is modeled as three less incoming damage from mounted attackers,
not generic armor. The attacker-category predicate includes mounted ranged
units.

### Mounted Trebuchet

Ordo Cavalry regeneration is a Khitan technology overlay, not a base-unit
property. It is enabled only when the tape setup includes that technology.

### Gbeto

The Gbeto uses the Arbalester cohesive kiting controller, with timing derived
from its sourced movement speed, reload, and attack delay. Its projectile
delivers melee-class damage.

### Organ Gun

Each projectile in the Elite Organ Gun's six-projectile volley has a real
trajectory and collision test. Projectiles share the current damage profile,
spread using sourced dispersion, and deal full damage when a dispersed path
intersects an enemy. No arbitrary round-robin target assignment is permitted.

### War Chariot

The later War Chariot task produces separate Focus Fire and Spread Fire viewer
entries. Each fixture records bolt count, interval, damage, dispersion,
pass-through, minimum range, target-death behavior, and the Bolt Magazine
effect. The current one-mode repository approximation is not authoritative.

## Regional-unit selection

Exactly one civilization represents each regional family. Prefer a
combat-impacting unique technology or civilization bonus: Mayan Elite Eagle,
Incan Elite Champi, Dravidian Elite Elephant Archer, Italian Condottiero,
Mapuche Slinger, Berber Elite Genitour, Burgundian Flemish Militia, Vietnamese
Imperial Skirmisher, Polish Winged Hussar, Persian Savar, Hindustani Imperial
Camel, Wei Heavy Hei Guang Cavalry, Dravidian Siege Elephant, Jurchen Heavy
Rocket Cart, Bohemian Houfnice, Shu Traction Trebuchet, and Roman Legionary.

## Batch workflow

Each batch is independently reviewable:

1. Inventory the exact golden tape rows and their unit-count ratios.
2. Export and audit build-177723 mechanics fixtures.
3. Add focused failing tests before each behavior change.
4. Port only general, unit, projectile, form, mode, or technology mechanics.
5. Add the twenty unit families to the clean-room viewer.
6. Run the full existing test suite and the standard-unit regression gate.
7. Run five deterministic samples per golden row. Expand only volatile rows,
   to a maximum of 100 samples.
8. Persist every completed simulation immediately through the recoverable
   benchmark runner.
9. Report tape result, simulation median, delta, winner agreement, convergence,
   failures, and direct local/Tailnet viewer links.
10. Stop for review before beginning the next twenty-unit batch.

## Acceptance criteria

- All batch fixtures are reproducible from source data.
- Every new behavior test was observed failing before implementation.
- The full clean-room test suite passes.
- Existing standard-unit mechanics and benchmark outputs do not regress beyond
  predeclared stochastic tolerance.
- Viewer selection, manual counts, equal-resource setup, deterministic seeds,
  and replay telemetry work for every new unit.
- Golden comparisons use only manifested archives and exact tape ratios.
- No opponent-specific rules or force-fitted random variation are added.


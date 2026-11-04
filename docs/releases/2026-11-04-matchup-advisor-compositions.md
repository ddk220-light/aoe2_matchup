# Matchup Advisor: main units and trash complements

Each civilization now gets a main unit and a no-gold sidekick. The main is scored by which enemy threats it counters, rather than its raw number of wins. The sidekick is chosen specifically to cover enemies that beat that main. The remaining analysis shows the three highest-scoring other candidates per civilization, excluding the two picks. Scorpions participate normally; reference-only siege cards without matchup evidence are no longer appended to this short list.

Recommendation policy `threat-coverage-complement-v1` uses the existing saved outcomes and actual civilization-specific gold costs:

```
weight(unit) = 1 if it costs gold, otherwise 0.5
threat(enemy) = weight(enemy) × (1 + sum(weight(our unit) for each unit that enemy beats))
value(our unit) = sum(threat(enemy) for each enemy our unit beats)
sidekick value = sum(threat(enemy) for each main-unit loss the sidekick beats)
```

The baseline `1` keeps ordinary broad coverage useful even when an enemy has no wins. A viable gold unit with the highest value is the main; the best overall unit is the fallback only if no gold unit can win. Score ties use weighted win coverage, then gold status and stable unit names/IDs. Gold Scorpions have weight 1, with no siege discount. No-gold upgrades such as Persian Crossbowmen and Malay Two-Handed Swordsmen are identified from their costs, rather than unit-line names.

The sidekick must be a different unit with zero gold cost. Its decisive coverage of the main's losses comes first, then close results against those losses, then new winning coverage and its general score. Close/equal outcomes never count as wins or covered threats. When no trash counter exists, the cards say so, and remaining threats stay visible. If the selected no-gold option has no wins or relevant close results, it is labelled a trash fallback rather than inventing a counter.

Both main and support cards show costs, named enemy counters, losses and close matchups. The sidekick highlights exactly which main-unit counters it answers. Clicks retain the original individual army-count details; these recommendations do not represent a newly simulated mixed army. The source dataset, outcome classifications, physical contexts, hashes, prediction metadata, unit rankings and engine remain unchanged. All source types continue to use the same public presentation.

Validation:

- Nine model tests cover threat weighting, resource weights, Scorpions, zero-win enemy weights, support priorities, close outcomes, viable gold/fallback selection, the three-candidate limit, reversal/counts and provenance independence.
- A read-only sweep checked all 1,540 civilization pairs / 3,080 sides and all 151,223 displayed matchups. Every side has a gold main, a distinct no-gold support and three distinct remaining candidates. Every highlighted support target is both a main loss and a support win. There are 2,027 covered main-unit threats; gaps remain explicit. Three selected trash supports have no winning matchups; they keep one main-unit threat close, which is not counted as covered.
- Browser checks cover four recommendations, the main/support resource types, support assignments, three alternatives per side, details, selection/deselection, light/dark, source-independent rendering and responsive layouts. Canonical unit icons and the 56-civilization picker are retained.

For example, Danes versus Saxons selects Heavy Mounted Crossbowman (value 32.5) plus Light Cavalry, which covers its Elite Skirmisher counter. Saxons select Champion (31.5) plus Elite Skirmisher to answer Heavy Mounted Crossbowman, while Heavy Scorpion remains an uncovered threat.

# Compact Matchup Advisor

The selected comparison now scrolls directly to the recommendations after both civilizations are chosen. The old matchup-count/settings/scoring banner is removed. The sticky header remains clear of the target; reduced-motion preferences use an immediate scroll, and stale selections cannot schedule a later scroll.

Each civilization has one compact three-section panel:

- Main: unit, costs, score, and icon-only wins/losses/close results.
- Sidekick: unit and only the main-unit threats it beats or holds close. Its unrelated wins, losses, costs, score and explanatory paragraph are removed.
- Add counters: extra unit icons pointing to the remaining threats they beat. Shared counters are grouped to reduce the number of suggested additions. A threat with no winning counter in the table remains explicitly marked “No counter.”

Unit names stay in headings, image alternatives, tooltips, accessible labels and the existing click-through details. They are removed from matchup lists. The three alternatives per civilization use the same compact icon rows, reduced padding and short headings. The original main/sidekick weights, recommendations, saved outcomes, provenance, rankings and simulation runtime are unchanged.

Additional-counter selection considers every other available unit, choosing the addition that covers the highest total remaining threat weight, then the most threats, then the existing value ordering. Every assignment uses a direct winning row against that enemy; close results are not wins. This is a counter map, not a new mixed-army simulation.

Validation:

- Eleven model tests include grouped additions and threats with no winning counter.
- A read-only sweep of all 1,540 civilization pairs / 3,080 sides verified every extra-counter assignment, no duplicated targets, and explicit handling of every remaining threat. It found 971 assigned targets and 1,110 targets with no available winning counter; at most two extra units are needed for any plan's answerable threats.
- Twenty larger-roster/example layout cases at 320×640 and 390×700 fit the full three-section plan below the navigation without horizontal overflow. The tallest measured plan was 425.24px. The Armenian/Aztec example fits in roughly 330–365px per civilization at 390px width.
- Desktop/mobile browser checks cover automatic scrolling, icon-only lists, focused sidekick jobs, direct winning extra counters, three distinct alternatives, selection/deselection, details, light/dark and source-independent presentation.

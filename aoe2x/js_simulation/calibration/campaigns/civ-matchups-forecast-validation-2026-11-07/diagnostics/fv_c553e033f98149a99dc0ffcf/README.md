# Exhausted Bohemian Hussite Wagon / Khitan Mounted Trebuchet seed

Job `fv_c553e033f98149a99dc0ffcf`, seed 1, original counts **27 / 19**, remains unfinished.
The 180/600/1800/3600-wall-second attempts all ended at their watchdogs.
The final attempt ended at tick 1,882,803; its
last fsynced snapshot is earlier, at tick 1,867,634.

All four attempts reproduce the same late positions, HP, actions and targets:
one Hussite Wagon at 62.233333333337754 HP and eight Mounted Trebuchets at
570 combined HP. The final timeline has 119 consecutive
unchanged combat/position snapshots, from game second
196.15 to 31127.233333333334.
Only blocked and pursuit-route-planned event counters increase over those
suffixes. Their exact deltas and all source hashes are in `REVIEW.json`.

This establishes nontermination in the frozen runtime. It does not establish
the precise acquisition/range/routing cause or an actual AoE2 winner or draw.
Only seed 0 was saved; required seeds 1 and 2 and a pair exact replay remain
missing. No partial outcome or diagnostic is imported as a correction.

The source is Git commit `43f129b7852722b4d6c8f87928104b34c98e447f`. Attempt lines, progress timelines,
original context/profile order and counts are bound by exact hashes. No physics,
forecast, inventory, queue control or runtime file was changed. No retry or
campaign restart was performed; the ordinary queue continues with this job
blocked by its exhausted journal record.

Reproduce into a new directory with `python analyze.py --output <new-directory>`.
A separately reviewed recovery decision is required before retrying this case.

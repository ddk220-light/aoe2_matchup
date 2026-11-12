# Controlled DE farming capture inputs

Four generated scenarios are ready for an in-game check. They were parsed back and structurally verified, but have not been run in DE. This Linux workspace has no DE executable.

The selected economy technologies are forced in Dark Age to isolate their effects; this is a laboratory test of the post-Imperial economy parameters, not a normal match. All workers are generic Byzantines.

1. Load a scenario in current DE. Use the standard data set, no mods, no cheats, and fixed 1.7x game speed. Record the exact executable build.
2. Use Player 1; do not assign an AI or issue worker orders. Farms begin native construction at game time 10 seconds after selected upgrades are applied.
3. Record the whole test to at least 22 game-minutes for the two-farm cases, and 25 for the ten-farm post-Imperial case. Keep the game clock visible; save the replay if available.
4. Verify initial farm food, worker carry and speed against the case manifest. Stop comparison if these differ, or if foundation snapping changes the layout.
5. Measure each farm from its actual construction-completion time to depletion. Also capture the first work-spot position, each change of work spot, carried food, drop-off positions and final deposit.
6. Use harvested food (banked plus carried) for fixed-time comparisons. Do not mix this with banked-only food or depletion with final-deposit time.
7. The ten-farm setup is a no-reseeding diagnostic: wood becomes zero at 60 seconds. Compare before depletion, or match this setting in the model.
8. Repeat each two-farm case at least 10 times for an initial distribution. Increase repetitions if the uncertainty of the mean remains above 1%; do not select favorable individual runs.
9. Actual farm-creation, task and gather timestamps must be observed. Trigger scheduling and native construction are not presumed instantaneous or exactly 15 seconds in a live run.

The exact unit references, coordinates, expected values and file hashes are in `capture-manifest.json`. Native construction deliberately avoids guessing how preplaced farms inherit food-capacity upgrades.

# Static stats overlay pilot

The first export is Wei Elite Tiger Cavalry (left) against Armenian Elite Composite Bowman (right). Both panels remain visible throughout the battle. These are starting, fully upgraded Imperial stats, including a fixed full-health portrait bar. They do not consume live gRPC data yet.

`apps/video/overlay/static_stats.py` renders the installed game's `combined` MSDF font atlas, selection-panel parchment, and stat icons, with repository unit portraits. No replacement font or generated artwork is used. Numbers come from `data/golden/aoe2_reference.db`. The CLI deliberately accepts only this pilot pair until more unit-specific effects are implemented.

## Reading the reference panels

| Symbol | Meaning |
| --- | --- |
| Sword / arrow | Melee / pierce attack damage; black `base+upgrade` notation |
| Armor | Melee armor / pierce armor, each with its own base and upgrade |
| Target with arrow | Attack range in tiles; shown for ranged units |
| Circular target without arrow | Blast radius; the Legionary reference's `0.50` is area damage radius |
| Gold chevrons | Reload time in game seconds; smaller means faster attacks |
| Boot | Movement speed in tiles per game second |
| Portrait bar and fraction | Hit points; fixed starting health in this version |

Ranged units can deal melee damage (for example Throwing Axemen), so attack type and attack range must remain separate concepts.

## Pilot matchup annotations

- Tiger Cavalry: attack `13+4`, followed by green `(7 bonus damage)`. The annotation is separate from ordinary attack and technology upgrades.
- Composite Bowman: attack `4+4`, armor `2+3 / 0+4`, range `4+3`. No negative armor annotation or duplicate incoming-damage note is displayed.
- Bonus damage is calculated against its matching bonus armor class, separately from normal melee/pierce armor. No effective-defense penalties are shown. Armor bypass is explained in the unit's effect note.
- Tiger notes: each kill adds 10 current/maximum HP and 1 attack, capped at +40 HP and +4 attack. The numbers remain at starting values in this pilot. See the [Tiger Cavalry mechanics reference](https://ageofempires.fandom.com/wiki/Tiger_Cavalry_%28Age_of_Empires_II%29).
- Composite notes: arrows ignore pierce armor.

## Repeat the export

From the repository root in PowerShell, with FFmpeg available on PATH or discoverable in its WinGet installation:

```powershell
$env:PYTHONPATH='apps/video'
& apps/video/.venv/Scripts/python.exe -m overlay.static_stats 'aoe2x/js_simulation/calibration/lab/runs/tiger_unique_01_armenians_composite/live/run_001'
```

The `static-stats-overlay` subfolder holds `panels.png`, provenance and calculated modifiers in `stats.json`, `render.log`, and `battle-with-stats.mp4`. The source battle, raw recording and gRPC frames stay intact. The export uses two encoder threads to limit contention with the background campaign.

Validation: source and export both contain 1,488 frames at 2560×1440, 60 fps, with a 24.957-second container duration. Copied AAC audio has the same SHA-256 digest. Exported first, middle and last frames decode successfully; the rendered middle frame was visually checked for text fit and placement. Numeric regression checks cover bonus damage, armor-class offsets and separation from ordinary attack and armor.

Revision: titles have increased top and side padding. The Starting stats label is omitted. Tiger notes retain only per-kill growth and maximum growth.

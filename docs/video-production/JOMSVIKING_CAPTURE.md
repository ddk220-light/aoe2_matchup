# Jomsviking release capture

Approved 2026-09-22: record Elite Jomsviking (Danes) against the 76 other
entries in the 77-unit unique land roster. This is a raw-only campaign.
No overlay, simulator, narration, compilation or upload worker is launched.

The installed Viking Sagas release supplies master IDs 2712 (Elite
Jomsviking), 2706 (Elite Hearth Troop), and 2709 (Elite Jarl). The scenario
parser predates the release, so `build_run.py` supplies these IDs and the
exact civilization tokens from the installed `civilizations.json`:
`DANES-CIV`, `SAXONS-CIV`, `VARANGIANS-CIV`. Jarl is ranged; Hearth Troop
uses its primary melee classification. Post-Imperial game research supplies
the actual upgrades and unique abilities.

## Prices and counts

Use the [approved balance policy](BALANCE_POLICY.md): food 1, wood 0.9,
gold 1.1, full civilization discounts, one comparison population per
physical unit, 27 cheaper units and rounded geometric cost balancing for
the expensive side, with no resource ceiling. The ranged side's actual
fielded weighted cost determines 5–10 extra Hussars in mixed matchups.

The release costs are 65 food + 15 gold for Jomsviking, 80 wood + 35 gold
for Hearth Troop before the maximum 20% Saxon discount (64 wood + 28 gold),
and 75 food + 55 gold for Jarl. Saxon pricing assumes four Town Centers
and/or Castles for the maximum discount, as requested. This changes the
cost-based army allocation; it does not place buildings in the arena.

`prepare_jomsviking_capture.py` independently checks all 77 purchase costs
against an isolated extraction of the installed release and preserves the
previous catalogs under the campaign's `provenance/`. Changed prices are
listed in `release-cost-audit.json`. Historical plans and recordings are
never rewritten or rerun by this preparation.

Price derivation includes starting civilization tech-tree modifiers before
age and unique technologies. The Mayan initial 10% archer discount must not
be omitted: Elite Plumed Archers cost 39 wood + 39 gold after the full chain.
Saxons' conditional castle/TC foot-soldier discount applies to both Hearth
Troops and Barracks-trained Varangian Guards. The earlier exclusion of Guards
was incorrect; see [the Saxon correction](VARANGIAN_GUARD_CAPTURE.md#september-27-saxon-correction).

The 2026-09-22 audit compared all 76 frozen Jomsviking plans with the new DAT
prices and actual recorded starting counts. The nine release price changes
were already present; 75 captures remain valid. Only Plumed Archer requires
26 Jomsvikings versus 27 archers (six Hussars), replacing 27 versus 26.
The user explicitly requested an in-place replacement, so that single local
job is recreated with the same ID and `live/run_001` path. The campaign's
`replacement-receipt.json` retains the old plan/checksums and the reuse audit;
it does not retain a second copy of the video. Existing valid recordings and
their original plans remain intact, even though the global catalog hash changes.

## Jarl follow-on

Prepare once with `prepare_jomsviking_capture.py --subject jarl`. The campaign
is `data/local/jarl-capture`; resume using the same supervisor command below
with that work path. Elite Jarl is always player 2, Varangians, master 2709.
The 77-unit roster yields 76 opponents: exclude Jarl itself and include
Jomsviking. Use ranged classification, the current weighted prices and the
fielded-army Hussar rule. The Armenian ranged-versus-ranged pilot expects
105 opening HP per Jarl after the installed Post-Imperial technologies.
Start this campaign only after the Jomsviking replacement is verified.

## Hearth Troop follow-on

After Jarl completes, prepare the final DLC unique-unit campaign with
`prepare_jomsviking_capture.py --subject hearth-troop`. Its work directory is
`data/local/hearth-troop-capture`; use the same capture supervisor with that
path. Elite Hearth Troop is player 2, Saxons, master 2706, primary melee.
Exclude itself from the same 77-unit roster to produce 76 matchups. Retain
the maximum Saxon discount (64 wood + 28 gold), current weighted counts and
scaled ranged-side Hussars. The pilot gates the full raw-only queue on its
recorded opening counts and the expected 85 HP per Hearth Troop.

## Start and resume

The prepared campaign is `data/local/jomsviking-capture`. Preparation is
one-time and refuses to overwrite a frozen manifest. Resume with:

```powershell
$env:PYTHONPATH='apps/video;.'
$env:PYTHONUTF8='1'
apps/video/.venv/Scripts/python.exe -u apps/video/run_camel_comparison_capture.py --work data/local/jomsviking-capture
```

Start only one supervisor, with the game ready in the Scenario Editor or
Load Scenario screen. The recorder mutex prevents simultaneous campaigns.
The first Armenian Composite Bowman capture gates the remainder on verified
counts, raw data and 75 opening HP per Elite Jomsviking. Its verified result
is reused in the full pass, not recorded twice.

`supervisor.json`, `pilot-validation.json`, `capture/status.json` and the
worker logs record progress. The inner recorder writes ten-match reports.
The existing supervisor checks temperatures every 15 minutes and storage
every ten seconds; it stops at a battle boundary below 8 GiB free. Missing
CPU sensor readings must be reported as unavailable, never as a safe CPU
temperature. No external disk is required for the current local campaign.

## Retained outputs

Each status row identifies its run directory beneath
`aoe2x/js_simulation/calibration/lab/runs/jomsviking_v3_unique_*`.
Each run retains the raw recording, clean `battle.mp4`, `frames.bin`,
decoded HP, timing, generated scenario, plan and checksum inventory.
Frozen catalogs, exact counts, cost weights and Hussar scaling evidence
are retained with the campaign. These provide the sources for future
overlays. Apply [recording retention](RECORDING_RETENTION.md) only after a
completed bundle has been verified; do not delete active files.

Stop at a safe boundary by creating `data/local/jomsviking-capture/PAUSE`
(during the pilot use `pilot-phase/PAUSE`). Do not remove a thermal pause
without following its documented resume checks.

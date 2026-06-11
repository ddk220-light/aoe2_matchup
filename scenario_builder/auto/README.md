# auto/ — hands-off matchup-video automation

> **Windows is the supported platform** — see [README_WINDOWS.md](README_WINDOWS.md)
> for setup, env vars and the current run commands. Parts of this document describe
> the original macOS pipeline and are kept for reference; the macOS backend is frozen.

Turn a list of unit matchups into titled battle videos with **one command**. For
each matchup it builds a scenario from a golden template, drives the AoE2:DE
Scenario Editor to record a real AI-vs-AI fight, and composes a titled video —
then dismisses the end screen and moves to the next matchup. No human watches the
screen: every "what screen am I on?" decision is made by screenshot OCR.

```
intro stat card  ->  real fight footage (+ game audio)  ->  "Battle Complete" recap card
```

Verified: a 2-matchup batch produced both videos fully hands-off, ~4 min each.

---

## Run it

```bash
cd scenario_builder
.venv/bin/python -m auto.batch_matchups \
  --matchup "Muisca:elite_temple_guard_muisca:Aztecs:elite_jaguar_warrior_aztecs:Elite Temple Guard vs Jaguar Warrior (Muisca vs Aztecs)" \
  --matchup "Muisca:elite_temple_guard_muisca:Vikings:elite_berserk_vikings:Elite Temple Guard vs Berserk (Muisca vs Vikings)"
```

Each `--matchup` is **`CIV1:slug1:CIV2:slug2:Display Name`** (repeat for as many as
you want):

- **CIV** — title-case civ name (`Muisca`, `Aztecs`, `Vikings`).
- **slug** — the reference-DB unit slug. Unique units carry a civ suffix
  (`elite_temple_guard_muisca`); standard units are the plain fully-upgraded name
  (`paladin`, `halberdier`). The slug must exist in `webapp/aoe2_reference.db`.
- **Display Name** — becomes the output filename *and* the on-screen title; may
  contain spaces, parentheses, etc.

Output mp4s go to `--copy-to` (default
`/Volumes/Orchid/AOEII_videos/3kResMatchUpVideos`). Progress streams to
`--log` (default `/tmp/auto_matchup.log`); `tail -f` it to watch.

**Validate before running** — resolves every matchup's units and checks the
environment, then exits without touching the game:

```bash
.venv/bin/python -m auto.batch_matchups --dry-run --matchup "..." --matchup "..."
```

### Sweep a unit against the unique-unit list

`unique_units.json` (built by `python -m auto.build_unique_list`) is the ordered,
validated list of all 62 land unique units, alphabetical by civ. Run a fixed unit
against a slice of it without typing each matchup:

```bash
.venv/bin/python -m auto.batch_matchups \
  --list auto/unique_units.json --slice 1:5 \
  --opponent "Muisca:elite_temple_guard_muisca" \
  --join "Temple Guard vs Uniques 01-05.mp4"
```

- `--list` + `--opponent CIV:slug` → builds `opponent vs <each list entry>` matchups.
- `--slice A:B` → 1-based inclusive range into the list (`1:5` = the first five).
- `--join NAME.mp4` → after all fights, concatenate every clip into **one** combined
  video (the individual clips are not copied out in join mode — only the joined one).

### Equal-count vs equal-resources

By default each side fields `--unit-cap` units (30v30). Add **`--resources`** for an
equal-*resource* fight instead: the cheaper unit is capped at `--unit-cap`, and the
pricier unit's count is the most that fits the **same total cost** (food + wood +
gold, taken from the reference DB). E.g. Temple Guard (115) vs Jaguar Warrior (90)
→ **23 vs 30**. The computed counts show in the dry-run plan and the on-screen title.

### On-screen unit count

Every generated scenario carries a looping **Live readout** trigger that prints
`UnitA: N   vs   UnitB: M` at the top of the screen, refreshed each second, so the
surviving counts are visible *in the video* (not OCR-extracted). Trigger effects
can't sum army HP, so this shows unit **count** only — individual HP bars are
already visible in-game.

### Prerequisites (one-time)

Run from a **Terminal** (Terminal.app / iTerm) that has BOTH, in System Settings →
Privacy & Security:
- **Screen Recording** — for `screencapture` + the SCK recorder, and
- **Accessibility** — for scripted clicks via cliclick (*separate* from Screen
  Recording).

TCC is read at process **launch** — restart the Terminal after enabling either.
Leave AoE2:DE open in the **Scenario Editor**, frontmost. While a batch runs,
**don't touch the mouse/keyboard or switch apps** — the recorder captures whatever
is on screen and the clicks need AoE2 frontmost.

---

## How one matchup runs

```
run_matchup()
  1. build_run     generate the run scenario from the golden jungle template
                   (swap in the two units + civs, retarget the win/stop triggers,
                   add a force-engage, NO tech research) -> /tmp/aoe2_matchup_runs/
  2. stage         clear the game's scenario folder, drop in that ONE file named
                   "Matchup Run" (so the Load list has a single entry — no search)
  3. navigate      Load -> click the one row -> Load -> editor -> Menu  (no typing)
  4. record        SCK recorder: video + system audio, 1920x1248@60
  5. Test          fight begins; recorder captures from the countdown
  6. watch         poll the screen; the "You have been defeated!" banner = the end
  7. stop          SIGINT -> the .mov finalizes at the end
  8. dismiss       click "Continue" -> back to a clean Scenario Editor
  9. compose       intro card -> real fight (+audio) -> recap card  (NO OCR)
 10. copy          drop the finished mp4 in --copy-to
```

`batch_matchups` loops this over the queue. Between runs the game is already back
in the editor (step 8), so the next run rebuilds + re-stages its scenario and
navigates fresh — handling the "save changes?" prompt from the still-loaded prior
scenario.

Each click is located by **label text** (`vision.find_text`), so coordinates adapt
to resolution; only the end-detection is adaptive (fights vary in length).

---

## Modules

- **`vision.py`** — `screencapture` + rapidocr. `detect_state()` (which screen),
  `detect_end()` (the defeat/victory banner), `find_text(img, label, region)` →
  the button's logical point (screencapture is Retina 2×, so point = pixel ÷ 2).
- **`input_driver.py`** — cliclick wrappers. `click()` is the game-safe pattern
  (move → settle → discrete down/up; a warp+click is dropped by the engine).
  `accessibility_ok()` checks the injection grant.
- **`record_until_end.py`** — the recorder lifecycle (`start_recorder`,
  `watch_until_end`, `stop_recorder`) and the **no-OCR compose** (`compose_recap`:
  intro + real fight + recap card, no survivor counts).
- **`orchestrate_matchup.py`** — `run_matchup()` (one full matchup, with the
  navigation + the `return_to_editor()` dismiss) and a single-matchup CLI.
- **`batch_matchups.py`** — the queue runner: pre-flight validation → loop
  `run_matchup` → summary.
- **`../build_run.py`** — turns the golden template into a per-run scenario.
- **`../prepare_template.py`** — one-time: strip the tech-research triggers from a
  freshly-edited template (post-imperial armies are already fully upgraded).

## The golden template

`templates/template_landscape_jungle.aoe2scenario` (committed to the repo) is the
hand-decorated jungle battlefield: map, terrain, Gaia eye-candy, both player slots,
the two 30-unit armies in formation, the scout keep-alive, and the control triggers
(diplomacy / camera / title / 3-2-1 countdown / win conditions). It is **tech-free**.

`build_run` keeps all of that and only **retargets** it per run: sets each fighting
player's civ, swaps each army's unit type, rewrites the triggers that referenced the
old unit ids, refreshes the title, and adds a force-engage so the armies collide.
Generated scenarios live in `/tmp/aoe2_matchup_runs/`; the automation stages the
active one into the game folder.

## The cards are templates too

`overlay/render_card.py` holds the HTML card templates; `overlay/overlay_data.py`
`get_unit_card(civ, slug)` auto-fills them from repo data —
`webapp/aoe2_reference.db` (fully-upgraded stats, cost, attack bonuses, unique
techs) + the local icon PNGs. Nothing per-matchup is hand-authored.

## Robustness

- **Pre-flight** — `batch_matchups` resolves every matchup's units (card data *and*
  scenario unit id) and checks the environment (template, recorder binary,
  copy-to volume, Accessibility) **before** touching the game. A typo aborts the
  whole batch up front instead of wasting good runs. `--dry-run` does only this.
- **Isolation** — a failing matchup is logged and **skipped**; the batch continues
  and prints a final `N/M succeeded` summary.
- **Guaranteed cleanup** — `run_matchup` always stops the recorder and dismisses
  back to the editor (even on error), so one bad run can't orphan a recorder or
  leave the game stuck for the next matchup.
- **Recording sanity** — an empty/tiny `.mov` (e.g. Screen Recording not granted)
  fails loudly instead of composing a black video.

## Notes / limitations

- **Whole-display capture** — the video is the full screen and the audio is the
  full system mix. Don't switch apps or play other sounds during a run.
- **No survivor counts** — by design (no OCR of the fight): the recap card states
  the matchup, not a winner or unit counts.
- **Lead-in trim** — the menu/load seconds before the fight are trimmed with a
  fixed heuristic (`LEAD_PAD` in `orchestrate_matchup.py`); a faint title can
  linger a beat into the footage.
- The recorder binary is built at `../recorder/sck_record` (`../recorder/build.sh`).

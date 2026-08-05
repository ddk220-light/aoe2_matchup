# Matchup Scenario System — FINAL (2026-07-18)

> Template internals. Entry point for the whole video workflow:
> `UNIT_VIDEO_WALKTHROUGH.md`. 2026-07-26: all embedded AI text is CHAT-FREE
> (repo .per + deployed + all 3 scenario AI slots) — keep it that way.

Golden battle-scenario templates per engagement kind + a generator that retargets them to any
civ/unit matchup. All three engagement kinds **confirmed working in-game** (2026-07-18).

## The golden templates (canonical, in the repo)

`apps/video/templates/golden_*.aoe2scenario` — recorded from the user's hand-fixed,
in-game-confirmed `works_*` files. 16×16 flat map, P1 = human spectator (map revealers,
PromiDE — harmless on a human slot).

| Template | P2 | P3 |
|---|---|---|
| `golden_infvsinf`    | infantry ×36 on `ddkMatchupAI` (TOP)  | infantry ×40 on **NoneAi** (BOTTOM) |
| `golden_rangedvsinf` | ranged ×30 on `ddkMatchupAI` (TOP)    | infantry ×34 on **NoneAi** (BOTTOM) |
| `golden_cavvsranged` | cavalry ×29 on **NoneAi** (**EAST** ~13,7) | ranged ×28 on `ddkMatchupAI` (BOTTOM) |

Cav-vs-ranged is the repositioned one: cavalry sits east, the ranged ball bottom, and the
AI roles flip to P3.

## The AI rules (learned the hard way)

- **The DE standard AI (PromiDE) does NOT work for infantry or ranged armies** — it crashes
  the game on scenario load (native BugSplat, nothing logged). Use the editor's **"None"** AI:
  `ai_names='NoneAi'`, `ai_type=2`, embedded blob `(defconst the-maze 0)\r\n(defrule(true)=>(disable-self))`
  → pure engine default behavior (units auto-engage).
- The patrol/kite side runs **`ddkMatchupAI.ai`** (`ai_type=0`) — THE production name for the
  clockwise square-patrol AI (= `ddkSquareV25`; see `ai_experiments/SQUARE_PATROL_EXPERIMENTS.md`;
  earlier alias `ddkCircleModel`, anticlockwise twin `ddkCircleModelCCW`; all deployed in
  `…\AoE2DE\resources\_common\ai\`, generator `tools/make_ddkmatchupai.py`).
- **A scenario stores AI data in THREE places; all must be consistent** or DE crashes on load:
  (1) `PlayerDataTwo.ai_names/ai_type`, (2) `PlayerDataTwo.ai_files[slot].ai_per_file_text`
  (per-slot embedded script), (3) the trailing `Files` section (`ai_files_present` /
  `number_of_ai_files` / `ai_files[i].{ai_file_name, ai_file}`). The golden templates are
  already consistent — which is why the generator never touches AI at all.
- AI = empty name on a fighting slot also crashes. Never write it.

## Generator: `apps/video/build_civ_copies.py`

Copies a golden template and changes ONLY: unit types (`unit_const`), army counts
(equal-resources trim), and civilizations (P1 civ follows P3). AI, embedded blobs, Files
section, and kept-unit positions stay byte-identical to the template.

- **Equal resources:** `MAX_COUNT=25`/side; weighted cost `food·1.0 + wood·0.7 + gold·1.5`
  (lockstep with `aoe2x/sim/simulation_real.weighted_cost`); cheaper-per-unit side gets 25,
  pricier side trimmed to match total cost. Costs come live from
  `data/golden/aoe2_reference.db` `final_cost_*` (Imperial, fully upgraded).
- Ref-DB cost slugs: knight line = `paladin`; unique units carry the civ suffix
  (`elite_woad_raider_celts`).
- Reproducibility verified: regenerating from the repo templates is **byte-identical** to the
  in-game-confirmed outputs.

```bash
apps/video/.venv/Scripts/python.exe apps/video/build_civ_copies.py
# -> writes <matchup>.aoe2scenario into the AoE2 save folder scenario dir
```

Current batch (all confirmed in-game): `aztec_celt_infvsinf` (Aztec Champion ×25 vs Celt
Elite Woad ×19), `aztec_celt_rangedvsinf` (Aztec Arbalester ×24 vs Celt Champion ×25),
`aztec_celt_cavvsranged` (Celt Cavalier ×12 vs Aztec Arbalester ×25). New matchups = add a
row to `COPIES` (mind civ tech trees, e.g. Aztecs have no cavalry).

## History / forensics

The 2026-07-08/09 load-crash investigation (superseded pipeline scripts, diagnostics,
red-herring log) is archived in `apps/video/archive/matchup_crash_forensics/`. Debug lesson
that survives: **the game logs nothing for scenario load-crashes — diff the scenario DATA
(all three AI locations) instead of reading logs.** (Crash dumps, if ever needed:
`%LOCALAPPDATA%\Temp\AoE2DE*.dmp`, WER `%LOCALAPPDATA%\CrashDumps\`, per-session
`…\Games\Age of Empires 2 DE\logs\<session>\MainLog.txt`.)

The old 840 KB `templates/golden_template.aoe2scenario` (pre-2026-07-18 single-template
test bed) crashes the current game build on load — retired, kept for git history only.

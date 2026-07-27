# Unit Analysis Video — THE GOLDEN WORKFLOW

The complete, reproducible recipe for producing a per-unit analysis video (YouTube
long-form + 9:16 short). **Perfected on the Elite Champi Warrior (Incas),
2026-07-26** — that run is the reference implementation: user-declared win
conditions, sim categorization, in-game arbitration of every contradiction, three
engine fixes earned from tapes, curated fight list, zero hand-pins in the final
output. Earlier subjects (ETG, Blackwood, Guecha) predate parts of this flow.

**Everything needed to replicate is in this repo** (branch `aoe2_ai_for_simulation`)
except three regenerable/local things: `apps/video/media/` (re-download from the
Railway bucket — see Phase 0), `sim_v2/_work/` (deterministic re-sim), and the
recordings themselves (raws mirrored to `~/Videos/aoe2_backups/`).

## Document map

| Doc | Covers |
|---|---|
| **this file** | The end-to-end workflow, gates, and golden-state inventory |
| `RUNBOOK.md` | Recording-sweep operations: game pre-flight, failure recovery |
| `MATCHUP_SCENARIO_SYSTEM.md` | The golden scenario templates + retargeting generator |
| `sim_v2/README.md` | The V2 sim method + categorization internals |
| `MAC_SETUP.md` | (Optional) running the recording phase on macOS |
| `ai_experiments/IMMORTAL_CORE.md` | History/design of the ddk AI family |
| `../../docs/architecture/` | The webapp itself (the sim engine's home) |

## The workflow at a glance (4 steps, 2 user gates)

1. **User picks the subject** and declares WIN CONDITIONS: for each opponent
   unit line, the rankings-page pool percentile below which the subject should
   win ("beats militia below the 60th, all camels, no gunpowder…"). ~13 numbers,
   saved as `sim_v2/win_conditions/<slug>.json`.
2. **Sim + categorize + SHOW THE TABLE** (GATE 1): run the V2 sim over the
   ~76-opponent pool, derive expected/unexpected from the win conditions, and
   present the user the full table (per line, with percentiles, win rates, and
   the filmed picks). **Every rule-vs-sim contradiction gets 5 in-game runs**
   on the golden rig; a confirmed sim error means FIX THE ENGINE (Phase 2).
   User approves the final list + picks.
3. **Record the filmed picks** (reuse existing tapes where the fight is
   identical; retake protocol for probabilistic outcomes) and verify 100%.
4. **Assemble + deliver** the long-form and the short from the same raws.

### TL;DR command block (subject past the gates)

`VPY` = main checkout's `apps/video/.venv/Scripts/python.exe` ·
`AOE2_MEDIA_DIR` = main checkout's `apps/video/media` · `W` = an ABSOLUTE
workdir path (relative breaks the node stage) · game FULLSCREEN at the editor.

```bash
# 1. simulate + categorize under the user's win conditions
python sim_v2/build_v2_categorization.py <Civ> <slug> --workdir "$W" --stage simulate --jobs 6
python sim_v2/build_v2_categorization.py <Civ> <slug> --workdir "$W" --stage categorize \
    --win-conditions sim_v2/win_conditions/<slug>.json --overrides sim_v2/overrides/<slug>.json
# 2. record, ONE invocation PER category (ranks restart at 1 per invocation)
$VPY sim_v2/record_fights.py <Civ> <slug> <category> <out_dir> <OppCiv>/<oppslug> ...
$VPY sim_v2/verify_fight.py <out_dir>          # must be N/N — read the per-fight lines
# 3. build both deliverables
$VPY build_unit_long_form.py --subject "<Civ>:<slug>" --cat "$W/categorized.json" \
    --clips-dir <out_dir> --out "<out_dir>/<Unit Name> - Counters and Matchups.mp4" --skip-coinflip
python -m auto.build_reel --subject "<Civ>:<slug>" --cat "$W/categorized.json" \
    --raws-dir "<out_dir>/raw recordings" --per-category --pacing long \
    --out "<out_dir>/<Unit Name> - Short.mp4"
```

---

## Phase 0 — Environment (once per machine/worktree)

- **Python**: anything touching the game/scenarios/media runs on the MAIN
  checkout's `apps/video/.venv/Scripts/python.exe` (worktrees have no venv).
  Set `AOE2_GRPC_PYTHON` to that python for the rig. Sim/categorize stages run
  on the repo conda python.
- **gRPC mTLS certs** (`cade-client.key/.pem`, `certificate-authority.pem`) in
  the worktree's `aoe2x/grpc/` — gitignored; copy from the main checkout.
- **Media** (`sprite_full.png` + `attack.gif` per unit): `apps/video/media/`
  (gitignored). Missing assets: the Railway bucket is readable tokenless via
  the public presigned-redirect route `…/assets/<key>` with SHORT unit names
  (`gifs/<name>.gif`, `img/unit_sprites_full/<name>.png`); the overlay code
  auto-fetches gifs it lacks. `AOE2_MEDIA_DIR` MUST be set for assembly —
  `build_unit_long_form.py` refuses to run without it (a silent fallback once
  shipped a mute intro).
- **Game**: AoE2:DE FULLSCREEN at the Scenario Editor (load `Matchup Run` from
  the editor's Load page to get there). Launch: `steam://rungameid/813780`.
- **Audio (user rules)**: civ MUSIC (~75%) and unit SOUND (~73%) stay ON — they
  are wanted in recordings. The AIs are chat-free (a per-second debug chat once
  put 6 notification ticks/sec into every soundtrack); if any chat/probe is
  re-added to an AI, strip it EVERYWHERE before recording (deployed ai folder +
  repo `.per` + all 3 embedded AI slots in every scenario).
- Kill the Win11 IME overlay before every batch:
  `taskkill //f //im TextInputHost.exe` (git-bash slash escaping).

## Phase 1 — Win conditions + categorization (GATE 1)

1. **User declares win conditions** → `sim_v2/win_conditions/<slug>.json`:
   ```json
   { "subject": "Incas/elite_champi_warrior",
     "thresholds": { "militia": 60.0, "spear": 100.0, "shock_infantry": 70.0,
       "skirmisher": 100.0, "archer": 90.0, "cav_archer": 60.0, "gunpowder": 0.0,
       "scorpion": 0.0, "knight": 50.0, "light_cav": 100.0, "camel": 100.0,
       "steppe_lancer": 100.0, "elephant": 10.0 } }
   ```
   Semantics: the subject is expected to beat any opponent strictly BELOW that
   percentile of its own line; `100` = the whole line inclusive; `0` = none.
   Percentiles are the rankings-page pool percentiles
   (`aoe2x.advisor.best_units._load_pool_score_percentiles` — mirrors the live
   site). Units with no pool score need a `"manual": {"Civ/slug": "win"|"loss"}`
   entry (the categorizer hard-errors otherwise).
2. Run simulate + categorize (commands above). The rule engine:
   outcome (win ≥0.8 wr / loss ≤0.2 / else coin-flip) comes from the sim;
   expected-vs-unexpected comes from `SR.win_condition_favored`. Without a
   win-conditions file the old cascade applies (bonus → ranged-counters-melee-inf
   → dearer-unit) — kept for comparison only; win conditions are the standard.
3. **Show the user the table** grouped by line: percentile, sim wr, resulting
   category, plus the auto filmed picks. **STOP — user approves.**
4. **Contradictions** (rule says win, sim says loss, or vice versa) → Phase 2.

## Phase 2 — In-game arbitration + FIX THE ENGINE

The golden rig is ground truth. For each contradiction (and any matchup the
user doubts):

1. Record **5 runs** into a diag dir:
   `$VPY sim_v2/record_fights.py <Civ> <slug> diagA <diag_dir> <Opp>/<slug>` (×5,
   distinct category tags so names never collide). ~2.5 min/run.
2. Tally the sidecars (side1 = P2; on `golden_rangedvsinf` the RANGED side is
   P2 — verify_fight normalizes, ad-hoc scripts must check).
3. **Sim right** (champi-vs-CKN): expectation was wrong — the category stands.
4. **Sim wrong** → find the MECHANIC, fix the ENGINE, never hand-edit the
   category. The 2026-07-26 reference fixes (all validated on a 13-anchor tape
   sweep + frontend tests before shipping):
   - `simulate.js getDamageAgainst`: the attack's CLASS picks the resisting
     armor (thrown-melee Gbeto/Mameluke/Throwing-Axeman vs MELEE armor) — a
     real shipped-engine bug found via 0/5 tapes.
   - `TRAMPLE_CONE=60` (headless): conical blast (dat blast_attack_level 162,
     e.g. Ibirapema) splashes only the front arc; schema has no shape column so
     config_combat says 360° — fatal under ENVELOP.
   - `KITE_CATCH=1.15` (headless): flee is denied only when kiter is faster AND
     chaser ≥1.15 tiles/s ABSOLUTE AND the kiter can't hurt the chaser
     (dmg ≤ max(3, 5% HP)). See sim_v2_model.js for the full three-condition
     rationale; speed RATIO and global TRAMPLE_K were tested and are WRONG.
   Method: reproduce headless with a timeline probe (patch
   `BattleSimulation.prototype.update` to sample counts/hp/nearest-enemy
   distance), form the hypothesis, implement as an env-knob transform in
   `headless_sim.js` + rationale in `sim_v2_model.js` (production `simulate.js`
   only for genuine shipped bugs), then sweep EVERY tape anchor before baking.
5. `ingame_outcome` pins (+ display `ingame_wr`/`ingame_hp`) are documented
   STOPGAPS only — the champi run retired all of them once the engine
   reproduced the tapes natively. That is the bar.
6. Re-simulate, re-categorize, re-confirm the table with the user.

## Phase 3 — Record the filmed fights

**Filmed picks**: automatic rule = 3/category (wins most-expensive-first,
losses cheapest-first, #3 forced to a different broad class). The user curates
via `"showcase_override"` in `sim_v2/overrides/<slug>.json` — which REPLACES
the picks for ALL categories, so freeze the auto picks for the categories you
aren't changing (champi final: 4 unexpected wins for on-screen variety —
War Wagon, Centurion, Tiger Cavalry, Iron Pagoda — one big-ranged + three
distinct heavy cavalry; two same-read units like Ballista Elephant + War Wagon
is one too many).

1. One `record_fights.py` invocation PER category; ranks restart at 1 each
   invocation — to fill slots 2-3 of a category whose rank-1 tape is reused,
   record then RENAME rank prefixes (clip + hp.json + all 5 raw files),
   renaming in an order that never collides.
2. **Reuse tapes** whenever the fight (civ/slug/counts) is identical — copy
   under the new `<category>_<rank>_<oppslug>` name; never re-record a good
   fight. Superseded tapes go to `<out>/not_in_cut/` (kept, not deleted).
3. Each fight: stage scenario → load via search filter (`Matchup`) → Test →
   gRPC `.END` detection → quit to editor → compose overlay mp4 + archive raws
   (`.mov` + `.frames.bin` + `.hp.json` + `.meta.json` + `.END`). First fight
   of a batch sometimes hits a nav race — the rig self-recovers on the next
   fight; just re-run the failed one (single-opponent invocation = rank 1).
4. `verify_fight.py <out_dir>` must be **N/N** — read per-fight lines
   (`cat=None expect=?` rows are unverified, not passes).
5. **Retake protocol**: a probabilistic fight can land its tail outcome (Iron
   Pagoda wr 0.93 rolled a champi wipe once). Move the bad take + raws to
   `<out>/retakes_bad/`, re-record just that fight, rename to the right rank.
   The tape must show the sim's TYPICAL outcome.
6. Mirror `raw recordings/` to `~/Videos/aoe2_backups/<sweep>/` after every batch.

### The rig itself (what makes the fights golden)

- **AIs** (repo: `ai_experiments/`; deployed: Steam `resources/_common/ai/`):
  `ddkMatchupAI` = the patrol side (square-loop patrol, V25 clockwise), and
  `ddkModelAI` = the kiting AI (not used by the matchup templates but part of
  the family). Both CHAT-FREE. Scenario AI lives in THREE places (PlayerDataTwo
  ai_names, PlayerDataTwo ai_per_file_text, Files section) — all three must
  match or the scenario silently crash-loads; `retarget_golden_ai.py` is the
  rewrite recipe. NEVER read mixed-version scenarios (1.57+1.58) in one python
  process (AoE2ScenarioParser global-state corruption).
- **Templates** (`templates/golden_*.aoe2scenario`): 16×16 panda map, P1 human
  spectator w/ map revealers, patrol side P2, other side NoneAi (the standard
  AI crash-loads on inf/ranged armies). Mapping: melee-vs-melee →
  `golden_infvsinf` (SUBJECT on P2), one side ranged → `golden_rangedvsinf`
  (RANGED side on P2), cav subject vs ranged → `golden_cavvsranged`. The
  builder (`build_golden_v2.build_v2_from_sides`) transforms ONLY
  unit_const/counts/civs — never AI fields, never the CHANGE_VIEW camera (8,7).
- **Army sizing**: equal resources, weighted cost F·1.0+W·1.0+G·1.5, per-unit
  cost ÷ TRAIN_BATCH (ONLY Blackwood trains in pairs — allowlist, not
  pop_space), cheaper unit capped at 21 (`RES_BUDGET=3000`). The sim's arena
  counts and the rig's counts MUST agree (same function family:
  `build_v2_categorization.arena_counts` ↔ recorder `equal_resource_counts`).
- **Capture**: 2560×1440@60 fullscreen; gRPC HP stream is the sole fight-end
  signal; sidecar side1=P2 (subject-normalization downstream).

## Phase 4 — Assembly

All cards are the PARCHMENT family (headless-Chrome HTML render; IM Fell
English/SC + EB Garamond, Georgia fallback offline).

**Long-form** — `build_unit_long_form.py` (fully derived from categorized.json):
- Order: Intro (3.5s animated hero + civ voice barks) → Expected Wins →
  Expected Losses → Unexpected Wins → Unexpected Losses (surprises last) →
  Outro (6s, aoe2matchup.com CTA). **`--skip-coinflip` is the standard** (user
  2026-07-26: the toss-up card doesn't add value). Empty categories: silence.
- Per category: explanation card (5s, auto copy from counts) → fights in rank
  order → ranking card (8s) only when ≥4 rows (value column = % HP remaining —
  subject's for wins, enemy's for losses; in-game-corrected rows show their
  measured numbers, never a discredited sim value).
- Output: 2560×1440@60 mp4 + `.chapters.txt`.
- **Verify before delivering**: ffprobe durations; frame-probe segment
  boundaries (ONE ffmpeg invocation per probe); intro volumedetect (voice ≈
  −19 dB max, silence −91 = the media-root bug); spot-read the ranking card.

**Short** — `auto/build_reel.py --per-category --pacing long`: one fight per
non-empty category from the SAME raws, 1080×1920. The "Shorts Overlays
Parchment" design: header card with unit names + equal-resources cost lines
(`N × (cost) = total res`, gold ×1.5 note), 1080×698 gameplay window (crop
`1862:1202:480:117` of 2560×1440 — x=480 user-calibrated, frozen), live HP
strip, The Numbers panel (army/damage/attack-rate/TTK), Spotlight intro with
stat bars, outro CTA.

## Phase 5 — Deliver + back up + commit

1. Deliver both files (chat attach and/or Taildrop:
   `"/c/Program Files/Tailscale/tailscale.exe" file cp <files> <device>:`).
2. **Backups**: raws mirrored per batch; diag runs keep their own dirs
   (`champi_*_diag/`); superseded takes in `not_in_cut/` + `retakes_bad/`.
3. **Git** (branch `aoe2_ai_for_simulation`): commit EVERYTHING repo-side —
   engine + model, rules, win_conditions, overrides, templates, AIs, overlay
   code, docs, and the categorization snapshot (`sim_v2/results/<slug>.{json,md}`
   — `_work/` is gitignored, results/ is the kept record). Push only with the
   user's OK (never staging/main from a session — those auto-deploy).
4. Not in git BY DESIGN: `media/` (bucket-recoverable), `.venv/`, `_work/`
   (deterministic re-sim), videos + raws (local + `~/Videos/aoe2_backups/`),
   gRPC certs (secrets), the 200MB matchup DBs (`D:/AI`).

## Known gotchas (bitten before)

- `--workdir` must be ABSOLUTE for `--stage simulate` (node resolves relative
  paths from `sim_v2/`, doubling the prefix).
- Scenario Load list is NOT date-sorted; the rig types "Matchup" into the
  search filter (persists between opens — always set, never assume).
- Never write the same `<category>_<rank>` name into a dir that already has
  one; rename/move superseded sets FIRST.
- One recording at a time; no CPU-heavy renders during capture (light file
  edits are fine).
- `showcase_override` replaces picks for ALL categories — omit none.
- Sidecar side1 = P2 = the patrol side, which for ranged-vs-melee is the
  RANGED side, not the subject.
- Windows `taskkill` needs `//f //im` under git-bash.
- The pool-percentile helper handles civs with TWO uniques on one line
  (list-of-pairs in UNIT_LINES) — fixed 2026-07-26 (`_line_imperial_slugs`),
  don't regress it.

# Unit Analysis Video — Full Walkthrough (any unit)

The end-to-end, reproducible process that produced *Elite Temple Guard — Counters and
Matchups* (2026-07-19). Follow it for any subject unit. It has **two user sign-off
gates** — do not proceed past a gate without explicit user approval.

Roles: "sim" = the V2 headless sim (`sim_v2/` frozen model over the shipped
`simulate.js`); "rig" = the in-game recording pipeline (Scenario Editor +
ddkMatchupAI golden templates + gRPC HP capture).

---

## Phase 0 — Environment (once per machine/worktree)

- Python for anything touching the game/scenarios/media: the MAIN checkout's
  `apps/video/.venv/Scripts/python.exe` (worktrees have no venv). Set
  `AOE2_GRPC_PYTHON` to that same python for the rig.
- gRPC mTLS certs (`cade-client.key/.pem`, `certificate-authority.pem`) must sit in
  the worktree's `aoe2x/grpc/` — gitignored; copy from the main checkout.
- Media (hi-res `sprite_full.png` + `attack.gif` per unit): main checkout
  `apps/video/media/units/<slug>/`; overlay code falls back there automatically
  (`intro_card._MEDIA_ROOTS`), or set `AOE2_MEDIA_DIR`.
  **If a unit's GIF is missing:** the full media set lives in the Railway project's
  bucket (project "aoe2" via `railway` CLI — auth with `RAILWAY_TOKEN`, never print
  it; the bucket is also readable tokenless through the webapp's public
  presigned-redirect route). Download `attack.gif` + `sprite_full.png` into
  `apps/video/media/units/<slug>/`. Ask the user if the bucket layout is unclear.
- Game: AoE2:DE open at the **Scenario Editor**, **FULLSCREEN** for recordings
  (windowed OK only for quick tests). Announce before firing `request_access`
  dialogs so the user is present. This machine is DVORAK — the rig's `_win_type`
  already sends layout-independent unicode input; don't regress it.

## Phase 1 — Sim categorization + the list (GATE 1)

1. Run the V2 categorization for the subject:
   `sim_v2/build_v2_categorization.py` (15-seed frozen model; TRAIN_BATCH allowlist
   halves per-unit cost ONLY for true multi-unit-per-train lines, e.g. Blackwood 2/train;
   Karambit is 1/train at 0.5 pop — NOT batched).
   Per-subject curation lives in `sim_v2/overrides/<subject>.json`
   (`remove` / `add` / `extra_results` for single-matchup re-sims /
   `exclude_showcase` / `ingame_outcome` pins — pins ONLY for validated unmodeled
   mechanics; otherwise **fix the sim, never hand-pin**).
2. Output: `sim_v2/results/<subject>.{md,json}` with rows, categories
   (expected_win / unexpected_win / coin_flip / unexpected_loss / expected_loss),
   `showcase`, and the `filmed` block — 3 picks per non-empty category via
   `aoe2x/analysis/story_rules_v2.pick_filmed`: #1 = cost extreme (most expensive
   win / cheapest loss), #2 next by cost, #3 a different unit class if #1+#2 share one.
3. **Show the user the structured expected/unexpected lists** (an HTML artifact or
   the ranking-card renders). **STOP — user signs off on the categorization and the
   filmed picks before anything is recorded.**

## Phase 2 — In-game validation of the sim (GATE 2)

1. Build validation scenarios at the SAME arena counts the sim used, from the golden
   engagement templates (pattern: `build_etg_validation.py`): coin-flips + any
   unvalidated unexpected results + 2-3 certain anchors. Template mapping:
   melee-vs-melee → `golden_infvsinf` (subject P2 = ddkMatchupAI patrol, opponent
   P3 = NoneAi); one side ranged → `golden_rangedvsinf` (ranged side on P2 patrol);
   cav subject vs ranged → `golden_cavvsranged`. Transform ONLY unit_const/counts/civs
   — never AI fields (stored in 3 places; any mismatch = silent load crash).
2. Run each in-game (rig or manually with the user watching), record outcomes,
   compare against sim win-rates/margins (`sim_v2/verify_fight.py` on sidecars).
3. **Mismatch?** → sim-review loop with the user: identify the physics/mechanic gap,
   fix the ENGINE (env-knob transform in `sim_v2/headless_sim.js` + rationale in
   `sim_v2_model.js`), re-sim, re-validate. Pin via `ingame_outcome` only when the
   mechanic is confirmed unmodeled (document why). Then regenerate Phase 1 outputs
   and re-confirm the list with the user.
4. **Match?** → proceed.

## Phase 3 — Record the filmed fights

1. `sim_v2/record_fights.py <SubjCiv> <subj_slug> <category> <out_dir> <OppCiv>/<opp_slug> ...`
   — uses `build_golden_v2.build_v2_from_sides` (the FINAL golden templates; never
   the retired `build_golden_from_sides`). One invocation PER category so the
   `<category>_<rank>_<oppslug>` names come out right (rank restarts per invocation).
   Output dir: `~/Videos/aoe2_matchups/<subject>_sweep/` (fresh dir per template
   generation — never overwrite an older set).
2. Game fullscreen at the editor, hands off the machine. Each fight ~2.5 min:
   stage scenario → load via search filter → Test → gRPC .END detection → quit to
   editor → compose live-overlay mp4 + archive raws.
3. Every fight archives to `raw recordings/`: `.mov` (untouched capture), `.frames.bin`
   (raw gRPC stream w/ timestamps), `.hp.json`, `.meta.json`, `.END`. **Mirror the
   whole dir to `~/Videos/aoe2_backups/` after each batch** — raws are the source of
   truth; overlays are re-cuttable post-process.
4. `verify_fight.py <out_dir>` must report N/N matching their filmed categories.
   Any mismatch vs the sim's category → back to Phase 2's review loop.

## Phase 4 — Cards + assembly

All cards are the PARCHMENT family (headless-Chrome HTML render; IM Fell English/SC +
EB Garamond, Georgia fallback offline):

- **Intro** (~3.5s video): `overlay/intro_card.py make_unit_intro_video` — Unit
  Spotlight with the animated attack-GIF hero, percentile stat bars (vs the unit's
  broad class), bonus-damage + armor-category chips, one-line verdict.
- **Per category with ≥1 fight**: explanation card (`make_category_explanation_card`,
  progress marker counts ONLY non-empty categories) → fights in rank order →
  ranking card (`make_category_ranking_card`) **only if the category has ≥4 units**
  (fewer = all were shown on camera; no list). Ranking card rules: top-20 by cost +
  "All N matchups at AOE2MATCHUP.COM" banner when truncated; value column = % HP
  remaining (subject's for wins, enemy's for losses), header carries the subject's
  FULL name; displayed value > 70% renders bold; filmed rows get SHOWN tags.
- **Empty categories: say NOTHING** (no card, no chapter).
- **Coin-flips**: no fights; one `make_coinflip_odds_card` near the end listing
  win:loss odds per coin-flip opponent.
- **Outro** (~6s video): `make_outro_thanks_video` — centered attack-GIF hero +
  "visit AOE2MATCHUP.COM …" banner + "Thank You For Watching".
- **Assembly**: follow `build_etg_long_form.py` (hand-built segment list in the
  order above, card renders normalized to the fights' native format,
  `concat_videos`, `write_chapters` — UTF-8). Verify: ffprobe + frame-probe each
  segment boundary (ONE ffmpeg invocation per probe; multiple `-i` of the same file
  in one command silently maps everything to input 0) + chapters ±2s.

## Phase 5 — Deliver

1. Show the user the final video (+ chapters); taildrop to the phone on request:
   `"/c/Program Files/Tailscale/tailscale.exe" file cp <file> iphone172:`
2. Commit on the working branch when the user approves. **Never push any branch
   without explicit user approval** (staging/main auto-deploy on Railway).
3. Later formats (9:16 reel via `auto/build_reel.py`) cut from the SAME raws —
   no re-recording.

## Known gotchas (bitten before)

- Scenario Load list is NOT date-sorted; the rig types "Matchup" into the search
  filter (which persists between opens — always set, never assume).
- The sim's arena counts and the rig's equal-resources counts must agree — both use
  weighted cost F·1.0 + W·1.0 + G·1.5 with cap 21 (video path). `build_civ_copies`'s
  wood 0.7 is the production-sim lockstep, used for validation *scenario* building
  where counts are passed explicitly.
- Rank numbering collisions: never record the same `<category>_<rank>` name into a
  dir that already has one (move superseded sets aside first).
- One recording at a time; don't run CPU-heavy renders during capture.

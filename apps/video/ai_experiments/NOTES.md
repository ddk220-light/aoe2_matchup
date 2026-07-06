# Custom Kite-Tester AI — Learnings & Status

> **✅ 2026-07-02 — SOLVED: `ddkImmortalCoreE/F` kites Immortal-style in editor Test** (user: "worked!").
> The winning approach was a **literal transcription** of Immortal's cav-archer pipeline (extraction
> workflow → `immortal_core_spec.md` in this dir → 85-rule .per with absolute-jump numbering) plus five
> environment fixes discovered by in-game probes/telemetry:
> 1. **Not all sn-* names are builtin** — copy Immortal's sn defconst ids ("invalid identifier" at load).
> 2. **`up-filter-distance` empties find-remote in our hand-written context** (twice confirmed:
>    ddkKiteV3 + CoreD's D7 trace) — never use it; prune by `up-remove-objects … object_data-to-precise`.
> 3. **`up-get-object-data 12` (range) can return 0** — floor it (`c:max 4`); a 0 range inverts the
>    kite servo (units step TOWARD the enemy).
> 4. **Never let units fight while scenario-default AGGRESSIVE** — stance-lock is unbreakable by orders;
>    de-aggro fresh units at adoption (halt idiom) and open with movement (boot state 18, not 22).
> 5. **`up-get-search-state` slot 0 = LOCAL total; the REMOTE count is slot +2.**
> Telemetry: `(chat-to-player 1 "…")` is visible in editor Test (chat-to-all is NOT); diagnostic rules
> appended AFTER the last jump target don't disturb the load-bearing numbering.
> `ddkImmortalCoreF` = CoreE + 4-class generality (bolas/longbow/arambai/HC) + 600ms kite dwell.


> **2026-07-01 — ddkMicroV1: the from-scratch line is BACK, rebuilt on verified donor mechanisms.**
> Corpus analysis (5-agent workflow, citations verified) found: **Rehoboam 1.80h is readable source**
> and has the only readable Immortal-grade kite (orbit-around-enemy ±750 cross @17068-17147, reload
> window @18378-18447, tree-check+stuck→flip @17425-17469); **Illuminati I-DUC.per:1578-1601** has the
> wall fix nobody's kite has (`up-path-distance strict=1 == 65535` fan-out retry); Bright Spark's shipped
> kite plausibly has a zeroed sideways component (corners itself); Immortal is structurally wall-blind.
> **ddkMicroV1.per** (this dir + Steam ai dir) marries those: orbit + reload-tail gate + obstacle
> point-contains (tree 915/wall 927/gate 939) flip + stuck detector + path-checked fan-out escalation +
> ranged-vs-melee condition (kite only when out-ranging) + cmdid-military class -1 find (all units incl.
> uniques by construction). **ddkEngineKite.per** = engine-kite baseline
> (`set-difficulty-parameter ability-to-maintain-distance 0` — 0=on, from AI (HD version).per ~7076).
> Test scenarios: "ddk Micro Clean" / "ddk Micro Obstacles" (build_immortal_test.py `--obstacles`).
> The pre-V1 sections below remain for the underlying engine gotchas (all still apply).


> **PIVOT 2026-06-29 — the from-scratch line below is PARKED.** ddkKiteV6 didn't match Immortal.
> User wants Immortal as the base, just **bounded on-screen and off the wall/tree edges**. Immortal's
> kite is a scored position search that already clamps its retreat to the **map edge**
> (`up-bound-precise-point … c: 13`), and it has no min-map-size gate — so the lever is the **arena,
> not the AI**: a small, obstacle-free map. The sticking came from the `default3` template's **566
> Gaia boundary trees + 'Contain strays' trigger** (the cage Immortal jams into). Fix shipped as
> **`apps/video/build_immortal_test.py`** (small map + strips all 566 Gaia + disables Contain strays;
> staged as "ddk Immortal Bound.aoe2scenario"). `--map-size` (default 32) is THE tuning knob. Assign
> **Immortal v0d10f** to P2 in the editor and Test. Editing Immortal's 115k-line compiled bytecode was
> rejected as too risky. Everything below is the earlier from-scratch DUC effort, kept for reference.


Goal: a from-scratch AoE2:DE AI (`.per`) for the matchup-sim/video tool that makes a group of
ranged units **kite** — circle in a tight, **on-screen** ring around a fixed center, **firing each
time the weapon reloads**, then circling again. Only kite when **ranged-vs-melee** (the unit
out-ranges the enemy); ranged-vs-ranged / melee-vs-melee just fight normally (NOT YET BUILT).

This was built bottom-up with ~15 in-game tests (editor "Test" mode). Each `.per` here is a step.
The big working AI `ddkTesterAI.per` is the separate "borrowed Immortal" option (class-generalized
Immortal; see the `ai-kiting-arena-research` memory) — NOT this from-scratch line.

## STATUS (2026-06-28)

| Piece | Works? | Proven by |
|---|---|---|
| Custom `.per` runs in editor Test | ✅ | `ddkResignTest` (player instantly resigns) |
| Move group to a point | ✅ | `ddkMoveV3` (marched east) |
| Orbit a fixed center in a tight circle | ✅ | `ddkCircleV2`/`ddkCircleV3` (user confirmed) |
| Detect the enemy | ✅ | `ddkSeeTest` (resigned once focus-player set) |
| Fire / volley the enemy | ✅ | `ddkKiteV4` ("stand and fire") |
| Orbit + fire by reload-gate | ❌ | `ddkKiteV5` — **circles but never fires** (deadlock, see below) |
| **Orbit + fire by time-stutter, around the enemy** | ⏳ | `ddkKiteV6` — built, awaiting in-game test |

### Why V5 deadlocked — and what the proven kite (Bright Spark) actually does

`ddkKiteV5` gated SHOOT on `(obj55 <= 0)` and ORBIT on `(obj55 > 0)`. It circled and never fired.
**Deep dive against `…\Downloads\Bright Spark 41 DE\Bright Spark 41\Advanced Cav Archer Micro.per`
(the proven reload-kite) revealed the real mechanism:**

- **A move order INTERRUPTS the engine's attack/reload cycle and FREEZES `obj_data 55`.** The instant
  a unit fires, obj55 jumps to ~max; V5 then immediately issued a move (because obj55 > 0), which froze
  obj55 at ~max. It never ticked back to 0 → ORBIT always won → never fired again. (ddkKiteV4 fired fine
  because it *never* moved — the engine ran the attack loop and obj55 cycled normally.)
- **Bright Spark only kites the *tail* of the reload.** Its FIRE rule = `(obj55 <= 0)(obj73 != 1)` →
  `up-target-objects action-default`. Its KITE-MOVE rule is gated `(obj55 < field54−910)(obj55 > 0)`
  — i.e. it issues **no order at all** right after firing (obj55 ≈ max, obj73 == 1), letting the engine
  tick obj55 down; only once obj55 has fallen below `reload−910` does it briefly move, then fire again.
  So it never freezes obj55 mid-reload. (`field54` = reload-time; the `−910` is a per-unit tuning
  offset: cav-archer −910, heavy-cav-archer −900, mameluke −400.)
- Bright Spark reads the enemy's **precise position from `object_data 38/39`** (not `up-get-point`),
  via `(up-set-target-object search-remote c: 0)(up-get-object-data 38 …)(up-get-object-data 39 …)`.
  This is the safe center-capture (the `up-get-point position-object` that broke ddkCircleV1 is avoided).

### The V6 fix — time-based stutter, orbit centred on the enemy (`ddkKiteV6`, awaiting test)

Don't gate on obj55 at all. **Alternate FIRE and MOVE on a pass counter** so each gets uninterrupted
passes (the attack loop actually looses a shot; the move actually circles):
- `gl-pcount` increments every pass, wraps at `CYCLE-PASSES`. `pcount < FIRE-PASSES` → FIRE phase;
  `pcount >= FIRE-PASSES` → ORBIT phase. (Built from the V3 throttle primitives — proven in editor Test;
  **no timers**, whose editor-Test behaviour is unproven here.)
- FIRE phase + enemy → the **ddkKiteV4 attack** (`up-target-objects 0 action-default`) — proven.
- ORBIT phase → the **ddkCircleV3 ring move** (`up-target-point gl-tx action-move … stance-no-attack`) —
  proven. Waypoint `gl-idx` advances only during ORBIT (ring holds still while firing).
- **Centre = the enemy** (per user request): each pass, find nearest enemy, read `obj 38/39` precise
  pos → `gl-cx/gl-cy`; the 16-point ring (R=300 = 3 tiles) is built around it, so the army orbits the
  (moving) enemy and keeps it boxed at range. Hardcoded tile 40,40 is only a pre-first-contact fallback.
- **Tuning knobs:** `FIRE-PASSES` (20) = stand-&-fire window (raise if it barely fires); `ORBIT-PASSES`
  (40) = circle window (~reload); `gl-tick` threshold (6) = orbit speed. `CYCLE-PASSES` MUST = the sum.

**If V6 works, the follow-up for *accurate* reload cadence** is to swap the pass counter for game
**timers** (`enable-timer`/`timer-triggered`, real seconds) sized from `object_data 54`, so cadence is
AI-pass-rate-independent. Do that only after the stutter itself is confirmed in-game.

## DUC engine gotchas (hard-won — each cost in-game cycles)

0. **A defrule may hold AT MOST 32 facts+actions combined** — exceeding it = ERR6002 "rule too long"
   and the WHOLE file fails to load (killed ddkMicroV3; split big sense rules; keep rules ≤ ~25).
   The editor DOES show a parse-error popup (file/line/ERRcode) when a broken AI loads — check for it
   whenever an AI "does nothing".

1. **Editor "Test" runs custom AIs + DUC unit orders** (Immortal/ddkTesterAI move units there). So
   editor Test is a valid test path; no need for a real game.
2. **AI chat is NOT visible in editor Test** — `chat-to-all` / `up-chat-data-to-all` produce nothing
   on screen. Do NOT use chat to diagnose. Use **`(resign)`** (instant, visible) or visible MOVEMENT
   as the signal — gate `(resign)` on a condition to test it.
3. **The game caches a compiled AI by FILENAME within a session.** Editing a `.per` and re-running
   the SAME personality reloads the STALE parse. **Always ship a FRESH filename** (ddkKiteV1→V2→…)
   when iterating. (This silently wasted several cycles.)
4. **Multi-goal writers overlap consecutive goal ids:** `up-get-search-state <g>` writes a **4-GOAL
   block** (g..g+3 = local-total/local-last/remote-total/remote-last); `up-get-point`/`up-copy-point`
   write **2** (x at g, y at g+1). Goal layouts MUST NOT place another var inside another's range.
   (A collision silently broke init once.)
5. **MOVE:** find AND `up-target-point` must be in the **SAME rule body** — `up-full-reset-search`
   between them wipes the search list, so the order hits 0 units. Re-issue every pass to hold control.
   Form: `(up-modify-sn sn-target-point-adjustment c:= 6)(up-target-point <xgoal> action-move -1 stance-no-attack)(up-modify-sn sn-target-point-adjustment c:= 5)`.
   Destination in **PRECISE coords = tile*100** (tile 40 = 4000). `up-create-group`/`up-set-group`
   did NOT help (empty group). Continuous re-issue to a FIXED point makes units jitter/"readjust" on
   the spot — fine for a circle since the waypoint keeps advancing.
6. **ENEMY DETECTION:** `up-find-remote` only searches the player named by `sn-focus-player-number`.
   **You MUST set it before every `up-find-remote`** (`(up-modify-sn sn-focus-player-number c:= <enemyPlayer>)`),
   else it returns 0 enemies and nothing ever fires. THIS was the V1/V2/V3 "never fires" cause.
   (Tester hardcodes enemy = player 3 = P3; generalize to a player loop + diplomacy check later.)
7. **FIRE:** `(up-find-remote …)(up-clean-search search-remote 44 1)(up-filter-include 4 -1 -1 -1)(up-find-local c: -1 c: 240)(up-target-objects 0 action-default -1 3)`
   in one rule (enemy in search-remote, my units in search-local) makes them stop and volley. Proven.
8. **`up-filter-distance c: 0 g: <obj-12-range-goal>` BROKE detection** (ddkKiteV3 circled, never saw
   the enemy) — it excluded every enemy. Either obj-12 isn't in plain tiles for the filter, or the
   target-point wasn't set right. **Drop the distance filter; detect "any enemy" (no filter) and let
   the unit's own range decide whether it fires.**
9. **Center-capture via `up-set-target-object search-local c: 0` + `up-get-point position-object` is
   SUSPECT** — it broke `ddkCircleV1` (never moved). Use a **hardcoded center** for now
   (ddkCircleV2/V3 work). Auto-centering still TODO — try `position-center` or a centroid loop, test
   in isolation.

### object_data field ids (used / verified)
`0` = unit id / facing · `2` = class (900-series encoding, e.g. cav-archer = 936) · `8`/`9` = point x/y ·
`12` = max attack range (tiles; ×100 for precise) · `13` = speed (precise/s) · `23` = target-unique-id ·
`38`/`39` = precise x/y · `44` = distance-to-target-point · `54` = reload-time (ms) · `55` = next-attack
(reload countdown ms; 0 = ready, jumps to reload on firing) · `62` = min-range · `80` = to-precise.
**`73` = TAG (AI-writable group id via up-create-group/up-modify-group-flag; -2 = untagged) — NOT an
attacking flag** (Immortal defconst `object_data-tag 73`, line 630; corrected 2026-07-01 — the earlier
"attacking flag" reading came from Bright Spark, which was checking its OWN tag marks). There is NO
engine attacking flag: Immortal detects engagement via object_data-action == attack / target-unique-id
/ the height of obj55.

## The working ORBIT recipe (ddkCircleV3 / V5)
- `set-goal` a fixed center (precise). `gl-tick` pass-counter advances `gl-idx` (mod N) every ~6
  passes. Per-idx DISPATCH rules set `gl-tx` = center + precomputed ring offset[idx] (16 points;
  R=300 precise = 3 tiles for kiting-in-range, R=800 = 8 tiles for the pure-circle demo). One ORBIT
  rule re-issues `up-target-point gl-tx action-move` every pass → units chase the advancing waypoint.
- Tunables: ring offset magnitude = radius; `gl-tick` threshold = orbit speed (bigger radius needs a
  proportionally larger threshold so units keep up); #waypoints = smoothness.

## Test setup
- Scenario builders (in `apps/video/`): `build_circle_test.py` (units + lone enemy, no combat),
  `build_kite_test.py` (P2=12 cav archers north of center, P3=8 knights AT center tile 40,40 = the
  AI's hardcoded orbit center). Staged into the profile scenario folder as "ddk Circle/Kite Test".
- AI files live in the STEAM install dir: `C:\Program Files (x86)\Steam\steamapps\common\AoE2DE\
  resources\_common\ai\` (NOT the user profile). Each needs an empty `.ai` companion to appear in
  the personality list. The game reads that Steam dir (ddkTesterAI works from there).
- To test: editor → load the scenario → assign the ddk* personality to P2 → Test (any difficulty).

## File inventory (this dir = backup of the Steam ai dir)
Diagnostic probes: `ddkResignTest` (AI runs?), `ddkFindTest` (find own military?), `ddkSeeTest`
(detect enemy w/ focus-player?). Move: `ddkMoveTest`(v1-2 broken), `ddkMoveV3`(works). Circle:
`ddkCircleTest`/`V1`(broken init), `ddkCircleV2`(works, hardcoded center), `ddkCircleV3`(works,
2x radius + 16 pts). Kite: `ddkKiteV1-3`(no fire — missing focus-player), `ddkKiteV4`(fires! no
orbit), `ddkKiteV5`(orbit + reload-gate = circles-no-fire DEADLOCK), `ddkKiteV6`(time-stutter +
enemy-centred orbit — awaiting in-game test). `ddkTesterAI`= the big Immortal-based option (separate
line, 3.5MB).

## 2026-07-02 (later) — ddkImmortalCoreG: the generalization, implemented

Plan items 1-4 of IMMORTAL_CORE.md in one version, generated from CoreF by script
(scratchpad make_coreG.py pattern) and validated structurally: 115 rules = CoreF 85 + 30
appendix; ONLY rules {0,44,45,46,49,54} differ from working CoreF; jump map identical;
all rules <=32 elements; every token F-proven or defconst'd.

* W_fire = final_attack_delay(ms)+60 from data/golden/aoe2_reference.db, keyed on median
  ACTUAL type (obj1 = object_data-object-id) with class fallbacks. Immortal's own table
  (#1600-1605, re-extracted in full) matches modal obj81 base-type + obj82 upgrade-type but
  carries STALE AoC-era delays (CA 1000 vs DE 583) - its arbalest row (+17ms margin) proves
  W_fire ~ delay works. CA now releases from volleys ~0.35s sooner than CoreF.
* gDwell = clamp(liveReload-1400, 400, 2200) replaces the 600 literal in Rule 46.
* gKiteOK: kite only when gRange > gERange+1; else hold VOLLEY (normal fight); "HOLD"
  failsafe after 2.5s; melee-fallback rule un-lobotomizes the engine if no ranged ball
  forms in 10s (pure-melee armies fight normally).
* Speed tiers (live obj13 x100): >=135 strafe 240/step 420%; <=115 150/350%; else 200/390%.

Deployed: Steam ai dir ddkImmortalCoreG.per/.ai. New scenarios: "ddk Immortal HandCannon /
Elephant / Mangudai" (Turks/Bengalis/Mongols vs knights). Expected chats: ImmortalCoreG up ->
TAGGED -> WFIRE SET -> KITE/VOLLEY; HOLD only vs ranged. Untested in-game.

## 2026-07-02 (cleanup) — zero-setup test scenarios + decluttered game dirs

* build_immortal_test.py gained --ai <name> (pre-picks a CUSTOM AI for P2 INSIDE the scenario:
  PlayerDataTwo.ai_names[pid-1] + ai_type[pid-1]=0; script NOT embedded, so .per edits keep
  flowing) and --blank (no armies; paint units in the editor). Round-trip verified on all 8.
* Scenario dir now holds ONLY: ddk TEST Blank / CavArcher (Huns) / Bolas (Mapuche) / Longbow
  (Britons) / Arambai (Burmese) / HandCannon (Turks) / Elephant (Bengalis) / Mangudai (Mongols)
  - each with ddkImmortalCoreG pre-picked: load in editor, hit Test, done.
* AI dir now holds ONLY ddkImmortalCoreG + ddkImmortalCoreF (fallback) + Immortal v0d10f
  (comparator). 82 old ai files + 22 old scenarios (incl. default1/3/8/9, AI Arena, Matchup Run,
  The Siege) MOVED to "C:\Users\ddk22\Games\Age of Empires 2 DE\ddk_backup\{ai,scenario}" -
  outside resources\_common, so the game stops listing them; nothing deleted. Builders are
  unaffected (templates load from apps/video/templates/).

## 2026-07-02 (terrain fix) — knights were standing on WATER

Root cause: default3 (the template) is a 60x60 JUNGLE map with a LAKE; shrinking map_size
keeps the TOP-LEFT 32x32 corner = 203 water + 73 beach + rainforest tiles, with the fight
centre (16,16) on the old waterline. Every shrunk scenario ever built this way had it.
Fix in build_immortal_test.py: after resize, paint ALL tiles terrain_id=DIRT_1(6),
elevation=0, layer=-1. All 8 ddk TEST scenarios rebuilt + verified: 1024x flat dirt, AI
pre-pick intact (ai_names[1]=ddkImmortalCoreG, ai_type=0), armies/civs/bounds correct.
P1 keeps 2 INVISIBLE_OBJECTs at (31.5,30.5) = template keep-alive markers (leave them).
Template diplomacy is one-way (P2 enemy->P3, P3 ally->P2): knights stand until shot, then
retaliate/chase - the intended arena behavior, unchanged.

## 2026-07-02 (obstacle arenas) — 5 layouts for the wall-handling phase

build_immortal_test.py --obstacles is now a named layout (line/block/pillars/choke/pocket),
spawn-box-safe and map-size-relative. Staged as ddk TEST Obst Line/Block/Pillars/Choke/Pocket
(CA Huns vs 8 knights, flat dirt, CoreG pre-picked; walls=P1 palisades obj927, trees=Gaia
obj915). Old "line" layout bug fixed in passing: the palisade row at cy-6 overlapped the kiter
spawn rows - now cy-9. All 5 verified: dirt terrain, obstacle counts, nothing in spawn boxes,
everything in bounds. These are the baseline arenas for re-layering point-contains flip +
Illuminati fan-out onto CoreG.

## 2026-07-02 (autonomous session) — four new variants, one per micro angle

See BACKLOG.md for the full plan. All validated (structural diff vs CoreG / standalone
token check), deployed to the Steam ai dir, each with pre-wired scenarios (17 total, all
verified: right AI, dirt terrain, armies, bounds):

* ddkImmortalCoreH (obstacles/edges): end-of-pass probe of the issued kite point --
  up-point-contains tree 915/wall 927/gate 939 + up-path-distance==65535 + pinned-on-edge
  (bounded point collapsed onto ball) -> strafe-sign FLIP w/ 2.5s cooldown + 1.6s lateral
  evade boost (strafe 320/step 300). Chats FLIP. Scenarios: the 5 Obst arenas.
  CAVEAT: point-unit convention (tile vs precise) unverified -- probe uses vecKite/100;
  if FLIP never chats when balls hit walls, try the precise point instead.
* ddkImmortalCoreI (ranged-vs-ranged): when NOT out-ranging, volley remains the fight but
  between volleys hop a short alternating LATERAL step (step 180%, dwell 400ms, 700ms min
  volley dwell; Rule 44 release gates reused). Chats STRAFE. Scenario: RvR Strafe (arbs).
* ddkMeleeV1 (fresh 16-rule AI, no jumps): sort own + enemies left->right by precise-x,
  assign own[k] -> enemy[k mod m] on a 2s beat via per-unit group-3 selection loop.
  NO de-aggro (native aggressive pursuit), NO sighted-response zeroing (auto-engage
  stays healthy; SN blocks only kill engine GROUP tasking). Chats TAGGED-M/ASSIGN.
  Scenarios: Melee vs Archers, Melee Mirror.
* ddkImmortalCoreS (siege): CoreG + class 913/955 in all three find blocks + DB W_fire
  rows (mangonel/onager/SO 60, scorpion 260, heavy scorpion 160). Long reload -> dwell
  2200 = snap volleys + long repositioning. Scenario: Siege (6 mangonels vs 10 arbs).

## 2026-07-05 — scope narrowed to ranged-vs-melee only

User decision: focus exclusively on ranged-vs-melee unit control; stock Immortal covers the
other roles. Deployed set is now just ddkImmortalCoreF/G/H in the Steam ai dir and 13
scenarios (Blank + 7 unit arenas on CoreG, 5 Obst arenas on CoreH). CoreI/CoreS/MeleeV1
(.per+.ai) moved to ddk_backup\ai; RvR Strafe / Melee vs Archers / Melee Mirror / Siege
scenarios moved to ddk_backup\scenario (game-regenerated "The Siege"/"default1" re-backed-up
with a "(2)" suffix). Sources stay in this folder and on the aoe2_ai_for_simulation branch.
tools/verify_all.py trimmed to the 13-scenario expectation table — reports ALL 13 GOOD.

## 2026-07-05 (later) — golden_template + CoreG dynamic-enemy fix; single-AI setup

User made their own test bed: scenario/golden_template.aoe2scenario (16x16, flat, no water,
dirt + forest-floor accents, ~90 Gaia trees/bushes as scenery, 0 triggers, P1 human spectator
w/ corner keep-alives, P2 Burmese red = ddkImmortalCoreG.ai 21x Elite Arambai, P3 Berbers
yellow = Immortal v0d10f 21x Knights, P2<->P3 MUTUAL enemies). THE template going forward;
reference copy committed at apps/video/templates/golden_template.aoe2scenario. Note: the
editor stores ai_names WITH the .ai extension ('ddkImmortalCoreG.ai') vs our builder's
bare name -- both load.

BUG FIX (user-reported: CoreG assigned to P3 does not kite): CoreG hardcoded enemy=3
(rule 32 sn-focus-player-number c:= 3, rule 76 sn-target-player c:= 3 -- straight from the
P2-vs-P3 transcription), so on P3 it hunted itself and found nothing. Fix in make_coreG.py
(regenerated, validated: base-rule diff exactly {0,32,44,45,46,49,54,76}, +34 appendix):
gEnemyPly goal (197, default 3 in rule 0) feeds both sn writes via g:=; end-of-pass appendix
resolves the real enemy with Immortal's own idiom (up-find-player player_stance-enemy
find-closest gEnemyFound) -- diplomacy-driven, so it needs mutual-enemy stances (golden_template
has them); falls back to 3 when nobody has enemy stance (old one-way-ally arenas). One-pass
lag by design. One-shot chat "ENEMY = P2"/"ENEMY = P3" (latch gDiagE 199) confirms detection.
validate_variant.py: pooling the 3.4MB ddkTesterAI.per whole breaks (chat strings contain ';'
which poisons the comment-stripper) -> curated extra-token allowlist instead (up-find-player,
cited). CoreG is now 119 rules.

SINGLE-AI CLEANUP (user: "use CoreG going forward, archive the rest"): CoreF + CoreH
(.per+.ai) -> ddk_backup\ai; ALL 13 ddk TEST scenarios -> ddk_backup\scenario (superseded by
golden_template; Arambai/Obst ones referenced the archived AIs). Steam ai dir now has ONLY
ddkImmortalCoreG + Immortal v0d10f (+ untouched non-ddk). verify_all.py rewritten for
golden_template (flat/no-water/AIs/armies/triggers/bounds). "The Siege"/"default1" reappear
in the scenario dir on their own -- game-generated, leave them.

REMINDER for testing: the game caches .per parses by FILENAME per session -- CoreG was
edited IN PLACE, so fully restart AoE2 before testing if it was running.

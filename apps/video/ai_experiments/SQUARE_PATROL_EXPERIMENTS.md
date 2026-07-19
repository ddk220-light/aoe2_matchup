# ddkSquare* — Fixed-Square Patrol AI Experiment Log

Running log of every `ddkSquareV*` variant: the approach, what worked, what didn't, and
the raw in-game debugging data. Written for later analysis. Session date: 2026-07-07/08.

## Goal

Take the working ranged-unit kiting AI (`ddkModelAI.per`) and make the tagged "ball" of
ranged units **patrol a fixed square track** instead of enemy-relative kiting.

**Two behaviours were pursued, in order:**
1. **Oscillate** — `A → B → A → C → A → …` (alternate the two corners adjacent to home; never
   visit the diagonal corner). This is what most of V1–V24 chased. **V24 was the first version
   to make this work correctly** (✅ user-confirmed 2026-07-08).
2. **Continuous clockwise loop** (the FINAL desired behaviour) — `A → B → D → C → A → …` around
   the full perimeter, **never reversing direction**. The user decided the out-and-back
   oscillation didn't help the fight as much as hoped and switched to a one-way loop.
   **V25** implements this on top of every V24 lesson. ← current final.

Stop-to-volley is handled by the base state machine in both.

Test bed: `templates/golden_template.aoe2scenario` (16×16 flat, no water), the square AI on
**P2** (units always spawn in the **same place** every run — confirmed by the user), enemy
melee on P3. Map is 16×16; the intended square is **inset 5 tiles**: corners at tiles
`(5,5) (11,5) (5,11) (11,11)` = precise `(500,500) (1100,500) (500,1100) (1100,1100)`.

---

## Infrastructure / how these are built and tested

- **Generators:** `tools/make_ddksquareV<N>.py` read `ddkModelAI.per`, do count-asserted
  token swaps + append a movement "appendix", write `ddkSquareV<N>.per`.
- **Base edit:** every variant swaps the kite move-orders `vecKite → vecSquare` (Rules
  56/57/65) and strips 6 frequent base chats (Rules 44/45/46). Validator therefore always
  reports **base changed rules = {44,45,46,56,57,65}**; anything else = a bug.
- **Validator:** `tools/validate_variant.py <base> <derived> 44,45,46,56,57,65 <appendix_rule_count>`
  (paren balance, ≤32 elements/rule, jump set unchanged/≤76, token whitelist, defconst
  consistency). `up-chat-data-to-player` is whitelisted.
- **Deploy:** copy `.per` + create an EMPTY `.ai` companion into the Steam dir
  `C:\Program Files (x86)\Steam\steamapps\common\AoE2DE\resources\_common\ai\`.
  **Fully restart AoE2** (parse cache) before testing.
- **Decode a run:** the game auto-writes the live match to
  `C:\Users\ddk22\Games\Age of Empires 2 DE\76561198690498042\savegame\rec.aoe2record`.
  `mgz.model.parse_match` fails on editor-Test headers, so **byte-scan chat** with
  `re.findall(rb'"message":"([^"]*)"', data)` and strip the `@#NN Name: ` prefix.
- **Probe idiom (diagnostics):** `up-chat-data-to-player 1 "TAG=%d" g: goal` emits ONE goal
  per call. Standard probe (every ~1s): `P = gTagged*100 + gState`, `E = gE/gS` (patrol
  position), `D = gDistToTgt`, `N = gECount`, `M = vecMed_x*10000+vecMed_y` (where the AI
  thinks the ball is), `S = vecSquare_x*10000+vecSquare_y` (the target).

### Base facts that constrain everything
- **Goals:** base uses only goals ≤ 200 (max `gDiagE 200`). Verified the base contains NO
  literal 204–216 anywhere. Variant goals live at 202+. **No base↔variant goal collision.**
- **State machine (`gState`):** 18 = KITE/move (move-orders fire), 22 = VOLLEY/hold. Rule
  15 boots to 18 after tagging; Rule 46 does 18→22; **Rules 44/45 do 22→18 but require
  `gKiteOK == 1`**. `gKiteOK` (goal 191) = 1 only when our range out-ranges the enemy
  median (Rules ~1167-1177). If we don't out-range, a failsafe (Rule ~1180) parks in 22.
- **`vecMed`** (goals 128/129) = the tagged ball's median unit precise position, computed by
  the base each pass (before the appendix runs). `vecKite` (132/133) = base's kite vector
  (still computed even though we override the move target to `vecSquare`).
- **Move gate cadence:** Rule 48 "re-order throttle" limits how often move-orders re-issue;
  Rule 47 skips the move-orders when `gState != 18`.

### AoE2 coordinate system (looked up 2026-07-08)
- Tiles `(X,Y)`; **`(0,0)` = West corner**. Map is a square drawn rotated 45° (diamond).
  Corners ≈ West `(0,0)`, East `(max,max)`, North/South = `(max,0)`/`(0,max)`. Sources
  disagree on which axis is N vs S — **doesn't matter for us, we alternate both.**
- AI/precise coords = tile × 100. `vecMed`/`vecSquare` are in precise coords.

---

## Version summary

| Ver | Approach | Result | One-line evidence |
|----|----------|--------|-------------------|
| V1–V5 | Evolve the square-track concept (CCW full square, 6→5 tile inset, chat = xy only) | mixed / superseded | early iteration |
| **V6** | CCW **all-4-corner** loop, NO snapping, arrival-gated | ✅ **worked** | `try1` save: 47 `xy=` targets, units followed |
| **V7** | Oscillate **A↔B** (bottom edge), arrival-gated `D<350` | ✅ **worked** | user-confirmed; see V18 (=V7+probe) data |
| V8 | A→B→A→C via **leg state-machine** (`gLeg` toggle, `c:*-1`) | ❌ broke | "tag did not stick", D6 STATE22, no movement |
| V9 | V8 + find-probe | ❌ broke | same |
| V10 | Signed `gS∈[-600,600]`, A→B→A→C | ❌ mild | "moving one by one", x changes ~1-2 |
| V11 | Arc **teleport** `gS 0↔2400`, A→B→A→C | ❌ broke | units stuck at A |
| **V12** | Oscillate **A↔C** (left edge), arrival-gated | ✅ **worked** | user-confirmed |
| V13 | `gAxis`+`gE`+flip, toggle via **`c:*-1`** | ❌ broke | no coords, D6 STATE22 |
| V14 | `gAxis`+`gE`+flip, **subtract toggle** (no `c:*-1`) + P/E probe | ❌ broke | P=118/122, **E=0** |
| V15 | V14 + P/E/D/N probe | ❌ broke | **E=0, D stuck 700–928** |
| V16 | V14 + timer "creep" when `D≥350` | ◑ partial | E reached 600/450 but D stayed ~700–800 |
| V17 | **No arrival gate**, pure timer march | ❌ | E cycled 0–600 but **D 580–780, units didn't follow, xy=0** |
| **V18** | **= V7 exactly + P/E/D/N probe** (control) | ✅ **worked** | D 64–464, 33 `xy=`, target walks bottom edge, N 21→0 |
| V19 | `gAxis`+flip with **V18/V7 goal layout** (gDir=209,gDistToTgt=205) | ❌ broke | **E=0, D 779→945** → kills goal-number theory |
| V20 | V19 + probe **M=vecMed, S=vecSquare** | ⧗ deployed, untested | — |
| V21 | Re-anchor **home A to units' corner (5,11)**; A→B→A→C; M/S probe | ⧗ deployed, untested | — |
| V22 | **Latched adaptive home = vecMed at tag**; 2 perpendicular legs toward centre; M/S/H probe | ✗ misread of intent | user wanted FIXED home, not adaptive |
| V23 | FIXED home at A=(500,1100); A→B→A→C; **M/S probe** | ❌ broke — but EXPOSED THE ROOT CAUSE | M=ball~(620,500), **S=(-1,-1) off-map**, D=~800=dist(ball,(-1,-1)) |
| **V24** | **THE FIX:** init gAxis/gDir before flip, widen render to gAxis≤0/≥1, home back at (500,500). A→B→A→C oscillation | ✅ **WORKED** (user-confirmed 2026-07-08) | first correct A→B→A→C; the -1-default fix landed it |
| **V25** | **FINAL — continuous CLOCKWISE loop** A→B→D→C→A, no reversal. `gCorner` edge index 0..3 (only advances, mod 4) + `gE` 0..LEG per edge; 4 render rules; arrival-gated; STEP tunable | ⧗ deployed, awaiting test | sim: A→B→D→C→A, no off-map target |

Legend: ✅ works · ❌ fails · ◑ partial · ⧗ pending.

---

## Detailed per-version notes + raw data

### V6 — all-4-corner CCW loop (WORKED)
- `gS` = arc position 0..2400 around the whole perimeter (`sxy` render), advance one STEP
  (150) per pass while KITE-moving AND `D<ARRIVE(350)`; wrap mod 2400. No snapping.
- `try1.aoe2spgame`: **47 `xy=` targets logged**, units followed the loop. Confirmed working.
- Note: visits ALL 4 corners incl. the one nearest the units — which is (retrospectively)
  why it coupled.

### V7 — A↔B bottom-edge oscillation (WORKED)
- `sxy` render, `gS` oscillates `[0,600]` (bottom edge), reverse at both corners, seed
  `gDir` via reverse-at-A. Goals: `gS 204, gDistToTgt 205, gLastX 206, gLastY 207,
  gPacked 208, gDir 209`.
- User: "moved by ~150 each time, kite then stop and shoot." Confirmed working.

### V8 / V9 — leg state-machine A→B→A→C (BROKE)
- Added `gLeg` toggle (0=bottom,1=left) with `c:*-1` negate trick, leg0/leg1 render rules,
  init rule. Chat: "TAGGED … D2 SM EMPTY - tag did not stick", "D6 STATE22", no `xy=`.
- Blamed scenario/variance initially — **user corrected: same scenario/player as V6/V7.**

### V10 — signed gS (MILD FAIL)
- `gS∈[-600,+600]`, `gS≥0`→bottom, `gS<0`→left. User: "moving one by one, x changes ~1-2"
  (possibly working-but-slow, but rejected).

### V11 — arc teleport (BROKE)
- Keep `sxy`; teleport `gS 0↔2400` at home to switch bottom↔left edge. Units stuck at A.

### V12 — A↔C left-edge oscillation (WORKED)
- V7 with only the two arc bounds changed (`AMIN=1800,AMAX=2400`). `sxy` maps `gS∈[1800,2400]`
  to the left edge. Confirmed working. **Retrospect: left edge passes through the units' west
  location → coupled.**

### V13 — gAxis+flip with c:*-1 (BROKE)
- `gAxis` toggle via `c:*-1`. No coords, D6 STATE22. Prompted the `c:*-1` suspicion.
- **`c:*-1` is UNPROVEN:** base multiplies by positives (`c:* 100`, `c:* 4`) but never a
  negative; no known-good `.per` uses `c:* -1`. V8 & V13 (the two hardest fails) both used it.

### V14 / V15 — gAxis+gE+flip, subtract toggle (BROKE)
- Toggle rewritten as `gFlipTmp=1; gFlipTmp-=gAxis; gAxis=gFlipTmp` (no `c:*-1`). Goals:
  `gE 204, gDir 205, gAxis 206, gDistToTgt 207, …`.
- V15 raw: **E=0 the whole game; D stuck ~700–928; P alternates 118/122; N 21→0.**
- First excursion is logically identical to V7 (`gAxis=0` bottom edge) yet E never advanced.

### V16 — creep fix (PARTIAL)
- Kept arrival-gated fast march; ADDED slow timer step when `D≥350`. E climbed to 600/450
  (target moved) but D stayed ~700–800 (units still didn't follow). Not enough.

### V17 — no arrival gate, pure timer (FAIL, informative)
- March = advance `gE` every 700ms while tagged & state18, **no distance condition.**
- Raw (V17 `rec`):
  - `E: 150 300 450 600 450 300 150 0 0 150 300 450 600 … 0 … ` (cycles 0–600 fine).
  - `D: 779 755 744 719 714 744 747 671 … 620 600 582` (**never < ~580**).
  - `N: 21 → 0`. `xy` messages: **0.**
  - Triangulated unit centroid ≈ tile **(12.2, 11.1)** (fit RMS 67 precise) — i.e. hugging
    the corner the A→B→A→C pattern *never visits*.
- Lesson: removing the gate lets the target run away from units → they never couple.

### V18 — V7 + probe (CONTROL, WORKED)
- Byte-identical movement to V7 (verified: diff vs V7 = only the 3 probe goals + 1 probe rule).
- Raw (V18 `rec`):
  - `E: 300 450 600 … 150 … 0 … 600` (cycles).
  - `D: 112 452 362 281 464 422 376 328 139 178 … 64 127 134 … 81 124 … 77` (**mostly < 350,
    units ON the target**).
  - `xy`: **33 targets**, walking the bottom edge `(500,500)→(650,500)→…→(1100,500)→…back`.
  - `N: 21 → 0` (killed everything).
- Proves: **the arrival gate is essential and correct** (keeps target glued to units);
  V7/V18 couple because their target passes through where the units are.

### V19 — gAxis+flip with the WORKING goal layout (BROKE → kills goal theory)
- Same flip logic as V15 but goals remapped to V18's exact numbers: `gE 204, gDistToTgt 205,
  gLastX 206, gLastY 207, gPacked 208, gDir 209, gAxis 210, gFlipTmp 211`.
- Raw (V19 `rec`):
  - `E: 0` for the entire game (105+ samples).
  - `D: 779 753 793 797 815 845 … 916 949 904 … 945` (rises then plateaus ~945).
  - `N: 21 → 0`. `xy`: **0.**
- **Kills the goal-number theory:** identical critical-goal layout to V18, still fails.
- Video (`test1.mp4`, 20.5 s): units fight in the **west/left** region the whole game; my
  overlay put home A at `(5,5)` up top → 6–9 tiles away. `D≈800` is *honest distance to the
  wrong corner*, not (necessarily) a calc bug. Arrival gate never opens ⇒ E=0.

### V20 — M/S probe (UNTESTED)
- V19 movement + probe reports `M=vecMed` and `S=vecSquare` to settle whether D is real:
  `S=5000500 & M far` ⇒ ball genuinely far; `M≈5000500 & D~800` ⇒ `up-get-point-distance`
  bug; `S≠5000500` ⇒ render bug. **Deployed, not yet run** (user pivoted to redrawing corners).

### V21 — re-anchor home to the units' corner (UNTESTED, current best hypothesis)
- Per user's annotated frame (`IMG_7075`): home **A = the corner the units sit on** (west),
  B & C = the two adjacent corners, D = far corner unused.
- Implemented: home `A=(500,1100)` [tile (5,11)]; `gAxis 0 → (500,1100-gE)` up to `B=(500,500)`;
  `gAxis 1 → (500+gE,1100)` across to `C=(1100,1100)`. Arrival-gated; units start ON home so
  the gate should open at once. Keeps M/S probe. **Deployed, awaiting test.**

---

## ⭐ ROOT CAUSE (found V23→V24, 2026-07-08) — supersedes the "location mismatch" theory

The `M`/`S` probe in V23 exposed the actual bug: **`S=vecSquare=(-1,-1)` (off-map)** while
**`M=vecMed=~(620,500)`** (ball near the (500,500) west corner). `D≈800 = dist(ball,(-1,-1))`.
So the target was NEVER a valid square point in any `gAxis`-render version.

Why: **goals here default to `-1`, not 0.** The `gAxis` render only fires on `gAxis==0`/`==1`,
but `gAxis` defaults to `-1` AND the flip rule misfires on pass 1 (default `gDir=-1 < 0`) and
knocks `gAxis` to junk. So neither render rule fires and `vecSquare` keeps its `-1` default
→ `(-1,-1)`. The `sxy` versions (V7/V12/V18) worked purely because `sxy`'s first branch
(`gS < 600`) catches the `-1` default and always renders.

This **invalidates the earlier "location mismatch" conclusion** — the ball was near (500,500)
the whole time; `D≈800` was distance-to-garbage, not distance-to-a-far-corner. V16/V17's creep
"partially worked" only because their timer advanced `gE` regardless, but the target was still
`(-1,-1)` so the units never really followed.

**FIX (V24):** (1) one-shot `gInit` latch sets `gAxis=0, gDir=+STEP, gE=0` before the flip can
run; (2) render conditions widened to `gAxis<=0` / `gAxis>=1` so a render ALWAYS fires;
(3) home back at (500,500). **Lesson: goals default to -1 — every state goal that gates a rule
must be explicitly initialized, and equality-keyed renders must have a catch-all branch.**

**✅ V24 CONFIRMED WORKING in-game (user, 2026-07-08)** — the first version to correctly do
A→B→A→C oscillation. This closes the whole saga: the `-1` default was the root cause the entire
time. V24 is the recorded working baseline for the oscillation behaviour.

### V22 — latched adaptive home (SUPERSEDED, was a misread)
- At first tag, latched `gHomeX/gHomeY = vecMed` (ball's own position) + inward legs. Built on
  the (later-invalidated) "location mismatch" theory. User rejected the premise: home must be a
  FIXED map corner, not the units' current position. Not the fix; kept for the record.

### V23 — fixed home, M/S probe (BROKE, but cracked the case)
- FIXED home `A=(500,1100)`, A→B→A→C, `gAxis`-render. Probe reported `M=vecMed≈(620,500)` (ball
  near the west (500,500) corner) and **`S=vecSquare=(-1,-1)`** — an off-map target. `D≈800` was
  exactly `dist(ball, (-1,-1))`. This is the observation that produced the ROOT CAUSE above.

### V24 — THE FIX, A→B→A→C oscillation (✅ WORKED, user-confirmed)
- `gInit` latch initializes `gAxis=0 / gDir=+STEP / gE=0` before the flip can misfire; render
  widened to `gAxis<=0` (X leg) / `gAxis>=1` (Y leg) so a valid target ALWAYS renders; home back
  at `(500,500)`. Sim with `-1` defaults: no off-map target, correct A→B→A→C order. In-game:
  units patrol out-and-back between the two adjacent corners. **Recorded working baseline.**

### V25 — FINAL: continuous CLOCKWISE loop (deployed, awaiting in-game test)
- User's final call: out-and-back didn't help the fight as hoped → switch to a one-way loop
  around the full square, clockwise, never reversing: **A(500,500) → B(1100,500) → D(1100,1100)
  → C(500,1100) → A → …**
- Mechanism (all V24 lessons kept): `gCorner` (edge index 0..3, **only ever +1, mod 4** — no
  direction toggle) selects the edge; `gE` (0..LEG=600) is progress along it. Four render rules
  interpolate `vecSquare` from the edge's start corner toward its end corner:
  `e0 A→B (500+gE,500)` · `e1 B→D (1100,500+gE)` · `e2 D→C (1100-gE,1100)` · `e3 C→A (500,1100-gE)`.
  Edge-0 keyed `c:<=0` (catch-all for the `-1` default). `gE` marches `+STEP` **arrival-gated
  (D<350)**; at `gE>=LEG` reset `gE=0` and advance `gCorner`. End of each edge == start of the
  next (same corner) ⇒ `vecSquare` is continuous, no jump.
- **STEP (=150) is the "how far the units move each step" knob the user wants to tune next.**
- Goals 202–213: `vecSquare 202/203, gE 204, gDistToTgt 205, gLastX 206, gLastY 207, gPacked 208,
  gCorner 209, gInit 210, gDbgT 211, gProbe 212, gDbgTmp 213`.
- Validation: 133 defrules, changed base rules `{44,45,46,56,57,65}`, ALL CHECKS PASS. Sim trace
  confirmed `A→B→D→C→A`, zero off-map targets. Probe adds `C=gCorner` (should walk 0→1→2→3→0).

## Findings (final)

**Confirmed:**
1. **`.per` goals default to `-1`, not 0.** THE root cause of every `gAxis`-render failure
   (V14/V15/V19/V23): the equality-keyed render never fired, so `vecSquare` stayed at its `-1`
   default `(-1,-1)` off-map. Fixed by explicit init + catch-all render (V24). *This invalidated
   the earlier "location mismatch" theory* — the ball was near (500,500) all along; `D≈800` was
   distance-to-garbage `(-1,-1)`, not distance-to-a-far-corner.
2. **The arrival gate `D<350` is essential** — it keeps the patrol target coupled to the ball so
   the units follow. Removing it (V17) makes the target outrun the units (D stuck 580–780, no
   `xy=`). V6/V7/V12/V18/V24 all keep it.
3. **`sxy` versions (V6/V7/V12/V18) worked** only because `sxy`'s first branch (`gS<600`) catches
   the `-1` default and always renders a valid point — they dodged bug #1 by luck of structure.
4. Units spawn in the **same place every run** (user-confirmed) — cross-version differences are
   100% code, never RNG.

**Disproven / ruled out:**
- **Location mismatch** — invalidated by the V23 M/S probe (ball was near (500,500) the whole time).
- **Base goal collision** — base never uses goals 204–216; variants live at 202+.
- **Goal-number layout** — V19 used V18's exact working layout and still failed (it had the `-1`
  render bug). The earlier correlation was confounded with "has the flip".
- **Positioning RNG** — spawn is fixed.

**Convention kept as a precaution:**
- `c:* -1` (multiply by a negative) is unproven in `.per`; all toggles use subtraction
  (`gT=1; gT-=gAxis; gAxis=gT`). Never shown to be a real culprit, but avoided everywhere.

## Current status & next step
- **V24 = recorded working baseline (oscillation).** **V25 = final clockwise loop, deployed,
  awaiting the in-game test.** Run **V25**: expect `S` to read real corners, `D` small,
  `E` cycling 0→600 per edge, `C=gCorner` walking `0→1→2→3→0`, and `xy=` tracing
  `A→B→D→C→A` continuously.
- **Next tuning task (user-flagged, deferred):** `STEP` — how far the ball advances per march
  step — is the knob for "the amount the unit moves". Adjust `STEP` (and optionally `ARRIVE`) in
  `make_ddksquarev25.py` once the loop direction is confirmed good.

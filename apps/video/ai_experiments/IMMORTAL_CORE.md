# ddkImmortalCore — the working Immortal-style kite AI (definitive reference)

> **RENAMED 2026-07-05: `ddkImmortalCoreG` → `ddkModelAI`** (the going-forward AI; generator
> `tools/make_ddkmodelai.py`, SRC still `ddkImmortalCoreF.per`). Beyond the CoreG logic below it
> adds: (1) broader ranged recognition — Ballista Elephant + the melee-class throwers Gbeto /
> Throwing Axeman / Mameluke are found by unit type and kite too (charge one-shots like Fire Lancer
> are excluded); (2) a robust dynamic-enemy detector (self-excluding `up-find-remote` scan, replacing
> the unverified `up-find-player`) so it works assigned to P2 OR P3; (3) the test scenarios pair it
> against a melee side with AI = **none** (native aggressive chase). Everything in the "CoreG"
> sections below applies to ddkModelAI under the new name. See NOTES.md 2026-07-05 (evening).

**Status (2026-07-02): WORKING.** `ddkImmortalCoreE` kites + focus-volleys cavalry archers in editor
Test ("worked! you actually did it"); `ddkImmortalCoreF` adds 4-class generality (bolas/longbow/
arambai/hand-cannoneer) + a 600ms kite-dwell floor. **`ddkImmortalCoreG` (untested in-game)
implements the generalization plan items 1–4**: per-unit W_fire from the repo DB, reload-scaled
dwell, kite-only-when-out-ranging, speed-tiered strafe/step — see §CoreG below. Live copies in the
Steam ai dir (`…\AoE2DE\resources\_common\ai\`), backups + the extraction spec
(`immortal_core_spec.md`) in this dir.

## What it is

A 1:1 **transcription** of Immortal v0d10f's cavalry-archer control pipeline (extracted from its
compiled 115k-line `.per` by a line-verified analysis), reduced to one group / one tag / enemy = P3,
plus five environment fixes that Immortal's context hides. It is NOT a reinterpretation: every rule
cites its Immortal source rule/lines; every simplification is flagged `; DEVIATION` in the file.

**Pipeline** (85 rules; rules 0–77 are load-bearing absolute-jump targets, 78+ are diagnostics):

1. **TIME** — real milliseconds via `(up-set-timer c: 1 c: 0)(up-get-timer c: 1 g)`; `msecPerLoop` =
   delta per rules pass. All cadences are ms-based, not pass-counted.
2. **SN INIT** — 39 strategic numbers (3 blocks) that disable every engine tasking channel, plus an
   end-of-pass steady-state override (sighted-response 0/0, target-player). Without these the engine
   TacticalAI re-tasks ungrouped soldiers onto visible enemies every tick, overriding scripted orders.
3. **CLUSTERING** (~4s beat; every pass until the first tag) — snapshot into engine groups 8/9, then
   the tag-write trio: `up-create-group 0 0 c: 1` → `up-modify-group-flag _true c: 1` →
   `up-reset-group c: 1`. Tag = `object_data 73`. On first tag: **de-aggro the fresh ball**
   (`up-target-point 0 action-none formation-ignore stance-stand-ground` + `0 action-stop …`).
4. **STATE MACHINE** (every pass) — find by class, filter by tag, compute group stats: min speed,
   median range/attack, max reload, **median position** (per-axis sort), `%just-fired`
   (obj55 > reload−W_fire−10) and `%ready` (obj55 ≤ 110ms) via per-unit loops; enemy scan (focus-P3
   find-remote, **no filter-distance**), enemy median/nearest, `%in-range`, farthest-first sort.
5. **TRANSITIONS** (verbatim Immortal thresholds) — VOLLEY(22)→KITE(18) when just-fired% < 45 and
   ready% < 60 (or 3s cap; or enemy < 2.5 tiles with softer gates); KITE→VOLLEY when ready% ≥ 91 AND
   in-range% > 55 (CoreF: + ≥600ms dwell).
6. **KITE** — re-order throttle (state entry / 1200–2400ms beats); kite distance servo
   (= range·100 + clamp(corrections, ±500) − dist-to-enemy); strafe ±200; step **normalized to
   3.9 × slowest-member speed**; `up-bound-precise-point`; order = **double-issued
   `up-target-point vecKite action-patrol|move formation-line stance-no-attack`** (patrol vs ranged
   enemies, move vs melee), each wrapped `sn-target-point-adjustment 6 → order → 5`.
7. **VOLLEY** — round-robin focus fire: strip own units on cooldown (obj55 ≥ fire-window), per target:
   arrows-needed = HP·factor(115/160/100-ballistics) / max(attack − pierce-armor, 1), capped
   clamp(18 − dist_tiles, 6, 17); assign that many shooters; skip units already on-target; order =
   `up-target-objects _true action-default formation-ignore stance-ignore`; +99 (focus everyone) when
   ready units < needed+2.

## The five environment gotchas (each cost a failed in-game run to find)

1. **Not all `sn-*` names are builtin** — Immortal defconsts every one itself. Copy its ids or you get
   `invalid identifier` at load (one error = whole file dead, with an editor popup).
2. **`up-filter-distance` empties `up-find-remote` in our hand-written context** (confirmed twice:
   ddkKiteV3, CoreD's D7 trace). Never use it; prune with `up-remove-objects … object_data-to-precise`.
3. **`up-get-object-data 12` (max range) can return 0** — floor it (`c:max 4`). A zero range inverts
   the kite servo's sign → units step TOWARD the enemy.
4. **Units fighting under scenario-default AGGRESSIVE stance are unmovable by any order we tested**
   (move/stop/patrol, single/double, any formation). Prevention, not breaking: de-aggro units while
   FRESH (adoption halt idiom) and open with movement (boot state 18), never with attack orders.
5. **`up-get-search-state` slot 0 = LOCAL total; REMOTE total is slot +2.** Gating on slot 0 after a
   find-remote reads 0 forever.

**Debug technique that made it converge:** `(chat-to-player 1 "…")` IS visible in editor Test
(chat-to-all is not); one-shot latched diagnostic rules appended AFTER the last jump target (≤76)
trace the pipeline without disturbing the load-bearing rule numbering. A defrule holds ≤32
facts+actions (ERR6002); the game caches parses by filename per session (always ship fresh names).

## Tuning knobs (CoreG: per-unit values are goal-driven from the appendix)

| Knob | Where | CoreF | CoreG | Effect |
|---|---|---|---|---|
| W_fire fire-window | `gWfire` | 1000 fixed | per-unit table (60–827), appendix | bigger = units count as "busy firing" longer → later kite release |
| Ready window | Rule 0 `gReadyWin` | 110ms | unchanged | what counts as "loaded" for the 91% volley gate |
| Kite dwell | Rule 46 vs `gDwell` | 600ms fixed | clamp(reload−1400, 400, 2200) | min repositioning time before a volley can start |
| Kite gate | Rules 44/45 `gKiteOK` | — (always kite) | kite iff gRange > gERange+1 | ranged-vs-ranged holds VOLLEY = normal fight |
| Strafe magnitude | Rule 49 `gStrafeBase` | 200 fixed | 150/200/240 by speed tier | lateral component of each kite step |
| Step length | Rule 54 `gStepPct` | 390% fixed | 350/390/420% by speed tier | how far each kite step travels |
| Speed tiers | appendix | — | fast ≥135, slow ≤115 (obj13 ×100) | which strafe/step row applies |
| Re-order beats | Rule 48 | 1200/2400ms | unchanged | how often a standing kite order is refreshed |
| Servo clamp | Rule 53 | ±500, floor 50 | unchanged | max radial correction per step |
| Volley round-robin caps | Rule 69 | clamp(18−dist,6,17) | unchanged | max shooters per target |
| Melee fallback | appendix | — | gTagged==0 for 10s → engine auto-fight | pure-melee armies fight normally |

## CoreG — the generalization, IMPLEMENTED (2026-07-02, plan items 1–4)

Goal: every ranged unit kites with its own rhythm — **rate of fire** sets the fire/move cadence,
**movement speed** sets the step distance. Most of it was already structural (`%ready`/`%just-fired`
from live obj54/obj55; steps normalized to 3.9× slowest speed); CoreG makes the remaining constants
per-unit. All 30 new rules live in the **appendix (rules 85–114)** — they run at end of pass, values
apply next pass, the load-bearing 0–77 numbering never moves. Only 6 rules of working CoreF were
touched (0, 44, 45, 46, 49, 54), verified by structural diff.

**1. W_fire table from the repo DB.** Immortal's #1600–1605 (full extraction, richer than first
recorded: default 500; 350 archer/xbow/arbalest/HC; 635 camel/rattan/organ-gun/arambai/ballista-
elephant; 400 elephant-archer/CKN/mameluke/janissary/conquistador; 1000 war-wagon/CA/gbeto/
throwing-axeman; 0 elite-janissary; 800 slinger+elite-TA) keys on the ball's **modal
`object_data-base-type` (obj81)** + its `up-get-object-type-data … object_data-upgrade-type (obj82)`.
Those values are **stale AoC-era attack delays** (CA was 1.0s then; DE = 0.583s) — its arbalest row
runs a mere +17ms margin over the true delay and kites perfectly, proving W_fire ≈ delay works.
CoreG therefore uses **W_fire = `final_attack_delay`(ms) + 60ms release margin** from
`data/golden/aoe2_reference.db`, keyed on the **median ACTUAL type (`object_data-object-id` = obj1)**
— placed scenario elites resolve exactly even with zero researched techs — with class fallbacks
(900→310, 936→643, 944→310, 923→277) for unlisted/future types. Detection latches once
(`gWset` 0→1→2, chats "WFIRE SET").

### THE TABLE — every unit in the 4 controlled classes (dat class 0/36/44/23), DB-exact

| Unit (dat ids base/elite)              | delay ms | W_fire | reload ms | speed | range |
|----------------------------------------|---------:|-------:|----------:|------:|------:|
| Janissary 46/557                        |        0 |     60 |      3450 |  0.96 |     8 |
| Longbowman 8/530                        |      167 |    227 |      2000 |  0.96 |    12 |
| Fire Archer 1968/1970                   |      167 |    227 |      3500 |  0.96 |     9 |
| Composite Bowman 1800/1802              |      200 |    260 |      2000 |  0.96 |     7 |
| Genitour 1010/1012                      |      200 |    260 |      3000 |  1.49 |     7 |
| Conquistador 771/773                    |      217 |    277 |      2900 |  1.43 |     6 |
| Slinger 185                             |      233 |    293 |      2000 |  0.96 |     9 |
| Grenadier 1911                          |      233 |    293 |      3450 |  0.96 |     7 |
| Ratha (ranged) 1759/1761                |      233 |    293 |      1667 |  1.43 |     7 |
| Archer 4 / Crossbowman 24               |      250 |    310 |      1700 |  0.96 |   7–8 |
| Plumed Archer 763/765                   |      250 |    310 |      1615 |  1.20 |     8 |
| Genoese Crossbowman 866/868             |      250 |    310 |      1700 |  0.96 |     7 |
| Blackwood Archer 2579/2581              |      250 |    310 |      1500 |  1.10 |     8 |
| Camel Archer 1007/1009                  |      250 |    310 |      1700 |  1.54 |     7 |
| Hand Cannoneer 5                        |      250 |    310 |      3450 |  0.96 |     7 |
| Arambai 1126/1128                       |      250 |    310 |      2000 |  1.43 |     5 |
| Skirmisher 7/6, Imperial 1155           |      317 |    377 |      3000 |  0.96 |     8 |
| Chu Ko Nu 73/559                        |      317 |    377 |      2400 |  0.96 |     7 |
| Bolas Rider 2569/2571                   |      317 |    377 |      2000 |  1.50 |     7 |
| Arbalester 492                          |      333 |    393 |      1700 |  0.96 |     8 |
| Kipchak 1231/1233                       |      350 |    410 |      1870 |  1.62 |     6 |
| Mangudai 11/561                         |      383 |    443 |      1428 |  1.54 |     7 |
| Rattan Archer 1129/1131                 |      383 |    443 |      1700 |  1.10 |     8 |
| Elephant Archer 873/875                 |      400 |    460 |      1700 |  0.99 |     7 |
| Guecha Warrior 2562/2564                |      417 |    477 |      3000 |  1.15 |     7 |
| War Wagon 827/829                       |      533 |    593 |      2250 |  1.32 |     8 |
| Cavalry Archer 39 / Xianbei Raider 1952 |      583 |    643 |      2000 |  1.54 |     7 |
| Heavy Cavalry Archer 474                |      767 |    827 |      1800 |  1.54 |     7 |

(reload/speed are the DB's Imperial fully-teched modal values, shown for character reference; the
AI reads reload and speed LIVE via obj54/obj13, so un-teched scenario balls self-correct. delay is
tech-invariant. Base-form ids share the elite row where the DB is Imperial-only. Note CA W_fire
drops 1000→643 vs CoreF — the ball releases from a volley ~0.35s sooner, addressing "could move a
bit more before firing".)

**2. Reload-scaled dwell** (Rule 46 token swap + appendix): `gDwell = clamp(liveReload − 1400, 400,
2200)`. Mangudai (1428ms) re-volley after 400ms; CA (2000) after 600 (= CoreF's floor, unchanged
baseline); hand cannoneers/janissaries (3450) commit 2s repositioning arcs.

**3. Kite only when out-ranging** (Rules 44/45 +1 fact; appendix computes `gKiteOK = gRange >
gERange+1` from the enemy median range already read in Rule 36 — melee reads 0). Not-out-ranging →
transitions to 18 never fire → ball holds VOLLEY = normal stand-and-focus-fire; a 2.5s failsafe
(chats "HOLD") flips a stuck approach into VOLLEY. A **melee fallback** rule restores
`sn-percent-enemy-sighted-response`/`sn-task-ungrouped-soldiers` if no ranged ball forms in 10s, so
a pure-melee army under this AI fights normally instead of standing passive.

**4. Speed-tiered strafe/step** (Rules 49/54 token swaps): live min-speed ≥1.35 tiles/s → strafe
240 / step 420% (wide cavalry arcs); ≤1.15 → 150/350% (short foot-archer hops); else 200/390%
(CoreF defaults).

Still open:

5. **Validation matrix** — the scenario folder holds EXACTLY the 8 test scenarios, each with
   **ddkImmortalCoreG already picked for P2 inside the file** (just load in the editor and hit Test —
   zero setup): `ddk TEST CavArcher` (Huns) / `Bolas` (Mapuche) / `Longbow` (Britons) / `Arambai`
   (Burmese) / `HandCannon` (Turks) / `Elephant` (Bengalis) / `Mangudai` (Mongols) — 12 kiters vs 8
   knights, map 32 — plus `ddk TEST Blank` (empty arena, civ+AI set: paint any units, Test).
   Expected chats: `ImmortalCoreG up` → `TAGGED` → `WFIRE SET` → KITE/VOLLEY cycle; `HOLD` only in
   ranged-vs-ranged. *AI pre-pick mechanism:* `build_immortal_test.py --ai <name>` writes
   `PlayerDataTwo.ai_names[pid-1]` + `ai_type[pid-1]=0` (custom; 1=standard, 2=none) — the script is
   NOT embedded, so editing `ddkImmortalCoreG.per` flows into all existing scenarios. `--blank`
   skips army placement. Everything moved out of the game dirs lives in
   `C:\Users\ddk22\Games\Age of Empires 2 DE\ddk_backup\{ai,scenario}` (the game doesn't scan it);
   the ai dir keeps only CoreG + CoreF (fallback) + Immortal v0d10f (comparator).
6. **Obstacle arena regression** — 5 staged layouts (`build_immortal_test.py --obstacles <name>`,
   CA vs knights, dirt, AI pre-picked): `ddk TEST Obst Line` (palisade line across the kite path +
   flank tree clumps) / `Obst Block` (two 4×4 tree blocks = dodge-behind cover) / `Obst Pillars`
   (seven 2×2 pillars = slalom) / `Obst Choke` (map-wide wall, one 5-tile gap = funnel) /
   `Obst Pocket` (L-wall around the NE corner = the classic trap). Walls are P1 palisades
   (obj-detect 927), trees Gaia (915). The transcription inherits Immortal's wall-blindness —
   expect it to jam into these; that's the baseline for layering on the point-contains flip +
   Illuminati path fan-out (both parse-proven from the earlier line).

## File lineage

`ddkImmortalCore` (parse fail: sn names) → `B` (+40 sn defconsts) → `C` (+move-first opening, de-aggro
on tag, tag-before-beat) → `D` (+diagnostic trace; found D7 scan empty) → `E` (−filter-distance,
+range floor — **first working**) → `F` (+4-class generality, +600ms dwell) → `G` (per-unit
parameterization from the repo DB: W_fire table + reload dwell + kite gate + speed tiers, 30 appendix
rules, generated+validated by script — untested in-game). Earlier exploration lines
(ddkTesterAI/2/3 = patched Immortal; ddkMicroV1-V10 + probes = the experiments that discovered gotchas
1–5) are retained in this dir; `NOTES.md` is the journey log.

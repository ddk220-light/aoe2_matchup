# ETG in-game validation runs — 2026-07-19

Scenarios built by `apps/video/build_etg_validation.py` from the golden templates at the
V2 arena counts (same counts as the sim rows — 1:1 comparable). Run via editor **Test**
mode, windowed; outcomes read off the battlefield (survivor counts approximate, from
screenshots; no HP decode). ETG = P2 on ddkMatchupAI patrol except vs Guecha
(rangedvsinf template: Guecha kites on P2, ETG on P3/NoneAi).

| Matchup (counts) | V2 pre-fix | In-game runs | Verdict |
|---|---|---|---|
| Elite Konnik 21v17 | coin_flip, 67% ETG, bimodal | **ETG 3–2** (5 runs). ETG wins razor-thin (1–3 of 21 alive); Konnik wins decisive (up to ~14/17 incl. dismounts) | ✅ coin_flip confirmed, bimodal confirmed |
| Elite Cataphract 21v15 | 0% ETG, S −62 | **Cataphract 1–0**: ~12–13 of 15 standing, ETG wiped | ✅ unexpected_loss confirmed |
| Elite Guecha 21v20 | coin_flip, 27% ETG, S −6 | **Guecha 3–0**, keeping 50–100% of 20 (kites the slower ETG all game; one aborted extra run showed ETG cornering them mid-fight — the loss basin exists) | ❌ sim under-rated the kite → **KITE fix** (see below) → now expected_loss, S −52 ✅ |
| Warrior Priest 17v21 | coin_flip, 73% ETG (both shredded) | **WP 2–0**, keeping ~15–16 of 21 | ❌ WP heal aura NOT in its combat dict (no heal/regen field) — unmodeled-mechanic pin `loss` added (WFG precedent) |

| Condottiero 15v21 | coin_flip, 47% ETG (both shredded, 5%/6% HP) | **ETG 4–1** (5 runs); every win thin on BOTH sides (ETG wins with 2–5 of 15, Condo win with ~4 of 21) | ✅ coin_flip confirmed (game leans ETG; within 5-run noise of 47%) |
| Paladin 21v16 | 100% ETG, S +38 | ETG decisive, ~8 of 21 alive, all Paladins dead | ✅ anchor confirmed (also: no delayed-melee churn-bypass bias visible) |
| Elite Battle Elephant 21v14 | 100% ETG, S +37 | ETG decisive, ~5–6 alive, all elephants dead | ✅ trample calibration holds |
| Champion 12v21 | 0% ETG, S −48 | Champion decisive, ~14 of 21 standing | ✅ anchor confirmed |

Not re-run: Huskarl (already the most-validated matchup — 20 decoded runs from the
original calibration). All 8 deployed `etg_*` scenarios remain in the game scenario
folder for future re-runs.

## KITE fix (the engine change this validated)

`moveAwayFromTarget` retreats straight away from the chaser and clamps to the 900×600
canvas → kiters wall-pin in seconds, so a FASTER ranged unit could never use its speed
edge the way the real arena + patrol AI allows. `KITE=1` (headless_sim.js transform,
baked into sim_v2_model.js): when the retreat step would leave the arena, slide along
the boundary toward whichever axis step ends farthest from the pursuer.

A/B (10 seeds, same seeds both sides):

| Row | KITE off | KITE on | game |
|---|---|---|---|
| Guecha 21v20 | 30% ETG, S −4 | 0% ETG, S −48, Guecha keeps 54% | 0/3 ETG, keeps 50–100% ✅ |
| Genitour 11v21 | 40% ETG | 10% ETG, S −16 | (not run; fast kiter, plausible) |
| Arbalester 14v21 | 0%, S −50 | 0%, S −75 | loss either way ✅ |
| Konnik 21v17 | 60%, S +1 | **bit-identical** | ✅ melee untouched |
| Huskarl 13v21 | 40%, S −6 | **bit-identical** | ✅ melee untouched |

Full 74-row re-sim + re-categorization: Guecha & Genitour coin_flip → expected_loss;
all slow-ranged losses more decisive; zero melee rows moved; Arambai & War Elephant
pins retired (sim earns both natively post GRAZE_K/TRAMPLE_K). Final split:
**23 EW / 0 UW / 3 CF / 2 UL / 48 EL.**

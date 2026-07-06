# Elite Temple Guard — locked picks & implementation deltas (2026-07-05)

Pilot subject for the unit-analysis-video feature. Categorization computed from the
**real batch baseline** `C:\AI\matchup_baseline_177723.db` (not local sims), using the
approved rules in `2026-07-04-unit-analysis-video-prototype.py`. This file pins the
finalized picks + the deltas the DB source and user decisions introduce.

## Subject
`Elite Temple Guard` / civ `Muisca` / slug `elite_temple_guard_muisca`
(115 hp, 16 atk, 5 melee / 6 pierce armor, 1.05 speed, +8 vs Cavalry; 70f 45g).

## Data source (delta vs plan's MatchupDbSource)
- Read **`matchup_means`** (multi-seed aggregate), NOT one `matchup_battles` row:
  `SELECT mean, sd, n, verdict FROM matchup_means WHERE my_civ=? AND my_slug=? AND opp_civ=? AND opp_slug=? AND scale='3k'`.
  `mean` is subject-positive S ∈ [−100,100]; both orientations are stored mirror-consistent.
- hp-left / counts for the storyboard come from the representative `matchup_battles` row
  (team1 = subject).
- **`sd`/`n` are new signals**: use low `sd` as a recording tiebreak so a filmed fight
  never contradicts its caption (e.g. Heavy Cav Archer vs TG is a genuine coin-flip,
  sd≈24 over 40 seeds — never pick it).
- Missing pair → skip with a warning (only `siege_onager` was missing; now dropped anyway).

## Opponent pool
- Uniques from `apps/video/auto/unique_units.json` + 12 generic staples.
- **Dropped `siege_onager`** staple (user: exclude mangonel/scorpion units). No scorpion/
  mangonel unit remains in the pool.
- **Kept Ballista Elephant** (Khmer, Ballista-class): a unique bolt-shooter, neither
  mangonel nor scorpion (user decision). Lands at expected-counter −63, not a pick.
- 75 opponents → 37 wins / 36 losses / 2 even.

## Pick-rule delta (expected_counter)
Default prototype rule = margin sort. **User override (2026-07-05):** the three filmed
expected-counter fights are a MIX, not three identical instant wipes —
**1 gunpowder shock + 2 iconic archer counters**. Curated trio (by slug):
`grenadier_jurchens`, `elite_chakram_thrower_gurjaras`, `elite_chu_ko_nu_chinese`.
Everything else (expected_win / unexpected_win / unexpected_counter picks, all
category_lists) uses the prototype's rules unchanged.

## FINAL 12 PICKS
| Category | #1 | #2 | #3 |
|---|---|---|---|
| expected_win | Heavy Camel Rider · Persians · +88 | Elite Tarkan · Huns · +70 | Elite Shrivamsha Rider · Gurjaras · +69 |
| unexpected_win | Elite White Feather Guard · Shu · +46 | Elite Ibirapema Warrior · Tupi · +36 | Elite Huskarl · Goths · +43 |
| expected_counter | Grenadier · Jurchens · −100 | Elite Chakram Thrower · Gurjaras · −94 | Elite Chu Ko Nu · Chinese · −93 |
| unexpected_counter | Elite Urumi Swordsman · Dravidians · −21 | Elite Obuch · Poles · −31 | Elite Serjeant · Sicilians · −36 |

(unexpected_win order is by pick-rule sort — bonus asc, S asc.)

## Intro assets (downloaded from Railway bucket `aoe2-assets-prod`)
`apps/video/media/units/elite_temple_guard_muisca/` (gitignored):
- `attack.gif` — 720×672, 45 frames (the hi-res attack animation)
- `sprite_full.png` / `sprite_full_blue.png` — 432×432 dat4x sprites
- `transparent.png` — 256×256 transparent icon

No AI-generated cinematic image exists for TG yet — `generated/youtube/<slug>_vs_all.png`
covers only 6 units (blackwood, guecha, kona, leitis, mangudai, woad_raider). If a
cinematic intro image is wanted, it needs generating via the flux2/nanobanana pipeline.

## Recording route (Phase 2)
Adapt the golden_template + `ddkModelAI` scenario/AI rig into the EXISTING record →
background-stat-monitor → overlay pipeline (user decision), rather than the old OCR-nav
default3 flow. Melee side also fights (no `NoneAi` needed). 16×16 arena, 21-unit cap →
storyboard `counts` should carry the 21-cap equal-resource trim, not the DB's 30-cap.

Storyboard artifact (regenerable, gitignored):
`apps/video/media/units/elite_temple_guard_muisca/storyboard.json`.

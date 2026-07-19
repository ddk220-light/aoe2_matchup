# Short-form Reel — design

A vertical (9:16) ~15s cut for Instagram Reels / YouTube Shorts / TikTok, built as a
**post-process on already-recorded matchup fights** — no game required. It reuses the
existing overlay stack (`apps/video/overlay/`): the gRPC HP sidecar, the Pillow HP-bar
band (`hud.py` / `overlay_hp.py`), the speed-ramp + concat machinery (`compose.py`).

## Canvas & layout (1080×1920)

The captured 16:9 gameplay is **fit to width (never cropped** — the two armies are
column-seated at the LEFT/RIGHT edges of the arena, so a center-crop would cut off the
combatants). 2560×1440 → **1080×608**, placed in the middle; the leftover vertical space
becomes the top/bottom overlay bands.

```
┌───────────────────────────┐  y=0
│  TOP band (520px)         │   subject: verdict chip + NAME + hero sprite
├───────────────────────────┤  y=520
│  gameplay 1080×608        │   the raw fight footage (fit to width, uncropped)
├───────────────────────────┤  y=1128
│  BOTTOM band (792px)      │   live HP bar (icons+names+counts+HP) + "why" caption
└───────────────────────────┘  y=1920
```

Constants live in `overlay/reel_compose.py` (`CANVAS`, `GAME_Y`, `HUD_Y`, `WHY_Y`).
The bottom **HP bar is the existing `hud.py` band** rendered full-width — its name tabs
already carry both unit icons + names + live counts, so it doubles as the "versus"
element. The lowest ~200px is left low-priority (platform UI — captions/buttons — sits
there).

## Timeline (~15s)

| Segment | ~len | Source |
|---|---|---|
| Intro hero card | 2.6s | `reel_cards.render_intro_hero` → `_card_segment` |
| Fight A | ~5s | `make_reel_fight` (tight ramp) |
| Fight B | ~5s | `make_reel_fight` (tight ramp) |
| CTA card | 2.2s | `reel_cards.render_cta` → `_card_segment` |

**Tight ramp** (`make_reel_fight`): keep ~1.3s of the clash + ~1.6s of the kill at 1×,
sprint the middle to ~2.2s at an **integer** factor (same anti-judder rule as the
long-form). Fights self-limit to ~5s regardless of raw length.

## Which matchups (selection)

Driven by the V2 categorization JSON (`apps/video/sim_v2/results/<subject>.json`,
`showcase` block). Rule (`build_reel.select_reel_matchups`), capped at 2, favouring the
*surprising* content:

1. `unexpected_win` (top) + `unexpected_loss` (top) if both exist.
2. If none → `expected_win` (top) + `expected_loss` (top) — show the unit's range.
3. If only one unexpected → pair it with the **opposite-valence** expected pick
   (e.g. a surprise loss + the best expected win).

"top" = the first showcase pick already chosen by the long-form pipeline (wins: most
expensive; losses: cheapest), so the short stays consistent with the full video.

The verdict chip label/colour comes from the row's `category`
(`expected_win`/`unexpected_win`/`expected_loss`/`unexpected_loss`).

## Modules

| File | Role |
|---|---|
| `overlay/reel_cards.py` | Pillow band/hero/CTA cards (no headless browser) |
| `overlay/reel_compose.py` | vertical single-pass fight compositor + intro/CTA + stitch |
| `auto/build_reel.py` | selection + resolve raws/sidecars + orchestrate (CLI) |

## Data dependency (important)

`make_reel_fight` needs **raw `.mov` + `.hp.json`** (clean gameplay for the middle band),
exactly like `recompose_from_raws`. The finished `<subject>_v2/*.mp4` clips already have
the horizontal HP bar + detail cards burned in, so they are NOT a valid source.

A subject can be cut into a reel once it has BOTH a categorization JSON and its raws on
disk. (As of 2026-07-07 the Temple Guard raws were overwritten by the later Bolas Rider
sweep — re-record with `run_guecha_sweep --record-only` to cut the ETG reel.)

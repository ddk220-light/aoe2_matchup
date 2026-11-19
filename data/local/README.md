# data/local

`data/local/` is the machine-local workspace for the video pipeline. Campaign
work folders, plans, status reports, logs, recordings, frame streams,
credentials and DAT extractions are all written here, and **none of it is in
Git**. Past runs are archived on the recording share, not in the repository.

Git tracks only the exact map and AI inputs below, at the paths the prepare
scripts read. The allowlist is the `data/local` block in the root `.gitignore`.

| Path | What it is | Read by |
|---|---|---|
| `arena-theme-review/scenarios/*.aoe2scenario`, `arena-theme-review/*.aoe2scenario` | Map drafts built from the Golden: 10 civ themes, 20 biome A/B variants, and the winter studies. `Winter Campaign Study - Detailed Battlefield` is the Arena scenery source; `Biome 01A - Winter Scenic` is the older Norse scenery source. | `prepare_detailed_standard_capture.py`, `prepare_norse_standard_capture.py` |
| `arena-theme-review/*.py`, `REVIEW.md`, `campaign-study/winter-*.json` | Theme-map builders and their notes and inputs | Run by hand when making new map themes |
| `legacy-kiting-preview/` | Approved Winter Rock scenery, `golden_rangedvsinf`, and the `ddkRockQuietAI` / `ddkRockPreviewAI` source scripts | `prepare_arena_donut_capture.py` (builds the Donut template and its quiet AI) |
| `arena-donut-standard/donut-template/` | Frozen Winter Donut template, audit, and `ddkDonutQuietAI.per` exactly as captured | `fix_jarl_opening_patrol.py`; scenario validation |
| `jarl-kiting-followup/donut-template/` | Donut opening-patrol and army-patrol variants | Jarl follow-up plans |
| `slinger-donut-timing/donut-template/` | Donut variant with `ddkDonutSlingerTiming.per` | Slinger timing plans |
| `detailed-standard-norse/winter-templates/`, `scenery-source/` | Frozen Arena winter Goldens (4 families) with audits | Arena scenery plans |
| `norse-standard-capture/winter-templates/` | Older Biome-01A winter Goldens with audits | Norse plans |

On a fresh machine, regenerate everything else:
- **DAT extraction:** `python scripts/audit_installed_dat.py` writes `data/local/dat-release-audit/`.
- **Pickled DAT:** `python scripts/cache_installed_dat.py` writes `viking-sagas-research/installed-dat.pkl`, which the winter-scenery prepare scripts need.
- **Campaign folders:** run the `apps/video/prepare_*.py` script for that campaign.

See [OWNERS_GUIDE.md](../../docs/video-production/OWNERS_GUIDE.md) §9.

# apps — the outcome surfaces (layer 5)

| App | What | Deploy |
|---|---|---|
| `web/` | aoe2matchup.com frontend (Astro) — battle sim, rankings, civ pages, matchup advisor, patch tracker; header/footer in `src/components/site/`, styles in `src/styles/`, page code in `src/features/` + `src/pages/`, live public files in `static/` | Vercel `frontend` service (root `vercel.json`): `scripts/migration/build_service.sh frontend` → `npm run build` (staging→main promotion; data ships as commits under `data/golden/`) |
| `backend/` | aoe2matchup.com JSON API (Flask) — `app.py` entrypoint + `aoe2_api/` package (`web.py`, `routes/`, `services/`, `data/`) | Vercel `backend` service: `scripts/migration/build_service.sh backend`, entrypoint `app:app` over the sealed `runtime/` |
| `viewer/` | standalone replay viewer (the old aoe2record visualizer) — thin shell mounting `aoe2x.replay` at / | `apps/viewer/Dockerfile`, build context = repo root |
| `video/` | matchup-video automation: scenario gen → drives the real game (pydirectinput + OCR) → ffmpeg capture + gRPC HP sidecar → overlay/compose → MP4 + YouTube chapters.txt | local only — see `apps/video/RUNBOOK.md` |

Apps are thin: pages/API adapters/automation only. Logic lives in `aoe2x/*`,
data in `data/golden/`. Build-time page data comes from `scripts/migration/`
(`prepare_release.py`). Production deploys from this monorepo on Vercel (see
`docs/vercel-deployment.md`); the old Flask website and Railway are retired.

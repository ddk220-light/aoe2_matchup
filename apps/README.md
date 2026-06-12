# apps — the outcome surfaces (layer 5)

| App | What | Deploy |
|---|---|---|
| `website/` | aoe2matchup.com — battle sim, rankings, civ pages, matchup advisor, patch tracker, embedded replay viewer at /replay | root `railway.json`: `cd apps/website && gunicorn app:app` (staging→main promotion; data ships as commits under `data/golden/`) |
| `viewer/` | standalone replay viewer (the old aoe2record visualizer) — thin shell mounting `aoe2x.replay` at / | `apps/viewer/Dockerfile`, build context = repo root |
| `video/` | matchup-video automation: scenario gen → drives the real game (pydirectinput + OCR) → ffmpeg capture + gRPC HP sidecar → overlay/compose → MP4 + YouTube chapters.txt | local only — see `apps/video/RUNBOOK.md` |

Apps are thin: pages/templates/automation only. Logic lives in `aoe2x/*`,
data in `data/golden/`.

NOTE: production currently still deploys from the pre-merge repos
(aoe2-unit-analyzer, aoe2record). Re-pointing the Railway services at this
monorepo is the deliberate, separate cutover step.

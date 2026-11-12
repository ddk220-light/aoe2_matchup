# Vercel deployment

Production is `https://aoe2matchup.com` in Vercel project
`aoe2-matchup-migration`, team `ddk220`. The production branch is `main`;
other branches receive protected previews. The old Railway service is retired.

The repository root `vercel.json` deploys the existing Astro frontend and Flask
API as two services. Each service runs `scripts/migration/build_service.sh` to
rebuild its sealed inputs from the committed source, databases and public media
manifests. Generated `apps/web/public`, `apps/web/src/generated` and
`apps/backend/runtime` directories remain ignored; a developer's checkout is
not a deployment dependency. Media and retained client assets are downloaded
from the existing public Blob URLs and verified against their SHA-256 manifests.

The `vercel-build` CI job generates both services, verifies their manifests,
smokes the packaged API and builds Astro from a clean checkout. The `test` job's
API contract tests (which import `aoe2_api.web` directly) and the retained
legacy engine contracts remain required validation.

Website presentation lives only in the Astro app (`apps/web`): the site header,
footer (`apps/web/src/components/site/`), base styles (`apps/web/src/styles/`),
every page's markup and scripts (`src/pages/`, `src/features/`) and the live
public files in `apps/web/static/{img,js}`. The Flask service (`apps/backend`:
`app.py` plus the `aoe2_api` package) serves only `/api/*` and
`/_internal/release`; every other path 404s there. Page titles, meta, links,
JSON-LD, page fragments and the sitemap are produced at build time by
`scripts/migration/prepare_release.py` (the `export_*.py` scripts and the
builders in `scripts/migration/site/`, whose only templates are the verbatim
snippets in `scripts/migration/site/templates/`). The former `apps/website`
Flask site has been deleted. The retired browser engine and page scripts live in
`legacy/client/` for parity and research tests only and are never published;
authoring copies of unit art, animations and media manifests live in
`data/media/`. Preview checks must cover affected pages and API calls, plus a
completed simulator battle.

Locally, `python scripts/migration/prepare_release.py` followed by
`npm run dev --prefix apps/web` serves the pages, and
`cd apps/backend && flask --app app run` serves the packaged API from the sealed
`runtime/` (Python 3.13). The Astro dev server does not proxy `/api/*`, so
check API-driven pages end to end on a preview deployment.
`python scripts/migration/verify_build.py` smokes the packaged API, and
`npm run build --prefix apps/web` refuses sources changed after sealing. Restore
`vercel.json` with `git checkout vercel.json` after a local seal unless the data
itself changed.

For a release, check the exact branch commit and both CI jobs, then verify its
Vercel deployment. A READY state alone is insufficient: request `/`, `/units`,
`/civilizations`, `/api/ref/unit-line/militia`, and a battle configuration. Test
public custom domains after promotion. If production was rolled back, explicitly
promote the tested production deployment to restore automatic domain assignment.

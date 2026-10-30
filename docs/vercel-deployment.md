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
smokes the packaged API and builds Astro from a clean checkout. The original
website/engine contract tests also remain required validation.

After changing website presentation, carry equivalent behavior into the Astro
components/features as well as the original Flask templates/scripts. Both use
the same exported API data, but their frontend code is separate. Preview checks
must cover affected pages and API calls, plus a completed simulator battle.

For a release, check the exact branch commit and both CI jobs, then verify its
Vercel deployment. A READY state alone is insufficient: request `/`, `/units`,
`/civilizations`, `/api/ref/unit-line/militia`, and a battle configuration. Test
public custom domains after promotion. If production was rolled back, explicitly
promote the tested production deployment to restore automatic domain assignment.

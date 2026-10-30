# Finalized unit rankings publication

The `/units` table now serves the accepted 555 civilization/unit scores across
56 civilizations and 10 categories. Shock infantry joins militia (91 entries);
elephants and steppe lancers join knights (70). The other category counts are
spear 56, archer 65, skirmisher 57, cavalry archer 59, scorpion 58, gunpowder 35,
light cavalry 51, and camel 13.

## Data identity and rebuilding

- Accepted source commit: `8d55b813b0cb8991d2eeb1122cc99d28f34c0f5d`
  on `simulations/v3-path-recovery-2026-10-29`.
- Dataset hash: `17a91c8fa14553abbce1f894cbeb4e637d9fe9a82977fc2da2b0bc824cfade3c`.
- `data/golden/unit_rankings_final.json` contains the approved scores, 3,591
  opponent rows, validation records, and original/corrected engine identities.
- `data/golden/aoe2_reference_rankings.db` is the exact reference snapshot used
  to display the campaign's units, stats, upgrades and abilities. Its SHA-256 is
  `234ad0a6c40e413563f737886f6eed2e71c0de41a6a373b569d34dbcaa5c0216`.
- Rebuild with `python -m aoe2x.rank.build_finalized_serving_db`. It verifies the
  reference identity, coverage and score calculations before publication.
- The serving database uses build key `rankings:17a91c8fa14553ab`, separate
  from the legacy game-build key. Historical rows are preserved byte-for-value
  for civilization/Advisor consumers. Siege and naval rankings retain their
  previous results. No browser simulator engine or input database changes.

The accepted consolidation includes 7,600 selected required runs: 6,768 from
the original engine and 832 from the corrected engine, covering 2,398 distinct
matchups. The mixture is intentional, with version counts retained per unit;
this release does not represent a homogeneous rerun.

## Score contract

The cheaper side fields 27 units; the opposing count is
`round(27 * sqrt(cheaper weighted cost / expensive weighted cost))`, with
food/wood/gold weights 1/0.9/1.1 and zero buffers. Each matchup starts with
seeds 0–2, adding 3–9 when initial decided outcomes differ.

A win contributes own surviving HP percentage, a loss negative enemy surviving
HP percentage, and a draw zero. Average runs within each matchup, then opponents
equally. Score is `50 + mean signed HP percentage / 2`, with no additional
mobility, range or cost multiplier. Category ranks preserve ties in unrounded
scores. Tooltips and CSV include the actual five or seven tested opponents.

## Verification

- All 555 API scores, category ranks and provenance counts checked against the
  approved source; all 3,591 opponent values reconcile with each final score.
- Builder rebuild preserves both finalized rows and all historical score rows;
  mismatched reference inputs are rejected before output mutation.
- Website Python contract: 488 passed, 26 skipped; two additional builder tests
  passed. JavaScript engine/frontend gate: 442 passed, plus projectile and
  simulator parameter scripts passed.
- Chromium checks: all three land tabs, category filters, descending scores,
  merged-category deep links, CSV export, new civilizations, mobile table and
  score popup; zero JavaScript errors.
- Production baseline `2581cd35` had stale simulator digest/roster tests and a
  test depending on an uncommitted local input. Expectations now use the already
  committed production artifacts. Independently captured base/release API,
  battle-config and five replay hashes are identical; no engine change occurred.
- Only ranking and methodology sitemap dates advance; unrelated content retains
  its own data date.

Direct external HTTP checks are unavailable from this cloud environment because
its outbound domain policy excludes the website. Deployment success is checked
through Railway's GitHub commit status; browser checks above use the local app.

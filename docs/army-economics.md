# Army economics in Battle Simulation

For a fresh checkout, captured-data restoration and the implementation map, start
with [the matchup timings handoff](matchup-timings-handoff.md).

The page/API implementation is available for **local review** and passes the
current user-approved release requirements. Khitan pastures use an online average
with immediate food credit; in-game gathering measurements were deferred by the
user on 2026-11-11. All gathering figures remain estimates, without a claim of
less-than-1% measured error. Public behavior defaults to off. No existing combat
campaign, reference mechanics database, rankings, or saved matchup outcome has
been rewritten.

## Run and inspect

```sh
python -m pip install -r tools/requirements-economy.txt
python tools/build_army_context_runtime.py
ARMY_ECONOMICS_MODE=review python -m flask --app apps.website.app run --port 5055
```

Open `http://127.0.0.1:5055/` and select both teams. The three summaries appear in
the existing team panels. Their details link opens the comparison below the
arena. Actual resolved army counts are used in preview and during playback.
The headline is **60-second army investment**, measured in weighted
villager-minutes. Common research costs enter the score; research speed,
exclusive upgrade packages and full research workload remain separate.

Configuration:

- `ARMY_ECONOMICS_MODE=off` (default): existing page/cost policy; context endpoint disabled.
- `review`: enable the comparison with explicit estimates and null results for unresolved mechanics.
- `released`: requires `releaseReady=true` in the compiled data; otherwise context is unavailable.
- `ARMY_CONTEXT_DB`: optional runtime database location; defaults to `data/golden/army_context.db`.

Release eligibility and validation are separate. The current API reports
`status: estimate` and `gatheringValidationPolicy.requiredForRelease: false`,
including in released mode. The UI explicitly labels estimated gathering rates
and deferred measurements.

Generated artifacts are `data/golden/army_context.db` and
`data/golden/army_context.validation.json`. The runtime database covers 56
civilizations and 1,031 profiles (1,030 units plus the War Chariot barrage mode).
It is about 30 MiB, compared with the 145 MiB source review database. Runtime
requests do not read scratch files or require SciPy. Restart the server after
changing application code/configuration; generated data is versioned and cache
entries follow atomic file replacements.

The source is the supplied DAT archive, SHA-256
`d0aefd92428e2215d6f4d9b1d544901e6f171e19183f9e0b88218de5153a337f`.
It contains verified patch 188329 changes. Its exact executable build is unknown;
the implementation does not claim this is the latest available game patch.

## Accounting and interface

`POST /api/v3/army-context` (response schema 3) accepts the same selections and army options as
`/api/v3/battle-config`, plus optional `contextVersion` and
`convertedVillagers: [integer_or_null, integer_or_null]`. It uses the same resolver
and returns actual counts, pricing, production routes, technology packages,
infrastructure, evidence, assumptions, `investmentComparison`, and lookups from zero
through each starting count. `lookup` describes fresh purchases;
`replacementLookup` credits initial batch surplus before buying replacements.
The response also supplies `trainingWindowSeconds: 60` and resource weights
`{food: 1, wood: 1, gold: 1.5, stone: 3}`. A stale version returns 409; schema-1/2 databases and missing/incompatible data
returns 503. Combat still works if context is unavailable; both sides revert
together to the existing price policy, never a partially corrected pair.

- The headline combines the displayed army's purchase bill, the selected
  production buildings, and the **net cost of common military technologies**.
  Common means the intersection of deduplicated technology IDs, including free
  technologies. Guaranteed completion refunds offset the combined bill; upfront
  prices stay visible. Unresolved common variable costs withhold the score.
- Apply food ×1, wood ×1, gold ×1.5 and stone ×3 to that combined bill, then
  evaluate the civilization's economy model. The result is weighted
  villager-minutes, an explicit scarcity preference rather than elapsed game
  time or a simulation of resources running out. Weights affect this comparison,
  not army count resolution or combat prices.
- Labor minimizes total villager-seconds over resource output vectors. Farm wood
  is a negative recurring input; reseeding downtime is already in the rate.
  Coproducts satisfy the combined bill without double credit or resale of surplus.
  Standalone component work is shown for explanation and need not sum to the
  pooled optimum. Existing reviewed resource layouts and activation assumptions
  remain unchanged; no unverified special-effect coefficient is inserted.
- The compiler enumerates the resource-price vertices of each complete economy's
  labor-program dual. The endpoint evaluates their linear functions for the
  selected pair's combined bill, with the same optimum as the offline solver.
  It requires no runtime SciPy, browser optimizer or animation-loop calculation.
  Unresolved economies have no compiled prices and no headline score.
- Purchases are indivisible: `Q = ceil(units / batch size)`. A 27-unit
  Blackwood Archer army requires 14 orders, pays for 28 units and keeps one extra
  for replacements. That spare covers the first casualty. Replacement lookups
  round cumulative demand, so subsequent spare units are also retained.
- Each production route completes `floor(60 / secondsPerOrder)` orders per
  building in the window. Required buildings are `ceil(Q / ordersPerBuilding)`.
  Select the route minimizing **combined weighted villager work**, with faster
  actual queue completion and then lower building ID breaking ties. Known
  infrastructure can be provisionally ranked by weighted resource prices while
  labor is unresolved, but no investment comparison is reported in that case.
  If no purchase can finish within 60 seconds, report that explicitly.
- The 60-second production window starts with buildings, technologies and
  resources ready. The headline covers resource collection, not villager
  construction animations or a build-order schedule. Research-building costs,
  economic setup, production upgrade investment and exclusive military packages
  remain separately inspectable; none is silently added to the headline.
- Building setup and common research are paid once. Live replacement work covers
  casualties only, using the same resource weights and existing buildings; it
  credits batch surplus and never charges research or buildings again. The
  starting-army score stays fixed through playback. The comparison reports the
  percentage by which one army's investment is lower than the other's; identical
  scores tie, and unavailable inputs withhold the comparison.
- Research lists combat upgrades and training unlocks, production upgrades, and
  economic setup separately. Each technology occurs once across these packages.
  Common IDs determine the research-speed comparison. Upfront/refund/net costs,
  exclusive packages, per-building workload and deduplicated infrastructure
  remain separately available. Free automatic upgrades need no queue building.
- Flemish Revolution retains its source formula (200F + 150G, plus 10F + 5G per
  converted villager) as an **unvalidated formula**. Population input evaluates
  it without presenting it as verified; its verification remains excluded by
  the user's explicit scope decision.
- Live replacements count initially purchased unit identities. First mounted
  Konnik death counts once; dismounted death adds nothing. Wounds, healing,
  reversible forms and auxiliary armies do not add replacement costs. Every
  crossed snapshot is consumed, including events skipped by rendering at speed.

When context is enabled, a versioned cost overlay reaches battle count resolution
and economy calculations together. It preserves all non-cost mechanics and the
original mechanics hash for source matching. Four physical-unit prices change:

| Civilization / unit | Previous simulation price | Source-derived final price |
| --- | --- | --- |
| Magyars / Elite Magyar Huszar | 35F + 45G | 80F |
| Mapuche / Elite Bolas Rider | 50W + 55G | 43W + 47G |
| Mayans / Arbalester | 20W + 35G | 18W + 32G |
| Mayans / Elite Plumed Archer | 43W + 43G | 39W + 39G |

Purchase rounding follows the existing simulator policy. Saxon maximum
conditional discounts and Blackwood batch sizing are retained, not applied twice.
Resource-based army counts can change with these verified price corrections.

## Sources, assumptions and deferred measurements

The generated validation report is authoritative. The 2026-11-11 user instruction
excludes four items from release requirements: Berber Xebec, Chinese Fire Ship,
Flemish Revolution cost verification and Wei Tuntian income. These are recorded
as `scopeExceptions` with `excluded_by_user` status, not as validated mechanics.
Wei labor now excludes Tuntian and uses its other modeled activities. The two
unit training routes remain unavailable, and Flemish variable costs remain
explicitly unverified.

Applicable auras are assumed fully active once, with no placement requirement or
aura-building investment. Coverage/placement no longer needs simulation; the
Georgian work-rate magnitude is supported by the online game descriptions.

Six special economy models now produce review estimates. An online check on
2026-11-11 used the game descriptions in `SiegeEngineers/aoe2techtree`, pinned to
commit `3bb43b1439eef88dfe7fe892d7f7dc41ac9dd76f`. Exact numerical resource
parameters remain from the supplied DAT. The online descriptions independently
confirm the Georgian +10% work rate, Malian +10% gold drop-off credit, and two
workers per pasture; they do not independently verify the precise timed-gold rates.
The user confirmed active-gathering-only gold and the coproduct interpretation.

| Model | Accounting |
| --- | --- |
| Burgundian Vineyards | DAT resource 236: 2 gold per active farming minute; simulation working counters exclude walking, drop-off, rebuilding and idle time. Reviewed layout: about 1.578 gold per villager-minute. |
| Vietnamese Paper Money | DAT resource 266: 1.5 × 1.2 × 1.2 × 1.1 = 2.376 gold per active wood-gathering minute. Felling and walking do not count. Reviewed layout: about 1.951 gold per villager-minute. |
| Poles stone mining | DAT resource 241: approximately 1 gold per 3 stone, in one activity vector. |
| Shu lumberjacks | DAT resource 502: 7 food per 100 wood, in one activity vector. |
| Malian gold | DAT resource 276: 10% extra credit on deposit; physical carry, depletion and working rate stay unchanged. The activity uses long-run credited yield, including eventual deposit of carried gold. |
| Georgian church aura | Rerun all four reviewed gathering layouts with worker work rate ×1.1; include reseeding work under full worker coverage. Preserve movement, carry, farm generation and recurring wood cost. No aura-building cost. |

`online-mechanic-evidence.json` stores pinned source text and assumptions.
`special-gather-rates.json` stores the actual fixtures, per-seed working fractions
and physical checks. Regenerate with `node tools/run_special_economy.mjs` before
compilation when inputs or engines change; stale hashes fail compilation.
These are mechanics-based estimates, not controlled validation.

The user subsequently authorized immediate pasture food credit, like Khmer,
using an online average instead of reconstructing each movement/drop-off cycle.
The selected [community test](https://forums.ageofempires.com/t/how-to-nerf-khitans/275361/183)
reports **25.20 food per villager-minute** after update 147949, with Hand Cart
and the second pasture upgrade. Its [method](https://forums.ageofempires.com/t/how-to-nerf-khitans/275361/191)
times a complete seeding-to-depletion cycle, so rebuilding downtime is already
included and is not added again. The sample is small; this is an approximate
post-Imperial proxy, not a verified average for the supplied DAT build. No extra
bonus is inferred for less frequent rebuilding after the Imperial pasture upgrade.

The pasture activity credits 0.42 food per villager-second and consumes
`0.42 × 110 / 1035` wood per villager-second. The labor solver therefore includes
the civilization's woodcutting work for renewal, alongside food gathering.
There is no external drop-off trip. The online rate already covers internal
walking. `pasture-online-reference.json` records source dates, settings, method,
limitations and the user's accounting assumptions; its hash versions the runtime.

Controlled measurements are deferred by explicit user instruction, not marked as
passed. The validator preserves the scenario catalog for later testing. No
in-scope model or measurement requirement currently blocks compilation.

Ratha melee is resolved using the existing explicit form pairing and matching DAT
cost/training fields of its trainable ranged form. Trebuchets retain their
source-linked packed production form. Training unlocks for Tarkan and Huskarl
are included in military investment.

The pasture extraction now distinguishes resource 289 (animal count) from 290
(herder count). Imperial source replay gives 1,035 food, nine animals and two
herders; integer carry replay gives six food per herder. These source inputs and
their technology/actor evidence are exposed as `pastureSourceInputs`. The
`pastureModel` field separately records the online rate and simplifying assumptions;
these do not claim to establish exact engine movement or shared-generation rules.

For future accuracy checks, independently measured windows can still be supplied
through `--observations measurements.json`. A supplied measurement that fails
validation remains a reported blocker; deferral does not turn a failed check into
a pass. The generated report retains `modelKey`, scenario signatures and output
vectors for later coverage. The manifest
format is:

```json
{
  "sourceSha256": "matching DAT hash",
  "windows": [{
    "modelKey": "key from the generated validation report",
    "capturePath": "live_observations/run-name/frames.bin",
    "captureSha256": "SHA-256 of the actual capture",
    "runNumber": 1,
    "startGameSecond": 60,
    "endGameSecond": 660,
    "villagerSeconds": 6000,
    "resourceDeltas": {"food": 0, "wood": 0, "gold": 0, "stone": 0}
  }]
}
```

Paths are relative to `aoe2x/js_simulation/calibration`. Resource deltas must be
measured banked + carried resources minus recurring inputs over the stated window;
villager-seconds includes walking, harvesting, construction and drop-off. Match
the generated scenario/layout and post-Imperial setup. The validator checks
capture identity, source version, nonoverlapping windows, coverage and <1% error
for every output component. Measurements never alter model parameters. Run
`--require-release-ready` in the promotion pipeline; it exits nonzero while any
model, route or validation blocker remains.

## Verification

```sh
python -m pytest -q tests/test_army_economics.py tests/test_army_observations.py tests/test_patch185872_battle_config.py
node --test --test-isolation=none tests/army_economics.test.mjs tests/battle_selection.test.mjs
QA_URL=http://127.0.0.1:5055 node tests/browser/army-economics.cjs
```

The browser suite exercises desktop and 390px mobile layouts, preview, playback,
pause, live deaths, restart, selection reset, real Konnik dismounts at 64×, and
context failure without combat failure. Accounting checks cover discrete 60s
queues, scarcity weights, coproduct pooling, refunds, route selection and compiled
labor functions against the offline solver. Screenshots go to
`.scratch/army-economics-qa/`. The fixed-seed regression runs all four corrected
prices with explicit armies and compares complete unit trajectories and event
hashes. It does not rerun or replace saved matchup campaigns.

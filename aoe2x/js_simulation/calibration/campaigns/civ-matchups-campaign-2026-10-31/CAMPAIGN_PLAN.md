# Civilization matchup campaign: phased, resumable completion

Status: approved execution plan. This branch starts from the completed
inference-only table (`5274d7adbc6c425f337c2cc287f7a162a798a04ce54b7358258e8f1be1d40a5e`).
The table contains 68,370 unresolved distinct profile pairs affecting 146,832
civilization/unit cells. Those counts will be recalculated after every phase.

## Result and invariants

Resolve the entire 555-unit, 56-civilization table, using direct V3 fights only
when existing eligible evidence and validated directional inference cannot settle
a pair. The table stores observed win/loss, inferred win/loss, equivalent mechanics,
or genuinely close/uncertain results. Missing, failed, timed-out and partially
sampled fights never become wins or close results. Do not score civilizations or
change the web app during this campaign.

Every new fight uses the ranking setup: 27 cheaper physical units; opposing count
`max(1, Math.round(27 * sqrt(cheap effective weighted cost / expensive effective
weighted cost)))`; food/wood/gold weights 1/0.9/1.1; zero buffer units; recorded
map and first-N formation; no scripted kiting or AI orders; stable owner
orientation; seeds 0, 1 and 2. If those first three completed outcomes differ,
run seeds 3 through 9, then record the mixed result as close/uncertain. Store
each seed separately with engine, scenario, profile and output hashes.

The current V3 fight path has a 9,000-tick (150-game-second) hard cap in
`src/fight.js` and `src/combat/world.js`. Remove that game-time stop in a new,
explicitly versioned campaign engine before the pilot. A wall-clock watchdog
remains to recover stuck workers; it is not an outcome classifier. The only
engine change planned here is the duration ceiling. Do not modify combat
physics or use shortcuts that force a winner.

Completed corrected-engine ranking records that ended before the old ceiling may
be carried as *prefix-compatible* anchors only after auditing exact input hashes
and checking deterministic replays across representative families. Preserve their
original provenance. Original-engine and old Advisor results are not direct
results for this campaign. If the ceiling change or replay check exposes any
different completed result, do not merge the versions; create a separate input
version and re-evaluate the affected anchors.

## Phases and gates

1. **Preparation and pilot (phase 00).** Freeze a manifest with the profile,
   scenario, rules, policy and runtime-file hashes. Build a deterministic job
   inventory from the unresolved profile pairs and their selected physical
   orientations. Prove the new duration setting leaves already-completed
   sub-150-second seeds unchanged. Run a small, stratified pilot of 16-32
   unresolved pairs, including ranged/melee, cavalry, infantry, siege, specials,
   and likely slow fights. Verify records, seed policy, resumption and throughput.
   Push this phase only after its integrity gate passes.
2. **High-reach anchors (phase 01).** Select unresolved pairs whose measured
   result could resolve the most other cells under the existing validated
   inference rules. Weight exact-profile alias count, unresolved neighbors,
   class coverage and estimated runtime. Use the pilot to calibrate worker count
   (up to four on this five-vCPU host) and wall watchdog. Rebuild inference from
   the completed new records before selecting the next phase.
3. **Adaptive batches (phases 02+).** Select up to 256 distinct unresolved
   profile pairs per phase; recompute the queue at each boundary. Prioritize
   unresolved boundaries and exceptional mechanics after high-reach ordinary
   families. Never schedule equivalent civilization aliases separately. Three
   initial seeds run first; seven follow-up seeds are enqueued only for varied
   initial outcomes. A phase is complete only when every required seed has a
   valid stored result or a documented blocked case that is assigned to a
   recovery phase.
4. **Slow/error recovery.** On worker failure, save the attempt and diagnostics,
   resume without rerunning valid seeds, and escalate wall time through 180,
   600, 1,800 and 3,600 seconds as needed. Isolate persistent outliers in later recovery
   phases so the normal queue continues. Diagnose pathology using game ticks,
   processing time, unit counts, movement and damage activity. A ceiling or
   watchdog event cannot be called close. Any necessary physics fix starts a
   separately versioned dataset while retaining all prior records.
5. **Final integrity review.** Verify every variant and cross-civ pair, exact
   alias expansion, complete required seeds, zero unhandled timeout/error rows,
   consistent engine/input provenance, successful phase checks, and source/
   output hashes. Publish the final table only after all requirements pass.

At the historical mean 21.8 seconds per seed, a naive three-seed pass over all
68,370 unresolved pairs would consume roughly 311 worker-hours / four workers,
or **about 13 days**, before seed extensions and slow outliers. This is an
upper-bound planning baseline, not an ETA: inference refreshes, exact sharing
and new anchors should reduce the number of fights, while new matchup families
may run slower. Phase 00 and 01 will produce a measured forecast. Do not hide
the actual remaining work behind a stopped queue.

## Durable execution and GitHub checkpoints

The campaign manifest and append-only per-run JSONL journals are authoritative.
Keep a local index for fast scheduling, reconstructible from journals. Write each
record durably before updating progress. A lock prevents duplicate supervisors.
On restart, validate the manifest/source hashes and existing records, rebuild the
queue from required seeds, and continue. Jobs use deterministic IDs derived from
ordered profile hashes, counts, scenario and policy. No different source version
can write into the same journal.

After **every completed phase**, atomically write progress, source validation,
inference coverage, unresolved requirements and phase review; commit and push
these plus the new journals to
`simulations/civ-matchups-campaign-2026-10-31`. Confirm the remote branch has
the commit before advancing when GitHub is available. On a transient GitHub
authentication failure, retain the ordered per-phase local commits, mark the
remote checkpoint pending, and continue calculation. Every later phase retries
the push of the entire saved history; final completion requires a successful
push. A phase that
fails integrity remains open for repair, never marked complete. A fresh cloud
worker can resume from the latest GitHub checkpoint without repeating completed
seeds.

The detached supervisor runs four workers initially, records phase and worker
heartbeats, and restarts after transient process failures. It must stop on hash
or journal corruption, rather than silently skipping that work. Progress reports
record physical pairs, completed seeds, pending seeds, undecided/error cases,
wall time, game time and the measured moving ETA.

## Acceptance checks before continuous execution

- The preparation branch contains this plan and has been pushed before the first
  new matchup job is launched.
- The new engine version differs only in the game-time ceiling; representative
  deterministic replays match the old corrected engine where both finished.
- The pilot uses the same unit counts, policy and geometry as the finalized
  rankings and exports a seed-level replayable record for every fight.
- A deliberate interruption resumes from stored seeds and does not create a
  duplicate record or a second concurrent runner.
- Every automatic phase gate validates its own journals, source hashes and
  inference refresh before a GitHub push and the next phase.
- Final completion requires the table coverage and every source journal to
  reconcile; a merely empty runnable queue is insufficient.

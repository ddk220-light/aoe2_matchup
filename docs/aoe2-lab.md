# AOE2 Lab

AOE2 Lab is the portable, resumable workflow for running the same canonical
matchup in AoE2:DE and in the JavaScript engine, comparing their outcomes, and
opening any persisted engine seed in the existing Tailnet viewer.

It has one source of matchup truth. A plan fixes the unit slugs, display
civilizations, resource weighting, unit counts, golden scenario family,
placement rule, and golden hash before either runner starts. Live capture and
simulation consume that same plan; neither runner independently reconstructs
the matchup.

## Fresh Windows installation

Requirements:

- Windows with AoE2:DE and its Scenario Editor
- Python 3.10 or newer (3.12 is the tested default)
- Node.js on `PATH`
- FFmpeg and Google Chrome for the existing video automation
- Tailscale only when Tailnet publication is wanted
- the local CadeRemote gRPC credentials under `aoe2x/grpc/` (never commit them)

From a fresh clone:

```powershell
Set-Location C:\path\to\aoe2_matchup
.\scripts\bootstrap_aoe2lab.ps1
```

The bootstrap creates `apps/video/.venv`, installs the editable project and all
live dependencies, creates a gitignored `aoe2lab.toml`, and runs the read-only
live dependency doctor. Edit `aoe2lab.toml` if the scenario directory cannot be
auto-detected or a non-default executable/tool path is needed. Machine paths and
credentials stay local.

Before a game-bound run, open AoE2:DE in the normal Scenario Editor UI and leave
it frontmost. The automation deliberately does not guess its way through Steam,
profile selection, game menus, or a save-changes modal.

```powershell
apps\video\.venv\Scripts\aoe2lab.exe doctor --live --ui
```

That command is non-mutating. It verifies Node, writable artifact storage, all
four committed goldens and their exact hashes, the executable gRPC Python (not
merely the presence of a stale venv path), logger/redecoder availability,
scenario storage, imports, the live gRPC stack, and—when `--ui` is supplied—the
current editor screen.

## One matchup

Inspect the exact plan before touching the game:

```powershell
aoe2lab plan --side2 arbalester --civ2 Chinese `
  --side3 paladin --civ3 Spanish
```

Run five engine seeds. `workers=0` is the default and uses every logical CPU up
to the number of seeds; each seed is an isolated Node process.

```powershell
aoe2lab simulate --side2 arbalester --civ2 Chinese `
  --side3 paladin --civ3 Spanish --seeds 5
```

Run one game capture, with one bounded retry:

```powershell
aoe2lab live --side2 arbalester --civ2 Chinese `
  --side3 paladin --civ3 Spanish --repeats 1 --retries 1
```

Run live capture, engine seeds, and comparison as one workflow:

```powershell
aoe2lab run --side2 arbalester --civ2 Chinese `
  --side3 paladin --civ3 Spanish --live-repeats 5 --sim-seeds 5
```

Counts default to equal weighted resources with a cap of 27, where food, wood,
and gold each weigh 1. Other supported policies are:

```powershell
# Equal unit counts
aoe2lab plan --side2 champion --side3 paladin --balance equal_count --count 20

# Explicit roster
aoe2lab plan --side2 champion --side3 paladin --balance explicit --n2 27 --n3 14

# Historical 1.5x gold valuation
aoe2lab plan --side2 champion --side3 paladin --gold-weight 1.5
```

The cheaper equal-resource army gets the cap. The expensive side is floored to
the largest whole-unit count that does not exceed it. Exact counts and costs are
printed in the plan and stored with the run.

## Golden scenarios and the NoneAI invariant

The four source scenarios live in `apps/video/templates/lab_goldens/` and are
committed so a clone does not depend on gitignored captures:

- melee versus melee
- ranged versus ranged
- ranged versus melee
- melee versus ranged

Every build fills the first N unit slots in original player order, preserving
edge-to-centre placement. Mixed ranged/melee families preserve Player 4's nine
Scout Cavalry, its positions, authored diplomacy and triggers, and the switch to
hostility only after Player 4 is defeated.

Players 2–4 remain the golden scenarios' `NoneAi` configuration (AI type 2) with
the same embedded 54-byte `(disable-self)` script. `NoneAI.per` under
`%TEMP%\AOE2DE_Temp` is a game-created extraction file, not a scenario dependency
and not an alternate AI selected by the lab. Windows or the game may remove the
empty temp parent. The runner recreates only that parent, then validates the
generated scenario's complete AI configuration against the exact golden before
pressing Test. A mismatch aborts the run; it never substitutes a human player or
a different `.per` file.

The earlier incident was therefore two layers: the game/Windows failed while
extracting its embedded AI into the temp directory, and the old driver failed to
recognize the error and continued sending input. AOE2 Lab addresses the driver
failure with preflight, exact golden validation, gRPC readiness, bounded retry,
screenshots, structured failure artifacts, and immediate capture sanity gates.

## Batch queue

Copy and edit `aoe2lab.batch.example.toml`, then run:

```powershell
aoe2lab batch .\my-batch.toml --phase simulate --seeds 5
aoe2lab batch .\my-batch.toml --phase live --live-repeats 5
aoe2lab batch .\my-batch.toml --phase full --seeds 5 --live-repeats 5
```

Live runs are serial because the game and foreground input are single-owner
resources. Simulation work is flattened across every matchup/seed pair into one
CPU-sized process pool, so a ten-matchup batch does not leave cores idle between
matchups. A failed job is isolated and recorded while unrelated queued jobs keep
running. Completed seed/repeat artifacts are provenance-checked checkpoints and
are reused on rerun.

Use `aoe2lab status` for all jobs or `aoe2lab status <job_id>` for one.

## Artifacts and failure recovery

Runtime output is gitignored under
`aoe2x/js_simulation/calibration/lab/runs/<job_id>/`:

```text
request.json                 original request
plan.json                    canonical resolved conditions + plan hash
manifest.json                state machine, checkpoints, viewer path
failure.json                 typed phase/error/hint/traceback when failed
logs/                        per-seed and live-attempt logs
simulation/seeds/seed_NNN.json  complete persisted viewer playback
simulation/summary.json      outcomes and signed remaining-HP percentages
live/run_NNN/                scenario, video, frames.bin, sidecar, diagnostics
live/summary.json            captured outcomes
comparison.json              live-versus-simulation result
```

Each queue also has a durable
`calibration/lab/batches/<batch_id>/manifest.json` and request snapshot. It
records every job's phase and failure independently, including requests that
were rejected before a job directory could be created.

Writes are atomic. A simulation seed is reusable only when its opening seed and
plan hash match and it has a complete playback. A live repeat is reusable only
after all required files exist, the frames dump is non-trivial, starting counts
match the plan, and exactly one test army reaches zero. Re-running the same job
resumes valid checkpoints; a different plan under the same job ID is rejected.

Comparison uses the agreed metric: signed remaining-HP percentage points (P2 is
positive, P3 negative). It reports every simulation seed whose winner is outside
the winners observed live, plus signed/absolute score delta and acceptance
against the requested point threshold. A wrong-winner comparison points the
viewer at an actual wrong-winner seed. A stable-winner HP miss points at the
completed seed closest to the simulation mean, so the report and viewer cannot
drift onto an unrelated run.

## Local and Tailnet viewer

```powershell
aoe2lab serve
aoe2lab serve --tailnet
```

The server discovers completed jobs directly from the artifact manifests. A lab
URL has the durable form:

```text
/?mode=lab&job=<job_id>&seed=<seed>
```

The dropdown switches among persisted jobs and seeds; opening a row does not run
a new simulation. Before reporting success, local serving verifies both the HTML
shell and job API and ensures the new server process did not die on a port
collision. Tailnet publication obtains the current device DNS name dynamically,
configures the requested route, and verifies the remote HTML, catalogue, and a
representative playback artifact when one exists.
Repeating `aoe2lab serve` on an already healthy lab port safely reuses that
server; an unrelated process on the port is rejected with an actionable error.

## Live-capture storage retention

Live capture defaults to `--retention stats`. A run is first validated from its
gRPC dump, then the decoded HP timeline, winner, survivor HP percentage, timing,
checksums, scenario provenance, manifest, and diagnostic log are retained while
large `.mov`, `.frames.bin`, reseed, metadata, and end-marker files are deleted.
Those retained statistics are sufficient for later simulations, pass/fail
comparison, reports, and the problem-matchup viewer.

Raw recordings are never retained by default. Choose a different policy only
when the capture request explicitly calls for it:

```powershell
# Compact raw evidence into recordings.zip, then remove expanded raw files.
aoe2lab live ... --retention archive

# Keep every expanded recording and raw stream for temporary debugging.
aoe2lab live ... --retention raw
```

Before touching the game, the live preflight checks free space on the artifact
and temporary-file volumes. `stats` budgets one peak recording because each run
is pruned immediately; `archive` and `raw` budget every requested repeat. The
defaults reserve 2 GiB beyond a 1 GiB estimated peak recording and are tunable
under `[live]` in `aoe2lab.toml`.

## Operational safety and modeling rule

- Run `doctor --live --ui` before a game-bound batch and do not use the mouse or
  keyboard while it owns the game.
- Never edit the committed goldens to repair a capture. Fix the plan/builder or
  restore the exact source.
- Captures are evidence, never runtime winner/HP corrections. Engine changes
  must remain reusable mechanics. Only the generic seeded first-acquisition
  policy may represent opening randomness.
- Do not commit `aoe2lab.toml`, videos, `frames.bin`, seed playbacks, logs, or lab
  runtime directories.

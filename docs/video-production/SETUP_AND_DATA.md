# Workstation, game data, and planning

[Return to the complete runbook](../VIDEO_PRODUCTION_RUNBOOK.md).

## What a fresh operator must obtain

| Dependency | How it is provisioned | Verification |
| --- | --- | --- |
| Current branch | Clone the repository and check out `codex/video-recorder-v3` | `git branch --show-current`; inspect current commit and worktree |
| AoE2:DE and requested civilization content | Install through the user's Steam account | Game starts; required unit/civ exists; Scenario Editor loads |
| Windows interactive desktop | Keep the game on the primary display, unlocked and frontmost | Doctor UI check and a reviewed pilot |
| Python | Python 3.12 recommended; retain its installation after creating the venv | Repository interpreter imports the complete live stack |
| Node | Install on PATH | `node --version`; planner and focused tests pass |
| FFmpeg/FFprobe | Install a full Windows build and put its `bin` on PATH | Both commands run; required H.264 NVENC and AAC codecs exist |
| NVIDIA GPU/driver | Required by the current full-video adapter's `h264_nvenc` command | Real tiny encoder smoke test; don't infer usability only from the codec list |
| Python live dependencies | `scripts/bootstrap_aoe2lab.ps1` | `aoe2lab doctor --live` |
| DAT extraction dependency | `genieutils-py`; the prior extraction environment used 0.1.2 | `from genieutils.datfile import DatFile` imports and current DAT parses |
| Reference data | Committed `data/golden/` artifacts or matching documented release | SQLite opens read-only; expected unit/civ rows resolve uniquely |
| Game DAT for audit/export | Copy the installed `resources/_common/dat/empires2_x2_p1.dat` into ignored `data/inputs/` | Record SHA-256/build and validate against the current game |
| CadeRemote mTLS credentials | Secure handoff from the configured recording machine/operator | Three expected files exist; authenticated local Info/Frames connection succeeds |
| Campaign art/font/audio | Installed game files; selected music is extracted locally | Font atlas, selected DDS, narration event and music media ID resolve |
| Wwise audio decoder | Official vgmstream Windows CLI, locally under `.tools/vgmstream/` | Decode one selected WEM and listen/probe duration |
| Narration account | User-owned ElevenLabs key and authorized voice/sample | Active voice ID, available quota, matching script/timestamp output |
| Upload account | Google Desktop OAuth client JSON and channel-owner consent | `channels.list(mine=true)` returns expected channel ID/handle |
| Storage | Local working volume plus optional external archive | Capacity forecast, write test, actual junction targets checked |
| Optional delivery | Tailscale login/device | Only needed for a requested Taildrop or Tailnet viewer |

The Git repository intentionally does not distribute OAuth clients/tokens, private game API keys/certificates, installed game assets, raw captures, the external drive, or downloaded executable tools. A new operator must obtain these through the table above. Existing Windows DPAPI tokens cannot simply be copied to a different user/computer; authorize there again.

The current repository does **not** contain a supported credential-extraction command for a fresh CadeRemote client. Do not substitute the game's unrelated `certificates/cacert.pem` for `cade-client.pem`. Request the known-working three-file credential bundle securely from the machine owner, or provision a supported client through the game API setup. If unavailable, stop the live-capture stage; planning and documentation still work. This prerequisite is explicit rather than pretending bootstrap creates private credentials.

## Environment and dependencies

The full-video helper scripts use Python 3.11's `tomllib` directly; use 3.12 even though the core package advertises Python ≥3.10. Run from repository root with `PYTHONPATH=apps/video;.`. Most production code uses the standard library plus NumPy, Pillow, OpenCV, the Scenario Parser, and gRPC. The live requirements are [requirements-windows.txt](../../aoe2x/lab/requirements-windows.txt), which includes [Windows input dependencies](../../apps/video/auto/requirements_windows.txt).

```powershell
.\scripts\bootstrap_aoe2lab.ps1 -Python 'C:\Python312\python.exe'
$Py = Join-Path (Get-Location).Path 'apps\video\.venv\Scripts\python.exe'
& $Py -m pip install 'genieutils-py==0.1.2' pytest
& $Py -c "import aoe2x, AoE2ScenarioParser, grpc, cv2, numpy, PIL, pydirectinput, pygetwindow; from genieutils.datfile import DatFile; print('imports OK')"
node --version
ffmpeg -version
ffprobe -version
ffmpeg -hide_banner -f lavfi -i color=size=128x128:rate=30 -t 1 -c:v h264_nvenc -f null -
```

Do not upgrade a parser or game build mid-campaign. If a newer DAT requires a different parser, test the change in isolation and record the version. The pinned extraction version above documents the tested historical dependency, not compatibility with every future patch.

The tiny NVENC command generates no lasting video and does not interact with the game. A non-NVIDIA workstation requires a reviewed encoder adaptation in the full builder; passing doctor alone does not make `h264_nvenc` work. Capture/overlay tooling has its own codec selection; inspect the actual logs for the selected codec.

Set local configuration:

```toml
[paths]
artifacts = "aoe2x/js_simulation/calibration/lab"
node = "node"
python = "apps/video/.venv/Scripts/python.exe"
bootstrap_python = "C:/Python312/python.exe"

[game]
executable = "C:/Program Files (x86)/Steam/steamapps/common/AoE2DE/AoE2DE_s.exe"
scenario_directory = "C:/Users/YOU/Games/Age of Empires 2 DE/PROFILE/resources/_common/scenario"
window_title = "Age of Empires II: Definitive Edition"

[grpc]
python = "apps/video/.venv/Scripts/python.exe"
logger = "aoe2x/grpc/grpc_hp_log.py"
redecoder = "aoe2x/grpc/redecode_hp.py"

[simulation]
workers = 0
seeds = 5

[live]
cap_seconds = 210
retention = "stats"
min_free_gb = 2
estimated_recording_gb = 1
```

Store that as ignored `aoe2lab.toml`. **Always use recorder mode for this workflow**, regardless of the default `retention="stats"` used by ordinary lab experiments. `recording_campaign` forces recorder/raw retention. A normal stats-only run can discard precisely the video/frames this series needs.

Set `AOE2_GAME_DIR` for offline game-art/intro extraction if Steam is elsewhere. It is independent of the executable and scenario directory above. Current offline campaign/media helpers assume the default Lab path; use junctions there instead of changing only `paths.artifacts` and splitting the workflow across two roots.

The gRPC files belong at:

```text
aoe2x/grpc/cade-client.key
aoe2x/grpc/cade-client.pem
aoe2x/grpc/certificate-authority.pem
```

Connection: `ipv6:[::1]:4341`, TLS target override `ca-game-api`. This is local authenticated game access, unrelated to Google or ElevenLabs credentials. [Logger connection code](../../aoe2x/grpc/grpc_hp_log.py) and [gRPC README](../../aoe2x/grpc/README.md) define the contract. A running game that does not expose this endpoint needs local game/API configuration troubleshooting, not firewall exposure to the internet.

## Game and desktop preparation

1. Finish or save the owner's personal game/scenario before taking the desktop.
2. Launch AoE2:DE through Steam if closed. Steam app ID is `813780`; the default executable is `AoE2DE_s.exe`.
3. Enter Editors and load the dedicated working scenario, commonly “Matchup Run.” Do not load/save over an unrelated user scenario.
4. Full screen on the primary monitor; consistent capture resolution. The established landscape output is 2560×1440 at 60 fps. Keep scaling/window geometry consistent with the validated pilot.
5. Enable game sound/music, verify the configured audio loopback device, and silence unrelated computer audio. Avoid computer-use spoken narration. Desktop recordings can include other apps if focus is lost.
6. Run `scripts/aoe2lab.ps1 doctor --live --ui`. Review every required failure before a batch.
7. Inspect the first scenario's actual generated positions, camera, P1/P2/P3 civilizations, Imperial tech application, `NoneAI`, and P4 trigger/diplomacy behavior.

The automated preflight does not prove every graphical/UI/game-version detail. A pilot with actual footage and first-frame gRPC stats is the integration test.

## Registering an entirely new unit

Distinguish a new **episode** for an already registered unit from a genuinely new **game identity**. The scaffold handles the first case. For the second:

1. Find the installed game master ID, exact civilization, highest requested tier, and attack mode. Consult DAT/reference selectors, not a guessed English label. Keep website slug separate if necessary.
2. Add the unit to [unique-unit-roster.json](../../data/unique-unit-roster.json) only if it belongs in the approved opponent roster. Otherwise add it as a recording-only subject in [recording-subjects.json](../../data/recording-subjects.json). Do not silently widen all future opponent rosters when adding an experiment.
3. Required fields follow existing entries: `slug`, `label`, `civ`, `master`, `class`, `baseCost`, `scenarioKey`, and `costSource`; optional `websiteSlug`, `naval`. `class` controls melee/ranged scenario selection. `baseCost` is legacy descriptive metadata.
4. Regenerate/verify the separate effective-cost catalog. The Node resolver must find `civ|slug`, matching master ID. Missing entries fail closed; never fall back to base cost.
5. Check [recording-unit-registry.js](../../aoe2x/js_simulation/src/recording-unit-registry.js) resolution order: engine registry, canonical roster, recording subjects. An existing slug can shadow a later recording-only row. Do not add a conflicting duplicate.
6. Verify [scenario generation](../../apps/video/build_run.py) can resolve the scenario key/master and requested mode. The pilot must prove the generated unit is the intended one after upgrades.
7. Resolve fully upgraded overlay stats from [reference DB](../../data/golden/README.md), or source-backed [supplemental stats](../../apps/video/overlay/supplemental-stats.json). Confirm portrait ID, team color, display name, font glyphs, civ theme/emblem, cost and unique-effect wording. Missing UI assets are a distinct problem from capture support.
8. If simulation is requested, export an exact fixture and register it; do not claim that recording-only support is simulation support. [Fixture export](../../aoe2x/js_simulation/tools/export_roster_mechanics.py) handles the canonical roster. A subject outside it needs explicit exporter/registry support and tests.
9. Prepare and inspect one plan without game interaction. Then use the main runbook's scaffold/pilot stages.

Example plan via CLI (for identity/count inspection):

```powershell
.\scripts\aoe2lab.ps1 plan --side2 elite_kamayuk_incas --civ2 Incas `
    --side3 elite_huskarl --civ3 Goths --cap 27
```

New standard manifests use the approved geometric formula and a 27-unit cap,
with no resource ceiling (owner update, September 15, 2026). Historical or
explicitly budgeted experiments retain their recorded limits. The generated
manifest and stored preflight are the canonical specification.

## Cost audit and patch provenance

The original production bug used base prices rather than effective civilization prices. Corrected costs are now central to capture plans, count validation, Shorts ranking, and simulation resource comparisons. The audit must consider **all** applicable cost-setting/multiplying effects, not only a few known discounts.

The current cost audit applies available standard Imperial technologies, civilization bonuses, and unique technologies from the installed data, retains the effect trace, rounds purchase resources, and converts training batches to per-physical-unit price. The Blackwood pair exception has explicit installed help/DAT evidence. Population cost is not a training-batch divisor.

Do not run regeneration while a campaign is capturing or its source hashes are supposed to stay frozen. First preserve the old catalog and identify the installed build. Copy the DAT without changing golden databases:

```powershell
$Dat = Join-Path $env:AOE2_GAME_DIR 'resources\_common\dat\empires2_x2_p1.dat'
Get-FileHash -LiteralPath $Dat -Algorithm SHA256
New-Item -ItemType Directory -Force 'data/local/production-audit' | Out-Null
Copy-Item -LiteralPath 'data/recording-costs.json' -Destination 'data/local/production-audit/recording-costs-before.json'
Copy-Item -LiteralPath $Dat -Destination 'data/inputs/empires2_x2_p1.dat'
& $Py -c "from pathlib import Path; from aoe2x.extract.run import extract_all; extract_all(Path('data/inputs/empires2_x2_p1.dat'), Path('data/local/cost-audit-extracted'))"
if ($LASTEXITCODE -ne 0) { throw 'Installed-DAT extraction failed' }
```

Generate the complete engine registry snapshot used by the audit. Avoid a PowerShell UTF-16/BOM redirection file:

```powershell
$RegistryJson = node --input-type=module -e "import {UNIT_REGISTRY} from './aoe2x/js_simulation/src/unit-registry.js'; console.log(JSON.stringify(UNIT_REGISTRY));"
if ($LASTEXITCODE -ne 0) { throw 'Registry export failed' }
[IO.File]::WriteAllText((Join-Path $Repo 'data/local/cost-audit-registry.json'), ($RegistryJson -join "`n"), [Text.UTF8Encoding]::new($false))
& $Py scripts/audit_recording_costs.py
if ($LASTEXITCODE -ne 0) { throw 'Cost audit failed' }
$Catalog = Get-Content 'data/recording-costs.json' -Raw | ConvertFrom-Json
if (@($Catalog.unresolved).Count -ne 0) { throw 'Unresolved cost identities; do not capture' }
```

The audit writes `data/recording-costs.json` and `data/local/production-audit/cost-audit.json`, `report.md`. Review `effectiveCost`, `purchaseCost`, `unitsPerPurchase`, and `effects`, including changed effect IDs and extraction hashes. **Check `unresolved` even when the audit exits zero.** It is an evidence generator; not every historical unresolved identity is currently reflected in its process exit status.

Meaningful checks:

```powershell
node --test aoe2x/js_simulation/tests/recording-costs.test.mjs
& $Py -m pytest --noconftest tests/test_recording_cost_effects.py -q -p no:cacheprovider
```

At plan/run time [recording-costs.js](../../aoe2x/js_simulation/src/recording-costs.js) resolves the exact audited identity; [costs.py](../../aoe2x/lab/costs.py) verifies catalog hash, per-unit cost, army resources, and resource-balanced counts. The Golden hash and plan hash cover separate provenance. A catalog changing can invalidate old plan hashes even when a particular cost is unchanged; preserve prior evidence rather than editing it in place.

For historical captures, the audit produces `RETAKE`, `REUSE_COUNTS_MATCH`, or `UNRESOLVED`. Same counts allow consideration of reuse, but do not prove camera, techs, audio, HP, or scenario correctness. Run [audit_recording_setup.py](../../scripts/audit_recording_setup.py), examine findings, and build an explicit canonical replacement map. Cost-driven result differences are **observed winner changes**, not proof that price correction alone caused them: each raw battle is a separate realization.

## Simulation fixture provenance

Reference mechanics come from [export_unit_mechanics.py](../../aoe2x/js_simulation/tools/export_unit_mechanics.py) and the installed DAT/reference DB. Runtime profiles are in `aoe2x/js_simulation/fixtures/unit_stats/` and registered by [roster-unit-registry.js](../../aoe2x/js_simulation/src/roster-unit-registry.js).

```powershell
$env:PYTHONPATH = 'apps/video;.'
& $Py aoe2x/js_simulation/tools/export_roster_mechanics.py --slugs elite_kamayuk_incas
node aoe2x/js_simulation/tools/preflight_recorder_roster.mjs data/local/recorder-roster-preflight.json
```

Export only the intended missing/stale identities. The exporter may refuse absent/ambiguous DB selectors; fix the source mapping rather than cloning a similar unit's profile. Its explicit DAT fallback currently covers specific omitted units, not arbitrary new content. Match the DAT and DB builds. Check real attack delay/windup, class damage, projectile count, armor stripping, recharge/shields, trample, explosions, transformations, and ownership mechanics relevant to the new unit. Add targeted behavior tests and compare to captured frames.

Preflight validates profile identity/provenance and Golden inputs. The focused mechanics test suite additionally exercises short smoke simulations. Neither establishes winner accuracy over full battles. Missionary conversion and naval simulation remain known unsupported areas; see [limitations](MAINTENANCE_AND_VALIDATION.md#known-limits).

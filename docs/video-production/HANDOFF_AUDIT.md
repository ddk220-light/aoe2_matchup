# Workflow handoff audit — September 13, 2026

[Start at the complete runbook](../VIDEO_PRODUCTION_RUNBOOK.md).

## Scope

This handoff packages the accumulated recorder, cost correction, conversion/end detection, overlay, simulation comparison, intro/narration, Shorts, thermal supervision, and resumable OAuth upload implementation on `codex/video-recorder-v3`, together with a new detailed operating guide. Generated unit art/covers and episode source/provenance are included; large captures, frame streams, extracted audio, downloaded tools and credentials remain local/archived.

The guide comprises the entry point plus setup/data, operations/recovery, media/publication, and maintenance references. It links historical decisions and episode records while labeling superseded status claims. It documents prerequisites a fresh clone cannot supply and the current limits, rather than promising an unattended one-command production on an unconfigured computer.

## Repairs made while preparing the handoff

- Added a dry-run-by-default normal land-episode scaffold. It derives the roster size, P2/P3 identities, manifests, paths and adapters from the canonical subject; validates every effective-cost plan before writing; refuses overwrites; and never starts capture, synthesis or publication itself.
- Tested the scaffold's actual write path in an isolated temporary workspace with **73 real read-only Node plans**, then verified a repeat refuses overwriting the episode.
- Fixed five-seed postprocessing to accept current JSON manifests as well as early TOML manifests, preserving job identities.
- Added `AOE2_GAME_DIR` for offline game-art/catalog discovery on another Steam installation.
- Added configurable package/media ID/output arguments to music extraction, so new civs do not require editing a Chinese-only script.
- Rejected reuse of retired ElevenLabs voice metadata, even when the saved sample hash matches.
- Corrected copied Monaspa fallback script names and its generated-description hashtag; existing uploaded media/settings were not rewritten by this documentation task.
- Clarified that recording-subject base prices are descriptive; the audited effective-cost catalog controls captures.
- Added source-ignore boundaries for private upload state, local downloads, extracted audio and older generated recordings/work files.
- Added a repeatable [local-link/anchor checker](../../scripts/check_video_docs.py).

## Verification evidence

- Focused Python suites: **73 tests passed**, including the full isolated scaffold-write preflight and an additional 31 scenario/navigation/resume/media tests. Thermal selection/freshness/threshold suite: **3 passed**.
- Focused Node planner/mechanics suite: **42 tests passed**.
- Roster preflight: **74/74 ready, zero failures**; profile/Golden input checks, not a claim of empirical calibration.
- Read-only live dependency doctor: **passed**, with installed FFmpeg available. The first sandboxed check could not locate FFmpeg/FFprobe; rerunning with the actual installed binary directory and normal local access passed. No battle was started for this check.
- Documentation: **164 local links/anchors checked, no missing targets** across six handoff documents. Python source syntax was checked across the proposed workflow sources; reports are stored in ignored `data/local/handoff-*.json`.

The first Python invocation loaded the unrelated website conftest and encountered missing Flask in the video venv. The isolated recorder/mechanics suite was then run with `--noconftest`; the full website suite is not represented as passing. The additional resume test initially used a pre-audit stub without costs; it now uses a real canonical two-unit plan and matching scenario filename, and passes without weakening the production cost guard. No new capture, paid narration request, production media render, or YouTube upload was launched to validate this documentation task; media tests use temporary fixtures.

## Production status checked during the handoff

| Subject | Verified state |
| --- | --- |
| Elite Obuch | 73/73 captures complete, no unresolved failures; raw video and gRPC frames retained; media package not started |
| Elite Monaspa | Full compilation plus ten Shorts remotely processed, 11/11 COMPLETE; [full video](https://www.youtube.com/watch?v=5gRrdmf9r24) |

Local authoritative receipts remain under the Lab and `data/local/`; this committed table is a dated snapshot. The user-paused Codex scheduled capture task was not reactivated. CPU sensor unavailability and the existing user-authorized continuation policy remain explicitly documented.

## Review boundaries

The commands and data contracts were checked against current source, focused tests, actual dependency checks, and completed production receipts. The new scaffold is exercised through planning/file creation, not a new in-game video release. A future unit still requires its correct scenario/cost pilot, sourced intro, actual media review, upload authorization, and remote processing checks. The complete workflow remains usable without pretending those unit-specific judgments can be replaced by copying a success flag.

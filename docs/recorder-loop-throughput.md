# Recorder loop throughput

Implemented on codex/video-recorder-v3, September 7, 2026.

The historical Conquistador run spent roughly 30 seconds fighting, 36 seconds navigating to Test, 41 seconds stopping/returning to the editor, and additional synchronous export time. It was not waiting for the battle most of the time.

## Changes

- RapidOCR uses a maximum detector dimension of 960, upright text, and two intra-op/one inter-op threads. This avoids enlarging narrow UI strips to 736 pixels high and CPU oversubscription. Identical recorded menu: default 7.187 seconds versus 1.355 seconds; editor tabs 6.998 versus 0.473 seconds. Both locate the required labels.
- Navigation waits for the expected screen instead of fixed multi-second sleeps. Load/Test use small label regions. The staged scenario row is selected by name; its last region is checked again on reuse, and a miss searches the list again. No blind first-row fallback.
- Successful test cleanup opens F10 once, waits for Quit, waits for Yes, and confirms the editor. Unknown-state recovery remains separate.
- gRPC elimination flag checks run every 100 ms between OCR fallback checks; the minimum fight delay applies only to the banner fallback. Existing stable-elimination grace remains in the logger. Recorder-only output keeps another 0.5 seconds instead of five seconds.
- The serial campaign persists validated raw capture before handing trimming/checksums to one offline worker. That worker uses two ffmpeg encoding threads while the next matchup runs. A run is only published as verified after export and bundle validation finish. The ordinary single-run API still completes export synchronously.
- Reports distinguish finalizing from verified, retain failures, and record capture/finalization wall times. STOP stops new capture, drains already-saved exports, and permits offline resume.

## Validation

18 focused tests pass: recorder scenario/camera preservation, bundle integrity/resume, campaign failure handling, background finalization concurrency, missing menu/row safety, cached-row revalidation and immediate gRPC end detection.

First two-match integration spike completed with both raw bundles, gRPC elimination and exported media validated. The first export took 34 seconds and overlapped preparation/navigation of the second match. A second two-match spike validates the narrower label checks, repeated-row cache and fast cleanup. Measurements below are from real runs with the V3 simulation worker still active.

Local evidence: `.tools/recorder-ocr-benchmark.json`, `.tools/recorder-speed-spike.log`, `.tools/recorder-speed-spike-b.log`, and `aoe2x/js_simulation/calibration/lab/campaigns/recorder-speed-spike{-b}/`. These isolated jobs do not replace any of the 73 completed campaign recordings.

The 100 ms interval is not a hard end-detection deadline: screenshot OCR and CPU scheduling can delay a poll. Loading, recorder startup, raw durability checks, and initial list discovery still take time. Offline export no longer blocks the next live capture.

## Final integration results

Both two-match spikes completed: four raw/gRPC bundles and four exported videos verified, no capture or export failures. The final spike recorded Composite Bowman then Warrior Priest.

| Measurement | Historical run | Final live spike |
|---|---:|---:|
| Editor to Test | about 36 s | 17–18 s |
| Stop through editor return | about 41 s | 8–9 s |
| Export blocking next capture | 30+ s | 0 s (32–36 s offline) |

Final capture wall times were 54.234 and 69.062 seconds including battle, navigation, cleanup and durable raw validation; exported battle durations were 19.524 and 33.542 seconds. Observed fight-end to next game-start was 37 seconds, compared with well over a minute in the older loop. This is a substantial reduction, not a claim of continuous gameplay or a guaranteed three-second upper bound on every transition.

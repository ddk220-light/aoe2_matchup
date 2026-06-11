# Matchup-video sweep RUNBOOK

How to run a recording sweep smoothly, end to end, with everything we learned the
hard way baked in. The system is **self-sufficient**: the gRPC capture stack lives in
`scenario_builder/grpc/` (recorder + live fight-end tailer, offline redecoder, fixed
delta decoder + schema, protobuf stubs, mTLS certs) and the `.venv` carries
`grpcio`/`protobuf`. No external checkouts needed.

## Pre-flight (2 minutes, saves hours)

1. **Game state**: AoE2:DE fullscreen, sitting in the **Scenario Editor** with the
   normal UI visible. Any map open is fine — runs load their own staged scenario.
   - The "No UI" mode / hidden HUD breaks screen detection ("not detected in a known
     screen"). Restore the UI first.
   - A leftover **"Do you want to save your changes?" modal** (from a previously
     interrupted run) also reads as `unknown` — dismiss with **No** (the open scenario
     is always a generated one, never your file).
2. **Profile**: the scenario folder is auto-detected as the most-recently-used
   `…\Games\Age of Empires 2 DE\<steamid>\resources\_common\scenario`. After switching
   profiles, just make sure the new profile has been used once.
3. **Hands off** the machine while a batch runs — navigation clicks land on whatever
   is frontmost, and moving project folders mid-run kills the capture stack
   (subprocess scripts resolve at run time).
4. Quick sanity if anything feels off:
   ```powershell
   .venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.'); from auto import vision; print(vision.detect_state(vision.grab()))"   # want: editor
   .venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.'); from auto import grpc_capture as g; print(g.available())"             # want: True
   ```

## The smooth path for a sweep

```powershell
cd scenario_builder
# 1. RECORD (game-bound). One civ per invocation; --force re-records existing clips.
#    A civ runs ALL its unique units (Wei = Xianbei Raider AND Tiger Cavalry).
.venv\Scripts\python.exe -m auto.run_guecha_sweep --only <Civ> --no-stitch [--force]
# …or everything missing in one go:
.venv\Scripts\python.exe -m auto.run_guecha_sweep --no-stitch

# 2. RE-RENDER (CPU-bound, no game needed) — run AFTER recording, never alongside
#    (parallel ffmpeg encodes drop recording frames):
.venv\Scripts\python.exe -m auto.recompose_from_raws --jobs 3

# 3. STITCH the compilation + YouTube chapters:
.venv\Scripts\python.exe -m auto.run_guecha_sweep --stitch-only
```

For long sweeps prefer `--record-only` for step 1 (halves wall-clock; raws + stream
dumps are archived and rendered later by step 2).

**Healthy run signature** (in the sweep log): `stream recorder started` →
`[watch] gRPC live tailer reports fight end at +XXs` (the banner watcher winning the
2s poll race instead is also fine) → `[sidecar] gRPC redecode is SANE — OCR pass
skipped` → `sidecar=grpc`. A healthy run takes ~150s; a run that takes 300s+ took a
fallback — read its log section.

## What each artifact is

Next to every raw in `raw recordings/`: the `.mov` (footage), `.frames.bin` (raw gRPC
stream dump — the timeline can ALWAYS be re-decoded from this with a newer decoder),
`.meta.json`, `.END` (live tailer's fight-end wall stamp → end-anchoring), `.hp.json`
(the decoded sidecar; derived, rebuildable). Delivered clips get the `.hp.json`
alongside. `guecha_sweep/golden/` holds the footage-verified ground-truth capture —
never overwrite it (re-runs overwrite the raw-recordings copy of the same matchup).

## Failure modes we actually hit (symptom → cause → fix)

| Symptom | Cause | Fix |
|---|---|---|
| Every run: "AoE2:DE not detected in a known screen" | Hidden UI, a leftover save-changes modal, or game not in editor | Restore UI / dismiss modal (No) / open editor; rerun |
| `sidecar=None` + minutes of doomed OCR per run | gRPC stack unavailable (paths moved) or redecode produced no rows | `grpc_capture.available()` must be True; read `<prefix>.logger.log`; the footage has no readout text (NO_READOUT), so OCR can never rescue a run |
| redecode `TimeoutExpired` AND truncated `.frames.bin` (~one snapshot) | Decoder hang (the live tailer shares the decoder in-process, so a hang freezes the dump too) | Decoder bug — reproduce offline with `faulthandler.dump_traceback_later`, fix, validate vs golden dump |
| Sidecar exists but only one side ever decodes / armies "11v0" | Army filter too strict — fragile units are real (Elite Blackwood Archer = **25 HP**) | Filter is owner∈{2,3} + type∈{9,11,12} + master≠448 + **hp>0** — keep it that way |
| `1 entities created, 582 resyncs` at seed | Entity-band locator grabbed an isolated false marker in blob data | Band start requires marker DENSITY (≥3 more markers within 80KB) |
| HP bar shifted ~10–15s late | Continuous-stream capture (Test ran in the SAME instance, no clock reset) anchored at V0 | Sidecars carry `end_video_s` (tailer `.END` wall stamp); `select_sidecar` END-anchors the timeline; V0 is only the fallback |
| A whole civ's second unit never records | (fixed) the sweep used to reduce to one unit per civ | `unique_units()` returns the full validated enumeration now |

## Decoder changes: how to validate before trusting

Any change to `scenario_builder/grpc/` must pass, in order:
1. **Golden regression**: `.venv\Scripts\python.exe grpc\redecode_hp.py <copy of golden pair>` →
   24v30, side1 zero at stream t≈28, side2 ends 24u/1644hp.
2. The **scorer** (footage-OCR rmse harness) lives in the research checkout
   (`C:\dev\aoe2\aoe2grpc\_wf_score_fix.py`): rmse ≤ 1.0 + run1 regression.
3. One live run, then check the sidecar's end state matches the WINS banner.

The stream clock runs at **game speed (1.7×)**; sidecars are converted to video
seconds (`AOE2_GAME_SPEED`). Deaths arrive via removal ops ~0.5–1s after the visual
kill — the END anchor absorbs this.

## Golden rules

- **Copy, don't depend**: everything the pipeline needs lives in the repo.
- **Never run recompose during recording** (CPU steals recording frames).
- The WINS banner trigger stays in scenarios (stop-signal fallback + verdict check);
  the title/readout text is blanked by default (`AOE2_NO_READOUT=1`) — set it to `0`
  only for a one-off decoder cross-check run.
- If a batch dies mid-run: the game is usually left in a load dialog or modal —
  fix the screen first, then relaunch; completed clips are skipped automatically
  (delete a bad clip to make its civ re-record it without `--force`).
- When files vanish or look wrong: **ask the human first** — they may have moved
  things; forensics second.

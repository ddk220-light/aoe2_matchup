# Running `inferred-2026-resim-pc` on the owner's PC (instructions for a local Claude Code session)

You are a Claude Code session running on the owner's own Windows PC. Your job:
run the matchup batch `inferred-2026-resim-pc` to completion using **up to 85% of
the CPU**, keep it **pausable/resumable at any time** (the owner uses this PC),
then export the results and push them. Read this whole file first, then
`aoe2x/matchups/README.md` (sections Runner, supervise, status, export) and
`aoe2x/matchups/RUN_INFERRED_2026.md`.

Hard rules:
- Don't edit sim/engine code (`aoe2x/matchups/engines/`, `aoe2x/js_simulation/`)
  or anything that changes results. Don't touch `main`/`staging`, website DBs, or
  run `build-db`/`audit-db`.
- Don't disturb the owner's main checkout (`D:\AI\aoe2_matchup` may be on another
  branch with uncommitted work). Work in the worktree below.
- Ask the owner before installing software or changing a system setting
  (power plan, etc.).

## 1. What is already known about this PC (recon 2026-11-13)

| | |
|---|---|
| Machine | DragonStar, Windows 11 Home (build 26300) |
| CPU | AMD Ryzen 9 9900X — 12 physical / 24 logical cores |
| RAM | 61.6 GB (≈39 GB free at the time) |
| Disk | D: 236 GB free (repo); C: 69 GB free (records under `%USERPROFILE%\.cache`) |
| Power | Balanced; on AC **sleeps after 15 min idle**, hibernates after 3 h |
| Python | 3.13 on PATH (no pytest); `D:\miniconda3\python.exe` has pytest |
| Node | PATH has v20.10.0 (**rejected** by the `verified` policy). A verified **v24.22.1** exists at `C:\Users\ddk22\AppData\Local\OpenAI\Codex\runtimes\cua_node\76f5b5935a63c7ba\bin\node.exe` (belongs to another app; may vanish on its update). Accepted versions: v24.22.1, v22.23.4 (`engines/frozen-civ-matchups-v3/ENGINE.json`). If you need a stable copy, propose to the owner installing a portable Node v24.22.1 zip (e.g. `D:\tools\node-v24.22.1-win-x64\`). |
| Worktree | `D:\AI\aoe2_matchup_runs` on branch `matchup-runs` (create with `git worktree add ..\aoe2_matchup_runs matchup-runs` if missing) |
| Records | `%USERPROFILE%\.cache\aoe2-matchup-runs\inferred-2026-resim-pc\` (log `supervise.out`) |

Re-verify these quickly (cores, free RAM, node path, `git -C D:\AI\aoe2_matchup_runs pull`)
before starting — they may have changed.

## 2. What the test run proved (2026-11-13, commit 6c6271291)

- Windows fixes are on `matchup-runs` (CRLF engine bytes, lock liveness,
  `msvcrt` lock, STOP handling). `verify-engine`, `validate-config`, `freeze`,
  `inventory` pass; 94/94 matchups tests pass on Windows.
- **394 seeds already done** for this run; they count (resume is exact).
- 3 workers: ≈2,000 seeds/h, ≈1 core and ≈200 MB RAM per worker,
  mean 5.3 s per seed (median 3.3 s), 1.05 seeds/context.
- STOP → clean exit in ~1 s (exit 143, lock released); restart resumed exactly;
  two exports in a row are byte-identical.
- Remaining work: ≈9,800–15,500 seeds.

## 3. Parallelism: target 85% CPU

Each worker is one single-threaded simulation, so throughput scales with
workers until the cores are full. The worker count is **not** part of the run
hash, so it can be changed at every restart (`supervise --workers N`).

- Starting point: `N = floor(0.85 × logical cores)` = **20** on this 24-thread CPU.
- Calibrate: run 5 minutes, measure total CPU (e.g. PowerShell
  `Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 5 -MaxSamples 12`).
  If the average is above 85%, STOP and restart with fewer workers; if well below
  (e.g. < 75%) and the owner isn't using the PC, try more (never above 22). Record
  the chosen N and the measured seeds/h in the run log you report.
- Run the supervisor (and its node children) at **BelowNormal priority** so the
  owner's foreground apps stay responsive: launch it with
  `Start-Process ... -WindowStyle Hidden` and afterwards set
  `(Get-Process -Id <pid>).PriorityClass = 'BelowNormal'` on the supervisor,
  runner and node processes (children inherit the priority class if it is set
  before they spawn; set it on any that don't).
- RAM is not a constraint (≈200 MB/worker; `maxOldSpaceMb` 3072 is only a cap).
- Expected: ≈10,000–13,000 seeds/h at 20 workers → **≈1–1.5 h** total.

Optional but recommended before the long run (a few minutes): cross-platform
determinism check. `git fetch origin simulations/civ-forecast-recovery-2026-11-10`
and run `python -m aoe2x.matchups replay-check --node <node> --workers 8` (see
README; it replays 60 archived 2026 seeds and must report 60/60 identical).
The Node versions were verified on Linux only; this proves Windows matches.
If it is not 60/60, STOP and report — do not run the batch.

## 4. Commands (from `D:\AI\aoe2_matchup_runs`)

```powershell
$R = "$env:USERPROFILE\.cache\aoe2-matchup-runs\inferred-2026-resim-pc"
$NODE = "<full path to node v24.22.1>"

python -m aoe2x.matchups status inferred-2026-resim-pc          # progress / ETA / blocked

# start or resume (same command every time)
Remove-Item "$R\STOP" -ErrorAction SilentlyContinue
Start-Process python -ArgumentList "-m","aoe2x.matchups","supervise","inferred-2026-resim-pc","--workers","20","--node",$NODE `
  -WindowStyle Hidden -RedirectStandardOutput "$R\supervise.out" -RedirectStandardError "$R\supervise.err"

# pause (clean; nothing half-done is lost)
New-Item "$R\STOP" -ItemType File -Force

# stale lock after a crash/reboot
python -m aoe2x.matchups unlock inferred-2026-resim-pc
```

(`-RedirectStandardOutput` overwrites; rename the old log first if you want to keep it.)

## 5. Pause / resume for the owner

Make this easy for the owner and tell them exactly how in your report:

- Create two tiny scripts in the records dir (not in git):
  `pause.cmd` (creates `STOP`) and `resume.cmd` (deletes `STOP`, runs the start
  command above with the calibrated N). Optionally `resume-light.cmd` with
  ~8 workers for when they are using the PC lightly.
- Sleep/reboot/crash are all safe: the run just stops; `resume.cmd` continues
  exactly. Partial results are never lost.
- Sleep: the PC sleeps after 15 min idle, which pauses the run. Ask the owner
  whether to (a) set `powercfg /change standby-timeout-ac 0` for the duration and
  restore `15` afterwards, or (b) keep it awake without changing settings via a
  small helper that calls `SetThreadExecutionState(ES_CONTINUOUS|ES_SYSTEM_REQUIRED)`
  while the supervisor is alive. Don't change the setting without their OK.

## 6. Monitoring

Check `status` every ~15 minutes while you are active. Watch: contexts complete
rising, `failed attempts`, and `blocked` (contexts that hit all four timeouts
180/600/1,800/3,600 s). A few blocked contexts are expected to be rare; report
them, don't retry unless asked (`run --retry-blocked`). If the runner exits with
code 2 (integrity/config) the supervisor won't restart it: read `$R\logs\runner.log`
and report.

## 7. When finished: bring the results back

```powershell
python -m aoe2x.matchups export inferred-2026-resim-pc          # -> $R\export\
git switch -c results/inferred-2026-resim-pc                     # from matchup-runs
# copy $R\export\* to data\matchup_runs\inferred-2026-resim-pc\  (≈2.5 MB)
git add data/matchup_runs/inferred-2026-resim-pc
git commit -m "Matchups: inferred-2026-resim-pc results (<N> contexts, <seeds> seeds, <blocked> blocked)"
git push -u origin results/inferred-2026-resim-pc
git switch matchup-runs
```

Include in the commit message / final report: workers used, Node version and
path, total seeds, wall time, seeds/h, blocked count, replay-check result, and
`export/manifest.json`'s snapshot hash. The cloud session will pick the branch
up from there (classification + advisor Revision 4 rerun). Do not run
`build-db` or touch `data/golden/`.

# Run: inferred-2026-resim (operator note)

Simulates the 10,193 profile pairs (19,647 displayed cells) whose published 2026
outcome was rule-inferred, so each gets real outcomes and remaining-HP/survivor
data. Owner request 2026-11-12. Results are for owner review only: do **not**
run `build-db`/`audit-db` or touch `data/golden/civ_matchups_first_pass.db`.

| What | Where |
|---|---|
| Run config (committed) | `aoe2x/matchups/configs/inferred-2026-resim.json` |
| Selection + priors builder (committed) | `aoe2x/matchups/inferred_2026.py` |
| Selection / priors files (not in git) | `/home/user/matchup-runs-records/inputs/inferred-2026-resim/{contexts,priors}.jsonl.gz` + `selection-receipt.json` |
| Records (not in git) | `/home/user/matchup-runs-records/inferred-2026-resim/` |
| Supervisor log | `<records>/supervise.out`, `<records>/logs/` |
| Source index | `~/.cache/aoe2-matchup-runs/baselines/campaign-2026/result-index.jsonl.gz` (sha256 `d672f226…`) |

Settings: frozen 2026 bundle, scenarios and `frozen-civ-matchups-v3` engine;
published-results orientation (every context equals its serving-DB evidence
row's stored context, checked by `verify` below); sampling `one-three-ten` with
the rule-inferred outcome as prior; 3 workers; Node `/opt/node24/bin/node`
(v24.22.1, recorded replay evidence). Run hash `4b56a1c1…`.

All commands run **from the repository root of the `matchup-runs` checkout**
(here the worktree `/tmp/claude-0/-home-user-aoe2-matchup/c64ba011-deb2-5026-8014-2063b1e15df5/scratchpad/mr`).
Running them from a checkout without `aoe2x/matchups` fails with
`No module named aoe2x.matchups.__main__`.

```bash
cd <matchup-runs checkout>
R=/home/user/matchup-runs-records/inferred-2026-resim

# status (any time)
python -m aoe2x.matchups status inferred-2026-resim          # add --json for machine output
tail -3 $R/supervise.out; cat $R/state.json | head -40

# stop (clean: the runner finishes nothing half-way; journals stay consistent)
touch $R/STOP                                                 # supervisor stops runner and exits
#   or: kill -TERM $(python -c "import json;print(json.load(open('$R/supervisor.json'))['pid'])")

# start / resume (same command after a STOP, a crash or a container restart)
rm -f $R/STOP
setsid nohup python -m aoe2x.matchups supervise inferred-2026-resim --node /opt/node24/bin/node \
  >> $R/supervise.out 2>&1 < /dev/null &
#   if status reports a stale lock after a hard restart: python -m aoe2x.matchups unlock inferred-2026-resim

# export when done (or any time for a partial, deterministic snapshot)
python -m aoe2x.matchups export inferred-2026-resim           # -> $R/export/{manifest.json,results.jsonl.gz,...}

# re-check the selection / orientation mapping (no battles)
python -m aoe2x.matchups.inferred_2026 verify inferred-2026-resim \
  --index ~/.cache/aoe2-matchup-runs/baselines/campaign-2026/result-index.jsonl.gz
```

Resume is exact: decisions are pure functions of the journals, so restarting
after any kill reproduces the uninterrupted run (see README "Runner"). The
config pins the selection and priors files by sha256; if they are lost,
regenerate them byte-identically with
`python -m aoe2x.matchups.inferred_2026 build --index <result index> --out /home/user/matchup-runs-records/inputs/inferred-2026-resim`.
If the worktree itself is gone, recreate it from the shared repository:
`git -C /home/user/aoe2_matchup worktree add <dir> matchup-runs` (the branch is
committed locally, not pushed).

Exit codes of the runner: 0 finished, 1 crashed (supervisor restarts), 2
integrity/config (not restarted: read `$R/logs/runner.log`), 75 lock held, 143
stopped. Blocked contexts (four timeouts: 180/600/1,800/3,600 s) are listed by
`status` and exported in `blocked.jsonl.gz`; `run --retry-blocked` retries them.

Expected: ~15,900 seeds by the planner's model; pilot measured 1.03 seeds/context
and ~730 seeds/h on 3 workers (≈ 14 h total).

## Portable copy for another machine: `inferred-2026-resim-pc`

`configs/inferred-2026-resim-pc.json` is the same run with no machine-specific
paths: the selection/priors files are committed under
`aoe2x/matchups/inputs/inferred-2026-resim/` (same sha256 as above) and records
go to `${MATCHUP_RUNS_STORE}/inferred-2026-resim-pc` (default
`~/.cache/aoe2-matchup-runs/`). No RB or result index needed to run it:

```bash
python -m aoe2x.matchups freeze inferred-2026-resim-pc
python -m aoe2x.matchups inventory inferred-2026-resim-pc
python -m aoe2x.matchups supervise inferred-2026-resim-pc --node <node 24 path>
python -m aoe2x.matchups export inferred-2026-resim-pc
```

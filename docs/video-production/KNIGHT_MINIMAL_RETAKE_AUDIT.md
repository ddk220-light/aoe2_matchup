# Knight rerun audit and minimal correction queue

## Verdict

The blanket rerun was unnecessary. A formula version changing is not evidence
that a battle changed. Compare frozen plans and actual captured army counts
before scheduling a rerun. An inaccessible video is not evidence that the
battle must be rerun either; retain its recorded results and locate its media
separately.

The original eight variants contain 591 battles. Both formula versions use
the same comparison prices, discounts, square-root cost balance and cap of 27.
The subject cavalry already count as one population in both versions. Only two
opponents had reduced population that altered the old counts: Elite Karambit
Warriors and Elite Blackwood Archers. **575 counts are unchanged; 16 differ.**

Counts below are subject cavalry versus opponent. Each row applies to both
opponents, so each row represents two corrections.

| Subject | Original counts | Approved counts |
|---|---:|---:|
| Frank Paladin | 10 vs 27 | 15 vs 27 |
| Teutonic Paladin | 10 vs 27 | 15 vs 27 |
| Lithuanian Paladin, four relics | 10 vs 27 | 15 vs 27 |
| Persian Savar | 10 vs 27 | 15 vs 27 |
| Bulgarian Cavalier | 10 vs 27 | 15 vs 27 |
| Polish Cavalier | 13 vs 27 | 18 vs 27 |
| Burmese Cavalier | 10 vs 27 | 15 vs 27 |
| Sicilian Cavalier | 10 vs 27 | 15 vs 27 |

Separately, nine expansion variants need the opponent Elite Leitis's +4 melee
attack: Spanish, Burgundian and Celtic Paladins; Khmer, Berber and Malay
Cavaliers; Wei, Wu and Shu Heavy Hei Guang Cavalry. Their counts do not change.
The older eight variants' Leitis corrections were already recorded and archived.

Total necessary work was **25 individual corrections**, not 600 battles.

## Stop and reuse decision

At the safe stop, five full campaigns had finished and 33 Polish battles had
finished: 402 recordings. Ten of those were needed count corrections; the other
392 were unnecessary repeats for the identified changes. Preserve those completed
recordings; do not choose between old and new recordings based on their outcomes.

The report uses the five already-completed replacement sets consistently, and
reuses the three remaining Cavalier sets with only their two count cells replaced.
This source choice is fixed in `apps/video/ranking_sources.json`. It does not
select whichever trial won or retained more HP.

The replacement queue contains six count corrections (Polish, Burmese and Sicilian
Cavaliers against the two opponents) followed by the nine expansion Leitis fixes.
`apps/video/prepare_knight_required_retakes.py` compares original manifest-selected
plans, verifies completed corrections and old Leitis receipts, copies only the
required frozen plans, and marks the blanket queue superseded. Preparation is
one-time and refuses existing destinations; resume the queue without preparing again.

```powershell
$env:PYTHONPATH='apps/video;.'
$env:PYTHONUTF8='1'
apps/video/.venv/Scripts/python.exe -u apps/video/run_knight_expansion.py --work data/local/knight-required-retakes
```

The capture coordinator retains pilot, recorder mutex, thermal, export and
checked-copy protections. The archive disk is SAFEHOUSE, Buffalo physical serial
`00000107000079B6`, volume serial `1588195055`; verify identity rather than a drive
letter. Keep the 4 GiB reserve. Never overwrite existing external files or change
disk formatting/partitions. Only verified local duplicates may be reclaimed.
No new scheduled monitor is authorized.

## Reconnected archive evidence

The older archive disk was reconnected as E:, label Archives, WD serial
`WXB1A11Y1348`, volume `F274E9A2`. The four original Paladin compact archives and
their existing Leitis corrections were read from it. Every named MP4 and frames
file exists with its indexed size. Actual starting counts differ only for the
two identified opponents; game version, Golden templates, support counts and
relic settings agree with the replacement data after applying existing fixes.

For Polish, Burmese and Sicilian Cavaliers, all 74 recorded results per variant
were found under `E:/AoE2 Renders/retained-source-versions`. Their original plans,
capture manifests and recording metadata survive, including already-corrected
four-relic Leitis. Their frozen prices, Golden hashes, game version and relic
settings match the new plans; only the same two count cells differ.

Their original named Cavalier MP4/frame files were not located on the connected
disks during this audit. **Result availability and replay availability are
different.** The results can be ranked without replay files. Do not silently
declare these source recordings available for rebuilding overlays, and do not
start extra captures to replace them without investigating their location.

Rebuild explicit metadata-only ranking indexes, without writing to the source disk:

```powershell
apps/video/.venv/Scripts/python.exe apps/video/index_retained_cavalier_results.py --source 'E:/AoE2 Renders/retained-source-versions'
```

The helper requires exactly 74 distinct opponents per civilization, matching
job identities and planned/actual counts, and the already-corrected Leitis.
It preserves original plans and policies, capture results, source metadata
hashes and expected media hashes. It refuses to overwrite an existing index.
These indexes explicitly do not certify replay media availability.

After the 15 selected corrections are captured and archived:

```powershell
$env:PYTHONPATH='apps/video;.'
apps/video/.venv/Scripts/python.exe apps/video/report_knight_line_rankings.py --line knight --archive-root 'D:/AoE2 Renders' --archive-root data/local/knight-reused-indexes --require-current-all
```

The reporter accepts an old `geometric_shared_discount_v1` label only when the
actual counts equal the current formula. Unknown policies, different counts,
different Golden/game versions, buffers or opponent relic settings still fail
comparability. Final validation requires all 17 variants and exactly the same
70 included opponents. Original policy labels and results remain unchanged.

## Local audit trail

- `data/local/knight-v2-recapture/original-count-audit.json`: all 591 plan comparisons.
- `data/local/knight-required-retakes/audit.json`: necessary, reused and selected jobs.
- `data/local/knight-required-retakes/connected-archive-verification.json`: Paladin file and capture checks.
- `data/local/knight-required-retakes/retained-cavalier-verification.json`: Cavalier metadata comparisons.
- `data/local/knight-required-retakes/{queue,status}.json`: selected queue and live state.
- Each selected campaign's `capture/status.json` and `archive-status.json`: capture and checked-copy receipts.
- `data/local/knight-reused-indexes/`: recoverable result indexes with source hashes.

Read [RECORDED_RANKING.md](RECORDED_RANKING.md) for scoring and the three top-25
reports, and [RECORDING_RETENTION.md](RECORDING_RETENTION.md) for preservation.

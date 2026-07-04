# Extraction accuracy analysis

Audit of how faithfully `extract_world_timeline.py` recovers dates from the
visual-only spreadsheet. Written 2026-07-04 against source
`World_History_Timeline_2.xlsm`; re-runnable at any time via
`python world_timeline/audit_accuracy.py`.

## Method

There is no external ground truth for ~20k entries, but the sheet audits
itself: **718 labels embed their own date range** ("Mamluk Egypt (AD
1250–1517)", "(27BC to AD1453)", "(c. 5000 – c. 2000 BC)"). The extractor
parses these into `label_year_start` / `label_year_end`; the audit compares
them against the *positional* years recovered from sheet geometry
(`year_start` / `year_end`). Disagreement beyond ±4 years (the 2-year column
grid can round at both ends) marks an outlier; every outlier class was
inspected by hand and either fixed or explained below.

Structural invariants verified separately:

- The column→year map reproduces **all 113 year labels in row 4 exactly**
  (including the half-width 1-year columns around AD 235–300).
- All 1,415 data-area merged-cell ranges have complete cell runs in the XML
  (no bar silently truncated by a merge).
- No entry has `year_end < year_start`; no empty labels; CSV row count ==
  JSON entry count.
- Independent cross-check: UK & Ireland section = 940 entries, matching the
  workbook's own per-section statistics table on its Help tab exactly;
  other sections agree within a few % (boundary/legend differences).

## Results

| Audit | agreement within ±4 yrs |
|---|---|
| Initial extraction (v1, 696 checkable labels) | 79.2 % |
| After fixes below (718 checkable, non-layout) | **87.1 %** |

Median positional error for agreeing entries is 0 years at both ends.

## Issues found and fixed

1. **Bars clipped at the 3400 BC sheet edge** (Neolithic cultures, Archaic
   periods…). The sheet starts at 3400 BC; anything older is drawn from the
   first column. *Fix:* `continues_left` is now set whenever a bar touches
   the left edge and its label says it starts earlier; the true start is in
   `label_year_start`.
2. **End-repetition fragments.** Long bars repeat their name near the right
   end; when a bar's interior is subdivided by differently-filled sub-bars,
   the trailing label became a separate 2-year entry ("Maya (c. 1800 BC -
   AD 1546)" appearing at 1544–1546). *Fix:* fragments on the same row with
   a common label prefix merge back **only when the merged span matches a
   date range written in the label** (±6 yrs). 29 fragments merged; the
   oracle-validated condition produced zero false merges — repeated same-name
   entries like Grover Cleveland's two non-consecutive terms stay separate.
3. **Mid-timeline key/legend boxes.** Reference tables drawn in empty grid
   areas inherit fake dates from their x-position ("List of Chemical
   Elements" at AD 1148, "Key to list of Popes" at 28 BC). *Fix:* every
   entry inside the rectangle under a "Key…"/"List of…" header is flagged
   `is_layout: true`, walking rows downward adaptively. Together with the
   pre-3250 BC corner keys and numbered lists, 1,071 entries are flagged.
4. **Labels with two date ranges** ("Kingdom of Mauretania (285 BC–431 AD
   and again (533–698 AD))"). *Fix:* all ranges are parsed and the one most
   consistent with the drawn span is stored.
5. **Oracle parser bugs** (not extraction bugs): "(1000BC – AD 1000)" once
   parsed as 1000 BC–1000 BC. Fixed before trusting outlier lists.

## Remaining disagreements (91 entries) — mostly not errors

The dominant residual class is **interrupted parent bars**: the drawn bar
legitimately stops where the sheet's visual story splits it, while the label
carries the author's full range. Examples: "Roman Empire (27BC to AD1453)"
is drawn 28 BC–AD 330 (the bar visually hands over to the Byzantine bar);
"Early Bronze Age (c. 3300 - 2100 BC)" is drawn to 3000 BC where EBA I/II/III
sub-bars take over; "Ottoman Empire (1298 - 1923)" is drawn to 1400 where
the Interregnum interrupts. **Positional years = what the sheet draws;
`label_year_*` = what the author wrote.** Consumers should prefer
`label_year_*` when present.

A handful are genuine one-off oddities (e.g. "Imamate of Oman (749-1959)"
drawn at 714–744; "Spread of Islam (800–1600)" whose fill run extends to
1968) — individually inspectable via the audit script's outlier list.

## Known residual limitations

- **Split boundaries between same-colour neighbours are inferred.** ~870
  adjacent same-fill entry pairs touch with no border; the split is placed
  at the label cell. Labels sit at bar starts throughout the sheet (spot
  checks + the fact that start errors are ~0 in the audit), so this is
  usually right, but individual boundaries can be off.
- **Unfilled floating annotations** (~1,500 entries, `color: null`) take
  their extent from incidental neighbouring borders; median span is 6 yrs.
  Treat their duration as approximate; many are point annotations.
- **`group` is best-effort.** Left-pane labels are stacked word-by-word and
  vertically centred; re-joining and nearest-row assignment is heuristic.
- **Geometry ≠ semantics.** A bar's span is faithfully extracted but the
  extraction cannot know whether it depicts a life, a reign, or a period
  (Genghis Khan's bar is 1162–1206, birth→Great Khan).
- **Colours are display-approximate.** Excel theme tints are applied
  per-channel rather than in HSL luminance space; hues are right, exact
  shades may differ slightly from Excel's rendering.
- **Un-headed legend boxes** would not be caught by the "Key…"/"List of…"
  rectangle detection if any exist without such a header.
- Standalone `?` uncertainty markers next to bars are dropped (a leading
  `?` on the label itself sets `uncertain: true`).

## Re-running the audit after a source update

```bash
python world_timeline/extract_world_timeline.py /path/to/World_History_Timeline_2.xlsm
python world_timeline/audit_accuracy.py
```

Investigate anything new in the outlier list top-20; the established
residual classes above are expected to reappear.

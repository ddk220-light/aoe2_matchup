# World History Timeline — data extraction

Converts the **World History Timeline** spreadsheet (`World_History_Timeline_2.xlsm`,
~26 MB, not committed) into machine-readable JSON/CSV suitable for rendering on a
website. The source sheet is purely *visual*: ~20,000 historical entries are drawn
as coloured horizontal bars on a 5,200-row × 2,800-column grid where the x-axis is
time (3400 BC → AD 2000+).

## Usage

```bash
python world_timeline/extract_world_timeline.py /path/to/World_History_Timeline_2.xlsm
# -> world_timeline/output/world_timeline.json
# -> world_timeline/output/world_timeline_entries.csv
```

Stdlib only (parses the xlsx XML directly — no openpyxl needed, runs in ~25 s).

## How the visual encoding was reverse-engineered

| Visual element | Encoding in the file | How it's decoded |
|---|---|---|
| Time axis | Row 4 has a year label every 25 columns, col 22 = 3400 BC | Each column spans 2 years; half-width columns (`<col width="0.71">`, e.g. AD 235–300, the Crisis of the Third Century) span 1 year. The derived col→year map validates exactly against all 113 year labels. |
| Entry duration | A bar = contiguous run of cells sharing a fill colour, delimited by vertical cell borders | Each row is segmented at border edges / fill changes / cell gaps. `year_start` = first column's year, `year_end` = year after the last column. |
| Entry name | Text in one cell of the bar; very long bars repeat the label (`← Archaic Egyptian →`) so it stays on-screen | Repeated labels (one a prefix of another after stripping `←`/`→`/`?` markers) collapse into one entry; genuinely distinct labels inside one same-fill run split the bar at each label cell. |
| Sections (33 major + sub-headers = 42) | ALL-CAPS text in column B (frozen pane cols B–O) | Header row → next header row defines the section band; every entry gets its band's name. |
| Row-group labels ("Pharaoh", "Capital of Egypt"…) | Stacked word-by-word down columns B–D every other row | Consecutive label rows are re-joined into one name when they read as a sentence fragment; each entry gets the nearest group label within 15 rows (best-effort → `group` may be null or occasionally wrong). |
| Extra prose | ~4,000 legacy cell comments | Attached as `note` to the entry covering the commented cell (89 in the data area could not be matched and are exported in `unmatched_notes`). |
| Article links | ~700 hyperlinks on `ì` icon cells | Attached as `link` (World History Encyclopedia / Wikipedia URLs). |
| Colour | Cell fill (direct RGB or theme colour + tint) | Resolved to `#RRGGBB` via the workbook theme palette. |

## Output format

`world_timeline.json`:

```jsonc
{
  "meta":     { "entry_count": 19992, "year_range": [-3412, 2028], ... },
  "sections": [ { "name": "Egypt", "row_start": 11, "row_end": 44, "entry_count": 223 }, ... ],
  "entries":  [ {
      "section": "Egypt",
      "group": "Period",              // best-effort row-group label, may be null
      "row": 15,                      // sheet row = vertical lane
      "label": "Old Kingdom (2686–2181 BC)",
      "year_start": -2686,            // positional: negative = BC, 2-year resolution
      "year_end": -2182,              // positional: year the bar stops
      "label_year_start": -2686,      // authoritative: parsed from the label, if present
      "label_year_end": -2181,        //   (null when the label has no date range;
                                      //    end null also means "- present")
      "continues_left": false,        // bar clipped at the 3400 BC edge
      "continues_right": false,       // bar runs to "present" / off the right edge
      "uncertain": false,             // label carried a leading '?'
      "is_layout": false,             // see caveats
      "color": "#D6D4CB",
      "note": "…",                    // cell comment, if any
      "link": "https://…"             // article link, if any
    }, ... ],
  "unmatched_notes": [ ... ]          // comments that couldn't be tied to an entry
}
```

**Prefer `label_year_*` over `year_start`/`year_end` when present** — they are
the dates the author wrote; the positional years are what the sheet draws
(quantised to the grid, clipped at the sheet edge, and sometimes stopping
where a parent bar hands over to its sub-periods). Accuracy audit, fixes,
and residual limitations: **`ACCURACY.md`** (re-runnable via
`python world_timeline/audit_accuracy.py` — 87% of the 718 self-dated labels
agree with the drawn position within ±4 years; the rest are explained there).

`world_timeline_entries.csv` is the same `entries` array flattened.

## Caveats for website use

- **Dates are grid-quantised**: everything is ±2 years (the column width). The
  sheet's own convention — dates before ~1000 BC are often speculative.
- **`is_layout: true`** (1,071 entries) marks cells whose x-position is page
  layout, not a date: the per-section "key" tables drawn in the empty
  pre-3250 BC corner, numbered reference lists (e.g. "4. Hesiod" in
  Philosophy), and mid-timeline key/legend boxes ("List of Chemical
  Elements", "Key to list of Popes"). Filter these out when plotting by
  time; they still carry useful text/notes (and sometimes `label_year_*`).
- **Point events** (a single 2-year column, e.g. "Suez Crisis") have
  `year_end - year_start == 2`; render as a point/diamond rather than a bar.
- **`row` is the vertical lane**: rendering entries of a section grouped by `row`
  reproduces the original stacked layout with no time-overlap within a lane.
- Entry count (19,992) is ~1.3 % above the sheet's own count (19,741): the
  splitting/merging heuristics and key-table cells account for the difference.

#!/usr/bin/env python3
"""Extract machine-readable data from the World History Timeline spreadsheet.

The source workbook (``World_History_Timeline_2.xlsm``) encodes ~19,700
historical entries *visually* on its ``Timeline`` tab:

- **Time axis**: row 4 carries year labels every 25 columns starting at
  column 22 (= 3400 BC). A normal column spans 2 years; a handful of
  half-width columns (identified in ``<cols>`` by ``width=0.71``) span
  1 year each (e.g. the Crisis of the Third Century, AD 235-300).
- **Entries**: an entry is a horizontal "bar" of contiguous cells that share
  a fill colour and are delimited by vertical cell borders. The entry name
  sits in one (or, for very long bars, several repeated) cell(s) of the bar.
  ``<-``/``->`` arrows in labels mark continuation beyond the sheet edges.
- **Sections**: 42 ALL-CAPS headers in column B (frozen pane, columns B-O)
  divide the sheet into horizontal bands (EGYPT, CHINA, RELIGION...).
  Smaller row-group labels ("Pharaoh", "Capital of Egypt"...) are stacked
  word-by-word down columns B-D and are re-joined here into group names.
- **Extras**: ~4,000 cell comments hold additional prose; ~700 hyperlinks
  point to World History Encyclopedia / Wikipedia articles.

This script parses the raw xlsx XML directly (stdlib only, no openpyxl) and
emits JSON + CSV. Usage:

    python extract_world_timeline.py /path/to/World_History_Timeline_2.xlsm [outdir]

Year convention in the output: integers, negative = BC (arithmetic scale, as
used by the sheet itself). ``year_end`` is the year the bar stops, i.e. the
start year of the first column *after* the bar. Resolution is the 2-year
column grid, so all years are +/-2.
"""

import csv
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

TIMELINE_SHEET = "Timeline"
FIRST_DATA_COL = 16          # columns B..O (2..15) are the frozen label pane
ANCHOR_COL, ANCHOR_YEAR = 22, -3400   # first year label on row 4
CHROME_TEXTS = {"S", "ì", ".", "?", "▼", "▲", "↗", "←", "→"}


def colnum(ref: str) -> int:
    n = 0
    for ch in ref:
        if ch.isalpha():
            n = n * 26 + ord(ch.upper()) - 64
        else:
            break
    return n


def rownum(ref: str) -> int:
    return int(re.search(r"\d+", ref).group(0))


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ").replace("\x9f", "•")).strip()


def strip_markers(text: str) -> str:
    """Remove continuation arrows / uncertainty '?' used as visual markers."""
    t = clean(text)
    t = re.sub(r"^[←→?\s]+", "", t)
    t = re.sub(r"[←→\s]+$", "", t)
    return t


SMALL_WORDS = {"and", "of", "the", "in", "on", "to", "a", "an"}
ACRONYMS = {"usa": "USA", "uk": "UK"}

# "(3100–2686 BC)", "(AD 641–969)", "(30 BC–641 AD)", "(c. 1800 BC - AD 1546)",
# "(1000BC to AD 1000)", "(1515-47)", "(AD 1517 - present)" ...
LABEL_RANGE = re.compile(
    r"\(\s*(?:r\.\s*|reigned\s*)?(?:c\.?\s*)?(?:(AD|CE)\s*)?(\d{1,4})\s*(BC|BCE|AD|CE)?\s*"
    r"(?:–|—|-|−|\bto\b|/)\s*"
    r"(?:(AD|CE)\s*|c\.?\s*)*(?:(AD|CE)\s*)?(?:(\d{1,4})\s*(BC|BCE|AD|CE)?|(present))\s*\)",
    re.I,
)


def parse_label_ranges(label):
    """All (start, end) year ranges the author wrote into the label.
    end is None for '- present'. Years negative = BC."""
    out = []
    for m in LABEL_RANGE.finditer(label):
        pre_a, a, post_a, pre_b1, pre_b2, b, post_b, present = m.groups()
        a = int(a)
        ea = (pre_a or post_a or "").upper()
        if present:
            out.append((-a if ea in ("BC", "BCE") else a, None))
            continue
        b = int(b)
        eb = (pre_b1 or pre_b2 or post_b or "").upper()
        if ea in ("BC", "BCE") and not eb:
            eb = "AD" if b < a else "BC"
        if eb in ("BC", "BCE") and not ea:
            ea = "BC"
        if not ea and not eb:
            if b < a and b < 100:
                b = (a // 100) * 100 + b  # "(1515-47)" style abbreviation
            ea = eb = "AD"
        ya = -a if ea in ("BC", "BCE") else a
        yb = -b if eb in ("BC", "BCE") else b
        if yb >= ya:
            out.append((ya, yb))
    return out


def best_label_range(ranges, y0, y1):
    """The label range most consistent with the drawn span (labels with two
    reigns — 'X (285 BC–431 AD and again (533–698 AD))' — carry several)."""
    if not ranges:
        return None
    def cost(r):
        s = abs(y0 - r[0])
        e = 0 if r[1] is None else abs(y1 - r[1])
        return s + e
    return min(ranges, key=cost)


KEY_HEADER = re.compile(r"^(key\b|key[:\-]|key to|list of|legend\b)", re.I)


def prettify_heading(caps: str) -> str:
    words = clean(caps).split(" ")
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        if lw in ACRONYMS:
            out.append(ACRONYMS[lw])
        elif i > 0 and lw in SMALL_WORDS:
            out.append(lw)
        else:
            out.append(w.capitalize())
    return " ".join(out)


# --------------------------------------------------------------------------
# workbook plumbing
# --------------------------------------------------------------------------

def sheet_paths(z: zipfile.ZipFile, sheet_name: str):
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rel_map = {r.get("Id"): r.get("Target") for r in rels}
    for sh in wb.iter(NS + "sheet"):
        if sh.get("name") == sheet_name:
            target = rel_map[sh.get(RNS + "id")].lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            return target
    raise KeyError(sheet_name)


def load_shared_strings(z):
    out = []
    with z.open("xl/sharedStrings.xml") as fh:
        for _, el in ET.iterparse(fh):
            if el.tag == NS + "si":
                out.append("".join(t.text or "" for t in el.iter(NS + "t")))
                el.clear()
    return out


def load_theme_palette(z):
    """Theme colour slots in fgColor@theme order: lt1/dk1 swapped per OOXML."""
    root = ET.fromstring(z.read("xl/theme/theme1.xml"))
    a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    scheme = root.find(f"{a}themeElements/{a}clrScheme")
    slots = []
    for el in scheme:
        srgb = el.find(a + "srgbClr")
        sysc = el.find(a + "sysClr")
        slots.append(srgb.get("val") if srgb is not None else sysc.get("lastClr"))
    # clrScheme order: dk1 lt1 dk2 lt2 accent1-6 hlink folHlink
    # fgColor@theme index order: lt1 dk1 lt2 dk2 accent1-6 ... (0/1 and 2/3 swapped)
    order = [1, 0, 3, 2] + list(range(4, len(slots)))
    return [slots[i] for i in order]


def apply_tint(hex6: str, tint: float) -> str:
    out = []
    for i in (0, 2, 4):
        v = int(hex6[i : i + 2], 16)
        v = v * (1 + tint) if tint < 0 else v + (255 - v) * tint
        out.append(f"{max(0, min(255, round(v))):02X}")
    return "".join(out)


def load_styles(z, theme):
    """Return per-cellXf (fill_hex_or_None, has_left_border, has_right_border)."""
    root = ET.fromstring(z.read("xl/styles.xml"))
    fills = []
    for f in root.find(NS + "fills"):
        pf = f.find(NS + "patternFill")
        hexc = None
        if pf is not None and pf.get("patternType") not in (None, "none"):
            fg = pf.find(NS + "fgColor")
            if fg is not None:
                if fg.get("rgb"):
                    hexc = fg.get("rgb")[-6:]
                elif fg.get("theme") is not None:
                    base = theme[int(fg.get("theme"))]
                    hexc = apply_tint(base, float(fg.get("tint") or 0))
                elif fg.get("indexed") is not None:
                    hexc = "808080"  # legacy indexed colours: rare, grey fallback
            else:
                hexc = "808080"
        fills.append(hexc)
    borders = []
    for b in root.find(NS + "borders"):
        left = b.find(NS + "left")
        right = b.find(NS + "right")
        borders.append(
            (
                left is not None and left.get("style") is not None,
                right is not None and right.get("style") is not None,
            )
        )
    xfs = []
    for xf in root.find(NS + "cellXfs"):
        fl = fills[int(xf.get("fillId") or 0)]
        bl, br = borders[int(xf.get("borderId") or 0)]
        xfs.append((fl, bl, br))
    return xfs


def parse_sheet(z, path, shared):
    """Stream the (very large) sheet: {row: [(col, styleIdx, value|None)]}."""
    rows = {}
    one_year_cols = set()
    with z.open(path) as fh:
        for _, el in ET.iterparse(fh):
            tag = el.tag
            if tag == NS + "row":
                cells = []
                for c in el:
                    if c.tag != NS + "c":
                        continue
                    v = None
                    vel = c.find(NS + "v")
                    if c.get("t") == "s" and vel is not None:
                        v = shared[int(vel.text)]
                    elif c.get("t") == "inlineStr":
                        ise = c.find(NS + "is")
                        if ise is not None:
                            v = "".join(t.text or "" for t in ise.iter(NS + "t"))
                    elif vel is not None:
                        v = vel.text
                    cells.append((colnum(c.get("r")), int(c.get("s") or 0), v))
                if cells:
                    rows[int(el.get("r"))] = cells
                el.clear()
            elif tag == NS + "col":
                # half-width columns represent 1 year instead of 2
                if abs(float(el.get("width")) - 0.7109375) < 1e-6:
                    one_year_cols.update(
                        range(int(el.get("min")), int(el.get("max")) + 1)
                    )
                el.clear()
    return rows, one_year_cols


def build_col_year(rows, one_year_cols, max_col):
    """col -> start year. Anchored at ANCHOR_COL/ANCHOR_YEAR, validated vs row 4."""
    col_year = {}
    y = ANCHOR_YEAR
    for c in range(ANCHOR_COL, max_col + 2):
        col_year[c] = y
        y += 1 if c in one_year_cols else 2
    y = ANCHOR_YEAR
    for c in range(ANCHOR_COL - 1, FIRST_DATA_COL - 1, -1):
        y -= 1 if c in one_year_cols else 2
        col_year[c] = y
    labels = [
        (c, int(v))
        for c, _, v in rows.get(4, [])
        if v and v.lstrip("-").isdigit()
    ]
    bad = [(c, v, col_year.get(c)) for c, v in labels if col_year.get(c) != v]
    if bad:
        raise AssertionError(f"year-axis mismatch at {bad[:5]}")
    return col_year


def load_comments(z, sheet_path):
    rel_path = f"{os.path.dirname(sheet_path)}/_rels/{os.path.basename(sheet_path)}.rels"
    rels = ET.fromstring(z.read(rel_path))
    target = None
    for r in rels:
        if r.get("Type", "").endswith("/comments"):
            target = os.path.normpath(
                os.path.join(os.path.dirname(sheet_path), r.get("Target"))
            )
    notes = {}
    if target:
        root = ET.fromstring(z.read(target))
        for com in root.iter(NS + "comment"):
            ref = com.get("ref")
            txt = "".join(t.text or "" for t in com.iter(NS + "t"))
            notes[(rownum(ref), colnum(ref))] = clean(txt)
    # external hyperlinks (article links)
    rel_map = {
        r.get("Id"): r.get("Target")
        for r in rels
        if r.get("Type", "").endswith("/hyperlink")
    }
    return notes, rel_map


def load_hyperlinks(z, sheet_path, rel_map):
    links = {}
    with z.open(sheet_path) as fh:
        for _, el in ET.iterparse(fh):
            if el.tag == NS + "hyperlink":
                rid = el.get(RNS + "id")
                if rid in rel_map:
                    ref = el.get("ref").split(":")[0]
                    links[(rownum(ref), colnum(ref))] = rel_map[rid]
            el.clear()
    return links


# --------------------------------------------------------------------------
# timeline reconstruction
# --------------------------------------------------------------------------

def find_sections(rows):
    """42 ALL-CAPS headers in column B -> [(row, name)]."""
    out = []
    for r in sorted(rows):
        for c, _, v in rows[r]:
            if c == 2 and isinstance(v, str):
                t = clean(v)
                if (
                    r > 4
                    and len(t) > 2
                    and t == t.upper()
                    and re.search(r"[A-Z]{3}", t)
                    and t not in CHROME_TEXTS
                ):
                    out.append((r, prettify_heading(t)))
    return out


CONNECTOR_ENDINGS = (":", ",", "&", " and", " of", " in", " the", " to", " for")


def _is_continuation(prev_part: str, part: str) -> bool:
    """Multi-row labels are stacked word-by-word; a row is a continuation of
    the label above when it reads like a sentence fragment."""
    first = part[0]
    return (
        first in "(•-&+"
        or first.islower()
        or prev_part.endswith(CONNECTOR_ENDINGS)
        or prev_part.lower() in SMALL_WORDS
    )


def find_groups(rows, section_rows):
    """Row-group labels (cols B-D, stacked word rows) -> clustered names."""
    raw = []
    for r in sorted(rows):
        if r <= 4:
            continue
        if r in section_rows:
            continue
        for c, _, v in rows[r]:
            if 2 <= c <= 15 and isinstance(v, str):
                t = clean(v)
                if t and t not in CHROME_TEXTS and not t.isdigit():
                    raw.append((r, t))
    clusters = []
    for r, t in raw:
        if (
            clusters
            and r - clusters[-1]["rows"][-1] <= 6
            and not _crosses(clusters[-1]["rows"][-1], r, section_rows)
            and _is_continuation(clusters[-1]["parts"][-1], t)
        ):
            clusters[-1]["rows"].append(r)
            clusters[-1]["parts"].append(t)
        else:
            clusters.append({"rows": [r], "parts": [t]})
    return [
        {
            "name": clean(" ".join(cl["parts"])),
            "row_start": cl["rows"][0],
            "row_end": cl["rows"][-1],
        }
        for cl in clusters
    ]


def _crosses(r1, r2, section_rows):
    return any(r1 < s <= r2 for s in section_rows)


def segment_row(cells, styles):
    """Split one sheet row into bar segments using borders + fill runs."""
    segs = []
    cur = None
    prev_col = None
    for col, s, v in cells:
        fill, bl, br = styles[s]
        if cur is None or col != prev_col + 1 or bl or fill != cur["fill"]:
            if cur:
                segs.append(cur)
            cur = {"start": col, "end": col, "fill": fill, "texts": []}
        cur["end"] = col
        if isinstance(v, str):
            t = clean(v)
            if t and t not in CHROME_TEXTS:
                cur["texts"].append((col, t))
        if br:
            segs.append(cur)
            cur = None
        prev_col = col
    if cur:
        segs.append(cur)
    return [s for s in segs if s["texts"]]


def split_multi_label(seg):
    """A segment may hold several *distinct* entries (same fill, no border),
    or one entry whose label repeats along a very long bar. Repeats (one label
    a prefix of the other after marker-stripping) collapse; distinct labels
    split the bar at each label cell."""
    texts = seg["texts"]
    groups = [[texts[0]]]
    for col, t in texts[1:]:
        a = strip_markers(groups[-1][0][1]).lower()
        b = strip_markers(t).lower()
        if a and b and (a.startswith(b) or b.startswith(a)):
            groups[-1].append((col, t))
        else:
            groups.append([(col, t)])
    if len(groups) == 1:
        return [dict(seg, texts=texts)]
    out = []
    for i, g in enumerate(groups):
        start = seg["start"] if i == 0 else g[0][0]
        end = seg["end"] if i == len(groups) - 1 else groups[i + 1][0][0] - 1
        out.append({"start": start, "end": end, "fill": seg["fill"], "texts": g})
    return out


def best_label(texts):
    return max((strip_markers(t) for _, t in texts), key=len)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "World_History_Timeline_2.xlsm"
    outdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "output"
    )
    os.makedirs(outdir, exist_ok=True)

    z = zipfile.ZipFile(src)
    shared = load_shared_strings(z)
    theme = load_theme_palette(z)
    styles = load_styles(z, theme)
    path = sheet_paths(z, TIMELINE_SHEET)
    rows, one_year_cols = parse_sheet(z, path, shared)
    max_col = max(c for cells in rows.values() for c, _, _ in cells)
    col_year = build_col_year(rows, one_year_cols, max_col)
    notes, rel_map = load_comments(z, path)
    links = load_hyperlinks(z, path, rel_map)

    sections = find_sections(rows)
    section_rows = [r for r, _ in sections]
    groups = find_groups(rows, set(section_rows))

    def section_for(row):
        name = None
        for r, n in sections:
            if r <= row:
                name = n
            else:
                break
        return name

    def group_for(row, sec_row_range):
        best, bestd = None, 16  # ignore labels more than 15 rows away
        for g in groups:
            if not (sec_row_range[0] <= g["row_start"] <= sec_row_range[1]):
                continue
            d = 0 if g["row_start"] <= row <= g["row_end"] else min(
                abs(row - g["row_start"]), abs(row - g["row_end"])
            )
            if d < bestd:
                best, bestd = g["name"], d
        return best

    sec_ranges = {}
    for i, (r, n) in enumerate(sections):
        end = sections[i + 1][0] - 1 if i + 1 < len(sections) else max(rows)
        sec_ranges[n] = (r, end)

    entries = []
    for r in sorted(rows):
        if r <= 4:
            continue
        cells = sorted((c, s, v) for c, s, v in rows[r] if c >= FIRST_DATA_COL)
        if not cells:
            continue
        for seg in segment_row(cells, styles):
            for part in split_multi_label(seg):
                label = best_label(part["texts"])
                if not label:
                    continue
                y0 = col_year.get(part["start"])
                y1 = col_year.get(part["end"] + 1)
                if y0 is None or y1 is None:
                    continue
                raw = " ".join(t for _, t in part["texts"])
                sec = section_for(r)
                # layout artifacts: section "key" tables drawn in the empty
                # pre-3250 BC corner, and numbered reference lists — their
                # x-position is page layout, not a date (mid-timeline key
                # boxes are flagged in a later pass)
                is_layout = y1 <= -3250 or bool(re.match(r"^\d+\.\s", label))
                ranges = parse_label_ranges(label)
                lr = best_label_range(ranges, y0, y1)
                entries.append(
                    {
                        "section": sec or "General",
                        "group": group_for(r, sec_ranges.get(sec, (0, 10 ** 9)))
                        if sec
                        else None,
                        "row": r,
                        "label": label,
                        "year_start": y0,
                        "year_end": y1,
                        # authoritative dates the author wrote into the label
                        # (position on the sheet is quantised / clipped)
                        "label_year_start": lr[0] if lr else None,
                        "label_year_end": lr[1] if lr else None,
                        "continues_left": part["start"] <= ANCHOR_COL + 2
                        and ("←" in raw or bool(lr and lr[0] < ANCHOR_YEAR)),
                        "continues_right": part["end"] >= max_col - 12
                        and ("→" in raw or "present" in raw.lower()),
                        "uncertain": raw.lstrip().startswith("?"),
                        "is_layout": is_layout,
                        "color": "#" + part["fill"] if part["fill"] else None,
                        "note": None,
                        "link": None,
                        "_cols": (part["start"], part["end"]),
                        "_ranges": ranges,
                    }
                )

    # --- pass: merge end-repetition fragments -----------------------------
    # Very long bars repeat their label near the right end ("...the WHT
    # includes the name of the entry at the start and end"). When the bar's
    # interior is interrupted by differently-filled sub-bars, that trailing
    # label becomes a separate tiny segment. Merge fragments back into the
    # main entry when the merged span matches the label's own date range.
    by_row = {}
    for e in entries:
        by_row.setdefault(e["row"], []).append(e)
    def union_matches(m0, m1, ranges, cont_right):
        """Does the merged span match one of the ranges written in a label?
        A span clipped at the 3400 BC sheet edge matches an earlier start."""
        for r0, r1 in ranges:
            start_ok = abs(m0 - r0) <= 6 or (m0 <= ANCHOR_YEAR and r0 <= ANCHOR_YEAR)
            end_ok = (r1 is None and cont_right) or (
                r1 is not None and abs(m1 - r1) <= 6
            )
            if start_ok and end_ok:
                return True
        return False

    def merge_key(label):
        return strip_markers(label).lower().lstrip("-–—• ")

    dropped = set()
    for r, es in by_row.items():
        es.sort(key=lambda e: e["_cols"][0])
        for i, a in enumerate(es):
            if id(a) in dropped:
                continue
            la = merge_key(a["label"])
            for b in es[i + 1 :]:
                if id(b) in dropped:
                    continue
                lb = merge_key(b["label"])
                common = os.path.commonprefix([la, lb])
                if len(common.strip()) < 8:
                    continue
                m0 = min(a["year_start"], b["year_start"])
                m1 = max(a["year_end"], b["year_end"])
                cr = a["continues_right"] or b["continues_right"]
                if union_matches(m0, m1, a["_ranges"] + b["_ranges"], cr):
                    a["year_start"], a["year_end"] = m0, m1
                    a["_cols"] = (
                        min(a["_cols"][0], b["_cols"][0]),
                        max(a["_cols"][1], b["_cols"][1]),
                    )
                    if len(b["label"]) > len(a["label"]):
                        a["label"] = b["label"]
                    lr = best_label_range(a["_ranges"] + b["_ranges"], m0, m1)
                    a["label_year_start"], a["label_year_end"] = lr
                    a["continues_right"] = cr
                    a["note"] = a["note"] or b["note"]
                    a["link"] = a["link"] or b["link"]
                    dropped.add(id(b))
    if dropped:
        entries = [e for e in entries if id(e) not in dropped]
        by_row = {}
        for e in entries:
            by_row.setdefault(e["row"], []).append(e)

    # --- pass: flag mid-timeline key/legend boxes -------------------------
    # "Key to list of Popes", "List of Chemical Elements"... are reference
    # tables drawn in empty areas of the grid; their cells inherit fake
    # dates from their x-position. Flag everything in the rectangle under a
    # key header: rows walk downward while they still contain cells inside
    # the header's column range (+ margin).
    headers = [e for e in entries if KEY_HEADER.match(e["label"])]
    for h in headers:
        c0, c1 = h["_cols"][0] - 5, h["_cols"][1] + 25
        h["is_layout"] = True
        row, misses = h["row"], 0
        while misses <= 4 and row <= h["row"] + 60:
            row += 1
            hit = False
            for e in by_row.get(row, []):
                if e["_cols"][0] >= c0 and e["_cols"][1] <= c1:
                    e["is_layout"] = True
                    hit = True
            misses = 0 if hit else misses + 1

    # attach comments + article links to the entry covering (or adjacent to)
    # the annotated cell on the same row
    unmatched_notes = []
    for (r, c), txt in notes.items():
        target = None
        for e in by_row.get(r, []):
            s, en = e["_cols"]
            if s - 3 <= c <= en + 3:
                target = e
                break
        if target is not None:
            target["note"] = (target["note"] + " | " + txt) if target["note"] else txt
        elif c >= FIRST_DATA_COL:
            unmatched_notes.append(
                {"row": r, "year": col_year.get(c), "text": txt}
            )
    for (r, c), url in links.items():
        for e in by_row.get(r, []):
            s, en = e["_cols"]
            if s - 4 <= c <= en + 4 and not e["link"]:
                e["link"] = url
                break

    for e in entries:
        del e["_cols"]
        del e["_ranges"]
    entries.sort(key=lambda e: (e["row"], e["year_start"]))

    section_list = [
        {
            "name": n,
            "row_start": sec_ranges[n][0],
            "row_end": sec_ranges[n][1],
            "entry_count": sum(1 for e in entries if e["section"] == n),
        }
        for _, n in sections
    ]

    doc = {
        "meta": {
            "source": os.path.basename(src),
            "sheet": TIMELINE_SHEET,
            "year_convention": "integer years, negative = BC; 2-year resolution",
            "year_range": [
                min(e["year_start"] for e in entries),
                max(e["year_end"] for e in entries),
            ],
            "entry_count": len(entries),
        },
        "sections": section_list,
        "entries": entries,
        "unmatched_notes": unmatched_notes,
    }
    jpath = os.path.join(outdir, "world_timeline.json")
    with open(jpath, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)

    cpath = os.path.join(outdir, "world_timeline_entries.csv")
    fields = [
        "section", "group", "row", "label", "year_start", "year_end",
        "label_year_start", "label_year_end",
        "continues_left", "continues_right", "uncertain", "is_layout",
        "color", "note", "link",
    ]
    with open(cpath, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(entries)

    print(f"{len(entries)} entries, {len(section_list)} sections")
    print(f"notes attached: {sum(1 for e in entries if e['note'])} "
          f"(unmatched in data area: {len(unmatched_notes)}), "
          f"links attached: {sum(1 for e in entries if e['link'])}")
    print(f"wrote {jpath}\nwrote {cpath}")


if __name__ == "__main__":
    main()

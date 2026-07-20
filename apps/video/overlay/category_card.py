"""category_card.py — headless-Chrome-rendered full-screen (1920x1080) CATEGORY
cards for the long-form unit-analysis video: the section-divider "explanation"
card that opens each category segment, and the "full ranking" card that closes
it.

Visual family: PARCHMENT — a warm radial-gradient parchment ground (#ecdfc2 ->
#e2d1ac -> #cdb489), corner stains, a heavy inset vignette, a double/hairline
border pair and four diamond corner marks, set in 'IM Fell English' (+ SC
small-caps variant) titles over 'EB Garamond' body text. This replaces the
older Pillow-drawn version of these two cards (dark gold/cream family shared
with `overlay.intro_card`) with a faithful reproduction of the user's two
mockups:
  - "Category Title Parchment.dc.html"   -> make_category_explanation_card
  - "Ranking List Parchment.dc.html"     -> make_category_ranking_card
Rendering goes through headless Chrome (reusing `overlay.render_card._screenshot`)
because the design (double borders, layered radial gradients, webfonts,
text-shadow) isn't practical in Pillow. If Google Fonts can't be reached, the
cards fall back to Georgia / 'Palatino Linotype' automatically.

Two cards:
  make_category_explanation_card(title, subtitle, index, total, category_key)
      -> full-screen divider: small-caps "Category" chip, huge IM Fell English
         title (tinted per category), a divider rule with a central diamond, a
         large italic subtitle, and a bottom block: "i / total Categories" +
         diamond progress dots (filled = current) + "AOE2MATCHUP.COM".
  make_category_ranking_card(title, rows, filmed_keys, category_key,
                              value_header=None, subject_short="Subject")
      -> full-screen ranked list (all rows for the category, in the order the
         caller already sorted them by cost), 2-column parchment panel with a
         small-caps column-header row per column, "Shown" tags on filmed rows,
         and a % HP value column (see DATA CHANGES below).

DATA CHANGES from the mockup (user-requested): the mockup's value column shows
unit COST; this build shows % HP REMAINING instead, while rows stay ordered by
cost exactly as the caller already orders them (most-expensive-first for win
categories, cheapest-first for loss categories):
  - expected_win / unexpected_win  -> value = row['subject_hp']  (the subject
    unit's own % HP left)
  - unexpected_loss / expected_loss -> value = row['opp_hp']     (the opponent's
    % HP left)
  - coin_flip                       -> value = row['wr'] * 100   (subject win %)
Each list column gets an explicit small-caps header row ("#  ·  Unit  ·  <value
header>") so the number's meaning is never ambiguous; `value_header` defaults
to "{subject_short} HP Left" / "Enemy HP Left" / "Win Chance" by category —
pass the subject's FULL unit name as `subject_short` (user rule: the header
says "Elite Temple Guard HP Left", never a shorthand like "Guard") — and
the meta line under the title also states what's being shown. Rows whose
DISPLAYED (rounded) value is > 70 render bold in the darkest ink (#2a1c0d) —
a crushing win for win categories, a crushing loss for loss categories; the
rule does not apply to coin_flip.

Category accent color (title only — everything else stays the mockup's brown
#6b4a1e "chrome"): green for wins, red for losses, brown-gold for coin flips.

CLI: python -m overlay.category_card explain|rank [out.png]
     (renders a demo card using the Elite Temple Guard "expected_win" category)
"""
from __future__ import annotations

import html
import math
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from PIL import Image

from overlay.render_card import _find_browser, _screenshot  # headless-Chrome helpers

W, H = 1920, 1080

# ---------------------------------------------------------------------------
# Category accent colors — tint ONLY the big title text; every other chrome
# element (chip border, rules, diamonds, dots, "Shown" tag) stays the
# mockup's fixed brown below.
# ---------------------------------------------------------------------------
ACCENT_WIN = "#2f5427"        # deep green
ACCENT_LOSS = "#7c2418"       # deep red
ACCENT_COINFLIP = "#6b4a1e"   # brown-gold (mockup neutral)

_ACCENT_BY_CATEGORY = {
    "expected_win": ACCENT_WIN,
    "unexpected_win": ACCENT_WIN,
    "coin_flip": ACCENT_COINFLIP,
    "unexpected_loss": ACCENT_LOSS,
    "expected_loss": ACCENT_LOSS,
}

_WIN_CATEGORIES = {"expected_win", "unexpected_win"}
_LOSS_CATEGORIES = {"unexpected_loss", "expected_loss"}

# parchment "chrome" palette (fixed, mockup-matched)
_CHROME = "#6b4a1e"
_INK = "#4a3220"
_TITLE_NEUTRAL = "#3d2a16"
_INK_DARK = "#2a1c0d"          # bold-row ink
_ROW_NAME = "#3d2a16"
_ROW_CIV = "#7a5a36"
_MUTED = "rgba(94,66,30,.6)"


def _accent(category_key: str) -> str:
    return _ACCENT_BY_CATEGORY.get(category_key, ACCENT_COINFLIP)


# ---------------------------------------------------------------------------
# Webfonts — 'IM Fell English' (+SC) / 'EB Garamond' via Google Fonts, with an
# offline fallback to Georgia / 'Palatino Linotype'.
# ---------------------------------------------------------------------------
_GOOGLE_FONTS_URL = ("https://fonts.googleapis.com/css2?family=IM+Fell+English:ital@0;1"
                     "&family=IM+Fell+English+SC&family=EB+Garamond:ital,wght@0,500;0,600;0,700;1,500"
                     "&display=swap")

_fonts_online_cache: bool | None = None


def _fonts_reachable() -> bool:
    global _fonts_online_cache
    if _fonts_online_cache is None:
        try:
            urllib.request.urlopen(_GOOGLE_FONTS_URL, timeout=3)
            _fonts_online_cache = True
        except Exception:
            _fonts_online_cache = False
    return _fonts_online_cache


def _font_stack() -> dict:
    online = _fonts_reachable()
    if online:
        link = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
                f'<link href="{_GOOGLE_FONTS_URL}" rel="stylesheet">')
        return dict(link=link, online=True,
                    title="'IM Fell English', Georgia, serif",
                    title_sc="'IM Fell English SC', Georgia, serif",
                    body="'EB Garamond', Georgia, serif")
    return dict(link="", online=False,
                title="Georgia, 'Palatino Linotype', serif",
                title_sc="Georgia, 'Palatino Linotype', serif",
                body="Georgia, 'Palatino Linotype', serif")


# ---------------------------------------------------------------------------
# Shared page chrome: parchment background, vignette, borders, corner marks.
# ---------------------------------------------------------------------------
def _corner_marks() -> str:
    corners = [(18, 18), (18, 1886), (1046, 18), (1046, 1886)]
    return "".join(
        f'<div style="position:absolute;top:{t}px;left:{l}px;width:16px;height:16px;'
        f'background:{_CHROME};transform:rotate(45deg);"></div>'
        for t, l in corners)


def _page_open(fonts: dict, screen_label: str) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8">
{fonts['link']}
<style>
* {{ box-sizing:border-box; }}
body{{margin:0;background:#cbb28a;}}
</style>
</head>
<body>
<div data-screen-label="{screen_label}" style="position:relative;width:1920px;height:1080px;
  overflow:hidden;font-family:{fonts['body']};
  background:radial-gradient(1400px 900px at 45% 40%, #ecdfc2 0%, #e2d1ac 55%, #cdb489 100%);
  color:{_INK};">
  <div style="position:absolute;inset:0;background:
    radial-gradient(500px 380px at 12% 88%, rgba(122,90,42,.14), transparent 70%),
    radial-gradient(420px 320px at 90% 10%, rgba(122,90,42,.12), transparent 70%),
    radial-gradient(300px 260px at 70% 92%, rgba(122,90,42,.1), transparent 70%);"></div>
  <div style="position:absolute;inset:0;box-shadow:inset 0 0 220px rgba(94,66,30,.45);"></div>
  <div style="position:absolute;inset:26px;border:3px double rgba(94,66,30,.55);pointer-events:none;"></div>
  <div style="position:absolute;inset:38px;border:1px solid rgba(94,66,30,.3);pointer-events:none;"></div>
  {_corner_marks()}
"""


_PAGE_CLOSE = "</div></body></html>"


# ---------------------------------------------------------------------------
# Card 1 — category explanation (section-divider)
# ---------------------------------------------------------------------------
def build_category_explanation_html(title: str, subtitle: str, index: int, total: int,
                                    category_key: str = "expected_win") -> str:
    fonts = _font_stack()
    accent = _accent(category_key)
    title_esc = html.escape(str(title))
    subtitle_esc = html.escape(str(subtitle))

    dots = "".join(
        f'<div style="width:12px;height:12px;transform:rotate(45deg);'
        f'background:{accent if i == index - 1 else "transparent"};'
        f'border:1.5px solid {_CHROME};"></div>'
        for i in range(total))

    body = f"""
  <div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;
    justify-content:center;gap:26px;padding:0 200px;text-align:center;">
    <div style="border:1.5px solid {_CHROME};color:{_CHROME};font-family:{fonts['title_sc']};
      letter-spacing:6px;font-size:28px;padding:6px 28px;">Category</div>
    <div style="font-family:{fonts['title']};font-size:150px;line-height:1;color:{accent};
      text-shadow:0 2px 0 rgba(236,223,194,.8), 0 3px 4px rgba(94,66,30,.35);">{title_esc}</div>
    <div style="display:flex;align-items:center;gap:18px;width:640px;">
      <div style="height:1.5px;flex:1;background:linear-gradient(90deg,transparent,rgba(94,66,30,.6));"></div>
      <div style="width:10px;height:10px;background:{_CHROME};transform:rotate(45deg);flex:none;"></div>
      <div style="height:1.5px;flex:1;background:linear-gradient(90deg,rgba(94,66,30,.6),transparent);"></div>
    </div>
    <div style="font-size:40px;font-style:italic;color:#5c4326;max-width:1150px;line-height:1.45;">{subtitle_esc}</div>
  </div>

  <div style="position:absolute;left:0;right:0;bottom:70px;display:flex;flex-direction:column;
    align-items:center;gap:14px;">
    <div style="font-family:{fonts['title_sc']};font-size:26px;letter-spacing:5px;color:{_CHROME};">
      {index} / {total} Categories</div>
    <div style="display:flex;gap:14px;">{dots}</div>
    <div style="font-size:22px;letter-spacing:3px;color:{_MUTED};">AOE2MATCHUP.COM</div>
  </div>
"""
    return _page_open(fonts, "Category Title") + body + _PAGE_CLOSE


def make_category_explanation_card(title: str, subtitle: str, index: int, total: int,
                                    category_key: str = "expected_win") -> Image.Image:
    """Full-screen 1920x1080 explanation card: small-caps "Category" chip, huge
    (150px) 'IM Fell English' title tinted by category, a divider rule with a
    central diamond, an italic subtitle, and a bottom "i / total Categories" +
    diamond progress trail (filled = current) + brand line."""
    return _render_to_image(build_category_explanation_html(title, subtitle, index, total,
                                                             category_key))


# ---------------------------------------------------------------------------
# Card 2 — full category ranking
# ---------------------------------------------------------------------------
def _default_value_header(category_key: str, subject_short: str) -> str:
    if category_key in _WIN_CATEGORIES:
        return f"{subject_short} HP Left"
    if category_key in _LOSS_CATEGORIES:
        return "Enemy HP Left"
    return "Win Chance"


def _value_desc(category_key: str) -> str:
    return "showing win chance" if category_key == "coin_flip" else "showing % HP remaining"


def _order_label(category_key: str) -> str:
    return "cheapest first" if category_key in _LOSS_CATEGORIES else "most expensive first"


def _row_value(row: dict, category_key: str) -> float:
    if category_key in _WIN_CATEGORIES:
        return float(row.get("subject_hp") or 0)
    if category_key in _LOSS_CATEGORIES:
        return float(row.get("opp_hp") or 0)
    return float(row.get("wr") or 0) * 100.0


# sizing tiers: at <=~13 rows-per-column the layout matches the mockup
# exactly; beyond that, font/padding/gap shrink together so up to ~24
# rows/column (a 48-row expected_loss category, 2 columns) still fits the
# fixed list panel. Rather than guess the shrink factor, _fit_sizing()
# actually measures the rendered column height via headless Chrome
# (--dump-dom) and iterates until it fits — text metrics for serif webfonts
# don't scale predictably enough to trust a closed-form estimate.
_BASE_SIZING = dict(rank_font=26, name_font=27, value_font=28, tag_font=19,
                    header_font=22, pad_v=5, gap=4, header_pad_v=6)
_CONTENT_H = (H - 60 - 285) - 2 * 28   # panel bottom(60)/top(285)/pad_v(28) — see panel layout
_COLUMN_W = 812                        # (1920 - 80*2 - 40*2 - 56) / 2, matches the grid column


def _scaled_sizing(scale: float) -> dict:
    scale = max(scale, 0.28)
    return dict(scale=scale, **{
        k: max(1, round(v * scale)) for k, v in _BASE_SIZING.items()
    })


def _diamond_sep() -> str:
    return f'<div style="width:8px;height:8px;background:{_CHROME};transform:rotate(45deg);flex:none;"></div>'


def _ranking_column_html(rows: list[dict], sizing: dict, value_header: str, sc_font: str) -> str:
    header = (f'<div style="display:flex;align-items:center;gap:16px;'
              f'padding:{sizing["header_pad_v"]}px 16px;margin-bottom:{sizing["gap"]}px;'
              f'border-bottom:1.5px solid rgba(107,74,30,.45);">'
              f'<span style="width:44px;font-family:{sc_font};font-size:{sizing["header_font"]}px;'
              f'letter-spacing:2px;color:{_CHROME};">#</span>'
              f'<span style="flex:1;font-family:{sc_font};font-size:{sizing["header_font"]}px;'
              f'letter-spacing:2px;color:{_CHROME};">Unit</span>'
              # natural width + nowrap (not the rows' fixed 170px): the header may
              # carry the subject's FULL name ("Elite Temple Guard HP Left") and
              # still right-aligns flush with the value column's right edge.
              f'<span style="margin-left:auto;white-space:nowrap;text-align:right;'
              f'font-family:{sc_font};'
              f'font-size:{sizing["header_font"]}px;letter-spacing:2px;color:{_CHROME};">'
              f'{html.escape(value_header)}</span></div>')

    row_html = []
    for r in rows:
        bg = "rgba(107,74,30,.16)" if r["filmed"] else "transparent"
        border = _CHROME if r["filmed"] else "transparent"
        ink = _INK_DARK if r["bold"] else _ROW_NAME
        name_weight = 800 if r["bold"] else 600
        value_weight = 800 if r["bold"] else 700
        tag = (f'<span style="font-family:{sc_font};font-size:{sizing["tag_font"]}px;'
              f'letter-spacing:2px;color:#ecdfc2;background:{_CHROME};padding:2px 12px;'
              f'flex:none;">Shown</span>' if r["filmed"] else "")
        row_html.append(
            f'<div style="display:flex;align-items:center;gap:16px;'
            f'padding:{sizing["pad_v"]}px 16px;background:{bg};border:1.5px solid {border};">'
            f'<span style="width:44px;font-family:{sc_font};font-size:{sizing["rank_font"]}px;'
            f'color:#8a6428;flex:none;">{r["rank"]}</span>'
            f'<span style="flex:1;font-size:{sizing["name_font"]}px;font-weight:{name_weight};'
            f'color:{ink};min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'
            f'{r["name"]} <span style="color:{_ROW_CIV};font-weight:500;">({r["civ"]})</span></span>'
            f'{tag}'
            f'<span style="width:170px;text-align:right;font-size:{sizing["value_font"]}px;'
            f'font-weight:{value_weight};color:{ink};flex:none;">{r["value_txt"]}</span></div>')
    return (f'<div style="display:flex;flex-direction:column;gap:{sizing["gap"]}px;min-width:0;">'
           f'{header}{"".join(row_html)}</div>')


def _measure_column_height(column_html: str, fonts: dict) -> float | None:
    """Actual rendered height (px) of a column's HTML at _COLUMN_W width, via
    headless Chrome's --dump-dom (runs scripts/layout, no screenshot needed).
    Returns None if measurement fails (caller falls back to keeping sizing)."""
    marker = "COLH"
    page = f"""<!doctype html><html><head><meta charset="utf-8">
{fonts['link']}
<style>*{{box-sizing:border-box;}}body{{margin:0;font-family:{fonts['body']};}}</style>
</head><body>
<div id="col" style="width:{_COLUMN_W}px;">{column_html}</div>
<div id="m"></div>
<script>
function measure() {{
  document.getElementById('m').textContent =
    '{marker}:' + document.getElementById('col').scrollHeight + ':{marker}';
}}
// Measure only once the webfonts have actually swapped in — measuring
// against fallback-font metrics (still active mid-parse/mid-fetch)
// under-reports the height and causes clipping in the real card.
if (document.fonts && document.fonts.ready) {{
  document.fonts.ready.then(measure).catch(measure);
  setTimeout(measure, 4000);  // safety net if fonts.ready never resolves
}} else {{
  setTimeout(measure, 1500);
}}
</script>
</body></html>"""
    try:
        browser = _find_browser()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "measure.html"
            p.write_text(page, encoding="utf-8")
            cmd = [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
                   "--virtual-time-budget=6000", "--dump-dom", p.as_uri()]
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout
        m = re.search(marker + r":(\d+):" + marker, out)
        return float(m.group(1)) if m else None
    except Exception:
        return None


def _fit_sizing(tallest_col: list[dict], value_header: str, fonts: dict,
                content_h: float = _CONTENT_H) -> dict:
    """Start at the mockup's default sizing; if the taller column's measured
    height overflows the panel, shrink (font/padding/gap together) and
    re-measure, up to a few iterations, so nothing clips."""
    scale = 1.0
    sizing = _scaled_sizing(scale)
    for _ in range(4):
        col_html = _ranking_column_html(tallest_col, sizing, value_header, fonts["title_sc"])
        measured = _measure_column_height(col_html, fonts)
        if measured is None or measured <= content_h:
            break
        scale = scale * (content_h * 0.96 / measured)
        sizing = _scaled_sizing(scale)
    return sizing


def build_category_ranking_html(title: str, rows: list[dict], filmed_keys, category_key: str,
                                value_header: str | None, subject_short: str,
                                max_rows: int = 20) -> str:
    fonts = _font_stack()
    accent = _accent(category_key)
    filmed_set = {tuple(k) for k in (filmed_keys or [])}
    value_header = value_header or _default_value_header(category_key, subject_short)

    # cap at max_rows (rows arrive cost-sorted, so this keeps the cost-extreme
    # top); a truncated list gets a bottom banner pointing at the full list.
    n_total = len(rows)
    truncated = max_rows is not None and n_total > max_rows
    if truncated:
        rows = rows[:max_rows]

    n = len(rows)
    built = []
    for i, r in enumerate(rows):
        value = _row_value(r, category_key)
        pct = round(value)
        bold = category_key != "coin_flip" and pct > 70
        built.append(dict(
            rank=i + 1,
            name=html.escape(str(r.get("name", ""))),
            civ=html.escape(str(r.get("civ", ""))),
            value_txt=f"{pct}%",
            bold=bold,
            filmed=(r.get("civ"), r.get("slug")) in filmed_set,
        ))

    rows_per_col = max(1, math.ceil(n / 2)) if n else 0
    left, right = built[:rows_per_col], built[rows_per_col:]
    # a truncated card gives up 70px of panel to the bottom banner
    panel_bottom = 130 if truncated else 60
    content_h = (H - panel_bottom - 285) - 2 * 28
    sizing = _fit_sizing(left, value_header, fonts, content_h)  # left >= right in length

    title_esc = html.escape(str(title))
    order_label = _order_label(category_key)
    value_desc = _value_desc(category_key)
    count_label = (f"top {n} of {n_total}" if truncated
                   else f"{n} matchup{'s' if n != 1 else ''}")

    header_block = f"""
  <div style="position:absolute;left:100px;top:60px;right:100px;display:flex;flex-direction:column;gap:10px;">
    <div style="display:flex;align-items:center;gap:16px;">
      <div style="border:1.5px solid {_CHROME};color:{_CHROME};font-family:{fonts['title_sc']};
        letter-spacing:5px;font-size:24px;padding:5px 22px;">Category Ranking</div>
      <div style="height:1px;flex:1;background:linear-gradient(90deg,rgba(94,66,30,.55),transparent);"></div>
    </div>
    <div style="font-family:{fonts['title']};font-size:72px;line-height:1;color:{accent};
      text-shadow:0 2px 0 rgba(236,223,194,.8), 0 3px 4px rgba(94,66,30,.35);">{title_esc}</div>
    <div style="display:flex;gap:16px;align-items:center;font-family:{fonts['title_sc']};
      font-size:22px;letter-spacing:2px;color:{_CHROME};">
      <span>{count_label}</span>
      {_diamond_sep()}
      <span>{order_label}</span>
      {_diamond_sep()}
      <span>{value_desc}</span>
    </div>
  </div>
"""
    panel = f"""
  <div style="position:absolute;left:80px;right:80px;top:285px;bottom:{panel_bottom}px;
    background:rgba(236,223,194,.75);border:2px solid {_CHROME};
    box-shadow:0 0 0 5px rgba(107,74,30,.12), 0 18px 40px rgba(94,66,30,.3);
    padding:28px 40px;display:grid;grid-template-columns:1fr 1fr;column-gap:56px;
    align-content:start;overflow:hidden;">
    {_ranking_column_html(left, sizing, value_header, fonts["title_sc"])}
    {_ranking_column_html(right, sizing, value_header, fonts["title_sc"])}
  </div>
"""
    banner = ""
    if truncated:
        banner = f"""
  <div style="position:absolute;left:80px;right:80px;bottom:34px;display:flex;
    align-items:center;justify-content:center;gap:16px;font-family:{fonts['title_sc']};
    font-size:24px;letter-spacing:3px;color:{_CHROME};">
    <span>All {n_total} matchups at</span>
    {_diamond_sep()}
    <span style="color:#3d2a16;">AOE2MATCHUP.COM</span>
  </div>
"""
    return _page_open(fonts, "Ranking List") + header_block + panel + banner + _PAGE_CLOSE


def build_zero_category_html(title: str, subtitle: str, *, big_text: str = "NONE",
                             category_key: str = "unexpected_win") -> str:
    fonts = _font_stack()
    accent = _accent(category_key)
    title_esc = html.escape(str(title))
    big_esc = html.escape(str(big_text))
    subtitle_esc = html.escape(str(subtitle))

    body = f"""
  <div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;
    justify-content:center;gap:22px;padding:0 200px;text-align:center;">
    <div style="border:1.5px solid {_CHROME};color:{_CHROME};font-family:{fonts['title_sc']};
      letter-spacing:6px;font-size:28px;padding:6px 28px;">Category</div>
    <div style="font-family:{fonts['title']};font-size:110px;line-height:1;color:{_TITLE_NEUTRAL};
      text-shadow:0 2px 0 rgba(236,223,194,.8), 0 3px 4px rgba(94,66,30,.35);">{title_esc}</div>
    <div style="font-family:{fonts['title_sc']};font-size:220px;line-height:1;color:{accent};
      letter-spacing:14px;text-shadow:0 3px 0 rgba(236,223,194,.8), 0 4px 6px rgba(94,66,30,.4);">{big_esc}</div>
    <div style="display:flex;align-items:center;gap:18px;width:640px;">
      <div style="height:1.5px;flex:1;background:linear-gradient(90deg,transparent,rgba(94,66,30,.6));"></div>
      <div style="width:10px;height:10px;background:{_CHROME};transform:rotate(45deg);flex:none;"></div>
      <div style="height:1.5px;flex:1;background:linear-gradient(90deg,rgba(94,66,30,.6),transparent);"></div>
    </div>
    <div style="font-size:38px;font-style:italic;color:#5c4326;max-width:1150px;line-height:1.45;">{subtitle_esc}</div>
  </div>

  <div style="position:absolute;left:0;right:0;bottom:70px;display:flex;flex-direction:column;
    align-items:center;gap:14px;">
    <div style="font-size:22px;letter-spacing:3px;color:{_MUTED};">AOE2MATCHUP.COM</div>
  </div>
"""
    return _page_open(fonts, "Zero Category") + body + _PAGE_CLOSE


def make_zero_category_card(title: str, subtitle: str, *, big_text: str = "NONE",
                            category_key: str = "unexpected_win") -> Image.Image:
    """Full-screen 1920x1080 zero-state card for a category with no matching fights
    (e.g. "Unexpected Wins" when there are none): same parchment chrome as
    `make_category_explanation_card` — small-caps "Category" chip, title, a big
    tinted `big_text` treatment ("NONE" by default), divider, italic subtitle —
    but with no progress-dots block (there's no fight sequence to mark progress
    through). `category_key` only selects the accent tint (green for a win
    category, red for a loss category)."""
    return _render_to_image(build_zero_category_html(title, subtitle, big_text=big_text,
                                                      category_key=category_key))


def build_coinflip_odds_html(title: str, rows: list[dict], subtitle: str,
                             category_key: str = "coin_flip") -> str:
    """rows: [{name, civ, odds}] — `odds` is a pre-formatted display string
    (e.g. "67 : 33")."""
    fonts = _font_stack()
    accent = _accent(category_key)
    title_esc = html.escape(str(title))
    subtitle_esc = html.escape(str(subtitle))

    row_html = []
    for r in rows:
        name = html.escape(str(r.get("name", "")))
        civ = html.escape(str(r.get("civ", "")))
        odds = html.escape(str(r.get("odds", "")))
        row_html.append(
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'gap:24px;padding:20px 36px;background:rgba(236,223,194,.65);'
            f'border:1.5px solid {_CHROME};">'
            f'<span style="font-size:36px;font-weight:700;color:{_ROW_NAME};">{name} '
            f'<span style="color:{_ROW_CIV};font-weight:500;font-size:27px;">({civ})</span></span>'
            f'<span style="font-family:{fonts["title_sc"]};font-size:36px;letter-spacing:2px;'
            f'color:{accent};">{odds}</span></div>')

    body = f"""
  <div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;
    justify-content:center;gap:32px;padding:0 260px;text-align:center;">
    <div style="border:1.5px solid {_CHROME};color:{_CHROME};font-family:{fonts['title_sc']};
      letter-spacing:6px;font-size:28px;padding:6px 28px;">Category</div>
    <div style="font-family:{fonts['title']};font-size:120px;line-height:1;color:{accent};
      text-shadow:0 2px 0 rgba(236,223,194,.8), 0 3px 4px rgba(94,66,30,.35);">{title_esc}</div>
    <div style="display:flex;flex-direction:column;gap:18px;width:1150px;">{"".join(row_html)}</div>
    <div style="font-size:32px;font-style:italic;color:#5c4326;max-width:1200px;line-height:1.4;">{subtitle_esc}</div>
  </div>
"""
    return _page_open(fonts, "Coin Flip Odds") + body + _PAGE_CLOSE


def make_coinflip_odds_card(title: str, rows: list[dict], subtitle: str,
                            category_key: str = "coin_flip") -> Image.Image:
    """Full-screen 1920x1080 odds-listing card for the "too close to call" close:
    same parchment chrome, one row per matchup (`rows` = [{name, civ, odds}], a
    pre-formatted "NN : NN" odds string per row) stacked in a bordered plate,
    plus an italic closing subtitle line. Generic — no ETG-specific text baked
    in; caller supplies title/rows/subtitle."""
    return _render_to_image(build_coinflip_odds_html(title, rows, subtitle, category_key))


def make_category_ranking_card(title: str, rows: list[dict], filmed_keys, category_key: str = "expected_win",
                               value_header: str | None = None, subject_short: str = "Subject",
                               max_rows: int = 20) -> Image.Image:
    """Full-screen 1920x1080 ranked-list card. `rows` = results-JSON row dicts
    (name, civ, slug, cost, subject_hp, opp_hp, wr, ...) already sorted by the
    caller (most-expensive-first for win/coin-flip categories, cheapest-first
    for loss categories). `filmed_keys` = an iterable of (civ, slug) tuples —
    those rows get a "Shown" tag + highlight plate. The value column shows %
    HP remaining (subject's own for win categories, the opponent's for loss
    categories, subject win% for coin_flip) — NOT cost, despite the mockup.
    `value_header` overrides the per-column header text (default derived from
    `category_key` + `subject_short` — pass the subject's FULL unit name, e.g.
    "Elite Temple Guard HP Left" / "Enemy HP Left" /
    "Win Chance"). Rows whose displayed % is > 70 render bold (except
    coin_flip).

    Only the top `max_rows` (20) by the caller's cost order are listed; a
    longer category gets a bottom "All N matchups at AOE2MATCHUP.COM" banner
    in place of the tail (user rule 2026-07-19). VIDEO-ASSEMBLY RULE (enforced
    by the storyboard, not here): categories with FEWER THAN 4 units get no
    ranking card at all — every unit in them was already shown on camera."""
    html_str = build_category_ranking_html(title, rows, filmed_keys, category_key,
                                           value_header, subject_short, max_rows)
    return _render_to_image(html_str)


# ---------------------------------------------------------------------------
# Render helper — headless Chrome screenshot -> PIL Image
# ---------------------------------------------------------------------------
def _render_to_image(html_str: str) -> Image.Image:
    with tempfile.TemporaryDirectory() as td:
        out_png = Path(td) / "card.png"
        _screenshot(html_str, out_png, W, H, scale=1, extra_args=["--virtual-time-budget=10000"])
        return Image.open(out_png).copy()


# ---------------------------------------------------------------------------
# CLI demo (Elite Temple Guard / expected_win)
# ---------------------------------------------------------------------------
def _demo_data():
    import json
    repo_root = Path(__file__).resolve().parents[3]
    p = repo_root / "apps" / "video" / "sim_v2" / "results" / "elite_temple_guard_muisca.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    rows = [r for r in d["rows"] if r.get("category") == "expected_win"]
    rows.sort(key=lambda r: -(r.get("cost") or 0))
    filmed = {tuple(pair) for pair in d["filmed"].get("expected_win", [])}
    return rows, filmed


def main(argv: list[str]) -> None:
    mode = argv[1] if len(argv) > 1 else "explain"
    out = Path(argv[2]) if len(argv) > 2 else (
        Path(__file__).parent / "samples" / f"_category_card_{mode}.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    if mode == "rank":
        rows, filmed = _demo_data()
        img = make_category_ranking_card("Expected Wins", rows, filmed, "expected_win",
                                         subject_short="Elite Temple Guard")
    elif mode == "zero":
        img = make_zero_category_card(
            "Unexpected Wins",
            "The Elite Temple Guard never wins a fight it isn't favored in. "
            "76 matchups tested — zero upsets in its favor.",
            category_key="unexpected_win")
    elif mode == "coinflip":
        img = make_coinflip_odds_card(
            "Too Close To Call",
            [dict(name="Elite Konnik", civ="Bulgarians", odds="67 : 33"),
             dict(name="Condottiero", civ="Italians", odds="47 : 53"),
             dict(name="Elite Huskarl", civ="Goths", odds="40 : 60")],
            "These could go either way — full numbers at AOE2MATCHUP.COM.",
            category_key="coin_flip")
    else:
        img = make_category_explanation_card(
            "Expected Wins",
            "The Temple Guard has a damage bonus against these units — and it "
            "shows. 23 matchups tested. Every one a convincing win.",
            1, 4, "expected_win")
    img.convert("RGB").save(out)
    print("WROTE", out)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # apps/video/
    main(sys.argv)

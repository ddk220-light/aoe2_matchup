"""
render_card.py — render matchup cards to transparent PNGs, styled like the
aoe2matchup.com UI, via headless Chrome/Edge (no extra Python deps).

Cards:
  render_intro(u1, u2)          - full pre-fight card: icons, stats with PER-STAT
                                  WIN HIGHLIGHTING (winner's value gold + ▲),
                                  cost, attack bonuses, unique techs, upgrades.
  render_outro(result, u1, u2)  - post-fight results card: winner banner, final
                                  survivors, HP bars, sim verdict.
  render_hud_card(u1, u2)       - compact static strip (legacy; live HUD is in hud.py).

`render_card()` is kept as an alias of render_intro for back-compat.
"""
from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

PALETTE = dict(
    gold="#c9a84c", gold_light="#dbb960", gold_dark="#8b6914",
    bg_deep="#120d07", bg="#1e1610", bg_warm="#2a1f14",
    text="#efe6d2", text_muted="#a89878", red="#a83030",
    green="#6eaa46", food="#d98a5a", wood="#b07a45", gold_res="#e6c85a",
)

# stats where a LOWER value is better
_LOWER_BETTER = {"Reload"}

_CHROME_CANDIDATES = [
    # Windows
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    # macOS
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    # Linux
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
]


def _find_browser() -> str:
    for p in _CHROME_CANDIDATES:
        if Path(p).exists():
            return p
    found = (shutil.which("chrome") or shutil.which("google-chrome")
             or shutil.which("chromium") or shutil.which("msedge"))
    if found:
        return found
    raise RuntimeError("No headless Chrome/Edge/Chromium found.")


def _img_data_uri(path: str) -> str:
    if not path or not Path(path).exists():
        return ""
    data = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def _num(val) -> float | None:
    """Pull a float out of a stat value like '85%', '3.5s', 9, 0.96."""
    if val is None:
        return None
    m = re.search(r"-?\d+(\.\d+)?", str(val))
    return float(m.group()) if m else None


def _stat_winners(u1: dict, u2: dict) -> dict:
    """label -> 1 / 2 / 0 (tie/incomparable) for stats present on BOTH units."""
    s1 = {k: v for k, v in u1.get("stats", [])}
    s2 = {k: v for k, v in u2.get("stats", [])}
    out = {}
    for label in set(s1) & set(s2):
        a, b = _num(s1[label]), _num(s2[label])
        if a is None or b is None or a == b:
            out[label] = 0
        else:
            lower = label in _LOWER_BETTER
            if (a < b) == lower:
                out[label] = 1
            else:
                out[label] = 2
    return out


def _res_chips(cost: dict) -> str:
    chips = []
    for key, color, label in (("food", PALETTE["food"], "F"),
                              ("wood", PALETTE["wood"], "W"),
                              ("gold", PALETTE["gold_res"], "G")):
        if cost.get(key):
            chips.append(f'<span class="res" style="color:{color}">{label} {cost[key]}</span>')
    return " ".join(chips)


def _stat_rows(stats: list, side: int, winners: dict) -> str:
    rows = []
    for k, v in stats:
        win = winners.get(k, None) == side
        cls = "stat win" if win else "stat"
        mark = ' <span class="up">&#9650;</span>' if win else ""
        rows.append(f'<div class="{cls}"><span class="k">{k}</span>'
                    f'<span class="v">{v}{mark}</span></div>')
    return "".join(rows)


def _list_chips(items: list, cls: str) -> str:
    return "".join(f'<span class="{cls}">{i}</span>' for i in items)


def _unique_block(unique: list) -> str:
    if not unique:
        return ""
    rows = []
    for u in unique:
        rows.append(f'<div class="uniq"><span class="star">&#9733;</span> {u["name"]}'
                    f'<span class="uniq-meta">{u.get("building","")} &middot; '
                    f'{_res_chips(u.get("cost", {}))}</span></div>')
    return f'<div class="row-label">Unique tech</div>{"".join(rows)}'


def _unit_panel(u: dict, side: int, winners: dict) -> str:
    icon = _img_data_uri(u.get("icon", ""))
    icon_html = (f'<img class="icon" src="{icon}" alt="">' if icon
                 else '<div class="icon"></div>')
    bonuses = "".join(f'<span class="bonus">+{b["amount"]} vs {b["vs"]}</span>'
                      for b in u.get("attack_bonuses", []))
    bonus_block = (f'<div class="row-label">Attack bonus</div>'
                   f'<div class="chips">{bonuses}</div>') if bonuses else ""
    # Upgrades and Civ-bonuses sections intentionally omitted from the video card —
    # the overview keeps to stats, cost, attack bonuses, and unique tech.
    return f"""
    <div class="unit">
      <div class="head">
        {icon_html}
        <div class="title">
          <div class="name">{u['name']}</div>
          <div class="sub">{u['civ']} &middot; {u.get('unit_type','')}</div>
          <div class="cost">{_res_chips(u['cost'])}
            <span class="total">= {u['cost']['total']} res</span></div>
        </div>
      </div>
      <div class="stats">{_stat_rows(u['stats'], side, winners)}</div>
      {bonus_block}{_unique_block(u.get('unique_techs', []))}
    </div>"""


def _css() -> str:
    P = PALETTE
    return f"""
* {{ box-sizing:border-box; }}
html,body {{ margin:0; padding:0; background:transparent;
  font-family:'Palatino Linotype','Book Antiqua',Georgia,serif; color:{P['text']}; }}
.wrap {{ padding:26px; }}
.banner {{ text-align:center; font-size:32px; letter-spacing:2px; color:{P['gold']};
  text-transform:uppercase; margin-bottom:14px; text-shadow:0 2px 8px #000; }}
.banner .brand {{ display:block; font-size:13px; color:{P['text_muted']};
  letter-spacing:3px; margin-top:2px; }}
.matchup {{ display:flex; align-items:stretch; justify-content:center; gap:22px; }}
.unit {{ width:440px; background:linear-gradient(160deg,{P['bg_warm']},{P['bg']});
  border:2px solid {P['gold_dark']}; border-radius:14px; padding:18px 20px;
  box-shadow:0 6px 26px rgba(0,0,0,.6), inset 0 0 0 1px rgba(201,168,76,.12); }}
.head {{ display:flex; gap:16px; align-items:center;
  border-bottom:1px solid rgba(201,168,76,.25); padding-bottom:13px; }}
.icon {{ width:108px; height:108px; border-radius:12px; border:3px solid {P['gold']};
  background:{P['bg_deep']}; object-fit:cover; box-shadow:0 0 14px rgba(201,168,76,.25); }}
.title .name {{ font-size:28px; color:{P['gold_light']}; line-height:1.05; }}
.title .sub {{ font-size:15px; color:{P['text_muted']}; margin-top:4px; }}
.cost {{ margin-top:9px; font-size:16px; }}
.res {{ font-weight:bold; margin-right:9px; }}
.total {{ color:{P['text_muted']}; font-size:13px; }}
.stats {{ display:grid; grid-template-columns:1fr 1fr; gap:6px 18px; margin:14px 0 4px; }}
.stat {{ display:flex; justify-content:space-between;
  border-bottom:1px dotted rgba(168,152,120,.3); padding:4px 0; font-size:17px; }}
.stat .k {{ color:{P['text_muted']}; }}
.stat .v {{ color:{P['text']}; font-weight:bold; }}
.stat.win .v {{ color:{P['gold_light']}; }}
.stat.win {{ background:linear-gradient(90deg,transparent,rgba(201,168,76,.10));
  border-bottom-color:rgba(201,168,76,.5); }}
.up {{ color:{P['green']}; font-size:11px; }}
.row-label {{ color:{P['gold']}; font-size:12px; text-transform:uppercase;
  letter-spacing:1px; margin:12px 0 5px; }}
.chips {{ display:flex; flex-wrap:wrap; gap:5px; }}
.upg,.civb,.bonus {{ font-size:12px; padding:2px 8px; border-radius:10px;
  background:rgba(201,168,76,.10); border:1px solid rgba(201,168,76,.3); color:{P['text']}; }}
.bonus {{ background:rgba(168,48,48,.18); border-color:rgba(168,48,48,.5); color:#e9b3b3; }}
.civb {{ background:rgba(120,160,90,.12); border-color:rgba(120,160,90,.4); }}
.uniq {{ font-size:15px; color:{P['gold_light']}; margin:3px 0;
  display:flex; align-items:baseline; gap:6px; }}
.uniq .star {{ color:{P['gold']}; }}
.uniq-meta {{ color:{P['text_muted']}; font-size:12px; margin-left:auto; }}
.vs {{ align-self:center; font-size:48px; color:{P['gold']}; font-weight:bold;
  text-shadow:0 2px 10px #000; }}
/* outro */
.result-banner {{ text-align:center; margin-bottom:18px; }}
.result-banner .who {{ font-size:46px; color:{P['gold']}; text-transform:uppercase;
  letter-spacing:3px; text-shadow:0 3px 12px #000; }}
.result-banner .sub {{ font-size:16px; color:{P['text_muted']}; margin-top:6px; }}
.score {{ display:flex; justify-content:center; align-items:stretch; gap:26px; }}
.scol {{ width:330px; text-align:center; background:linear-gradient(160deg,{P['bg_warm']},{P['bg']});
  border:2px solid {P['gold_dark']}; border-radius:14px; padding:18px; }}
.scol.win {{ border-color:{P['gold']}; box-shadow:0 0 22px rgba(201,168,76,.35); }}
.scol.lose {{ opacity:.78; }}
.scol img {{ width:96px; height:96px; border-radius:12px; border:3px solid {P['gold']}; }}
.scol .nm {{ font-size:22px; color:{P['gold_light']}; margin:8px 0 2px; }}
.scol .big {{ font-size:62px; font-weight:bold; color:{P['text']}; line-height:1; margin:6px 0; }}
.scol .lbl {{ font-size:14px; color:{P['text_muted']}; }}
.hpbar {{ height:12px; background:{P['bg_deep']}; border-radius:6px; margin-top:12px;
  overflow:hidden; border:1px solid rgba(201,168,76,.3); }}
.hpbar > i {{ display:block; height:100%; background:{P['green']}; }}
"""


def build_intro_html(u1: dict, u2: dict, title: str | None = None) -> str:
    winners = _stat_winners(u1, u2)
    title = title or f"{u1['name']}  vs  {u2['name']}"
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{_css()}</style></head>
<body><div class="wrap">
  <div class="banner">{title}<span class="brand">aoe2matchup.com</span></div>
  <div class="matchup">{_unit_panel(u1,1,winners)}<div class="vs">VS</div>{_unit_panel(u2,2,winners)}</div>
</div></body></html>"""


def build_outro_html(result, u1: dict, u2: dict) -> str:
    P = PALETTE
    win = result.winner
    if win == 1:
        who = f"{u1['name']} wins"
    elif win == 2:
        who = f"{u2['name']} wins"
    else:
        who = "Draw"
    # Describe the battle we just watched: who won and how many units are left.
    if win == 0:
        sub = (f"Both sides spent &middot; {u1['name']} {result.survivors1} "
               f"&middot; {u2['name']} {result.survivors2} left")
    else:
        w_name = u1['name'] if win == 1 else u2['name']
        w_surv = result.survivors1 if win == 1 else result.survivors2
        w_start = result.start1 if win == 1 else result.start2
        l_surv = result.survivors2 if win == 1 else result.survivors1
        sub = (f"{w_surv} of {w_start} {w_name} still standing "
               f"&middot; {l_surv} left on the other side")

    def col(u, side, surv, start, hp):
        cls = "scol win" if win == side else ("scol lose" if win else "scol")
        icon = _img_data_uri(u.get("icon", ""))
        img = f'<img src="{icon}">' if icon else ""
        return f"""<div class="{cls}">{img}
          <div class="nm">{u['name']}</div>
          <div class="big">{surv}</div>
          <div class="lbl">of {start} survived &middot; {hp:.0%} HP</div>
          <div class="hpbar"><i style="width:{max(0,min(100,hp*100)):.0f}%"></i></div></div>"""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{_css()}</style></head>
<body><div class="wrap">
  <div class="result-banner"><div class="who">{who}</div><div class="sub">{sub}</div></div>
  <div class="score">
    {col(u1,1,result.survivors1,result.start1,result.hp1_pct)}
    <div class="vs">VS</div>
    {col(u2,2,result.survivors2,result.start2,result.hp2_pct)}
  </div>
</div></body></html>"""


def _screenshot(html: str, out_png, width: int, height: int, scale: int = 2,
                browser: str | None = None) -> Path:
    out_png = Path(out_png).resolve()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    browser = browser or _find_browser()
    with tempfile.TemporaryDirectory() as td:
        html_path = Path(td) / "card.html"
        html_path.write_text(html, encoding="utf-8")
        cmd = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
               "--no-sandbox", f"--force-device-scale-factor={scale}",
               "--default-background-color=00000000",
               f"--window-size={width},{height}", f"--screenshot={out_png}",
               html_path.as_uri()]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if not out_png.exists():
            raise RuntimeError(f"Render failed (exit {proc.returncode}).\n{proc.stderr[-800:]}")
    return out_png


def render_intro(u1, u2, out_png, width=1340, height=760, scale=2, title=None) -> Path:
    return _screenshot(build_intro_html(u1, u2, title), out_png, width, height, scale)


def render_outro(result, u1, u2, out_png, width=1000, height=520, scale=2) -> Path:
    return _screenshot(build_outro_html(result, u1, u2), out_png, width, height, scale)


# back-compat
def render_card(u1, u2, out_png, mode="full", width=1340, height=760, scale=2,
                title=None, browser=None) -> Path:
    return render_intro(u1, u2, out_png, width, height, scale, title)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from overlay_data import get_unit_card
    from results import extract_sim_results
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    u1 = get_unit_card("Wu", "elite_fire_archer_wu")
    u2 = get_unit_card("Wu", "jian_swordsman_wu")
    s = Path(__file__).parent / "samples"
    print("intro:", render_intro(u1, u2, s / "firearcher_vs_jian_card.png"))
    res = extract_sim_results("Wu", "elite_fire_archer_wu", "Wu", "jian_swordsman_wu")
    print("outro:", render_outro(res, u1, u2, s / "firearcher_vs_jian_outro.png"))

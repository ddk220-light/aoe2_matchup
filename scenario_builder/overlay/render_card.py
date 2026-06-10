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


# Inline-SVG resource icons (no asset files in the repo) — drumstick / log ends / coin.
_RES_SVG = {
    "food": """<svg viewBox="0 0 24 24" class="ri"><circle cx="6.2" cy="18.2" r="2.6"
      fill="#ead9bd"/><circle cx="10" cy="21" r="2.6" fill="#ead9bd"/>
      <rect x="6" y="12" width="5" height="7" rx="2" transform="rotate(45 8.5 15.5)"
      fill="#ead9bd"/><ellipse cx="14.6" cy="8.8" rx="7.6" ry="6.2"
      transform="rotate(-38 14.6 8.8)" fill="#c46a3f"/></svg>""",
    "wood": """<svg viewBox="0 0 24 24" class="ri"><g fill="#8a5a2e" stroke="#4d2f14"
      stroke-width="1"><circle cx="7.5" cy="16.5" r="5"/><circle cx="16.5" cy="16.5" r="5"/>
      <circle cx="12" cy="8.5" r="5"/></g><g fill="#cda06a"><circle cx="7.5" cy="16.5"
      r="2.3"/><circle cx="16.5" cy="16.5" r="2.3"/><circle cx="12" cy="8.5" r="2.3"/></g></svg>""",
    "gold": """<svg viewBox="0 0 24 24" class="ri"><circle cx="12" cy="12" r="9.5"
      fill="#e6c85a" stroke="#8b6914" stroke-width="1.6"/><circle cx="12" cy="12" r="5.6"
      fill="none" stroke="#a87f1e" stroke-width="1.4"/></svg>""",
}


def _res_iconic(cost: dict, mult: int = 1, sep: str = "&ensp;") -> str:
    """'food/wood/gold' amounts (x mult) as icon+number chips."""
    parts = []
    for key in ("food", "wood", "gold"):
        amt = cost.get(key) or 0
        if amt:
            parts.append(f'<span class="resi">{_RES_SVG[key]}{int(amt * mult):,}</span>')
    return sep.join(parts)


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


def _applicable_bonuses(attacker: dict, defender: dict) -> list:
    """The attacker's attack bonuses that actually apply against THIS defender — i.e.
    '+X vs <class>' only when the defender belongs to that armor class."""
    dac = set(defender.get("armor_class_ids", []))
    return [b for b in attacker.get("attack_bonuses", []) if b.get("vs_id") in dac]


def _unit_panel(u: dict, side: int, winners: dict, bonuses_list: list, count: int) -> str:
    icon = _img_data_uri(u.get("icon", ""))
    icon_html = (f'<img class="icon" src="{icon}" alt="">' if icon
                 else '<div class="icon"></div>')
    if bonuses_list:
        chips = "".join(f'<span class="bonus">+{b["amount"]} vs {b["vs"]}</span>'
                        for b in bonuses_list)
    else:
        chips = '<span class="none">no bonus applies</span>'
    bonus_block = f'<div class="row-label">Bonus vs opponent</div><div class="chips">{chips}</div>'
    total_res = int(count * (u["cost"]["total"] or 0))
    army_line = (f'<div class="army"><b>{count}</b> units &middot; '
                 f'<b>{total_res}</b> resources</div>')
    # batch-trained units (Blackwood Archers come 2 per train): show the listed
    # per-train price; totals already use the per-unit cost
    tr = u["cost"].get("train")
    cost_chips = _res_chips(tr or u["cost"])
    each_tag = (f"= {tr['total']} res / {u['cost']['batch']} units" if tr
                else f"= {u['cost']['total']} res each")
    # Upgrades and Civ-bonuses sections intentionally omitted from the video card.
    return f"""
    <div class="unit">
      <div class="head">
        {icon_html}
        <div class="title">
          <div class="name">{u['name']}</div>
          <div class="sub">{u['civ']} &middot; {u.get('unit_type','')}</div>
          <div class="cost">{cost_chips}
            <span class="total">{each_tag}</span></div>
          {army_line}
        </div>
      </div>
      <div class="stats">{_stat_rows(u['stats'], side, winners)}</div>
      {bonus_block}
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
.army {{ margin-top:7px; font-size:17px; color:{P['gold_light']}; }}
.army b {{ color:{P['text']}; font-size:19px; }}
.none {{ font-size:12px; padding:2px 8px; border-radius:10px; color:{P['text_muted']};
  border:1px dashed rgba(168,152,120,.4); }}
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


def build_intro_html(u1: dict, u2: dict, title: str | None = None,
                     counts=(30, 30)) -> str:
    winners = _stat_winners(u1, u2)
    title = title or f"{u1['name']}  vs  {u2['name']}"
    b1 = _applicable_bonuses(u1, u2)
    b2 = _applicable_bonuses(u2, u1)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{_css()}</style></head>
<body><div class="wrap">
  <div class="banner">{title}<span class="brand">aoe2matchup.com</span></div>
  <div class="matchup">{_unit_panel(u1,1,winners,b1,counts[0])}<div class="vs">VS</div>{_unit_panel(u2,2,winners,b2,counts[1])}</div>
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


def build_outro_recap_html(u1: dict, u2: dict) -> str:
    """A minimal post-fight recap: both units side by side, NO winner / survivor
    counts (the automated pipeline doesn't measure them — see build_run.py). Just a
    clean 'that was the matchup' bookend after the real footage."""
    def col(u):
        icon = _img_data_uri(u.get("icon", ""))
        img = f'<img src="{icon}">' if icon else ""
        return f"""<div class="scol">{img}
          <div class="nm">{u['name']}</div>
          <div class="lbl">{u['civ']} &middot; {u.get('unit_type','')}</div></div>"""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{_css()}</style></head>
<body><div class="wrap">
  <div class="result-banner"><div class="who">Battle Complete</div>
    <div class="sub">{u1['name']} &nbsp;vs&nbsp; {u2['name']}</div></div>
  <div class="score">
    {col(u1)}<div class="vs">VS</div>{col(u2)}
  </div>
</div></body></html>"""


def render_outro_recap(u1, u2, out_png, width=1000, height=440, scale=2) -> Path:
    return _screenshot(build_outro_recap_html(u1, u2), out_png, width, height, scale)


def _fmt_secs(s: float) -> str:
    return f"{s:.0f}s" if s >= 9.5 else f"{s:.1f}s"


def build_unit_panel_html(u: dict, opponent: dict, side: int, count: int) -> str:
    """A SINGLE unit's live card for compositing over the opening of the fight.

    Redesigned around what the viewer actually needs to predict the fight:
      * a DUEL block — damage per hit vs THIS opponent (attack + applicable bonuses
        - the right armor), effective DPS (attack rate + accuracy folded in), and
        hits/time to kill one opponent, charge attack included on the first hit;
      * a TRIMMED stat row — HP, Speed, and only the armor the opponent's damage
        type actually tests (plus Range for ranged units). No off-type armor, no
        raw Reload/Accuracy rows: they live inside the DPS/TTK numbers now;
      * cost with resource icons, army size and total;
      * the attack-bonus chips that feed the damage number.
    The side that kills faster gets the gold edge on its duel block."""
    from overlay.combat_math import duel, primary_damage_class
    mine = duel(u, opponent)
    theirs = duel(opponent, u)

    icon = _img_data_uri(u.get("icon", ""))
    icon_html = (f'<img class="icon" src="{icon}" alt="">' if icon
                 else '<div class="icon"></div>')
    total_res = int(count * (u["cost"]["total"] or 0))
    tr = u["cost"].get("train")        # batch-trained: show the listed per-train price
    per_tag = f' / {u["cost"]["batch"]}' if tr else ""
    cost_line = (f'{_res_iconic(tr or u["cost"])}'
                 f'<span class="x">{per_tag} &times; {count} = <b>{total_res:,}</b> res</span>')

    # duel block (gold edge when this side wins the time-to-kill race)
    duel_html = ""
    if mine:
        faster = bool(mine.get("ttk_s") is not None and theirs and theirs.get("ttk_s") is not None
                      and mine["ttk_s"] < theirs["ttk_s"])
        ttk = f' &middot; ~{_fmt_secs(mine["ttk_s"])}' if mine.get("ttk_s") else ""
        charge = ""
        if mine.get("charge"):
            ch = u.get("charge") or {}
            charge = (f'<div class="charge">&#9889; +{mine["charge"]:.0f} charge dmg on the '
                      f'first hit (recharges {ch.get("recharge_s", 0):.0f}s)</div>')
        dps = f"{mine['dps']:.1f}" if mine.get("dps") is not None else "&mdash;"
        duel_html = f"""
      <div class="duel{' edge' if faster else ''}">
        <div class="row-label">vs {opponent['name']}</div>
        <div class="dgrid">
          <div class="d"><span class="dv">{mine['dmg']:.0f}</span><span class="dk">dmg / hit</span></div>
          <div class="d"><span class="dv">{dps}</span><span class="dk">DPS</span></div>
          <div class="d wide"><span class="dv">{mine['hits']} hit{'s' if mine['hits'] != 1 else ''}{ttk}</span><span class="dk">to kill one</span></div>
        </div>
        {charge}
      </div>"""

    # trimmed stats: HP / Speed / the armor THEIR damage type tests / Range (ranged only)
    their_dmg_class = primary_damage_class(opponent.get("attacks") or {})
    arm_label, arm_val = (("Pierce Armor", u.get("pierce_armor"))
                          if their_dmg_class == 3 else ("Melee Armor", u.get("melee_armor")))
    rows = [("HP", u.get("hp"), opponent.get("hp")),
            ("Speed", u.get("speed"), opponent.get("speed")),
            (arm_label, arm_val, None)]
    if u.get("is_ranged") and u.get("range"):
        rows.append(("Range", u.get("range"), opponent.get("range")))
    stat_html = ""
    for k, v, ov in rows:
        v_num = _num(v)
        win = ov is not None and v_num is not None and _num(ov) is not None and v_num > _num(ov)
        mark = ' <span class="up">&#9650;</span>' if win else ""
        disp = (int(v_num) if v_num is not None and v_num == int(v_num)
                else round(v_num, 2) if v_num is not None else v)
        stat_html += (f'<div class="stat{" win" if win else ""}">'
                      f'<span class="k">{k}</span><span class="v">{disp}{mark}</span></div>')

    bonuses = _applicable_bonuses(u, opponent)
    if bonuses:
        chips = "".join(f'<span class="bonus">+{b["amount"]} vs {b["vs"]}</span>'
                        for b in bonuses)
    else:
        chips = '<span class="none">no bonus applies</span>'

    override = """
.wrap { padding:0; }
.unit { width:700px; padding:14px 24px 12px; position:relative;
  background:linear-gradient(160deg, rgba(42,31,20,0.86), rgba(18,13,7,0.86));
  border:2px solid rgba(201,168,76,0.65); border-radius:14px;
  box-shadow:0 5px 22px rgba(0,0,0,0.5), inset 0 0 0 1px rgba(201,168,76,0.10); }
.head { display:flex; gap:20px; align-items:center; padding:10px 14px 12px; border-radius:10px;
  background:linear-gradient(90deg, rgba(201,168,76,0.16), rgba(201,168,76,0.03));
  border-bottom:1px solid rgba(201,168,76,0.4); }
.icon { width:112px; height:112px; border-width:3px; }
.title .name { font-size:38px; text-shadow:0 2px 6px #000; }
.title .sub { font-size:20px; margin-top:3px; }
.cost { margin-top:8px; font-size:22px; display:flex; align-items:center; gap:4px; }
.resi { display:inline-flex; align-items:center; gap:4px; font-weight:bold; }
.ri { width:24px; height:24px; vertical-align:middle; }
.cost .x { color:#a89878; font-size:19px; margin-left:6px; }
.cost .x b { color:#efe6d2; }
.duel { margin:12px 0 2px; padding:10px 14px 11px; border-radius:10px;
  background:rgba(0,0,0,0.30); border:2px solid rgba(201,168,76,0.25); }
.duel.edge { border-color:#c9a84c; box-shadow:0 0 14px rgba(201,168,76,.30); }
.duel .row-label { margin:0 0 7px; font-size:17px; }
.dgrid { display:flex; gap:26px; align-items:baseline; }
.d { display:flex; align-items:baseline; gap:8px; }
.dv { font-size:34px; font-weight:bold; color:#efe6d2; }
.duel.edge .dv { color:#dbb960; }
.dk { font-size:16px; color:#a89878; }
.charge { margin-top:7px; font-size:17px; color:#e8c46a; }
.stats { display:grid; grid-template-columns:repeat(4, auto); gap:5px 24px;
  margin:12px 0 2px; justify-content:start; }
.stat { font-size:21px; padding:3px 10px 3px 6px; border-left:3px solid transparent;
  display:flex; gap:10px; border-bottom:1px dotted rgba(168,152,120,.3); }
.stat .k { color:#a89878; } .stat .v { color:#efe6d2; font-weight:bold; }
.stat.win { border-left-color:#c9a84c;
  background:linear-gradient(90deg, rgba(201,168,76,.16), transparent); }
.stat.win .v { color:#dbb960; }
.up { font-size:12px; }
.row-label { margin:9px 0 4px; font-size:14px; }
.chips { gap:6px; } .bonus, .none { font-size:16px; }
.tag { position:absolute; right:14px; bottom:8px; font-size:13px; letter-spacing:1px;
  color:rgba(168,152,120,0.75); }
"""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{_css()}
{override}</style></head>
<body><div class="wrap"><div class="unit">
  <div class="head">{icon_html}
    <div class="title"><div class="name">{u['name']}</div>
      <div class="sub">{u['civ']} &middot; {u.get('unit_type','')}</div>
      <div class="cost">{cost_line}</div></div></div>
  {duel_html}
  <div class="stats">{stat_html}</div>
  <div class="row-label">Bonus vs opponent</div><div class="chips">{chips}</div>
  <div class="tag">aoe2matchup.com</div>
</div></div></body></html>"""


def _autocrop(p, pad=6):
    """Crop a transparent screenshot to the card's bounds (predictable compositing)."""
    try:
        from PIL import Image
        im = Image.open(p).convert("RGBA")
        bb = im.getbbox()                     # tight box around the non-transparent card
        if bb:
            bb = (max(0, bb[0] - pad), max(0, bb[1] - pad),
                  min(im.width, bb[2] + pad), min(im.height, bb[3] + pad))
            im.crop(bb).save(p)
    except Exception:
        pass
    return p


def render_unit_panel(u, opponent, out_png, side=1, count=30,
                      width=900, height=760, scale=2) -> Path:
    """Render one unit's detail card to a transparent PNG, auto-cropped to the card
    bounds (so compositing position is predictable). See build_unit_panel_html."""
    return _autocrop(_screenshot(build_unit_panel_html(u, opponent, side, count),
                                 out_png, width, height, scale))


def _verdict(res: dict) -> str:
    """Decisiveness, from how much of the winner's army is left."""
    win = res["winner"]
    if not win:
        return "Stalemate"
    hp = res[f"s{win}"]["hp"]
    if hp >= 0.60:
        return "Decisive victory"
    if hp >= 0.30:
        return "Clear victory"
    return "Close call"


def build_results_panel_html(u1: dict, u2: dict, res: dict) -> str:
    """The END-OF-MATCHUP results card, composited over the post-battle hold (not a
    separate screen): winner banner + per-side columns with units left ("23/30") and
    the army-HP bar/% left, plus a footer with the VERDICT (decisiveness), the fight
    duration and each side's resources lost. `res` is compose._sidecar_summary's dict:
    {winner, s1:{start,left,hp}, s2:{...}, true_hp, duration_s}."""
    P = PALETTE
    win = res["winner"]
    if win == 1:
        who = f"{u1['name']} wins"
    elif win == 2:
        who = f"{u2['name']} wins"
    else:
        who = "Draw"
    hp_lbl = "HP left" if res.get("true_hp") else "army left"
    w = res.get(f"s{win}") if win else None
    sub = (f"{w['left']} of {w['start']} still standing &middot; "
           f"{w['hp']:.0%} {hp_lbl}" if w else "both armies spent")

    # footer: verdict · fight duration · resources lost per side
    dur = res.get("duration_s")
    dur_s = (f"{int(dur // 60)}m {int(dur % 60):02d}s" if dur and dur >= 60
             else (f"{dur:.0f}s" if dur else "&mdash;"))
    lost1 = int((res["s1"]["start"] - res["s1"]["left"]) * (u1["cost"]["total"] or 0))
    lost2 = int((res["s2"]["start"] - res["s2"]["left"]) * (u2["cost"]["total"] or 0))
    foot = f"""
  <div class="foot">
    <div class="f"><span class="fk">Verdict</span><span class="fv">{_verdict(res)}</span></div>
    <div class="f"><span class="fk">Fight</span><span class="fv">{dur_s}</span></div>
    <div class="f"><span class="fk">Res lost</span>
      <span class="fv">{_RES_SVG['gold']} {lost1:,} &nbsp;vs&nbsp; {lost2:,}</span></div>
  </div>
  <div class="brandline">aoe2matchup.com</div>"""

    def col(u, side):
        s = res[f"s{side}"]
        cls = "scol win" if win == side else ("scol lose" if win else "scol")
        icon = _img_data_uri(u.get("icon", ""))
        img = f'<img src="{icon}">' if icon else ""
        crown = '<div class="crown">&#9819;</div>' if win == side else ""
        hp_pct = max(0, min(100, round(s["hp"] * 100)))
        return f"""<div class="{cls}">{crown}{img}
          <div class="nm">{u['name']}</div>
          <div class="civ">{u['civ']}</div>
          <div class="big">{s['left']}<span class="of">/{s['start']}</span></div>
          <div class="lbl">units left</div>
          <div class="hpbar"><i style="width:{hp_pct}%"></i></div>
          <div class="lbl hp">{hp_pct}% {hp_lbl}</div></div>"""

    override = f"""
.wrap {{ padding:0; }}
.panel {{ width:1080px; margin:0 auto; padding:22px 26px 26px; border-radius:16px;
  background:linear-gradient(165deg, rgba(42,31,20,0.90), rgba(18,13,7,0.92));
  border:2px solid rgba(201,168,76,0.7);
  box-shadow:0 8px 30px rgba(0,0,0,0.6), inset 0 0 0 1px rgba(201,168,76,0.12); }}
.result-banner {{ margin-bottom:16px; }}
.result-banner .who {{ font-size:52px; }}
.result-banner .sub {{ font-size:20px; }}
.score {{ gap:30px; }}
.scol {{ width:430px; position:relative; padding:20px;
  background:linear-gradient(160deg, rgba(42,31,20,0.6), rgba(18,13,7,0.6)); }}
.scol img {{ width:104px; height:104px; }}
.scol .nm {{ font-size:27px; }}
.scol .civ {{ font-size:17px; color:{P['text_muted']}; }}
.scol .big {{ font-size:72px; margin:8px 0 0; }}
.scol .big .of {{ font-size:30px; color:{P['text_muted']}; font-weight:normal; }}
.scol .lbl {{ font-size:16px; }}
.scol .lbl.hp {{ margin-top:6px; font-size:18px; color:{P['text']}; }}
.hpbar {{ height:16px; margin-top:14px; }}
.scol.win .hpbar > i {{ background:{P['green']}; }}
.scol.lose .hpbar > i {{ background:{P['red']}; }}
.crown {{ position:absolute; top:8px; right:14px; font-size:34px; color:{P['gold']};
  text-shadow:0 2px 8px #000; }}
.vs {{ font-size:42px; }}
.foot {{ display:flex; justify-content:center; gap:46px; margin-top:18px; padding-top:14px;
  border-top:1px solid rgba(201,168,76,0.3); }}
.f {{ display:flex; align-items:baseline; gap:10px; }}
.fk {{ font-size:14px; color:{P['gold']}; text-transform:uppercase; letter-spacing:1px; }}
.fv {{ font-size:22px; color:{P['text']}; font-weight:bold;
  display:inline-flex; align-items:center; gap:6px; }}
.ri {{ width:22px; height:22px; vertical-align:middle; }}
.brandline {{ text-align:center; margin-top:10px; font-size:14px; letter-spacing:2px;
  color:rgba(168,152,120,0.8); }}
"""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{_css()}
{override}</style></head>
<body><div class="wrap"><div class="panel">
  <div class="result-banner"><div class="who">{who}</div><div class="sub">{sub}</div></div>
  <div class="score">{col(u1, 1)}<div class="vs">VS</div>{col(u2, 2)}</div>
  {foot}
</div></div></body></html>"""


def render_results_panel(u1, u2, res, out_png, width=1280, height=720, scale=2) -> Path:
    """Render the end-of-matchup results card to a transparent, auto-cropped PNG for
    compositing over the post-battle hold."""
    return _autocrop(_screenshot(build_results_panel_html(u1, u2, res),
                                 out_png, width, height, scale))


def build_premise_html(u1: dict, u2: dict, counts=(30, 30)) -> str:
    """The PREMISE strip shown under the top bar for the opening seconds: states WHY
    the army sizes are what they are. Equal-resource fights say so explicitly with the
    matched totals; equal-count fights say that; anything else just states the sizes.
    Each side's exact food/wood/gold spend is shown with resource icons."""
    n1, n2 = counts
    t1 = int(n1 * (u1["cost"]["total"] or 0))
    t2 = int(n2 * (u2["cost"]["total"] or 0))
    if max(t1, t2) and abs(t1 - t2) <= 0.07 * max(t1, t2):
        title = "EQUAL RESOURCES"
        sub = f"&asymp; {round((t1 + t2) / 2):,} res each side"
    elif n1 == n2:
        title = "EQUAL NUMBERS"
        sub = f"{n1} vs {n2} &middot; {t1:,} vs {t2:,} res"
    else:
        title = f"{n1} vs {n2} UNITS"
        sub = f"{t1:,} vs {t2:,} res"
    mix1 = _res_iconic(u1["cost"], mult=n1)
    mix2 = _res_iconic(u2["cost"], mult=n2)
    css = """
.wrap { padding:0; }
.premise { width:980px; margin:0 auto; padding:12px 26px 13px; border-radius:14px;
  background:linear-gradient(165deg, rgba(42,31,20,0.88), rgba(18,13,7,0.90));
  border:2px solid rgba(201,168,76,0.65); text-align:center;
  box-shadow:0 6px 24px rgba(0,0,0,0.55); }
.premise .t { font-size:34px; letter-spacing:3px; color:#c9a84c; text-transform:uppercase;
  text-shadow:0 2px 8px #000; }
.premise .t .s { color:#a89878; font-size:21px; letter-spacing:1px; margin-left:14px;
  text-transform:none; }
.mixes { display:flex; justify-content:space-between; align-items:center; margin-top:8px;
  font-size:21px; }
.mixes .side { display:flex; align-items:center; gap:10px; }
.mixes .who { color:#a89878; font-size:17px; }
.resi { display:inline-flex; align-items:center; gap:4px; font-weight:bold; }
.ri { width:22px; height:22px; vertical-align:middle; }
"""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{_css()}
{css}</style></head>
<body><div class="wrap"><div class="premise">
  <div class="t">{title}<span class="s">{sub}</span></div>
  <div class="mixes">
    <div class="side"><span class="who">{n1}&times; {u1['name']}</span>{mix1}</div>
    <div class="side">{mix2}<span class="who">{n2}&times; {u2['name']}</span></div>
  </div>
</div></div></body></html>"""


def render_premise(u1, u2, counts, out_png, width=1100, height=260, scale=2) -> Path:
    """Render the premise strip to a transparent, auto-cropped PNG."""
    return _autocrop(_screenshot(build_premise_html(u1, u2, counts),
                                 out_png, width, height, scale))


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


def render_intro(u1, u2, out_png, width=1340, height=760, scale=2, title=None,
                 counts=(30, 30)) -> Path:
    return _screenshot(build_intro_html(u1, u2, title, counts), out_png, width, height, scale)


def render_outro(result, u1, u2, out_png, width=1000, height=520, scale=2) -> Path:
    return _screenshot(build_outro_html(result, u1, u2), out_png, width, height, scale)


# back-compat
def render_card(u1, u2, out_png, mode="full", width=1340, height=760, scale=2,
                title=None, browser=None) -> Path:
    return render_intro(u1, u2, out_png, width, height, scale, title)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # scenario_builder/
    from overlay.overlay_data import get_unit_card
    from overlay.results import extract_sim_results
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

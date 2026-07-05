"""ddkImmortalCoreS = CoreG + SIEGE control (backlog item 4).

Adds the siege classes to every find (clustering Rule 6, state-machine Rule 12, W_fire
detect): class 913 (mangonel line, DUC 13+900) + class 955 (scorpions, 55+900). W_fire
rows from the repo DB: mangonel/onager/siege onager delay 0ms -> 60; scorpion 200 -> 260;
heavy scorpion 100 -> 160. Everything else the CoreG pipeline already provides: reload
6s -> dwell caps at 2200 (long repositioning arcs), speed 0.6 -> slow tier short steps,
volley engine round-robins targets, kite machine backs the mangonels away from chargers.

The three find-blocks and the appendix W_fire table are edited by exact anchors; the new
table rows are INSERTED before the gWset closer (appendix has no jump targets, so
insertion is numbering-safe). Validate with the set-based mode.
"""
import io

SRC = r"apps\video\ai_experiments\ddkImmortalCoreG.per"
DST = r"apps\video\ai_experiments\ddkImmortalCoreS.per"
text = io.open(SRC, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in text else "\n"

def rep(old, new, n=1):
    global text
    assert text.count(old) == n, f"anchor x{text.count(old)} (want {n}): {old[:60]!r}"
    text = text.replace(old, new)

rep("; CoreG = CoreF + per-unit kiting character; ALL VALUES FROM the repo DB",
    "; CoreS = CoreG + SIEGE (mangonel line class 913 + scorpions 955 join the ball;\n"
    ";   W_fire rows from the DB: mangonel/onager/SO 60, scorpion 260, heavy scorpion 160).\n"
    "; CoreG = CoreF + per-unit kiting character; ALL VALUES FROM the repo DB")

rep("(defconst class-hand-cannoneer 944)",
    "(defconst class-hand-cannoneer 944)\n"
    "(defconst class-siege-weapon 913)\n"
    "(defconst class-ballista 955)")

# add the two siege finds to Rule 6, Rule 12, and the W_fire detect rule (3 blocks)
rep("\t(up-find-local c: class-conquistador c: 240)",
    "\t(up-find-local c: class-conquistador c: 240)\n"
    "\t(up-find-local c: class-siege-weapon c: 240)\n"
    "\t(up-find-local c: class-ballista c: 240)", n=3)

rep("\t(chat-to-player 1 \"ImmortalCoreG up\")",
    "\t(chat-to-player 1 \"ImmortalCoreS up\")")

# class fallbacks: insert after the conquistador class-default rule
rep("\t(up-compare-goal gUClass c:== class-conquistador)\n"
    "\t=>\n"
    "\t(up-modify-goal gWfire c:= 277)\n"
    ")",
    "\t(up-compare-goal gUClass c:== class-conquistador)\n"
    "\t=>\n"
    "\t(up-modify-goal gWfire c:= 277)\n"
    ")\n"
    "(defrule\n"
    "\t(up-compare-goal gWset c:== 1)\n"
    "\t(up-compare-goal gUClass c:== class-siege-weapon)\n"
    "\t=>\n"
    "\t(up-modify-goal gWfire c:= 60)\n"
    ")\n"
    "(defrule\n"
    "\t(up-compare-goal gWset c:== 1)\n"
    "\t(up-compare-goal gUClass c:== class-ballista)\n"
    "\t=>\n"
    "\t(up-modify-goal gWfire c:= 260)\n"
    ")")

# type rows: insert before the gWset closer
CLOSER = ("(defrule\n"
          "\t(up-compare-goal gWset c:== 1)\n"
          "\t=>\n"
          "\t(up-modify-goal gWset c:= 2)")
ROWS = (";--- 60: Mangonel 280 / Onager 550 / Siege Onager 588 (delay 0) ---\n"
        "(defrule\n"
        "\t(up-compare-goal gWset c:== 1)\n"
        "\t(or (or (up-compare-goal gUType c:== 280)\n"
        "\t\t(up-compare-goal gUType c:== 550))\n"
        "\t\t(up-compare-goal gUType c:== 588))\n"
        "\t=>\n"
        "\t(up-modify-goal gWfire c:= 60)\n"
        ")\n"
        ";--- 260/160: Scorpion 279 (delay 200) / Heavy Scorpion 542 (delay 100) ---\n"
        "(defrule\n"
        "\t(up-compare-goal gWset c:== 1)\n"
        "\t(up-compare-goal gUType c:== 279)\n"
        "\t=>\n"
        "\t(up-modify-goal gWfire c:= 260)\n"
        ")\n"
        "(defrule\n"
        "\t(up-compare-goal gWset c:== 1)\n"
        "\t(up-compare-goal gUType c:== 542)\n"
        "\t=>\n"
        "\t(up-modify-goal gWfire c:= 160)\n"
        ")\n")
rep(CLOSER, ROWS + CLOSER)

if NL == "\r\n":
    # the inserted blocks above use \n; normalize any bare \n to \r\n
    text = text.replace("\r\n", "\n").replace("\n", "\r\n")
io.open(DST, "w", encoding="utf-8", newline="").write(text)
print(f"wrote {DST}: {text.count('(defrule')} defrules")

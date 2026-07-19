"""Generate ddkSquareV6.per = ddkSquareV5 but with NO SNAPPING.

WHY: the re-snap (project the drifted centroid onto the NEAREST edge, jump the arc
there) sent the target to a DIFFERENT edge whenever the enemy shoved the ball off the
loop -- and the straight-line path to that far target ran through the enemy in the
centre, getting the units slaughtered.  (Seen 3x in try1.)

FIX -- never snap, just march:
  * REMOVE the whole projection / re-snap.  The arc gS only ever advances by STEP,
    so the target only ever moves to the ADJACENT loop point (1.5 tiles along the
    same/next edge) -- it can NEVER jump across the square.
  * ARRIVAL GATE: advance gS only while KITE-moving AND the ball is within ARRIVE of
    the current target.  If the enemy pushes the ball behind, the target WAITS (holds
    on the loop, pulling the ball back) instead of running ahead around the loop
    (which would also create a cross-the-centre path).  This is not a snap -- gS never
    re-projects, only steps forward or waits.
  * FIRST move = corner (500,500) at gS=0, which is the point FARTHEST from centre, so
    the opening move heads away from the enemy, not into it.
  * The ball naturally rides a ~500-550 band (pushed in by melee, pulled back to the
    500 loop line) -- exactly the "doesn't have to be perfect" tolerance requested.

Geometry identical (INSET=5 -> loop [500,1100], 6-tile sides, arc 0..2400, CCW).
Chat: only the packed target "xy=%d" on change (x*10000+y); frequent base chats stripped.
Validation: validate_variant.py ddkModelAI.per ddkSquareV6.per 44,45,46,56,57,65 7
"""
import io

MAP_TILES = 16
INSET     = 5
STEP      = 150    # arc units per march step (1.5 tiles), + = counter-clockwise
ARRIVE    = 350    # advance only when the ball is within this (precise) of the target

LO   = INSET * 100
HI   = (MAP_TILES - INSET) * 100
SIDE = HI - LO
PERIM = 4 * SIDE

SRC = r"apps\video\ai_experiments\ddkModelAI.per"
DST = r"apps\video\ai_experiments\ddkSquareV6.per"

text = io.open(SRC, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in text else "\n"


def rep(old, new, n=1):
    global text
    old = old.replace("\n", NL)
    new = new.replace("\n", NL)
    c = text.count(old)
    assert c == n, f"anchor matched {c}x (want {n}): {old[:70]!r}"
    text = text.replace(old, new)


def sxy(inp, ox, oy):
    return f"""(defrule
\t(up-compare-goal {inp} c:< {SIDE})
\t=>
\t(up-modify-goal {ox} c:= {LO})
\t(up-modify-goal {ox} g:+ {inp})
\t(up-modify-goal {oy} c:= {LO})
)
(defrule
\t(up-compare-goal {inp} c:>= {SIDE})
\t(up-compare-goal {inp} c:< {2 * SIDE})
\t=>
\t(up-modify-goal {ox} c:= {HI})
\t(up-modify-goal gTmpA g:= {inp})
\t(up-modify-goal gTmpA c:- {SIDE})
\t(up-modify-goal {oy} c:= {LO})
\t(up-modify-goal {oy} g:+ gTmpA)
)
(defrule
\t(up-compare-goal {inp} c:>= {2 * SIDE})
\t(up-compare-goal {inp} c:< {3 * SIDE})
\t=>
\t(up-modify-goal {oy} c:= {HI})
\t(up-modify-goal gTmpA g:= {inp})
\t(up-modify-goal gTmpA c:- {2 * SIDE})
\t(up-modify-goal {ox} c:= {HI})
\t(up-modify-goal {ox} g:- gTmpA)
)
(defrule
\t(up-compare-goal {inp} c:>= {3 * SIDE})
\t=>
\t(up-modify-goal {ox} c:= {LO})
\t(up-modify-goal gTmpA g:= {inp})
\t(up-modify-goal gTmpA c:- {3 * SIDE})
\t(up-modify-goal {oy} c:= {HI})
\t(up-modify-goal {oy} g:- gTmpA)
)"""


# ---------- header note ----------
rep("; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +",
    f"; ddkSquareV6 = ddkSquareV5 ({INSET} tiles from edge, CCW loop [{LO},{HI}]) but with\n"
    ";   NO SNAPPING.  The killer re-snap (jump the target to the nearest edge when the\n"
    ";   ball drifts) sent units straight through the centre enemy.  Now the arc only\n"
    ";   ever advances by one step (adjacent loop point) and WAITS if the ball falls\n"
    ";   behind (arrival gate) -- so the target can never jump across the square.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

# ---------- new goals (202-208) ----------
rep("(defconst gDiagE 200)",
    "(defconst gDiagE 200)\n"
    "(defconst vecSquare 202)\n(defconst vecSquare_x 202)\n(defconst vecSquare_y 203)\n"
    "(defconst gS 204)\n(defconst gDistToTgt 205)\n"
    "(defconst gLastX 206)\n(defconst gLastY 207)\n(defconst gPacked 208)")

# ---------- strip the FREQUENT base chats ----------
rep('\n\t(chat-to-player 1 "KITE")', "", n=1)
rep('\n\t(chat-to-player 1 "KITE2")', "", n=1)
rep('\n\t(chat-to-player 1 "VOLLEY")', "", n=1)
rep('\n\t(chat-to-player 1 "MOVE-P")', "", n=1)
rep('\n\t(chat-to-player 1 "MOVE-M")', "", n=1)
rep('\n\t(chat-to-player 1 "no targets in range")', "", n=1)

# ---------- Rules 56/57: kite order targets the SQUARE waypoint ----------
rep("(up-target-point vecKite action-patrol formation-line stance-no-attack)",
    "(up-target-point vecSquare action-patrol formation-line stance-no-attack)", n=2)
rep("(up-target-point vecKite action-move formation-line stance-no-attack)",
    "(up-target-point vecSquare action-move formation-line stance-no-attack)", n=2)

# ---------- APPENDIX (7 rules) ----------
ap = []
ap.append(f""";=== ddkSquareV6 CCW SQUARE-TRACK APPENDIX ({INSET} from edge; loop [{LO},{HI}],
;    arc 0..{PERIM}).  NO SNAP: gS only steps forward or waits.  goals 202-208. ===

;--- vecSquare := loop(gS)  (the move target; gS defaults to 0 = corner ({LO},{LO})) ---""")
ap.append(sxy("gS", "vecSquare_x", "vecSquare_y"))
ap.append(f""";--- how far is the ball from the current target ---
(defrule
\t(true)
\t=>
\t(up-get-point-distance vecMed vecSquare gDistToTgt)
)
;--- march CCW one step, ONLY while KITE-moving AND the ball has reached the current
;    target (within {ARRIVE}).  Never re-projects -> the target only ever advances to the
;    adjacent loop point; if the ball is shoved behind it WAITS.  (reverse: {STEP} -> {PERIM - STEP}) ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gState c:== 18)
\t(up-compare-goal gDistToTgt c:< {ARRIVE})
\t=>
\t(up-modify-goal gS c:+ {STEP})
\t(up-modify-goal gS c:mod {PERIM})
)
;--- LOG: one packed message per target change.  packed = x*10000 + y ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(nand (up-compare-goal vecSquare_x g:== gLastX)
\t\t(up-compare-goal vecSquare_y g:== gLastY))
\t=>
\t(up-modify-goal gLastX g:= vecSquare_x)
\t(up-modify-goal gLastY g:= vecSquare_y)
\t(up-modify-goal gPacked g:= vecSquare_x)
\t(up-modify-goal gPacked c:* 10000)
\t(up-modify-goal gPacked g:+ vecSquare_y)
\t(up-chat-data-to-player 1 "xy=%d" g: gPacked)
)""")

appendix = "\n".join(ap) + "\n"
if NL == "\r\n":
    appendix = appendix.replace("\n", "\r\n")
text = text.rstrip("\r\n") + NL + appendix

io.open(DST, "w", encoding="utf-8", newline="").write(text)
n_rules = text.count("(defrule")
print(f"wrote {DST}: {len(text)} chars, {n_rules} defrules (expect 129), NL={NL!r}")

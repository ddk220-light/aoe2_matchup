"""Generate ddkSquareV5.per = ddkSquareV4 but the debug chat prints BOTH coords in a
SINGLE message per target change, instead of separate x= / y= lines.

up-chat-data-to-player prints only ONE value per call (verified across every AI in the
game folder -- no two-%d form exists anywhere), so both coords are PACKED into one
integer:  packed = x*10000 + y.  Read it as: the last 4 digits are Y, everything before
is X.  Examples: (650,500)->6500500 ; (1100,500)->11000500 ; (1100,1100)->11001100 ;
(500,1100)->5001100.  Chatted as "xy=%d", only when the target changes.

Geometry/behaviour identical to V3/V4 (INSET=5 -> loop [500,1100], 6-tile sides, arc
0..2400, counter-clockwise).  Frequent base chats stay stripped.
Validation: validate_variant.py ddkModelAI.per ddkSquareV5.per 44,45,46,56,57,65 17
"""
import io

MAP_TILES = 16
INSET     = 5
STEP      = 150
SNAP      = 120
CENTRE    = (MAP_TILES * 100) // 2

LO   = INSET * 100
HI   = (MAP_TILES - INSET) * 100
SIDE = HI - LO
PERIM = 4 * SIDE

SRC = r"apps\video\ai_experiments\ddkModelAI.per"
DST = r"apps\video\ai_experiments\ddkSquareV5.per"

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
    f"; ddkSquareV5 = ddkSquareV4 ({INSET} tiles from edge, CCW loop [{LO},{HI}]) but the\n"
    ";   debug chat prints BOTH coords in ONE message per target change, packed as\n"
    ";   x*10000+y (read last 4 digits = y).  All frequent base chats stay stripped.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

# ---------- new goals (202-220) ----------
rep("(defconst gDiagE 200)",
    "(defconst gDiagE 200)\n"
    "(defconst vecSquare 202)\n(defconst vecSquare_x 202)\n(defconst vecSquare_y 203)\n"
    "(defconst gS 204)\n"
    "(defconst vecNP 205)\n(defconst vecNP_x 205)\n(defconst vecNP_y 206)\n"
    "(defconst gNPS 207)\n(defconst gOffLoop 208)\n"
    "(defconst gCx 209)\n(defconst gCy 210)\n"
    "(defconst gDL 211)\n(defconst gDR 212)\n(defconst gDB 213)\n(defconst gDT 214)\n"
    "(defconst gMin 215)\n(defconst gSqBan 216)\n"
    "(defconst gLastX 218)\n(defconst gLastY 219)\n(defconst gPacked 220)")

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

# ---------- APPENDIX (17 rules) ----------
ap = []
ap.append(f""";=== ddkSquareV5 CCW SQUARE-TRACK APPENDIX ({INSET} from edge; loop [{LO},{HI}],
;    arc 0..{PERIM}).  One packed xy message per target change.  goals 202-220. ===

;--- one-time init (no chat): vecSquare fallback centre, gS=0 ---
(defrule
\t(up-compare-goal gSqBan c:!= 1)
\t=>
\t(up-modify-goal gSqBan c:= 1)
\t(up-modify-goal vecSquare_x c:= {CENTRE})
\t(up-modify-goal vecSquare_y c:= {CENTRE})
\t(up-modify-goal gS c:= 0)
)
;--- proj1: clamp centroid into the [{LO},{HI}] box ---
(defrule
\t(true)
\t=>
\t(up-modify-goal gCx g:= vecMed_x)
\t(up-modify-goal gCx c:max {LO})
\t(up-modify-goal gCx c:min {HI})
\t(up-modify-goal gCy g:= vecMed_y)
\t(up-modify-goal gCy c:max {LO})
\t(up-modify-goal gCy c:min {HI})
)
;--- proj2: distance from the clamped point to each of the 4 edges ---
(defrule
\t(true)
\t=>
\t(up-modify-goal gDL g:= gCx)
\t(up-modify-goal gDL c:- {LO})
\t(up-modify-goal gDR c:= {HI})
\t(up-modify-goal gDR g:- gCx)
\t(up-modify-goal gDB g:= gCy)
\t(up-modify-goal gDB c:- {LO})
\t(up-modify-goal gDT c:= {HI})
\t(up-modify-goal gDT g:- gCy)
)
;--- proj3: gMin = nearest edge distance ---
(defrule
\t(true)
\t=>
\t(up-modify-goal gMin g:= gDL)
\t(up-modify-goal gMin g:min gDR)
\t(up-modify-goal gMin g:min gDB)
\t(up-modify-goal gMin g:min gDT)
)
;--- proj4: snap onto the nearest edge -> vecNP + arc gNPS (ties: last wins) ---
(defrule
\t(up-compare-goal gMin g:== gDB)
\t=>
\t(up-modify-goal vecNP_x g:= gCx)
\t(up-modify-goal vecNP_y c:= {LO})
\t(up-modify-goal gNPS g:= gCx)
\t(up-modify-goal gNPS c:- {LO})
)
(defrule
\t(up-compare-goal gMin g:== gDR)
\t=>
\t(up-modify-goal vecNP_x c:= {HI})
\t(up-modify-goal vecNP_y g:= gCy)
\t(up-modify-goal gNPS g:= gCy)
\t(up-modify-goal gNPS c:+ {SIDE - LO})
)
(defrule
\t(up-compare-goal gMin g:== gDT)
\t=>
\t(up-modify-goal vecNP_y c:= {HI})
\t(up-modify-goal vecNP_x g:= gCx)
\t(up-modify-goal gNPS c:= {2 * SIDE + HI})
\t(up-modify-goal gNPS g:- gCx)
)
(defrule
\t(up-compare-goal gMin g:== gDL)
\t=>
\t(up-modify-goal vecNP_x c:= {LO})
\t(up-modify-goal vecNP_y g:= gCy)
\t(up-modify-goal gNPS c:= {3 * SIDE + HI})
\t(up-modify-goal gNPS g:- gCy)
)
;--- proj5: gOffLoop = 1 iff the centroid is > {SNAP} from the loop ---
(defrule
\t(true)
\t=>
\t(up-modify-goal gOffLoop c:= 0)
\t(up-get-point-distance vecMed vecNP gTmpA)
)
(defrule
\t(up-compare-goal gTmpA c:> {SNAP})
\t=>
\t(up-modify-goal gOffLoop c:= 1)
)
;--- snap: engaged & off the loop -> jump the arc to the nearest loop point ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gOffLoop c:== 1)
\t=>
\t(up-modify-goal gS g:= gNPS)
)
;--- march: engaged, ON the loop, MOVING (KITE state 18) -> step CCW ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gOffLoop c:== 0)
\t(up-compare-goal gState c:== 18)
\t=>
\t(up-modify-goal gS c:+ {STEP})
\t(up-modify-goal gS c:mod {PERIM})
)""")

ap.append(";--- vecSquare := loop(gS) ---")
ap.append(sxy("gS", "vecSquare_x", "vecSquare_y"))

ap.append(""";--- LOG: one packed message per target change.  packed = x*10000 + y
;    (read the last 4 digits as y, the rest as x) ---
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
print(f"wrote {DST}: {len(text)} chars, {n_rules} defrules (expect 139), NL={NL!r}")

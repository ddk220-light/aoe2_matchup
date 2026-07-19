"""Generate ddkSquareV3.per = ddkModelAI + FIXED CCW SQUARE TRACK (bigger loop).

Same as ddkSquareV2 but the loop is INSET tiles from the edge (now 5, was 6) and the
geometry is PARAMETERIZED off INSET/MAP_TILES so resizing is a one-line change and the
arc/projection constants are derived (no hand-computed numbers).

INSET=5 on a 16x16 map -> loop = perimeter of x,y in [500,1100] (tiles 5..11), 6-tile
sides, centre (800,800), arc s in [0,2400).  Counter-clockwise (s increasing); reverse
by changing the march step c:+ STEP -> c:+ (PERIM-STEP).  Immortal VOLLEY kept.

GRAFT: rules 0-77 untouched except Rule 56/57 (kite target vecKite -> vecSquare).
Validation: validate_variant.py ddkModelAI.per ddkSquareV3.per 56,57 17
"""
import io

# ---- geometry knobs (change INSET to resize the loop) ----
MAP_TILES = 16
INSET     = 5
STEP      = 150   # arc units per march step (1.5 tiles); direction = +STEP (CCW)
SNAP      = 120   # >this from the loop (precise) => re-snap onto it
CENTRE    = (MAP_TILES * 100) // 2   # 800 fallback

LO   = INSET * 100                    # 500
HI   = (MAP_TILES - INSET) * 100      # 1100
SIDE = HI - LO                        # 600
PERIM = 4 * SIDE                      # 2400

SRC = r"apps\video\ai_experiments\ddkModelAI.per"
DST = r"apps\video\ai_experiments\ddkSquareV3.per"

text = io.open(SRC, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in text else "\n"


def rep(old, new, n=1):
    global text
    old = old.replace("\n", NL)
    new = new.replace("\n", NL)
    c = text.count(old)
    assert c == n, f"anchor matched {c}x (want {n}): {old[:70]!r}"
    text = text.replace(old, new)


def addk(goal, k):
    """emit a signed constant add on `goal`."""
    return f"(up-modify-goal {goal} c:+ {k})" if k >= 0 else f"(up-modify-goal {goal} c:- {-k})"


def sxy(inp, ox, oy):
    """4 rules: point (ox,oy) := loop point at arc `inp` (0..PERIM-1). gTmpA scratch."""
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
    f"; ddkSquareV3 = ddkModelAI + FIXED COUNTER-CLOCKWISE SQUARE TRACK ({INSET} tiles from\n"
    f";   the edge -> loop = perimeter of x,y in [{LO},{HI}], {SIDE // 100}-tile sides, arc\n"
    f";   s in [0,{PERIM}).  Circles the SAME way (CCW, s increasing), IGNORING the enemy;\n"
    ";   Immortal VOLLEY kept -> circle, stop to attack, circle.  Reverse direction by\n"
    f";   changing the march step c:+ {STEP} -> c:+ {PERIM - STEP}.  Pure graft: rules 0-77\n"
    ";   untouched except the kite target (56/57) -> vecSquare.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

# ---------- new goals (202-217) ----------
rep("(defconst gDiagE 200)",
    "(defconst gDiagE 200)\n"
    "(defconst vecSquare 202)\n(defconst vecSquare_x 202)\n(defconst vecSquare_y 203)\n"
    "(defconst gS 204)\n"
    "(defconst vecNP 205)\n(defconst vecNP_x 205)\n(defconst vecNP_y 206)\n"
    "(defconst gNPS 207)\n(defconst gOffLoop 208)\n"
    "(defconst gCx 209)\n(defconst gCy 210)\n"
    "(defconst gDL 211)\n(defconst gDR 212)\n(defconst gDB 213)\n(defconst gDT 214)\n"
    "(defconst gMin 215)\n(defconst gHbT 216)\n(defconst gSqBan 217)")

# ---------- Rules 56/57: kite order targets the SQUARE waypoint ----------
rep("(up-target-point vecKite action-patrol formation-line stance-no-attack)",
    "(up-target-point vecSquare action-patrol formation-line stance-no-attack)", n=2)
rep("(up-target-point vecKite action-move formation-line stance-no-attack)",
    "(up-target-point vecSquare action-move formation-line stance-no-attack)", n=2)

# ---------- APPENDIX (17 rules) ----------
ap = []
ap.append(f""";=== ddkSquareV3 CCW SQUARE-TRACK APPENDIX ({INSET} tiles from edge; loop [{LO},{HI}],
;    arc 0..{PERIM}).  Fixed direction, enemy-independent.  goals 202-217. ===

;--- banner + one-time init (vecSquare fallback centre, gS=0) ---
(defrule
\t(up-compare-goal gSqBan c:!= 1)
\t=>
\t(up-modify-goal gSqBan c:= 1)
\t(up-modify-goal vecSquare_x c:= {CENTRE})
\t(up-modify-goal vecSquare_y c:= {CENTRE})
\t(up-modify-goal gS c:= 0)
\t(chat-to-player 1 "ddkSquareV3 CCW up")
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
;--- proj4: snap onto the nearest edge -> vecNP + its arc gNPS (ties: last wins) ---
(defrule
\t(up-compare-goal gMin g:== gDB)
\t=>
\t(up-modify-goal vecNP_x g:= gCx)
\t(up-modify-goal vecNP_y c:= {LO})
\t(up-modify-goal gNPS g:= gCx)
\t{addk("gNPS", -LO)}
)
(defrule
\t(up-compare-goal gMin g:== gDR)
\t=>
\t(up-modify-goal vecNP_x c:= {HI})
\t(up-modify-goal vecNP_y g:= gCy)
\t(up-modify-goal gNPS g:= gCy)
\t{addk("gNPS", SIDE - LO)}
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
;--- march: engaged, ON the loop, and MOVING (KITE state 18) -> step CCW.
;    (reverse to clockwise by changing {STEP} -> {PERIM - STEP}) ---
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

ap.append(";--- vecSquare := loop(gS)  (the move target on the track) ---")
ap.append(sxy("gS", "vecSquare_x", "vecSquare_y"))

ap.append(""";--- heartbeat log (every 2s while engaged): arc, offloop, target x/y ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-modify-goal gTmpA g:= gTimeMilli)
\t(up-modify-goal gTmpA g:- gHbT)
\t(up-compare-goal gTmpA c:>= 2000)
\t=>
\t(up-modify-goal gHbT g:= gTimeMilli)
\t(up-chat-data-to-player 1 "SQ s=%d" g: gS)
\t(up-chat-data-to-player 1 "SQ off=%d" g: gOffLoop)
\t(up-chat-data-to-player 1 "SQ tx=%d" g: vecSquare_x)
\t(up-chat-data-to-player 1 "SQ ty=%d" g: vecSquare_y)
)""")

appendix = "\n".join(ap) + "\n"
if NL == "\r\n":
    appendix = appendix.replace("\n", "\r\n")
text = text.rstrip("\r\n") + NL + appendix

io.open(DST, "w", encoding="utf-8", newline="").write(text)
n_rules = text.count("(defrule")
print(f"wrote {DST}: {len(text)} chars, {n_rules} defrules (expect 139), "
      f"loop=[{LO},{HI}] side={SIDE} perim={PERIM}, NL={NL!r}")

"""Generate ddkSquareV2.per = ddkModelAI + FIXED COUNTER-CLOCKWISE SQUARE TRACK.

Simplification of ddkSquareV1 per user: circle the fixed loop in ONE direction
(counter-clockwise), IGNORING where the enemy is.  Keep stopping to attack (the
Immortal VOLLEY is untouched) and then moving.  No enemy-distance math at all.

GEOMETRY (16x16 map -> precise 0..1600; loop inset 6 tiles = perimeter of x,y in
[600,1000]).  Arc s in [0,1600), s INCREASING walks the loop in this order:
    s [   0, 400): bottom (600+s, 600)          [x: 600 -> 1000]
    s [ 400, 800): right  (1000, 600+(s-400))   [y: 600 -> 1000]
    s [ 800,1200): top    (1000-(s-800), 1000)  [x: 1000 -> 600]
    s [1200,1600): left   (600, 1000-(s-1200))  [y: 1000 -> 600]
Increasing s = one rotational direction (intended counter-clockwise on screen).
*** To REVERSE (clockwise), change the march step from `c:+ 150` to `c:+ 1450`. ***

BEHAVIOR each pass (appendix; vecSquare applies next pass):
  * Project the group centroid onto the loop -> nearest loop point / arc gNPS + gOffLoop.
  * If OFF the loop (> kSNAP away): gS := gNPS  (first move / re-snap to the track).
  * Else, and only while in the KITE state (moving, not volleying): gS := (gS+STEP) mod 1600.
  * vecSquare := loop(gS).  The KITE order (rules 56/57) moves the ball there.
  The KITE<->VOLLEY cycle is unchanged, so the ball circles a bit, stops to volley,
  circles a bit -- always the same way around, regardless of the enemy.

GRAFT: rules 0-77 untouched except Rule 56/57 (kite target vecKite -> vecSquare).
goals 202-217, 0-default-safe (init folded into the run-once banner rule).
Validation: validate_variant.py ddkModelAI.per ddkSquareV2.per 56,57 17
SRC = ddkModelAI.per.  Fresh name (parse cache per file).
"""
import io

SRC = r"apps\video\ai_experiments\ddkModelAI.per"
DST = r"apps\video\ai_experiments\ddkSquareV2.per"

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
    """4 rules: point (ox,oy) := loop point at arc `inp` (0..1599). gTmpA scratch."""
    return f"""(defrule
\t(up-compare-goal {inp} c:< 400)
\t=>
\t(up-modify-goal {ox} c:= 600)
\t(up-modify-goal {ox} g:+ {inp})
\t(up-modify-goal {oy} c:= 600)
)
(defrule
\t(up-compare-goal {inp} c:>= 400)
\t(up-compare-goal {inp} c:< 800)
\t=>
\t(up-modify-goal {ox} c:= 1000)
\t(up-modify-goal gTmpA g:= {inp})
\t(up-modify-goal gTmpA c:- 400)
\t(up-modify-goal {oy} c:= 600)
\t(up-modify-goal {oy} g:+ gTmpA)
)
(defrule
\t(up-compare-goal {inp} c:>= 800)
\t(up-compare-goal {inp} c:< 1200)
\t=>
\t(up-modify-goal {oy} c:= 1000)
\t(up-modify-goal gTmpA g:= {inp})
\t(up-modify-goal gTmpA c:- 800)
\t(up-modify-goal {ox} c:= 1000)
\t(up-modify-goal {ox} g:- gTmpA)
)
(defrule
\t(up-compare-goal {inp} c:>= 1200)
\t=>
\t(up-modify-goal {ox} c:= 600)
\t(up-modify-goal gTmpA g:= {inp})
\t(up-modify-goal gTmpA c:- 1200)
\t(up-modify-goal {oy} c:= 1000)
\t(up-modify-goal {oy} g:- gTmpA)
)"""


# ---------- header note ----------
rep("; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +",
    "; ddkSquareV2 = ddkModelAI + FIXED COUNTER-CLOCKWISE SQUARE TRACK.  The ranged ball\n"
    ";   circles a fixed square loop inset 6 tiles from the edge of the 16x16 map, always\n"
    ";   the SAME way around (counter-clockwise), IGNORING the enemy.  Immortal VOLLEY kept\n"
    ";   -> circle, stop to attack, circle.  Loop = perimeter of x,y in [600,1000]; arc s\n"
    ";   increasing.  To reverse direction change the march step c:+ 150 -> c:+ 1450.\n"
    ";   Pure graft: rules 0-77 untouched except the kite target (56/57) -> vecSquare.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

# ---------- new goals (202-217; all above ddkModelAI's max of 200) ----------
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
ap.append(""";=== ddkSquareV2 CCW SQUARE-TRACK APPENDIX (rules 78+; vecSquare applies NEXT pass).
;    Fixed direction, enemy-independent.  See tools/make_ddksquarev2.py. goals 202-217. ===

;--- banner + one-time init (vecSquare fallback centre, gS=0) ---
(defrule
\t(up-compare-goal gSqBan c:!= 1)
\t=>
\t(up-modify-goal gSqBan c:= 1)
\t(up-modify-goal vecSquare_x c:= 800)
\t(up-modify-goal vecSquare_y c:= 800)
\t(up-modify-goal gS c:= 0)
\t(chat-to-player 1 "ddkSquareV2 CCW up")
)
;--- PROJECT the group centroid onto the loop -> vecNP, gNPS, gOffLoop ---
;--- proj1: clamp centroid into the [600,1000] box ---
(defrule
\t(true)
\t=>
\t(up-modify-goal gCx g:= vecMed_x)
\t(up-modify-goal gCx c:max 600)
\t(up-modify-goal gCx c:min 1000)
\t(up-modify-goal gCy g:= vecMed_y)
\t(up-modify-goal gCy c:max 600)
\t(up-modify-goal gCy c:min 1000)
)
;--- proj2: distance from the clamped point to each of the 4 edges ---
(defrule
\t(true)
\t=>
\t(up-modify-goal gDL g:= gCx)
\t(up-modify-goal gDL c:- 600)
\t(up-modify-goal gDR c:= 1000)
\t(up-modify-goal gDR g:- gCx)
\t(up-modify-goal gDB g:= gCy)
\t(up-modify-goal gDB c:- 600)
\t(up-modify-goal gDT c:= 1000)
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
\t(up-modify-goal vecNP_y c:= 600)
\t(up-modify-goal gNPS g:= gCx)
\t(up-modify-goal gNPS c:- 600)
)
(defrule
\t(up-compare-goal gMin g:== gDR)
\t=>
\t(up-modify-goal vecNP_x c:= 1000)
\t(up-modify-goal vecNP_y g:= gCy)
\t(up-modify-goal gNPS g:= gCy)
\t(up-modify-goal gNPS c:- 200)
)
(defrule
\t(up-compare-goal gMin g:== gDT)
\t=>
\t(up-modify-goal vecNP_y c:= 1000)
\t(up-modify-goal vecNP_x g:= gCx)
\t(up-modify-goal gNPS c:= 1800)
\t(up-modify-goal gNPS g:- gCx)
)
(defrule
\t(up-compare-goal gMin g:== gDL)
\t=>
\t(up-modify-goal vecNP_x c:= 600)
\t(up-modify-goal vecNP_y g:= gCy)
\t(up-modify-goal gNPS c:= 2200)
\t(up-modify-goal gNPS g:- gCy)
)
;--- proj5: gOffLoop = 1 iff the centroid is > 120 (1.2 tiles) from the loop ---
(defrule
\t(true)
\t=>
\t(up-modify-goal gOffLoop c:= 0)
\t(up-get-point-distance vecMed vecNP gTmpA)
)
(defrule
\t(up-compare-goal gTmpA c:> 120)
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
;    (reverse to clockwise by changing 150 -> 1450) ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gOffLoop c:== 0)
\t(up-compare-goal gState c:== 18)
\t=>
\t(up-modify-goal gS c:+ 150)
\t(up-modify-goal gS c:mod 1600)
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
print(f"wrote {DST}: {len(text)} chars, {n_rules} defrules (expect 139), NL={NL!r}")

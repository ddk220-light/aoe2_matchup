"""Generate ddkSquareV1.per = ddkModelAI + DETERMINISTIC SQUARE-TRACK MOVEMENT.

A different approach from the servo/feedback kiting (dropped).  The ranged ball is
constrained to a FIXED square loop inset 6 tiles from the edge of the 16x16 map, and
it circles that loop, always heading toward the loop point FARTHEST from the enemy
(staying opposite them).  The Immortal focus-fire VOLLEY is kept, so the ball circles,
stops to volley, circles -- "stop briefly to volley".  Nothing random; it cannot get
"stuck" because it only ever targets reachable points on a fixed open loop.

GEOMETRY (16x16 map -> precise 0..1600; inset 6 tiles):
  The loop is the square perimeter x,y in [600,1000] (tiles 6..10), centre (800,800).
  Parameterized by arc-length s in [0,1600), clockwise from corner (600,600):
    s [   0, 400): bottom edge  (600+s, 600)
    s [ 400, 800): right  edge  (1000, 600+(s-400))
    s [ 800,1200): top    edge  (1000-(s-800), 1000)
    s [1200,1600): left   edge  (600, 1000-(s-1200))

BEHAVIOR each pass (computed in the appendix, applied next pass):
  * Project the group centroid onto the loop -> nearest loop point vecNP (+ its arc).
  * If the centroid is OFF the loop (> kSNAP from it): target = vecNP  (first move / re-snap).
  * Else (on the loop): look one step (kSTEP) each way along s; move to whichever
    adjacent loop point is FARTHER from the enemy centroid.  If neither beats the
    current point (we're already opposite the enemy) -> HOLD (don't jitter).
  * The chosen point is written to vecSquare; the KITE state issues the move to it.

GRAFT (near-pure): rules 0-77 untouched EXCEPT:
  Rule 0  -- init vecSquare=(800,800), gS=0, banner ddkModelAI -> ddkSquareV1
  Rule 56 -- kite order target vecKite -> vecSquare (patrol variant; vs melee it never fires)
  Rule 57 -- kite order target vecKite -> vecSquare (move variant; the one that fires vs melee)
  The old servo (rules 49-55) still runs but its vecKite output is now ignored (harmless).
Everything else (tag/find/stats/enemy-scan/transitions/VOLLEY focus-fire) is ddkModelAI.

Distances use SQUARED distance via integer goal math (no sqrt needed for argmax); max
coord 1600 -> max d^2 ~5.1M, well within int range.  Logs s / offloop / target to
player 1 (visible in editor Test) via up-chat-data-to-player.

Validation: validate_variant.py ddkModelAI.per ddkSquareV1.per 0,56,57 31
SRC = ddkModelAI.per (run make_ddkmodelai.py first).  Fresh name (parse cache per file).
"""
import io

SRC = r"apps\video\ai_experiments\ddkModelAI.per"
DST = r"apps\video\ai_experiments\ddkSquareV1.per"

text = io.open(SRC, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in text else "\n"


def rep(old, new, n=1):
    global text
    old = old.replace("\n", NL)   # match the source file's line ending
    new = new.replace("\n", NL)
    c = text.count(old)
    assert c == n, f"anchor matched {c}x (want {n}): {old[:70]!r}"
    text = text.replace(old, new)


# ---------- appendix rule generators (return .per text, tabs as \t) ----------
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


def sqdist(px, py, out):
    """1 rule: out := squared distance from point (px,py) to enemy centroid vecEC."""
    return f"""(defrule
\t(true)
\t=>
\t(up-modify-goal gTmpA g:= {px})
\t(up-modify-goal gTmpA g:- vecEC_x)
\t(up-modify-goal gTmpA g:* gTmpA)
\t(up-modify-goal gTmpB g:= {py})
\t(up-modify-goal gTmpB g:- vecEC_y)
\t(up-modify-goal gTmpB g:* gTmpB)
\t(up-modify-goal {out} g:= gTmpA)
\t(up-modify-goal {out} g:+ gTmpB)
)"""


# ---------- header note ----------
rep("; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +",
    "; ddkSquareV1 = ddkModelAI + DETERMINISTIC SQUARE-TRACK MOVEMENT.  The ranged ball\n"
    ";   circles a fixed square loop inset 6 tiles from the edge of the 16x16 map, always\n"
    ";   heading toward the loop point FARTHEST from the enemy (staying opposite), one\n"
    ";   edge-step at a time.  Immortal VOLLEY kept -> circle, stop to volley, circle.\n"
    ";   Not random; can't get stuck (only targets reachable points on an open loop).\n"
    ";   Loop = perimeter of x,y in [600,1000]; arc s in [0,1600) clockwise.  Pure graft:\n"
    ";   rules 0-77 untouched except Rule 0 init and the kite target (56/57) -> vecSquare.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

# ---------- new goals (202-228; all above ddkModelAI's max of 200) ----------
rep("(defconst gDiagE 200)",
    "(defconst gDiagE 200)\n"
    "(defconst vecSquare 202)\n(defconst vecSquare_x 202)\n(defconst vecSquare_y 203)\n"
    "(defconst gS 204)\n(defconst gSA 205)\n(defconst gSB 206)\n"
    "(defconst vecCandA 207)\n(defconst vecCandA_x 207)\n(defconst vecCandA_y 208)\n"
    "(defconst vecCandB 209)\n(defconst vecCandB_x 209)\n(defconst vecCandB_y 210)\n"
    "(defconst vecCandC 211)\n(defconst vecCandC_x 211)\n(defconst vecCandC_y 212)\n"
    "(defconst gDistA 213)\n(defconst gDistB 214)\n(defconst gDistC 215)\n"
    "(defconst vecNP 216)\n(defconst vecNP_x 216)\n(defconst vecNP_y 217)\n"
    "(defconst gNPS 218)\n(defconst gOffLoop 219)\n"
    "(defconst gCx 220)\n(defconst gCy 221)\n"
    "(defconst gDL 222)\n(defconst gDR 223)\n(defconst gDB 224)\n(defconst gDT 225)\n"
    "(defconst gMin 226)\n(defconst gHbT 227)\n(defconst gSqBan 228)")

# ---------- (Rule 0 is left untouched -- it is already near the 32-element cap.
#            vecSquare/gS are initialised in the run-once banner rule below instead;
#            gS defaults to 0 anyway, and vecSquare(800,800) is only a one-pass
#            fallback before the appendix computes the real loop point.) ----------

# ---------- Rules 56/57: kite order targets the SQUARE waypoint ----------
rep("(up-target-point vecKite action-patrol formation-line stance-no-attack)",
    "(up-target-point vecSquare action-patrol formation-line stance-no-attack)", n=2)
rep("(up-target-point vecKite action-move formation-line stance-no-attack)",
    "(up-target-point vecSquare action-move formation-line stance-no-attack)", n=2)

# ---------- APPENDIX (31 rules) ----------
ap = []
ap.append(""";=== ddkSquareV1 SQUARE-TRACK APPENDIX (rules 78+; runs END of pass, vecSquare
;    applies NEXT pass).  Computes the move target on the fixed loop.  See
;    tools/make_ddksquarev1.py for the geometry + rationale.  goals 202-228. ===

;--- banner + one-time init (vecSquare fallback centre, gS=0) ---
(defrule
\t(up-compare-goal gSqBan c:!= 1)
\t=>
\t(up-modify-goal gSqBan c:= 1)
\t(up-modify-goal vecSquare_x c:= 800)
\t(up-modify-goal vecSquare_y c:= 800)
\t(up-modify-goal gS c:= 0)
\t(chat-to-player 1 "ddkSquareV1 square-track up")
)
;--- adjacent arcs: gSA = (gS + step) mod 1600 ; gSB = (gS + 1600 - step) mod 1600 ---
(defrule
\t(true)
\t=>
\t(up-modify-goal gSA g:= gS)
\t(up-modify-goal gSA c:+ 150)
\t(up-modify-goal gSA c:mod 1600)
\t(up-modify-goal gSB g:= gS)
\t(up-modify-goal gSB c:+ 1450)
\t(up-modify-goal gSB c:mod 1600)
)""")

ap.append(";--- current loop point vecCandC := loop(gS) ---")
ap.append(sxy("gS", "vecCandC_x", "vecCandC_y"))
ap.append(";--- forward candidate vecCandA := loop(gSA) ---")
ap.append(sxy("gSA", "vecCandA_x", "vecCandA_y"))
ap.append(";--- backward candidate vecCandB := loop(gSB) ---")
ap.append(sxy("gSB", "vecCandB_x", "vecCandB_y"))

ap.append(";--- squared distances of the three points to the enemy centroid ---")
ap.append(sqdist("vecCandC_x", "vecCandC_y", "gDistC"))
ap.append(sqdist("vecCandA_x", "vecCandA_y", "gDistA"))
ap.append(sqdist("vecCandB_x", "vecCandB_y", "gDistB"))

ap.append(""";--- PROJECT the group centroid onto the loop -> vecNP, gNPS, gOffLoop ---
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
)""")

ap.append(""";--- DECISION (engaged only): pick vecSquare + advance gS ---
;--- snap: off the loop -> go to the nearest loop point ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gOffLoop c:== 1)
\t=>
\t(up-modify-goal gS g:= gNPS)
\t(up-copy-point vecSquare vecNP)
)
;--- move forward: on loop, forward step is farthest from enemy ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gOffLoop c:== 0)
\t(up-compare-goal gDistA g:> gDistC)
\t(up-compare-goal gDistA g:>= gDistB)
\t=>
\t(up-modify-goal gS g:= gSA)
\t(up-copy-point vecSquare vecCandA)
)
;--- move backward: on loop, backward step is farthest from enemy ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gOffLoop c:== 0)
\t(up-compare-goal gDistB g:> gDistC)
\t(up-compare-goal gDistB g:> gDistA)
\t=>
\t(up-modify-goal gS g:= gSB)
\t(up-copy-point vecSquare vecCandB)
)
;--- hold: on loop, already opposite the enemy (neither step is better) -> stay ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gOffLoop c:== 0)
\t(up-compare-goal gDistA g:<= gDistC)
\t(up-compare-goal gDistB g:<= gDistC)
\t=>
\t(up-copy-point vecSquare vecCandC)
)
;--- heartbeat log (every 2s while engaged): arc, offloop, target x/y ---
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
print(f"wrote {DST}: {len(text)} chars, {n_rules} defrules (expect 153), NL={NL!r}")

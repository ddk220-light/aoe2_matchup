"""Generate ddkSquareV11.per = ddkSquareV7 EXACTLY, with the ONE change requested:
after returning to home corner A, alternate which far corner it visits next --
A -> B -> A -> C -> A -> B -> A -> C ...

RESET-FROM-V7 CONTRACT (nothing else changes):
  * The render is V7's `sxy` arc->point function, VERBATIM.  Same corners, same edges,
    same "the way it guides".
  * STEP=150 ("how much it changes"), ARRIVE=350 arrival gate, and the march rule are
    all IDENTICAL to V7.  Same firing (Rules 56/57 target vecSquare), same chat.
  * The ONLY additions are one `gLeg` bit (0=bottom edge to B, 1=left edge to C) and the
    home-corner handler that, instead of just reversing, flips to the OTHER edge.

WHY THIS NEEDS NO NEW GEOMETRY:  V7's sxy already maps the whole perimeter arc [0,2400):
    arc 0 = A=(500,500)   arc 600 = B=(1100,500)   arc 1800 = C=(500,1100)
  A is arc 0 AND arc 2400 (both render to (500,500)), so:
    bottom leg (gLeg 0): gS marches 0 -> 600 (A->B), reverse, 600 -> 0 (B->A).
    at A: switch to left leg -> gLeg 1, gS=2400.
    left  leg (gLeg 1): gS marches 2400 -> 1800 (A->C), reverse, 1800 -> 2400 (C->A).
    at A: switch back to bottom leg -> gLeg 0, gS=0.
  gS only ever steps +/-STEP along ONE edge; it never crosses the centre, never snaps.
  gDir's SIGN tells outbound (to far corner) from inbound (back to A), so the home
  handler only fires on arrival, never re-triggering the same pass.

Geometry identical to V7 (INSET=5 -> loop [500,1100]).  Chat: only packed "xy=%d" on change.
Validation: validate_variant.py ddkModelAI.per ddkSquareV11.per 44,45,46,56,57,65 12
"""
import io

MAP_TILES = 16
INSET     = 5
STEP      = 150
ARRIVE    = 350

LO    = INSET * 100                 # 500
HI    = (MAP_TILES - INSET) * 100   # 1100
SIDE  = HI - LO                     # 600   (one edge; B is at arc SIDE)
PERIM = 4 * SIDE                    # 2400  (home A is at arc 0 == arc PERIM)
FARC  = 3 * SIDE                    # 1800  (C is at arc 3*SIDE on the left edge)

SRC = r"apps\video\ai_experiments\ddkModelAI.per"
DST = r"apps\video\ai_experiments\ddkSquareV11.per"

text = io.open(SRC, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in text else "\n"


def rep(old, new, n=1):
    global text
    old = old.replace("\n", NL)
    new = new.replace("\n", NL)
    c = text.count(old)
    assert c == n, f"anchor matched {c}x (want {n}): {old[:70]!r}"
    text = text.replace(old, new)


# ---- V7's sxy(): arc value -> (x,y) around the perimeter.  KEPT VERBATIM. ----
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
    f"; ddkSquareV11 = ddkSquareV7 EXACTLY + alternate far corner:  A -> B -> A -> C -> A -> B ...\n"
    f";   A=({LO},{LO}) home; B=({HI},{LO}) far end of BOTTOM edge (arc {SIDE}); C=({LO},{HI}) far end of\n"
    f";   LEFT edge (arc {FARC}).  Out to B, back to A, out to C, back to A, forever.  V7's sxy render,\n"
    ";   STEP, arrival gate and march rule are UNCHANGED; the only add is a gLeg bit that flips the\n"
    ";   edge at A.  Both are edges meeting at A, so no path crosses the centre; no snapping.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

# ---------- new goals (202-210) ----------
rep("(defconst gDiagE 200)",
    "(defconst gDiagE 200)\n"
    "(defconst vecSquare 202)\n(defconst vecSquare_x 202)\n(defconst vecSquare_y 203)\n"
    "(defconst gS 204)\n(defconst gDir 205)\n(defconst gLeg 206)\n"
    "(defconst gDistToTgt 207)\n"
    "(defconst gLastX 208)\n(defconst gLastY 209)\n(defconst gPacked 210)")

# ---------- strip the FREQUENT base chats (same as V7) ----------
rep('\n\t(chat-to-player 1 "KITE")', "", n=1)
rep('\n\t(chat-to-player 1 "KITE2")', "", n=1)
rep('\n\t(chat-to-player 1 "VOLLEY")', "", n=1)
rep('\n\t(chat-to-player 1 "MOVE-P")', "", n=1)
rep('\n\t(chat-to-player 1 "MOVE-M")', "", n=1)
rep('\n\t(chat-to-player 1 "no targets in range")', "", n=1)

# ---------- Rules 56/57: kite order targets the SQUARE waypoint (same as V7) ----------
rep("(up-target-point vecKite action-patrol formation-line stance-no-attack)",
    "(up-target-point vecSquare action-patrol formation-line stance-no-attack)", n=2)
rep("(up-target-point vecKite action-move formation-line stance-no-attack)",
    "(up-target-point vecSquare action-move formation-line stance-no-attack)", n=2)

# ---------- APPENDIX (12 rules) ----------
ap = []
ap.append(f""";=== ddkSquareV11 = V7 render + A->B->A->C alternation.  goals 202-210. ===
;    gLeg 0 = bottom edge (home arc 0 .. B arc {SIDE});  gLeg 1 = left edge (home arc {PERIM} .. C arc {FARC}).
;    gDir sign: + = outbound to far corner, - = inbound to A (bottom); mirrored on the left leg.

;--- seed gDir outbound (+{STEP}) once (gDir defaults 0; never 0 again after) ---
(defrule
\t(up-compare-goal gDir c:== 0)
\t=>
\t(up-modify-goal gDir c:= {STEP})
)
;--- vecSquare := loop(gS)  (V7's sxy, VERBATIM; gS defaults 0 = home corner A) ---""")
ap.append(sxy("gS", "vecSquare_x", "vecSquare_y"))
ap.append(f""";--- distance from the ball to the current target (V7, verbatim) ---
(defrule
\t(true)
\t=>
\t(up-get-point-distance vecMed vecSquare gDistToTgt)
)
;--- march: step gS by gDir while KITE-moving AND the ball reached the target
;    (V7's march rule, VERBATIM -- same conditions, same {ARRIVE} gate, same {STEP} via gDir) ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gState c:== 18)
\t(up-compare-goal gDistToTgt c:< {ARRIVE})
\t=>
\t(up-modify-goal gS g:+ gDir)
)
;--- bottom leg, reached far corner B (gS >= {SIDE}): reverse, head back to A ---
(defrule
\t(up-compare-goal gLeg c:== 0)
\t(up-compare-goal gS c:>= {SIDE})
\t=>
\t(up-modify-goal gS c:= {SIDE})
\t(up-modify-goal gDir c:= -{STEP})
)
;--- left leg, reached far corner C (gS <= {FARC}): reverse, head back to A ---
(defrule
\t(up-compare-goal gLeg c:== 1)
\t(up-compare-goal gS c:<= {FARC})
\t=>
\t(up-modify-goal gS c:= {FARC})
\t(up-modify-goal gDir c:= {STEP})
)
;--- bottom leg, back home at A inbound (gS <= 0, gDir < 0): SWITCH to left leg toward C ---
(defrule
\t(up-compare-goal gLeg c:== 0)
\t(up-compare-goal gS c:<= 0)
\t(up-compare-goal gDir c:< 0)
\t=>
\t(up-modify-goal gLeg c:= 1)
\t(up-modify-goal gS c:= {PERIM})
\t(up-modify-goal gDir c:= -{STEP})
)
;--- left leg, back home at A inbound (gS >= {PERIM}, gDir > 0): SWITCH to bottom leg toward B ---
(defrule
\t(up-compare-goal gLeg c:== 1)
\t(up-compare-goal gS c:>= {PERIM})
\t(up-compare-goal gDir c:> 0)
\t=>
\t(up-modify-goal gLeg c:= 0)
\t(up-modify-goal gS c:= 0)
\t(up-modify-goal gDir c:= {STEP})
)
;--- LOG: one packed message per target change.  packed = x*10000 + y (V7, verbatim) ---
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
print(f"wrote {DST}: {len(text)} chars, {n_rules} defrules (expect 134), NL={NL!r}")

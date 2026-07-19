"""Generate ddkSquareV8.per = ddkSquareV7 but PIVOT-ALTERNATE between two corners.

Pattern requested:  A -> B -> A -> C -> A -> B -> A -> C ...
A is the home/pivot corner; the ball goes out to B, back to A, out to C, back to A,
alternating B and C forever.  A-B and A-C are both EDGES meeting at A, so every move
is a straight line along the perimeter -- the path never crosses the centre, and the
far (top-right) corner is never visited.

  A = (500,500)  pivot (bottom-left)
  B = (1100,500) far end of the BOTTOM edge  (leg 0)
  C = (500,1100) far end of the LEFT  edge   (leg 1)

State machine (all in the appendix):
  gLeg  0=bottom (A..B), 1=left (A..C)   gPos 0=at A .. 600=at far corner
  gDir  +STEP outbound (A->far) / -STEP inbound (far->A)
  vecSquare = leg0:(500+gPos,500)  leg1:(500,500+gPos)
  * march gPos by gDir while KITE-moving AND the ball reached the current target (ARRIVE).
  * at far corner (gPos>=600, outbound): reverse -> head back to A.
  * back at A (gPos<=0, inbound): reverse outbound AND TOGGLE leg -> next excursion is
    the other edge.  (A is (500,500) on both legs, so the pivot is seamless.)
  No snapping; the target only ever steps one along the current edge or pivots at A.

Geometry INSET=5 -> loop [500,1100].  Chat: only packed "xy=%d" on change.
Validation: validate_variant.py ddkModelAI.per ddkSquareV8.per 44,45,46,56,57,65 8
"""
import io

MAP_TILES = 16
INSET     = 5
STEP      = 150
ARRIVE    = 350

LO   = INSET * 100                 # 500  (near corner coord)
HI   = (MAP_TILES - INSET) * 100   # 1100 (far corner coord)
LEG  = HI - LO                     # 600  (leg length = one edge)

SRC = r"apps\video\ai_experiments\ddkModelAI.per"
DST = r"apps\video\ai_experiments\ddkSquareV8.per"

text = io.open(SRC, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in text else "\n"


def rep(old, new, n=1):
    global text
    old = old.replace("\n", NL)
    new = new.replace("\n", NL)
    c = text.count(old)
    assert c == n, f"anchor matched {c}x (want {n}): {old[:70]!r}"
    text = text.replace(old, new)


# ---------- header note ----------
rep("; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +",
    f"; ddkSquareV8 = pivot-alternate between two corners:  A -> B -> A -> C -> A -> B ...\n"
    f";   A=({LO},{LO}) pivot; B=({HI},{LO}) bottom edge; C=({LO},{HI}) left edge.  Out to B,\n"
    ";   back to A, out to C, back to A, forever.  Both are edges from A, so no path ever\n"
    ";   crosses the centre; the far corner is never visited.  Arrival-gated, no snapping.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

# ---------- new goals (202-211) ----------
rep("(defconst gDiagE 200)",
    "(defconst gDiagE 200)\n"
    "(defconst vecSquare 202)\n(defconst vecSquare_x 202)\n(defconst vecSquare_y 203)\n"
    "(defconst gPos 204)\n(defconst gDir 205)\n(defconst gLeg 206)\n"
    "(defconst gDistToTgt 207)\n"
    "(defconst gLastX 208)\n(defconst gLastY 209)\n(defconst gPacked 210)\n"
    "(defconst gInit 211)")

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

# ---------- APPENDIX (8 rules) ----------
ap = []
ap.append(f""";=== ddkSquareV8 PIVOT-ALTERNATE (A=({LO},{LO}) <-> B=({HI},{LO}) / C=({LO},{HI})).
;    gLeg 0=bottom 1=left; gPos 0..{LEG}; gDir +/-{STEP}.  goals 202-211. ===

;--- one-time seed: gDir outbound (+{STEP}); gLeg/gPos default to 0 (start A->B) ---
(defrule
\t(up-compare-goal gInit c:!= 1)
\t=>
\t(up-modify-goal gInit c:= 1)
\t(up-modify-goal gDir c:= {STEP})
)
;--- vecSquare := current leg point.  leg 0 (bottom): ({LO}+gPos, {LO}) ---
(defrule
\t(up-compare-goal gLeg c:== 0)
\t=>
\t(up-modify-goal vecSquare_x c:= {LO})
\t(up-modify-goal vecSquare_x g:+ gPos)
\t(up-modify-goal vecSquare_y c:= {LO})
)
;--- leg 1 (left): ({LO}, {LO}+gPos) ---
(defrule
\t(up-compare-goal gLeg c:== 1)
\t=>
\t(up-modify-goal vecSquare_x c:= {LO})
\t(up-modify-goal vecSquare_y c:= {LO})
\t(up-modify-goal vecSquare_y g:+ gPos)
)
;--- distance from the ball to the current target ---
(defrule
\t(true)
\t=>
\t(up-get-point-distance vecMed vecSquare gDistToTgt)
)
;--- march: step gPos by gDir while KITE-moving AND the ball reached the target ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gState c:== 18)
\t(up-compare-goal gDistToTgt c:< {ARRIVE})
\t=>
\t(up-modify-goal gPos g:+ gDir)
)
;--- at far corner (outbound): clamp + reverse back toward A ---
(defrule
\t(up-compare-goal gPos c:>= {LEG})
\t(up-compare-goal gDir c:> 0)
\t=>
\t(up-modify-goal gPos c:= {LEG})
\t(up-modify-goal gDir c:= -{STEP})
)
;--- back at pivot A (inbound): clamp, go outbound, TOGGLE leg (0<->1 via 1-gLeg) ---
(defrule
\t(up-compare-goal gPos c:<= 0)
\t(up-compare-goal gDir c:< 0)
\t=>
\t(up-modify-goal gPos c:= 0)
\t(up-modify-goal gDir c:= {STEP})
\t(up-modify-goal gLeg c:* -1)
\t(up-modify-goal gLeg c:+ 1)
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
print(f"wrote {DST}: {len(text)} chars, {n_rules} defrules (expect 130), NL={NL!r}")

"""Generate ddkSquareV10.per = go back to ddkSquareV7's WORKING oscillation and add
A->B->A->C alternation with the SMALLEST possible change.

V8 rewrote the whole movement into a leg state-machine (gLeg toggle, c:*-1, leg rules,
init rule) and that regressed.  V10 throws all that out and keeps V7's structure: one
signed variable gS that oscillates, one march rule, two reverse rules.  The only change
vs V7 is that gS is allowed to go NEGATIVE, which walks the LEFT edge (A->C) instead of
the bottom edge (A->B):

  gS:  0(A) -> +600(B) -> 0(A) -> -600(C) -> 0(A) -> +600(B) ...   = A->B->A->C->A->B

  render (2 cases, replaces V7's 4-case arc sxy):
    gS >= 0 : ( 500 + gS , 500 )        bottom edge, A..B
    gS <  0 : ( 500 , 500 - gS )        left  edge, A..C   (gS<0 so -gS>0 -> y climbs)

No gLeg, no toggle, no c:*-1, no snapping.  Arrival-gated + reverse-at-corner exactly
like V7.  gDir auto-seeds to +150 the first pass (gDir defaults 0).

Geometry INSET=5 -> corners A=(500,500) B=(1100,500) C=(500,1100).
Validation: validate_variant.py ddkModelAI.per ddkSquareV10.per 44,45,46,56,57,65 8
"""
import io

MAP_TILES = 16
INSET     = 5
STEP      = 150
ARRIVE    = 350

LO   = INSET * 100                 # 500
HI   = (MAP_TILES - INSET) * 100   # 1100
LEG  = HI - LO                     # 600  (edge length; gS swings in [-LEG, +LEG])

SRC = r"apps\video\ai_experiments\ddkModelAI.per"
DST = r"apps\video\ai_experiments\ddkSquareV10.per"

text = io.open(SRC, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in text else "\n"


def rep(old, new, n=1):
    global text
    old = old.replace("\n", NL)
    new = new.replace("\n", NL)
    c = text.count(old)
    assert c == n, f"anchor matched {c}x (want {n}): {old[:70]!r}"
    text = text.replace(old, new)


rep("; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +",
    f"; ddkSquareV10 = V7's oscillation + A->B->A->C via a SIGNED gS in [-{LEG},+{LEG}]:\n"
    f";   gS 0(A)->+{LEG}(B)->0->-{LEG}(C)->0 ...  render: gS>=0 -> ({LO}+gS,{LO}); gS<0 -> ({LO},{LO}-gS).\n"
    ";   No gLeg/toggle/c:*-1 (that was the V8 regression).  Arrival-gated, no snapping.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

rep("(defconst gDiagE 200)",
    "(defconst gDiagE 200)\n"
    "(defconst vecSquare 202)\n(defconst vecSquare_x 202)\n(defconst vecSquare_y 203)\n"
    "(defconst gS 204)\n(defconst gDir 205)\n(defconst gDistToTgt 206)\n"
    "(defconst gLastX 207)\n(defconst gLastY 208)\n(defconst gPacked 209)")

rep('\n\t(chat-to-player 1 "KITE")', "", n=1)
rep('\n\t(chat-to-player 1 "KITE2")', "", n=1)
rep('\n\t(chat-to-player 1 "VOLLEY")', "", n=1)
rep('\n\t(chat-to-player 1 "MOVE-P")', "", n=1)
rep('\n\t(chat-to-player 1 "MOVE-M")', "", n=1)
rep('\n\t(chat-to-player 1 "no targets in range")', "", n=1)

rep("(up-target-point vecKite action-patrol formation-line stance-no-attack)",
    "(up-target-point vecSquare action-patrol formation-line stance-no-attack)", n=2)
rep("(up-target-point vecKite action-move formation-line stance-no-attack)",
    "(up-target-point vecSquare action-move formation-line stance-no-attack)", n=2)

APPENDIX = f""";=== ddkSquareV10 = V7 oscillation, signed gS -> A->B->A->C.  goals 202-209. ===

;--- seed gDir outbound (+{STEP}) once (gDir defaults 0) ---
(defrule
\t(up-compare-goal gDir c:== 0)
\t=>
\t(up-modify-goal gDir c:= {STEP})
)
;--- render: gS >= 0 -> bottom edge ({LO}+gS, {LO})  [A..B] ---
(defrule
\t(up-compare-goal gS c:>= 0)
\t=>
\t(up-modify-goal vecSquare_x c:= {LO})
\t(up-modify-goal vecSquare_x g:+ gS)
\t(up-modify-goal vecSquare_y c:= {LO})
)
;--- render: gS < 0 -> left edge ({LO}, {LO}-gS)  [A..C] ---
(defrule
\t(up-compare-goal gS c:< 0)
\t=>
\t(up-modify-goal vecSquare_x c:= {LO})
\t(up-modify-goal vecSquare_y c:= {LO})
\t(up-modify-goal vecSquare_y g:- gS)
)
;--- distance from the ball to the current target ---
(defrule
\t(true)
\t=>
\t(up-get-point-distance vecMed vecSquare gDistToTgt)
)
;--- march: step gS by gDir while KITE-moving AND the ball reached the target ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gState c:== 18)
\t(up-compare-goal gDistToTgt c:< {ARRIVE})
\t=>
\t(up-modify-goal gS g:+ gDir)
)
;--- reverse at corner B (gS >= +{LEG}) ---
(defrule
\t(up-compare-goal gS c:>= {LEG})
\t=>
\t(up-modify-goal gS c:= {LEG})
\t(up-modify-goal gDir c:= -{STEP})
)
;--- reverse at corner C (gS <= -{LEG}) ---
(defrule
\t(up-compare-goal gS c:<= -{LEG})
\t=>
\t(up-modify-goal gS c:= -{LEG})
\t(up-modify-goal gDir c:= {STEP})
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
)"""

appendix = APPENDIX.replace("\n", NL) if NL == "\r\n" else APPENDIX
text = text.rstrip("\r\n") + NL + appendix + NL
n_rules = text.count("(defrule")
io.open(DST, "w", encoding="utf-8", newline="").write(text)
print(f"wrote {DST}: {len(text)} chars, {n_rules} defrules (expect 130), NL={NL!r}")

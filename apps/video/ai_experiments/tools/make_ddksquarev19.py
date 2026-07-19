"""Generate ddkSquareV19.per = the A->B->A->C alternation, but with the CRITICAL goals
kept at the exact numbers the WORKING versions (V7/V12/V18) use.

WHY: perfect empirical split across 6 versions --
  work (V7/V12/V18, single edge): gDistToTgt=205, gDir=209
  fail (V11/V14/V15, alternation): gDir=205, gDistToTgt=207, state goal at 206
The base provably never touches 204-216, so a base collision is ruled out -- but the
correlation is too clean to ignore, and it's confounded with "has the flip".  V19
breaks the confound: it HAS the flip (gAxis+gE, subtract toggle) but restores the
working goal layout:
  gE=204, gDistToTgt=205, gLastX=206, gLastY=207, gPacked=208, gDir=209   <- exactly V18
  gAxis=210, gFlipTmp=211                                                 <- new, high (210 proven OK by V18's probe)
  probe gDbgT=212, gProbe=213, gDbgTmp=214
Arrival-gated march (V7/V18 verbatim), P/E/D/N probe kept.

Decisive: works -> the goal numbers were it (feature done).  Still stalls (E=0) ->
the flip/gAxis logic is guilty, cleanly isolated.
Validation: validate_variant.py ddkModelAI.per ddkSquareV19.per 44,45,46,56,57,65 9
"""
import io

MAP_TILES = 16
INSET     = 5
STEP      = 150
ARRIVE    = 350
PROBE_MS  = 1000

LO   = INSET * 100
HI   = (MAP_TILES - INSET) * 100
LEG  = HI - LO

SRC = r"apps\video\ai_experiments\ddkModelAI.per"
DST = r"apps\video\ai_experiments\ddkSquareV19.per"

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
    "; ddkSquareV19 = A->B->A->C alternation with the WORKING goal layout (gDistToTgt=205, gDir=209\n"
    ";   like V7/V18; gAxis=210, gFlipTmp=211 pushed high).  Arrival-gated march, subtract toggle, probe.\n"
    ";   Test: works -> goal numbers were the bug; stalls -> flip logic is.  \n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

# ---- goal layout: 202-209 EXACTLY as V18, + gAxis/gFlipTmp/probe at 210-214 ----
rep("(defconst gDiagE 200)",
    "(defconst gDiagE 200)\n"
    "(defconst vecSquare 202)\n(defconst vecSquare_x 202)\n(defconst vecSquare_y 203)\n"
    "(defconst gE 204)\n(defconst gDistToTgt 205)\n"
    "(defconst gLastX 206)\n(defconst gLastY 207)\n(defconst gPacked 208)\n"
    "(defconst gDir 209)\n"
    "(defconst gAxis 210)\n(defconst gFlipTmp 211)\n"
    "(defconst gDbgT 212)\n(defconst gProbe 213)\n(defconst gDbgTmp 214)")

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

APPENDIX = f""";=== ddkSquareV19 = A->B->A->C, working goal layout (202-209 = V18) + gAxis/flip 210-211. ===

;--- render, gAxis 0: bottom edge (500+gE, 500)  [A..B] ---
(defrule
\t(up-compare-goal gAxis c:== 0)
\t=>
\t(up-modify-goal vecSquare_x c:= {LO})
\t(up-modify-goal vecSquare_x g:+ gE)
\t(up-modify-goal vecSquare_y c:= {LO})
)
;--- render, gAxis 1: left edge (500, 500+gE)  [A..C] ---
(defrule
\t(up-compare-goal gAxis c:== 1)
\t=>
\t(up-modify-goal vecSquare_x c:= {LO})
\t(up-modify-goal vecSquare_y c:= {LO})
\t(up-modify-goal vecSquare_y g:+ gE)
)
;--- distance from the ball to the current target ---
(defrule
\t(true)
\t=>
\t(up-get-point-distance vecMed vecSquare gDistToTgt)
)
;--- march: V7/V18 arrival-gated step (D<{ARRIVE}) ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gState c:== 18)
\t(up-compare-goal gDistToTgt c:< {ARRIVE})
\t=>
\t(up-modify-goal gE g:+ gDir)
)
;--- reverse at the far corner (gE >= {LEG}) ---
(defrule
\t(up-compare-goal gE c:>= {LEG})
\t=>
\t(up-modify-goal gE c:= {LEG})
\t(up-modify-goal gDir c:= -{STEP})
)
;--- FLIP the edge once on arriving home inbound.  gAxis = 1 - gAxis (subtract, no c:*-1) ---
(defrule
\t(up-compare-goal gE c:<= 0)
\t(up-compare-goal gDir c:< 0)
\t=>
\t(up-modify-goal gFlipTmp c:= 1)
\t(up-modify-goal gFlipTmp g:- gAxis)
\t(up-modify-goal gAxis g:= gFlipTmp)
)
;--- reverse at home A (gE <= 0): clamp + head back out (seeds gDir=+{STEP}) ---
(defrule
\t(up-compare-goal gE c:<= 0)
\t=>
\t(up-modify-goal gE c:= 0)
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
)
;--- PROBE every {PROBE_MS}ms: P=gTagged*100+gState ; E=gE ; D=gDistToTgt ; N=gECount ---
(defrule
\t(up-modify-goal gDbgTmp g:= gTimeMilli)
\t(up-modify-goal gDbgTmp g:- gDbgT)
\t(up-compare-goal gDbgTmp c:>= {PROBE_MS})
\t=>
\t(up-modify-goal gDbgT g:= gTimeMilli)
\t(up-modify-goal gProbe g:= gTagged)
\t(up-modify-goal gProbe c:* 100)
\t(up-modify-goal gProbe g:+ gState)
\t(up-chat-data-to-player 1 "P=%d" g: gProbe)
\t(up-chat-data-to-player 1 "E=%d" g: gE)
\t(up-chat-data-to-player 1 "D=%d" g: gDistToTgt)
\t(up-chat-data-to-player 1 "N=%d" g: gECount)
)"""

appendix = APPENDIX.replace("\n", NL) if NL == "\r\n" else APPENDIX
text = text.rstrip("\r\n") + NL + appendix + NL

io.open(DST, "w", encoding="utf-8", newline="").write(text)
n_rules = text.count("(defrule")
print(f"wrote {DST}: {len(text)} chars, {n_rules} defrules (expect 131), NL={NL!r}")

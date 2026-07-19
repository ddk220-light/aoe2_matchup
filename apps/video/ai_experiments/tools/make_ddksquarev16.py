"""Generate ddkSquareV16.per = the FIX for the arrival-gate deadlock.

DIAGNOSIS (from V15's probe): tag OK, state cycles 18<->22, N (enemies) OK, but
D=gDistToTgt is stuck at 700-928 -- the ball starts ~7-9 tiles from home corner A and
the march's  D<350  gate never opens, so gE never takes its first step (E=0 forever).
This is inherent to the arrival gate: it can't take the FIRST step until the ball has
already reached the corner, and a swarmed ball can't close that gap on its own.  (V7/V12
only worked in runs where the ball happened to start near its first corner.)

FIX -- keep V7's tight kiting when close, add a slow creep when far:
  * march-fast (arrival-gated, per pass):  tagged & state18 & N>=1 & D<350  -> gE += gDir.
        This IS V7's march verbatim -- tight kite once the ball is on the edge.
  * march-creep (timer beat, ~{CREEP}ms):  tagged & state18 & N>=1 & D>=350 -> gE += gDir.
        When the ball is far, step the target along the edge anyway so it is never pinned;
        the ball is ordered to the moving target and gets drawn onto the square.  Both the
        A-B and A-C edges are on the perimeter, so the target never crosses the centre.
  The two are mutually exclusive (D<350 vs D>=350), so gE never double-steps.

MOVEMENT otherwise identical to V14/V15: gE[0,600]+gAxis, subtract toggle (no c:*-1),
A->B->A->C.  Probe (P/E/D/N every {PROBE_MS}ms) kept to confirm E now climbs off 0.

Validation: validate_variant.py ddkModelAI.per ddkSquareV16.per 44,45,46,56,57,65 11
"""
import io

MAP_TILES = 16
INSET     = 5
STEP      = 150
ARRIVE    = 350
CREEP     = 1000     # ms per creep step when the ball is far (~matches unit speed)
PROBE_MS  = 1000

LO   = INSET * 100
HI   = (MAP_TILES - INSET) * 100
LEG  = HI - LO

SRC = r"apps\video\ai_experiments\ddkModelAI.per"
DST = r"apps\video\ai_experiments\ddkSquareV16.per"

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
    f"; ddkSquareV16 = A->B->A->C with arrival-gate deadlock FIXED: march-fast (D<{ARRIVE}, V7 kite) +\n"
    f";   march-creep (D>={ARRIVE}, one step per {CREEP}ms) so a far/swarmed ball is never pinned at a corner.\n"
    ";   gE[0,600]+gAxis, subtract toggle.  Probe P/E/D/N kept.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

rep("(defconst gDiagE 200)",
    "(defconst gDiagE 200)\n"
    "(defconst vecSquare 202)\n(defconst vecSquare_x 202)\n(defconst vecSquare_y 203)\n"
    "(defconst gE 204)\n(defconst gDir 205)\n(defconst gAxis 206)\n"
    "(defconst gDistToTgt 207)\n"
    "(defconst gLastX 208)\n(defconst gLastY 209)\n(defconst gPacked 210)\n"
    "(defconst gFlipTmp 211)\n(defconst gDbgT 212)\n(defconst gProbe 213)\n(defconst gDbgTmp 214)\n"
    "(defconst gBeatT 215)\n(defconst gBeatTmp 216)")

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

APPENDIX = f""";=== ddkSquareV16 = deadlock-fixed A->B->A->C.  goals 202-216. ===

;--- seed gDir outbound (+{STEP}) once (defaults 0) ---
(defrule
\t(up-compare-goal gDir c:== 0)
\t=>
\t(up-modify-goal gDir c:= {STEP})
)
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
;--- march-fast: V7's tight kite step, per pass, once the ball is ON the edge (D<{ARRIVE}) ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gState c:== 18)
\t(up-compare-goal gDistToTgt c:< {ARRIVE})
\t=>
\t(up-modify-goal gE g:+ gDir)
)
;--- march-creep: when the ball is FAR (D>={ARRIVE}), step the target once per {CREEP}ms so it is
;    never pinned; the ball is ordered to the moving target and gets drawn onto the square ---
(defrule
\t(up-modify-goal gBeatTmp g:= gTimeMilli)
\t(up-modify-goal gBeatTmp g:- gBeatT)
\t(up-compare-goal gBeatTmp c:>= {CREEP})
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gState c:== 18)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gDistToTgt c:>= {ARRIVE})
\t=>
\t(up-modify-goal gBeatT g:= gTimeMilli)
\t(up-modify-goal gE g:+ gDir)
)
;--- reverse at the far corner (gE >= {LEG}) ---
(defrule
\t(up-compare-goal gE c:>= {LEG})
\t=>
\t(up-modify-goal gE c:= {LEG})
\t(up-modify-goal gDir c:= -{STEP})
)
;--- FLIP the edge once on arriving home inbound.  gAxis = 1 - gAxis (no c:*-1) ---
(defrule
\t(up-compare-goal gE c:<= 0)
\t(up-compare-goal gDir c:< 0)
\t=>
\t(up-modify-goal gFlipTmp c:= 1)
\t(up-modify-goal gFlipTmp g:- gAxis)
\t(up-modify-goal gAxis g:= gFlipTmp)
)
;--- reverse at home A (gE <= 0): clamp + head back out ---
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
print(f"wrote {DST}: {len(text)} chars, {n_rules} defrules (expect 133), NL={NL!r}")

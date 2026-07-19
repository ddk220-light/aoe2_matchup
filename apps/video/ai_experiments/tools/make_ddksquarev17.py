"""Generate ddkSquareV17.per = NO arrival gate at all.  The square target just keeps
cycling A->B->A->C on a steady timer; the units follow the moving x,y.  They never have
to "reach" a corner -- that requirement was deadlocking the start and splitting the ball
into two clumps around the corner.

MARCH (the only change from V16): one rule, a timer beat, NO distance condition --
    every {BEAT}ms while tagged & kiting (state 18): gE += gDir.
That's it.  reverse-at-corner and flip-at-home still bound it to the perimeter, so it
walks bottom edge A->B, back, left edge A->C, back, forever.  Units are ordered to the
moving vecSquare (Rules 56/57) and chase it; wherever they are, the target keeps going.

Everything else identical to V16/V14: gE[0,600]+gAxis, subtract toggle (no c:*-1),
render, log, and the P/E/D/N probe (so you can watch E cycle and D shrink as they follow).

Validation: validate_variant.py ddkModelAI.per ddkSquareV17.per 44,45,46,56,57,65 10
"""
import io

MAP_TILES = 16
INSET     = 5
STEP      = 150
BEAT      = 700      # ms per target step (no arrival gate; pure cadence)
PROBE_MS  = 1000

LO   = INSET * 100
HI   = (MAP_TILES - INSET) * 100
LEG  = HI - LO

SRC = r"apps\video\ai_experiments\ddkModelAI.per"
DST = r"apps\video\ai_experiments\ddkSquareV17.per"

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
    f"; ddkSquareV17 = square target cycles A->B->A->C on a {BEAT}ms timer with NO arrival gate.\n"
    ";   Units never have to reach a corner; they just follow the moving x,y.  gE[0,600]+gAxis,\n"
    ";   subtract toggle.  reverse-at-corner + flip-at-home keep it on the perimeter.  Probe P/E/D/N.\n"
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

APPENDIX = f""";=== ddkSquareV17 = timer-driven square patrol, NO arrival gate.  goals 202-216. ===

;--- seed gDir outbound (+{STEP}) once ---
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
;--- distance (kept only for the probe's D readout) ---
(defrule
\t(true)
\t=>
\t(up-get-point-distance vecMed vecSquare gDistToTgt)
)
;--- march: step the target once per {BEAT}ms while tagged & kiting.  NO distance gate --
;    the square just keeps cycling; the units follow the moving x,y wherever they are. ---
(defrule
\t(up-modify-goal gBeatTmp g:= gTimeMilli)
\t(up-modify-goal gBeatTmp g:- gBeatT)
\t(up-compare-goal gBeatTmp c:>= {BEAT})
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gState c:== 18)
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
print(f"wrote {DST}: {len(text)} chars, {n_rules} defrules (expect 132), NL={NL!r}")

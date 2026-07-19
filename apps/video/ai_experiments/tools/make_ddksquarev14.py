"""Generate ddkSquareV14.per = V13's seamless A->B->A->C, but with the UNPROVEN operation
removed, plus a self-diagnostic so one test run pinpoints any remaining failure.

WHAT CHANGED vs V13 (which failed: no coords, stuck STATE22):
  1. The axis toggle no longer uses  c:* -1  (multiply by negative).  The base AI never
     multiplies by a negative and no known-good AI in the corpus does either -- it is an
     UNPROVEN op and the prime suspect (V8 and V13, the two hard failures, both used it;
     V7 and V12, which work, never multiply).  V14 flips the axis with plain subtraction:
        gFlipTmp = 1 ; gFlipTmp -= gAxis ; gAxis = gFlipTmp     (gAxis 0<->1, no negatives)
  2. A STATE PROBE chats every 2s:
        P = gTagged*100 + gState        E = gE
     Decode:  P=0 -> never tagged (base problem, not the square logic)
              P=118 -> tagged & in KITE state 18   P=122 -> tagged & stuck in VOLLEY 22
              E climbing 0..600 -> the march is advancing (movement works)
              E stuck at 0 -> tagged/stated but not marching
     (P/E come from proven ops only: c:* 100 and the base gTimeMilli beat idiom.)

MOVEMENT is otherwise IDENTICAL to V13:  gE in [0,600] oscillates exactly like V7/V12
(never teleports, never negative); gAxis picks the edge -- gAxis=0 leg IS V7 (bottom,
(500+gE,500)), gAxis=1 leg IS V12 (left, (500,500+gE)); at home gE=0 both render A, so the
flip is seamless.  Sequence A->B->A->C->A->B ...

Validation: validate_variant.py ddkModelAI.per ddkSquareV14.per 44,45,46,56,57,65 9
"""
import io

MAP_TILES = 16
INSET     = 5
STEP      = 150
ARRIVE    = 350
PROBE_MS  = 2000

LO   = INSET * 100                 # 500
HI   = (MAP_TILES - INSET) * 100   # 1100
LEG  = HI - LO                     # 600

SRC = r"apps\video\ai_experiments\ddkModelAI.per"
DST = r"apps\video\ai_experiments\ddkSquareV14.per"

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
    f"; ddkSquareV14 = V13 (A->B->A->C via gE[0,{LEG}]+gAxis) but NO c:*-1 (subtract toggle) + STATE PROBE.\n"
    f";   Probe every {PROBE_MS}ms: P=gTagged*100+gState (0=untagged,118=kite,122=stuck-volley); E=gE.\n"
    ";   gAxis=0 leg IS V7 (bottom); gAxis=1 leg IS V12 (left); flip at home A is seamless.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

# ---------- new goals (202-214) ----------
rep("(defconst gDiagE 200)",
    "(defconst gDiagE 200)\n"
    "(defconst vecSquare 202)\n(defconst vecSquare_x 202)\n(defconst vecSquare_y 203)\n"
    "(defconst gE 204)\n(defconst gDir 205)\n(defconst gAxis 206)\n"
    "(defconst gDistToTgt 207)\n"
    "(defconst gLastX 208)\n(defconst gLastY 209)\n(defconst gPacked 210)\n"
    "(defconst gFlipTmp 211)\n(defconst gDbgT 212)\n(defconst gProbe 213)\n(defconst gDbgTmp 214)")

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

# ---------- APPENDIX (9 rules) ----------
APPENDIX = f""";=== ddkSquareV14 = V7/V12 legs + seamless flip (no c:*-1) + state probe.  goals 202-214. ===

;--- render, gAxis 0: bottom edge (500+gE, 500)  [A..B] -- identical to V7 ---
(defrule
\t(up-compare-goal gAxis c:== 0)
\t=>
\t(up-modify-goal vecSquare_x c:= {LO})
\t(up-modify-goal vecSquare_x g:+ gE)
\t(up-modify-goal vecSquare_y c:= {LO})
)
;--- render, gAxis 1: left edge (500, 500+gE)  [A..C] -- identical to V12 ---
(defrule
\t(up-compare-goal gAxis c:== 1)
\t=>
\t(up-modify-goal vecSquare_x c:= {LO})
\t(up-modify-goal vecSquare_y c:= {LO})
\t(up-modify-goal vecSquare_y g:+ gE)
)
;--- distance from the ball to the current target (V7/V12, verbatim) ---
(defrule
\t(true)
\t=>
\t(up-get-point-distance vecMed vecSquare gDistToTgt)
)
;--- march: step gE by gDir while KITE-moving AND the ball reached the target (V7/V12 rule) ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gState c:== 18)
\t(up-compare-goal gDistToTgt c:< {ARRIVE})
\t=>
\t(up-modify-goal gE g:+ gDir)
)
;--- reverse at the far corner (gE >= {LEG}): head back toward home A (V7/V12, verbatim) ---
(defrule
\t(up-compare-goal gE c:>= {LEG})
\t=>
\t(up-modify-goal gE c:= {LEG})
\t(up-modify-goal gDir c:= -{STEP})
)
;--- FLIP the edge once on arriving home inbound (gE<=0 AND gDir<0).  gAxis = 1 - gAxis
;    (subtraction only -- NO c:*-1).  reverse-home below sets gDir=+{STEP} the same pass,
;    so this can't re-fire while waiting at home. ---
(defrule
\t(up-compare-goal gE c:<= 0)
\t(up-compare-goal gDir c:< 0)
\t=>
\t(up-modify-goal gFlipTmp c:= 1)
\t(up-modify-goal gFlipTmp g:- gAxis)
\t(up-modify-goal gAxis g:= gFlipTmp)
)
;--- reverse at home A (gE <= 0): clamp + head back out (seeds gDir=+{STEP} on pass 1) (V7/V12) ---
(defrule
\t(up-compare-goal gE c:<= 0)
\t=>
\t(up-modify-goal gE c:= 0)
\t(up-modify-goal gDir c:= {STEP})
)
;--- LOG: one packed message per target change.  packed = x*10000 + y (V7/V12, verbatim) ---
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
;--- STATE PROBE every {PROBE_MS}ms: P=gTagged*100+gState ; E=gE.  (diagnostic; proven ops only) ---
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
)"""

appendix = APPENDIX.replace("\n", NL) if NL == "\r\n" else APPENDIX
text = text.rstrip("\r\n") + NL + appendix + NL

io.open(DST, "w", encoding="utf-8", newline="").write(text)
n_rules = text.count("(defrule")
print(f"wrote {DST}: {len(text)} chars, {n_rules} defrules (expect 131), NL={NL!r}")

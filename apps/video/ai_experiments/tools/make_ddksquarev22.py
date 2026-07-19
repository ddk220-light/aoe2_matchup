"""ddkSquareV22.per = FINAL: home is captured from the units themselves (no tile guessing).

Whole-saga lesson: the A->B->A->C failures were a location mismatch -- home anchored on the
wrong side from where the ball fights. The tile/compass mapping is murky, so V22 does NOT
hardcode a corner. Instead, at the first tag it LATCHES home = vecMed (the ball's own
position), then patrols two perpendicular legs toward the map centre:

    A(home) -> B (out along X, ~6 tiles toward centre) -> A -> C (out along Y) -> A -> ...

Because home == the units, D is ~0 at the start, the arrival gate opens immediately, and it
kites. "We don't care about north/south, just pick one and come back" -> the two legs are the
+/-X and +/-Y directions, each pointed toward map centre so they stay on the map.

State:
  gInit 0->1 (capture home + default +STEP legs) ->2 (flip a leg to -STEP if home past centre).
  gAxis 0 = X leg, 1 = Y leg (flip at home, subtract toggle).
  gE 0..600 oscillation, arrival-gated march (D<350), same as the proven V7/V18.
Probe reports P,E,D,M(vecMed),S(vecSquare),H(captured home) so we can verify the anchor.

Validation: validate_variant.py ddkModelAI.per ddkSquareV22.per 44,45,46,56,57,65 15
"""
import io

STEP=150; ARRIVE=350; LEG=600; MID=800; PROBE_MS=1000
SRC=r"apps\video\ai_experiments\ddkModelAI.per"
DST=r"apps\video\ai_experiments\ddkSquareV22.per"
text=io.open(SRC,encoding="utf-8",newline="").read()
NL="\r\n" if "\r\n" in text else "\n"

def rep(old,new,n=1):
    global text
    old=old.replace("\n",NL); new=new.replace("\n",NL)
    c=text.count(old); assert c==n,f"anchor {c}x (want {n}): {old[:70]!r}"
    text=text.replace(old,new)

rep("; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +",
    "; ddkSquareV22 = home LATCHED from vecMed at tag (no tile guessing); 2 perpendicular legs toward\n"
    ";   centre: A->B->A->C.  Arrival-gated; home==units so the gate opens at once.  Probe P/E/D/M/S/H.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

rep("(defconst gDiagE 200)",
    "(defconst gDiagE 200)\n"
    "(defconst vecSquare 202)\n(defconst vecSquare_x 202)\n(defconst vecSquare_y 203)\n"
    "(defconst gE 204)\n(defconst gDistToTgt 205)\n"
    "(defconst gLastX 206)\n(defconst gLastY 207)\n(defconst gPacked 208)\n"
    "(defconst gDir 209)\n"
    "(defconst gAxis 210)\n(defconst gFlipTmp 211)\n"
    "(defconst gHomeX 212)\n(defconst gHomeY 213)\n"
    "(defconst gStepX 214)\n(defconst gStepY 215)\n(defconst gInit 216)\n"
    "(defconst gDbgT 217)\n(defconst gProbe 218)\n(defconst gDbgTmp 219)")

rep('\n\t(chat-to-player 1 "KITE")',"",n=1)
rep('\n\t(chat-to-player 1 "KITE2")',"",n=1)
rep('\n\t(chat-to-player 1 "VOLLEY")',"",n=1)
rep('\n\t(chat-to-player 1 "MOVE-P")',"",n=1)
rep('\n\t(chat-to-player 1 "MOVE-M")',"",n=1)
rep('\n\t(chat-to-player 1 "no targets in range")',"",n=1)

rep("(up-target-point vecKite action-patrol formation-line stance-no-attack)",
    "(up-target-point vecSquare action-patrol formation-line stance-no-attack)",n=2)
rep("(up-target-point vecKite action-move formation-line stance-no-attack)",
    "(up-target-point vecSquare action-move formation-line stance-no-attack)",n=2)

APPENDIX=f""";=== ddkSquareV22 = latched-home 2-leg patrol.  goals 202-219. ===

;--- INIT stage 1: latch home = vecMed, default legs +{STEP}, once at first tag ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gInit c:== 0)
\t=>
\t(up-modify-goal gHomeX g:= vecMed_x)
\t(up-modify-goal gHomeY g:= vecMed_y)
\t(up-modify-goal gStepX c:= {STEP})
\t(up-modify-goal gStepY c:= {STEP})
\t(up-modify-goal gInit c:= 1)
)
;--- INIT stage 2a: if home is in the far-X half, aim the X leg the other way (toward centre) ---
(defrule
\t(up-compare-goal gInit c:== 1)
\t(up-compare-goal gHomeX c:>= {MID})
\t=>
\t(up-modify-goal gStepX c:= -{STEP})
)
;--- INIT stage 2b: same for Y ---
(defrule
\t(up-compare-goal gInit c:== 1)
\t(up-compare-goal gHomeY c:>= {MID})
\t=>
\t(up-modify-goal gStepY c:= -{STEP})
)
;--- INIT done ---
(defrule
\t(up-compare-goal gInit c:== 1)
\t=>
\t(up-modify-goal gInit c:= 2)
)
;--- render X leg (gAxis 0), +X:  (homeX + gE, homeY) ---
(defrule
\t(up-compare-goal gAxis c:== 0)
\t(up-compare-goal gStepX c:> 0)
\t=>
\t(up-modify-goal vecSquare_x g:= gHomeX)
\t(up-modify-goal vecSquare_x g:+ gE)
\t(up-modify-goal vecSquare_y g:= gHomeY)
)
;--- render X leg, -X:  (homeX - gE, homeY) ---
(defrule
\t(up-compare-goal gAxis c:== 0)
\t(up-compare-goal gStepX c:< 0)
\t=>
\t(up-modify-goal vecSquare_x g:= gHomeX)
\t(up-modify-goal vecSquare_x g:- gE)
\t(up-modify-goal vecSquare_y g:= gHomeY)
)
;--- render Y leg (gAxis 1), +Y:  (homeX, homeY + gE) ---
(defrule
\t(up-compare-goal gAxis c:== 1)
\t(up-compare-goal gStepY c:> 0)
\t=>
\t(up-modify-goal vecSquare_x g:= gHomeX)
\t(up-modify-goal vecSquare_y g:= gHomeY)
\t(up-modify-goal vecSquare_y g:+ gE)
)
;--- render Y leg, -Y:  (homeX, homeY - gE) ---
(defrule
\t(up-compare-goal gAxis c:== 1)
\t(up-compare-goal gStepY c:< 0)
\t=>
\t(up-modify-goal vecSquare_x g:= gHomeX)
\t(up-modify-goal vecSquare_y g:= gHomeY)
\t(up-modify-goal vecSquare_y g:- gE)
)
;--- distance ---
(defrule
\t(true)
\t=>
\t(up-get-point-distance vecMed vecSquare gDistToTgt)
)
;--- march: arrival-gated (D<{ARRIVE}) ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gState c:== 18)
\t(up-compare-goal gDistToTgt c:< {ARRIVE})
\t=>
\t(up-modify-goal gE g:+ gDir)
)
;--- reverse at far end (gE >= {LEG}) ---
(defrule
\t(up-compare-goal gE c:>= {LEG})
\t=>
\t(up-modify-goal gE c:= {LEG})
\t(up-modify-goal gDir c:= -{STEP})
)
;--- flip leg at home (subtract toggle, no c:*-1) ---
(defrule
\t(up-compare-goal gE c:<= 0)
\t(up-compare-goal gDir c:< 0)
\t=>
\t(up-modify-goal gFlipTmp c:= 1)
\t(up-modify-goal gFlipTmp g:- gAxis)
\t(up-modify-goal gAxis g:= gFlipTmp)
)
;--- reverse at home (seed gDir) ---
(defrule
\t(up-compare-goal gE c:<= 0)
\t=>
\t(up-modify-goal gE c:= 0)
\t(up-modify-goal gDir c:= {STEP})
)
;--- LOG xy ---
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
;--- PROBE: P,E,D,M=vecMed,S=vecSquare,H=home ---
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
\t(up-modify-goal gProbe g:= vecMed_x)
\t(up-modify-goal gProbe c:* 10000)
\t(up-modify-goal gProbe g:+ vecMed_y)
\t(up-chat-data-to-player 1 "M=%d" g: gProbe)
\t(up-modify-goal gProbe g:= vecSquare_x)
\t(up-modify-goal gProbe c:* 10000)
\t(up-modify-goal gProbe g:+ vecSquare_y)
\t(up-chat-data-to-player 1 "S=%d" g: gProbe)
\t(up-modify-goal gProbe g:= gHomeX)
\t(up-modify-goal gProbe c:* 10000)
\t(up-modify-goal gProbe g:+ gHomeY)
\t(up-chat-data-to-player 1 "H=%d" g: gProbe)
)"""

appendix=APPENDIX.replace("\n",NL) if NL=="\r\n" else APPENDIX
text=text.rstrip("\r\n")+NL+appendix+NL
io.open(DST,"w",encoding="utf-8",newline="").write(text)
print(f"wrote {DST}: {text.count('(defrule')} defrules (expect 137), NL={NL!r}")

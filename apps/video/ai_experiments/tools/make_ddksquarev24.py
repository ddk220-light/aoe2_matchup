"""ddkSquareV24.per = THE FIX. The gAxis-render versions all failed for one reason:
vecSquare was never rendered, so the target sat at the goal-default (-1,-1) off-map.

Proof (V23 M/S probe): M(ball)=~(620,500)  S(target)=(-1,-1)  D=~800=dist(ball,(-1,-1)).
Root cause: goals default to -1 here (not 0). The render fires only on gAxis==0/==1, but
gAxis defaults to -1 AND the flip rule misfires on pass 1 (default gDir=-1 < 0) and corrupts
gAxis to junk -> neither render rule ever fires -> vecSquare keeps its -1 default. The sxy
versions (V7/V12/V18) worked because sxy's first branch (gS<600) catches the -1 default.

FIXES:
  1. one-shot INIT (gInit latch) sets gAxis=0, gDir=+STEP, gE=0 BEFORE the flip can run.
  2. render conditions widened to gAxis<=0 (leg X) / gAxis>=1 (leg Y) so SOME render always
     fires no matter what gAxis holds.
  3. home back at the WEST corner (500,500) where the ball actually is (M showed ~(620,500)),
     patrolling A->B(1100,500)->A->C(500,1100).  Arrival-gated; ball is ~1.4 tiles from A so
     the gate opens at once. Probe P/E/D/M/S.

Validation: validate_variant.py ddkModelAI.per ddkSquareV24.per 44,45,46,56,57,65 10
"""
import io

STEP=150; ARRIVE=350; LEG=600; PROBE_MS=1000
HX,HY = 500,500           # HOME A = west corner (ball sits ~here, M=~(620,500))
SRC=r"apps\video\ai_experiments\ddkModelAI.per"
DST=r"apps\video\ai_experiments\ddkSquareV24.per"
text=io.open(SRC,encoding="utf-8",newline="").read()
NL="\r\n" if "\r\n" in text else "\n"

def rep(old,new,n=1):
    global text
    old=old.replace("\n",NL); new=new.replace("\n",NL)
    c=text.count(old); assert c==n,f"anchor {c}x (want {n}): {old[:70]!r}"
    text=text.replace(old,new)

rep("; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +",
    f"; ddkSquareV24 = FIX uninitialized gAxis (was leaving vecSquare at -1,-1 off-map).  INIT gAxis=0/gDir=+{STEP},\n"
    f";   widened render (gAxis<=0 / >=1), home A=({HX},{HY}) west corner.  A->B(1100,{HY})->A->C({HX},1100).  Probe.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

rep("(defconst gDiagE 200)",
    "(defconst gDiagE 200)\n"
    "(defconst vecSquare 202)\n(defconst vecSquare_x 202)\n(defconst vecSquare_y 203)\n"
    "(defconst gE 204)\n(defconst gDistToTgt 205)\n"
    "(defconst gLastX 206)\n(defconst gLastY 207)\n(defconst gPacked 208)\n"
    "(defconst gDir 209)\n"
    "(defconst gAxis 210)\n(defconst gFlipTmp 211)\n(defconst gInit 212)\n"
    "(defconst gDbgT 213)\n(defconst gProbe 214)\n(defconst gDbgTmp 215)")

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

APPENDIX=f""";=== ddkSquareV24 = FIX uninit gAxis; home A=({HX},{HY}).  goals 202-215. ===

;--- one-shot INIT: gAxis/gDir/gE to sane values BEFORE the flip can misfire (goals default -1) ---
(defrule
\t(up-compare-goal gInit c:!= 1)
\t=>
\t(up-modify-goal gInit c:= 1)
\t(up-modify-goal gAxis c:= 0)
\t(up-modify-goal gDir c:= {STEP})
\t(up-modify-goal gE c:= 0)
)
;--- render, X leg (gAxis <= 0): A->B  ({HX}+gE, {HY})  gE0=A gE600=B(1100,{HY}) ---
(defrule
\t(up-compare-goal gAxis c:<= 0)
\t=>
\t(up-modify-goal vecSquare_x c:= {HX})
\t(up-modify-goal vecSquare_x g:+ gE)
\t(up-modify-goal vecSquare_y c:= {HY})
)
;--- render, Y leg (gAxis >= 1): A->C  ({HX}, {HY}+gE)  gE0=A gE600=C({HX},1100) ---
(defrule
\t(up-compare-goal gAxis c:>= 1)
\t=>
\t(up-modify-goal vecSquare_x c:= {HX})
\t(up-modify-goal vecSquare_y c:= {HY})
\t(up-modify-goal vecSquare_y g:+ gE)
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
;--- flip leg at home (subtract toggle) ---
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
;--- PROBE: P,E,D,M=vecMed,S=vecSquare ---
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
)"""

appendix=APPENDIX.replace("\n",NL) if NL=="\r\n" else APPENDIX
text=text.rstrip("\r\n")+NL+appendix+NL
io.open(DST,"w",encoding="utf-8",newline="").write(text)
print(f"wrote {DST}: {text.count('(defrule')} defrules (expect 132), HOME=({HX},{HY}), NL={NL!r}")

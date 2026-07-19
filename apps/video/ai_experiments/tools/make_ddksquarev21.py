"""ddkSquareV21.per = the alternation re-anchored to the corner the units ACTUALLY sit on.

Per the user's drawing:
  A = HOME = (5,11) = precise (500,1100)  -- the west corner, where the ball spawns/fights
  B = (5,5)   = (500,500)   -- up the LEFT edge from A (x=500 fixed, y 1100->500)
  C = (11,11) = (1100,1100) -- along the BOTTOM edge from A (y=1100 fixed, x 500->1100)
  (unused far corner D = (11,5))
  Patrol A->B->A->C->A->B ...

Everything else = V19/V20: arrival-gated march (units start ON home so the gate opens at
once), gE[0,600]+gAxis, subtract toggle, working goal layout, P/E/D/M/S probe.
  gAxis 0 -> (500, 1100-gE)  [A..B up the left edge]
  gAxis 1 -> (500+gE, 1100)  [A..C along the bottom edge]
  gE=0 -> both = (500,1100)=A, so the flip at home is seamless.

Validation: validate_variant.py ddkModelAI.per ddkSquareV21.per 44,45,46,56,57,65 9
"""
import io

MAP_TILES=16; INSET=5; STEP=150; ARRIVE=350; PROBE_MS=1000
LO=INSET*100; HI=(MAP_TILES-INSET)*100; LEG=HI-LO      # 500,1100,600
HX,HY=LO,HI                                            # HOME A = (500,1100)
SRC=r"apps\video\ai_experiments\ddkModelAI.per"
DST=r"apps\video\ai_experiments\ddkSquareV21.per"
text=io.open(SRC,encoding="utf-8",newline="").read()
NL="\r\n" if "\r\n" in text else "\n"

def rep(old,new,n=1):
    global text
    old=old.replace("\n",NL); new=new.replace("\n",NL)
    c=text.count(old); assert c==n,f"anchor {c}x (want {n}): {old[:70]!r}"
    text=text.replace(old,new)

rep("; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +",
    f"; ddkSquareV21 = alternation re-anchored: HOME A=({HX},{HY}) (units' corner); B=({LO},{LO}) up left edge;\n"
    f";   C=({HI},{HI}) along bottom edge.  A->B->A->C.  Arrival-gated; units start ON home so gate opens.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

rep("(defconst gDiagE 200)",
    "(defconst gDiagE 200)\n"
    "(defconst vecSquare 202)\n(defconst vecSquare_x 202)\n(defconst vecSquare_y 203)\n"
    "(defconst gE 204)\n(defconst gDistToTgt 205)\n"
    "(defconst gLastX 206)\n(defconst gLastY 207)\n(defconst gPacked 208)\n"
    "(defconst gDir 209)\n"
    "(defconst gAxis 210)\n(defconst gFlipTmp 211)\n"
    "(defconst gDbgT 212)\n(defconst gProbe 213)\n(defconst gDbgTmp 214)")

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

APPENDIX=f""";=== ddkSquareV21 = A=({HX},{HY}) home; B=({LO},{LO}); C=({HI},{HI}).  goals 202-214. ===

;--- render, gAxis 0: LEFT edge A->B  (500, 1100-gE)  gE0=A(500,1100) gE600=B(500,500) ---
(defrule
\t(up-compare-goal gAxis c:== 0)
\t=>
\t(up-modify-goal vecSquare_x c:= {HX})
\t(up-modify-goal vecSquare_y c:= {HY})
\t(up-modify-goal vecSquare_y g:- gE)
)
;--- render, gAxis 1: BOTTOM edge A->C  (500+gE, 1100)  gE0=A(500,1100) gE600=C(1100,1100) ---
(defrule
\t(up-compare-goal gAxis c:== 1)
\t=>
\t(up-modify-goal vecSquare_x c:= {HX})
\t(up-modify-goal vecSquare_x g:+ gE)
\t(up-modify-goal vecSquare_y c:= {HY})
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
;--- reverse far ---
(defrule
\t(up-compare-goal gE c:>= {LEG})
\t=>
\t(up-modify-goal gE c:= {LEG})
\t(up-modify-goal gDir c:= -{STEP})
)
;--- flip at home (subtract toggle) ---
(defrule
\t(up-compare-goal gE c:<= 0)
\t(up-compare-goal gDir c:< 0)
\t=>
\t(up-modify-goal gFlipTmp c:= 1)
\t(up-modify-goal gFlipTmp g:- gAxis)
\t(up-modify-goal gAxis g:= gFlipTmp)
)
;--- reverse home (seed gDir) ---
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
;--- PROBE: P,E,D + M=vecMed(packed) + S=vecSquare(packed) ---
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
print(f"wrote {DST}: {text.count('(defrule')} defrules (expect 131), HOME=({HX},{HY}), NL={NL!r}")

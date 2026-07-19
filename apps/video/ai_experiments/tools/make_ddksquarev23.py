"""ddkSquareV23.per = FIXED home at the square's WEST corner (the 'A' the user marked).

NOT adaptive (V22 was a misread). Home is a hardcoded map point = the west corner of the
inset square the units are meant to patrol within, matching the user's drawing:
  A = HOME = (500,1100)  = tile (5,11)   -- west corner (where the ball sits / stays within)
  B = (500,500)   = tile (5,5)    -- up   the west edge  (x fixed 500, y 1100->500)
  C = (1100,1100) = tile (11,11)  -- across the south edge (y fixed 1100, x 500->1100)
  (far corner D = (1100,500) unused)
  Patrol A->B->A->C->A->B ...   ("pick one, out and back, then the other, out and back")

Arrival-gated march (D<350) like the proven V7/V18 so the target stays glued to the ball;
gE[0,600] oscillation, flip at home (subtract toggle), working goal layout. Probe reports
P/E/D and M=vecMed, S=vecSquare so we can confirm the ball is on the square. If M shows the
ball starts a little off (500,1100), nudge the HX/HY constants below to match.

Validation: validate_variant.py ddkModelAI.per ddkSquareV23.per 44,45,46,56,57,65 9
"""
import io

STEP=150; ARRIVE=350; LEG=600; PROBE_MS=1000
HX,HY = 500,1100          # HOME A = west corner of the square (edit here to re-anchor)
BX,BY = 500,500           # B: end of the "up" leg   (gAxis 0: x=HX, y = HY - gE)
CX,CY = 1100,1100         # C: end of the "across" leg (gAxis 1: y=HY, x = HX + gE)
SRC=r"apps\video\ai_experiments\ddkModelAI.per"
DST=r"apps\video\ai_experiments\ddkSquareV23.per"
text=io.open(SRC,encoding="utf-8",newline="").read()
NL="\r\n" if "\r\n" in text else "\n"

def rep(old,new,n=1):
    global text
    old=old.replace("\n",NL); new=new.replace("\n",NL)
    c=text.count(old); assert c==n,f"anchor {c}x (want {n}): {old[:70]!r}"
    text=text.replace(old,new)

rep("; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +",
    f"; ddkSquareV23 = FIXED home at the square's WEST corner A=({HX},{HY}); B=({BX},{BY}) up, C=({CX},{CY}) across.\n"
    ";   A->B->A->C.  Arrival-gated.  NOT adaptive.  Probe P/E/D/M/S.\n"
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

APPENDIX=f""";=== ddkSquareV23 = FIXED west-corner home A=({HX},{HY}).  goals 202-214. ===

;--- render, gAxis 0: UP leg A->B  (x={HX}, y={HY}-gE)  gE0=A({HX},{HY}) gE600=B({BX},{BY}) ---
(defrule
\t(up-compare-goal gAxis c:== 0)
\t=>
\t(up-modify-goal vecSquare_x c:= {HX})
\t(up-modify-goal vecSquare_y c:= {HY})
\t(up-modify-goal vecSquare_y g:- gE)
)
;--- render, gAxis 1: ACROSS leg A->C  (x={HX}+gE, y={HY})  gE0=A gE600=C({CX},{CY}) ---
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
print(f"wrote {DST}: {text.count('(defrule')} defrules (expect 131), HOME=({HX},{HY}), NL={NL!r}")

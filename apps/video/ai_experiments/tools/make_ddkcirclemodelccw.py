"""ddkCircleModelCCW.per = ANTICLOCKWISE twin of ddkCircleModel (=ddkSquareV25).

Identical mechanics (goals default -1 -> init; arrival gate D<ARRIVE; gCorner edge index only
advances mod 4; STEP march). ONLY the 4 render edges are reversed so the ball walks the square
the OTHER way:  A(500,500) -> C(500,1100) -> D(1100,1100) -> B(1100,500) -> A.

Use: the mixed matchups keep base positions (NO ownership swap). When the ranged ball is in the
TOP (ranged_vs_melee, enemy below) it kites CLOCKWISE = ddkCircleModel. When the ranged ball is
kept in the BOTTOM (melee_vs_ranged, enemy above) it must peel the other way = CCW = this file.

Validation: validate_variant.py ddkModelAI.per ddkCircleModelCCW.per 44,45,46,56,57,65 11
"""
import io

STEP=150; ARRIVE=350; LEG=600; PROBE_MS=1000
AX,AY = 500,500       # A = west corner
BX,BY = 1100,500      # B
DX,DY = 1100,1100     # D = far corner
CX,CY = 500,1100      # C
SRC=r"apps\video\ai_experiments\ddkModelAI.per"
DST=r"apps\video\ai_experiments\ddkCircleModelCCW.per"
text=io.open(SRC,encoding="utf-8",newline="").read()
NL="\r\n" if "\r\n" in text else "\n"

def rep(old,new,n=1):
    global text
    old=old.replace("\n",NL); new=new.replace("\n",NL)
    c=text.count(old); assert c==n,f"anchor {c}x (want {n}): {old[:70]!r}"
    text=text.replace(old,new)

rep("; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +",
    f"; ddkCircleModelCCW = ANTICLOCKWISE loop A({AX},{AY})->C({CX},{CY})->D({DX},{DY})->B({BX},{BY})->A.\n"
    ";   Reverse of ddkCircleModel; gCorner (edge 0..3) only advances (mod 4).  Arrival-gated march.  Probe.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

rep("(defconst gDiagE 200)",
    "(defconst gDiagE 200)\n"
    "(defconst vecSquare 202)\n(defconst vecSquare_x 202)\n(defconst vecSquare_y 203)\n"
    "(defconst gE 204)\n(defconst gDistToTgt 205)\n"
    "(defconst gLastX 206)\n(defconst gLastY 207)\n(defconst gPacked 208)\n"
    "(defconst gCorner 209)\n(defconst gInit 210)\n"
    "(defconst gDbgT 211)\n(defconst gProbe 212)\n(defconst gDbgTmp 213)")

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

APPENDIX=f""";=== ddkCircleModelCCW = anticlockwise perimeter loop.  goals 202-213. ===

;--- one-shot INIT: gCorner/gE sane BEFORE any read (goals default -1) ---
(defrule
\t(up-compare-goal gInit c:!= 1)
\t=>
\t(up-modify-goal gInit c:= 1)
\t(up-modify-goal gCorner c:= 0)
\t(up-modify-goal gE c:= 0)
)
;--- render edge 0  A->C  (x={AX}, y={AY}+gE)  keyed c:<=0 = catch-all for the -1 default ---
(defrule
\t(up-compare-goal gCorner c:<= 0)
\t=>
\t(up-modify-goal vecSquare_x c:= {AX})
\t(up-modify-goal vecSquare_y c:= {AY})
\t(up-modify-goal vecSquare_y g:+ gE)
)
;--- render edge 1  C->D  (x={CX}+gE, y={CY}) ---
(defrule
\t(up-compare-goal gCorner c:== 1)
\t=>
\t(up-modify-goal vecSquare_x c:= {CX})
\t(up-modify-goal vecSquare_x g:+ gE)
\t(up-modify-goal vecSquare_y c:= {CY})
)
;--- render edge 2  D->B  (x={DX}, y={DY}-gE) ---
(defrule
\t(up-compare-goal gCorner c:== 2)
\t=>
\t(up-modify-goal vecSquare_x c:= {DX})
\t(up-modify-goal vecSquare_y c:= {DY})
\t(up-modify-goal vecSquare_y g:- gE)
)
;--- render edge 3  B->A  (x={BX}-gE, y={BY}) ---
(defrule
\t(up-compare-goal gCorner c:== 3)
\t=>
\t(up-modify-goal vecSquare_x c:= {BX})
\t(up-modify-goal vecSquare_x g:- gE)
\t(up-modify-goal vecSquare_y c:= {BY})
)
;--- distance ball -> target ---
(defrule
\t(true)
\t=>
\t(up-get-point-distance vecMed vecSquare gDistToTgt)
)
;--- march: arrival-gated (D<{ARRIVE}), always +{STEP}, never reverses ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gState c:== 18)
\t(up-compare-goal gDistToTgt c:< {ARRIVE})
\t=>
\t(up-modify-goal gE c:+ {STEP})
)
;--- end of edge (gE >= {LEG}): reset gE, advance to next edge (anticlockwise) ---
(defrule
\t(up-compare-goal gE c:>= {LEG})
\t=>
\t(up-modify-goal gE c:= 0)
\t(up-modify-goal gCorner c:+ 1)
)
;--- wrap edge index 4 -> 0 (mod 4) ---
(defrule
\t(up-compare-goal gCorner c:>= 4)
\t=>
\t(up-modify-goal gCorner c:= 0)
)
;--- LOG xy on change ---
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
;--- PROBE: P=tag/state, E=gE, D=dist, M=vecMed, S=vecSquare, C=gCorner ---
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
\t(up-chat-data-to-player 1 "C=%d" g: gCorner)
)"""

appendix=APPENDIX.replace("\n",NL) if NL=="\r\n" else APPENDIX
text=text.rstrip("\r\n")+NL+appendix+NL
io.open(DST,"w",encoding="utf-8",newline="").write(text)
print(f"wrote {DST}: {text.count('(defrule')} defrules (expect 133), CCW A->C->D->B, NL={NL!r}")

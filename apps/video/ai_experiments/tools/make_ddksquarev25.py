"""ddkSquareV25.per = CONTINUOUS CLOCKWISE perimeter loop (no back-and-forth).

V24 proved the mechanics (goals default -1 -> must init; arrival gate D<ARRIVE keeps the
target glued to the ball; subtraction toggles not c:*-1; goals 202+).  But V24 oscillated
A->B->A->C.  The user wants a real loop around the square, clockwise, never reversing:

    A(500,500) -> B(1100,500) -> D(1100,1100) -> C(500,1100) -> A ...

Mechanism (all V24 lessons kept):
  gCorner (edge index 0..3) says which edge we're walking; gE (0..LEG) is progress along it.
  Four render rules interpolate vecSquare from the edge's start corner toward its end corner:
    edge 0  A->B : x = 500 + gE, y = 500          (+X)
    edge 1  B->D : x = 1100,     y = 500 + gE     (+Y)
    edge 2  D->C : x = 1100 - gE, y = 1100        (-X)
    edge 3  C->A : x = 500,      y = 1100 - gE    (-Y)
  gE marches +STEP per pass, arrival-gated (D<ARRIVE) exactly like V24 -- so STEP is still the
  "how far the units move each step" knob the user wants to tune later.  When gE reaches LEG,
  gE resets to 0 and gCorner advances (mod 4).  gCorner NEVER decreases: pure clockwise, no flip.
  The end of each edge == the start of the next (same corner) so vecSquare is continuous.

INIT: goals default -1, so a one-shot gInit latch sets gCorner=0, gE=0 before anything reads
them; edge-0 render is keyed c:<=0 (catch-all) so a stray -1 still renders A, never off-map.
Probe P/E/D/M/S kept for this verification run (S must be a real corner, D small, E cycling,
C=gCorner walking 0->1->2->3->0).

Validation: validate_variant.py ddkModelAI.per ddkSquareV25.per 44,45,46,56,57,65 11
"""
import io

STEP=150; ARRIVE=350; LEG=600; PROBE_MS=1000
AX,AY = 500,500       # A = home / west corner
BX,BY = 1100,500      # B = adjacent corner (end of +X edge)
DX,DY = 1100,1100     # D = far corner (end of +Y edge)
CX,CY = 500,1100      # C = other adjacent corner (end of -X edge)
SRC=r"apps\video\ai_experiments\ddkModelAI.per"
DST=r"apps\video\ai_experiments\ddkSquareV25.per"
text=io.open(SRC,encoding="utf-8",newline="").read()
NL="\r\n" if "\r\n" in text else "\n"

def rep(old,new,n=1):
    global text
    old=old.replace("\n",NL); new=new.replace("\n",NL)
    c=text.count(old); assert c==n,f"anchor {c}x (want {n}): {old[:70]!r}"
    text=text.replace(old,new)

rep("; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +",
    f"; ddkSquareV25 = CONTINUOUS CLOCKWISE loop A({AX},{AY})->B({BX},{BY})->D({DX},{DY})->C({CX},{CY})->A.\n"
    ";   No back-and-forth; gCorner (edge 0..3) only advances (mod 4).  Arrival-gated march; STEP tunable.  Probe.\n"
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

APPENDIX=f""";=== ddkSquareV25 = continuous clockwise perimeter loop.  goals 202-213. ===

;--- one-shot INIT: gCorner/gE sane BEFORE any read (goals default -1) ---
(defrule
\t(up-compare-goal gInit c:!= 1)
\t=>
\t(up-modify-goal gInit c:= 1)
\t(up-modify-goal gCorner c:= 0)
\t(up-modify-goal gE c:= 0)
)
;--- render edge 0  A->B  (x={AX}+gE, y={AY})  keyed c:<=0 = catch-all for the -1 default ---
(defrule
\t(up-compare-goal gCorner c:<= 0)
\t=>
\t(up-modify-goal vecSquare_x c:= {AX})
\t(up-modify-goal vecSquare_x g:+ gE)
\t(up-modify-goal vecSquare_y c:= {AY})
)
;--- render edge 1  B->D  (x={BX}, y={BY}+gE) ---
(defrule
\t(up-compare-goal gCorner c:== 1)
\t=>
\t(up-modify-goal vecSquare_x c:= {BX})
\t(up-modify-goal vecSquare_y c:= {BY})
\t(up-modify-goal vecSquare_y g:+ gE)
)
;--- render edge 2  D->C  (x={DX}-gE, y={DY}) ---
(defrule
\t(up-compare-goal gCorner c:== 2)
\t=>
\t(up-modify-goal vecSquare_x c:= {DX})
\t(up-modify-goal vecSquare_x g:- gE)
\t(up-modify-goal vecSquare_y c:= {DY})
)
;--- render edge 3  C->A  (x={CX}, y={CY}-gE) ---
(defrule
\t(up-compare-goal gCorner c:== 3)
\t=>
\t(up-modify-goal vecSquare_x c:= {CX})
\t(up-modify-goal vecSquare_y c:= {CY})
\t(up-modify-goal vecSquare_y g:- gE)
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
;--- end of edge (gE >= {LEG}): reset gE, advance to next edge clockwise ---
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
print(f"wrote {DST}: {text.count('(defrule')} defrules (expect 133), CLOCKWISE A->B->D->C, NL={NL!r}")

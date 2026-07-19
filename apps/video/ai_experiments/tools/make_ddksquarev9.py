"""Generate ddkSquareV9.per = ddkSquareV8 (pivot-alternate A->B->A->C) + a FIND PROBE.

Diagnostic only: identical movement to V8, plus a rule that every 2s reports how many
ranged units the finder sees (found=%d) and whether the ball is tagged (tag=%d).  This
pins down why the tag isn't sticking:
  found=0        -> the finder isn't seeing your army (wrong player slot, or the unit
                    type isn't in the find list: archery / cav-archer / hand-cannoneer /
                    conquistador classes + gbeto / throwing-axeman / mameluke / ballista-eleph).
  found>0, tag 0->1 -> tagging works; then the xy targets should flow.

Validation: validate_variant.py ddkModelAI.per ddkSquareV9.per 44,45,46,56,57,65 9
"""
import io

MAP_TILES = 16
INSET     = 5
STEP      = 150
ARRIVE    = 350

LO   = INSET * 100
HI   = (MAP_TILES - INSET) * 100
LEG  = HI - LO

SRC = r"apps\video\ai_experiments\ddkModelAI.per"
DST = r"apps\video\ai_experiments\ddkSquareV9.per"

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
    "; ddkSquareV9 = ddkSquareV8 (pivot A->B->A->C) + FIND PROBE (found/tag every 2s)\n"
    ";   to diagnose why the tag is not sticking.  Movement identical to V8.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

rep("(defconst gDiagE 200)",
    "(defconst gDiagE 200)\n"
    "(defconst vecSquare 202)\n(defconst vecSquare_x 202)\n(defconst vecSquare_y 203)\n"
    "(defconst gPos 204)\n(defconst gDir 205)\n(defconst gLeg 206)\n"
    "(defconst gDistToTgt 207)\n"
    "(defconst gLastX 208)\n(defconst gLastY 209)\n(defconst gPacked 210)\n"
    "(defconst gInit 211)\n(defconst gDbgT 212)")

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

APPENDIX = f""";=== ddkSquareV9 = V8 pivot-alternate + FIND PROBE.  goals 202-212. ===

;--- one-time seed: gDir outbound (+{STEP}); gLeg/gPos default to 0 (start A->B) ---
(defrule
\t(up-compare-goal gInit c:!= 1)
\t=>
\t(up-modify-goal gInit c:= 1)
\t(up-modify-goal gDir c:= {STEP})
)
;--- PROBE: every 2s report ranged units the finder sees + tag state ---
(defrule
\t(up-modify-goal gTmpA g:= gTimeMilli)
\t(up-modify-goal gTmpA g:- gDbgT)
\t(up-compare-goal gTmpA c:>= 2000)
\t=>
\t(up-modify-goal gDbgT g:= gTimeMilli)
\t(up-full-reset-search)
\t(up-find-local c: class-archery c: 240)
\t(up-find-local c: class-cavalry-archer c: 240)
\t(up-find-local c: class-hand-cannoneer c: 240)
\t(up-find-local c: class-conquistador c: 240)
\t(up-find-local c: ballista-elephant c: 240)
\t(up-find-local c: elite-ballista-elephant c: 240)
\t(up-find-local c: gbeto c: 240)
\t(up-find-local c: elite-gbeto c: 240)
\t(up-find-local c: throwing-axeman c: 240)
\t(up-find-local c: elite-throwing-axeman c: 240)
\t(up-find-local c: mameluke c: 240)
\t(up-find-local c: elite-mameluke c: 240)
\t(up-get-search-state vecSS)
\t(up-chat-data-to-player 1 "found=%d" g: vecSS_L)
\t(up-chat-data-to-player 1 "tag=%d" g: gTagged)
\t(up-full-reset-search)
)
;--- vecSquare := current leg point.  leg 0 (bottom): ({LO}+gPos, {LO}) ---
(defrule
\t(up-compare-goal gLeg c:== 0)
\t=>
\t(up-modify-goal vecSquare_x c:= {LO})
\t(up-modify-goal vecSquare_x g:+ gPos)
\t(up-modify-goal vecSquare_y c:= {LO})
)
;--- leg 1 (left): ({LO}, {LO}+gPos) ---
(defrule
\t(up-compare-goal gLeg c:== 1)
\t=>
\t(up-modify-goal vecSquare_x c:= {LO})
\t(up-modify-goal vecSquare_y c:= {LO})
\t(up-modify-goal vecSquare_y g:+ gPos)
)
;--- distance from the ball to the current target ---
(defrule
\t(true)
\t=>
\t(up-get-point-distance vecMed vecSquare gDistToTgt)
)
;--- march: step gPos by gDir while KITE-moving AND the ball reached the target ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gState c:== 18)
\t(up-compare-goal gDistToTgt c:< {ARRIVE})
\t=>
\t(up-modify-goal gPos g:+ gDir)
)
;--- at far corner (outbound): clamp + reverse back toward A ---
(defrule
\t(up-compare-goal gPos c:>= {LEG})
\t(up-compare-goal gDir c:> 0)
\t=>
\t(up-modify-goal gPos c:= {LEG})
\t(up-modify-goal gDir c:= -{STEP})
)
;--- back at pivot A (inbound): clamp, go outbound, TOGGLE leg (0<->1 via 1-gLeg) ---
(defrule
\t(up-compare-goal gPos c:<= 0)
\t(up-compare-goal gDir c:< 0)
\t=>
\t(up-modify-goal gPos c:= 0)
\t(up-modify-goal gDir c:= {STEP})
\t(up-modify-goal gLeg c:* -1)
\t(up-modify-goal gLeg c:+ 1)
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
)"""

appendix = APPENDIX.replace("\n", NL) if NL == "\r\n" else APPENDIX
text = text.rstrip("\r\n") + NL + appendix + NL
n_rules = text.count("(defrule")
io.open(DST, "w", encoding="utf-8", newline="").write(text)
print(f"wrote {DST}: {len(text)} chars, {n_rules} defrules (expect 131), NL={NL!r}")

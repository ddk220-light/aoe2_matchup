"""ddkImmortalCoreI = CoreG + ranged-vs-ranged stutter-strafe (backlog item 2).

CoreG holds VOLLEY permanently when not out-ranging (gKiteOK==0) = a plain stand-and-shoot
fight. CoreI keeps the volley as the fight but, between volleys (most units past their
fire window, not yet reloaded), takes a SHORT LATERAL hop with an ALTERNATING strafe side
("STRAFE" chat) -- the human move: dodge incoming arrows left/right without losing DPS.
While not out-ranging: step 180% (short hops, vs 350-420 kite steps) and dwell 400ms
(snap back to the volley as soon as reloaded + in range). The radial servo still anchors
the ball at max range, so hops are lateral-dominant by construction.
Rules 0-77 untouched except Rule 0 banner.
"""
import io

SRC = r"apps\video\ai_experiments\ddkImmortalCoreG.per"
DST = r"apps\video\ai_experiments\ddkImmortalCoreI.per"
text = io.open(SRC, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in text else "\n"

def rep(old, new):
    global text
    assert text.count(old) == 1, f"anchor x{text.count(old)}: {old[:60]!r}"
    text = text.replace(old, new)

rep("; CoreG = CoreF + per-unit kiting character; ALL VALUES FROM the repo DB",
    "; CoreI = CoreG + RANGED-vs-RANGED STUTTER-STRAFE (when not out-ranging, hop a short\n"
    ";   alternating lateral step between volleys: step 180%, dwell 400ms; chats STRAFE).\n"
    "; CoreG = CoreF + per-unit kiting character; ALL VALUES FROM the repo DB")

rep("\t(chat-to-player 1 \"ImmortalCoreG up\")",
    "\t(chat-to-player 1 \"ImmortalCoreI up\")")

APPENDIX = """
;=== CoreI RvR STUTTER-STRAFE APPENDIX (runs last; state flips apply next pass) ===
;--- I1: between volleys vs an equal/longer-range enemy, hop laterally -- Rule 44's
;    own release gates (most units past the fire window, not yet reloaded) + 700ms in
;    state so a volley always lands first. Alternating sign = the left/right weave.
;    Rules 44/45 stay gKiteOK-gated, so this is the ONLY 22->18 path when not out-ranging. ---
(defrule
\t(up-compare-goal gState c:== 22)
\t(up-compare-goal gKiteOK c:== 0)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gPctFired c:< 45)
\t(up-compare-goal gPctReady c:< 60)
\t(up-compare-goal gStateAge c:>= 700)
\t=>
\t(up-modify-goal gState c:= 18)
\t(up-modify-goal gStateT g:= gTimeMilli)
\t(up-modify-goal gStateAge c:= 0)
\t(up-modify-goal gStrafeSign c:* -1)
\t(chat-to-player 1 "STRAFE")
)
;--- I2: while not out-ranging, keep the hops SHORT and the return SNAPPY.
;    Runs after the speed-tier and dwell rules -> overrides them. ---
(defrule
\t(up-compare-goal gKiteOK c:== 0)
\t=>
\t(up-modify-goal gStepPct c:= 180)
\t(up-modify-goal gDwell c:= 400)
)
"""
appendix = APPENDIX.replace("\n", NL) if NL == "\r\n" else APPENDIX
text = text.rstrip("\r\n") + NL + appendix
io.open(DST, "w", encoding="utf-8", newline="").write(text)
print(f"wrote {DST}: {text.count('(defrule')} defrules")

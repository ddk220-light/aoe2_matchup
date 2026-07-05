"""ddkImmortalCoreH = CoreG + obstacle & map-edge handling (backlog item 1).

At end of each pass, PROBE the kite order point that was just issued (vecKite, precise):
blocked if its tile contains a tree(915)/wall(927)/gate(939), is path-unreachable
(up-path-distance strict == 65535), or the bounded point collapsed onto the ball
(pinned against map edge/corner). Blocked -> flip gStrafeSign (2.5s cooldown, chats
"FLIP") and for 1.6s boost lateral evasion (strafe 320 / step 300%). One-pass lag by
design; rules 0-77 untouched except Rule 0 inits + banner.

up-point-contains / up-path-distance take a TILE point in our usage -> vecProbe = vecKite/100.
(If FLIP never chats in-game when balls hit walls, try passing vecKite directly — the
point-unit convention is the one unverified bit; see BACKLOG.md.)
"""
import io

SRC = r"apps\video\ai_experiments\ddkImmortalCoreG.per"
DST = r"apps\video\ai_experiments\ddkImmortalCoreH.per"
text = io.open(SRC, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in text else "\n"

def rep(old, new):
    global text
    assert text.count(old) == 1, f"anchor x{text.count(old)}: {old[:60]!r}"
    text = text.replace(old, new)

rep("; CoreG = CoreF + per-unit kiting character; ALL VALUES FROM the repo DB",
    "; CoreH = CoreG + OBSTACLE & MAP-EDGE HANDLING (appendix probe of the issued kite\n"
    ";   point: point-contains tree/wall/gate, path-distance unreachable, pinned-on-edge\n"
    ";   -> strafe-sign flip w/ 2.5s cooldown + 1.6s lateral evade boost; chats FLIP).\n"
    "; CoreG = CoreF + per-unit kiting character; ALL VALUES FROM the repo DB")

rep("(defconst gStepPct 196)",
    "(defconst gStepPct 196)\n"
    "(defconst gFlipT 197)\n"
    "(defconst gBlocked 198)\n"
    "(defconst vecProbe 200)\n"
    "(defconst vecProbe_x 200)\n"
    "(defconst vecProbe_y 201)")

rep("\t(up-modify-goal gStepPct c:= 390)\n\t(chat-to-player 1 \"ImmortalCoreG up\")",
    "\t(up-modify-goal gStepPct c:= 390)\n"
    "\t(up-modify-goal gFlipT c:= -9999)\n"
    "\t(up-modify-goal gBlocked c:= 0)\n"
    "\t(chat-to-player 1 \"ImmortalCoreH up\")")

APPENDIX = """
;=== CoreH OBSTACLE/EDGE APPENDIX (runs last; probes the order issued THIS pass,
;    corrects the direction for the NEXT pass) ===
;--- H0: reset + tile-ize the probe point (vecKite is PRECISE = tile*100) ---
(defrule
\t(true)
\t=>
\t(up-modify-goal gBlocked c:= 0)
\t(up-modify-goal vecProbe_x g:= vecKite_x)
\t(up-modify-goal vecProbe_x c:/ 100)
\t(up-modify-goal vecProbe_y g:= vecKite_y)
\t(up-modify-goal vecProbe_y c:/ 100)
\t(up-get-point-distance vecMed vecKite gTmpA)
)
;--- H1: kite point tile blocked by tree/wall/gate, or unreachable ---
(defrule
\t(up-compare-goal gState c:== 18)
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(or (up-point-contains vecProbe c: 915)
\t(or (up-point-contains vecProbe c: 927)
\t(or (up-point-contains vecProbe c: 939)
\t\t(up-path-distance vecProbe 1 == 65535))))
\t=>
\t(up-modify-goal gBlocked c:= 1)
)
;--- H2: pinned -- the bounded order point collapsed onto the ball (map edge/corner);
;    radial retreat is exhausted, only a direction change gets us out ---
(defrule
\t(up-compare-goal gState c:== 18)
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gTmpA c:< 120)
\t=>
\t(up-modify-goal gBlocked c:= 1)
)
;--- H3: THE FLIP (2.5s cooldown so we don't oscillate against a long wall) ---
(defrule
\t(up-compare-goal gBlocked c:== 1)
\t(up-modify-goal gTmpB g:= gTimeMilli)
\t(up-modify-goal gTmpB g:- gFlipT)
\t(up-compare-goal gTmpB c:>= 2500)
\t=>
\t(up-modify-goal gStrafeSign c:* -1)
\t(up-modify-goal gFlipT g:= gTimeMilli)
\t(chat-to-player 1 "FLIP")
)
;--- H4: for 1.6s after a flip, go LATERAL (big strafe, short radial step) so the
;    ball slides along the obstacle/edge instead of pushing into it.
;    Runs AFTER the speed-tier rules -> overrides them while active. ---
(defrule
\t(up-modify-goal gTmpB g:= gTimeMilli)
\t(up-modify-goal gTmpB g:- gFlipT)
\t(up-compare-goal gTmpB c:< 1600)
\t=>
\t(up-modify-goal gStrafeBase c:= 320)
\t(up-modify-goal gStepPct c:= 300)
)
"""
appendix = APPENDIX.replace("\n", NL) if NL == "\r\n" else APPENDIX
text = text.rstrip("\r\n") + NL + appendix
io.open(DST, "w", encoding="utf-8", newline="").write(text)
print(f"wrote {DST}: {text.count('(defrule')} defrules")

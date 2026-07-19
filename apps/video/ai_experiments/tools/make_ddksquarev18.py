"""Generate ddkSquareV18.per = ddkSquareV7 EXACTLY + the P/E/D/N probe (nothing else).

Purpose: instrument the version the user remembers working (V7: arrival-gated A<->B
oscillation on the bottom edge) so a rerun of THE SAME scenario shows, from the save:
  * where the units actually are (triangulate from D vs the known target position),
  * whether gS (=E) advances -- i.e. whether V7's arrival gate ever opens here,
  * P/state and N as before.
Then we compare V7's real numbers to V17's and see what genuinely differs.

Movement is byte-identical to V7 (sxy render, STEP=150, arrival gate D<350, reverse-at-A/B,
goal layout 202-209).  The ONLY addition is the probe (goals 210-212) + xy log kept.
Validation: validate_variant.py ddkModelAI.per ddkSquareV18.per 44,45,46,56,57,65 10
"""
import io

MAP_TILES = 16
INSET     = 5
STEP      = 150
ARRIVE    = 350
PROBE_MS  = 1000

LO   = INSET * 100
HI   = (MAP_TILES - INSET) * 100
SIDE = HI - LO

AMIN = 0          # corner A = (500,500)
AMAX = SIDE       # corner B = (1100,500)

SRC = r"apps\video\ai_experiments\ddkModelAI.per"
DST = r"apps\video\ai_experiments\ddkSquareV18.per"

text = io.open(SRC, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in text else "\n"


def rep(old, new, n=1):
    global text
    old = old.replace("\n", NL)
    new = new.replace("\n", NL)
    c = text.count(old)
    assert c == n, f"anchor matched {c}x (want {n}): {old[:70]!r}"
    text = text.replace(old, new)


def sxy(inp, ox, oy):
    return f"""(defrule
\t(up-compare-goal {inp} c:< {SIDE})
\t=>
\t(up-modify-goal {ox} c:= {LO})
\t(up-modify-goal {ox} g:+ {inp})
\t(up-modify-goal {oy} c:= {LO})
)
(defrule
\t(up-compare-goal {inp} c:>= {SIDE})
\t(up-compare-goal {inp} c:< {2 * SIDE})
\t=>
\t(up-modify-goal {ox} c:= {HI})
\t(up-modify-goal gTmpA g:= {inp})
\t(up-modify-goal gTmpA c:- {SIDE})
\t(up-modify-goal {oy} c:= {LO})
\t(up-modify-goal {oy} g:+ gTmpA)
)
(defrule
\t(up-compare-goal {inp} c:>= {2 * SIDE})
\t(up-compare-goal {inp} c:< {3 * SIDE})
\t=>
\t(up-modify-goal {oy} c:= {HI})
\t(up-modify-goal gTmpA g:= {inp})
\t(up-modify-goal gTmpA c:- {2 * SIDE})
\t(up-modify-goal {ox} c:= {HI})
\t(up-modify-goal {ox} g:- gTmpA)
)
(defrule
\t(up-compare-goal {inp} c:>= {3 * SIDE})
\t=>
\t(up-modify-goal {ox} c:= {LO})
\t(up-modify-goal gTmpA g:= {inp})
\t(up-modify-goal gTmpA c:- {3 * SIDE})
\t(up-modify-goal {oy} c:= {HI})
\t(up-modify-goal {oy} g:- gTmpA)
)"""


rep("; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +",
    f"; ddkSquareV18 = ddkSquareV7 (arrival-gated A<->B oscillation, arc {AMIN}..{AMAX}) + P/E/D/N probe.\n"
    ";   Movement byte-identical to V7; probe added to record how it really behaves in this scenario.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

# ---- goals: V7's 202-209 + probe 210-212 ----
rep("(defconst gDiagE 200)",
    "(defconst gDiagE 200)\n"
    "(defconst vecSquare 202)\n(defconst vecSquare_x 202)\n(defconst vecSquare_y 203)\n"
    "(defconst gS 204)\n(defconst gDistToTgt 205)\n"
    "(defconst gLastX 206)\n(defconst gLastY 207)\n(defconst gPacked 208)\n"
    "(defconst gDir 209)\n"
    "(defconst gDbgT 210)\n(defconst gProbe 211)\n(defconst gDbgTmp 212)")

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

ap = []
ap.append(f""";=== ddkSquareV18 = V7 oscillation (arc {AMIN}..{AMAX}) + probe.  goals 202-212. ===

;--- vecSquare := loop(gS)  (gS defaults 0 = corner A) ---""")
ap.append(sxy("gS", "vecSquare_x", "vecSquare_y"))
ap.append(f""";--- distance from the ball to the current target ---
(defrule
\t(true)
\t=>
\t(up-get-point-distance vecMed vecSquare gDistToTgt)
)
;--- march: V7 arrival-gated step (D<{ARRIVE}) ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gState c:== 18)
\t(up-compare-goal gDistToTgt c:< {ARRIVE})
\t=>
\t(up-modify-goal gS g:+ gDir)
)
;--- reverse at corner B ---
(defrule
\t(up-compare-goal gS c:>= {AMAX})
\t=>
\t(up-modify-goal gS c:= {AMAX})
\t(up-modify-goal gDir c:= -{STEP})
)
;--- reverse at corner A (also seeds gDir=+{STEP}) ---
(defrule
\t(up-compare-goal gS c:<= {AMIN})
\t=>
\t(up-modify-goal gS c:= {AMIN})
\t(up-modify-goal gDir c:= {STEP})
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
)
;--- PROBE every {PROBE_MS}ms: P=gTagged*100+gState ; E=gS ; D=gDistToTgt ; N=gECount ---
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
\t(up-chat-data-to-player 1 "E=%d" g: gS)
\t(up-chat-data-to-player 1 "D=%d" g: gDistToTgt)
\t(up-chat-data-to-player 1 "N=%d" g: gECount)
)""")

appendix = "\n".join(ap) + "\n"
if NL == "\r\n":
    appendix = appendix.replace("\n", "\r\n")
text = text.rstrip("\r\n") + NL + appendix

io.open(DST, "w", encoding="utf-8", newline="").write(text)
n_rules = text.count("(defrule")
print(f"wrote {DST}: {len(text)} chars, {n_rules} defrules (expect 132), NL={NL!r}")

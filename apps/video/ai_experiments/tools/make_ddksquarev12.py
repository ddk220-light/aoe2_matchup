"""Generate ddkSquareV12.per = ddkSquareV7 with the LEFT edge instead of the bottom edge.

This is V7's generator with TWO numbers changed (AMIN/AMAX = the arc range) and nothing
else.  Same goal numbers, same sxy render, same STEP, same arrival gate, same march rule,
same reverse rules.  V7's own docstring documents this exact knob:

    "To patrol a DIFFERENT edge, change AMIN/AMAX (arc values):
       bottom (500,500)-(1100,500): 0..600   ...   left (500,1100)-(500,500): 1800..2400"

V7 oscillated the BOTTOM edge  A=(500,500) <-> B=(1100,500)  (arc 0..600).
V12 oscillates the LEFT   edge  A=(500,500) <-> C=(500,1100)  (arc 1800..2400).

Start-up: gS defaults 0, so the reverse-at-AMIN rule snaps it to arc 1800 = C on the
first pass -> the very first move order sends the units (spawned near A) straight up to
C.  The arrival gate then holds C until they get there, then the target walks back down
to A, and it oscillates A <-> C forever.  Movement is x=500 fixed, y stepping by STEP
(150) between 500 and 1100 -- i.e. up and down the left edge, exactly like V7 did left-
right along the bottom.

Validation: validate_variant.py ddkModelAI.per ddkSquareV12.per 44,45,46,56,57,65 9
"""
import io

MAP_TILES = 16
INSET     = 5
STEP      = 150
ARRIVE    = 350

LO   = INSET * 100
HI   = (MAP_TILES - INSET) * 100
SIDE = HI - LO

# --- the two corners to oscillate between, as arc values (LEFT edge) ---
AMIN = 3 * SIDE   # corner C = (500,1100)  (arc 1800; the FAR corner, first target)
AMAX = 4 * SIDE   # corner A = (500,500)   (arc 2400; HOME corner)

SRC = r"apps\video\ai_experiments\ddkModelAI.per"
DST = r"apps\video\ai_experiments\ddkSquareV12.per"

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


# ---------- header note ----------
rep("; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +",
    f"; ddkSquareV12 = ddkSquareV7 but on the LEFT edge:  A=({LO},{LO}) <-> C=({LO},{HI}) (arc {AMIN}..{AMAX}).\n"
    ";   Identical to V7 in every way (sxy render, STEP, arrival gate, march, reverse rules,\n"
    ";   goal numbers) -- ONLY the two arc bounds changed from the bottom edge to the left edge.\n"
    ";   First move sends the units up to C; then it oscillates C<->A up and down x=500 forever.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

# ---------- new goals (202-209) -- IDENTICAL to V7 ----------
rep("(defconst gDiagE 200)",
    "(defconst gDiagE 200)\n"
    "(defconst vecSquare 202)\n(defconst vecSquare_x 202)\n(defconst vecSquare_y 203)\n"
    "(defconst gS 204)\n(defconst gDistToTgt 205)\n"
    "(defconst gLastX 206)\n(defconst gLastY 207)\n(defconst gPacked 208)\n"
    "(defconst gDir 209)")

# ---------- strip the FREQUENT base chats ----------
rep('\n\t(chat-to-player 1 "KITE")', "", n=1)
rep('\n\t(chat-to-player 1 "KITE2")', "", n=1)
rep('\n\t(chat-to-player 1 "VOLLEY")', "", n=1)
rep('\n\t(chat-to-player 1 "MOVE-P")', "", n=1)
rep('\n\t(chat-to-player 1 "MOVE-M")', "", n=1)
rep('\n\t(chat-to-player 1 "no targets in range")', "", n=1)

# ---------- Rules 56/57: kite order targets the SQUARE waypoint ----------
rep("(up-target-point vecKite action-patrol formation-line stance-no-attack)",
    "(up-target-point vecSquare action-patrol formation-line stance-no-attack)", n=2)
rep("(up-target-point vecKite action-move formation-line stance-no-attack)",
    "(up-target-point vecSquare action-move formation-line stance-no-attack)", n=2)

# ---------- APPENDIX (9 rules) -- IDENTICAL structure to V7 ----------
ap = []
ap.append(f""";=== ddkSquareV12 TWO-CORNER OSCILLATION on the LEFT edge (A=({LO},{LO}) <-> C=({LO},{HI}),
;    arc {AMIN}..{AMAX}).  gS bounces between AMIN(C) and AMAX(A); never wraps, never snaps.  goals 202-209. ===

;--- vecSquare := loop(gS)  (gS defaults 0 -> snapped to arc {AMIN} = corner C on pass 1) ---""")
ap.append(sxy("gS", "vecSquare_x", "vecSquare_y"))
ap.append(f""";--- distance from the ball to the current target ---
(defrule
\t(true)
\t=>
\t(up-get-point-distance vecMed vecSquare gDistToTgt)
)
;--- march: step by gDir (+/-{STEP}) while KITE-moving AND the ball has reached the
;    current target (within {ARRIVE}).  gDir auto-inits to +{STEP} via the reverse-at-C rule. ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gState c:== 18)
\t(up-compare-goal gDistToTgt c:< {ARRIVE})
\t=>
\t(up-modify-goal gS g:+ gDir)
)
;--- reverse at home corner A (arc {AMAX}): clamp + head back down toward C ---
(defrule
\t(up-compare-goal gS c:>= {AMAX})
\t=>
\t(up-modify-goal gS c:= {AMAX})
\t(up-modify-goal gDir c:= -{STEP})
)
;--- reverse at far corner C (arc {AMIN}): clamp + head back up toward A (also seeds gDir=+{STEP} at start) ---
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
)""")

appendix = "\n".join(ap) + "\n"
if NL == "\r\n":
    appendix = appendix.replace("\n", "\r\n")
text = text.rstrip("\r\n") + NL + appendix

io.open(DST, "w", encoding="utf-8", newline="").write(text)
n_rules = text.count("(defrule")
print(f"wrote {DST}: {len(text)} chars, {n_rules} defrules (expect 131), "
      f"oscillate LEFT edge arc {AMIN}..{AMAX}, NL={NL!r}")

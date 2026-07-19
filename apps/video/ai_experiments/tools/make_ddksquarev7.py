"""Generate ddkSquareV7.per = ddkSquareV6 but OSCILLATE BETWEEN TWO CORNERS instead
of circling the whole square.

WHY: circling all 4 corners keeps rounding a new corner INTO the pursuing melee (the
enemy cuts across the centre to intercept, so "the other corner" ends up in its face).
Instead, patrol ONE edge back and forth between its two corners -- the corners are the
points FARTHEST from centre, so reversing there is the safest place to turn, and the
melee just has to keep chasing left-right along the edge.

BEHAVIOUR:
  * First move -> corner A = (500,500)  (gS = AMIN = 0), farthest from centre.
  * March forward along the bottom edge to corner B = (1100,500) (gS = AMAX = 600).
  * At B reverse; march back to A; at A reverse; repeat.  A <-> B forever.
  * The other two corners (top edge) are never visited.
  * Same arrival gate as V6 (advance only when the ball has reached the current target,
    so it never runs ahead) and NO snapping (gS only steps +/- one, never re-projects).

To patrol a DIFFERENT edge, change AMIN/AMAX (arc values):
  bottom (500,500)-(1100,500): 0..600     right (1100,500)-(1100,1100): 600..1200
  top (1100,1100)-(500,1100): 1200..1800  left (500,1100)-(500,500): 1800..2400
Reverse the start direction by seeding gDir (auto-inits to +STEP at AMIN).

Geometry identical (INSET=5 -> loop [500,1100]).  Chat: only packed "xy=%d" on change.
Validation: validate_variant.py ddkModelAI.per ddkSquareV7.per 44,45,46,56,57,65 9
"""
import io

MAP_TILES = 16
INSET     = 5
STEP      = 150
ARRIVE    = 350

LO   = INSET * 100
HI   = (MAP_TILES - INSET) * 100
SIDE = HI - LO

# --- the two corners to oscillate between, as arc values (bottom edge) ---
AMIN = 0          # corner A = (500,500)
AMAX = SIDE       # corner B = (1100,500)  (= 600)

SRC = r"apps\video\ai_experiments\ddkModelAI.per"
DST = r"apps\video\ai_experiments\ddkSquareV7.per"

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
    f"; ddkSquareV7 = ddkSquareV6 but OSCILLATE between two corners instead of circling.\n"
    f";   Patrols the bottom edge back and forth: A=({LO},{LO}) <-> B=({HI},{LO}) (arc {AMIN}..{AMAX}),\n"
    ";   reversing at each corner (the points farthest from centre).  The other two\n"
    ";   corners are never visited, so it stops rounding a new corner into the melee.\n"
    ";   Arrival-gated, no snapping.  Change AMIN/AMAX to patrol a different edge.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

# ---------- new goals (202-209) ----------
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

# ---------- APPENDIX (9 rules) ----------
ap = []
ap.append(f""";=== ddkSquareV7 TWO-CORNER OSCILLATION ({INSET} from edge; A=({LO},{LO}) <-> B=({HI},{LO}),
;    arc {AMIN}..{AMAX}).  gS bounces between AMIN and AMAX; never wraps, never snaps.  goals 202-209. ===

;--- vecSquare := loop(gS)  (gS defaults to 0 = corner A) ---""")
ap.append(sxy("gS", "vecSquare_x", "vecSquare_y"))
ap.append(f""";--- distance from the ball to the current target ---
(defrule
\t(true)
\t=>
\t(up-get-point-distance vecMed vecSquare gDistToTgt)
)
;--- march: step by gDir (+/-{STEP}) while KITE-moving AND the ball has reached the
;    current target (within {ARRIVE}).  gDir auto-inits to +{STEP} via the reverse-at-A rule. ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gState c:== 18)
\t(up-compare-goal gDistToTgt c:< {ARRIVE})
\t=>
\t(up-modify-goal gS g:+ gDir)
)
;--- reverse at corner B: clamp + head back toward A ---
(defrule
\t(up-compare-goal gS c:>= {AMAX})
\t=>
\t(up-modify-goal gS c:= {AMAX})
\t(up-modify-goal gDir c:= -{STEP})
)
;--- reverse at corner A: clamp + head back toward B (also seeds gDir=+{STEP} at start) ---
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
      f"oscillate arc {AMIN}..{AMAX}, NL={NL!r}")

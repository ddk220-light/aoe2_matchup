"""Generate ddkSquareV13.per = alternate A->B->A->C->A->B... done the RIGHT way.

WHY the earlier alternators (V8/V10/V11) broke, and this one won't:
  Both PROVEN-working versions oscillate ONE variable inside [0,600] and NEVER move it
  any other way -- V7 (bottom edge A<->B) and V12 (left edge A<->C).  The broken
  alternators all had to TELEPORT that variable across arc ranges (V11: 0<->2400) or
  swing it NEGATIVE (V10: -600..+600) to reach the other corner.  That jump is what the
  game choked on (units stuck at home, target barely changing).

  V13 removes the jump entirely.  It splits the state into:
    gE    = distance out from home A, ALWAYS in [0,600], oscillated EXACTLY like V7/V12
            (same march rule, same two reverse rules, never teleports, never negative).
    gAxis = which edge this excursion uses:  0 -> move X (toward B),  1 -> move Y (toward C).
  Render:
    gAxis 0 :  vecSquare = (500 + gE, 500)     <- identical to V7's bottom-edge path
    gAxis 1 :  vecSquare = (500, 500 + gE)     <- identical to V12's left-edge path
  At home gE=0 BOTH render to A=(500,500), so flipping gAxis there is SEAMLESS -- the unit
  is standing at A and the target does not move.  The flip fires exactly once per round
  trip (gated on gDir<0 = "arriving home inbound"; the reverse-home rule immediately sets
  gDir=+150, so it can't re-fire while waiting at home).

  Net: the gAxis=0 leg IS V7, the gAxis=1 leg IS V12, and it alternates A->B->A->C->A->B...

Validation: validate_variant.py ddkModelAI.per ddkSquareV13.per 44,45,46,56,57,65 8
"""
import io

MAP_TILES = 16
INSET     = 5
STEP      = 150
ARRIVE    = 350

LO   = INSET * 100                 # 500  (home corner A coordinate on both axes)
HI   = (MAP_TILES - INSET) * 100   # 1100 (far corner coordinate: B on X, C on Y)
LEG  = HI - LO                     # 600  (excursion length; gE swings [0, LEG])

SRC = r"apps\video\ai_experiments\ddkModelAI.per"
DST = r"apps\video\ai_experiments\ddkSquareV13.per"

text = io.open(SRC, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in text else "\n"


def rep(old, new, n=1):
    global text
    old = old.replace("\n", NL)
    new = new.replace("\n", NL)
    c = text.count(old)
    assert c == n, f"anchor matched {c}x (want {n}): {old[:70]!r}"
    text = text.replace(old, new)


# ---------- header note ----------
rep("; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +",
    f"; ddkSquareV13 = alternate A->B->A->C->A->B ... the safe way.  gE in [0,{LEG}] oscillates EXACTLY\n"
    f";   like V7/V12 (never teleports, never negative); gAxis picks the edge: 0 -> (500+gE,500)=A..B,\n"
    f";   1 -> (500,500+gE)=A..C.  At home gE=0 both render A=({LO},{LO}), so the axis flip there is\n"
    ";   seamless (unit standing still, target doesn't move).  gAxis=0 leg IS V7; gAxis=1 leg IS V12.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

# ---------- new goals (202-210) ----------
rep("(defconst gDiagE 200)",
    "(defconst gDiagE 200)\n"
    "(defconst vecSquare 202)\n(defconst vecSquare_x 202)\n(defconst vecSquare_y 203)\n"
    "(defconst gE 204)\n(defconst gDir 205)\n(defconst gAxis 206)\n"
    "(defconst gDistToTgt 207)\n"
    "(defconst gLastX 208)\n(defconst gLastY 209)\n(defconst gPacked 210)")

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

# ---------- APPENDIX (8 rules) ----------
APPENDIX = f""";=== ddkSquareV13 = seamless A->B->A->C alternation.  gE in [0,{LEG}], gAxis 0/1.  goals 202-210. ===

;--- render, gAxis 0: bottom edge (500+gE, 500)  [A..B] -- identical to V7 ---
(defrule
\t(up-compare-goal gAxis c:== 0)
\t=>
\t(up-modify-goal vecSquare_x c:= {LO})
\t(up-modify-goal vecSquare_x g:+ gE)
\t(up-modify-goal vecSquare_y c:= {LO})
)
;--- render, gAxis 1: left edge (500, 500+gE)  [A..C] -- identical to V12 ---
(defrule
\t(up-compare-goal gAxis c:== 1)
\t=>
\t(up-modify-goal vecSquare_x c:= {LO})
\t(up-modify-goal vecSquare_y c:= {LO})
\t(up-modify-goal vecSquare_y g:+ gE)
)
;--- distance from the ball to the current target (V7/V12, verbatim) ---
(defrule
\t(true)
\t=>
\t(up-get-point-distance vecMed vecSquare gDistToTgt)
)
;--- march: step gE by gDir while KITE-moving AND the ball reached the target
;    (V7/V12 march rule, VERBATIM -- same conditions, same {ARRIVE} gate, same {STEP} via gDir) ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gState c:== 18)
\t(up-compare-goal gDistToTgt c:< {ARRIVE})
\t=>
\t(up-modify-goal gE g:+ gDir)
)
;--- reverse at the far corner (gE >= {LEG}): head back toward home A (V7/V12, verbatim) ---
(defrule
\t(up-compare-goal gE c:>= {LEG})
\t=>
\t(up-modify-goal gE c:= {LEG})
\t(up-modify-goal gDir c:= -{STEP})
)
;--- FLIP the edge, once, on arriving home inbound (gE<=0 AND gDir<0).  gAxis 0<->1 via *-1,+1.
;    reverse-home below sets gDir=+{STEP} the same pass, so this can't re-fire while at home. ---
(defrule
\t(up-compare-goal gE c:<= 0)
\t(up-compare-goal gDir c:< 0)
\t=>
\t(up-modify-goal gAxis c:* -1)
\t(up-modify-goal gAxis c:+ 1)
)
;--- reverse at home A (gE <= 0): clamp + head back out (also seeds gDir=+{STEP} on pass 1).
;    IDENTICAL to V7/V12's reverse-at-home; idempotent. ---
(defrule
\t(up-compare-goal gE c:<= 0)
\t=>
\t(up-modify-goal gE c:= 0)
\t(up-modify-goal gDir c:= {STEP})
)
;--- LOG: one packed message per target change.  packed = x*10000 + y (V7/V12, verbatim) ---
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

io.open(DST, "w", encoding="utf-8", newline="").write(text)
n_rules = text.count("(defrule")
print(f"wrote {DST}: {len(text)} chars, {n_rules} defrules (expect 130), NL={NL!r}")

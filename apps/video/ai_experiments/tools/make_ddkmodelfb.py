"""Generate ddkModelFB.per = ddkModelAI + FEEDBACK-BASED MOVEMENT (Part 4).

A closed-loop KITE watchdog.  ddkModelAI's kite servo is open-loop: it recomputes a
move vector every pass and issues it, never checking whether the ball ACTUALLY went
anywhere.  If a wall / cliff / body-screen of enemy units / a re-tasked stance stops
the move, the servo keeps issuing the same doomed vector forever.  ddkModelFB closes
the loop on the achieved result instead of a predicted cause -- so it catches EVERY
failure mode (terrain CoreH can't enumerate, unit body-blocks point-contains is blind
to, silent order overrides) without naming any of them.

MECHANISM (all in the numbering-free appendix; rules 0-77 are UNTOUCHED -- pure append):
  Each ~1s window of CONTINUOUS kiting (state 18), compare the ball median + the
  distance-to-enemy-median now vs at the window's start:
    * dSelf  = how far the ball median moved this window   (up-get-point-distance)
    * dGap   = change in distance to the enemy median       (+ = gap opening = good)
  Decision table:
    | dSelf >= MOVE & dGap >= 0        -> healthy kite            -> reset stuck counter
    | dSelf >= MOVE & dGap <= -GAP     -> we move but enemy gains -> forced VOLLEY (OUTRUN)
    | dSelf <  MOVE & dGap <  GAP      -> blocked                 -> escalate (see ladder)
  Blocked escalation ladder (gStuckN counts consecutive blocked windows):
    L1 (1) : flip gStrafeSign + 1.6s lateral slide (strafe 320 / step 300%) -- try the
             OTHER way around the obstacle / body screen.
    L2 (>=2): still stuck -> harder tangential (strafe 420 / step 240%) + flip again.
    L3 (>=3): give up escaping -> forced VOLLEY (PENNED) so a cornered ball at least
             stands and focus-fires instead of grinding a wall.  Re-attempts kiting
             after the volley dwell (gStuckN resets on state change).

WHY THIS IS STRONGER THAN CoreH's obstacle probe: CoreH asks "is the point I'm about
to order onto a tree/wall/gate/edge?" (open-loop, must enumerate obstacle types, blind
to enemy bodies and order overrides).  This asks "did the last order actually move us?"
The 2-delta split also yields a free EMPIRICAL SPEED CHECK (OUTRUN): the range-only
gKiteOK gate lets slow archers try to kite a faster melee unit forever; dGap catches
"full speed and still losing ground" and holds VOLLEY instead.

STATE: goals 202-211, ALL 0-default-safe (a goal reads 0 until first written), so NO
Rule-0 init is needed and nothing in 0-77 changes.  Validation:
  validate_variant.py ddkModelAI.per ddkModelFB.per - 10   (0 base rules changed, +10)

TUNABLES (inline literals, mirroring the ddkModelAI appendix style):
  WINDOW   1000 ms  -- eval cadence; keep >= one re-order beat (Rule 48 = 1200/2400ms)
                       so a still-executing order isn't misjudged as failed.
  MOVE       60     -- precise (0.6 tile): median displacement below this = "didn't move".
  GAP        40     -- precise (0.4 tile): deadband for "gap essentially unchanged".
  OUTRUN    -40     -- precise: gap shrank more than this (enemy clearly gaining) -> hold.
  LAT      1600 ms  -- lateral-slide window after a flip (matches CoreH H4).
  L3 count    3     -- consecutive blocked windows before giving up to VOLLEY.

SRC = ddkModelAI.per (run make_ddkmodelai.py first).  Layered on the mainline so it
inherits diplomacy-stance enemy detection + broad ranged recognition + the W_fire table.
"""
import io

SRC = r"apps\video\ai_experiments\ddkModelAI.per"
DST = r"apps\video\ai_experiments\ddkModelFB.per"

text = io.open(SRC, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in text else "\n"


def rep(old, new, n=1):
    global text
    c = text.count(old)
    assert c == n, f"anchor matched {c}x (want {n}): {old[:70]!r}"
    text = text.replace(old, new)


# --- header note (comment only; validator strips comments) ---
rep("; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +",
    "; ddkModelFB = ddkModelAI + FEEDBACK-BASED MOVEMENT (closed-loop kite watchdog):\n"
    ";   every ~1s window in KITE, measure own displacement + change in enemy gap;\n"
    ";   blocked (didn't move, gap not opening) -> flip strafe sign + lateral slide,\n"
    ";   escalating to a forced VOLLEY after 3 stuck windows; moved-but-gap-shrinking\n"
    ";   (enemy outruns us) -> forced VOLLEY.  Pure appendix -- rules 0-77 UNTOUCHED.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

# --- new goals (202-211; all 0-default-safe, no Rule-0 init required) ---
rep("(defconst gDiagE 200)",
    "(defconst gDiagE 200)\n"
    "(defconst vecMedMark 202)\n"
    "(defconst vecMedMark_x 202)\n"
    "(defconst vecMedMark_y 203)\n"
    "(defconst gDistEMark 204)\n"
    "(defconst gMarkT 205)\n"
    "(defconst gStuckN 206)\n"
    "(defconst gMoved 207)\n"
    "(defconst gGapDelta 208)\n"
    "(defconst gLatUntil 209)\n"
    "(defconst gEvalNow 210)\n"
    "(defconst gFbBanner 211)")

APPENDIX = """
;=== ddkModelFB FEEDBACK APPENDIX (rules 78+; runs END of pass, values apply NEXT
;    pass -- one-pass lag by design so rules 0-77 numbering never moves).  A closed
;    loop on the ACHIEVED kite result: did the last window of orders actually move us
;    and open the gap?  See tools/make_ddkmodelfb.py for the full rationale + tunables.
;    goals 202-211 are all 0-default-safe -> no Rule-0 init.  gStrafeSign(137) is
;    already inited +1 by Rule 0. ===

;--- one-time banner so editor Test confirms WHICH file loaded ---
(defrule
\t(up-compare-goal gFbBanner c:!= 1)
\t=>
\t(up-modify-goal gFbBanner c:= 1)
\t(chat-to-player 1 "ddkModelFB feedback up")
)
;--- FB0: clear the once-per-window eval flag every pass ---
(defrule
\t(true)
\t=>
\t(up-modify-goal gEvalNow c:= 0)
)
;--- FB1: RE-ARM the window mark whenever we are NOT in a continuous kite (state != 18)
;    or a transition just happened (gJustChanged == 1).  This establishes the mark on
;    the pass we ENTER kite and keeps it fresh across volleys, so the window only ever
;    measures uninterrupted kiting.  Also zeroes the stuck counter on any state change. ---
(defrule
\t(or (up-compare-goal gState c:!= 18)
\t\t(up-compare-goal gJustChanged c:== 1))
\t=>
\t(up-copy-point vecMedMark vecMed)
\t(up-modify-goal gDistEMark g:= gDistMedE)
\t(up-modify-goal gMarkT g:= gTimeMilli)
\t(up-modify-goal gStuckN c:= 0)
)
;--- FB2: EVAL once the window (>=1000ms) has elapsed while still kiting.  Measure
;    dSelf (median displacement) + dGap (change in enemy distance), latch gEvalNow,
;    then RE-MARK for the next window. ---
(defrule
\t(up-compare-goal gState c:== 18)
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-modify-goal gTmpA g:= gTimeMilli)
\t(up-modify-goal gTmpA g:- gMarkT)
\t(up-compare-goal gTmpA c:>= 1000)
\t=>
\t(up-get-point-distance vecMedMark vecMed gMoved)
\t(up-modify-goal gGapDelta g:= gDistMedE)
\t(up-modify-goal gGapDelta g:- gDistEMark)
\t(up-modify-goal gEvalNow c:= 1)
\t(up-copy-point vecMedMark vecMed)
\t(up-modify-goal gDistEMark g:= gDistMedE)
\t(up-modify-goal gMarkT g:= gTimeMilli)
)
;--- FB3: HEALTHY -- we moved and the gap held or opened -> reset the stuck counter. ---
(defrule
\t(up-compare-goal gEvalNow c:== 1)
\t(up-compare-goal gMoved c:>= 60)
\t(up-compare-goal gGapDelta c:>= 0)
\t=>
\t(up-modify-goal gStuckN c:= 0)
)
;--- FB4: OUTRUN -- we moved at full stride but the gap SHRANK (enemy is faster than
;    us; the range-only kite gate can't see this).  Stop kiting, hold and focus-fire. ---
(defrule
\t(up-compare-goal gEvalNow c:== 1)
\t(up-compare-goal gMoved c:>= 60)
\t(up-compare-goal gGapDelta c:<= -40)
\t=>
\t(up-modify-goal gState c:= 22)
\t(up-modify-goal gStateT g:= gTimeMilli)
\t(up-modify-goal gStateAge c:= 0)
\t(up-modify-goal gJustChanged c:= 1)
\t(up-modify-goal gStuckN c:= 0)
\t(chat-to-player 1 "OUTRUN-HOLD")
)
;--- FB5: BLOCKED -- we did NOT move and the gap did NOT open (wall / cliff / enemy
;    bodies / order override).  Count it, flip the strafe sign, and open a 1.6s lateral
;    slide window so the next orders slide ALONG the obstacle instead of into it. ---
(defrule
\t(up-compare-goal gEvalNow c:== 1)
\t(up-compare-goal gMoved c:< 60)
\t(up-compare-goal gGapDelta c:< 40)
\t=>
\t(up-modify-goal gStuckN c:+ 1)
\t(up-modify-goal gStrafeSign c:* -1)
\t(up-modify-goal gLatUntil g:= gTimeMilli)
\t(up-modify-goal gLatUntil c:+ 1600)
\t(chat-to-player 1 "STUCK-FLIP")
)
;--- FB6: PENNED -- 3 consecutive blocked windows means direction changes aren't
;    getting us out (cornered / fully body-blocked).  Give up escaping and hold VOLLEY
;    so we at least fire; a fresh kite attempt (flipped) follows the volley dwell. ---
(defrule
\t(up-compare-goal gEvalNow c:== 1)
\t(up-compare-goal gStuckN c:>= 3)
\t=>
\t(up-modify-goal gState c:= 22)
\t(up-modify-goal gStateT g:= gTimeMilli)
\t(up-modify-goal gStateAge c:= 0)
\t(up-modify-goal gJustChanged c:= 1)
\t(up-modify-goal gStuckN c:= 0)
\t(chat-to-player 1 "PENNED-HOLD")
)
;--- FB7: LATERAL slide while a direction-change window is active.  Runs AFTER the
;    speed-tier rules earlier in the appendix, so it OVERRIDES gStrafeBase/gStepPct
;    for the next pass (wide strafe, short radial step -> slide sideways). ---
(defrule
\t(up-compare-goal gTimeMilli g:< gLatUntil)
\t=>
\t(up-modify-goal gStrafeBase c:= 320)
\t(up-modify-goal gStepPct c:= 300)
)
;--- FB8: still stuck (>=2 windows) -> push even harder tangential. ---
(defrule
\t(up-compare-goal gTimeMilli g:< gLatUntil)
\t(up-compare-goal gStuckN c:>= 2)
\t=>
\t(up-modify-goal gStrafeBase c:= 420)
\t(up-modify-goal gStepPct c:= 240)
)
"""

appendix = APPENDIX.replace("\n", NL) if NL == "\r\n" else APPENDIX
text = text.rstrip("\r\n") + NL + appendix
io.open(DST, "w", encoding="utf-8", newline="").write(text)
n_rules = text.count("(defrule")
print(f"wrote {DST}: {len(text)} chars, {n_rules} defrules (expect 132), NL={NL!r}")

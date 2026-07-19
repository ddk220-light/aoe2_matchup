"""Generate ddkModelFB2.per = ddkModelAI + FEEDBACK-BASED MOVEMENT v2 (verbose logging).

WHY v2 (v1 "still got stuck"): v1's watchdog only evaluated after 1000ms of CONTINUOUS
state-18 (KITE).  But the state machine flips KITE(18) <-> VOLLEY(22) every ~600ms
(the dwell) plus on %-ready/%-fired conditions -- so on a CORNERED ball (which is in
range and keeps flipping to VOLLEY to fire) the 1000ms continuous-18 window almost
never completed, FB2 never fired, and STUCK-FLIP never triggered.  The ball just sat.

v2 FIXES:
  1. ENGAGEMENT-SPANNING WINDOW.  The mark is NO LONGER reset on KITE/VOLLEY flips.
     It resets only when we are not actively trying to create distance -- i.e. NOT
     (tagged AND size>=1 AND enemies>=1 AND gKiteOK==1).  So the window measures net
     progress across whole kite/volley cycles.  A window >= one full cycle avoids the
     "volley pause looks stuck" false-positive; WINDOW=1800ms spans a typical cycle.
  2. gKiteOK GATE.  Only look for "stuck" when the AI WANTS to open the gap
     (out-ranging).  Ranged-vs-ranged holds VOLLEY by design -> not stuck.
  3. VERBOSE NUMERIC LOGGING via up-chat-data-to-player (proven in "AI (HD version)").
     Every window prints the measured move + gap; every stuck detection prints the new
     direction + escalation level; a 2s heartbeat prints state / kiteOK / stuck level.
     All to player 1 (visible in editor Test, unlike chat-to-all / up-chat-data-to-all).

DECISION each window (dSelf = median displacement, dGap = change in enemy distance):
  | dSelf >= MOVE & dGap >  -OUT   -> HEALTHY  -> reset stuck        (chat "FB OK moving")
  | dSelf >= MOVE & dGap <= -OUT   -> OUTRUN   -> forced VOLLEY      (chat "FB OUTRUN hold")
  | dSelf <  MOVE & dGap <   GAP   -> BLOCKED  -> flip + lateral     (chat "FB STUCK newdir")
  BLOCKED escalates on gStuckN: L1 flip+slide(320/300), L2 harder(420/240), L3(>=3) forced VOLLEY.

TUNABLES (inline literals; the logs let you calibrate these from real numbers):
  WINDOW  1800 ms  MOVE 60 (0.6 tile)  GAP 50 (0.5 tile)  OUTRUN 50 (gap shrink >0.5t)
  LAT 1600 ms lateral window   HB 2000 ms heartbeat   L3 = 3 blocked windows

STATE: goals 202-212, all 0-default-safe -> rules 0-77 UNTOUCHED (pure append).
Validation: validate_variant.py ddkModelAI.per ddkModelFB2.per - 11   (0 changed, +11)
Fresh filename (not FB) because the game caches parses by filename per session.
SRC = ddkModelAI.per (run make_ddkmodelai.py first).
"""
import io

SRC = r"apps\video\ai_experiments\ddkModelAI.per"
DST = r"apps\video\ai_experiments\ddkModelFB2.per"

text = io.open(SRC, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in text else "\n"


def rep(old, new, n=1):
    global text
    c = text.count(old)
    assert c == n, f"anchor matched {c}x (want {n}): {old[:70]!r}"
    text = text.replace(old, new)


# --- header note (comment only; validator strips comments) ---
rep("; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +",
    "; ddkModelFB2 = ddkModelAI + FEEDBACK-BASED MOVEMENT v2 (engagement-spanning stuck\n"
    ";   watchdog + verbose numeric logging).  v1 only evaluated after 1s of CONTINUOUS\n"
    ";   KITE, but the ball flips KITE<->VOLLEY every ~600ms, so a cornered ball never\n"
    ";   completed a window and never flipped.  v2 measures net progress across whole\n"
    ";   kite/volley cycles (mark reset only on disengagement), gated on gKiteOK, and\n"
    ";   logs move/gap/dir/level + a 2s heartbeat to player 1.  Pure appendix (0-77 kept).\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +")

# --- new goals (202-212; all 0-default-safe, no Rule-0 init required) ---
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
    "(defconst gFbBanner 211)\n"
    "(defconst gHbT 212)")

APPENDIX = """
;=== ddkModelFB2 FEEDBACK+LOG APPENDIX (rules 78+; runs END of pass, values apply NEXT
;    pass).  Engagement-spanning closed loop on the ACHIEVED kite result + verbose
;    telemetry to player 1.  See tools/make_ddkmodelfb2.py for rationale + tunables.
;    goals 202-212 are all 0-default-safe -> no Rule-0 init.  gStrafeSign(137) is
;    already inited +1 by Rule 0. ===

;--- one-time banner so editor Test confirms WHICH file loaded ---
(defrule
\t(up-compare-goal gFbBanner c:!= 1)
\t=>
\t(up-modify-goal gFbBanner c:= 1)
\t(chat-to-player 1 "ddkModelFB2 up")
)
;--- HEARTBEAT: every 2s while engaged, print state / kiteOK / stuck level so we can
;    see WHY the watchdog is or isn't firing (e.g. kiteOK=0 means it isn't kiting). ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-modify-goal gTmpA g:= gTimeMilli)
\t(up-modify-goal gTmpA g:- gHbT)
\t(up-compare-goal gTmpA c:>= 2000)
\t=>
\t(up-modify-goal gHbT g:= gTimeMilli)
\t(up-chat-data-to-player 1 "FB hb state=%d" g: gState)
\t(up-chat-data-to-player 1 "FB hb kiteOK=%d" g: gKiteOK)
\t(up-chat-data-to-player 1 "FB hb stuck=%d" g: gStuckN)
)
;--- FB0: clear the once-per-window eval flag every pass ---
(defrule
\t(true)
\t=>
\t(up-modify-goal gEvalNow c:= 0)
)
;--- FB1: RE-ARM the window mark whenever we are NOT actively trying to open the gap:
;    NOT (tagged AND size>=1 AND enemies>=1 AND gKiteOK==1).  Crucially this does NOT
;    reset on KITE<->VOLLEY flips, so the window spans whole cycles (the v1 bug fix). ---
(defrule
\t(or (up-compare-goal gTagged c:!= 1)
\t(or (up-compare-goal gSize c:< 1)
\t(or (up-compare-goal gECount c:< 1)
\t\t(up-compare-goal gKiteOK c:!= 1))))
\t=>
\t(up-copy-point vecMedMark vecMed)
\t(up-modify-goal gDistEMark g:= gDistMedE)
\t(up-modify-goal gMarkT g:= gTimeMilli)
\t(up-modify-goal gStuckN c:= 0)
)
;--- FB2: EVAL once the window (>=1800ms) has elapsed while actively kiting.  Measure
;    dSelf (median displacement) + dGap (change in enemy distance), LOG both, latch
;    gEvalNow, then re-mark for the next window. ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gKiteOK c:== 1)
\t(up-modify-goal gTmpA g:= gTimeMilli)
\t(up-modify-goal gTmpA g:- gMarkT)
\t(up-compare-goal gTmpA c:>= 1800)
\t=>
\t(up-get-point-distance vecMedMark vecMed gMoved)
\t(up-modify-goal gGapDelta g:= gDistMedE)
\t(up-modify-goal gGapDelta g:- gDistEMark)
\t(up-modify-goal gEvalNow c:= 1)
\t(up-chat-data-to-player 1 "FB win move=%d" g: gMoved)
\t(up-chat-data-to-player 1 "FB win gap=%d" g: gGapDelta)
\t(up-copy-point vecMedMark vecMed)
\t(up-modify-goal gDistEMark g:= gDistMedE)
\t(up-modify-goal gMarkT g:= gTimeMilli)
)
;--- FB3: HEALTHY -- we moved and the gap held (dGap > -50) -> reset stuck. ---
(defrule
\t(up-compare-goal gEvalNow c:== 1)
\t(up-compare-goal gMoved c:>= 60)
\t(up-compare-goal gGapDelta c:> -50)
\t=>
\t(up-modify-goal gStuckN c:= 0)
\t(chat-to-player 1 "FB OK moving")
)
;--- FB4: OUTRUN -- we moved but the gap SHRANK (enemy faster than us; the range-only
;    kite gate can't see this).  Stop kiting, hold and focus-fire. ---
(defrule
\t(up-compare-goal gEvalNow c:== 1)
\t(up-compare-goal gMoved c:>= 60)
\t(up-compare-goal gGapDelta c:<= -50)
\t=>
\t(up-modify-goal gState c:= 22)
\t(up-modify-goal gStateT g:= gTimeMilli)
\t(up-modify-goal gStateAge c:= 0)
\t(up-modify-goal gJustChanged c:= 1)
\t(up-modify-goal gStuckN c:= 0)
\t(chat-to-player 1 "FB OUTRUN hold")
)
;--- FB5: BLOCKED -- did NOT move and the gap did NOT open.  THIS is the "kite failed,
;    pick a new direction" case: count it, flip the strafe sign, open a 1.6s lateral
;    slide window, and LOG the new direction + escalation level. ---
(defrule
\t(up-compare-goal gEvalNow c:== 1)
\t(up-compare-goal gMoved c:< 60)
\t(up-compare-goal gGapDelta c:< 50)
\t=>
\t(up-modify-goal gStuckN c:+ 1)
\t(up-modify-goal gStrafeSign c:* -1)
\t(up-modify-goal gLatUntil g:= gTimeMilli)
\t(up-modify-goal gLatUntil c:+ 1600)
\t(chat-to-player 1 "FB STUCK no-move newdir")
\t(up-chat-data-to-player 1 "FB newdir sign=%d" g: gStrafeSign)
\t(up-chat-data-to-player 1 "FB stuck level=%d" g: gStuckN)
)
;--- FB6: PENNED -- 3 consecutive blocked windows -> direction changes aren't getting us
;    out.  Give up escaping and hold VOLLEY; a fresh (flipped) kite follows the dwell. ---
(defrule
\t(up-compare-goal gEvalNow c:== 1)
\t(up-compare-goal gStuckN c:>= 3)
\t=>
\t(up-modify-goal gState c:= 22)
\t(up-modify-goal gStateT g:= gTimeMilli)
\t(up-modify-goal gStateAge c:= 0)
\t(up-modify-goal gJustChanged c:= 1)
\t(up-modify-goal gStuckN c:= 0)
\t(chat-to-player 1 "FB PENNED hold")
)
;--- FB7: LATERAL slide while a direction-change window is active.  Runs AFTER the
;    speed-tier rules earlier in the appendix -> overrides gStrafeBase/gStepPct next
;    pass (wide strafe, short radial step -> slide sideways along the obstacle). ---
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
print(f"wrote {DST}: {len(text)} chars, {n_rules} defrules (expect 133), NL={NL!r}")

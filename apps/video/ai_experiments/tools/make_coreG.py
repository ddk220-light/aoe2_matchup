"""Generate ddkImmortalCoreG.per = CoreF + per-unit parameterization appendix.

Surgical edits (load-bearing rules 0-77, whitelisted):
  Rule 0  -- init 5 new goals, banner text F->G
  Rule 44 -- +fact gKiteOK==1  (kite only when out-ranging)
  Rule 45 -- +fact gKiteOK==1
  Rule 46 -- 600ms dwell literal -> g:>= gDwell (reload-scaled)
  Rule 49 -- strafe 200 literal -> g:= gStrafeBase (speed-tiered)
  Rule 54 -- step 390 literal   -> g:= gStepPct   (speed-tiered)
Appendix rules 85+ (nothing jumps there; numbering-free).

W_fire = final_attack_delay(ms) + 60 release margin, from data/golden/aoe2_reference.db.
Unit ids from AoE2ScenarioParser datasets (same source the arena builders use).
"""
import io, sys

SRC = r"apps\video\ai_experiments\ddkImmortalCoreF.per"
DST = r"apps\video\ai_experiments\ddkImmortalCoreG.per"

text = io.open(SRC, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in text else "\n"

def rep(old, new):
    global text
    n = text.count(old)
    assert n == 1, f"anchor matched {n}x (want 1): {old[:70]!r}"
    text = text.replace(old, new)

# --- header ---
rep("; RULE NUMBERING IS LOAD-BEARING: up-jump-direct targets are absolute defrule\n"
    "; indices (0-based). This file must contain EXACTLY these 78 defrules in this\n"
    "; order. Never insert/delete a rule without renumbering every jump.",
    "; RULE NUMBERING IS LOAD-BEARING: up-jump-direct targets are absolute defrule\n"
    "; indices (0-based). Rules 0-77 are jump-target-exact; rules 78+ (diagnostics +\n"
    "; the CoreG parameterization appendix) are numbering-free -- nothing jumps there.\n"
    ";\n"
    "; CoreG = CoreF + per-unit kiting character; ALL VALUES FROM the repo DB\n"
    "; data/golden/aoe2_reference.db (current patch, 2026-07-02):\n"
    ";   * W_fire = final_attack_delay(ms) + 60ms release margin, keyed on the ball's\n"
    ";     median ACTUAL type (obj1), class fallback. Same mechanism as Immortal\n"
    ";     #1600-1605, but Immortal's values are stale AoC-era delays (CA 1000 vs\n"
    ";     DE's 583+60) -- the DB supplies current-patch truth per unit.\n"
    ";   * kite dwell = clamp(liveReload - 1400, 400, 2200): mangudai (1428ms) snaps\n"
    ";     back to volleys in 400ms; hand cannoneers (3450ms) commit 2s arcs.\n"
    ";   * kite ONLY when out-ranging (gRange > gERange+1); equal/out-ranged ranged\n"
    ";     fights hold VOLLEY = stand-and-focus-fire (normal fight).\n"
    ";   * strafe/step speed-tiered: >=1.35 tiles/s wide arcs, <=1.15 short hops.")

# --- new defconsts ---
rep("(defconst object_data-unique-id 0)",
    "(defconst object_data-unique-id 0)\n(defconst object_data-object-id 1)")
rep("(defconst gDiag7 189)",
    "(defconst gDiag7 189)\n"
    "(defconst gDwell 190)\n"
    "(defconst gKiteOK 191)\n"
    "(defconst gWset 192)\n"
    "(defconst gUType 193)\n"
    "(defconst gUClass 194)\n"
    "(defconst gStrafeBase 195)\n"
    "(defconst gStepPct 196)")

# --- Rule 0: init new goals (23 -> 28 elements, cap 32) ---
rep("\t(up-modify-goal gDiag7 c:= 0)\n\t(chat-to-player 1 \"ImmortalCoreF up\")",
    "\t(up-modify-goal gDiag7 c:= 0)\n"
    "\t(up-modify-goal gDwell c:= 600)\n"
    "\t(up-modify-goal gKiteOK c:= 1)\n"
    "\t(up-modify-goal gWset c:= 0)\n"
    "\t(up-modify-goal gStrafeBase c:= 200)\n"
    "\t(up-modify-goal gStepPct c:= 390)\n"
    "\t(chat-to-player 1 \"ImmortalCoreG up\")")

# --- Rule 44/45: kite only when out-ranging ---
rep("\t\t(up-compare-goal gStateAge c:>= 3000))\n\t(up-compare-goal gState c:== 22)",
    "\t\t(up-compare-goal gStateAge c:>= 3000))\n"
    "\t(up-compare-goal gKiteOK c:== 1)\n"
    "\t(up-compare-goal gState c:== 22)")
rep("\t(up-compare-goal gDistClosE c:< 250)\n\t(up-compare-goal gState c:== 22)",
    "\t(up-compare-goal gDistClosE c:< 250)\n"
    "\t(up-compare-goal gKiteOK c:== 1)\n"
    "\t(up-compare-goal gState c:== 22)")

# --- Rule 46: reload-scaled dwell ---
rep("\t(up-compare-goal gStateAge c:>= 600)",
    "\t(up-compare-goal gStateAge g:>= gDwell)")

# --- Rule 49: speed-tiered strafe ---
rep("\t(up-modify-goal gStrafeMag c:= 200)",
    "\t(up-modify-goal gStrafeMag g:= gStrafeBase)")

# --- Rule 54: speed-tiered step ---
rep("\t(up-modify-goal gKiteLen c:= 390)",
    "\t(up-modify-goal gKiteLen g:= gStepPct)")

# ============ APPENDIX ============
# (wfire_ms, [dat ids], comment) -- wfire = DB final_attack_delay(ms) + 60
ROWS = [
    (60,  [46, 557],                 "Janissary/Elite (delay 0)"),
    (227, [8, 530, 1968, 1970],      "Longbowman/Elite (167), Fire Archer/Elite (167)"),
    (260, [1800, 1802, 1010, 1012],  "Composite Bowman/Elite (200), Genitour/Elite (200)"),
    (277, [771, 773],                "Conquistador/Elite (217)"),
    (293, [185, 1911, 1759, 1761],   "Slinger (233), Grenadier (233), Ratha ranged/Elite (233)"),
    (310, [4, 24, 763, 765, 866, 868, 2579, 2581],
          "Archer (250), Crossbowman (250), Plumed/Elite (250), Genoese Xbow/Elite (250), Blackwood/Elite (250)"),
    (310, [1007, 1009, 5, 1126, 1128],
          "Camel Archer/Elite (250), Hand Cannoneer (250), Arambai/Elite (250)"),
    (377, [7, 6, 1155, 73, 559, 2569, 2571],
          "Skirmisher/Elite/Imperial (317), Chu Ko Nu/Elite (317), Bolas Rider/Elite (317)"),
    (393, [492],                     "Arbalester (333)"),
    (410, [1231, 1233],              "Kipchak/Elite (350)"),
    (443, [11, 561, 1129, 1131],     "Mangudai/Elite (383), Rattan Archer/Elite (383)"),
    (460, [873, 875],                "Elephant Archer/Elite (400)"),
    (477, [2562, 2564],              "Guecha Warrior/Elite (417)"),
    (593, [827, 829],                "War Wagon/Elite (533)"),
    (643, [39, 1952],                "Cavalry Archer (583), Xianbei Raider (583)"),
    (827, [474],                     "Heavy Cavalry Archer (767)"),
]
CLASS_DEFAULTS = [
    ("class-archery",        310, "modal foot-archer delay 250 + 60"),
    ("class-cavalry-archer", 643, "CA row"),
    ("class-hand-cannoneer", 310, "HC delay 250 + 60"),
    ("class-conquistador",   277, "conquistador delay 217 + 60"),
]

def or_chain(ids):
    terms = [f"(up-compare-goal gUType c:== {i})" for i in ids]
    expr = terms[0]
    for t in terms[1:]:
        expr = f"(or {expr}\n\t\t{t})"
    return expr

ap = []
ap.append("""
;=== CoreG PARAMETERIZATION APPENDIX (rules 85+; runs END of pass, values apply
;    NEXT pass -- one-pass lag is by design so rules 0-77 numbering never moves).
;    Every constant here is from data/golden/aoe2_reference.db (see header). ===

;--- reload-scaled kite dwell (plan item 2): clamp(liveReload - 1400, 400, 2200).
;    Live obj54 auto-reflects in-game techs; CA 2000ms -> 600 (= CoreF's floor). ---
(defrule
\t(true)
\t=>
\t(up-modify-goal gDwell g:= gReload)
\t(up-modify-goal gDwell c:- 1400)
\t(up-modify-goal gDwell c:max 400)
\t(up-modify-goal gDwell c:min 2200)
)
;--- speed-tiered strafe/step (plan item 4; gSpeed = min ball speed x100, live,
;    so un-teched scenario balls tier by their REAL speed) ---
(defrule
\t(true)
\t=>
\t(up-modify-goal gStrafeBase c:= 200)
\t(up-modify-goal gStepPct c:= 390)
)
(defrule
\t(up-compare-goal gSpeed c:>= 135)
\t=>
\t(up-modify-goal gStrafeBase c:= 240)
\t(up-modify-goal gStepPct c:= 420)
)
(defrule
\t(up-compare-goal gSpeed c:<= 115)
\t=>
\t(up-modify-goal gStrafeBase c:= 150)
\t(up-modify-goal gStepPct c:= 350)
)
;--- kite gate (plan item 3): kite ONLY when we out-range the enemy median
;    (gERange is read raw in Rule 36 -- melee reads 0). Otherwise Rules 44/45
;    never fire and the ball holds VOLLEY = a normal stand-and-shoot fight. ---
(defrule
\t(true)
\t=>
\t(up-modify-goal gKiteOK c:= 0)
)
(defrule
\t(up-modify-goal gTmpA g:= gERange)
\t(up-modify-goal gTmpA c:+ 1)
\t(up-compare-goal gRange g:> gTmpA)
\t=>
\t(up-modify-goal gKiteOK c:= 1)
)
;--- failsafe: not-out-ranging ball stuck in state 18 (approach) flips to VOLLEY
;    after 2.5s even if Rule 46's in-range gate never fills ---
(defrule
\t(up-compare-goal gState c:== 18)
\t(up-compare-goal gKiteOK c:== 0)
\t(up-compare-goal gECount c:>= 1)
\t(up-compare-goal gStateAge c:>= 2500)
\t=>
\t(up-modify-goal gState c:= 22)
\t(up-modify-goal gStateT g:= gTimeMilli)
\t(up-modify-goal gStateAge c:= 0)
\t(up-modify-goal gJustChanged c:= 1)
\t(chat-to-player 1 "HOLD")
)
;--- melee fallback: no ranged ball ever formed (pure-melee army) -> restore the
;    engine's auto-fight AFTER Rule 76 zeroed it, so melee-vs-melee is normal ---
(defrule
\t(up-compare-goal gTagged c:== 0)
\t(up-compare-goal gTimeMilli c:>= 10000)
\t=>
\t(up-modify-sn sn-percent-enemy-sighted-response c:= 100)
\t(up-modify-sn sn-enemy-sighted-response-distance c:= 20)
\t(up-modify-sn sn-task-ungrouped-soldiers c:= 1)
)
;--- W_FIRE DETECT (plan item 1; Immortal #1572-1578's modal base-type reduced to
;    median ACTUAL type: obj1 = the PLACED unit id, so unresearched scenario
;    elites resolve exactly; arena balls are homogeneous). Latched once. ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gWset c:== 0)
\t=>
\t(up-full-reset-search)
\t(up-find-local c: class-archery c: 240)
\t(up-find-local c: class-cavalry-archer c: 240)
\t(up-find-local c: class-hand-cannoneer c: 240)
\t(up-find-local c: class-conquistador c: 240)
\t(up-remove-objects search-local object_data-tag c:!= 1)
\t(up-clean-search search-local object_data-object-id search_order-ascending)
\t(up-get-search-state vecSS)
\t(up-modify-goal gTmpA g:= vecSS_L)
\t(up-modify-goal gTmpA c:- 1)
\t(up-modify-goal gTmpA c:/ 2)
\t(up-set-target-object search-local g: gTmpA)
\t(up-get-object-data object_data-object-id gUType)
\t(up-get-object-data object_data-class-id gUClass)
\t(up-modify-goal gWset c:= 1)
)
;--- class fallbacks first (unlisted/future types), exact type rows after (later
;    rules overwrite within the same pass) ---""")

for cls, w, why in CLASS_DEFAULTS:
    ap.append(f"""(defrule
\t(up-compare-goal gWset c:== 1)
\t(up-compare-goal gUClass c:== {cls})
\t=>
\t(up-modify-goal gWfire c:= {w})
)""")

ap.append(";--- THE W_FIRE TABLE -- aoe2_reference.db final_attack_delay(ms) + 60 ---")
for w, ids, comment in ROWS:
    ap.append(f""";--- {w}: {comment} ---
(defrule
\t(up-compare-goal gWset c:== 1)
\t{or_chain(ids)}
\t=>
\t(up-modify-goal gWfire c:= {w})
)""")

ap.append("""(defrule
\t(up-compare-goal gWset c:== 1)
\t=>
\t(up-modify-goal gWset c:= 2)
\t(chat-to-player 1 "WFIRE SET")
)""")

appendix = "\n".join(ap) + "\n"
if NL == "\r\n":
    appendix = appendix.replace("\n", "\r\n")
text = text.rstrip("\r\n") + NL + appendix

io.open(DST, "w", encoding="utf-8", newline="").write(text)
n_rules = text.count("(defrule")
print(f"wrote {DST}: {len(text)} chars, {n_rules} defrules (expect 115), NL={NL!r}")

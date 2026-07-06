"""Generate ddkModelAI.per = CoreF + per-unit parameterization + broad ranged
recognition + robust dynamic-enemy detection.  (Renamed from ddkImmortalCoreG,
2026-07-05: "don't call it code g anymore -- the DDK model AI".)

SRC = the proven ddkImmortalCoreF.per baseline (rules 0-77 jump-numbered, 78+ free).

Surgical edits to load-bearing rules 0-77 (whitelisted):
  Rule 0  -- init new goals, banner CoreF -> ddkModelAI
  Rule 6  -- clustering find: +8 ranged unit-type finds (melee-class throwers)
  Rule 12 -- SM find: same +8 finds
  Rule 32 -- enemy-scan focus c:= 3 -> g:= gEnemyPly (dynamic enemy)
  Rule 44 -- +fact gKiteOK==1  (kite only when out-ranging)
  Rule 45 -- +fact gKiteOK==1
  Rule 46 -- 600ms dwell literal -> g:>= gDwell  (reload-scaled)
  Rule 49 -- strafe 200 literal  -> g:= gStrafeBase (speed-tiered)
  Rule 54 -- step 390 literal    -> g:= gStepPct   (speed-tiered)
  Rule 76 -- steady-state sn-target-player c:= 3 -> g:= gEnemyPly
Appendix rules 78+ (nothing jumps there; numbering-free).

RANGED = any unit that shoots projectiles continuously at range (archers, cav
archers, HC, conquistador/arambai, ballista elephant, AND the throwers that live
in melee-inclusive classes: gbeto/throwing-axeman = Infantry, mameluke = Cavalry).
Those four are added by unit TYPE (base+elite) because their CLASS also holds pure
melee units.  One-shot charge units (e.g. Fire Lancer) are NOT ranged -- excluded
by never adding their class/line.

W_fire = final_attack_delay(ms) + 60 release margin, from data/golden/aoe2_reference.db.
"""
import io

SRC = r"apps\video\ai_experiments\ddkImmortalCoreF.per"
DST = r"apps\video\ai_experiments\ddkModelAI.per"

text = io.open(SRC, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in text else "\n"

def rep(old, new, n=1):
    global text
    c = text.count(old)
    assert c == n, f"anchor matched {c}x (want {n}): {old[:70]!r}"
    text = text.replace(old, new)

# ---- broadened ranged find block (rule 6, rule 12, and the W_fire detect) ----
FIND_OLD = ("\t(up-find-local c: class-archery c: 240)\n"
            "\t(up-find-local c: class-cavalry-archer c: 240)\n"
            "\t(up-find-local c: class-hand-cannoneer c: 240)\n"
            "\t(up-find-local c: class-conquistador c: 240)")
FIND_NEW = FIND_OLD + (
    "\n\t(up-find-local c: ballista-elephant c: 240)\n"
    "\t(up-find-local c: elite-ballista-elephant c: 240)\n"
    "\t(up-find-local c: gbeto c: 240)\n"
    "\t(up-find-local c: elite-gbeto c: 240)\n"
    "\t(up-find-local c: throwing-axeman c: 240)\n"
    "\t(up-find-local c: elite-throwing-axeman c: 240)\n"
    "\t(up-find-local c: mameluke c: 240)\n"
    "\t(up-find-local c: elite-mameluke c: 240)")

# --- header ---
rep("; RULE NUMBERING IS LOAD-BEARING: up-jump-direct targets are absolute defrule\n"
    "; indices (0-based). This file must contain EXACTLY these 78 defrules in this\n"
    "; order. Never insert/delete a rule without renumbering every jump.",
    "; RULE NUMBERING IS LOAD-BEARING: up-jump-direct targets are absolute defrule\n"
    "; indices (0-based). Rules 0-77 are jump-target-exact; rules 78+ (diagnostics +\n"
    "; the ddkModelAI parameterization appendix) are numbering-free -- nothing jumps there.\n"
    ";\n"
    "; ddkModelAI = CoreF + per-unit kiting character + broad ranged recognition +\n"
    "; robust dynamic-enemy detection.  Values from data/golden/aoe2_reference.db:\n"
    ";   * W_fire = final_attack_delay(ms) + 60ms release margin, keyed on the ball's\n"
    ";     median ACTUAL type (obj1), class fallback.\n"
    ";   * kite dwell = clamp(liveReload - 1400, 400, 2200).\n"
    ";   * kite ONLY when out-ranging (gRange > gERange+1); else hold VOLLEY.\n"
    ";   * strafe/step speed-tiered.\n"
    ";   * RANGED = continuous projectile shooter: the 4 ranged classes PLUS the\n"
    ";     melee-class throwers (gbeto/throwing-axeman/mameluke) and ballista elephant,\n"
    ";     added by unit type. Charge one-shots (Fire Lancer) are NOT ranged.")

# --- new defconsts (object-id read + the melee-class ranged unit types) ---
rep("(defconst object_data-unique-id 0)",
    "(defconst object_data-unique-id 0)\n(defconst object_data-object-id 1)\n"
    "(defconst ballista-elephant 1120)\n(defconst elite-ballista-elephant 1122)\n"
    "(defconst gbeto 1013)\n(defconst elite-gbeto 1015)\n"
    "(defconst throwing-axeman 281)\n(defconst elite-throwing-axeman 531)\n"
    "(defconst mameluke 282)\n(defconst elite-mameluke 556)")
rep("(defconst gDiag7 189)",
    "(defconst gDiag7 189)\n"
    "(defconst gDwell 190)\n"
    "(defconst gKiteOK 191)\n"
    "(defconst gWset 192)\n"
    "(defconst gUType 193)\n"
    "(defconst gUClass 194)\n"
    "(defconst gStrafeBase 195)\n"
    "(defconst gStepPct 196)\n"
    "(defconst gEnemyPly 197)\n"
    "(defconst gScan2 198)\n"
    "(defconst gScan3 199)\n"
    "(defconst gDiagE 200)")

# --- broaden the two in-pass find blocks (rule 6 clustering, rule 12 SM) ---
rep(FIND_OLD, FIND_NEW, n=2)

# --- Rule 0: init new goals + banner ---
rep("\t(up-modify-goal gDiag7 c:= 0)\n\t(chat-to-player 1 \"ImmortalCoreF up\")",
    "\t(up-modify-goal gDiag7 c:= 0)\n"
    "\t(up-modify-goal gDwell c:= 600)\n"
    "\t(up-modify-goal gKiteOK c:= 1)\n"
    "\t(up-modify-goal gWset c:= 0)\n"
    "\t(up-modify-goal gStrafeBase c:= 200)\n"
    "\t(up-modify-goal gStepPct c:= 390)\n"
    "\t(up-modify-goal gEnemyPly c:= 3)\n"
    "\t(chat-to-player 1 \"ddkModelAI up\")")

# --- Rule 32: enemy scan focuses the DYNAMIC enemy player ---
rep("\t(up-modify-sn sn-focus-player-number c:= 3)",
    "\t(up-modify-sn sn-focus-player-number g:= gEnemyPly)")
# --- Rule 76: steady-state engine override targets the same dynamic enemy ---
rep("\t(up-modify-sn sn-target-player c:= 3)",
    "\t(up-modify-sn sn-target-player g:= gEnemyPly)")

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
    (260, [282, 556, 1120, 1122],    "Mameluke/Elite (200), Ballista Elephant/Elite (200)"),
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
    (527, [281, 531],                "Throwing Axeman/Elite (467)"),
    (560, [1013, 1015],              "Gbeto/Elite (500)"),
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
;=== ddkModelAI PARAMETERIZATION APPENDIX (rules 78+; runs END of pass, values
;    apply NEXT pass -- one-pass lag by design so rules 0-77 numbering never moves).
;    Every constant here is from data/golden/aoe2_reference.db (see header). ===

;--- reload-scaled kite dwell: clamp(liveReload - 1400, 400, 2200). ---
(defrule
\t(true)
\t=>
\t(up-modify-goal gDwell g:= gReload)
\t(up-modify-goal gDwell c:- 1400)
\t(up-modify-goal gDwell c:max 400)
\t(up-modify-goal gDwell c:min 2200)
)
;--- speed-tiered strafe/step (gSpeed = min ball speed x100, live) ---
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
;--- kite gate: kite ONLY when we out-range the enemy median. ---
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
;--- failsafe: not-out-ranging ball stuck in state 18 flips to VOLLEY after 2.5s ---
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
;--- W_FIRE DETECT: read the ball's median ACTUAL type (obj1) after finding all
;    ranged units (classes + melee-class throwers). Latched once. ---
(defrule
\t(up-compare-goal gTagged c:== 1)
\t(up-compare-goal gSize c:>= 1)
\t(up-compare-goal gWset c:== 0)
\t=>
\t(up-full-reset-search)
""" + FIND_NEW + """
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
)
;=== DYNAMIC ENEMY PLAYER (2026-07-05 v2 -- self-excluding remote scan) ==========
;   BUG this fixes: assigned to P3, the AI hunted its own units (old hardcoded 3 /
;   the unverified up-find-player) -> all units slid to one spot and never fired.
;   up-find-remote can NEVER return the AI's OWN units, so whichever candidate
;   player returns military when focused is the ENEMY; the self player returns 0.
;   Uses ONLY primitives proven in Rule 32 (focus + find-remote + get-search-state).
;   Scans P2 then P3 (the only military slots in these arenas); prefers P2 so an
;   AI on P3 locks P2, an AI on P2 (P2=self=0) falls through to P3. One-pass lag.
(defrule
\t(true)
\t=>
\t(up-modify-sn sn-focus-player-number c:= 2)
\t(up-reset-search _false _false _true _true)
\t(up-reset-filters)
\t(up-find-remote c: -1 c: 40)
\t(up-get-search-state vecSS)
\t(up-modify-goal gScan2 g:= vecSS_R)
)
(defrule
\t(true)
\t=>
\t(up-modify-sn sn-focus-player-number c:= 3)
\t(up-reset-search _false _false _true _true)
\t(up-reset-filters)
\t(up-find-remote c: -1 c: 40)
\t(up-get-search-state vecSS)
\t(up-modify-goal gScan3 g:= vecSS_R)
)
(defrule
\t(up-compare-goal gScan2 c:>= 1)
\t=>
\t(up-modify-goal gEnemyPly c:= 2)
)
(defrule
\t(up-compare-goal gScan2 c:== 0)
\t(up-compare-goal gScan3 c:>= 1)
\t=>
\t(up-modify-goal gEnemyPly c:= 3)
)
(defrule
\t(up-compare-goal gEnemyPly c:== 2)
\t(up-compare-goal gDiagE c:!= 2)
\t=>
\t(up-modify-goal gDiagE c:= 2)
\t(chat-to-player 1 "ENEMY = P2")
)
(defrule
\t(up-compare-goal gEnemyPly c:== 3)
\t(up-compare-goal gDiagE c:!= 3)
\t=>
\t(up-modify-goal gDiagE c:= 3)
\t(chat-to-player 1 "ENEMY = P3")
)""")

appendix = "\n".join(ap) + "\n"
if NL == "\r\n":
    appendix = appendix.replace("\n", "\r\n")
text = text.rstrip("\r\n") + NL + appendix

io.open(DST, "w", encoding="utf-8", newline="").write(text)
n_rules = text.count("(defrule")
print(f"wrote {DST}: {len(text)} chars, {n_rules} defrules (expect 124), NL={NL!r}")

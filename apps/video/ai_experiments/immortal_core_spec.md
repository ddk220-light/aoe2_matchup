VERIFICATION COMPLETE — all five load-bearing quote sets re-read from the target file. Results, then the assembled spec.

# PART 1 — VERIFICATION OF THE FIVE LOAD-BEARING QUOTES

**1. Grouping/tag commands — VERIFIED EXACT.**
- Tag-write trio @27722-27724: `(up-create-group 0 0 c: 1)` / `(up-modify-group-flag _true c: 1)` / `(up-reset-group c: 1)` — exact, reset immediately after flag.
- Groups 8/9 snapshot @27469-27471: `(up-create-group 0 0 c: 8)` / `(up-remove-objects search-local object_data-index c:< 40)` / `(up-create-group 0 0 c: 9)` — exact.
- CA clustering dispatch #8757 @104816-104822: find cavalry-archer 240, remove tag==8, remove tag==9, clean by tag ascending, jump — exact.
- Volley scratch groups @42102 (group 0), @42120 (group 1), @42219 (group 2): created via `up-create-group 0 0`, never flagged, never reset — exact. Bail rule #1116 @27473-27477 (`boolvar751==1` OR `up-group-size c: 8 c:== 0`) — exact.

**2. Volley pass command list — VERIFIED EXACT @42098-42364**, with two transcript clarifications:
- **#2775 @42222-42231 (correction of rendering, not conclusion):** the condition is var142 != ALL SEVEN of {actionid-convert, -repair, -hunt, -gather, -build, -heal, -attack} → `var3127 c:= 160`. With var142=600 (attack) the condition fails so var3127 stays 115 — Transcript B's conclusion stood but its rendering implied a direct ==600 test.
- **#2760 @42103** is `(up-reset-search _true _true _false _false)` (clears LOCAL, keeps REMOTE) — matches transcript's "1 1 0 0".
- #2779 @42268: `(up-remove-objects search-local object_data-index g:< var3129)` ✓; arrows math @42269-42279 = `max(var111−PA,0)+var3125, max 1` then `HP/dmg clamp[0,17]+1 min varTmp4835` ✓. #2788 @42333-42336 `vec41_F g:< varTmp4845 → varTmp4840 c:+ 99` ✓. **#2790 @42350-42356 verbatim confirmed:** `(up-set-target-object search-remote g: var3128)` / `(up-remove-objects search-local object_data-index g:>= varTmp4840)` / `(up-remove-objects search-local object_data-target-unique-id g:== varTmp4836)` / `(up-target-objects _true action-default formation-ignore stance-ignore)`. #2791 @42358-42364: `var3129 g:+ varTmp4840; var3128 c:+ 1; get-search-state; var3128 g:mod vec41_S; jump 2778` ✓.

**3. 22→18 flip — VERIFIED EXACT @41538-41550.** Condition `(or (and var117<45 (or (and var118<75, var146>55) var118<60)) var123>=3000) && var93==22`; actions exactly the 5-line tail `var122:=3, var93:=18, var94 g:= timeMilli, var123:=0, boolvar232 c:+ 512`. #2706 @41552-41563 and #2707 @41565-41579 (including the duplicated `var93 c:== 18` at 41572-41573 and `var118 c:>= 91`) — exact as transcribed.

**4. Time idiom — VERIFIED EXACT @49196-49210:** `(up-set-timer c: 1 c: 0)` / `(up-get-timer c: 1 varTmp1)` / `timeMilli g:= varTmp1` / centi / sec / `msecPerLoop = timeMilli − ptimeMilli`. End-of-script #9735 @115895-115900: `loopCounter c:+ 1`, `ptimeMilli g:= timeMilli` ✓. Throttle #2736 @41874-41886 verbatim ✓ (mods on var123, `nor` structure, `g:< msecPerLoop`).

**5. Kite orders #2757/#2758 — VERIFIED EXACT @42068-42092.** Both are the double-issue wrapped in `(up-modify-sn sn-target-point-adjustment c:= 6)` → order → `c:= 5`, twice back-to-back. #2757: `(up-target-point vec229 action-patrol formation-line stance-no-attack)` gated on var143!=1, var138>=4, sn71<=65, var150>=200, var3124∈[−150,150]. #2758: `(true)` → same with `action-move`.

Also re-verified: init SN block #8659/#8660 @103187-103232 (all 39 sn writes exact as Transcript A); end-of-pass override #9732 @115863-115878 (`sn-target-player s:= 339`, sighted-response 0/0, disable-cap 1) ✓; setupStateMachine #1562-#1565 @31345-31378 ✓; getData: var109/110/111 @31483-31502 (speed asc idx 0, range/attack asc median), var112 @31514-31517 (reload desc idx 0), W_fire CA row #1603 @31720-31726 (=1000), var116=var112−var113−10 @31745-31750, var117 loop @31755-31780 (count next-attack > var116), var2765 110/45 @31811-31819, var118 loop @31821-31853 (count next-attack <= var2765), vec225 median @31528-31550 (per-axis sort + middle index) ✓; SM unpack/repack #8763/#8766 @104873-104987 ✓.

**Minor corrections to Transcript B (kite math, verified @41887-42066):**
- B20/#2748 @41986-41991: halving var3122 additionally requires `var154 c:< 2000` (open field var154≈10000 → skipped for that reason too).
- B19/#2747 @41976-41984: the `c:max 50` floor is in the condition side; skirmishers additionally get `c:max 150` in the action.
- B22/#2752 @42014-42026: both lerps target vec2552; second lerp factor = `−40 %* varTmp4797` ✓; #2756 @42057-42066 multiplies BOTH components by varTmp4825 before dividing both by the vecZero-distance, then `(up-bound-precise-point vec229 _true c: 100)` ✓.

---

# PART 2 — ddkImmortalCore v1 (single CA ball, tag 1, enemy = player 3)

Transcribe 1:1. Rule ids = defrule order starting at 0; this file must contain ONLY these defrules so `up-jump-direct c: N` targets are the numbers shown. `up-jump-rule -1` re-runs the current rule (Immortal's own loop idiom, verified @42115). All builtin names (`search-local`, `object_data-*`, `action-*`, `formation-line`=2, `stance-no-attack`=3, `stance-ignore`=-1, `action-default`=0, `_true`=1, `search_order-ascending`=1/-descending=2) are UP 1.5 builtins. Numbers: `class-cavalry-archer`=936, `cavalry-archer` (line const), `class-all-units`=-1, `object_data-tag`=73, `object_data-next-attack`=55, `object_data-to-precise`=80, `sn-target-point-adjustment`=292.

```
;=== ddkImmortalCore — goal map (all >=100) ===
(defconst gTimeMilli 100)(defconst gPtimeMilli 101)(defconst gMsecPerLoop 102)(defconst gLoopCounter 103)
(defconst gTmpA 104)(defconst gTmpB 105)(defconst gRunOnce 108)
(defconst vecSS 110)(defconst vecSS_L 110)(defconst vecSS_R 112)   ; 110..113 = [loc-tot,loc-last,REM-tot(+2),rem-last]
(defconst gState 115)(defconst gStateT 116)(defconst gStateAge 117)(defconst gSize 118)
(defconst gRange 119)(defconst gAttack 120)(defconst gReload 121)(defconst gWfire 122)(defconst gFireWin 123)
(defconst gPctFired 124)(defconst gPctReady 125)(defconst gReadyWin 126)(defconst gSpeed 127)
(defconst vecMed 128)(defconst vecMed_x 128)(defconst vecMed_y 129)          ; var225 role, PRECISE (tiles*100)
(defconst vecEC 130)(defconst vecEC_x 130)(defconst vecEC_y 131)             ; vec232 role
(defconst vecKite 132)(defconst vecKite_x 132)(defconst vecKite_y 133)       ; vec229 role
(defconst gDistMedE 134)(defconst gDistClosE 135)(defconst gPctInRange 136)  ; var149 / var150 / var128
(defconst gStrafeSign 137)(defconst gStrafeMag 138)(defconst gKiteDist 139)(defconst gKiteDistC 140)
(defconst gJustChanged 141)(defconst gLatch 142)(defconst gECount 143)(defconst gERange 144)
(defconst gEAction 145)(defconst gMedNext 146)(defconst gEnemySync 147)      ; var146 role, fixed 0
(defconst gWinPct 148)                                                        ; var165 role, fixed 100
(defconst vecZero 152)(defconst vecZero_x 152)(defconst vecZero_y 153)       ; vec21 role
(defconst vecRetreat 154)                                                     ; vec2552 role
(defconst vecNearE 156)(defconst vecNearE_x 156)(defconst vecNearE_y 157)    ; vec2Tmp430 role
(defconst vecFarOwn 158)(defconst vecFarOwn_x 158)(defconst vecFarOwn_y 159) ; vec2Tmp550 role
(defconst gI 160)(defconst gCnt 161)(defconst gT55 162)(defconst gUid 163)
(defconst gKiteLen 164)(defconst gNormLen 165)(defconst gMod24 166)(defconst gMod12 167)
(defconst gTgtIdx 168)(defconst gAsgCnt 169)      ; var3128/var3129 — MUST stay consecutive (pair-zeroed)
(defconst gTgtUid 170)(defconst gTgtHP 171)(defconst gTgtPA 172)(defconst gDmg 173)
(defconst gArrows 174)(defconst gArrowCap 175)(defconst gHPFactor 176)(defconst gNeed 177)
(defconst gPruneR 178)(defconst gFarD 179)(defconst gBonus1 180)(defconst gBonus2 181)
```

```
;--- Rule 0 — INIT ONCE (Immortal #3573 @48613-15 + fixed reads we cannot cheaply derive)
(defrule (up-compare-goal gRunOnce c:!= 1) =>
 (up-modify-goal gRunOnce c:= 1)
 (up-modify-goal gLoopCounter c:= 0)
 (up-modify-goal gMsecPerLoop c:= 546)     ; #3573 placeholder
 (up-modify-goal gPtimeMilli c:= -500)     ; #3573 placeholder
 (up-modify-goal gState c:= 0)
 (up-modify-goal gStrafeSign c:= 1)        ; DEVIATION: Immortal flips var96 via terrain probe #2733 (up-can-build-line vs sn113) and tower checks #2735 — we fix +1
 (up-modify-goal gEnemySync c:= 0)         ; DEVIATION: var146 only computed vs ranged enemies (#2630-2666); vs melee it stays 0 anyway
 (up-modify-goal gWinPct c:= 100)          ; DEVIATION: var165 = army-value ratio from the 400ms census #1704-1739 — fixed "winning" => 1200ms kite beat, no x2 retreat
 (up-modify-goal gReadyWin c:= 110)        ; #1617 default; DEVIATION: no 45-tightening (needs var144 enemy volley sync)
 (up-modify-goal gWfire c:= 1000)          ; #1603 cavalry-archer W_fire row
 (up-modify-goal gBonus1 c:= 0)            ; var3125 — #2768-2773 skirm/mameluke table, 0 for CA vs cavalry
 (up-modify-goal gBonus2 c:= 0)            ; var3126
 (up-modify-goal vecZero_x c:= 0)
 (up-modify-goal vecZero_y c:= 0))

;--- Rule 1 — TIME (Immortal #3592 @49196-49210, verbatim idiom)
(defrule (true) =>
 (up-set-timer c: 1 c: 0)
 (up-get-timer c: 1 gTmpA)
 (up-modify-goal gTimeMilli g:= gTmpA)
 (up-modify-goal gTmpA g:= gTimeMilli)
 (up-modify-goal gTmpA g:- gPtimeMilli)
 (up-modify-goal gMsecPerLoop g:= gTmpA))

;--- Rule 2 — SN BLOCK A (Immortal #8659 @103190-103205; split for the 25-element cap)
(defrule (true) =>
 (up-modify-sn sn-percent-enemy-sighted-response c:= 100)
 (up-modify-sn sn-enemy-sighted-response-distance c:= 20)
 (up-modify-sn sn-disable-sighted-response-cap c:= 1)
 (up-modify-sn sn-ignore-attack-group-under-attack c:= 0)
 (up-modify-sn sn-disable-attack-groups c:= 0)
 (up-modify-sn sn-group-form-distance c:= 2)
 (up-modify-sn sn-scaling-frequency c:= 30000)
 (up-modify-sn sn-attack-separation-time-randomness c:= 0)
 (up-modify-sn sn-scale-minimum-attack-group-size c:= 0)
 (up-modify-sn sn-scale-maximum-attack-group-size c:= 0)
 (up-modify-sn sn-attack-group-size-randomness c:= 0)
 (up-modify-sn sn-number-attack-groups c:= 0)
 (up-modify-sn sn-minimum-attack-group-size c:= 1)
 (up-modify-sn sn-maximum-attack-group-size c:= 1)
 (up-modify-sn sn-attack-group-gather-spacing c:= 1)
 (up-modify-sn sn-number-boat-attack-groups c:= 0))
;--- Rule 3 — SN BLOCK B (#8659 remainder @103207-103220)
(defrule (true) =>
 (up-modify-sn sn-minimum-boat-attack-group-size c:= 1)
 (up-modify-sn sn-maximum-boat-attack-group-size c:= 1)
 (up-modify-sn sn-disable-defend-groups c:= 0)
 (up-modify-sn sn-maximum-defend-group-size c:= 1)
 (up-modify-sn sn-number-boat-defend-groups c:= 0)
 (up-modify-sn sn-minimum-boat-defend-group-size c:= 1)
 (up-modify-sn sn-maximum-boat-defend-group-size c:= 1)
 (up-modify-sn sn-special-attack-influence1 c:= 0)
 (up-modify-sn sn-special-attack-influence2 c:= 0)
 (up-modify-sn sn-special-attack-influence3 c:= 0)
 (up-modify-sn sn-disable-tower-priority c:= 1)
 (up-modify-sn sn-do-not-scale-for-difficulty-level c:= 1)
 (up-modify-sn sn-enable-offensive-priority c:= 1)
 (up-modify-sn sn-attack-intelligence c:= 0))
;--- Rule 4 — SN BLOCK C (#8660 @103225-103232, verbatim)
(defrule (true) =>
 (up-modify-sn sn-task-ungrouped-soldiers c:= 0)
 (up-modify-sn sn-gather-defense-units c:= 0)
 (up-modify-sn sn-filter-under-attack c:= 0)
 (up-modify-sn sn-initial-attack-delay c:= 0)
 (up-modify-sn sn-maximum-gaia-attack-response c:= 3)
 (up-modify-sn sn-percent-attack-soldiers c:= 100)
 (up-modify-sn sn-percent-attack-boats c:= 100)
 (up-modify-sn sn-enable-patrol-attack c:= 1))

;=== CLUSTERING (tag lifecycle) — beat-gated ~4040ms ===
;--- Rule 5 — beat gate (#8749 tail @104733-36 + #8750 @104737-45; DEVIATION: census + 2020ms fast path dropped)
(defrule
 (up-modify-goal gTmpA g:= gTimeMilli)
 (up-modify-goal gTmpA c:mod 4040)
 (nand (up-compare-goal gTmpA g:< gMsecPerLoop)
     (up-compare-goal gLoopCounter c:> 0))
 => (up-jump-direct c: 12))
;--- Rule 6 — latch clear + find + strip 8/9 + sort by tag (#8751 @104750 + #8757 @104816-104820, verbatim)
(defrule (true) =>
 (up-modify-goal gLatch c:= 0)
 (up-full-reset-search)
 (up-find-local c: cavalry-archer c: 240)
 (up-remove-objects search-local object_data-tag c:== 8)
 (up-remove-objects search-local object_data-tag c:== 9)
 (up-clean-search search-local object_data-tag search_order-ascending))
;--- Rule 7 — groups 8/9 snapshot (#1115 @27469-71, verbatim; pure save containers, never flagged/reset)
(defrule (true) =>
 (up-create-group 0 0 c: 8)
 (up-remove-objects search-local object_data-index c:< 40)
 (up-create-group 0 0 c: 9))
;--- Rule 8 — bail (#1116 @27473-77, verbatim)
(defrule
 (or (up-compare-goal gLatch c:== 1)
     (up-group-size c: 8 c:== 0))
 => (up-jump-direct c: 12))
;--- Rule 9 — restore 9+8, keep untagged (#1117/#1178 restore idiom @27482-84, @28035)
(defrule (true) =>
 (up-full-reset-search)
 (up-set-group search-local c: 9)
 (up-set-group search-local c: 8)
 (up-remove-objects search-local object_data-tag c:== 1)  ; DEVIATION: Immortal keeps c:== -2 (@28035); removing tag 1 also keeps tag-0 units (flag-_false leftovers)
 (up-get-search-state vecSS))
;--- Rule 10
(defrule (up-compare-goal vecSS_L c:== 0) => (up-jump-direct c: 12))
;--- Rule 11 — THE TAG WRITE (trio verbatim from #1141 @27722-24 / seed #1204-1210 @28214-16; DEVIATION: no 19-tile seed radius / 14-tile adopt radius — one arena ball takes everyone)
(defrule (true) =>
 (up-create-group 0 0 c: 1)
 (up-modify-group-flag _true c: 1)
 (up-reset-group c: 1)
 (up-modify-goal gLatch c:= 1))

;=== STATE MACHINE — every pass ===
;--- Rule 12 — find by CLASS (#2624 @40817-21 + #2626 dedupe @40833)
(defrule (true) =>
 (up-full-reset-search)
 (up-find-local c: class-cavalry-archer c: 240)
 (up-clean-search search-local -1 search_order-none))
;--- Rule 13 — THE TAG FILTER (#1562 @31348-50; var103 fixed 1)
(defrule (true) =>
 (up-remove-objects search-local object_data-tag c:!= 1)
 (up-get-search-state vecSS)
 (up-modify-goal gSize g:= vecSS_L))
;--- Rule 14
(defrule (up-compare-goal gSize c:== 0) => (up-jump-direct c: 76))
;--- Rule 15 — adoption bootstrap (#1564 @31366-73; DEVIATION: boots to 22 — states 2..17 are cut)
(defrule
 (up-compare-goal gState c:== 0)
 =>
 (up-modify-goal gState c:= 22)
 (up-modify-goal gStateT g:= gTimeMilli)
 (up-modify-goal gJustChanged c:= 1))
;--- Rule 16 — flag clear + state age (#1572 @31431-37, verbatim semantics: clear-at-top-of-getData)
(defrule (true) =>
 (up-modify-goal gJustChanged c:= 0)
 (up-modify-goal gTmpA g:= gTimeMilli)
 (up-modify-goal gTmpA g:- gStateT)
 (up-modify-goal gStateAge g:= gTmpA))
;--- Rule 17 — speed(min)/range(median)/attack(median) (#1578 @31483-31502, verbatim idiom)
(defrule (true) =>
 (up-clean-search search-local object_data-speed search_order-ascending)
 (up-set-target-object search-local c: 0)
 (up-get-object-data object_data-speed gSpeed)
 (up-clean-search search-local object_data-range search_order-ascending)
 (up-modify-goal gTmpA g:= gSize)
 (up-modify-goal gTmpA c:- 1)
 (up-modify-goal gTmpA c:/ 2)
 (up-set-target-object search-local g: gTmpA)
 (up-get-object-data object_data-range gRange)
 (up-clean-search search-local object_data-base-attack search_order-ascending)
 (up-set-target-object search-local g: gTmpA)
 (up-get-object-data object_data-base-attack gAttack))
;--- Rule 18 — max reload + fire window (#1579 @31514-17 + #1607 @31745-50; gWfire=1000 = #1603 CA row)
(defrule (true) =>
 (up-clean-search search-local object_data-reload-time search_order-descending)
 (up-set-target-object search-local c: 0)
 (up-get-object-data object_data-reload-time gReload)
 (up-modify-goal gTmpA g:= gReload)
 (up-modify-goal gTmpA g:- gWfire)
 (up-modify-goal gTmpA c:- 10)
 (up-modify-goal gFireWin g:= gTmpA))       ; = reload - 1000 - 10 = 990 for CA
;--- Rule 19 — median next-attack + GROUP MEDIAN POINT (#1581 @31528-31550, verbatim per-axis idiom; vecMed is PRECISE)
(defrule (true) =>
 (up-clean-search search-local object_data-next-attack search_order-ascending)
 (up-modify-goal gTmpA g:= gSize)
 (up-modify-goal gTmpA c:- 1)
 (up-modify-goal gTmpA c:/ 2)
 (up-set-target-object search-local g: gTmpA)
 (up-get-object-data object_data-next-attack gMedNext)
 (up-clean-search search-local object_data-precise-x search_order-ascending)
 (up-set-target-object search-local g: gTmpA)
 (up-get-object-data object_data-precise-x vecMed_x)
 (up-clean-search search-local object_data-precise-y search_order-ascending)
 (up-set-target-object search-local g: gTmpA)
 (up-get-object-data object_data-precise-y vecMed_y))
;--- Rules 20-25 — var117 = % just fired (loop #1608-1612 @31755-31780, verbatim shape)
(defrule (true) =>                                    ; Rule 20
 (up-modify-goal gCnt c:= 0)
 (up-modify-goal gI g:= gSize)
 (up-modify-goal gI c:- 1))
(defrule (up-compare-goal gI c:< 0) => (up-jump-direct c: 25))   ; Rule 21
(defrule (true) =>                                    ; Rule 22 (#1609: target THEN read, every time)
 (up-set-target-object search-local g: gI)
 (up-get-object-data object_data-next-attack gT55))
(defrule (up-compare-goal gT55 g:> gFireWin) => (up-modify-goal gCnt c:+ 1))  ; Rule 23 (#1610)
(defrule (true) => (up-modify-goal gI c:- 1) (up-jump-direct c: 21))          ; Rule 24 (#1611)
(defrule (true) =>                                    ; Rule 25 (#1612)
 (up-modify-goal gCnt c:* 100)
 (up-modify-goal gCnt g:/ gSize)
 (up-modify-goal gPctFired g:= gCnt))
;--- Rules 26-31 — var118 = % ready within 110ms (loop #1618-1623 @31821-31853)
(defrule (true) =>                                    ; Rule 26
 (up-modify-goal gCnt c:= 0)
 (up-modify-goal gI g:= gSize)
 (up-modify-goal gI c:- 1))
(defrule (up-compare-goal gI c:< 0) => (up-jump-direct c: 31))   ; Rule 27
(defrule (true) =>                                    ; Rule 28 (#1620)
 (up-set-target-object search-local g: gI)
 (up-get-object-data object_data-next-attack gT55))
(defrule (up-compare-goal gT55 g:<= gReadyWin) => (up-modify-goal gCnt c:+ 1))  ; Rule 29 (#1621)
(defrule (true) => (up-modify-goal gI c:- 1) (up-jump-direct c: 27))            ; Rule 30 (#1622)
(defrule (true) =>                                    ; Rule 31 (#1623)
 (up-modify-goal gCnt c:* 100)
 (up-modify-goal gCnt g:/ gSize)
 (up-modify-goal gPctReady g:= gCnt))

;=== ENEMY SCAN (Immortal #1898 @34177 group-0 save; #1912-1926 scan+prune; DEVIATION: single find-remote vs P3 replaces the per-player one-at-a-time can-search loop @34322-34397)
;--- Rule 32
(defrule (true) =>
 (up-create-group 0 0 c: 0)                 ; group 0 := own tag group (scratch save, #1898)
 (up-reset-search _false _false _true _true)
 (up-set-precise-target-point vecMed)
 (up-filter-distance c: -1 c: 21)           ; #1898 var2816=21 scan radius
 (up-modify-sn sn-focus-player c:= 3)
 (up-find-remote c: -1 c: 40)
 (up-find-remote c: -1 c: 40))              ; second call in case >40 (find continues)
;--- Rule 33 — prune + reset filters (#1924-26 @34398-34428 reduced: arena has no farms/walls/towers)
(defrule (true) =>
 (up-remove-objects search-remote object_data-category c:== category-building)
 (up-remove-objects search-remote object_data-class-id c:== class-villager)
 (up-reset-filters)
 (up-get-search-state vecSS)
 (up-modify-goal gECount g:= vecSS_R))
;--- Rule 34 — no enemies -> finish (DEVIATION: Immortal transitions to roam/regroup states we cut)
(defrule (up-compare-goal gECount c:== 0) => (up-jump-direct c: 76))
;--- Rule 35 — enemy centroid (DEVIATION: component MEDIAN replaces weighted centroid _fcn #2187-2197 @36586-36688; same idiom Immortal uses for its own median)
(defrule (true) =>
 (up-clean-search search-remote object_data-precise-x search_order-ascending)
 (up-modify-goal gTmpA g:= gECount)
 (up-modify-goal gTmpA c:- 1)
 (up-modify-goal gTmpA c:/ 2)
 (up-set-target-object search-remote g: gTmpA)
 (up-get-object-data object_data-precise-x vecEC_x)
 (up-clean-search search-remote object_data-precise-y search_order-ascending)
 (up-set-target-object search-remote g: gTmpA)
 (up-get-object-data object_data-precise-y vecEC_y))
;--- Rule 36 — nearest enemy + var149 + enemy medians + nearest-first remote order (#2118 @36014-27 idiom, verified form of #2762 @42125-28; #2088/#2092 medians; DEVIATION: replaces target-scoring selection sort #2673-2680 @41233-41325 with plain distance sort)
(defrule (true) =>
 (up-set-precise-target-point vecMed)
 (up-clean-search search-remote object_data-to-precise search_order-ascending)
 (up-set-target-object search-remote c: 0)
 (up-get-object-data object_data-to-precise gDistMedE)
 (up-get-object-data object_data-precise-x vecNearE_x)
 (up-get-object-data object_data-precise-y vecNearE_y)
 (up-clean-search search-remote object_data-range search_order-ascending)
 (up-set-target-object search-remote g: gTmpA)      ; gTmpA still = (gECount-1)/2 from Rule 35
 (up-get-object-data object_data-range gERange)
 (up-clean-search search-remote object_data-action search_order-ascending)
 (up-set-target-object search-remote g: gTmpA)
 (up-get-object-data object_data-action gEAction)
 (up-set-precise-target-point vecMed)
 (up-clean-search search-remote object_data-to-precise search_order-ascending))  ; restore nearest-first for volley
;--- Rules 37-42 — var128 = % own within range+0.7 of nearest enemy (#2128-2133 @36105-36143, per-unit range read kept)
(defrule (true) =>                                    ; Rule 37
 (up-set-precise-target-point vecNearE)
 (up-modify-goal gCnt c:= 0)
 (up-modify-goal gI g:= gSize)
 (up-modify-goal gI c:- 1))
(defrule (up-compare-goal gI c:< 0) => (up-jump-direct c: 42))   ; Rule 38
(defrule (true) =>                                    ; Rule 39
 (up-set-target-object search-local g: gI)
 (up-get-object-data object_data-range gTmpA)
 (up-modify-goal gTmpA c:* 100)
 (up-modify-goal gTmpA c:+ 70)
 (up-get-object-data object_data-to-precise gTmpB))
(defrule (up-compare-goal gTmpB g:<= gTmpA) => (up-modify-goal gCnt c:+ 1))  ; Rule 40
(defrule (true) => (up-modify-goal gI c:- 1) (up-jump-direct c: 38))         ; Rule 41
(defrule (true) =>                                    ; Rule 42
 (up-modify-goal gCnt c:* 100)
 (up-modify-goal gCnt g:/ gSize)
 (up-modify-goal gPctInRange g:= gCnt))
;--- Rule 43 — FARTHEST-FIRST SORT (load-bearing: persists into volley group 0) + var150 (#2134 @36144-36167 / #2681 @41326-37)
(defrule (true) =>
 (up-set-precise-target-point vecEC)
 (up-clean-search search-local object_data-precise-distance search_order-descending)  ; own farthest-from-enemy first
 (up-modify-goal gTmpA g:= gSize)
 (up-modify-goal gTmpA c:- 1)
 (up-set-precise-target-point vecNearE)
 (up-set-target-object search-local g: gTmpA)        ; index F-1 = closest own unit
 (up-get-object-data object_data-to-precise gDistClosE))

;=== TRANSITIONS (verbatim thresholds) ===
;--- Rule 44 — 22->18 (#2705 @41538-41550 VERBATIM; gEnemySync fixed 0 keeps the var146 branch dead exactly as vs melee)
(defrule
 (or (and (up-compare-goal gPctFired c:< 45)
         (or (and (up-compare-goal gPctReady c:< 75)
                 (up-compare-goal gEnemySync c:> 55))
             (up-compare-goal gPctReady c:< 60)))
     (up-compare-goal gStateAge c:>= 3000))
 (up-compare-goal gState c:== 22)
 =>
 (up-modify-goal gState c:= 18)
 (up-modify-goal gStateT g:= gTimeMilli)
 (up-modify-goal gStateAge c:= 0)
 (up-modify-goal gJustChanged c:= 1))
;--- Rule 45 — 22->18 enemy-close (#2706 @41552-41563 VERBATIM)
(defrule
 (or (up-compare-goal gPctReady c:< 75)
     (up-compare-goal gStateAge c:>= 2000))
 (up-compare-goal gPctFired c:< 55)
 (up-compare-goal gDistClosE c:< 250)
 (up-compare-goal gState c:== 22)
 =>
 (up-modify-goal gState c:= 18)
 (up-modify-goal gStateT g:= gTimeMilli)
 (up-modify-goal gStateAge c:= 0)
 (up-modify-goal gJustChanged c:= 1))
;--- Rule 46 — 18->22 (#2707 @41565-41579; DEVIATION: (varTmp4778<50 OR var146<55) auto-true with var146=0; boolvar783/784 engagement-bias flags omitted)
(defrule
 (up-compare-goal gPctInRange c:> 55)
 (up-compare-goal gPctReady c:>= 91)
 (up-compare-goal gState c:== 18)
 =>
 (up-modify-goal gState c:= 22)
 (up-modify-goal gStateT g:= gTimeMilli)
 (up-modify-goal gStateAge c:= 0)
 (up-modify-goal gJustChanged c:= 1))

;=== KITE (state 18) ===
;--- Rule 47
(defrule (up-compare-goal gState c:!= 18) => (up-jump-direct c: 58))
;--- Rule 48 — RE-ORDER THROTTLE (#2736 @41874-41886 VERBATIM shape; DEVIATION: var96!=var3120 sign-flip disjunct dropped, sign never flips here)
(defrule
 (up-modify-goal gMod24 g:= gStateAge)
 (up-modify-goal gMod24 c:mod 2400)
 (up-modify-goal gMod12 g:= gStateAge)
 (up-modify-goal gMod12 c:mod 1200)
 (nor (or (up-compare-goal gJustChanged c:== 1)
         (and (up-compare-goal gMod12 g:< gMsecPerLoop)
             (up-compare-goal gWinPct c:>= 60)))
     (and (up-compare-goal gMod24 g:< gMsecPerLoop)
         (up-compare-goal gWinPct c:< 60)))
 => (up-jump-direct c: 58))
;--- Rule 49 — strafe magnitude (#2737 @41888-41895; DEVIATION: varTmp4815 building-pull = 0, no towers)
(defrule
 (up-modify-goal gStrafeMag c:= 200)
 (up-compare-goal gDistClosE c:< 100)
 => (up-modify-goal gStrafeMag c:= 0))
;--- Rule 50 — kite distance base (#2739 @41902-41918 arithmetic verbatim; DEVIATION: entry gate dropped — varTmp4797 fixed 0 (<25) and enemies exist, so Immortal would not jump either)
(defrule (true) =>
 (up-modify-goal gKiteDist c:= 0)
 (up-modify-goal gTmpA g:= gSize)
 (up-modify-goal gTmpA c:* 4)
 (up-modify-goal gTmpA c:- 10)
 (up-modify-goal gKiteDist g:- gTmpA)
 (up-modify-goal gTmpB c:= 100)
 (up-modify-goal gTmpB g:- gPctInRange)
 (up-modify-goal gKiteDist g:- gTmpB))
;--- Rule 51 — (#2745 @41963-41967 verbatim)
(defrule
 (up-compare-goal gMedNext c:== 0)
 (up-compare-goal gPctReady c:== 100)
 => (up-modify-goal gKiteDist c:- 25))
;--- Rule 52 — (#2746 @41969-41974 verbatim)
(defrule
 (up-modify-goal gTmpA g:= gRange)
 (up-modify-goal gTmpA c:* 100)
 (up-modify-goal gTmpA c:+ 85)
 (up-compare-goal gTmpA g:< gDistMedE)
 => (up-modify-goal gKiteDist c:- 100))
;--- Rule 53 — clamp + rebase (#2747 @41976-41984 + #2748 @41986-41991; skirm max-150 branch and var3122-halving omitted: CA + var154 fear fixed 10000)
(defrule (true) =>
 (up-modify-goal gKiteDist c:max -500)
 (up-modify-goal gKiteDist c:min 500)
 (up-modify-goal gKiteDistC g:= gKiteDist)
 (up-modify-goal gTmpA g:= gRange)
 (up-modify-goal gTmpA c:* 100)
 (up-modify-goal gKiteDist g:+ gTmpA)
 (up-modify-goal gKiteDist c:max 50)
 (up-modify-goal gKiteDist g:- gDistMedE))
;--- Rule 54 — kite vector (#2749 @41993-96, #2752 @42014-26, #2754 @42040-50; DEVIATIONS: retreat-override #2750/#2751 omitted (needs vec236/home); -40%*dot lerp omitted (dot fixed 0); TC-drag #2753 omitted (var126=-1); vec234 military centroid -> vecEC (equal vs army-only P3); tower-pull lerp = 0)
(defrule (true) =>
 (up-copy-point vecRetreat vecEC)
 (up-copy-point vecKite vecMed)
 (up-modify-goal gTmpA c:= -1)
 (up-modify-goal gTmpA g:* gKiteDist)
 (up-lerp-tiles vecKite vecRetreat g: gTmpA)
 (up-modify-goal gTmpB g:= gStrafeMag)
 (up-modify-goal gTmpB g:* gStrafeSign)
 (up-cross-tiles vecKite vecEC g: gTmpB)
 (up-add-point vecKite vecMed c: -1)
 (up-modify-goal gKiteLen c:= 390)
 (up-modify-goal gKiteLen g:%* gSpeed))
;--- Rule 55 — normalize to 3.9x speed, rebase, bound (#2756 @42057-42066 VERBATIM order; vecZero plays vec21; #2755 x2-when-losing omitted, gWinPct fixed 100)
(defrule (true) =>
 (up-get-point-distance vecZero vecKite gNormLen)
 (up-modify-goal vecKite_x g:* gKiteLen)
 (up-modify-goal vecKite_y g:* gKiteLen)
 (up-modify-goal vecKite_x g:/ gNormLen)
 (up-modify-goal vecKite_y g:/ gNormLen)
 (up-add-point vecKite vecMed c: 1)
 (up-bound-precise-point vecKite _true c: 100))
;--- Rule 56 — PATROL variant vs ranged enemies (#2757 @42068-42082 VERBATIM orders; DEVIATION: var143!=1 and sn71<=65 gates dropped)
(defrule
 (up-compare-goal gERange c:>= 4)
 (up-compare-goal gDistClosE c:>= 200)
 (up-compare-goal gKiteDistC c:<= 150)
 (up-compare-goal gKiteDistC c:>= -150)
 =>
 (up-modify-sn sn-target-point-adjustment c:= 6)
 (up-target-point vecKite action-patrol formation-line stance-no-attack)
 (up-modify-sn sn-target-point-adjustment c:= 5)
 (up-modify-sn sn-target-point-adjustment c:= 6)
 (up-target-point vecKite action-patrol formation-line stance-no-attack)
 (up-modify-sn sn-target-point-adjustment c:= 5)
 (up-jump-direct c: 58))
;--- Rule 57 — THE KITE MOVE vs melee (#2758 @42084-42092 VERBATIM: double-issue, 6->order->5, action-move, formation-line, stance-no-attack)
(defrule (true) =>
 (up-modify-sn sn-target-point-adjustment c:= 6)
 (up-target-point vecKite action-move formation-line stance-no-attack)
 (up-modify-sn sn-target-point-adjustment c:= 5)
 (up-modify-sn sn-target-point-adjustment c:= 6)
 (up-target-point vecKite action-move formation-line stance-no-attack)
 (up-modify-sn sn-target-point-adjustment c:= 5))

;=== VOLLEY (state 22) — #2759-#2791 verbatim ===
;--- Rule 58 (#2759 @42094-42097)
(defrule (up-compare-goal gState c:!= 22) => (up-jump-direct c: 76))
;--- Rule 59 (#2760 @42099-42106: group 0 := own, farthest-first order from Rule 43)
(defrule (true) =>
 (up-create-group 0 0 c: 0)
 (up-reset-search _true _true _false _false)
 (up-get-search-state vecSS)
 (up-modify-goal gI g:= vecSS_R)
 (up-modify-goal gI c:- 1))
;--- Rule 60 (#2761 @42108-42115 VERBATIM incl. up-jump-rule -1)
(defrule
 (up-compare-goal gI c:>= 0)
 =>
 (up-set-target-object search-remote g: gI)
 (up-get-object-data object_data-unique-id gUid)
 (up-add-object-by-id search-local g: gUid)
 (up-modify-goal gI c:- 1)
 (up-jump-rule -1))
;--- Rule 61 (#2762 @42117-42133 VERBATIM)
(defrule (true) =>
 (up-create-group 0 0 c: 1)
 (up-set-group search-local c: 0)
 (up-set-target-object search-local c: 0)
 (up-get-object-data object_data-precise-x vecFarOwn_x)
 (up-get-object-data object_data-precise-y vecFarOwn_y)
 (up-set-precise-target-point vecFarOwn)
 (up-clean-search search-remote object_data-to-precise search_order-ascending)
 (up-set-target-object search-remote c: 0)
 (up-get-object-data object_data-to-precise gFarD)
 (up-full-reset-search)
 (up-set-group search-local c: 1)
 (up-get-search-state vecSS)
 (up-modify-goal gI g:= vecSS_L)
 (up-modify-goal gI c:- 1))
;--- Rule 62 (#2763 @42135-42142: re-reverse restores remote order)
(defrule
 (up-compare-goal gI c:>= 0)
 =>
 (up-set-target-object search-local g: gI)
 (up-get-object-data object_data-unique-id gUid)
 (up-add-object-by-id search-remote g: gUid)
 (up-modify-goal gI c:- 1)
 (up-jump-rule -1))
;--- Rule 63 (#2764 @42144-42153 VERBATIM: prune targets beyond max(range*100, farthest-own-to-nearest)+50, measured from vecFarOwn)
(defrule (true) =>
 (up-set-group search-local c: 0)
 (up-modify-goal gPruneR g:= gRange)
 (up-modify-goal gPruneR c:* 100)
 (up-modify-goal gPruneR g:max gFarD)
 (up-modify-goal gPruneR c:+ 50)
 (up-remove-objects search-remote object_data-to-precise g:> gPruneR)
 (up-get-search-state vecSS))
;--- Rule 64 (#2765 @42155-42158)
(defrule (up-compare-goal vecSS_R c:!= 0) => (up-jump-direct c: 66))
;--- Rule 65 (#2766 @42160-63 + #2767 flip merged; DEVIATION: merged into one rule)
(defrule (true) =>
 (chat-to-all "ERROR: no enemies in range to attack")
 (up-modify-goal gState c:= 18)
 (up-modify-goal gStateT g:= gTimeMilli)
 (up-modify-goal gStateAge c:= 0)
 (up-modify-goal gJustChanged c:= 1)
 (up-jump-direct c: 76))
;--- Rule 66 (#2774 @42215-42220 VERBATIM: strip own units still on cooldown; group 2 := ready-to-fire)
(defrule (true) =>
 (up-remove-objects search-local object_data-next-attack g:>= gFireWin)
 (up-create-group 0 0 c: 2)
 (up-modify-goal gHPFactor c:= 115))
;--- Rule 67 (#2775 @42222-42231 VERBATIM: HP overestimate 160% when enemy median action is none of the work actions; vs attacking knights stays 115)
(defrule
 (up-compare-goal gEAction c:!= actionid-convert)
 (up-compare-goal gEAction c:!= actionid-repair)
 (up-compare-goal gEAction c:!= actionid-hunt)
 (up-compare-goal gEAction c:!= actionid-gather)
 (up-compare-goal gEAction c:!= actionid-build)
 (up-compare-goal gEAction c:!= actionid-heal)
 (up-compare-goal gEAction c:!= actionid-attack)
 => (up-modify-goal gHPFactor c:= 160))
;--- Rule 68 (#2776 @42233-42236 VERBATIM)
(defrule
 (up-research-status c: ri-ballistics c:== research-complete)
 => (up-modify-goal gHPFactor c:= 100))
;--- Rule 69 (#2777 @42238-42251 VERBATIM: per-target cap + PAIR-ZERO of gTgtIdx/gAsgCnt via up-add-point — keep goals 168/169 consecutive)
(defrule
 (up-modify-goal gTmpA g:= gDistClosE)
 =>
 (up-modify-goal gTmpA c:/ 10)
 (up-modify-goal gTmpA c:+ 100)
 (up-modify-goal gHPFactor g:min gTmpA)
 (up-modify-goal gTmpB g:= gDistClosE)
 (up-modify-goal gTmpB c:/ 100)
 (up-modify-goal gArrowCap c:= 18)
 (up-modify-goal gArrowCap g:- gTmpB)
 (up-modify-goal gArrowCap c:max 6)
 (up-modify-goal gArrowCap c:min 17)
 (up-add-point gTgtIdx gTgtIdx c: -1)
 (up-get-search-state vecSS))
;--- Rule 70 (#2778 @42253-42257 VERBATIM loop head)
(defrule
 (nand (up-compare-goal gAsgCnt g:< gSize)
     (up-compare-goal vecSS_R c:!= 0))
 => (up-jump-direct c: 76))
;--- Rule 71 (#2779 @42259-42279 VERBATIM: arrows-needed for current round-robin target)
(defrule (true) =>
 (up-set-target-object search-remote g: gTgtIdx)
 (up-get-object-data object_data-unique-id gTgtUid)
 (up-get-object-data object_data-hitpoints gTgtHP)
 (up-modify-goal gTgtHP g:%* gHPFactor)
 (up-get-object-data object_data-pierce-armor gTgtPA)
 (up-set-group search-local c: 2)
 (up-remove-objects search-local object_data-index g:< gAsgCnt)
 (up-modify-goal gDmg g:= gAttack)
 (up-modify-goal gDmg g:- gTgtPA)
 (up-modify-goal gDmg c:max 0)
 (up-modify-goal gDmg g:+ gBonus1)
 (up-modify-goal gDmg c:max 1)
 (up-modify-goal gArrows g:= gTgtHP)
 (up-modify-goal gArrows g:/ gDmg)
 (up-modify-goal gArrows c:max 0)
 (up-modify-goal gArrows c:min 17)
 (up-modify-goal gArrows c:+ 1)
 (up-modify-goal gArrows g:min gArrowCap))
; DEVIATION: exact-damage simulation #2780-2786 @42281-42325 (early-game only, gated on sn130<90 && sn71<52) omitted — we always take Immortal's late-game path #2787.
;--- Rule 72 (#2787 @42327-42331 VERBATIM)
(defrule
 (up-modify-goal gNeed g:= gArrows)
 =>
 (up-modify-goal gNeed c:+ 2)
 (up-get-search-state vecSS))
;--- Rule 73 (#2788 @42333-42336 VERBATIM: fewer ready units than needed+2 -> assign everyone / focus fire)
(defrule (up-compare-goal vecSS_L g:< gNeed) => (up-modify-goal gArrows c:+ 99))
; DEVIATION: skirmisher hold-fire special #2789 @42338-42348 omitted (var106==skirmisher only).
;--- Rule 74 (#2790 @42350-42356 — THE VOLLEY ORDER, VERBATIM)
(defrule (true) =>
 (up-set-target-object search-remote g: gTgtIdx)
 (up-remove-objects search-local object_data-index g:>= gArrows)
 (up-remove-objects search-local object_data-target-unique-id g:== gTgtUid)
 (up-target-objects _true action-default formation-ignore stance-ignore))
;--- Rule 75 (#2791 @42358-42364 VERBATIM)
(defrule
 (up-modify-goal gAsgCnt g:+ gArrows)
 =>
 (up-modify-goal gTgtIdx c:+ 1)
 (up-get-search-state vecSS)
 (up-modify-goal gTgtIdx g:mod vecSS_R)
 (up-jump-direct c: 70))

;=== END OF PASS ===
;--- Rule 76 — steady-state SN override (#9732 @115875-115878; DEVIATION: literal player 3 replaces packed s:339; town/dropsite sns omitted — no economy)
(defrule (true) =>
 (up-modify-sn sn-target-player c:= 3)
 (up-modify-sn sn-percent-enemy-sighted-response c:= 0)
 (up-modify-sn sn-enemy-sighted-response-distance c:= 0)
 (up-modify-sn sn-disable-sighted-response-cap c:= 1))
;--- Rule 77 — pass bookkeeping (#9735 @115898-115900)
(defrule (true) =>
 (up-modify-goal gLoopCounter c:+ 1)
 (up-modify-goal gPtimeMilli g:= gTimeMilli))
```

**Optional appendix (untagged stance sweeper, Immortal #8698 @103471-103487)** — add before Rule 5 if stray untagged units auto-chase; renumber all jumps if you do:
```
(defrule (true) =>
 (up-full-reset-search)
 (up-find-local c: class-cavalry-archer c: 240)
 (up-remove-objects search-local object_data-tag c:> 0)
 (up-remove-objects search-local object_data-attack-stance c:!= stance-aggressive)
 (up-target-point 0 action-none formation-ignore stance-defensive)
 (up-target-point 0 action-stop formation-ignore stance-ignore))
```

**Global deviation summary:** (a) no SN 430/431 packing — single group keeps state in dedicated goals (Immortal packs only to multiplex 6 tag-SMs through shared working goals, #8763/#8766 @104873-104987); (b) states 2-17/23 cut, bootstrap 0→22; (c) getTagInfo (#1108-1113) and merge/evict/rebalance/split/dissolve clustering branches cut — one ball, one tag; (d) target-scoring sort replaced by distance sort; (e) fixed goals: var146=0, var165=100, var154=10000, varTmp4797=0, var126=−1, var96=+1, var2765=110, var3125/26=0.

---

# PART 3 — TEST-INTERPRETATION TABLE

| Failure mode observed | Re-examine (transcript element, file lines) |
|---|---|
| Units ignore the kite move / keep attacking | #2758 @42084-42092: all 5 elements must be present — `action-move`, `formation-line`, `stance-no-attack`, TSA 6→order→5 wrap, and the DOUBLE issue. Then #8660 @103225 (`sn-task-ungrouped-soldiers 0`) and #9732 @115876-77 (sighted-response 0/0) — if engine tasking is alive it re-targets units instantly. Confirm Rule 76 runs LAST every pass. |
| Units only obey patrol (your old symptom) | You were missing stance-no-attack + double-issue on action-move. Compare your order line to #2758 verbatim; also confirm the tag filter left the right units in search-local at order time (#1562 @31348 — the order acts on whatever survived the filter). |
| Volley order fires nothing | Strip chain order in #2790 @42353-56: set-target BEFORE strips; index strip uses group-2 restored list from #2779 @42267-68; check gFireWin: if var116 is wrong (reload units), #2774 @42218 removes ALL units. Verify gReload read via #1579 idiom @31514-17 (desc sort, index 0) returns ~2000, and gFireWin≈990. |
| Volley hits only 1 enemy then stops | #2791 loop plumbing @42358-64: `g:mod vecSS_R` needs the get-state refresh; #2778 exit condition `nand(gAsgCnt<gSize, S!=0)`; #2788 +99 fires when ready < arrows+2 (that is CORRECT focus-fire behavior, not a bug). |
| Object-data reads return 0 | Read pattern: `up-set-target-object <list> g:i` IMMEDIATELY before every `up-get-object-data` (#1609 @31761-65), on a list built by find+filter in the SAME pass (#2624 @40817-21 → #1562 @31348). Never read from a list that survived a `up-full-reset-search` except via `up-set-group` restore (#1117 @27482-84). If tag reads give 0 instead of −2: 0 = a unit previously untagged via `up-modify-group-flag _false` (#1177 @28011-13, #2682 @41345); −2 = never grouped. Filter with `c:> 0` / `c:== N`, never `c:!= -2` alone. |
| Tag never sticks / group filter matches nothing | Trio ORDER #1141 @27722-24: create → flag `_true` → reset. Flag before reset; group number == tag value == the filter constant (1). Verify by reading object_data-tag (73) on a unit next pass: must equal 1. |
| Clustering never runs / runs every pass | Beat gate #8750 @104737-45: `mod 4040 g:< msecPerLoop` requires real msecPerLoop — time Rule 1 (#3592 @49199-49210) must be FIRST and Rule 77 (#9735 @115898-900) LAST; loopCounter>0 blocks pass 0. |
| Kite spam (orders every pass) | Throttle #2736 @41874-86: gJustChanged must be cleared at TOP of getData (Rule 16, #1572 @31434 semantics) and set ONLY by transitions; beat is `mod var123` (state age), not timeMilli. |
| Group never flips back to 22 | #2707 @41565-79 needs gPctReady>=91 AND gPctInRange>55 — check the var118 window (110ms, #1617 @31813) against your units' next-attack readings, and the var128 loop (range·100+70 vs to-precise, Rules 37-42) — if var128 stays ≤55 the group kites forever. |
| Group stuck in 22, never kites | #2705 @41539-43: needs var117<45 AND var118<60, or age≥3000 — the 3s cap alone guarantees eventual flip; if not flipping, gStateAge is broken → check var94 write in transitions and the `timeMilli − var94` subtraction (Rule 16). |
| Units drift to map corner / kite point garbage | #2756 @42057-66: vecZero must be (0,0) (vec21 role); vecKite must be an OFFSET when normalized (`up-add-point vecKite vecMed c: -1` BEFORE, `c: 1` AFTER); all points precise (tiles·100); `up-bound-precise-point ... c: 100` keeps 1 tile off map edge. |
| No damage focus / wrong targets | Remote ordering: our distance sort (Rule 36) replaces Immortal's scoring sort #2673-80 @41233-41325 — if targeting looks dumb (ignores monks/siege), transcribe the scoring sort next. Also #2764 @42152 prune radius measured from the FARTHEST own unit (vecFarOwn), not the median. |

Verified source: `C:\Program Files (x86)\Steam\steamapps\common\AoE2DE\resources\_common\ai\Immortal v0d10f.per` (all line numbers above re-read this session).
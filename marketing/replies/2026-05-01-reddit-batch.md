# Reddit Replies — 2026-05-01

Scouted via Reddit JSON API (`r/aoe2/new` + `r/aoe2/hot`). Two threads with genuine questions where sim data adds value.

---

## Reply 1 — Mapuche vs BBC + pikes

**Thread:** "Fav civ pickers- what strats are good against you?"
**URL:** https://www.reddit.com/r/aoe2/comments/1szp1m3/fav_civ_pickers_what_strats_are_good_against_you/
**Reply to:** u/borwil's comment (score:3) — *"1100 elo team random Mapuche, I have trouble playing against bombard cannons. If they use pikes to defend I always need to call help from my teammate. Any ideas how to deal with that?"*
**Type:** Specific counter question → include site link (one at the end)

**Sim data backing this reply:**
| Matchup | 20v20 | Equal resources (3000) |
|---|---|---|
| Elite Champi Warrior vs Halberdier | Champi 20–0 (74% HP) | Champi 40–0 (65% HP) |
| Elite Champi Warrior vs Bombard Cannon (10v10, equal res 3000) | BBC 10–0 | Champi 28–0 (70% HP) |
| Elite Kona vs Bombard Cannon (15v15, equal res 3000) | Kona 1–0 (3% HP) | Kona 22–0 (79% HP) |

Costs: Champi Warrior 75 res • Halberdier 60 res • Bombard Cannon 450 res

**Key insight:** Halbs counter cavalry, not infantry. Elite Champi Warriors beat halberdiers at both equal count AND equal resources — so the enemy's "pike screen to defend BBCs from cavalry" is completely irrelevant to Mapuche's answer. Also, Mapuche has no cavalry at all (no hussar, no cavalier), so the standard BBC counter doesn't apply.

---

**PASTE THIS:**

> u/borwil — the tough part with Mapuche is you have no hussar, so the normal "cavalry through the pikes" answer is off the table.
>
> What actually works is your **Elite Champi Warrior**. The key thing people miss: halberdiers counter *cavalry*, not infantry. Your Champi Warriors are infantry, so the pike screen protecting the BBCs does nothing against them. In a 20v20, Champi Warriors beat halbs 20–0 (74% HP remaining), and they still win at equal resources because Champi costs only 75 res vs halbs 60 — very similar price.
>
> Against the BBCs themselves: a Bombard Cannon costs 450 resources each. At equal cost (~3000 res), you're sending 40 Champi Warriors into 6 BBCs, and the Champi Warriors win 28–0. Yes, if they have equal *numbers* of BBCs the cannon will shred you — but no one can afford equal numbers of BBCs. Just mass the Champi Warriors, accept the opening volleys, and sweep through.
>
> Elite Kona also has a built-in +5 attack bonus vs Gunpowder units (literally coded in as a BBC counter) and wins vs BBCs at equal resources too. It costs 105 res vs Champi's 75, so for teamgame resource efficiency Champi mass is usually the better call.
>
> Ran the numbers at aoe2matchup.com if you want to check other Mapuche matchups.

---

## Reply 2 — Portuguese Organ Guns (the real lategame threat)

**Thread:** "Playing against Portuguese, you *have* to go full aggro to prevent them from going to Imp, right?"
**URL:** https://www.reddit.com/r/aoe2/comments/1szleja/playing_against_portuguese_you_have_to_go_full/
**Reply to:** Top-level comment on the post (not replying to a specific comment)
**Type:** Strategic discussion — no self-promo link (most comments already give reasonable answers; we add data, not a sales pitch)

**Sim data backing this reply:**
| Matchup | 20v20 | Equal resources (3000) |
|---|---|---|
| Elite Organ Gun vs Arbalester | OG 20–0 (100% HP) | OG 22–0 (100% HP) |
| Elite Organ Gun vs Elite Skirmisher | OG 18–0 (89% HP) | OG 13–0 (57% HP) |
| Elite Organ Gun vs Champion | OG 20–0 (100% HP) | OG 22–0 (79% HP) |
| Elite Organ Gun vs Hussar | OG 19–0 (61% HP) | **Hussar 15–0 (7% HP)** |
| Elite Organ Gun vs Elite Eagle | OG 15–0 (66% HP) | **Eagle 31–0 (26% HP)** |

Costs: Elite Organ Gun 136 res • Arbalester 70 res • Elite Eagle 70 res • Hussar 80 res

**Key insight:** The community assumption is "make arbs vs Organ Guns" (arbs counter archers). The sim says that's completely wrong — Organ Guns dominate arbs even at equal resources because the scatter projectiles cluster-kill bunched ranged units. The actual counter is fast melee: hussars and especially elite eagles (same cost as arbs but decisively win the engagement).

---

**PASTE THIS:**

> The comments are right that Feitorias are overhyped on open maps — they're only a problem when all the mines run dry. But "just play standard" has a hidden assumption that your standard comp handles their Organ Guns. It often doesn't.
>
> The simulation result that surprised me: **Arbalest loses to Elite Organ Gun at equal resources, badly.** OG wins 22–0 at full HP. Same for Elite Skirmisher — OG wins that too. The Organ Gun fires multiple scatter projectiles per shot, and clustered ranged units bunch up perfectly to eat every projectile. It's the opposite of the archer matchup intuition.
>
> What actually works: **fast melee**. Hussar beats Organ Gun at equal resources (barely — 15 remaining at 7% HP). Elite Eagle is even better — same cost as an arbalest (70 resources each) but beats Organ Guns decisively at equal resources (31 Eagles left vs 0). They close the gap through the opening volleys and then it becomes a melee fight the OG can't win.
>
> So the real answer to Portuguese lategame isn't "be more aggressive" — it's "don't mass archers into their castle, make fast melee instead."

---

## Scouting notes

- Reddit scouted via JSON API (`r/aoe2/new` + `r/aoe2/hot`, 50 posts each)
- Other threads checked, not worth replying to: ban/ELO questions, UI mods, campaign discussion, new player general questions
- Next scout: check back in ~2 days for new strategy threads

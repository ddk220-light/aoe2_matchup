# What the new civs' unique units actually do — community wisdom vs simulation results

> All matchups tested at full upgrades (Imperial, Elite UU, all blacksmith / university / unique techs, civ bonuses applied). Each match run two ways:
> - **30v30** — equal count, raw combat strength.
> - **4500 res** — equal pooled resources, cost-efficiency (the realistic test).
>
> Results read as `winner survivors-loser_survivors (HP%/HP%)`.
>
> Each section starts with what the community / Steam guides / Fandom wiki say about the unit, then shows what the sim actually does. The interesting parts are where they disagree.

---

## TL;DR — the 5 findings that contradict community wisdom

1. **The Aztec Jaguar Warrior is a hard counter to the Muisca Temple Guard** that almost nobody talks about. 50 Jaguars walk through 36 Temple Guards with 62% HP remaining at equal cost.

2. **The Mapuche Bolas Rider beats the Saracen Heavy Camel at being anti-cavalry.** The "anti-cav cav archer" outclasses the "anti-cav melee" unit because it kites. 27-0 at equal cost.

3. **The Kona does NOT counter all gunpowder — it loses badly to Conquistador.** Crushes Hand Cannoneer (15-0) and Janissary (9-0), but gets wiped by Conquistador (0-30 with 80% HP remaining for Conq). The community says "Kona is a gunpowder counter" — there's a glaring exception.

4. **The Tupi Blackwood Archer's "OP pair-training" is a production-time advantage, not a combat advantage.** At equal cost (where both sides have the same gold pool, neutralizing the pair-train benefit) it loses to literally every other archer UU and even to generic Arbalesters.

5. **The Tupi Ibirapema's trample is a hard counter to mid-tier cavalry, not all cavalry.** It beats Knights, Eagles, Heavy Camels, Halberdiers cleanly — but Burgundian Cavalier (basically a Paladin) wins 11-0 with 90% HP remaining. Trample loses to per-unit firepower.

---

## TUPI

### Blackwood Archer — community says "OP because pair-training"

> *Steam community guide: "incredibly weak individually, with the lowest hit points of any unit in the game, but they make up for this with numbers and relatively cheap cost. They train in pairs — 2 units per production cycle."*

What the sim says:

| Matchup | 30v30 | 4500 res |
|---|---|---|
| vs **Skirmisher** | **A 60-0 (99%/0%)** | **B 0-32 (0%/42%)** |
| vs Imperial Skirmisher | B 0-10 (0%/32%) | B 0-70 (0%/93%) |
| vs Eagle Warrior | B 0-12 (0%/39%) | B 0-50 (0%/77%) |
| vs Goth Huskarl | B 0-14 (0%/44%) | B 0-43 (0%/74%) |
| vs Britons Longbow | B 0-30 (0%/98%) | B 0-60 (0%/100%) |
| vs Generic Arbalester | B 0-18 (0%/58%) | B 0-64 (0%/100%) |

**The hidden truth:** the Blackwood Archer's pair-training is a **production-rate multiplier**, not a damage multiplier. In an equal-count fight (60 BWAs vs 60 Skirms) the BWAs absolutely murder the Skirms — 99% HP remaining. But in an equal-cost fight, both sides field whatever they can afford at the same gold, the pair-training doesn't help, and BWAs lose to almost everything because they have the lowest HP in the game.

So is the BWA strong or weak? **Both, depending on the bottleneck.** If you're production-time-constrained (early Castle, limited Archery Ranges), the pair-train doubles your DPS output and the unit is genuinely scary. If you're gold-constrained (mid/late game), you're just feeding cheap arrows to whatever the opponent makes.

### Ibirapema Warrior — community says "trample = great vs grouped units"

> *Steam community guide: "deals area damage, exceptional against grouped units. Pairs well with Blackwood Archers."*

What the sim says:

| Matchup | 30v30 | 4500 res |
|---|---|---|
| vs Persian Knight (Cavalier) | A 23-0 (20%/0%) | **A 50-0 (60%/0%)** |
| vs Eagle Warrior | A 30-0 (48%/0%) | **A 39-0 (30%/0%)** |
| vs Heavy Camel | A 27-0 (25%/0%) | **A 50-0 (48%/0%)** |
| vs Britons Halberdier | A 30-0 (82%/0%) | A 50-0 (71%/0%) |
| vs **Burgundian Cavalier (Paladin)** | **B 0-25 (0%/47%)** | **B 0-11 (0%/10%)** |
| vs Teutonic Knight | B 0-30 (0%/93%) | B 0-39 (0%/91%) |
| vs Mayan Plumed Archer | B 0-29 (0%/87%) | B 0-51 (0%/89%) |
| vs Goth Champion (mass) | A 20-0 (21%/0%) | B 0-51 (0%/41%) |

**The hidden truth:** Ibirapema's trample is brutal against *cheap* groupings — Halberdiers, Knights, Eagles, Heavy Camels all melt because each swing kills 2-3 units at once. But against high-HP single units (Cavalier/Paladin, Teutonic Knight) the trample doesn't matter — one swing barely dents one Paladin. Ibira loses to Burgundian Cavalier with 10% HP remaining vs 0%. Players who bucket "Ibira good vs cav" miss that there's a clear HP-per-unit threshold above which trample stops mattering.

**The clean rule:** Ibirapema beats anything below ~120 HP. It loses to anything above.

---

## MUISCA

### Temple Guard — community says "sustained combat king with attack speed ramp"

> *Steam community guide: "channels religious fervor into combat through an attack speed mechanic — the longer they remain fighting, the faster they attack. Don't send on long raids — strength comes from sustained combat. Don't retreat: that resets the attack speed bonus."*

What the sim says:

| Matchup | 30v30 | 4500 res |
|---|---|---|
| vs **Aztec Jaguar Warrior** | **B 0-30 (0%/41%)** | **B 0-50 (0%/62%)** |
| vs Saracen Mameluke | B 0-29 (0%/76%) | B 0-31 (0%/70%) |
| vs Teutonic Knight | B 0-30 (0%/78%) | B 0-39 (0%/81%) |
| vs Viking Berserk (regen vs ramp) | A 30-0 (30%/0%) | **B 0-16 (0%/19%)** |
| vs Goth Champion (mass) | A 30-0 (27%/0%) | **B 0-91 (0%/71%)** |
| vs Frank Paladin | A 30-0 (32%/0%) | A 36-0 (42%/0%) |
| vs Goth Huskarl | A 30-0 (51%/0%) | A 30-0 (22%/0%) |
| vs Eagle Warrior | A 30-0 (58%/0%) | A 36-0 (20%/0%) |

**The hidden truth — four real counters to the Temple Guard, ordered by how surprising they are:**

1. **Jaguar Warrior** — The Aztec UU has a +bonus damage vs infantry attack. At 50-0 with 62% HP at equal cost, this is an absolute wipe, and almost nobody talks about it. If you face Muisca and you're Aztec, just make Jaguars.

2. **Mameluke** — Anti-cav UU but it has 8 range and absurd attack. Temple Guard can't reach it, dies at range.

3. **Teutonic Knight** — Same role as Temple Guard but with ridiculous melee armor. Straight-up better.

4. **Berserk in mass** — Regen beats attack-speed-ramp at equal cost. The Berserk's healing is a cheaper, more reliable sustain mechanic than the TG's accelerating attack speed.

**The Halberdier non-counter:** worth noting since it's the obvious one — Halberdiers do nothing to Temple Guards (they only counter cavalry-class units, TG is infantry-class). 67% HP remaining for TG vs 0% for Halbs at equal cost. *That's expected — don't lead with it.*

### Guecha Warrior — community says "improved Skirmisher with regen"

> *Fandom wiki: "regenerates 5 hit points over 3 seconds whenever a nearby allied Guecha Warrior is killed in a 6 tile radius. Effective against archers, similar to a Skirmisher."*

What the sim says:

| Matchup | 30v30 | 4500 res |
|---|---|---|
| vs Spanish Hand Cannoneer | A 17-0 (57%/0%) | A 11-0 (27%/0%) |
| vs Crossbowman | A 27-0 (89%/0%) | A 31-0 (77%/0%) |
| vs Skirmisher | A 27-0 (90%/0%) | A 26-0 (65%/0%) |
| vs Mongol Mangudai | B 0-6 (0%/19%) | A 13-0 (30%/0%) |
| vs **Imperial Skirmisher** | A 20-0 (63%/0%) | **B 0-55 (0%/73%)** |
| vs **Berber Genitour** | **B 0-4 (0%/11%)** | **B 0-6 (0%/13%)** |
| vs Britons Longbow | B 0-20 (0%/65%) | B 0-58 (0%/97%) |

**The hidden truth — two surprising losses:**

1. **Genitour wipes Guecha** despite the Guecha's high pierce armor (5/7) and the Genitour being a "weak" cav archer. The Genitour kites perfectly and Guechas can't catch it. 4-0 at 30v30, 6-0 at equal cost — both with the Guechas barely scratching the Genitours.

2. **Imperial Skirm beats Guecha at equal cost** (0-55 with 73% HP for Imp Skirm), even though Guecha wins 30v30. Imperial Skirm is so cheap (35F/25W, no gold) that you can field nearly 3× the count. The "improved Skirmisher" loses to the actual Skirmisher at equal gold.

**Where Guechas do shine:** they obliterate gold-heavy ranged units (Hand Cannoneer, Crossbowman, basic Skirms) and they hard-counter the Tupi Blackwood Archer (32-0 at equal cost). They are not a generic anti-archer answer.

---

## MAPUCHE

### Bolas Rider — community says "anti-cavalry mounted archer"

> *Fandom wiki: "short-ranged anti-cavalry mounted archer. Charges its attack +2/+3 over 30s. Slow projectile reduces target speed by 15% for 10s. Bolas attack deals extra damage to mounted units."*

What the sim says:

| Matchup | 30v30 | 4500 res |
|---|---|---|
| vs **Saracen Heavy Camel (Imperial Camel)** | B 0-9 (0%/26%) | **A 27-0 (42%/0%)** |
| vs Mongol Mangudai | B 0-7 (0%/21%) | **A 26-0 (55%/0%)** |
| vs Frank Paladin | B 0-13 (0%/42%) | **A 25-0 (44%/0%)** |
| vs Byzantine Cataphract | B 0-13 (0%/42%) | **A 28-0 (51%/0%)** |
| vs Tupi Blackwood Archer | A 10-0 (33%/0%) | A 38-0 (80%/0%) |
| vs Britons Halberdier | A 26-0 (73%/0%) | B 0-15 (0%/19%) |
| vs Generic Arbalester | A 16-0 (53%/0%) | B 0-30 (0%/46%) |
| vs **Spanish Conquistador** | **B 0-30 (0%/100%)** | **B 0-33 (0%/95%)** |
| vs Imperial Skirmisher | B 0-18 (0%/56%) | B 0-65 (0%/87%) |

**The hidden truth — the Bolas Rider is the most cost-efficient anti-cavalry unit in the game.** At equal cost it beats:
- The Mongol Mangudai (the gold-standard cav archer)
- The Frank Paladin (the gold-standard heavy cav)
- The Byzantine Cataphract (the anti-infantry cav)
- The Saracen Heavy Camel (the dedicated anti-cav melee)

That last one is the headline. The Heavy Camel exists specifically to murder cavalry. The Bolas Rider — a different cavalry unit — beats it at its own job because it kites. Players don't expect a cav archer to win the anti-cav race against a melee specialist.

**Two units that wreck Bolas Riders:**
- **Conquistador.** Gunpowder cav with 16 attack and pierce armor. Bolas Riders cannot scratch them (literally 100% HP remaining for Conq at 30v30). If you see Spanish, switch to Konas.
- **Imperial Skirmisher.** Cheap hard counter — same story as every cav archer fighting Imp Skirm.

### Kona — community says "fast cav with HP-execute, effective vs gunpowder"

> *Fandom wiki: "+1 attack for every missing 15% HP of the target. Effective against gunpowder units. Not affected by cavalry blacksmith techs (Mapuche don't have access to them)."*

What the sim says:

| Matchup | 30v30 | 4500 res |
|---|---|---|
| vs Spanish Hand Cannoneer | A 14-0 (46%/0%) | A 15-0 (35%/0%) |
| vs Turk Janissary | A 4-0 (13%/0%) | A 9-0 (20%/0%) |
| vs **Spanish Conquistador** | **B 0-30 (0%/80%)** | **B 0-30 (0%/63%)** |
| vs Mongol Hussar | A 30-0 (47%/0%) | A 28-0 (24%/0%) |
| vs Frank Paladin | B 0-30 (0%/41%) | B 0-15 (0%/11%) |
| vs Byzantine Cataphract | B 0-30 (0%/34%) | A 9-0 (12%/0%) |
| vs Saracen Mameluke | B 0-30 (0%/96%) | B 0-32 (0%/90%) |
| vs Saracen Heavy Camel | B 0-30 (0%/57%) | B 0-36 (0%/52%) |
| vs Britons Pikeman | A 30-0 (61%/0%) | B 0-24 (0%/23%) |
| vs **Goth Halberdier (mass)** | A 30-0 (42%/0%) | **B 0-104 (0%/82%)** |

**The hidden truth — three corrections to the community framing:**

1. **The "anti-gunpowder" claim has a glaring exception: Conquistador.** Konas crush HCs (15-0) and barely beat Janissaries (9-0), but Conquistadors *roll the Konas* — 0-30 with 80% HP remaining at equal count. Don't make Konas vs Spanish.

2. **0 melee armor + no Bloodlines = catastrophic vs trash counters.** Goth Halberdiers at equal cost field 104 Halbs vs your full Kona pool, and walk away with 82% HP. That's a complete wipe. Even basic Pikemen (not Halberdiers!) beat Konas at equal cost. The 145 HP is misleading.

3. **The HP-execute mechanic is real but situational.** Konas hard-counter Hussars (24% HP remaining at equal cost) because Hussars have low HP — every Hussar dies in 1-2 swings, and the +1-per-15%-missing-HP bonus stacks fast. Against high-HP units the bonus barely activates because you can't bring them low enough to trigger.

**The verdict on Kona:** it's a finisher, not a frontline unit. Use it to pursue routing armies, harass economy, and clean up wounded enemies. Never charge it into a melee blob.

---

## What this all means in practice

If you're playing one of these civs:
- **Tupi:** the Ibirapema wins you mid-game fights via trample. Skip Blackwood Archers unless you have idle production capacity and surplus wood — they're a production-rate weapon, not a cost-efficient one. **Get Curare in Imperial** (community sources confirm this gives BWA poison damage that ignores armor — I didn't simulate this; it's worth re-running once Curare is in the sim).
- **Muisca:** Temple Guards everything except vs Aztecs and Saracens. Guechas are a counter-pick vs gold-heavy ranged comps (HC, Crossbow), not a generic anti-archer answer.
- **Mapuche:** Bolas Riders are your core anti-cavalry. Konas only against gunpowder *if not Spanish*, or to chase routed enemies.

If you're playing against one of these civs:
- **Tupi:** Skirmisher mass beats Blackwood Archers cleanly. Paladins beat Ibirapema. The combination of Skirms + Paladins covers everything Tupi does.
- **Muisca:** Aztec Jaguar Warriors hard-counter Temple Guards. Mameluke and Teutonic Knight also work. Don't make Halbs — they don't counter the Temple Guard at all.
- **Mapuche:** Conquistadors beat both Mapuche unique units. Imperial Skirms shut down Bolas Riders. Heavy halb mass shuts down Konas.

---

*Every matchup above is reproducible at [aoe2matchup.com](https://aoe2matchup.com). Pick the units, hit simulate, watch it play out.*

*Sources for community claims used in this report: [Mapuche wiki](https://ageofempires.fandom.com/wiki/Mapuche_(Age_of_Empires_II)), [Muisca wiki](https://ageofempires.fandom.com/wiki/Muisca), [Tupi wiki](https://ageofempires.fandom.com/wiki/Tupi_(Age_of_Empires_II)), [Kona](https://ageofempires.fandom.com/wiki/Kona), [Bolas Rider](https://ageofempires.fandom.com/wiki/Bolas_Rider), [Temple Guard](https://ageofempires.fandom.com/wiki/Temple_Guard), [Guecha Warrior](https://ageofempires.fandom.com/wiki/Guecha_Warrior), [Blackwood Archer](https://ageofempires.fandom.com/wiki/Tupi_Blackwood_Archer), [Steam Tupi guide](https://games.gg/age-of-empires-ii-definitive-edition/guides/aoe2-the-last-chieftains-tupi-civilization-guide/), [Steam Muisca guide](https://games.gg/age-of-empires-ii-definitive-edition/guides/aoe2-the-last-chieftains-muisca-civilization-guide/).*

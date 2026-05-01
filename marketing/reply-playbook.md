# Reddit / Discord reply playbook

> The workflow: when you spot a thread on r/aoe2, AoEZone, the official forum, or any Discord asking a unit/matchup question, paste the URL (or a screenshot of the question) into our chat. I'll draft a reply, run any sims needed, and give you paste-ready text. You post under your account.
>
> Why this split: Reddit blocks my direct fetching, and Google's site:reddit.com indexing was nerfed in 2023. So I can't autonomously find threads — but I can produce high-quality replies fast once you find one. ~3-5 minutes per reply on your end (find thread, paste URL, paste reply).

---

## The 9:1 rule, applied to reply-mode

Reddit's self-promotion rule: <10% of your activity should mention your site. The good news for you: **answering matchup questions IS the 9 in 9:1.** Every reply where you give value without linking the site builds karma. The rare reply where you DO link the site (because the matchup is genuinely on the page) is the legit 10%.

Concrete target for the first month:
- Aim for **~10 helpful replies per week** on r/aoe2 / AoEZone forum / official forum.
- Of those, **~1 reply per week** can naturally include a link to aoe2matchup.com — only when the matchup the user asked about is one you can show them the result for.
- **Zero** "check out my site" comments, ever. The link goes in only when it directly answers the question being asked.

---

## Reply templates by question type

Five categories cover ~80% of the questions you'll see in r/aoe2.

### Type 1: "What do I make against [civ X / unit Y]?"

Most common pattern on r/aoe2. The trap is generic answers; the win is specific stat-backed answers.

**Template:**
> Against [unit/civ], the simplest answer is [unit type]. Specific reason: [stat that drives the matchup, e.g. "they have 7 pierce armor so arrows do 1 damage"]. If they tech-switch into [common follow-up], swap to [secondary answer]. The full counter chain is [3-step plan].
>
> [If you simulated this matchup and have a number, drop it here naturally.]

**Example (real AoE2 question pattern, hypothetical):**

> **Q: "Got smoked by Mapuche Bolas Riders today. What do I make as Britons?"**
>
> Imperial Skirms. Bolas Riders die hard to Imp Skirm at scale — they have 7 range, Imp Skirm has 7 range with +bonus damage vs cav archers, and Imp Skirm is dirt cheap so you mass them faster. If they switch to Konas, your Halberdiers handle that — Konas have 0 melee armor and no Bloodlines, so Halbs absolutely shred them. The Britons combo of Longbow + Imp Skirm + Halb covers the entire Mapuche unit roster.

### Type 2: "Is [unit/civ] any good?"

These are more open-ended. The win is one specific surprising data point + one honest weakness.

**Template:**
> [Unit] is good at [specific role with hard data]. Where it falls off is [specific weakness, ideally with a number]. People underrate / overrate it because [common misconception].

**Example:**

> **Q: "Is the Tupi Blackwood Archer actually OP? I keep hearing pair-training is broken."**
>
> The pair-training is real but it's a production-rate advantage, not a damage advantage. In an equal-count fight, BWAs murder Skirms because each pair does double the work. In an equal-cost fight (which is what actually happens at scale, since both players have similar gold pools) BWAs lose to almost everything — including generic Arbalesters. So the BWA is great when you're producing-time-bottlenecked (early Castle, few Archery Ranges) and bad when you're gold-bottlenecked. Curare in Imperial supposedly helps a lot but I haven't seen it modeled yet.

### Type 3: "Who wins, X or Y?"

This is the question your site exists to answer. **This is the one type where linking the site is natural and not spammy.**

**Template:**
> [Direct answer with the win condition.] In a [count]v[count] fight at full upgrades, [winner] wins with [X] surviving and [hp%] HP remaining. The reason: [the specific stat or mechanic that decides it].
>
> *If you want to play with the matchup yourself: [link to the specific /vs/ page]*

**Example:**

> **Q: "Quick sanity check — does an Elite Cataphract beat an Elite Teutonic Knight 1v1?"**
>
> 1v1 the TK wins because of melee armor (10 vs 2) — Cata barely scratches it. But in a 30v30 the Cata wins comfortably because of trample and speed; TK is too slow to engage all of them.
>
> If you want to see the tick-by-tick: https://aoe2matchup.com/vs/Byzantines/elite_cataphract_byzantines/Teutons/elite_teutonic_knight_teutons

(That's a real URL on your site since you have 1,400+ matchup pages now.)

### Type 4: "How should I play [civ]?"

Strategy questions. Don't try to write a full guide in a comment. Pick ONE non-obvious thing.

**Template:**
> The non-obvious thing about [civ] is [insight]. Most guides will tell you [generic advice], but the actual edge is [specific thing]. In practice that means [concrete in-game behavior].

**Example:**

> **Q: "Tupi feels like they should be archer civ but I keep losing as them. What am I missing?"**
>
> You're missing the Ibirapema Warrior. The Tupi pitch in every guide is "pair-train BWAs and snowball" but the BWAs lose at equal cost to most things. The actual Tupi power unit is the Ibirapema — 90 HP, 13 attack, 100% conical trample. It hard-counters anything below ~120 HP per unit (Halbs, Knights, Eagles, Heavy Camels all melt). Use BWAs to shape the fight, Ibirapema to actually win it.

### Type 5: "Why did I lose to [comp]?"

Post-game analysis questions. The win is figuring out the actual lever, not just naming counter units.

**Template:**
> The thing that beat you wasn't [obvious unit] — it was [actual reason, often economic or tempo]. Specifically [evidence from their description]. To beat that next time, [specific change to your build].

**Example:**

> **Q: "Lost to a Muisca player going Temple Guards. I made Halbs but they did nothing. Wtf?"**
>
> Halbs only have anti-cavalry bonus damage — they do basically nothing to infantry-class units. Temple Guards have 5 melee armor, so a Halb hits them for 1 damage per swing. You needed range or a hard-counter UU. The cleanest answers: Mameluke (anti-cav UU but it has range), Teutonic Knight (just better infantry), or Aztec Jaguar Warrior (anti-infantry bonus damage, hard-counters Temple Guard). If you don't have a UU answer, mass Champions actually beats Temple Guards at equal cost — they're so cheap they overwhelm.

---

## Tone & format rules

- **Lead with the answer.** Not "Great question, so…" — just the answer.
- **Use specifics.** "5 melee armor means Halbs do 1 damage" beats "Halbs are bad against them."
- **One idea per paragraph.** Reddit eats walls of text.
- **No emojis, no signature, no "hope this helps."** AoE2 community is allergic to those.
- **Don't oversell.** If you're uncertain, say "I think" or "I'd guess" — Reddit respects honesty more than confidence.
- **If your sim contradicts community wisdom, say so plainly.** That's interesting; that's why people read.

---

## When to drop the link (and when not to)

**Drop the link when:**
- The question is literally "who wins X vs Y" and you have that exact matchup page.
- The question is "what does the data say about X" — your sim IS the data.
- Someone explicitly asks "is there a tool for this?"

**Don't drop the link when:**
- The question is about strategy/build orders/economy. Your tool doesn't help with those.
- The question is about civ design philosophy or balance. Wrong audience.
- You'd be dropping it just to drop it. People can smell it.

**The one rule:** if you remove the link from your reply, does the reply still help the person who asked? If yes → keeping the link is fine. If no → the reply isn't actually answering, you're just promoting.

---

## Where to look for questions

Since I can't scrape these in real time, you check them. ~10 minutes a day total.

**Daily (5 min):**
- r/aoe2 → sort by "New" → scan titles → look for question marks → bookmark anything you can answer
- AoE2 Discord (official server) → #questions and #strategy channels → scroll back ~30 messages

**Weekly (5 min):**
- AoEZone "Strategy Discussion" forum
- forums.ageofempires.com → II — Discussion category
- r/AgeofEmpires (smaller, less traffic, but less competition for replies)

**The bookmark workflow:**
- See a question you can answer → don't reply right away → drop the URL into our chat
- I write the reply, you paste it
- This avoids you typing a half-baked reply in 30 seconds and posting something bad

---

## What I'll do for each one you send me

Within ~5 minutes of getting a URL or screenshot, I'll give you:

1. **Draft reply** — paste-ready, in the matching template above.
2. **Sim verification** — if the question hinges on a specific matchup, I'll run the sim and put real numbers in the reply.
3. **Link decision** — I'll tell you whether the reply should include your site link, and which specific `/vs/` URL if so.
4. **Risk flags** — if the question looks like a troll, low-engagement post, or out-of-scope, I'll tell you not to bother.

---

## What I won't do

- Post under your account (I can't and shouldn't)
- Read your DMs or notifications
- Pretend to be you in conversation

The reply is yours; I'm just the typist.

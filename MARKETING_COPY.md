# Marketing copy — paste-ready

> Replace `[3 surprising results]` placeholders with actual results from your sim — see "How to fill in the blanks" at the bottom.

---

## 1. Reddit launch post — r/aoe2

**Where:** https://www.reddit.com/r/aoe2/submit
**Flair:** "Tool" or "Discussion"
**Best time to post:** Tuesday or Wednesday, 9–11 AM Eastern (peak r/aoe2 activity).

### Title
> I built a tool that simulates every AoE2 unit vs every other unit — fully upgraded, all 50 civs (including Three Kingdoms)

### Body
> Hey r/aoe2,
>
> I've spent the last few months building a battle simulator that answers the question we all argue about in chat: *"Who wins, X or Y?"*
>
> It models every unit in the game (50 civs, every unique unit including the Three Kingdoms additions — Champi Warrior, Sergeant, Temple Guard, Khitan Fire Lancer, etc.) at full upgrades, including civ bonuses and unique techs, and runs them tick-by-tick. It handles armor classes, attack delays, projectile travel, charge attacks, trample, bleed, dodge — basically every special mechanic.
>
> Three things that surprised me when I ran the round-robin:
> - **[surprising result 1]**
> - **[surprising result 2]**
> - **[surprising result 3]**
>
> It's free, no ads, no sign-up. You can pick any two units, run a 1v1, run an army fight at equal cost, or browse pre-computed rankings.
>
> Link in the comments (mods are stricter on links in post body). **Happy to take matchup requests** — drop your "I always wondered" matchup below and I'll run it and reply with the result + screenshot.

### First comment (where the link goes)
> Tool: https://aoe2matchup.com
>
> If something seems off (wrong stat, missing unit, weird sim result) please tell me — I want to fix it.

### Why this format works
- Leads with the question every player asks.
- "Three surprising results" is the hook that makes people click.
- Asking for matchup requests turns the comments section into free engagement and content for follow-up posts.
- Keeping the link in the comment is a r/aoe2 norm; top-level link posts get auto-flagged.

---

## 2. Discord drops

### Drop A — AoE2 official Discord, #content-creation or #community-creations channel
> Hey all — built an AoE2 matchup simulator I wanted to share. 50 civs, every unique unit (including Three Kingdoms) at full upgrades, simulated tick-by-tick. You pick the units, it runs the fight.
>
> Ran *Champi Warrior vs Elite Teutonic Knight* this morning, result was not what I expected.
>
> https://aoe2matchup.com — happy to take matchup requests if anyone wants me to run something specific.

### Drop B — AoEZone Discord, #strategy or #general
> Built a battle simulator that handles every unit / civ combo at full upgrades — armor classes, charge attacks, trample, bleed, all of it. Useful for "should I make X or Y" decisions before committing.
>
> https://aoe2matchup.com
>
> Would love feedback from people who care about the actual numbers.

### Drop C — Spirit of the Law / SOTL community Discord (or any creator's server)
> Long-time SOTL viewer — built a tool that basically does what his videos do but for any matchup you want. Simulates 1v1 + equal-resource army fights for any unit pair across all 50 civs.
>
> https://aoe2matchup.com
>
> Would be curious what matchups you'd want to see deeper analysis on.

### Discord etiquette tips (read before posting)
- **Lurk for a day or two first.** Read the rules and pinned messages in each server. Some have specific channels for self-promo.
- **Don't post the same message in multiple channels of the same server** — it's the fastest way to get banned.
- **Post once, then engage in the comments** — don't bump the post.
- **If asked "did you build this?" the answer is yes.** Don't pretend to be a casual sharer; people respect builders.

---

## 3. Creator outreach email — Spirit of the Law

**Subject:** Built a tool that runs the matchups from your videos — would love your eyes on it

> Hi [Name],
>
> Long-time viewer — your "How good is the [unit]?" series is the reason I started caring about AoE2 numbers in the first place.
>
> I've spent the last few months building a battle simulator that does what your videos do, but on demand for any matchup. 50 civs, every unique unit (including Three Kingdoms), all units fully upgraded, simulated tick-by-tick. It handles armor classes, attack delays, projectile travel, charge attacks, trample, bleed — every mechanic I could find documented.
>
> A few results that surprised me when I ran the round-robin:
> - [surprising result 1]
> - [surprising result 2]
>
> I'd love your feedback, even just brutal "this is wrong because…". And if you ever want to verify a matchup for a video without setting up scenarios in the editor, the tool is yours to use:
>
> https://aoe2matchup.com
>
> No ask, no agenda — just wanted the person whose channel inspired the project to know it exists.
>
> Thanks for years of great content,
> [Your name]

### How to send
- SOTL's contact info is in his YouTube "About" tab. Most creators list a business email there.
- **If you don't see an email, check his Twitter/X DMs or Patreon.**
- **Send Tuesday morning.** Higher open rates than Mondays or weekends.
- **Don't follow up for at least two weeks.** If no reply after that, send one short bump: *"Just bumping this in case it got buried — no pressure either way."* Then drop it.

### Variants for other creators (swap out the personalization)
- **T90 / Hera / Viper:** Lead with "I noticed you got a question about [matchup] in your last cast — I built a tool that answers exactly that kind of question."
- **MembTV / Resonance22:** Lead with "Your [video title] was the closest thing I'd seen to what I built."
- **AgeOfNoob:** Lighter tone — "Built a thing, thought you'd find it funny that the [unit] actually loses to [other unit]."

---

## 4. Bonus: meta description + OG description (already wired into the site code)

These are now live in `webapp/templates/` after the SEO update. You don't need to do anything — they show up automatically when someone shares your link on Reddit, Discord, or Twitter.

---

## How to fill in the "[surprising results]" blanks

Open your live simulator and run these matchups. Whichever 3 produce the most "huh, didn't expect that" outcomes, use those.

| Matchup | Why it's interesting |
|---|---|
| Champi Warrior vs Teutonic Knight | New unit vs classic tank |
| Sergeant vs Berserk | Two melee uniques nobody simulates |
| Goth Huskarl vs Britons Longbowman | Anti-archer vs archer, big "test of theory" matchup |
| Elite Cataphract vs Halberdier | Classic counter test |
| Khitan Fire Lancer vs Paladin | New mounted DLC unit vs gold-standard cav |
| Shotel Warrior (mass) vs Samurai (mass) | Two raw-DPS infantry uniques |

Run each, screenshot the result, and pick the 3 most surprising for your post. **Bonus tip:** the screenshot of the canvas mid-fight makes a great image for the post — Reddit's algorithm favors posts with images.

---

## Quick checklist before you post anything

- [ ] Deploy the latest code to Railway (so `/robots.txt`, `/sitemap.xml`, `/vs/...` pages and SEO meta tags actually go live on aoe2matchup.com)
- [ ] Replace `[surprising result N]` placeholders with real results from your sim
- [ ] Take 1 good screenshot of a mid-fight canvas (for the Reddit post + OG image)
- [ ] Save that screenshot as `webapp/static/img/og-default.png` (it'll auto-show on link previews)
- [ ] Optional: point `www.aoe2matchup.com` at Railway too (currently only the apex `aoe2matchup.com` is configured)

---

## What to do *after* posting

- **First 2 hours:** sit on the post. Reply to every comment, even the harsh ones. This boosts the post in r/aoe2's algorithm and earns you community trust.
- **Next 24 hours:** every matchup request someone leaves → run it, screenshot, reply with the result. This is free content + free engagement.
- **Day 2:** save the best questions/results and turn them into the next post (e.g. "You asked, I simulated — top 5 matchup requests from yesterday's thread"). That's your week-2 content done.

# Marketing

All assets and plans for promoting aoe2matchup.com.

## Structure

```
marketing/
├── README.md                    ← this file (index)
├── launch-plan.md               ← Reddit launch post + Discord drops + creator outreach
├── reply-playbook.md            ← five reply templates by question type, tone rules,
│                                  9:1 self-promo guidance
├── responded-threads.json       ← dedup list of threads we've already replied to;
│                                  read this before drafting any new reply
├── reports/                     ← deep-dive analysis posts (one every ~2 weeks)
│   └── 2026-04-30-new-civs-community-vs-sim.md
│       (Tupi/Muisca/Mapuche: community wisdom vs simulation results)
│
└── replies/                     ← drafted replies to specific live threads
    ├── 2026-04-30-aoe2-forum-batch.md  (3 forum replies — Tupi counter, PUP-May, civ balance)
    └── 2026-05-01-reddit-batch.md      (2 reddit replies — Mapuche vs BBC, Portuguese OG)
```

## Scout & reply workflow

There's a global skill installed at `~/.claude/skills/aoe2matchup-marketing-scout/SKILL.md`
that codifies the full process: how to scout Reddit (JSON API via `urllib`) and the AoE2
forum (browser only — Reddit is blocked), how to dedup against `responded-threads.json`,
how to choose simulations to run, and how to write replies in casual Reddit-native prose
without sounding like an AI.

When asking Claude to scout for new threads, it should auto-load that skill.

## Naming convention

- **Reports:** `YYYY-MM-DD-short-slug.md` — date is the day the report was finalized.
- **Replies:** `YYYY-MM-DD-source-batch.md` — date + which platform was scouted.

## Workflow

1. **Every ~2 weeks:** I write a new deep-dive report in `reports/`. You post it to r/aoe2 and the official AoE2 forum.
2. **Daily, ~10 min:** You scout r/aoe2 New + AoE2 Discord for question threads. Paste URLs/screenshots to me.
3. **Within ~5 min:** I draft replies and add them to a new file in `replies/`.
4. **Weekly:** I scout forums.ageofempires.com (Reddit + Discord are blocked from my browser, so you handle those).

See `reply-playbook.md` for the templates and `launch-plan.md` for the bigger-picture strategy.

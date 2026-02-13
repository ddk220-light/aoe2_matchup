# Webapp Architecture Skill — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a reference skill that helps future Claude instances find the right files, understand data flow, and not miss sync dependencies when modifying the AoE2 webapp.

**Architecture:** A project-local skill at `.claude/skills/webapp-architecture/SKILL.md` following the writing-skills TDD cycle: baseline test (RED) → write skill (GREEN) → verify and refactor (REFACTOR). The skill is a Reference type — tested via retrieval/application scenarios with subagents.

**Tech Stack:** Markdown skill file, Claude Code subagent testing

---

### Task 1: Create skill directory

**Files:**
- Create: `.claude/skills/webapp-architecture/` (directory)

**Step 1: Create the directory**

```bash
mkdir -p .claude/skills/webapp-architecture
```

**Step 2: Commit**

```bash
git add .claude/skills/
git commit -m "chore: create webapp-architecture skill directory"
```

---

### Task 2: RED — Run baseline scenario without skill

**Purpose:** Document how a fresh Claude instance handles a modification task WITHOUT the skill. This establishes what goes wrong so we know what the skill needs to fix.

**Step 1: Run baseline test scenario**

Launch a subagent with this prompt (no skill loaded):

> "In the AoE2 unit analyzer project at /Users/deepak/AI/aoe2unitanalyzer, I want to add a new combat property called `attack_speed_bonus` that gives certain units faster attack speed. Don't write any code — just tell me: (1) which files need to be modified and in what order, (2) what sync dependencies exist, and (3) how data flows from the database to the frontend for this property."

**Step 2: Document baseline behavior**

Record in a scratch note:
- Did the agent find ALL required files? (generate_main_db.py, app.py, simulation.py, simulate.html)
- Did it identify sync rules? (UNIT_LINES duplication, NAME_TO_ICON, etc.)
- Did it understand the config override priority?
- What did it miss or get wrong?

**Do NOT commit baseline results** — they're ephemeral test output.

---

### Task 3: GREEN — Write the skill

**Files:**
- Create: `.claude/skills/webapp-architecture/SKILL.md`

**Step 1: Write SKILL.md with all 6 sections**

Write the full skill file with these sections (content detailed in design doc at `docs/plans/2026-02-13-webapp-architecture-skill-design.md`):

1. **YAML Frontmatter** — name + description (triggering conditions only, no workflow summary)
2. **Architecture Overview** — core files, data flow summary, 3 databases (~150 words)
3. **Feature Map** — table: feature → backend/frontend/data files
4. **Sync Rules** — 6 hard sync rules as checklist + soft sync notes
5. **Modification Recipes** — 5 recipes: new sim mechanic, new unit/civ, new API endpoint, damage calc change, frontend UI change
6. **Data Flow Details** — combat unit flow, config override priority, matchup advisor flow, battle scores flow

**Key constraints:**
- Total size: 600-800 words
- Description must NOT summarize workflow (CSO rule from writing-skills)
- Use scannable format: tables, bullet lists, short code blocks
- Include keywords for Claude search: file names, function names, error-prone areas

**Step 2: Commit**

```bash
git add .claude/skills/webapp-architecture/SKILL.md
git commit -m "feat: add webapp-architecture reference skill"
```

---

### Task 4: GREEN — Verify skill improves behavior

**Step 1: Run same scenario WITH skill loaded**

Launch a subagent with the same prompt as Task 2, but this time the skill will be available in the project's `.claude/skills/` directory.

**Step 2: Compare results**

Check against baseline:
- Does the agent now find ALL required files?
- Does it identify sync rules it previously missed?
- Does it understand config override priority?
- Is the data flow description more accurate?

**Step 3: If skill doesn't improve behavior, go back to Task 3 and revise**

---

### Task 5: REFACTOR — Run additional scenarios and close loopholes

**Step 1: Run a second test scenario (different task type)**

> "I want to add a new civilization to the webapp. What files need to change and in what order?"

**Step 2: Run a third test scenario (frontend-focused)**

> "I need to add a new column to the unit rankings table on the /units page. Walk me through what to modify."

**Step 3: Identify gaps**

For each scenario, check:
- Did the skill help the agent find the right files?
- Were any sync rules missed?
- Was any data flow misunderstood?

**Step 4: Update SKILL.md to close any gaps found**

**Step 5: Commit**

```bash
git add .claude/skills/webapp-architecture/SKILL.md
git commit -m "refactor: improve webapp-architecture skill based on testing"
```

---

### Task 6: Final commit and cleanup

**Step 1: Verify skill file is well-formed**

- YAML frontmatter has only `name` and `description`
- Description starts with "Use when..."
- Total under 1024 chars for frontmatter
- Skill body under 800 words

**Step 2: Final commit if any changes**

```bash
git add .claude/skills/webapp-architecture/SKILL.md
git commit -m "chore: finalize webapp-architecture skill"
```

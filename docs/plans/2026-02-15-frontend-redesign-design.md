# Frontend Redesign Design

Date: 2026-02-15

## Goal

Redesign the AoE2 Unit Analyzer webapp frontend for visual consistency, better code architecture, and improved navigation. Keep the medieval identity but modernize the execution.

## Current State

- 7 HTML templates, 9,760 total lines, ALL inline CSS/JS
- Zero external CSS/JS files
- 3 different color schemes across pages
- ~800 lines of duplicated JS (NAME_TO_ICON x4, UNIQUE_BUILDING x2, ENABLED_CIVS x2)
- Inconsistent navigation (different links/labels per page)
- Font inconsistencies (Inter vs Open Sans vs system fonts)
- No shared components or template inheritance

## Architecture

### File Structure

```
webapp/
  templates/
    base.html              # Shared layout: <head>, nav, footer
    simulate.html          # Battle Sim (homepage at /)
    matchup_advisor.html
    index.html             # Unit Rankings
    civ_select.html
    civ_detail.html
  static/
    css/
      base.css             # Variables, reset, typography, nav, footer, cards, buttons, modals
      simulate.css
      rankings.css
      matchup.css
      civ-select.css
      civ-detail.css
    js/
      constants.js         # NAME_TO_ICON, UNIQUE_BUILDING, ENABLED_CIVS
      simulate.js          # Canvas + BattleUnit class
      rankings.js          # Table sorting, filtering, hover cards
      matchup.js           # Matchup advisor logic
      civ-select.js
      civ-detail.js
```

### Template Inheritance

`base.html` provides:
- `<head>` with meta tags, Google Fonts link, base.css
- Navigation bar
- `{% block page_css %}` for page-specific CSS
- `{% block content %}` for page content
- `{% block page_js %}` for page-specific JS
- Footer (minimal)

Pages use `{% extends 'base.html' %}` and only define their blocks.

## Typography

| Role | Font |
|------|------|
| Display headings (h1) | Cinzel 700 |
| Section headings (h2, h3) | Cinzel 600 |
| Body text, UI | Alegreya Sans 400/500/600 |
| Debug panels | JetBrains Mono 400 |

Google Fonts URL:
```
fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Alegreya+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap
```

## Color Palette

```css
:root {
    --gold:            #c9a84c;
    --gold-light:      #dbb960;
    --gold-dark:       #8b6914;
    --gold-glow:       rgba(201, 168, 76, 0.15);
    --bg-deep:         #120d07;
    --bg:              #1e1610;
    --bg-warm:         #2a1f14;
    --bg-hover:        #342618;
    --border:          #3d2e1e;
    --border-light:    #5a4228;
    --text:            #e8dcc8;
    --text-muted:      #a89878;
    --text-dim:        #6d5d48;
    --red-accent:      #7a1a1a;
    --red-deep:        #3a0e0e;
    --green:           #5a9a3a;
    --red:             #a83030;
    --team1:           #c0392b;
    --team2:           #2980b9;
}
```

Unified across ALL pages (matchup advisor brought in line with medieval theme).

## Background

CSS noise texture + radial vignette (no external images):

```css
body {
    background: var(--bg-deep);
    background-image:
        radial-gradient(ellipse at center, var(--bg) 0%, var(--bg-deep) 70%);
}
```

## Elevation System

```
Level 0:  var(--bg-deep)   page background
Level 1:  var(--bg)        main content areas
Level 2:  var(--bg-warm)   cards, panels
Level 3:  var(--bg-hover)  hover states
```

Cards: 1px var(--border), border-radius 8px, box-shadow 0 2px 8px rgba(0,0,0,0.3). Hover: border to var(--gold-dark), faint gold glow.

## Navigation

Persistent top bar on all pages:

```
[ AoE2 Analyzer ]   Battle Sim   Matchup Advisor   Rankings   Database v
                                                               └ Civilizations
```

- Left: app name (links to /)
- Main links: Battle Sim, Matchup Advisor, Rankings
- Database dropdown: Civilizations
- Active page: gold underline indicator
- Sticky on scroll with backdrop blur

## Routes

| Route | Template | Notes |
|-------|----------|-------|
| `/` | simulate.html | Battle Sim homepage |
| `/simulate` | redirect to `/` | Backward compat |
| `/units` | index.html | Unit Rankings |
| `/matchup-advisor` | matchup_advisor.html | |
| `/civilizations` | civ_select.html | Renamed from /civ |
| `/civilizations/<name>` | civ_detail.html | Renamed |
| `/civ` | redirect to `/civilizations` | Backward compat |
| `/civ/<name>` | redirect to `/civilizations/<name>` | Backward compat |

### Removed

- `/review` route and review.html template
- All `/api/comments/*` routes and associated backend code
- Comment submission UI (if any in civ_detail.html)

## What Does NOT Change

- Backend simulation engine (simulation.py)
- All non-comment API endpoints
- Database schema and queries
- Data extraction/analysis pipeline
- Functional behavior of each page
- Canvas-based battle visualization

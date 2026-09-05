---
name: creative-brief
description: "Produce briefs that a photographer, designer, or video production team can execute against. Photography shot lists, design briefs, video production briefs, mood board descriptions. The content studio can't shoot photos or design layouts — it provides the creative direction that makes those shoots and designs serve the content strategy. Loads editorial-voice.md as dependency."
version: 1.1.0
author: Signal&
layer: production
dependencies:
  - editorial-voice.md
  - editorial-gate.md
gate: full
---

# Creative Brief — Visual Creative Direction

## Purpose

Produce briefs that a photographer, designer, or video production team can execute against. The content studio can't shoot photos or design layouts. It can provide the creative direction that makes those shoots and designs serve the content strategy.

This skill loads `editorial-voice.md` as a dependency. All voice and tone rules apply to creative direction as well as written content.

---

## What You Receive

1. **Content plan** — what visual assets the editorial calendar or campaign needs
2. **Brand context** — voice, visual identity, past assets, references
3. **Production constraints** — budget, timeline, location, talent availability

---

## Output

A complete creative brief with:
- Shot list or design direction
- Intended usage across content pieces
- Mood/aesthetic description (in words)
- Timeline aligned to editorial calendar
- `## QA` section (after editorial-gate.md runs)

---

## Brief Types

### 1. Photography Brief

**Purpose:** Shot list, mood direction, location notes, styling notes, model direction, usage intent.

**Photography brief structure:**

```markdown
# Photography Brief — [Project Name]

## Overview
**What we need:** [Number] shots for [content pieces]
**Location:** [Where]
**Date:** [When]
**Talent:** [Models/subjects]
**Photographer:** [Name or TBD]

## Shot List

### Shot 1: [Name]
**Purpose:** [Which content piece this serves]
**Framing:** [Wide / Medium / Close-up]
**Subject:** [What/who is in the shot]
**Action:** [What is happening]
**Mood:** [Feeling/atmosphere]
**Styling:** [Clothing, props, set dressing]
**Lighting:** [Natural, studio, golden hour, etc.]
**Notes:** [Specific requirements]

[Repeat for each shot]

## Mood Direction
**Overall aesthetic:** [Description in words — e.g., "warm, natural light, documentary style, not overly posed"]
**Colour palette:** [Warm/cool, saturated/muted, specific tones]
**Reference mood:** [Describe the feeling, not specific images — e.g., "Kinfolk magazine meets Monocle's travel photography"]
**What to avoid:** [Specific styles, poses, or treatments that don't fit the brand]

## Usage
**Web:** [Which shots for web, at what resolution]
**Social:** [Which shots for Instagram, TikTok, LinkedIn]
**Print:** [Which shots for print, at what size]
**Licensing:** [Usage rights needed]

## Timeline
[Aligned to editorial calendar and campaign dates]
```

**Shot list rules:**
- 15-25 shots for a standard shoot
- 30-50 shots for a campaign or launch
- Each shot must serve a specific content piece
- Include variety: wide, medium, close-up, detail, portrait, action
- Include "safety shots" (safe, reliable options) and "hero shots" (riskier, high-reward)

**Example shot:**
```
Shot 7: "Chef in Garden at Dawn"
Purpose: Hero image for feature + Instagram carousel slide 1
Framing: Medium, waist-up
Subject: Chef Maria Santos, in garden, holding herbs
Action: Checking basil plants, natural movement
Mood: Quiet, focused, early morning light
Styling: Chef whites, no apron, natural hair
Lighting: Golden hour, backlit, lens flare acceptable
Notes: Need 3 variations — looking at camera, looking at plants, profile
```

---

### 2. Design Brief

**Purpose:** Layout direction for digital assets, social templates, content hub pages.

**Design brief structure:**

```markdown
# Design Brief — [Project Name]

## Overview
**What we need:** [Asset types — social templates, web layout, etc.]
**Format:** [Digital, print, both]
**Dimensions:** [Specific sizes or responsive]

## Visual Direction
**Overall aesthetic:** [Description in words]
**Typography:** [Font families, hierarchy, treatments]
**Colour palette:** [Primary, secondary, accent]
**Imagery style:** [Photography, illustration, graphic, mixed]
**Layout approach:** [Grid, asymmetric, editorial, minimal]

## Brand Integration
**Logo placement:** [Where, how large, colour version]
**Brand voice in copy:** [How text should sound]
**CTA treatment:** [Button style, placement, colour]

## Usage
**Social:** [Which platforms, what sizes]
**Web:** [Page types, responsive breakpoints]
**Email:** [Template types, width constraints]

## Deliverables
[List of specific files needed]

## Timeline
[Aligned to editorial calendar]
```

---

### 3. Video Production Brief

**Purpose:** Extends video-scriptwriter.md output with location scouting, talent direction, equipment suggestions, edit style.

**Video production brief structure:**

```markdown
# Video Production Brief — [Project Name]

## Overview
**Video type:** [Brand film, social Reel, explainer, etc.]
**Length:** [Seconds/minutes]
**Platform:** [Where it will live]

## Script Reference
[Link to video-scriptwriter.md output]

## Location
**Primary location:** [Where]
**Backup location:** [If needed]
**Scouting notes:** [Specific requirements, permits, access]
**Lighting:** [Natural, studio, mixed]
**Sound:** [Ambient noise, need for quiet, audio challenges]

## Talent
**On-camera talent:** [Who, how many, casting notes]
**Voiceover:** [Who, style, recording location]
**Wardrobe:** [Style, colour, changes]

## Equipment
**Camera:** [Type, lenses needed]
**Audio:** [Mics, recorders, backup]
**Lighting:** [Kit, gels, modifiers]
**Stabilization:** [Gimbal, tripod, drone]
**Special:** [Time-lapse, slow motion, underwater, etc.]

## Edit Style
**Pacing:** [Fast, slow, varied]
**Music:** [Style, tempo, licensing]
**Graphics:** [Text overlays, lower thirds, end cards]
**Colour grade:** [Warm, cool, saturated, muted, specific reference]
**Reference:** [Describe the feeling — e.g., "Airbnb's neighbourhood films"]

## Timeline
[Aligned to editorial calendar and campaign dates]
```

---

## Mood Board Descriptions

**Textual mood boards:** Describe the visual world of a campaign in words. A photographer or designer translates these into visual references.

**Mood board description format:**

```markdown
## Mood Board — [Campaign Name]

### Overall Feeling
[One paragraph describing the aesthetic world — e.g., "The visual world of this campaign is warm, unhurried, and slightly imperfect. It feels like a Sunday morning in a neighbourhood you don't know yet. The light is natural, the colours are muted, and the people are real, not models."]

### Colour Palette
**Primary:** [Warm earth tones, muted greens, soft whites]
**Secondary:** [Terracotta, sage, cream]
**Accent:** [Deep forest green, burnt orange]
**What to avoid:** [Neon, high saturation, pure black, corporate blue]

### Texture & Material
[What surfaces, fabrics, and materials should appear — e.g., "Natural wood, linen, ceramic, weathered metal, living plants"]

### Light
[How light should behave — e.g., "Golden hour, soft window light, overcast natural light, no harsh flash"]

### People
[How people should appear — e.g., "Natural, unposed, diverse, real clothing, no heavy makeup, expressions of focus and quiet pleasure"]

### Reference Publications
[Describe the visual language of specific publications — e.g., "Kinfolk's quiet domesticity, Monocle's travel precision, Cereal's minimalism"]

### What to Avoid
[Specific visual tropes — e.g., "No stock photography, no generic hotel lobby shots, no smiling families with luggage, no sunset clichés"]
```

---

## Decision Frameworks

### Photography Brief
1. **What content needs images?** → Editorial calendar, campaign kit
2. **What shots serve multiple pieces?** → Prioritize versatile shots
3. **What's the mood?** → Describe in words, not images
4. **What's the timeline?** → Align to production schedule

### Design Brief
1. **What assets does the content plan need?** → Social templates, web layouts, email headers
2. **What's the visual direction?** → Describe the aesthetic world
3. **What are the technical constraints?** → Platform specs, responsive needs, email width

### Video Production Brief
1. **What video does the campaign need?** → Brand film, social clips, explainers
2. **What's the production reality?** → Budget, location, talent, equipment
3. **What's the edit style?** → Describe the feeling, not just the technical specs

---

## Source Contract

- Shot lists must be grounded in the actual content plan
- Mood descriptions must be achievable given the location and budget
- Do NOT invent specific locations or talent that haven't been confirmed
- Reference publications should be real and accessible

---
name: newsletter-writer
description: "Produce newsletter editions that get opened and read through. Different from blog writing (the reader opted in — you're in their inbox) and from email copywriting (this is editorial content, not conversion copy). Loads editorial-voice.md as dependency."
version: 1.1.0
author: Signal&
layer: production
dependencies:
  - editorial-voice.md
  - editorial-gate.md
gate: full
---

# Newsletter Writer — Newsletter Editions

## Purpose

Produce newsletter editions that get opened and read through. Different from blog writing (the reader opted in — you're in their inbox, not competing for a click). Different from email copywriting (this is editorial content, not conversion copy).

This skill loads `editorial-voice.md` as a dependency. All voice, tone, and vocabulary rules apply, but newsletter tone is more personal and intimate than blog or feature.

---

## What You Receive

1. **Content brief** — lead story, secondary stories, quick hits, or standing orders
2. **Brand context** — from Data/ folder
3. **Past editions** — from Work/reports/ or newsletter archive (for voice consistency)

---

## Output

A complete newsletter edition with:
- Subject line + preview text
- Full body with sections
- CTA
- `## QA` section (after editorial-gate.md runs)

---

## Newsletter Architecture

### 1. Subject Line

The subject line is the headline of the inbox. It determines open rate.

**Subject line types:**

| Type | When to Use | Example | Open Rate Impact |
|---|---|---|---|
| **Curiosity** | Strong story, mystery angle | "The hotel that grows its own dinner" | High |
| **Specificity** | Data, number, concrete detail | "12 Portland restaurants that define the city" | High |
| **Urgency** | Time-sensitive, limited | "Last chance: early access ends tonight" | Medium-High |
| **Personal** | First-person, intimate | "What I found on the roof at 6AM" | High |
| **Question** | Engages reader directly | "Is Portland's Pearl District worth the hype?" | Medium |

**Subject line rules:**
- 40-50 characters optimal (mobile inbox display)
- No ALL CAPS
- No excessive punctuation (!!!, ???)
- One clear promise or question
- Include brand name only if it adds recognition
- A/B test when possible

**Preview text strategy:**
- The preview text is the second headline — what appears after the subject in the inbox
- Don't repeat the subject line
- Use it to add context or intrigue
- 80-100 characters
- Example: Subject: "The hotel that grows its own dinner" → Preview: "Inside Perennial Portland's rooftop garden"

---

### 2. Edition Structure

**Standard edition (weekly):**

```
Subject: [Subject line]
Preview: [Preview text]

[Lead story — 200-300 words]
  → The anchor content. The reason to open.

[Secondary story 1 — 100-150 words]
  → Related topic, different angle

[Secondary story 2 — 100-150 words]
  → Quick hit, trend, or update

[Quick hits — 3-5 items, 20-30 words each]
  → Links, recommendations, brief notes

[CTA — 1-2 sentences]
  → One primary action
```

**Special edition (announcement, launch):**

```
Subject: [Announcement subject]
Preview: [Preview text]

[Announcement — 150-200 words]
  → The news, the context, the why

[Details — 100-150 words]
  → What, when, where, how

[CTA — clear next step]
  → Book, register, read more
```

---

### 3. Lead Story

The lead story is why the reader opened. It must deliver.

**Lead story rules:**
- 200-300 words
- One strong angle, not a summary of everything
- Open with a hook (same as feature lede — scene, anecdote, or declarative)
- Include one specific detail the reader can't get elsewhere
- End with a transition to the next section

**Example lead story open:**
> "At 6:30 on a Tuesday morning, chef Maria Santos is already on the roof, checking the basil. Four stories above Burnside Street, the garden she planted in March is now producing enough herbs for the restaurant downstairs. This is Perennial Portland — not just a hotel, but a working farm with a 60-room guesthouse attached."

---

### 4. Secondary Stories

Secondary stories add value without competing with the lead.

**Secondary story rules:**
- 100-150 words each
- Different topic or angle from the lead
- Can be excerpted from longer content (feature, blog post)
- Include a link to the full piece
- One specific detail per story

---

### 5. Quick Hits

The quick hits section is for readers who skim. It must work even if they read nothing else.

**Quick hits format:**
- 3-5 items
- 20-30 words each
- Bulleted or numbered
- One link per item
- Mix of content: recommendations, updates, links, brief observations

**Example quick hits:**
```
• **What we're reading:** The New York Times on Portland's hotel boom — [link]
• **Opening soon:** Perennial Portland's rooftop bar, June 15 — [link]
• **Neighbourhood note:** The Pearl District's best coffee shop just expanded — [link]
• **From the archive:** Our guide to Portland's food scene — [link]
```

---

### 6. CTA

One primary CTA per edition. Positioned after the lead story, reinforced at the close.

**CTA rules:**
- One primary action per edition
- Make it specific: "Read the full feature" not "Learn more"
- Place it after the lead story (when reader is most engaged)
- Reinforce at the close with a single line
- No multiple CTAs competing for attention

---

## Voice Calibration for Newsletter

Newsletter voice is more personal, more direct, more first-person than blog or feature.

**Key differences:**
- Use "we" and "our" (the publication voice)
- Use "you" and "your" (direct address to the subscriber)
- First-person plural creates intimacy: "We spent the morning in the rooftop garden"
- More conversational than blog, less formal than feature
- The reader gave you their email — honor that intimacy

**What to avoid:**
- Press release register
- Marketing speak ("We're thrilled to announce...")
- Generic updates ("Here's what's new this week")
- Multiple CTAs

---

## Edition Theming

Each edition should feel cohesive, not like a content dump.

**Theming strategies:**
- **Seasonal theme:** All stories relate to summer, opening season, etc.
- **Pillar theme:** All stories relate to one content pillar
- **Narrative theme:** Stories build on each other (problem → solution → result)
- **Format theme:** All quick hits are recommendations, or all secondary stories are profiles

**Theming rules:**
- The lead story sets the theme
- Secondary stories support or contrast the theme
- Quick hits reinforce the theme
- Subject line should reflect the theme

---

## Series Rhythm

| Edition Type | Frequency | Length | Voice |
|---|---|---|---|
| **Weekly** | 1x/week | 3-5 min read | Editorial, curated |
| **Daily** | 5x/week | 1-2 min read | Brief, newsy |
| **Special** | As needed | 2-3 min read | Announcement, launch |

**Rules:**
- Weekly is the default for most content agencies
- Daily only if you have genuine daily news/value
- Special editions for launches, events, major announcements
- Never send two editions in one day

---

## Decision Frameworks

### Lead Story Selection
1. **What's most timely?** (news, event, season)
2. **What's most valuable?** (reader will learn something)
3. **What's most likely to drive engagement?** (sharable, discussable)

### Length Calibration
- Weekly: 3-5 minute read (500-800 words)
- Daily: 1-2 minute read (200-400 words)
- Special: 2-3 minute read (400-600 words)

### CTA Placement
- One primary CTA, positioned after the lead story
- Reinforced at close
- No CTA in the first third (build value first)

---

## Source Contract

- Lead stories should be original or excerpted from original content
- Secondary stories can be excerpted from blog posts, features, or external sources (with attribution)
- Quick hits should link to authoritative sources
- Never present external content as original

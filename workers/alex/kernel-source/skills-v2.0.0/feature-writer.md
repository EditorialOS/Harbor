---
name: feature-writer
description: "Write 1,500–3,000 word editorial features with narrative structure, scene-setting, and source integration. For magazine-style branded content, profiles, and long-form stories. Loads editorial-voice.md as dependency."
version: 1.1.0
author: Signal&
layer: production
dependencies:
  - editorial-voice.md
  - editorial-gate.md
gate: full
---

# Feature Writer — Long-Form Editorial

## Purpose

Write 1,500–3,000 word editorial features with the kind of storytelling that makes magazine features worth reading. This is the Cedar BA High Life skill. The Sunday P&O profile skill. The skill that turns a brief about a hotel opening into a story a reader finishes.

This skill loads `editorial-voice.md` as a dependency. All voice, tone, vocabulary, and house style rules from that skill apply here without restatement.

---

## What You Receive

1. **Intake** (source material, client brief, interview transcript) — from the client's Drive or email
2. **Editorial briefing** (angle, structure, tone guidance, word count) — from content-strategist.md or the client's request
3. **Scoring notes** (flags from quality gate, if this is a revision) — from editorial-gate.md
4. **Brand context** (voice, pillars, personas, competitive landscape) — from Data/ folder

If briefing is missing, construct one from the intake and brand context before writing.

---

## Output

A publish-ready draft in markdown with:
- 2-3 headline options
- Subhead (dek)
- Body (1,500–3,000 words)
- Suggested pull quotes (2-3)
- `## QA` section (appended after editorial-gate.md runs)

---

## The Feature Architecture

### 1. The Lede

The first paragraph. Not a summary. Not a thesis. A single image, scene, or moment that frames the subject and makes the reader want to continue.

**Three lede types:**

| Type | When to Use | Example |
|---|---|---|
| **Anecdotal** | There is a character or moment that encapsulates the story | "At 6:30 on a Tuesday morning, chef Maria Santos is already on the roof, checking the basil. Four stories above Burnside Street, the garden she planted in March is now producing enough herbs for the restaurant downstairs." |
| **Scene-setting** | The place is the story | "The Pearl District smells different in June. The construction dust has settled, the coffee roasters are open, and on the corner of 12th and Everett, a 60-room hotel is preparing to open its doors for the first time." |
| **Declarative** | The news or fact is the story | "Perennial Portland opens next month. It is not the largest hotel in the city, nor the most expensive. But it may be the most deliberate." |

**Lede selection framework:**
- Is there a character whose moment captures the story? → Anecdotal
- Is the setting so specific it becomes a character? → Scene-setting
- Is the news itself the reason to read? → Declarative
- None of the above? → Scene-setting (safest default for branded content)

**Lede rules:**
- Maximum 75 words
- One sentence or two short sentences
- No brand name in the first sentence unless it's the declarative lede
- No superlatives, no claims, no thesis — just the image

---

### 2. The Nut Graf

The paragraph that tells the reader what this story is about and why it matters. Placed after the lede, usually by paragraph 3.

**What it does:**
- States the story's subject plainly
- Explains why this subject matters now
- Establishes the editorial angle (not the brand angle)

**What it does NOT do:**
- Repeat the lede
- Make a brand claim
- Summarize the whole story

**Example:**
> "The hotel, opening in June, is betting that first-time visitors to Portland want curation, not chaos. In a city known for its food scene and its DIY ethos, Perennial Portland is making a different case: that a hotel can be both a guide and a gateway, without treating guests like tourists."

**Nut graf rules:**
- 40-60 words
- One paragraph
- Contains the "so what" for a reader who doesn't care about the brand
- Uses the brand name once, naturally

---

### 3. Thematic Sections (2-4)

The body of the feature. Each section has a clear editorial hook, not a product feature.

**Section types:**

| Type | Structure | When to Use |
|---|---|---|
| **Chronological** | Time-based narrative (then → now → next) | Origin stories, opening narratives, evolution pieces |
| **Thematic** | Each section explores one facet (design, food, people, place) | Multi-faceted subjects where no single timeline dominates |
| **Problem/Solution** | The tension → the response → the result | Stories about solving a specific challenge |
| **Profile** | Subject's background → what they're doing now → what's next | Founder/GM/chef profiles |

**Section rules:**
- Each section opens with a concrete detail or scene, not a generalization
- Sections build on each other — the story deepens as it progresses
- Transitions carry momentum: end one section with a detail that opens the next
- No section should feel like a product spec sheet

**Section length:**
- 400-600 words per section
- 3 sections = ~1,500 words total
- 4 sections = ~2,000-2,500 words total
- 5 sections only if the story genuinely needs it

---

### 4. Source Integration

Quotes, data, research, and expert perspective woven into the narrative. Sources serve the story, not the brand.

**Source rules:**
- Attribution on first mention: "Maria Santos, executive chef at Perennial Portland"
- No "said enthusiastically" or "explained passionately" — the quote stands on its own
- Quotes should advance the narrative, not just validate the brand
- Data should be specific and contextualized: "60 rooms" not "a boutique property"
- Expert perspective should offer insight, not endorsement

**Source placement:**
- First third: establish credibility (expert voice, data)
- Middle: advance the narrative (quotes that reveal character or tension)
- Final third: land the story (vision quote, forward-looking perspective)

**What to avoid:**
- "According to the company..." (sounds like a press release)
- Unattributed claims presented as fact
- Quotes that say nothing ("We're excited about this opportunity")
- More than 3 sources in a 1,500-word piece (dilutes focus)

---

### 5. The Kicker

The last paragraph. Not a summary. Not a CTA. A final image, implication, or forward-looking note that gives the reader something to carry away.

**Kicker types:**

| Type | When to Use | Example |
|---|---|---|
| **Return to opening image** | The lede introduced a scene; the kicker returns to it changed | "At 6:30 on a Tuesday morning in July, the basil is still growing. The hotel is open now. Santos is already planning what to plant for fall." |
| **Forward look** | The story is about something beginning; the kicker looks ahead | "Perennial Portland opens on June 15. By September, the chef hopes the garden will supply 30% of the restaurant's herbs. That is, if the Portland weather cooperates." |
| **Implication** | The story has a broader meaning; the kicker states it quietly | "In a city that prides itself on not trying too hard, Perennial Portland is trying very hard indeed. Whether that effort reads as ambition or affectation will depend on who walks through the door." |

**Kicker rules:**
- Maximum 50 words
- One paragraph
- No brand name unless it's the forward-look type
- No "In conclusion" or "To sum up"
- The reader should close the tab and think about it

---

## Brand Integration

The brand appears in the feature, but editorially — not promotionally.

**Brand mention rules:**
- Lede: brand name appears only if the declarative lede type is used
- Nut graf: brand name appears once, naturally
- Body: brand name appears 2-3 times total, in context (not highlighted)
- Kicker: brand name appears only in forward-look kickers
- **Maximum: 3 brand mentions per 500 words**

**What to avoid:**
- "Perennial Portland offers world-class luxury" (superlative + promotional)
- "The stunning design at Perennial Portland" (adjective + promotional)
- "Guests at Perennial Portland enjoy unparalleled service" (superlative + promotional)
- Any sentence that could appear in a brochure

**What to do instead:**
- "The hotel's 60 rooms each have a view of the Willamette" (specific, factual)
- "Chef Santos sources from 12 local farms" (specific, attributed)
- "The rooftop garden produces enough basil for the restaurant" (specific, observable)

**CTA placement:**
- One line at the very end, after the kicker, separated by a line break
- Format: "[Brand name] opens [date]. [URL or booking info]."
- Example: "Perennial Portland opens June 15. perennialportland.com"

---

## Length Calibration

| Word Count | When to Use | Structure |
|---|---|---|
| 1,500 | Focused single-angle story, one main source | Lede + nut graf + 3 sections + kicker |
| 2,000-2,500 | Multi-faceted subject, 2-3 sources, richer narrative | Lede + nut graf + 4 sections + kicker |
| 3,000 | Complex story with multiple timelines, 3+ sources, significant depth | Lede + nut graf + 5 sections + kicker |

**Default: 2,000 words.** This is the sweet spot for magazine features — enough room to build a narrative, not so long it loses the reader.

**When to go shorter:** The story is simple, one source, one angle. Don't pad.
**When to go longer:** The story genuinely needs the space. Don't inflate.

---

## Decision Frameworks

### Lede Selection
1. Is there a character whose moment captures the story? → Anecdotal
2. Is the setting so specific it becomes a character? → Scene-setting
3. Is the news itself the reason to read? → Declarative
4. None of the above? → Scene-setting

### Structure Selection
1. Is there a clear timeline (origin → now → future)? → Chronological
2. Are there multiple facets with no single timeline? → Thematic
3. Is there a central tension or challenge? → Problem/Solution
4. Is there a person at the center whose story carries the piece? → Profile

### Section Pacing
- Section 1: Establish (the world, the subject, the stakes)
- Section 2: Deepen (the detail, the character, the tension)
- Section 3: Complicate (the challenge, the nuance, the unexpected)
- Section 4 (if used): Resolve or forward (the outcome, the vision, the implication)

### Source Usage
- First mention: full attribution (name, title, affiliation)
- Subsequent mentions: last name only
- Quotes: woven into narrative, not block-quoted unless especially powerful
- Data: contextualized, not dumped

---

## Source Contract

- Do NOT invent concrete details: no specific menu items, no walking distances, no floor counts, no architect names, no award placements — unless they appear in your context (intake or briefing).
- If a detail would make the piece stronger but isn't in your source material, write around it. Use sensory observation, spatial description, or tonal framing instead of fabricated specifics.
- Quotes must come from the intake. Never invent a quote. Never paraphrase and present as direct speech.
- If the scoring step flagged source insufficiency, write observationally — authority comes from how you see, not what you claim.

---

## Example: Perennial Portland Feature (Outline)

**Headline options:**
1. First Look: Inside Perennial Portland
2. The Hotel That Grows Its Own Dinner
3. In Portland's Pearl District, a New Kind of Welcome

**Lede (scene-setting):**
> "The Pearl District smells different in June. The construction dust has settled, the coffee roasters are open, and on the corner of 12th and Everett, a 60-room hotel is preparing to open its doors for the first time."

**Nut graf:**
> "Perennial Portland, opening next month, is betting that first-time visitors to the city want curation, not chaos. In a place known for its food scene and its DIY ethos, the hotel is making a different case: that a guide can be both knowledgeable and unobtrusive."

**Section 1: The Design (thematic)**
- Open with a specific design detail (the lobby's material, the room layout)
- Context: how this fits into Portland's design history
- Source: architect or designer quote

**Section 2: The Food (thematic)**
- Open with the rooftop garden or the restaurant
- Context: Portland's food scene, what this adds
- Source: chef quote, specific sourcing detail

**Section 3: The Neighbourhood (thematic)**
- Open with a Pearl District street scene
- Context: how the hotel engages with its surroundings
- Source: GM or local perspective

**Kicker (forward look):**
> "Perennial Portland opens on June 15. By September, the chef hopes the garden will supply 30% of the restaurant's herbs. That is, if the Portland weather cooperates."

**CTA:**
> Perennial Portland opens June 15. perennialportland.com

---

## Revision Rules

If this is a revision (scoring notes provided from editorial-gate.md):
1. Read the gate feedback carefully.
2. Fix ONLY what the flags identify. Do not rewrite sections that passed.
3. Preserve the original voice, structure, and word count (±5%).
4. If a flag says a quote is misattributed, fix the attribution — do not remove the quote.
5. If a flag says a claim is unverified, either remove the claim or mark it [VERIFY WITH CLIENT].
6. If a flag says tone is advertorial in a specific section, rewrite that section only.
7. Return the revised draft with a `## Revision Log` section listing each flag and what you changed.

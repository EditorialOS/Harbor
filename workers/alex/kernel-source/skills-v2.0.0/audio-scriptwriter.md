---
name: audio-scriptwriter
description: "Write scripts for podcast episodes, audio briefings, and audio adaptations of editorial content. Podcast episode structure, audio briefing scripts, interview prep, show notes, and series planning. Loads editorial-voice.md as dependency."
version: 1.1.0
author: Signal&
layer: production
dependencies:
  - editorial-voice.md
  - editorial-gate.md
gate: full
---

# Audio Scriptwriter — Podcast & Audio Content

## Purpose

Write scripts for podcast episodes, audio briefings, and audio adaptations of editorial content.

This skill loads `editorial-voice.md` as a dependency. All voice, tone, and vocabulary rules apply, but audio voice is conversational, present-tense, and designed for listening — not reading.

---

## What You Receive

1. **Audio brief** — type (podcast, briefing, adaptation), length, audience, topic
2. **Source material** — interview transcript, feature draft, or topic notes
3. **Brand context** — from Data/ folder

---

## Output

A complete audio script with:
- Timing marks
- Segment breaks
- Transition language
- Production notes (music, sound, tone)
- Show notes / episode description
- `## QA` section (after editorial-gate.md runs)

---

## Audio Types

### 1. Podcast Episode (20-30 minutes)

**Structure:**
```
0:00-0:30   [INTRO]: Music fade-in, host welcome, episode preview
0:30-2:00   [HOOK]: The story that makes this episode worth 30 minutes
2:00-8:00   [SEGMENT 1]: First major topic or interview section
8:00-15:00  [SEGMENT 2]: Second major topic or interview section
15:00-22:00 [SEGMENT 3]: Third major topic or analysis
22:00-26:00 [CLOSE]: Summary, implication, forward look
26:00-28:00 [OUTRO]: Music, credits, next episode preview, CTA
28:00-30:00 [MUSIC OUT]: Fade
```

**Script rules:**
- Conversational register — contractions, first person, direct address
- Signposting — tell the listener where they are ("In the first half of this episode...")
- Pacing — vary sentence length, use pauses, break complex ideas into chunks
- No visual references ("as you can see", "the image below") — audio only
- No long quotes without attribution — listeners can't scan back
- Each segment should have a clear takeaway

**Example intro script:**
```
[Music: Warm, acoustic, 10 seconds]

HOST: Welcome to The Content Studio Podcast. I'm Alex.

This week, we're looking at something that shouldn't work — a hotel with a farm on the roof. Perennial Portland opens next month, and the chef growing basil four stories above Burnside Street is betting that guests want to know where their dinner came from.

It's a 25-minute episode. We'll talk to the chef, walk through the garden, and ask whether this is the future of hotel dining or a very expensive experiment.

[Music: Transition, 5 seconds]

HOST: Let's start with the roof.
```

---

### 2. Audio Briefing (3-5 minutes)

**Purpose:** Tight, punchy, structured for listening — not reading. News-style briefing.

**Structure:**
```
0:00-0:15   [INTRO]: Music sting, host, topic
0:15-0:45   [HEADLINE]: The one thing you need to know
0:45-2:00   [CONTEXT]: Why this matters, background
2:00-3:30   [DETAIL]: Specifics, data, quote
3:30-4:00   [IMPLICATION]: What this means
4:00-4:30   [OUTRO]: CTA, next briefing preview
```

**Script rules:**
- One story per briefing
- Tight sentences — no subordinate clauses
- One quote maximum — make it count
- End with implication, not just summary
- 3-5 minutes = 450-750 words at conversational pace

**Example briefing script:**
```
[Music: Short sting, 3 seconds]

HOST: This is The Content Studio Briefing. I'm Alex. Today: Perennial Portland's rooftop farm.

The headline: A 60-room boutique hotel in Portland's Pearl District is opening with a working garden on the roof. The chef estimates it will supply 30% of the restaurant's herbs by September.

Why this matters: Hotel restaurants typically source from distributors. Growing on-site cuts delivery miles, guarantees freshness, and gives the chef control over varieties. But it also adds complexity — weather, pests, maintenance, and the simple fact that rooftops are not ideal growing conditions.

The detail: Chef Maria Santos planted the garden in March. She chose basil, thyme, rosemary, and mint — herbs that handle Portland's variable weather and are used daily in the kitchen. The garden is irrigated with a drip system fed by the building's rainwater collection.

The implication: If this works, it becomes a model for other boutique hotels in climate-variable cities. If it doesn't, it's a very expensive lesson in the difference between a garden and a reliable supply chain.

Perennial Portland opens June 15.

[Music: Out sting, 3 seconds]
```

---

### 3. Interview Prep for Podcast

**Purpose:** Questions that create conversation, not interrogation.

**Question types:**

| Type | Purpose | Example |
|---|---|---|
| **Open story** | Elicit narrative | "Tell me about the day you decided to plant the garden." |
| **Process** | Reveal how something works | "Walk me through a harvest morning. What time do you start?" |
| **Challenge** | Surface tension | "What's the hardest part of growing food on a roof?" |
| **Surprise** | Reveal unexpected detail | "What did you learn about Portland weather that you didn't expect?" |
| **Forward** | Look ahead | "What does this garden look like in five years?" |
| **Personal** | Connect to human motivation | "What do you want a guest to feel when they taste something from the roof?" |

**Interview rules:**
- 5-7 questions for a 20-30 minute episode
- Follow-up suggestions for each question ("If they say X, ask Y")
- Avoid yes/no questions
- Avoid questions that lead to generic praise
- One question should be slightly challenging — not hostile, but probing

---

### 4. Audio Adaptation of Written Content

**Purpose:** Take a feature or blog post and restructure it for ears.

**Key differences from written content:**
- **Pacing:** Slower. Listeners can't skim. Break complex sentences into two.
- **Signposting:** More explicit. "Earlier in this episode..." "The next section..."
- **Repetition:** Key points should be stated twice — once when introduced, once when summarized.
- **Visuals:** Remove all visual references. Replace with sensory or spatial descriptions.
- **Quotes:** Attribute every time. "As chef Maria Santos told me..." not just the quote.

**Adaptation process:**
1. Read the written piece
2. Identify the narrative arc (lede, sections, kicker)
3. Break each section into 2-3 minute audio segments
4. Add signposting between segments
5. Rewrite visual descriptions as sensory descriptions
6. Add intro and outro
7. Note music and sound cues

**Example adaptation:**

Written: "The rooftop garden produces enough basil for the restaurant."
Audio: "By September, the chef estimates the garden will supply 30% of the restaurant's herbs. That's roughly 20 bunches of basil a week, grown four stories above the kitchen where it's used."

---

## Show Notes & Episode Descriptions

**Show notes format:**
```
Episode [Number]: [Title]

[One paragraph summary — what this episode is about and why it matters]

Topics covered:
• [Topic 1]
• [Topic 2]
• [Topic 3]

Guest: [Name, title, affiliation]

Links:
• [Relevant link 1]
• [Relevant link 2]

[CTA: Subscribe, review, share]
```

**Episode description rules:**
- Optimized for podcast app discovery (include keywords)
- 200-300 characters for Apple Podcasts / Spotify
- One clear promise or question
- Include guest name if notable

---

## Series Planning

**Episode sequencing:**
- Episode 1: Origin story or big idea
- Episode 2: The process or the people
- Episode 3: The challenge or the conflict
- Episode 4: The resolution or the future
- Episode 5: Listener questions or community

**Thematic arcs across a season:**
- Season theme: "The Future of Boutique Hospitality"
- Episode 1: The hotel that grows its own food
- Episode 2: The designer rethinking hotel rooms
- Episode 3: The neighbourhood as the amenity
- Episode 4: The guest who doesn't want to be a tourist
- Episode 5: What's next for Portland's hotel scene

**Guest strategy:**
- Mix of insiders (chef, GM, designer) and outsiders (critic, traveller, expert)
- One episode per season with a "name" guest for reach
- One episode per season with a listener/customer story for relatability

---

## Production Notes

**Music cues:**
- [Music: Warm, acoustic, 10 seconds] — intro
- [Music: Transition, 5 seconds] — between segments
- [Music: Resolve, 8 seconds] — outro
- [Music: None] — during interview or emotional moment

**Sound design:**
- Location sound: garden ambience, kitchen noise, city background
- Foley: footsteps, doors, utensils, water
- Silence: intentional pauses for emphasis or reflection

**Tone notes:**
- Conversational, not performative
- Present tense for descriptions
- Direct address to listener
- Authority without arrogance

---

## Decision Frameworks

### Format Selection
- Solo commentary: one voice, editorial, structured
- Interview: two voices, conversational, exploratory
- Narrative: one voice, story-driven, immersive
- Briefing: one voice, news-style, tight

### Length
- Briefing: 3-5 minutes
- Standard episode: 20-30 minutes
- Deep dive: 45-60 minutes

### Structure
- Solo: hook → context → analysis → implication → close
- Interview: intro → question 1 → follow-up → question 2 → follow-up → close
- Narrative: scene → scene → scene → resolution
- Briefing: headline → context → detail → implication

---

## Source Contract

- Interview questions must be grounded in the subject's actual story
- Audio adaptations must not invent details not in the source material
- Show notes must accurately reflect episode content
- Guest attributions must be correct

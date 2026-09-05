---
name: video-scriptwriter
description: "Write scripts the client or their production team shoots. Not storyboarding — the words, structure, timing, and shot suggestions. Brand films, short-form social video, interview prep, explainers, testimonial guides. Loads editorial-voice.md as dependency."
version: 1.1.0
author: Signal&
layer: production
dependencies:
  - editorial-voice.md
  - editorial-gate.md
gate: full
---

# Video Scriptwriter — Video Scripts & Shot Direction

## Purpose

Write scripts the client or their production team shoots. Not storyboarding (that's visual creative). This is the words, structure, timing, and shot suggestions.

This skill loads `editorial-voice.md` as a dependency. All voice, tone, and vocabulary rules apply, but video voice is more visual and present-tense than written content.

---

## What You Receive

1. **Video brief** — type, length, platform, audience, key messages
2. **Source material** — brand context, interview transcripts, product details
3. **Brand context** — from Data/ folder

---

## Output

A complete script with:
- Timing marks every 5 seconds
- Shot suggestions (wide/medium/close-up)
- Text overlay copy
- Music mood notes
- One-line summary for the client
- `## QA` section (after editorial-gate.md runs)

---

## Video Types

### 1. Brand Film (60-90 seconds)

**Purpose:** Emotional introduction to the brand. Not a sales pitch — a story.

**Structure:**
```
0:00-0:05  [HOOK]: One image that captures the brand's essence
0:05-0:20  [CONTEXT]: The world the brand exists in
0:20-0:45  [STORY]: The brand's reason for being, shown not told
0:45-0:60  [RESOLUTION]: The brand's promise, implied not stated
0:60-0:75  [CTA]: One line, one URL
0:75-0:90  [LOGO]: Brand name, quietly
```

**Script rules:**
- No voiceover for the first 10 seconds — let the image work
- Voiceover, if used, should be sparse — one sentence per 15 seconds maximum
- Show, don't tell. The script describes what the viewer sees, not what a narrator says
- No superlatives. No "world-class." No "unique."
- End with implication, not exclamation

**Example brand film script:**
```
0:00-0:05
VISUAL: Close-up of basil leaves, morning light, water droplets
SOUND: Birds, distant city traffic
TEXT: None

0:05-0:15
VISUAL: Pull back to reveal rooftop garden, four stories up, city behind
SOUND: Wind, light music begins
VOICEOVER: "Portland has a new hotel."
TEXT: None

0:15-0:30
VISUAL: Chef walks through garden, picks herbs, walks down stairs
SOUND: Music builds slightly
VOICEOVER: "It grows its own dinner."
TEXT: None

0:30-0:45
VISUAL: Kitchen, chef preparing dish, plated, served to guest
SOUND: Music at full, gentle
VOICEOVER: "Perennial Portland. Opening June 15."
TEXT: "Perennial Portland" / "June 15"

0:45-0:60
VISUAL: Guest at window, city view, sunset
SOUND: Music resolves
VOICEOVER: None
TEXT: "perennialportland.com"

0:60-0:75
VISUAL: Logo, quiet
SOUND: Music fades
TEXT: None
```

---

### 2. Short-Form Social Video (15-60 seconds)

**Purpose:** Platform-native content for Instagram Reels, TikTok, YouTube Shorts.

**Structure:**
```
0:00-0:02  [HOOK]: Stop the scroll
0:02-0:08  [VALUE]: Deliver the promise
0:08-0:12  [DETAIL]: Add specificity
0:12-0:15  [CTA]: Next step
```

**Script rules:**
- Hook in first 2 seconds — visual or text overlay
- Text overlay for every key point (many watch without sound)
- Fast cuts — one shot per 3-5 seconds
- No voiceover unless necessary — text + music + visual tells the story
- CTA in final 3 seconds

**Example Reel script:**
```
0:00-0:02
VISUAL: Chef on rooftop, waving at camera, holding basil
TEXT OVERLAY: "This hotel grows its own herbs"
SOUND: Trending audio, upbeat

0:02-0:06
VISUAL: Quick montage of garden rows, watering, harvesting
TEXT OVERLAY: "4 stories above Portland"
SOUND: Audio continues

0:06-0:10
VISUAL: Chef in kitchen, preparing dish, plating
TEXT OVERLAY: "Served in the restaurant below"
SOUND: Audio continues

0:10-0:15
VISUAL: Plated dish, guest smiling, hotel exterior at dusk
TEXT OVERLAY: "Perennial Portland / Opening June 15"
SOUND: Audio resolves
```

---

### 3. Interview Prep

**Purpose:** Questions structured to elicit story, not just information.

**Question types:**

| Type | Purpose | Example |
|---|---|---|
| **Origin** | How did this begin? | "What was the moment you decided to build this?" |
| **Process** | How does it work? | "Walk me through a typical morning in the garden." |
| **Challenge** | What was hard? | "What surprised you about building a hotel in Portland?" |
| **Vision** | Where is this going? | "What does Perennial Portland look like in five years?" |
| **Personal** | Why does this matter to you? | "What do you want guests to feel when they leave?" |

**Interview rules:**
- 5-7 questions maximum
- Questions should elicit story, not data
- Suggest b-roll for each answer (what to shoot while they talk)
- Final question should look forward
- Avoid yes/no questions

**Example interview guide:**
```
QUESTION 1: Origin
"What was the specific moment you decided Perennial Portland needed a rooftop garden?"
B-ROLL: Garden shots, chef working, close-ups of plants

QUESTION 2: Process
"Walk me through a Tuesday morning. What time do you start, what do you check first, what's the first thing you harvest?"
B-ROLL: Time-lapse of morning routine, kitchen prep

QUESTION 3: Challenge
"Portland's weather is unpredictable. What's the hardest part of growing food on a roof here?"
B-ROLL: Rain, wind, protective covers, chef problem-solving

QUESTION 4: Vision
"In five years, what do you want the garden to supply?"
B-ROLL: Wide shot of full garden, future plans, sketches

QUESTION 5: Personal
"What do you want a guest to feel when they taste something that grew four stories above their room?"
B-ROLL: Guest at table, reaction shot, sunset view
```

---

### 4. Explainer Script

**Purpose:** Clear, structured explanation of a product, service, or concept.

**Structure:**
```
0:00-0:05  [PROBLEM]: What pain does this solve?
0:05-0:15  [SOLUTION]: What is this, simply stated?
0:15-0:30  [HOW]: How does it work? (3 steps max)
0:30-0:45  [PROOF]: Why believe this? (data, testimonial, demonstration)
0:45-0:60  [CTA]: What to do next
```

**Script rules:**
- One idea per 10 seconds
- Visual should illustrate, not decorate
- Use analogies for complex concepts
- No jargon unless the audience uses it

---

### 5. Testimonial Guide

**Purpose:** How to direct a customer interview to get usable footage, not rehearsed talking points.

**Structure:**
- Pre-interview: Brief the customer on what you'll ask (not the answers)
- Questions: 3-5, story-focused
- B-roll: Suggested shots to capture during the interview

**Question rules:**
- "What was the problem you were trying to solve?"
- "What happened when you tried [alternative]?"
- "What made you choose [brand]?"
- "What was the moment you knew this was working?"
- "What would you tell someone considering [brand]?"

**What to avoid:**
- "How satisfied are you?" (leads to generic praise)
- "Would you recommend us?" (leads to yes/no)
- "What do you like best?" (leads to feature list)

---

## Shot Suggestion Style

The script includes shot suggestions, not full storyboards.

**Shot types:**

| Type | Description | When to Use |
|---|---|---|
| **Wide** | Establishing shot, full scene | Opening, transitions, context |
| **Medium** | Subject from waist up, some background | Interviews, demonstrations |
| **Close-up** | Face, hands, detail | Emotion, texture, product detail |
| **Extreme close-up** | Eyes, texture, small detail | Intimacy, sensory detail |
| **POV** | Subject's point of view | Immersion, experience |
| **Overhead** | Looking down | Process, food, layout |

**Shot suggestion format:**
```
[TIME] [SHOT TYPE] — [Subject/Action] — [Purpose]
```

**Example:**
```
0:00-0:05 Wide — Rooftop garden at dawn, city behind — Establish setting
0:05-0:10 Medium — Chef walking through garden rows — Introduce subject
0:10-0:15 Close-up — Hands picking basil, water droplets — Sensory detail
0:15-0:20 POV — Chef's view looking down at kitchen below — Connection
```

---

## Audio Direction

**Music mood notes:**
- Describe the feeling, not the genre ("warm, unhurried, acoustic" not "folk music")
- Note tempo ("slow build, 80 BPM" or "upbeat, 120 BPM")
- Note instrumentation ("acoustic guitar, light percussion, no vocals")
- Note emotional arc ("starts sparse, builds at 0:30, resolves at 0:55")

**Silence beats:**
- Note where silence is more powerful than music
- "No music 0:00-0:05 — let the natural sound work"
- "Music drops out at 0:45 — voiceover only for final line"

---

## Length by Platform

| Platform | Length | Structure |
|---|---|---|
| TikTok | 15-30s | Hook → value → CTA |
| Instagram Reel | 30-60s | Hook → value → detail → CTA |
| Brand film | 60-90s | Hook → context → story → resolution → CTA |
| Explainer | 90-120s | Problem → solution → how → proof → CTA |
| Interview | 3-5 min | 5 questions, edited to 2-3 min highlights |
| Testimonial | 60-90s | Problem → choice → result → recommendation |

---

## Decision Frameworks

### Length by Type
- Brand film: 60-90s
- Social video: 15-60s
- Explainer: 90-120s
- Interview: 3-5 min (raw), 2-3 min (edited)
- Testimonial: 60-90s

### Structure by Type
- Brand film: emotional arc
- Explainer: problem → solution → proof
- Social: hook → value → CTA
- Interview: origin → process → challenge → vision → personal

### Shot Suggestion Style
- Wide/medium/close-up notes
- Enough for a videographer to shoot from
- Not so detailed it constrains creative interpretation

---

## Source Contract

- Do NOT invent specific shots that don't exist in source material
- If a shot is described, it must be plausible given the location/subject
- Interview questions must be grounded in the brand's actual story
- B-roll suggestions should be realistic for the production context

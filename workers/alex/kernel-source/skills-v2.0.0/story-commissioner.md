---
name: story-commissioner
description: "Turn vague ideas into structured briefs. Angle development, story idea generation, commissioning batches, and pipeline management. The bridge between editorial strategy and content production. Loads editorial-voice.md as dependency."
version: 1.1.0
author: Signal&
layer: production
dependencies:
  - editorial-voice.md
gate: full
---

# Story Commissioner — Brief Creation & Angle Development

## Purpose

Turn "we should write something about that" into a structured brief that answers every question before the writer starts. This skill doesn't write content — it designs the container that makes writing possible.

The Story Commissioner is the bridge between strategy (what to publish) and production (the published piece). It ensures every commissioned piece has a clear angle, defined audience, specified length, assigned channel, confirmed deadline, and gathered reference material.

This skill loads `editorial-voice.md` as a dependency. Briefs should reflect the brand voice in their angle and framing, even though they are internal documents.

---

## What You Receive

1. **Raw input** — a vague idea, a client request, a standing order note, or a theme from the editorial calendar
2. **Brand context** — from Data/ folder (pillars, personas, voice, competitive landscape)
3. **Content inventory** — what's been published, what's in the pipeline (from Work/ and standing orders)
4. **Commissioning context** — how many pieces this cycle, what channels need filling, what deadlines are fixed

---

## Output

A structured brief document with:
- Angle statement (one sentence)
- Audience definition
- Length, format, channel
- Deadline
- Reference material list
- Briefing score (self-assessed)
- `## QA` section

---

## Workflows

### 1. /story-brief — Turn a Vague Idea into a Structured Brief

**Trigger:** "We should write about X", client request, standing order, editorial calendar slot

**The brief is a gift to the writer.** Every question answered before they start. No writer should have to ask "who is this for?" or "how long should it be?" or "what's the angle?"

**Brief structure:**

```markdown
# Story Brief — [Title/Slug]

## Angle
[One sentence that captures the editorial proposition. Not a topic — an angle.]

**Angle test:** Can you state why this story matters right now, to this audience, in one sentence? If not, the angle isn't sharp enough.

**Examples:**
- Weak: "A blog post about the rooftop garden" (topic, not angle)
- Strong: "The garden produces 30% of the restaurant's herbs — here's how a hotel learned to farm" (angle with stakes)
- Weak: "A feature on the new hotel" (no angle)
- Strong: "Perennial Portland is betting that first-time visitors want curation, not chaos" (angle with tension)

## Audience
**Primary:** [Persona name from audience-personas.md]
**Why they care:** [Specific reason this audience will read this]
**What they know already:** [Assumed knowledge — don't explain what they know]
**What they don't know:** [The discovery this piece delivers]

## Format & Specs
| Attribute | Spec |
|---|---|
| Format | [Feature / Blog / Social package / Email / Video script / Audio] |
| Length | [Word count or duration] |
| Channel | [Where it publishes] |
| Pillar | [Which content pillar this serves] |
| Tone | [Tone register for this channel — from editorial-voice.md] |

## Deadline
[Date]. Include buffer: draft due 48 hours before publish date for copy edit and ready-check.

## Sources & References
- [Source 1 — what it is, where to find it]
- [Source 2 — what it is, where to find it]
- [Interview subject, if applicable — name, title, availability]
- [Competitive reference — what's been written on this already, how this differs]

## Briefing Score
| Criterion | Score | Notes |
|---|---|---|
| Angle sharpness | /5 | Is the angle specific, timely, and differentiated? |
| Audience clarity | /5 | Is the audience defined and their motivation clear? |
| Source sufficiency | /5 | Are there enough sources to produce without invention? |
| Format fit | /5 | Is the format the right container for this story? |
| Deadline realism | /5 | Can this be produced to quality by the deadline? |

**Total: /25**
**Briefing quality:**
- 23-25: Excellent brief — writer can execute without questions
- 20-22: Good brief — minor gaps, writer may need one clarification
- 17-19: Adequate brief — writer will need guidance, flag for commissioner review
- Below 17: Insufficient — do not commission. Return to angle development.
```

**Brief rules:**
- One story per brief. No "and also cover this" additions.
- Angle must be specific enough that a different publication wouldn't write the same piece.
- Length must be realistic for the format. Don't brief a 2,000-word feature on a topic with one source.
- Every brief must serve a content pillar. If it doesn't, the angle is wrong.

---

### 2. /commission-batch — Generate and Rank Story Ideas

**Trigger:** Monthly editorial calendar planning, quarterly strategy review, content gap analysis

**Process:**
1. Generate 8-10 story ideas from current themes, audience demand signals, and editorial differentiation
2. Rank each by: audience demand (will they read it?), editorial differentiation (can we own this?), production feasibility (can we produce it?)
3. Select top 4-6 for briefing

**Idea generation framework:**

```
Themes from content pillars → What stories do these themes suggest?
        ↓
Audience pain points → What are they not finding?
        ↓
Competitive white space → What isn't being covered?
        ↓
Seasonal/cultural moments → What's timely right now?
        ↓
Internal assets → What do we have access to that others don't?
        ↓
        8-10 raw ideas
```

**Ranking matrix:**

| Idea | Audience Demand | Editorial Diff | Production Feasibility | Total | Commission? |
|---|---|---|---|---|---|
| [Idea 1] | /5 | /5 | /5 | /15 | Yes / No / Maybe |
| [Idea 2] | /5 | /5 | /5 | /15 | Yes / No / Maybe |

**Rules:**
- Commission only ideas scoring 11+ (out of 15)
- Commission 4-6 ideas per cycle. More = diluted quality.
- Include one "stretch" idea (high risk, high reward) per batch
- Include one "reliable" idea (proven format, safe bet) per batch
- Reject ideas that score high on demand but low on differentiation — someone else is already doing it better

---

## Quick Hits

### /angle — "I want to write about X"

**Input:** A topic or subject area
**Output:** 3 distinct angles with audience fit and channel recommendation

**Format:**
```
Topic: [Input topic]

Angle 1: [Specific angle]
- Audience: [Who cares]
- Channel: [Where it works best]
- Why now: [Timeliness]
- Difficulty: [Easy / Medium / Hard]

Angle 2: [Specific angle]
...

Angle 3: [Specific angle]
...

Recommendation: [Which angle to pursue and why]
```

**Rules:**
- Each angle must be specific enough that a different publication wouldn't choose it
- One angle should be the "obvious" one — the story everyone would tell
- One angle should be the "unexpected" one — the story only this brand can tell
- One angle should be the "timely" one — the story that matters right now

---

### /pipeline — "What's stuck?"

**Input:** The current state of all stories in production (from standing orders, Work/ folder, client updates)
**Output:** Pipeline status with SLA alerts

**Format:**
```markdown
# Pipeline Status — [Date]

| Story | Stage | Owner | Deadline | SLA Status | Flag |
|---|---|---|---|---|---|
| [Story 1] | Brief | Alex | [Date] | On track | — |
| [Story 2] | Draft | [Writer] | [Date] | At risk — 2 days overdue | FLAG |
| [Story 3] | Copy Edit | Alex | [Date] | On track | — |
| [Story 4] | Ready Check | Alex | [Date] | Blocked — waiting for client fact-check | BLOCKED |

## SLA Alerts
- **FLAG:** [Story 2] — draft 2 days overdue. Follow up with writer or reassign.
- **BLOCKED:** [Story 4] — client fact-check pending since [date]. Escalate if not resolved by [date].
- **UPCOMING:** [Story 5] — deadline [date]. Ensure brief is ready 48 hours before.

## Stage Definitions
| Stage | Meaning | SLA |
|---|---|---|
| Idea | Not yet briefed | — |
| Brief | Brief written, not yet commissioned | 24 hours to commission |
| Commissioned | Writer assigned, brief delivered | 48 hours for writer to acknowledge |
| Draft | Writer producing draft | Per brief deadline |
| Filed | Draft submitted, awaiting copy edit | 24 hours to begin copy edit |
| Copy Edit | Line editing, style enforcement | 48 hours |
| Ready Check | Final gate review | 24 hours |
| Approved | Passed gate, ready to publish | — |
| Published | Live | — |

**Rules:**
- Flag anything 24+ hours past SLA
- Blocked items need escalation path and deadline
- Pipeline review runs automatically with every /editorial-calendar workflow
```

---

## Decision Frameworks

### Angle Sharpness Test
1. Can you state the angle in one sentence?
2. Would a different publication write the same angle?
3. Does the angle have stakes — why does this matter now?
4. Is the angle specific enough to guide a writer?

### Commissioning Priority
1. Deadline-driven (what must ship this week?)
2. Calendar-driven (what serves the editorial plan?)
3. Opportunity-driven (what's timely right now?)
4. Gap-driven (what's missing from our coverage?)

### Brief Quality Gate
- Briefing score below 17/25 → Do not commission. Return to angle development.
- Briefing score 17-19 → Commission with commissioner review flag.
- Briefing score 20-25 → Commission without additional review.

---

## Source Contract

- Do NOT invent sources or reference material. If sources don't exist, flag in the brief: "Sources needed: [specific source required]."
- Do NOT brief stories that require reporting Alex cannot access. If the story needs an interview that hasn't been scheduled, the brief is incomplete.
- Competitive references must be real publications or content pieces. Do not invent competitor coverage.
- Angle differentiation must be genuine. "No one has written about this" is only useful if you've checked.
- Briefing scores are self-assessed. Be honest. A weak brief wastes a writer's time.

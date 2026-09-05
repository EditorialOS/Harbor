---
name: campaign-producer
description: "Assemble individual content pieces into cohesive multi-channel campaign packages. Campaign spine creation, launch kit assembly, tentpole packaging, partner content coordination, campaign timeline, and wrap brief. Does not write content — orchestrates. Loads editorial-voice.md and editorial-gate.md as dependencies."
version: 1.1.0
author: Signal&
layer: production
dependencies:
  - editorial-voice.md
  - editorial-gate.md
gate: full
---

# Campaign Producer — Multi-Channel Campaign Assembly

## Purpose

Assemble individual content pieces into cohesive multi-channel campaign packages. This skill doesn't write content — it orchestrates. It ensures the feature, the social posts, the email sequence, and the video script all tell the same story in channel-appropriate ways.

This is the skill that Cedar and Sunday charge the most for. The campaign kit is the premium deliverable.

This skill loads `editorial-voice.md` and `editorial-gate.md` as dependencies.

---

## What You Receive

1. **Campaign brief** — from content-strategist.md or client request
2. **Individual deliverables** — feature, blog, social, email, video, audio (produced by other skills)
3. **Brand context** — from Data/ folder
4. **Timeline** — launch date, tentpole dates, channel schedule

---

## Output

A complete campaign kit document with:
- Campaign spine (one sentence that holds everything together)
- Narrative spine (expanded story)
- Channel allocation (what each channel does)
- Production timeline (dependencies, deadlines)
- Per-channel adaptation notes
- Campaign wrap brief template
- `## QA` section (after editorial-gate.md runs)

---

## Campaign Architecture

### 1. The Campaign Spine

The one sentence that every piece of content in the campaign ladders up to.

**Spine test:** Can you explain every piece in the campaign as an expression of this one idea? If not, the spine is wrong.

**Example spines:**
- "Perennial Portland is not a hotel with a garden. It's a farm with a guesthouse."
- "The Pearl District has changed. Perennial Portland is part of that change."
- "First-time visitors to Portland don't need a guidebook. They need a neighbour."

**Spine rules:**
- One sentence
- Not a tagline (not catchy for its own sake)
- Not a mission statement (not abstract)
- A narrative claim that every piece can illustrate
- Should work for editorial content and marketing content

---

### 2. Narrative Spine (Expanded)

The 3-5 paragraph story that the campaign tells across all channels.

**Structure:**
1. **The world** — the context the audience lives in
2. **The tension** — what's wrong, missing, or changing
3. **The response** — what the brand is doing about it
4. **The proof** — specific evidence that this works
5. **The invitation** — what the audience can do

**Example:**
```
1. The world: Portland's hotel scene has been dominated by chains and
   generic boutique concepts. Visitors get the same experience in every city.

2. The tension: First-time visitors want to feel like locals, not tourists.
   They want curation, not chaos. But most hotels treat them like
   transactions.

3. The response: Perennial Portland is designed for the first-time visitor
   who wants confidence. A 60-room hotel with a rooftop farm, a
   neighbourhood guide, and a chef who sources from 12 local farms.

4. The proof: The rooftop garden supplies 30% of the restaurant's herbs.
   The neighbourhood guide is written by locals, not marketers. The rooms
   are designed for the city, not for a generic luxury standard.

5. The invitation: Perennial Portland opens June 15. Book now for early
   access.
```

---

### 3. Channel Allocation

Each channel has a distinct role. No channel does everything.

| Channel | Role | Content Type | Timing |
|---|---|---|---|
| **Web/Editorial** | Anchor | Hero feature (2,000 words), blog support (1,000 words) | Week 1, sustained |
| **Social (Instagram)** | Awareness | Carousel, Reels, Stories | Week 1-2, daily |
| **Social (TikTok)** | Engagement | Behind-the-scenes, hooks, trends | Week 1-3, 3-5x/week |
| **Social (LinkedIn)** | Thought leadership | Founder/GM posts, industry insight | Week 1-2, 2-3x/week |
| **Email** | Conversion | Announcement sequence, nurture | Week 1-2, 3 emails |
| **Video** | Emotional | Brand film, explainer | Week 1, launch day |
| **Audio** | Deep engagement | Podcast episode, briefing | Week 2, sustained |
| **PR** | Credibility | Press release, media pitch | Week 0-1 |

**Channel role rules:**
- Web/Editorial carries the narrative (the full story)
- Social builds awareness and engagement (the highlights)
- Email drives conversion (the direct ask)
- Video creates emotional connection (the feeling)
- Audio builds authority (the depth)
- PR builds credibility (the third-party validation)

---

### 4. Production Timeline

**Timeline structure:**

| Phase | Timing | Activities | Dependencies |
|---|---|---|---|
| **Pre-production** | -4 weeks | Brief approved, content calendar locked, assets sourced | None |
| **Production** | -3 to -1 weeks | All content drafted, edited, approved | Brief → drafts |
| **Launch** | Week 0 | Content goes live, social begins, email sends | Drafts → live |
| **Sustain** | Week 1-2 | Social continuation, email nurture, engagement | Launch → sustain |
| **Wrap** | Week 3 | Performance report, retrospective, learnings | Sustain → wrap |

**Dependency rules:**
- Feature must be drafted before social can repurpose
- Email sequence needs subject lines before A/B test can run
- Video script must be approved before production can schedule
- Brand film must be shot before launch week

**Buffer:**
- Add 3-5 days buffer between production and launch
- Add 1-2 days buffer between each content piece
- Something always slips

---

### 5. Per-Channel Adaptation Notes

For each channel, specify how the narrative spine expresses:

**Web/Editorial:**
- Full narrative, all 5 paragraphs of the spine
- 2,000-word feature + 1,000-word blog support
- SEO-optimized, evergreen

**Social (Instagram):**
- Paragraph 3 (the response) → carousel slides
- Paragraph 4 (the proof) → Reel with data/visuals
- Paragraph 5 (the invitation) → Story CTA

**Social (TikTok):**
- Paragraph 2 (the tension) → hook
- Paragraph 3 (the response) → value
- Paragraph 5 (the invitation) → CTA

**Email:**
- Paragraph 1-2 (world + tension) → subject line + preview
- Paragraph 3-4 (response + proof) → body
- Paragraph 5 (invitation) → CTA

**Video:**
- Paragraph 1 (world) → opening visuals
- Paragraph 2 (tension) → problem statement
- Paragraph 3 (response) → solution reveal
- Paragraph 4 (proof) → evidence
- Paragraph 5 (invitation) → CTA

---

### 6. Campaign Wrap Brief

**Post-campaign summary:**

```markdown
# Campaign Wrap — [Campaign Name]

## What Shipped
| Channel | Content | Status |
|---|---|---|
| Web | Feature + blog | Live |
| Social | 5 IG posts, 3 TikToks, 2 LinkedIn | Live |
| Email | 3-email sequence | Sent |
| Video | 60s brand film | Live |

## Timeline
- Planned launch: [Date]
- Actual launch: [Date]
- Slippage: [Days] — [Reason]

## Per-Channel Metrics
| Channel | Metric | Target | Actual | Delta |
|---|---|---|---|---|
| Web | Page views | [X] | [Y] | [Z] |
| Social (IG) | Reach | [X] | [Y] | [Z] |
| Email | Open rate | [X] | [Y] | [Z] |
| Video | Views | [X] | [Y] | [Z] |

## Initial Performance Read
- [What worked]
- [What didn't]
- [Surprises]

## Recommendations for Next Campaign
1. [Double down on X]
2. [Retire Y]
3. [Test Z]
```

---

## Decision Frameworks

### Narrative Spine Test
Can every piece in the campaign be explained as an expression of one central idea? If not, the spine is wrong.

### Channel Allocation Test
- Which channels carry the narrative? (editorial, social)
- Which channels drive action? (email, paid)
- Which channels build community? (social engagement, audio)
- No channel should do all three

### Timing Test
- What drops first? (teaser, announcement, full content)
- What sustains? (social series, email nurture)
- What closes? (wrap-up, retrospective)
- Is there buffer for slippage?

---

## Source Contract

- Campaign brief must be based on actual client objectives and timeline
- Channel metrics must be based on realistic targets (not aspirational)
- Per-channel adaptations must be grounded in the actual content produced
- Do NOT invent performance data for the wrap brief

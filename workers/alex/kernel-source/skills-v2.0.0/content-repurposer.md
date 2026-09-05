---
name: content-repurposer
description: "Take one piece of content and produce maximum derivative outputs without making them feel like diluted copies. Feature to social, blog to email, podcast to audiogram. One input → 15-20 channel-native derivatives. Loads editorial-voice.md and editorial-gate.md as dependencies."
version: 1.1.0
author: Signal&
layer: production
dependencies:
  - editorial-voice.md
  - editorial-gate.md
gate: full
---

# Content Repurposer — One Input, Multi-Format Output

## Purpose

Take one piece of content and produce maximum derivative outputs without making them feel like diluted copies. This is the efficiency multiplier — the skill that turns one feature into 15-20 pieces across channels.

This skill loads `editorial-voice.md` and `editorial-gate.md` as dependencies.

---

## What You Receive

1. **Source content** — feature, blog post, newsletter, podcast episode, video
2. **Target channels** — which platforms to produce for
3. **Brand context** — from Data/ folder

---

## Output

A per-channel derivative package with:
- Each piece tagged to its source content
- Format notes per channel
- `## QA` section (after editorial-gate.md runs on key derivatives)

---

## The Repurposing Framework

### Core Principle

**What's the atomic insight in the source content, and how does it best express on each channel?**

A 2,000-word feature about the rooftop garden doesn't become an 8-slide carousel that summarizes the feature. It becomes "8 things growing on a hotel rooftop in Portland right now" that stands alone on Instagram without ever reading the feature.

**The rule:** Each derivative must be **standalone valuable**. It must work without the source content. If it only makes sense after reading the original, it's not a derivative — it's a summary.

---

## Derivative Types by Source

### From Feature (2,000 words)

| Derivative | Channel | Atomic Insight | Standalone? |
|---|---|---|---|
| **Instagram carousel** | IG | 8 things growing on the roof | Yes — each slide is a fact |
| **TikTok Reel** | TikTok | Chef picks herbs at 6AM | Yes — 15-second moment |
| **LinkedIn post** | LinkedIn | Hotels should grow their own food | Yes — opinion piece |
| **Email teaser** | Email | The hotel with a farm on top | Yes — 100-word teaser + link |
| **Newsletter section** | Newsletter | Behind the garden | Yes — 200-word excerpt |
| **Pinterest pin** | Pinterest | Portland hotel rooftop garden | Yes — visual + description |
| **Video script** | Video | 60-second brand film | Yes — emotional arc |
| **Audio briefing** | Podcast | 3-minute briefing | Yes — news story |
| **Twitter/X thread** | Twitter | 5-tweet thread on hotel innovation | Yes — each tweet stands alone |
| **Quote cards** | All social | 5 quotable moments from the feature | Yes — visual + quote |

### From Blog Post (1,000 words)

| Derivative | Channel | Atomic Insight | Standalone? |
|---|---|---|---|
| **Instagram carousel** | IG | 5 tips from the guide | Yes — each tip is actionable |
| **TikTok Reel** | TikTok | One tip, demonstrated | Yes — 15-second tutorial |
| **LinkedIn post** | LinkedIn | The guide's core lesson | Yes — insight + link |
| **Email newsletter** | Email | Full post + context | Yes — with link to full |
| **Pinterest pin** | Pinterest | Guide title + key image | Yes — discovery tool |
| **Twitter/X thread** | Twitter | 5 key takeaways | Yes — each tweet is a tip |

### From Newsletter Edition

| Derivative | Channel | Atomic Insight | Standalone? |
|---|---|---|---|
| **Instagram post** | IG | Lead story excerpt | Yes — with link in bio |
| **LinkedIn post** | LinkedIn | Lead story insight | Yes — opinion + discussion |
| **Twitter/X thread** | Twitter | 3 highlights from the edition | Yes — each is a mini-post |
| **Blog post** | Web | Expanded lead story | Yes — full article |

### From Podcast Episode

| Derivative | Channel | Atomic Insight | Standalone? |
|---|---|---|---|
| **Audiogram** | IG/TikTok | 30-60 second clip with waveform | Yes — quotable moment |
| **Quote cards** | All social | 5 quotable moments | Yes — visual + quote |
| **Blog post** | Web | Episode summary + transcript excerpt | Yes — reading option |
| **Newsletter section** | Newsletter | Episode highlight | Yes — with link to listen |
| **LinkedIn post** | LinkedIn | One insight from the episode | Yes — discussion starter |

---

## Adaptation Rules by Channel

### Instagram Carousel
- 5-10 slides
- Slide 1: Hook (the atomic insight)
- Slides 2-8: Value (each slide one point)
- Slide 9: CTA (link in bio, save, share)
- Each slide: one image + one sentence
- No slide should require reading the source to understand

### TikTok Reel
- 15-30 seconds
- Hook in first 2 seconds
- One atomic insight per Reel
- Text overlay for every key point
- No "read the full article" — the Reel is the content

### LinkedIn Post
- 150-300 words
- One insight or argument
- First line = hook
- End with question for comments
- No external link in post (suppresses reach) — put in first comment

### Email Teaser
- 100-150 words
- The promise, not the summary
- One specific detail from the source
- CTA to read the full piece
- Subject line should be the hook

### Newsletter Section
- 200-300 words
- Excerpt or adaptation of one section
- Context for newsletter readers
- Link to full piece
- Should feel like original content, not a repost

### Pinterest Pin
- Image + description
- Description: keyword-rich, 200-500 characters
- Link to full content
- Board strategy: topic-based, not product-based

### Twitter/X Thread
- 5-10 tweets
- Each tweet: one point, standalone
- Thread should tell a story when read in order
- Each tweet should work if it goes viral alone
- First tweet: hook. Last tweet: CTA.

### Quote Cards
- 5 cards per source piece
- Each card: one quote + attribution + visual
- Quote must be from the source material
- Visual: brand-aligned, simple, readable
- Use for all social platforms

---

## The Repurposing Trap

**What NOT to do:**
- Don't create a carousel that summarizes the feature ("In this feature, we learned...")
- Don't create a Reel that says "read the full article" (the Reel should be the content)
- Don't create a LinkedIn post that's just a link drop
- Don't create an email that's just "here's what we published this week"

**What TO do:**
- Find the atomic insight in the source
- Express that insight in the channel's native format
- Make each derivative standalone valuable
- Add channel-specific value (hashtags, questions, visual, audio)

---

## Decision Framework

### Step 1: Extract the Atomic Insight
Read the source content. What's the one thing that makes this worth sharing? Not the summary — the insight.

### Step 2: Match Insight to Channel
Which channel's format best expresses this insight?
- Visual moment → Instagram/TikTok
- Argument/insight → LinkedIn/Twitter
- Story/narrative → Email/Newsletter
- Discovery/search → Pinterest
- Audio moment → Podcast/audiogram

### Step 3: Adapt, Don't Summarize
Rewrite the insight for the channel's format. Don't compress the source — re-express the insight.

### Step 4: Verify Standalone Value
Does this derivative work without the source? If not, rewrite.

---

## Source Contract

- Derivatives must be based on actual content from the source material
- Quotes must be exact and attributed
- Do NOT invent new claims or data for derivatives
- If the source lacks visual/audio material, describe the mood/aesthetic in words

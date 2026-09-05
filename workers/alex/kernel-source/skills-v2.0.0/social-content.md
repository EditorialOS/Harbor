---
name: social-content
description: "Create platform-native social content that feels native to each channel, not like repurposed blog posts. Instagram, TikTok, LinkedIn, Pinterest. Platform-specific formats, hook-first scripting, caption writing, hashtag strategy, and community response. Loads editorial-voice.md as dependency."
version: 1.1.0
author: Signal&
layer: production
dependencies:
  - editorial-voice.md
  - editorial-gate.md
gate: full
---

# Social Content — Platform-Native Social

## Purpose

Create social content that feels native to each platform, not like repurposed blog posts. This is the skill that makes the content studio a content agency rather than a magazine publisher.

This skill loads `editorial-voice.md` as a dependency. All voice, tone, and vocabulary rules apply, but tone modulation per platform overrides where specified.

---

## What You Receive

1. **Content brief** — topic, angle, source material, brand context
2. **Platform assignment** — which platform(s) to create for
3. **Format hint** — carousel, Reel, single image, Story, etc.
4. **Brand context** — from Data/ folder

---

## Output

A platform-specific content package with:
- Per-post caption/script
- Hashtag set
- Format notes (image count, video length, text overlay copy)
- Posting time recommendation
- `## QA` section (after editorial-gate.md runs)

---

## Platform-Specific Rules

### Instagram

**Formats:**
- **Single image**: One strong visual + caption story
- **Carousel**: Slide 1 = hook, Slides 2-7 = value, Slide 8 = CTA
- **Reel**: 15-60 seconds, hook in first 2 seconds, text overlay, trending audio optional
- **Story**: 3-5 frames, interactive (poll, question, quiz), ephemeral

**Caption rules:**
- 125-150 words maximum (optimal for engagement)
- First line is the hook — must stop the scroll
- Use line breaks for readability
- One CTA maximum ("Link in bio", "Save this", "Tag a friend")
- No hashtags in caption (put in first comment, or omit if account is established)
- Use 3-5 emojis maximum, strategically placed

**Reel script rules:**
- Hook in first 2 seconds (visual or audio)
- Text overlay for every key point (many watch without sound)
- Timing marks every 5 seconds
- CTA in final 3 seconds
- 15-30 seconds for awareness, 30-60 seconds for education

**Example Reel script:**
```
0:00-0:02 [HOOK]: Text overlay "This hotel grows its own herbs"
         Visual: Close-up of chef picking basil on rooftop
0:02-0:08 [VALUE]: Text overlay "4 stories above Portland"
         Visual: Wide shot of rooftop garden with city behind
0:08-0:12 [DETAIL]: Text overlay "Supplies the restaurant below"
         Visual: Chef walking down stairs with herbs
0:12-0:15 [CTA]: Text overlay "Perennial Portland. Opening June 15."
         Visual: Hotel exterior, brand name
```

---

### TikTok

**Format:** 15-60 seconds, vertical 9:16

**Hook-first rules:**
- First 2 seconds determine everything
- Hook options: surprising visual, direct question, bold claim, "POV:"
- Text overlay is mandatory (TikTok is sound-on but text reinforces)
- Use trending sounds when relevant, but don't force it
- Authenticity over production value

**Caption rules:**
- Short (3-10 words) — TikTok captions are search terms and context, not stories
- Include keywords for discovery
- Hashtags: 3-5, mix of broad (#travel) and niche (#portlandhotels)
- No "link in bio" (TikTok suppresses external links in captions)

**Example TikTok script:**
```
0:00-0:02 [HOOK]: Text overlay "POV: You just found the only Portland hotel with a rooftop farm"
         Visual: Quick cut to rooftop garden, chef waving
0:02-0:08 [VALUE]: Text overlay "The chef picks herbs at 6AM"
         Visual: Time-lapse of garden to kitchen
0:08-0:12 [DETAIL]: Text overlay "The restaurant serves them by 7PM"
         Visual: Plated dish, close-up
0:12-0:15 [CTA]: Text overlay "Perennial Portland. June 15."
         Visual: Hotel sign, booking info in bio
```

---

### LinkedIn

**Format:** Text post, document post, or article

**Text post rules:**
- 150-300 words (LinkedIn algorithm rewards text posts)
- First line = hook (question, bold claim, contrarian take)
- Use line breaks every 1-2 sentences
- One clear insight or lesson
- End with a question to drive comments
- No external links in the post (LinkedIn suppresses reach) — put link in first comment

**Document post rules:**
- 5-10 slides
- Each slide: one insight, one data point, or one step
- Slide 1: hook + promise
- Slides 2-8: value
- Slide 9: CTA or summary

**Voice:** More professional than Instagram, but not corporate. Thought leadership, not press release.

**Example LinkedIn post:**
```
Most boutique hotels get one thing wrong about first-time visitors.

They assume guests want luxury.

What guests actually want is confidence.

They want to know they're in the right neighbourhood, eating at the right restaurant, seeing the right things — without spending hours researching.

Perennial Portland, opening in June, is built around that insight.

The hotel doesn't just offer a room. It offers a curated neighbourhood experience — designed for visitors who want to feel like locals from day one.

What do you think travellers are actually looking for when they choose a hotel?
```

---

### Pinterest

**Format:** Standard pin (2:3 ratio), Idea pin (multi-page), or video pin

**Pin description rules:**
- 200-500 characters
- Keyword-rich but readable
- Include primary keyword in first 50 characters
- Describe the content, not just the image
- Include brand name naturally

**Board strategy:**
- Create boards by topic, not by product
- "Portland Travel Guide" not "Perennial Portland Content"
- Pin 5-10 times per week, mix of original and curated

**Example pin description:**
```
Planning a first trip to Portland? This 3-day food-focused itinerary covers the Pearl District's best restaurants, coffee shops, and neighbourhood walks. Designed for visitors who want to eat like locals, not tourists. Includes breakfast, lunch, and dinner recommendations for each day. #portlandtravel #pearldistrict #portlandfood #travelguide
```

---

## Caption Writing by Platform

| Platform | Caption Style | Length | CTA Style |
|---|---|---|---|
| Instagram | Storytelling, emotional | 125-150 words | Soft ("Save this", "Tag a friend") |
| TikTok | Search terms, context | 3-10 words | None (CTA in video) |
| LinkedIn | Insight, argument | 150-300 words | Question (drives comments) |
| Pinterest | Discovery, keywords | 200-500 characters | Click-through (link in pin) |

---

## Hashtag Strategy

**Reach tiers:**

| Tier | Hashtag Volume | Purpose | Examples |
|---|---|---|---|
| **Broad** | 1M+ posts | Discovery, reach | #travel #portland #hotel |
| **Niche** | 50K-500K posts | Community, engagement | #boutiquehotel #portlandfood |
| **Branded** | <10K posts | Brand tracking, UGC | #perennialportland #stayperennial |

**Rules:**
- 5-10 hashtags per post (Instagram)
- 3-5 hashtags per post (TikTok, LinkedIn)
- Mix all three tiers: 2 broad + 3 niche + 2 branded
- Never use banned or spam-associated hashtags
- Research hashtags before using (check recent posts for quality)

---

## Posting Cadence

| Platform | Minimum | Optimal | Maximum |
|---|---|---|---|
| Instagram | 3x/week | 5-7x/week | 2x/day |
| TikTok | 3x/week | 5-7x/week | 3x/day |
| LinkedIn | 2x/week | 3-5x/week | 1x/day |
| Pinterest | 5x/week | 10-15x/week | 30x/day |

**Rules:**
- Quality over quantity — one great post beats three mediocre ones
- Consistency matters more than frequency
- Post when your audience is active (test and learn)

---

## Trend Monitoring

**How to ride trends without looking desperate:**
- Only use trends that fit the brand voice
- Adapt the trend to your content, don't force your content into the trend
- Move fast — trends have a 3-7 day window
- Credit the trend originator if known

**Trend adaptation framework:**
1. What is the trend? (audio, format, challenge)
2. Does it fit our brand? (voice, audience, values)
3. How do we adapt it? (our angle, our content)
4. What's the execution? (script, visual, timing)

---

## Community Response

**Reply templates by context:**

| Context | Tone | Example |
|---|---|---|
| **Compliment** | Warm, grateful | "Thank you — that means a lot. The chef will be thrilled." |
| **Question** | Helpful, specific | "Great question. The rooftop garden is open to guests every morning from 7-10AM." |
| **Criticism** | Acknowledge, redirect | "Fair point. We're still learning — send us a DM, we'd love to hear more." |
| **Tag from friend** | Welcoming, informative | "Thanks for the tag! We're opening June 15 — link in bio for early access." |

**Rules:**
- Reply within 24 hours for engagement algorithm
- Use the brand voice, but warmer and more personal
- Never argue publicly
- Never use automated replies
- Sign community replies as the brand, not as "Alex"

---

## Decision Frameworks

### Format Selection
1. **What's the content about?** → Which format serves it best?
2. **Where is the audience?** → Which platform do they use?
3. **What's the goal?** → Awareness (Reel/TikTok), engagement (carousel), conversion (LinkedIn/Pinterest)?

### Platform Prioritization
1. **Where is the brand's audience?**
2. **Which platform rewards this type of content?**
3. **What can the brand produce consistently?**

### Adaptation vs. Creation
- **Adaptation:** Repurpose existing content for the platform (blog → carousel, feature → Reel)
- **Creation:** Platform-native content from scratch (TikTok trend, LinkedIn insight)
- This skill knows the difference and applies the right approach

---

## Source Contract

- Do NOT invent concrete details for visual descriptions
- If a visual doesn't exist in source material, describe the mood/aesthetic in words, not specific shots
- Quotes in social content must come from source material
- Hashtag research should be based on actual platform search, not invented

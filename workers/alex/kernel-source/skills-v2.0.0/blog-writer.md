---
name: blog-writer
description: "Write 600–1,500 word blog posts that serve both the reader and search. SEO-aware structure, scannable formatting, internal linking, and CTA placement. Different discipline from feature writing — information architecture, not narrative. Loads editorial-voice.md and seo-brief.md as dependencies."
version: 1.1.0
author: Signal&
layer: production
dependencies:
  - editorial-voice.md
  - seo-brief.md
  - editorial-gate.md
gate: full
---

# Blog Writer — Blog Posts & Web Articles

## Purpose

Write 600–1,500 word blog posts that serve both the reader and search. Different discipline from feature writing — blog posts have information architecture, features have narrative architecture.

This skill loads `editorial-voice.md` as a dependency. All voice, tone, vocabulary, and house style rules apply.
This skill loads `seo-brief.md` as a dependency when search performance matters.

---

## What You Receive

1. **Topic or brief** — from client request, standing orders, or content strategist
2. **SEO context** — from seo-brief.md (keyword clusters, search intent, structure recommendations)
3. **Brand context** — from Data/ folder
4. **Word count target** — from brief or standing orders (default: 1,000)

---

## Output

A publish-ready blog post in markdown with:
- SEO meta (title tag, meta description, slug)
- H2/H3 hierarchy
- Internal link suggestions
- CTA placement
- `## QA` section (after editorial-gate.md runs)

---

## Blog Post Architecture

### 1. The Title / H1

The H1 is the promise. It tells the reader what they will get and why they should read.

**Title formulas:**

| Formula | When to Use | Example |
|---|---|---|
| **How to [achieve outcome]** | Tutorial, guide, instructional | "How to Plan a Food-Focused Weekend in Portland" |
| **[Number] [things] to [action]** | Listicle, resource, roundup | "12 Portland Restaurants That Define the City Right Now" |
| **What [group] Needs to Know About [topic]** | News, trend, industry update | "What First-Time Portland Visitors Need to Know About the Pearl District" |
| **The [adjective] Guide to [topic]** | Comprehensive resource | "The Complete Guide to Portland's Boutique Hotel Scene" |
| **Why [subject] [verb] [outcome]** | Explainer, analysis | "Why Portland's Hotel Boom Is Changing Where Visitors Stay" |
| **[Question]?** | Direct answer format | "Is Portland's Pearl District Worth the Hype?" |

**Title rules:**
- Maximum 60 characters (for SEO display)
- Include primary keyword near the beginning
- No clickbait — the post must deliver what the title promises
- One clear benefit or promise

---

### 2. The Intro (First 100-150 Words)

The intro has one job: validate the reader's search and promise the answer.

**Intro structure:**
1. **Hook** (1 sentence) — acknowledge the reader's problem or curiosity
2. **Validation** (1-2 sentences) — show you understand why they're here
3. **Promise** (1 sentence) — state what the post will deliver
4. **Preview** (1 sentence) — list the sections or key points

**Example:**
> "Planning a first trip to Portland can feel overwhelming. The city has more neighbourhoods than most visitors expect, and the food scene changes fast enough that last year's recommendations are already outdated. This guide cuts through the noise — 12 restaurants, 6 neighbourhoods, and one clear itinerary that works for a three-day weekend. No tourist traps. No outdated picks."

**Intro rules:**
- No fluff. The reader searched for something specific. Give it to them immediately.
- No brand mention in the first paragraph unless the post is about the brand
- Include the primary keyword in the first 100 words
- End with a transition to the first H2

---

### 3. H2/H3 Hierarchy

The structure must work when skimmed. Every H2 and H3 should tell a complete story on its own.

**H2 types:**

| Type | Purpose | Example |
|---|---|---|
| **Section header** | Major topic division | "Where to Eat in the Pearl District" |
| **Step header** | Tutorial sequence | "Step 1: Book Your Hotel Before Your Flights" |
| **Question header** | FAQ format | "What Time of Year Is Best for Portland?" |
| **Comparison header** | A vs. B | "Pearl District vs. Downtown: Where to Stay" |

**H3 types:**
- Sub-topic within an H2
- Specific recommendation within a list
- Detail or example

**Structure rules:**
- Every H2 should be answerable in 200-400 words
- No H2 without at least one H3 or 200 words of body text
- H2s should follow a logical sequence: general → specific, or chronological, or problem → solution
- Include the primary keyword in at least one H2
- Include related keywords in H3s where natural

---

### 4. Body Text

**Paragraph rules:**
- 2-4 sentences per paragraph maximum
- One idea per paragraph
- Short sentences (15-20 words average)
- Active voice
- Second person ("you") for direct address

**Scannability rules:**
- Use bold for key terms and takeaways
- Use bullet lists for 3+ related items
- Use numbered lists for sequential steps
- Use tables for comparisons (2+ items, 2+ attributes)
- Break up text every 100-150 words with a list, table, or subhead

**Internal linking:**
- Link to 2-3 existing posts where relevant
- Use descriptive anchor text (not "click here")
- Place links where they serve the reader, not just for SEO
- Flag link suggestions in a `## Internal Links` section at the bottom

---

### 5. CTA Placement

Blog posts need a next step. Without one, the reader bounces.

**CTA types by post type:**

| Post Type | Primary CTA | Secondary CTA |
|---|---|---|
| **Guide / tutorial** | "Download the full itinerary" or "Book your stay" | "Read our neighbourhood guide" |
| **Listicle / roundup** | "Save this list" or "Share with a friend" | "Read our deep dive on [topic]" |
| **News / trend** | "Subscribe for weekly updates" | "Read our analysis of [related topic]" |
| **Brand story** | "Learn more about [brand]" | "Book a visit" |

**CTA rules:**
- One primary CTA per post
- Place it after the final H2, before the conclusion
- Make it specific (not "Learn more" — "Download the 3-day Portland itinerary")
- Optional secondary CTA in the conclusion
- No CTA in the first third of the post (build value first)

---

### 6. The Conclusion (50-100 Words)

Not a summary. A final thought + reinforcement of the promise + CTA.

**Conclusion structure:**
1. **Final thought** — one sentence that lands the post's main point
2. **Reinforcement** — remind the reader what they now know or can do
3. **CTA** — the next step

**Example:**
> "Portland doesn't reward the tourist who follows the guidebook. It rewards the visitor who knows which neighbourhood to walk through at 10 AM on a Tuesday. Use this guide as your starting point — then put it down and start walking."

---

## SEO Integration

When `seo-brief.md` is loaded, apply these rules:

**Keyword placement:**
- Primary keyword: H1, first 100 words, one H2, conclusion
- Related keywords: H3s, body text, image alt text
- Long-tail variants: naturally in body text, not forced

**Meta data:**
```
Title tag: [Primary keyword] — [Brand name] | [Value prop]
  (50-60 characters)

Meta description: [Promise + benefit + CTA]
  (150-160 characters)

Slug: /[primary-keyword-with-hyphens]
```

**Featured snippet optimization:**
- Paragraph snippet: answer the question in 40-60 words in the first paragraph
- List snippet: use numbered lists for "how to" and "steps"
- Table snippet: use tables for comparisons with clear headers

**Internal linking strategy:**
- Link from this post to 2-3 older posts
- Suggest 2-3 future posts that should link back to this one
- Create topic clusters: pillar post → cluster posts → related posts

---

## Length Calibration

| Word Count | When to Use | Structure |
|---|---|---|
| 600-800 | Simple answer, single topic, one search intent | H1 + 3 H2s + conclusion |
| 1,000-1,200 | Guide, tutorial, moderate depth | H1 + 4-5 H2s + 2-3 H3s + conclusion |
| 1,500 | Comprehensive resource, multiple search intents | H1 + 5-6 H2s + 4-6 H3s + conclusion + FAQ |

**Default: 1,000 words.** The sweet spot for SEO (enough depth to rank) and reader attention (not so long it intimidates).

---

## Decision Frameworks

### Format Selection
1. **Is the reader trying to do something?** → How-to / tutorial
2. **Is the reader comparing options?** → Listicle / comparison
3. **Is the reader staying current?** → News / trend analysis
4. **Is the reader researching a topic?** → Comprehensive guide
5. **Is the reader looking for inspiration?** → Brand story / profile

### Structure Selection
1. **Simple answer + context** → 600-800 words, 3 H2s
2. **Tutorial or guide** → 1,000-1,200 words, 4-5 H2s, numbered steps
3. **Comprehensive resource** → 1,500 words, 5-6 H2s, FAQ section

### Voice Calibration
- Blog voice is more direct and conversational than feature voice
- Use "you" and "your" frequently
- Address the reader's problem directly
- Be helpful, not clever

---

## Source Contract

- Do NOT invent concrete details: no specific menu items, no walking distances, no floor counts, no architect names, no award placements — unless they appear in your context.
- If a detail would make the piece stronger but isn't in your source material, write around it. Use general descriptions or link to authoritative sources.
- Quotes must come from the source material. Never invent a quote.
- If source insufficiency is flagged, write observationally or use general knowledge carefully, marking it as such.

---

## Example: Perennial Portland Blog Post (Outline)

**Title:** How to Plan a Food-Focused Weekend in Portland's Pearl District
**Meta title:** How to Plan a Food-Focused Weekend in Portland | Perennial Portland
**Meta description:** A 3-day itinerary for first-time visitors who want to eat like locals in Portland's Pearl District. 12 restaurants, 6 neighbourhoods, one clear plan.
**Slug:** /food-focused-weekend-pearl-district-portland

**H2s:**
1. Why the Pearl District (Not Downtown) for Food
2. Friday: Arrival and First Dinner
3. Saturday: The Full Food Day
   - H3: Breakfast (3 options)
   - H3: Lunch (3 options)
   - H3: Dinner (3 options)
4. Sunday: Brunch and Departure
5. What to Skip (And Why)
6. Where to Stay

**CTA:** "Download the full 3-day itinerary with maps and reservations"

**Internal links:**
- Link to: "First Look: Inside Perennial Portland" (feature)
- Link to: "Portland's Best Boutique Hotels" (future post)
- Suggest future post: "Portland Coffee Culture: A Neighbourhood Guide"

---
name: seo-brief
description: "Search context reference for blog posts and web-published content. Keyword cluster identification, search intent classification, content structure recommendations, internal linking strategy, meta title/description writing, and featured snippet optimization. Not an SEO tool — a reference skill that shapes how a writer structures content for search. Loaded alongside blog-writer.md when search performance matters."
version: 1.1.0
author: Signal&
layer: reference
dependencies: []
gate: none
---

# SEO Brief — Search Context Reference

## Purpose

Inform content production with search context. Not an SEO tool — a reference skill that shapes how a writer structures content for search.

This skill is loaded alongside `blog-writer.md` when search performance matters. Magazine features and newsletters do not need SEO. Blog posts and landing pages do.

---

## What You Receive

1. **Topic** — from content brief or standing orders
2. **Brand context** — from Data/ folder
3. **Competitive landscape** — from Data/competitive-landscape.md

---

## Output

SEO context to inform the blog writer:
- Keyword cluster
- Search intent classification
- Content structure recommendations
- Internal linking strategy
- Meta title, description, slug
- Featured snippet optimization notes

---

## When to Apply SEO

| Content Type | SEO? | Why |
|---|---|---|
| **Magazine feature** | No | Editorial content, not search-driven |
| **Blog post** | Yes | Discovery-driven, search is primary channel |
| **Landing page** | Yes | Conversion-driven, search is primary channel |
| **Newsletter** | No | Push content, not pull content |
| **Social post** | No | Platform-native, search is secondary |
| **Email** | No | Direct delivery, no search involved |

**The skill knows when to apply and when to stay out of the way.**

---

## Keyword Cluster Identification

**Primary keyword:** The main topic the post targets.
- One per post
- Should have search volume (use keyword research tools or infer from common search patterns)
- Should match the post's core topic exactly

**Related keywords:** Variants and sub-topics that support the primary.
- 3-5 per post
- Include long-tail variants ("best boutique hotel Portland Pearl District")
- Include question formats ("where to stay in Portland first time")

**Keyword cluster example:**
```
Primary: "boutique hotel Portland Pearl District"
Related:
- "best hotels Pearl District Portland"
- "where to stay Portland first time visitor"
- "Portland boutique hotel with restaurant"
- "Pearl District hotel recommendations"
- "Portland hotel rooftop garden"
```

---

## Search Intent Classification

**Four intent types:**

| Type | What the searcher wants | Content structure | Example |
|---|---|---|---|
| **Informational** | Learn something | How-to, guide, explainer | "How to plan a weekend in Portland" |
| **Navigational** | Find a specific site/page | Direct answer, confirmation | "Perennial Portland hotel" |
| **Transactional** | Buy, book, register | Product page, booking form | "Book Perennial Portland" |
| **Commercial investigation** | Compare before deciding | Comparison, review, roundup | "Best boutique hotels Portland" |

**Intent rules:**
- Match content structure to intent type
- Informational → comprehensive guide
- Navigational → direct, factual
- Transactional → clear CTA, minimal friction
- Commercial investigation → comparison, proof, differentiation

**How to determine intent:**
- Look at what currently ranks for the keyword
- If guides and articles rank → informational
- If product pages rank → transactional
- If comparison posts rank → commercial investigation
- If brand pages rank → navigational

---

## Content Structure Recommendations

**Based on what ranks:**

**If listicles rank:**
- Use numbered H2s
- Include comparison table
- Add summary box at top
- Target featured snippet with list format

**If guides rank:**
- Use step-by-step H2s
- Include FAQ section
- Add "what you need to know" summary box
- Target featured snippet with paragraph format

**If comparison posts rank:**
- Use comparison table
- Include pros/cons for each option
- Add recommendation section
- Target featured snippet with table format

**H2/H3 hierarchy based on search intent:**
- Informational: "What is X", "How to X", "Why X matters", "X vs. Y", "FAQ"
- Commercial: "Best X for Y", "X reviews", "X comparison", "Is X worth it?"
- Transactional: "X pricing", "X booking", "X packages", "How to book X"

---

## Internal Linking Strategy

**What to link to:**
- 2-3 existing posts that are contextually relevant
- Pillar posts (broad topics) from cluster posts (specific topics)
- New posts should link to older posts; older posts should be updated to link to new posts

**Anchor text rules:**
- Descriptive, not generic ("Portland neighbourhood guide" not "click here")
- Include keyword where natural
- Don't over-optimize (every link shouldn't be exact-match)

**Link placement:**
- First link in first 100 words (signals relevance to search engines)
- Body links where they serve the reader
- Related links section at bottom (optional)

---

## Meta Title & Description

**Title tag:**
- 50-60 characters
- Primary keyword near the beginning
- Brand name at end (if space allows)
- Format: [Primary Keyword] — [Value Prop] | [Brand]
- Example: "Boutique Hotel Portland Pearl District | Perennial Portland"

**Meta description:**
- 150-160 characters
- Include primary keyword
- Promise + benefit + CTA
- Example: "Discover Perennial Portland, a boutique hotel in the Pearl District with a rooftop garden and farm-to-table restaurant. Book your stay."

**Slug:**
- Primary keyword with hyphens
- No stop words (a, an, the, in, of)
- Example: `/boutique-hotel-portland-pearl-district`

---

## Featured Snippet Optimization

**Paragraph snippet:**
- Answer the question in 40-60 words in the first paragraph
- Use the question as an H2 or H3
- Format: direct answer + brief context

**List snippet:**
- Use numbered lists for "how to" and "steps"
- Use bullet lists for "best" and "top"
- Include 5-8 items
- Each item: 10-15 words

**Table snippet:**
- Use comparison tables with clear headers
- Include 3-5 rows
- Each row: 2-4 data points
- Example: "Hotel | Price | Location | Rating"

---

## Decision Frameworks

### When to SEO
- Blog posts: yes
- Landing pages: yes
- Features: no
- Newsletters: no
- Social: no
- Email: no

### Keyword Selection
1. What would someone search to find this content?
2. What's the primary intent behind that search?
3. What currently ranks for that keyword?
4. Can we create something better than what ranks?

### Structure Selection
1. What format dominates the search results? (listicle, guide, comparison)
2. What's missing from the current results? (depth, specificity, recency)
3. How can we structure the post to win the featured snippet?

---

## Source Contract

- Do NOT invent keyword search volume data
- Do NOT claim a keyword is "low competition" without evidence
- Recommendations should be based on observable search results, not speculation
- If keyword research tools are not available, use search engine results pages (SERPs) as primary research

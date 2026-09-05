---
name: email-copywriter
description: "Write emails that drive action. Different from newsletter-writer.md — newsletters are editorial (the reader is the audience). Marketing emails are conversion tools (the reader is being asked to do something). Loads editorial-voice.md as dependency."
version: 1.1.0
author: Signal&
layer: production
dependencies:
  - editorial-voice.md
  - editorial-gate.md
gate: full
---

# Email Copywriter — Marketing & Transactional Email

## Purpose

Write emails that drive action. Different from newsletter-writer.md — newsletters are editorial (the reader is the audience). Marketing emails are conversion tools (the reader is being asked to do something).

This skill loads `editorial-voice.md` as a dependency. All voice, tone, and vocabulary rules apply, but email copy is more direct and action-oriented than editorial.

---

## What You Receive

1. **Email type** — announcement, welcome sequence, nurture, re-engagement, event invitation
2. **Audience segment** — from brand context or brief
3. **Goal** — click, register, book, reply, etc.
4. **Brand context** — from Data/ folder

---

## Output

A complete email or sequence with:
- Subject line + preview text
- Body copy
- CTA (text and button options)
- Send timing recommendation
- `## QA` section (after editorial-gate.md runs)

---

## Email Types

### 1. Announcement Email

**Purpose:** Launch a product, event, or major update.

**Structure:**
- Subject: [News + benefit] or [Curiosity + deadline]
- Body: 100-150 words
  - Opening: The news, plainly stated
  - Context: Why this matters (1-2 sentences)
  - Details: What, when, where
  - CTA: Clear next step
- CTA button: [Primary action]

**Example:**
```
Subject: Perennial Portland opens June 15 — early access now open
Preview: Book before opening week for priority reservations

Perennial Portland opens next month.

The 60-room boutique hotel in the Pearl District — with a rooftop garden, a restaurant sourcing from 12 local farms, and a neighbourhood guide built for first-time visitors — is taking reservations for June 15 and beyond.

Early access is open now. Priority reservations for opening week are limited.

[Book your stay]
```

---

### 2. Welcome Sequence (3-5 emails)

**Purpose:** Build relationship and set expectations after signup.

**Sequence structure:**

**Email 1 — Day 0 (immediate):**
- Subject: Welcome to [Publication/Brand]
- Body: 100 words
  - Thank you for subscribing
  - What to expect (frequency, content type)
 - One immediate value (download, link, resource)
- CTA: [Download the guide] or [Read our best piece]

**Email 2 — Day 1:**
- Subject: The story behind [brand]
- Body: 150 words
  - Origin story or mission
  - What makes this different
  - Social proof (testimonial, number, recognition)
- CTA: [Follow on Instagram] or [Read our manifesto]

**Email 3 — Day 3:**
- Subject: [Specific value proposition]
- Body: 150 words
  - Deep dive into one pillar or offering
  - Case study or example
- CTA: [Book a call] or [Explore offerings]

**Email 4 — Day 7:**
- Subject: What [audience] are asking about [topic]
- Body: 150 words
  - FAQ or common question
  - Answer with authority
- CTA: [Read the full guide] or [Reply with your question]

**Email 5 — Day 14 (if applicable):**
- Subject: [Special offer or exclusive content]
- Body: 100 words
  - Exclusive for subscribers
  - Limited time or limited availability
- CTA: [Claim your offer]

**Rules:**
- Each email has one clear purpose
- Sequence builds relationship before asking for action
- Day 0 = orientation. Day 1-3 = value. Day 7+ = soft ask. Day 14+ = offer.

---

### 3. Nurture Sequence (5-8 emails)

**Purpose:** Move someone from awareness to action over time.

**Sequence structure:**
- Email 1: Problem identification ("Are you struggling with...?")
- Email 2: Solution introduction ("Here's how [brand] solves it...")
- Email 3: Social proof ("Here's what [customer] achieved...")
- Email 4: Objection handling ("You might be thinking...")
- Email 5: Soft ask ("Ready to explore?")
- Email 6: Urgency ("Limited spots / Early access ending...")
- Email 7: Final call ("Last chance...")
- Email 8: Re-engagement or pivot ("Not ready? Here's something else...")

**Rules:**
- One email every 3-5 days (not daily — too aggressive)
- Each email provides value, not just asks
- Subject lines should not feel like a sequence (vary the angle)
- CTA escalates: learn → explore → book → buy

---

### 4. Event Invitation

**Purpose:** Drive RSVPs for an event.

**Structure:**
- Subject: You're invited: [Event name]
- Body: 100-150 words
  - Event name, date, time, location
  - What to expect (1-2 sentences)
  - Why attend (benefit)
  - Social proof (who else is attending, past event success)
- CTA: [RSVP now] or [Register]

**Follow-up emails:**
- Reminder (1 week before): "[Event] is next week — are you coming?"
- Last chance (2 days before): "Last chance to register for [event]"
- Post-event (1 day after): "Thank you for attending [event] — here's what you missed"

---

### 5. Re-engagement Campaign

**Purpose:** Win back dormant subscribers or customers.

**Structure (3 emails):**

**Email 1 — "We miss you":**
- Subject: We miss you — here's what you've missed
- Body: 100 words
  - Acknowledge absence
  - Highlight what they've missed (new content, updates)
  - One piece of value (new guide, exclusive content)
- CTA: [Catch up] or [Download the new guide]

**Email 2 — "What changed":**
- Subject: [Something new that might interest you]
- Body: 100 words
  - New offering, content, or feature
  - Why it's relevant to them
- CTA: [Explore] or [Learn more]

**Email 3 — "Last call":**
- Subject: Should we keep you on the list?
- Body: 50 words
  - Direct question
  - Easy unsubscribe or preference update
- CTA: [Stay subscribed] or [Update preferences] or [Unsubscribe]

---

## Subject Line Testing Framework

**What to A/B test:**
- Curiosity vs. specificity
- Question vs. statement
- Personal vs. generic
- Short vs. long

**How to read results:**
- Open rate = subject line effectiveness
- Click rate = body copy + CTA effectiveness
- Conversion rate = landing page + offer effectiveness

**Test rules:**
- Test one variable at a time
- Minimum 1,000 subscribers per variant for statistical significance
- Run tests for 24-48 hours
- Document learnings in brand context

---

## Body Copy Structure

**Announcement:**
```
[News] + [Context] + [Details] + [CTA]
```

**Nurture:**
```
[Problem] + [Agitation] + [Solution] + [Proof] + [CTA]
```

**Welcome:**
```
[Welcome] + [Expectations] + [Value] + [CTA]
```

**Re-engagement:**
```
[Acknowledge] + [Value] + [Easy out] + [CTA]
```

---

## CTA Hierarchy

| Level | Type | Example | Placement |
|---|---|---|---|
| **Primary** | Button or bold text | "Book your stay" | After body, before close |
| **Secondary** | Text link | "Read the full guide" | In body or after close |
| **Tertiary** | P.S. | "P.S. Early access ends Friday" | After signature |

**Rules:**
- One primary CTA per email
- Secondary CTAs only if they don't compete
- P.S. is the most-read part of an email — use it for urgency or bonus info
- Button text: 2-4 words, action-oriented, specific

---

## Send Cadence

| Sequence | Timing | Notes |
|---|---|---|
| Welcome | Days 0, 1, 3, 7, 14 | Build relationship first |
| Nurture | Every 3-5 days | Don't overwhelm |
| Re-engagement | Weekly, then biweekly | Gentle escalation |
| Event | 2 weeks, 1 week, 2 days, day-of | Multiple reminders |
| Announcement | One-time + 1 reminder | Don't over-email |

---

## Decision Frameworks

### Sequence Length
- Welcome: 3-5 emails
- Nurture: 5-8 emails
- Re-engagement: 3 emails
- Event: 2-3 emails (invite + reminder)

### Send Timing
- Welcome: immediate, then days 1, 3, 7, 14
- Nurture: every 3-5 days
- Re-engagement: weekly, then biweekly
- Event: 2 weeks, 1 week, 2 days, day-of

### Voice Shift
- Email copy is more direct and action-oriented than editorial
- Still on-brand, but the register is different
- Use "you" and "your" frequently
- Address the reader's problem or goal directly

---

## Source Contract

- Do NOT invent customer quotes or testimonials
- Do NOT invent conversion rates or performance data
- Do NOT make claims about limited availability unless verified
- All social proof must come from source material or be clearly marked as hypothetical

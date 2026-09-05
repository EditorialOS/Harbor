---
name: editorial-voice
description: "Voice and standards reference for all content production. Loaded before every writing or editing task to ensure every piece sounds like the brand. Enforces voice attributes, tone modulation by channel, vocabulary rules, and house style."
version: 1.1.0
author: Signal&
layer: reference
dependencies: []
gate: none
---

# Editorial Voice — Voice & Standards Reference

## Purpose

Ensure every piece of content sounds like the brand, regardless of which production skill writes it. This is not a production skill — it is a reference layer loaded as a dependency by every writing, editing, and quality task.

When loaded, apply these rules to every output. Do not summarize them. Do not reference them explicitly in client-facing copy. Enforce them silently.

---

## How to Read the Client's Brand Voice

Read `Data/brand-voice.md` from the client's Drive folder. If it does not exist, use the default framework below and flag in the morning email: "I used default voice settings — please review and confirm."

A complete brand voice document contains:
- 3-5 voice attributes with do/don't examples per attribute
- Tone modulation rules by channel and context
- Vocabulary rules (preferred terms, banned terms, brand-specific naming)
- Formatting conventions (house style)

If any section is missing, apply the default framework for that section and flag the gap.

---

## Voice Attribute Framework (Default)

Voice attributes are what the brand always sounds like. They do not change by channel. They are the brand's personality in words.

**Default attributes (apply unless overridden by client's brand-voice.md):**

| Attribute | Definition | Do | Don't |
|---|---|---|---|
| **Declarative** | State things plainly. Confidence without aggression. | "The hotel opens in June." | "We are thrilled to announce that..." |
| **Restrained** | Specifics over superlatives. Let the detail carry weight. | "60 rooms, each with a view of the Willamette." | "Stunning, world-class luxury accommodations." |
| **Globally contextual** | Place the subject in its wider world. Never treat it as the center of the universe. | "In a city known for its food scene, a new hotel..." | "Perennial Portland is revolutionizing hospitality." |
| **Editorially honest** | Distinguish fact from marketing. Label brand claims clearly. | "The brand claims carbon neutrality (certification pending)." | "A sustainable, eco-friendly destination." |
| **Plainspoken** | Short sentences. Active voice. No jargon unless the audience uses it first. | "The chef sources from 12 local farms." | "Leveraging hyperlocal supply chain synergies." |

**How to enforce:**
- Read every sentence against all 5 attributes.
- If a sentence violates any attribute, rewrite it.
- If a sentence violates 2+ attributes, kill it and start over.

---

## Tone Modulation by Channel

Tone is how the voice adjusts per context. Same brand, different register.

| Channel | Tone | Sentence Length | Register | Example Shift |
|---|---|---|---|---|
| **Magazine feature** | Authoritative, immersive | Medium-long (20-35 words) | Editorial, third-person | "The Pearl District has changed. Perennial Portland is part of that change — not the cause of it." |
| **Blog post** | Direct, helpful | Medium (15-25 words) | Conversational, second-person | "If you're visiting Portland for the first time, start here." |
| **Newsletter** | Personal, intimate | Short-medium (10-20 words) | First-person plural or direct address | "We spent the morning in the rooftop garden. Here's what we found." |
| **Social (Instagram)** | Warm, visual | Short (5-15 words) | Casual, present-tense | "Basil, four stories above Burnside." |
| **Social (LinkedIn)** | Thoughtful, structured | Medium (15-25 words) | Professional, argument-driven | "Three things boutique hotels get wrong about first-time visitors." |
| **Social (TikTok)** | Hook-first, energetic | Very short (3-10 words) | Conversational, trend-aware | "POV: You just found the only Portland hotel with a rooftop farm." |
| **Email (marketing)** | Action-oriented, urgent | Short (10-20 words) | Direct, second-person | "Book before June 1. Rooms are limited." |
| **Email (newsletter)** | Editorial, curated | Medium (15-25 words) | First-person, relationship-driven | "This week's lead story: inside the kitchen at Perennial." |

**How to enforce:**
- Identify the channel before writing.
- Load the tone rules for that channel into active memory.
- Check 3 random sentences from the draft against the tone table. If 2+ are off, revise the whole piece.

---

## Vocabulary Rules (Default)

**Preferred terms** (use these, not synonyms):
- "guest" not "customer"
- "property" not "venue" or "facility"
- "chef" not "culinary director"
- "neighborhood" not "district" (unless it's a proper name like Pearl District)
- "opening" not "launch" (for hotels, restaurants, physical spaces)

**Banned terms** (never use, regardless of context):
- "world-class"
- "unique"
- "unparalleled"
- "leading"
- "premier"
- "luxury" (unless specifically defined by the client)
- "bespoke" (unless the client uses it in their own materials)
- "curated" (overused; use "selected" or specify the selection criteria)
- "experience" (as a noun replacing actual description; "dining experience" → "the restaurant")
- "synergy", "leverage", "optimize", "deliverables" (business jargon)

**Brand-specific naming:**
- Read the client's style-guide.md for proper names, trademarks, and capitalization.
- If unclear, default to: proper nouns capitalized, common nouns lowercase, no unnecessary trademark symbols.

**How to enforce:**
- Search the draft for every banned term. Replace or remove.
- Verify every preferred term is used consistently.
- Check brand names against the style guide.

---

## House Style (Default)

Apply these rules unless overridden by the client's style-guide.md:

| Rule | Standard |
|---|---|
| **Spelling** | British English (colour, centre, programme, travelled) |
| **Oxford comma** | No. Use: "The restaurant serves breakfast, lunch and dinner." |
| **Em-dashes** | Use em-dashes (—) for parenthetical breaks, not en-dashes (–) or hyphens (-). No spaces around em-dashes. |
| **Honorifics** | On first mention only (Mr, Ms, Dr). No full stops after honorifics. |
| **Company names** | Without "the" unless part of official name. "Perennial Portland" not "the Perennial Portland". |
| **Numbers** | Spell out one to nine. Numerals for 10+. Percentages as numerals with % symbol. |
| **Dates** | 7 February 2026 (not Feb 7, 2026 or 7/2/2026). |
| **Times** | 24-hour format (14:30) or with am/pm in lowercase (2.30pm). No periods in am/pm. |
| **Currency** | Symbol before amount, no space (£50, $100, €75). |
| **Quotations** | Double quotes for direct speech. Single quotes for nested quotes. Punctuation inside quotes. |
| **Titles** | Sentence case for headlines and subheads ("The new restaurant in Portland's Pearl District"). |

**How to enforce:**
- Run a line-by-line check against each rule.
- Flag inconsistencies, don't auto-correct if the choice is ambiguous.
- If the client's style guide conflicts with a default rule, follow the client's guide and note the override.

---

## Voice vs. Tone — The Distinction

**Voice** is what the brand always sounds like. It does not change. It is the personality.

**Tone** is how the voice adjusts per context. It changes by channel, audience, and purpose.

**Example:**
- Voice attribute: Declarative (always state things plainly)
- Magazine tone: Declarative + authoritative + immersive = "The hotel opens in June. The garden is already growing."
- TikTok tone: Declarative + hook-first + energetic = "This hotel has a rooftop farm. Yes, really."

Both are declarative. The tone modulates how declarative sounds.

**How to enforce:**
- First pass: check voice attributes (universal).
- Second pass: check tone modulation (channel-specific).
- Never let tone override voice. A TikTok post can be energetic and still declarative.

---

## Source Contract

Every piece of content must distinguish between:
- **Editorial fact** — verifiable, sourced, specific
- **Brand claim** — attributed to the brand, labeled as such
- **Observation** — the writer's descriptive framing, not presented as fact
- **Inference** — logical conclusion from available data, labeled as such

**Rules:**
- Do NOT invent concrete details: no specific menu items, no walking distances, no floor counts, no architect names, no award placements — unless they appear in the source material.
- If a detail would make the piece stronger but isn't in the source material, write around it. Use sensory observation, spatial description, or tonal framing instead of fabricated specifics.
- Quotes must come from the source material. Never invent a quote. Never paraphrase and present as direct speech.
- If source insufficiency is flagged, write observationally — authority comes from how you see, not what you claim.

---

## Output When Loaded

When this skill is loaded, do not produce a separate "voice guide" document. Instead:
1. Read the client's brand-voice.md and style-guide.md from Drive.
2. Merge with the default framework above (client overrides defaults).
3. Apply the merged rules to every sentence of the deliverable.
4. If the client's voice docs are missing or incomplete, apply defaults and flag in the morning email.

This skill is invisible to the client. It is the air the content breathes.

---
name: editorial-gate
description: "Quality gate for all content production. Every piece of content passes through this gate before it ships. Rigid 5-gate scoring framework — never skip a gate, never soft-pass. Returns APPROVED, REVISE, or KILL with specific line-level notes."
version: 1.1.0
author: Signal&
layer: governance
dependencies: []
gate: none
---

# Editorial Gate — Quality Gate

## Purpose

The last checkpoint before any content ships. Every piece of content — regardless of format, channel, or urgency — passes through this gate. No exceptions. No soft passes.

This skill is loaded as the final step for every content production task. It evaluates the draft against five gates, scores each 1-5, and returns a verdict: APPROVED, REVISE, or KILL.

**When to load:** After the draft is complete, after any copy editing, before delivery to the client.
**When to skip:** Never. Quick hits under 200 words may use a compressed 3-gate version (voice, brief fidelity, publish readiness).

---

## The Five Gates

### Gate 1: Voice Compliance

**Question:** Does this sound like this brand?

**What to check:**
- Every sentence against the 5 voice attributes (declarative, restrained, globally contextual, editorially honest, plainspoken)
- Tone modulation: does the register match the channel?
- Vocabulary rules: no banned terms, preferred terms used consistently
- House style: British spelling, no Oxford comma, em-dashes, honorifics, numbers, dates

**Scoring:**
| Score | Meaning |
|---|---|
| 5 | Every sentence sounds like the brand. No exceptions. |
| 4 | One or two minor lapses (a single banned term, one date format error). |
| 3 | Multiple lapses or one significant violation (tone shift in a section, repeated banned terms). |
| 2 | Systematic voice failure (reads like a different brand, promotional register throughout). |
| 1 | Generic or unbranded (could be any company in any industry). |

**Common failures:**
- "We are thrilled to announce..." (violates declarative)
- "World-class luxury experience" (violates restrained + banned terms)
- "Perennial Portland is revolutionizing hospitality" (violates globally contextual)
- Section 3 shifts to press release register (violates tone modulation)

---

### Gate 2: Brief Fidelity

**Question:** Does this deliver what was asked for?

**What to check:**
- The original brief or standing order (angle, structure, word count, format, channel)
- Did the writer follow the section plan?
- Is the angle preserved from brief to draft?
- Is the word count within ±10% of target?
- Are the specified sources used as directed?
- Is the brand integration frequency correct (max 3 mentions per 500 words)?

**Scoring:**
| Score | Meaning |
|---|---|
| 5 | Delivers exactly what was briefed, with no drift. |
| 4 | Minor drift (one section slightly off-angle, word count ±15%). |
| 3 | Significant drift (missing a section, wrong angle, wrong format). |
| 2 | Wrong deliverable (brief asked for a feature, draft is a listicle). |
| 1 | Unrecognizable (no connection between brief and draft). |

**Common failures:**
- Brief specified "narrative feature with scene-setting lede" → draft opens with a list
- Brief specified 800 words → draft is 1,200 words
- Brief specified "3 brand mentions max" → draft has 7
- Brief specified "interview with GM as editorial voice" → GM appears only in quote at end

---

### Gate 3: Structural Quality

**Question:** Is this well-constructed for its format?

**What to check by format:**

**Feature (narrative):**
- Lede: is it a scene, an anecdote, or a declarative opening? Does it hook?
- Nut graf: does the reader know what this story is about by paragraph 3?
- Narrative arc: does the story build? Is there momentum?
- Section pacing: when to go long, when to compress?
- Kicker: does the last paragraph land and give the reader something to carry?

**Blog post:**
- H2/H3 hierarchy: does it map to search intent and scannability?
- Intro hook: does it promise the answer (informational) or establish credibility (transactional)?
- Scannability: does the post work when skimmed?
- CTA placement: is there a clear next step?

**Social:**
- Hook strength: first 2 seconds (video) or first line (caption)
- Platform-native: does this feel like it belongs on this platform?
- Standalone value: does each post work without the others?

**Newsletter:**
- Subject line: would you open this?
- Preview text: does it complement or repeat the subject?
- Edition pacing: lead story → secondary → quick hits → CTA. Does it flow?

**Email sequence:**
- Sequence arc: does each email build toward the goal?
- Send cadence: are the intervals appropriate?
- CTA hierarchy: primary vs. secondary, clear next step?

**Scoring:**
| Score | Meaning |
|---|---|
| 5 | Exemplary construction. A model of the format. |
| 4 | Solid structure with one minor weakness (weak kicker, one section drags). |
| 3 | Functional but flawed (missing nut graf, weak hook, poor pacing). |
| 2 | Poorly constructed (no arc, no hook, sections don't connect). |
| 1 | Unstructured (stream of consciousness, no format awareness). |

---

### Gate 4: Factual Integrity

**Question:** Are claims sourced or sourceable? Are names, titles, dates correct?

**What to check:**
- Proper nouns: company names, personal names, place names — spelling and capitalization
- Titles and roles: is "CEO" correct or is it "Managing Director"?
- Numerical claims: square footage, distances, dates, percentages — are they in the source material?
- Certifications and awards: claimed or achieved? Current or expired?
- Quotes: do they match the source material? Are they attributed correctly?
- Geographic claims: locations, distances, regional descriptions
- Unverifiable assertions: claims not in the source material that the writer may have inferred

**Scoring:**
| Score | Meaning |
|---|---|
| 5 | Every claim verifiable. Zero flags. |
| 4 | One minor flag (plausible but unverified detail, minor name spelling discrepancy). |
| 3 | Multiple flags or one significant error (wrong title, unverified number). |
| 2 | Critical error (wrong date, fabricated quote, incorrect certification). |
| 1 | Systematic fabrication (multiple invented details, no source grounding). |

**Common failures:**
- "The hotel spans 160,000 sq m" — number not in source material
- "CEO Jane Smith" — her title is Managing Director
- Quote attributed to "the GM" but source material has no such quote
- "LEED Platinum certified" — certification is pending, not achieved

---

### Gate 5: Publish Readiness

**Question:** Is this clean, complete, and ready to ship?

**What to check:**
- No placeholder text ([TK], [insert quote], [date])
- No incomplete sections ("Section 3 to come")
- Consistent formatting throughout (headers, lists, spacing)
- Clean copy: no typos, no grammar errors, no punctuation inconsistencies
- All links functional (if applicable)
- All images referenced have alt text (if applicable)
- Meta data complete (SEO title, description, slug — if applicable)
- Derivatives generated (social posts, newsletter blurb — if applicable)

**Scoring:**
| Score | Meaning |
|---|---|
| 5 | Flawless. Could publish as-is. |
| 4 | One minor issue (one typo, one formatting inconsistency). |
| 3 | Multiple minor issues or one moderate issue (missing meta, incomplete section). |
| 2 | Significant incompleteness (missing sections, multiple placeholders). |
| 1 | Unfinished draft (placeholders throughout, no formatting). |

---

## Scoring & Verdict

### Full Gate (5 gates, all content over 200 words)

Run all 5 gates. Score each 1-5.

**Verdict rules:**
- **APPROVED**: 5/5 on all gates. Ship it.
- **REVISE**: Any gate scores 3-4. Return specific line-level notes per gate.
- **KILL**: Any gate scores 1-2. Return explanation of why it fails and what would need to change.

**Revision notes format:**
```
Gate [N]: [Name] — Score: [X]/5
- Issue: [specific problem]
- Location: [line or section]
- Fix: [specific instruction]
```

### Compressed Gate (3 gates, quick hits under 200 words)

For captions, headlines, subject lines, hooks, hashtags, replies:

| Gate | Question |
|---|---|
| Voice compliance | Does this sound like the brand? |
| Brief fidelity | Does this deliver what was asked? |
| Publish readiness | Is this clean and complete? |

**Verdict:**
- 5/5 on all 3 → APPROVED
- Any 3-4 → REVISE with notes
- Any 1-2 → KILL with explanation

---

## Output Format

### For APPROVED

Attach a `## QA` section at the bottom of the deliverable:

```markdown
## QA

| Gate | Score | Notes |
|---|---|---|
| Voice compliance | 5/5 | Clean — no voice lapses detected |
| Brief fidelity | 5/5 | Delivers exactly what was briefed |
| Structural quality | 5/5 | Strong narrative arc, solid kicker |
| Factual integrity | 5/5 | All claims verifiable |
| Publish readiness | 5/5 | Flawless — ready to ship |

**Verdict: APPROVED**
```

### For REVISE

Return a revision document (do not attach to deliverable):

```markdown
# REVISION REQUEST — [Deliverable Name]

## Gate Scorecard

| Gate | Score | Notes |
|---|---|---|
| Voice compliance | 4/5 | One banned term in paragraph 3 |
| Brief fidelity | 5/5 | — |
| Structural quality | 3/5 | Nut graf missing — reader doesn't know the story by paragraph 3 |
| Factual integrity | 5/5 | — |
| Publish readiness | 5/5 | — |

**Verdict: REVISE**

## Required Fixes

### Gate 3: Structural Quality
- **Issue:** No nut graf. The lede is strong (scene-setting) but the reader doesn't know what the story is about until paragraph 5.
- **Location:** Between paragraph 1 and paragraph 2
- **Fix:** Add one sentence after the lede that states the story's thesis: "The hotel, opening in June, is betting that first-time visitors want curation, not chaos."

### Gate 1: Voice Compliance
- **Issue:** "Unique" appears in paragraph 3 (banned term).
- **Location:** Paragraph 3, sentence 2
- **Fix:** Replace "unique" with specific detail: "the only hotel in the Pearl with a rooftop garden" or remove the claim.

## What Changed From Brief
None — structural issue, not brief drift.
```

### For KILL

Return a kill document with explanation:

```markdown
# KILL — [Deliverable Name]

## Gate Scorecard

| Gate | Score | Notes |
|---|---|---|
| Voice compliance | 2/5 | Reads as press release throughout. Promotional register, multiple banned terms. |
| Brief fidelity | 5/5 | — |
| Structural quality | 3/5 | — |
| Factual integrity | 1/5 | Three fabricated quotes, two unverified numerical claims. |
| Publish readiness | 4/5 | — |

**Verdict: KILL**

## Why This Fails

This draft fails on two critical gates:

1. **Voice compliance (2/5):** The entire piece reads as promotional copy, not editorial content. Sentences like "Perennial Portland offers a world-class luxury experience" and "the stunning rooftop garden provides unparalleled views" violate the restrained, declarative voice. The piece would need a complete rewrite from an editorial angle.

2. **Factual integrity (1/5):** Three quotes are not in the source material. The claim "160,000 sq m" is not verified. The LEED Platinum certification is listed as pending in source material, not achieved. These are not fixable with minor edits — they require re-reporting or removal of the claims.

## What Would Need to Change

To salvage this piece:
- Rewrite from an editorial angle (not promotional)
- Remove all fabricated quotes; replace with observation or source-verified quotes
- Verify or remove all numerical claims
- Re-run through the gate

**Recommendation:** Start over with a fresh brief.
```

---

## Gate Execution Rules

1. **Never skip a gate.** Even if the draft is clearly good, run all 5. The discipline matters.
2. **Never soft-pass.** A 4/5 is not "good enough." It's a revise. Only 5/5 ships.
3. **Be specific.** "Voice is off" is useless. "Paragraph 3 shifts to promotional register — 'world-class' is a banned term" is actionable.
4. **Line-level notes only.** Every revise or kill verdict must include exact locations and exact fixes.
5. **Separate evaluation from production.** If you are the same model that wrote the draft, evaluate it as if you didn't. Read every sentence fresh.
6. **Client never sees scores below 4.** If the verdict is revise or kill, the client sees the revision request or kill explanation. They do not see the scorecard.
7. **One gate failure is enough.** If any gate scores 1-2, the verdict is KILL regardless of other scores.

---

## When to Escalate

Escalate to the client (via morning email) when:
- A draft is KILLED and the issue requires client input (missing source material, unclear brief)
- A draft has been revised twice and still doesn't pass
- The gate detects a pattern (3+ drafts from the same skill failing the same gate)

Escalation format:
```
I reviewed [deliverable] and found [issue]. To proceed, I need:
- [Specific missing information]
- [Decision on approach]

I've paused work on this until I hear from you.
```

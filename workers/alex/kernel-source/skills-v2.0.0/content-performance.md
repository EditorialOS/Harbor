---
name: content-performance
description: "Produce content performance reports and strategic recommendations from metrics the client provides or that are available via analytics integration. Weekly reports, monthly reviews, quarterly strategic reviews, campaign performance, format analysis, and recommendation engine. Loads editorial-voice.md as dependency."
version: 1.1.0
author: Signal&
layer: production
dependencies:
  - editorial-voice.md
  - editorial-gate.md
gate: full
---

# Content Performance — Reporting & Analytics

## Purpose

Produce content performance reports and strategic recommendations from metrics the client provides or that are available via analytics integration.

This skill loads `editorial-voice.md` as a dependency. Reports should be written in the brand voice — analytical but accessible, not a data dump.

---

## What You Receive

1. **Performance data** — from client-provided reports, analytics exports, or API integrations
2. **Content inventory** — what was published, when, on which channels
3. **Goals** — from brand context or standing orders
4. **Historical data** — past reports for trend analysis

---

## Output

A performance report with:
- Metrics, analysis, and specific recommendations
- `## QA` section (after editorial-gate.md runs)

---

## Report Types

### 1. Weekly Content Report

**Purpose:** What was published, per-channel engagement, top performers, underperformers.

**Structure:**

```markdown
# Weekly Content Report — [Week of Date]

## What Was Published
| Content | Format | Channel | Publish Date |
|---|---|---|---|
| [Title] | [Format] | [Channel] | [Date] |

## Per-Channel Engagement
| Channel | Reach | Engagement | CTR | Shares | Comments |
|---|---|---|---|---|---|
| Web | [X] | [Y] | [Z] | [A] | [B] |
| Instagram | [X] | [Y] | [Z] | [A] | [B] |
| LinkedIn | [X] | [Y] | [Z] | [A] | [B] |
| Email | [X] | [Y] | [Z] | [A] | [B] |

## Top Performers
1. [Content] — [Metric] — [Why it worked, hypothesis]
2. [Content] — [Metric] — [Why it worked, hypothesis]

## Underperformers
1. [Content] — [Metric] — [Hypothesis for why]
2. [Content] — [Metric] — [Hypothesis for why]

## Notable Trends
- [Observation about this week vs. last week]
- [Platform-specific trend]

## Action Items
- [Specific next step]
- [Specific next step]
```

---

### 2. Monthly Content Review

**Purpose:** Trends across the month, what topics/formats performed, audience growth, engagement trajectory.

**Structure:**

```markdown
# Monthly Content Review — [Month]

## Performance by Pillar
| Pillar | Pieces Published | Avg Engagement | Trend |
|---|---|---|---|
| [Pillar 1] | [X] | [Y] | ↑/↓/→ |
| [Pillar 2] | [X] | [Y] | ↑/↓/→ |

## Performance by Format
| Format | Pieces Published | Avg Engagement | Trend |
|---|---|---|---|
| [Format 1] | [X] | [Y] | ↑/↓/→ |
| [Format 2] | [X] | [Y] | ↑/↓/→ |

## Performance by Channel
| Channel | Reach | Engagement | Conversion | Trend |
|---|---|---|---|---|
| [Channel 1] | [X] | [Y] | [Z] | ↑/↓/→ |
| [Channel 2] | [X] | [Y] | [Z] | ↑/↓/→ |

## Audience Growth
- New subscribers/followers: [X]
- Growth rate: [Y]% vs. last month
- Source of growth: [Organic / Paid / Referral / Search]

## Content Efficiency
- Total pieces published: [X]
- Avg time to produce: [Y] hours
- Avg engagement per piece: [Z]
- ROI estimate: [If applicable]

## Strategic Observations
- [What worked this month]
- [What didn't]
- [Surprises]
- [Patterns]

## Recommendations for Next Month
1. [Double down on X]
2. [Retire Y]
3. [Test Z]
```

---

### 3. Quarterly Strategic Review

**Purpose:** Performance by pillar, channel health, audience evolution, strategic recommendations for next quarter.

**Structure:**

```markdown
# Quarterly Content Review — [Quarter]

## What We Published
[Summary table of all content by pillar, format, channel]

## Performance by Pillar
| Pillar | Pieces | Avg Performance | Trend | Notes |
|---|---|---|---|---|
| [Pillar 1] | [X] | [Y] | ↑/↓/→ | [Observation] |

## Performance by Format
| Format | Pieces | Avg Performance | Trend | Notes |
|---|---|---|---|---|
| [Format 1] | [X] | [Y] | ↑/↓/→ | [Observation] |

## Performance by Channel
| Channel | Reach | Engagement | Conversion | Health |
|---|---|---|---|---|
| [Channel 1] | [X] | [Y] | [Z] | [Healthy / At Risk / Declining] |

## Audience Evolution
- Demographic shifts: [What changed]
- Behaviour changes: [What changed]
- New segments: [What emerged]

## Strategic Adjustments for Next Quarter
1. [Double down on X — evidence]
2. [Retire Y — evidence]
3. [Test Z — hypothesis]
4. [Invest in W — opportunity]

## Next Quarter's Priorities
1. [Priority 1 — tied to business goal]
2. [Priority 2 — tied to content goal]
3. [Priority 3 — tied to audience need]

## Content Calendar (Next Quarter)
[High-level calendar with key dates and tentpoles]
```

---

### 4. Campaign Performance Report

**Purpose:** Per-campaign metrics against the brief's success criteria.

**Structure:**

```markdown
# Campaign Performance — [Campaign Name]

## Campaign Overview
**Duration:** [Dates]
**Objective:** [What the campaign was trying to achieve]
**Success Criteria:** [From campaign brief]

## What Shipped
| Channel | Content | Status |
|---|---|---|
| [Channel 1] | [Content] | [Live / Delayed / Cancelled] |

## Per-Channel Metrics
| Channel | Metric | Target | Actual | Delta |
|---|---|---|---|---|
| [Channel 1] | [Metric] | [X] | [Y] | [Z] |

## Overall Performance
- Total reach: [X]
- Total engagement: [Y]
- Conversion: [Z]
- ROI: [If applicable]

## What Worked
- [Specific element + evidence]
- [Specific element + evidence]

## What Didn't
- [Specific element + evidence + hypothesis]
- [Specific element + evidence + hypothesis]

## Learnings
- [Insight for future campaigns]
- [Insight for future campaigns]

## Recommendations
1. [For next campaign]
2. [For content strategy]
```

---

### 5. Format Performance Analysis

**Purpose:** Which content formats drive the most engagement, shares, conversions per channel.

**Structure:**

```markdown
# Format Performance Analysis — [Period]

## Format Rankings by Channel

### Instagram
| Format | Pieces | Avg Reach | Avg Engagement | Avg Shares | Winner? |
|---|---|---|---|---|---|
| Carousel | [X] | [Y] | [Z] | [A] | [Yes/No] |
| Reel | [X] | [Y] | [Z] | [A] | [Yes/No] |
| Single image | [X] | [Y] | [Z] | [A] | [Yes/No] |
| Story | [X] | [Y] | [Z] | [A] | [Yes/No] |

### LinkedIn
[Same structure]

### Email
[Same structure]

### Web
[Same structure]

## Cross-Format Insights
- [What formats work across channels]
- [What formats are channel-specific]
- [What formats are underutilized]

## Recommendations
1. [Produce more of X format]
2. [Test Y format on Z channel]
3. [Retire W format]
```

---

## Recommendation Engine

**"Double down on X, retire Y, test Z" framework:**

| Recommendation | Trigger | Evidence Needed |
|---|---|---|
| **Double down** | Format/pillar/channel consistently outperforms | 3+ data points showing 20%+ above average |
| **Retire** | Format/pillar/channel consistently underperforms | 3+ data points showing 20%+ below average |
| **Test** | New opportunity or hypothesis | One strong data point or market signal |
| **Invest** | Emerging trend or audience shift | Qualitative + quantitative evidence |

**Recommendation format:**
```
[Action]: [What]
[Evidence]: [Specific data point]
[Expected outcome]: [What will happen if we do this]
[Risk]: [What could go wrong]
[Timeline]: [When to evaluate]
```

---

## Decision Frameworks

### Metrics That Matter
- **Brand awareness clients:** Reach, impressions, share of voice
- **Conversion clients:** Click-through rate, conversion rate, cost per acquisition
- **Community clients:** Comments, shares, mentions, sentiment
- **Authority clients:** Backlinks, referral traffic, speaking inquiries

### Report Frequency
- Weekly: tactical, operational, immediate feedback
- Monthly: strategic, pattern recognition, trend analysis
- Quarterly: directional, resource allocation, strategic pivot

### Honest Reporting
- Distinguish correlation from causation
- Flag missing data ("We don't have email open rates — recommend adding tracking")
- Be specific. "Blog posts performed well" is useless. "The 1,200-word neighbourhood guides averaged 3x the engagement of the 600-word listicles" is actionable.

---

## Source Contract

- Do NOT invent performance data
- Do NOT present correlation as causation
- Do NOT make recommendations without evidence
- If data is missing, say so and recommend what to measure
- If a metric is below target, explain why (hypothesis) and what to do

# Minimal AI OS — Canonical Specification

**Version:** 2.0.0
**Status:** Canonical. Supersedes and retires: `folder_spec.md` v1.0, `runtime_spec.md` v1.0, `ntsl_spec.md` v1.0, `skill_template.md` v1.0, `teammate_protocol.md` v1.0, `morning_report_template.md` v1.0, `setup_checklist.md` v1.0, `gate_protocol.md` (all versions).
**Governing orchestrator:** `Alex-Final.md` (alex-nightly v2.1.0). Where this spec and the orchestrator could disagree, the orchestrator's classification table governs routing; this spec governs structure, packaging, and integrity.

---

## 0. What This Is

Minimal AI OS is an operating system for AI teammates. The intelligence lives in markdown files. The runtime is a courier. The filesystem is the brain.

Its formal definition:

> **A conforming Minimal AI OS instance is one where (a) every kernel file's SHA-256 hash matches MANIFEST.json, and (b) the userland conforms to the templates the kernel defines.**

Drift is not a discipline problem in this system. It is a detectable state: kernel hashes either match or they don't. An instance that fails verification does not run.

---

## 1. The Kernel/Userland Partition

Every file in the system belongs to exactly one of two layers.

### Kernel — invariant, hash-locked, byte-identical across every client

| Component | Files |
|---|---|
| Specification | `spec.md` (this document) |
| Orchestrator | `Alex-Final.md` — identity, reasoning loop, classification table, workflow chains |
| Skills | `skills/*.md` — all 18 skill files |
| Engine | `runtime.py`, `verify.py`, `skill_add.py` |
| Templates | `templates/standing_orders.md`, `templates/teammate.md`, `templates/morning-report.md`, `templates/Data/*.md` (empty client-context molds) |
| Integrity | `MANIFEST.json` — path, version, SHA-256 for every kernel file |

Kernel rules:
- **Read-only in every deployed instance.** Enforced by filesystem permission where possible, by verification always.
- **Changed only through the deliberate-change protocol** (§8). There is no other path.
- **Never edited per-client.** If a client needs different skill behavior, that is a new kernel version shipped to everyone, or a fork with its own manifest — never a silent local edit.

### Userland — variant by design, per-client

| Component | Files |
|---|---|
| Client context | `Data/brand-voice.md`, `Data/content-pillars.md`, `Data/audience-personas.md`, `Data/style-guide.md`, `Data/competitive-landscape.md` |
| Scheduling | `Data/standing_orders.md` (NTSL) |
| Memory | `Data/alex-log.md`, `Data/decision_log.md` |
| Deliverables | `Work/**` |
| Assets | `Assets/**` |

Userland rules:
- Client variation flows **exclusively** through userland. `Data/brand-voice.md` and `Data/style-guide.md` override the defaults in `editorial-voice.md`; the client's file always wins; the override is noted in output when applied.
- Userland files must conform to the kernel's templates (structure, not content).
- Differences between clients' userland are configuration, not drift.

---

## 2. Folder Specification

One layout. The `ai_os/workspace/` layout from folder_spec v1.0 is retired.

```
ClientName/
├── Data/                        ← userland: context + memory
│   ├── brand-voice.md           ← voice guide, tone rules, vocabulary
│   ├── content-pillars.md       ← strategic pillars, topic clusters
│   ├── audience-personas.md     ← content-consumption personas
│   ├── style-guide.md           ← house style, formatting, naming
│   ├── competitive-landscape.md
│   ├── standing_orders.md       ← recurring tasks (NTSL) — SINGLE location, no mirror
│   ├── alex-log.md              ← run history — SINGLE memory file (logbook.md retired)
│   └── decision_log.md          ← parked questions for the human
├── Work/                        ← userland: deliverables
│   ├── strategy/                ← calendars, audits, pillar docs, briefs
│   ├── drafts/                  ← all content drafts
│   ├── social/                  ← social content packages
│   ├── campaigns/               ← multi-channel campaign kits
│   └── reports/                 ← performance reports, content audits
└── Assets/
    ├── photos/
    ├── brand/
    └── references/
```

The kernel (`Skills/`, orchestrator, engine, manifest) lives in the OS repo, not in the client folder. The runtime mounts both: kernel from the repo, userland from the client folder.

### Permission table

| Path | AI | Human | Notes |
|---|---|---|---|
| Kernel (repo) | Read | Read; write via change protocol only | Verified against manifest every run |
| `Data/` | Read | Read/Write | **Exception:** AI appends to `alex-log.md` and `decision_log.md` — these are the only two Data/ files the AI may write |
| `Work/` | Read/Write | Read/Write | AI never overwrites — every file date-stamped `YYYY-MM-DD-slug.md` |
| `Assets/` | Read | Read/Write | |

Conflict rule: human edits win. If human and AI touch the same file between runs, the human version is preserved and the AI logs a conflict note in `alex-log.md`.

---

## 3. Skill Package Format

Every skill is one markdown file in `skills/`. It is a Standard Operating Procedure — procedural knowledge, not code.

### Required frontmatter (machine-readable — the linter enforces this schema)

```yaml
---
name: kebab-case-skill-name          # must equal the filename minus .md
description: "One sentence: what this does and when to load it."
version: 1.0.0                        # semver; bumped via change protocol
author: Signal&
layer: production | reference | governance | orchestration
dependencies:                         # REQUIRED key. Empty list if none.
  - editorial-voice.md
  - editorial-gate.md
gate: full | compressed | none        # which gate mode this skill's output takes
---
```

Frontmatter rules:
- `dependencies` is a required key. Prose-only dependency statements do not count and fail the lint.
- `layer: reference` marks skills loaded as context (editorial-voice, seo-brief); `governance` marks control-flow skills (channel-briefs, editorial-gate); `production` marks skills that produce deliverables; `orchestration` is reserved for the orchestrator.
- A skill is "available" because it exists in `skills/` with valid frontmatter — the orchestrator's Available Skills table is generated from the directory, never hand-maintained.

### Required body sections (in order)

1. **Purpose** — scope and explicit non-scope
2. **What You Receive** — inputs and sources
3. **Output** — deliverables produced, including the `## QA` section where gated
4. **Skill body** — the procedure, frameworks, formats
5. **Decision Frameworks** — at least one
6. **Source Contract** — the do-not-invent clause. Required, final section.

### Loading rules (mirror of the orchestrator)

- `editorial-voice.md` loads before every writing/editing task.
- `editorial-gate.md` loads as the final step of every production task.
- Maximum 4 production skills + editorial-voice + editorial-gate per task. Chains break into sequential tasks.

---

## 4. The Quality Gate

`editorial-gate.md` is the sole gate mechanism. The v1.0 Gate API (self-hosted service, curl) is deprecated and must not be referenced by any kernel file.

**Canonical gate vocabulary — five gates, these names, no synonyms:**

1. Voice Compliance
2. Brief Fidelity
3. Structural Quality
4. Factual Integrity
5. Publish Readiness

**Gate policy (resolved; no other version is valid):**

| Output | Gate | Loop |
|---|---|---|
| Content over 200 words | Full 5-gate | REVISE verdicts get line-level notes; **max 2 revise passes**, then escalate to client |
| Quick hits under 200 words | Compressed 3-gate (Voice Compliance, Brief Fidelity, Publish Readiness) | Run **once**, attach score, no loop |
| Anything | — | **Nothing skips the gate entirely. Ever.** |

Verdicts: APPROVED (5/5 all gates) / REVISE (any gate 3–4) / KILL (any gate 1–2). Only 5/5 ships. Scoring detail, output formats, and escalation rules live in `editorial-gate.md`.

---

## 5. NTSL — Standing Orders

NTSL programs the AI's time without code. One file: `Data/standing_orders.md`.

**v2 change:** recurring tasks name a **Workflow**, not a Skill. The orchestrator's classification table maps workflow → skills. Humans think in outcomes (`/social-week`, `/newsletter`); the kernel resolves the skill load. The `Skill:` field from ntsl_spec v1.0 is retired.

```markdown
# STANDING ORDERS

## CLIENT INFO
- Client name: [First Last]
- Client email: [email]
- Industry: [ ]
- Publication name: [if applicable]

## RECURRING TASKS

### Weekly
- Task: [description]
  Day: [Monday–Friday]
  Workflow: [/social-week, /newsletter, ...]
  Notes: [specifics, constraints]

### Biweekly / Monthly
[same shape; Day may be "First Monday", "15th", "Last Friday"]

## ACTIVE CAMPAIGNS
- Campaign: [name]
  Workflow: [workflow]
  Timeline: [dates]
  Notes: [specifics]

## NOTES
- [persistent context]

## ALEX LOG
Last run: [timestamp]
Requests processed: [count]
Deliverables produced: [count]
```

The weekly flavor system (Monday=Strategist … Friday=Planner) is retained as optional planning guidance, not kernel law.

**The memory contract:** the AI reads `Data/alex-log.md` before parsing standing orders, every run. Work already logged as done is not redone.

**Changing strategy is editing this file.** No deployment. The runtime reads the new orders on its next run.

---

## 6. Runtime Contract

`runtime.py` implements this contract. The runtime is a courier: it verifies, loads, assembles, calls the model, gates, saves, logs, exits. No persistent process. All intelligence is in the files.

```
0. VERIFY
   Hash every kernel file; compare to MANIFEST.json.
   Match → proceed. Mismatch → halt, write integrity flag to the
   morning summary, process nothing.

1. BUILD THE QUEUE
   Drain surfaces (Asana "Ready for Alex", email, Slack backlog) +
   parse standing_orders.md for tasks due today.
   Priority: deadlines → standing orders → quick wins.

2. READ CONTEXT
   All of Data/. Note client first name from CLIENT INFO.

3. RESOLVE NTSL
   Match today's day-of-week; resolve each due task's workflow.

4. CLASSIFY
   Route each item via the orchestrator's classification table
   (workflow) or quick-hit table (command).

5. PRE-FLIGHT
   Per task, check the loaded skills' declared dependencies against
   available Data/ files:
   READY → proceed. PARTIAL → proceed, flag inferences in output.
   BLOCKED → skip task, log what's missing.

6. EXECUTE
   Assemble prompt: orchestrator identity + skill file(s) +
   editorial-voice + client context + task brief + log excerpt.
   Call the model (model-agnostic; provider set in .env).
   Campaign workflows STOP at the channel-briefs approval pause.

7. GATE
   Per §4. Max 2 revise passes. KILL → do not save, log, flag.

8. SAVE
   Approved deliverables → Work/{subfolder}/YYYY-MM-DD-slug.md.
   Never overwrite.

9. LOG + REPORT
   Append run record to Data/alex-log.md.
   Park questions in Data/decision_log.md.
   Post summary on the originating surface (format: §7).

10. EXIT
   No persistent process. The filesystem is the memory.
```

**Error handling:** model API down → retry once in 10 min, then halt and notify. Skill missing → skip task, flag (should be impossible post-verify). Context missing → BLOCKED per pre-flight. Gate KILL → never saved. Human edited a file mid-run → human wins, conflict logged.

**Model agnosticism:** one `call_model(prompt, config)` seam. Swapping providers is one config change; no markdown file changes.

---

## 7. Reporting & Feedback

The morning/wind-down summary is the product. Rules (canonical, from the orchestrator):

- Never post with zero deliverables — deliver or stay quiet and log why.
- Always list file paths the human can open.
- Always end with what you need, if anything.
- Never mention skills, workflows, tools, or internal structure.
- Under 200 words. Sign-off: "— Alex" (or the teammate's name).
- Post on the originating surface; standing-order summaries go to the default channel (`#alex`).

**Decision log:** at any high-stakes fork, the AI parks the question in `Data/decision_log.md` (question, context, options, recommendation, urgency) and moves to the next task. It never guesses when stakes are high.

**The human talks back by editing files:** standing orders for priorities, a dated feedback file in `Data/` for notes, or replying on the surface the summary arrived on.

---

## 8. Integrity: Manifest, Verification, Deliberate Change

### MANIFEST.json

```json
{
  "os_version": "2.0.0",
  "generated": "YYYY-MM-DDTHH:MM:SSZ",
  "files": [
    {"path": "spec.md",            "version": "2.0.0", "sha256": "..."},
    {"path": "Alex-Final.md",      "version": "2.1.0", "sha256": "..."},
    {"path": "skills/editorial-voice.md", "version": "1.0.0", "sha256": "..."}
  ]
}
```

- Generated by `generate_manifest.py` at commit time. Never hand-edited.
- `verify.py` recomputes and compares. Run as runtime step 0 and available standalone.

### The deliberate-change protocol

The only legal path to changing a kernel file:

1. Edit the file **in the OS repo** (never in a deployed instance).
2. Bump the file's `version` and, if behavior changed, the `os_version`.
3. Regenerate MANIFEST.json.
4. Commit. The diff + manifest is the audit trail.
5. Deployed instances pull on next sync; their next verify passes against the new manifest.

Any kernel change that skipped these steps is, by definition, drift — and verify catches it as such.

### Install (replaces setup_checklist.md)

```
1. clone the OS repo                      → kernel arrives versioned
2. init: stamp userland-template → ClientName/   (Data/, Work/, Assets/)
3. fill Data/ (or mark files "to be created during onboarding")
4. write Data/standing_orders.md from the template
5. configure .env (model provider, surface credentials, paths)
6. run verify.py                          → must pass before first run
7. first run → check alex-log.md, Work/, and the summary
8. calibrate over 3 runs (gate REVISE rate 20–50% is healthy), then lock
```

An instance is not "installed" until step 6 passes.

---

## 9. Teammate Identity

The orchestrator file **is** the identity layer for Alex — role, mental model, voice, guardrails, scope live there, loaded fresh every run, no persistent chat state.

To spin up a different teammate (another Alex, a Raya-pattern agent), instantiate `templates/teammate.md`: name, role, mental model, scope boundary, sign-off, voice attributes, guardrails. The teammate file is kernel for that teammate's deployments (hash-locked in its own manifest); the client relationship (first name, contact, industry) is userland, in CLIENT INFO.

Non-negotiable guardrails inherited by every teammate: never impersonate the client; never publish on the client's behalf; never invent data; never reveal internal structure; never skip the gate; never exceed loaded-skill scope.

---

## 10. Deprecations & Renames (v2.0.0)

| Retired | Replaced by |
|---|---|
| `runtime_spec.md` | §6 + `runtime.py` (the code is the spec) |
| `folder_spec.md` (`ai_os/workspace/` layout) | §2 (ClientName/Data-Work-Assets) |
| `logbook.md` (root memory file) | `Data/alex-log.md` — single memory file |
| standing_orders root+mirror dual location | `Data/standing_orders.md` only |
| `gate_protocol.md` / Gate API / Gate MCP via curl | `editorial-gate.md` skill (§4) |
| skill_template v1 "quick hits may skip the gate" | Compressed 3-gate, run once, no exemption (§4) |
| Gate names Voice/Structure/Factual/Completeness/Ready | The five names in §4 |
| NTSL `Skill:` field | NTSL `Workflow:` field (§5) |
| `/weekly-social` | `/social-week` |
| Hand-maintained Available Skills / routine registry | Generated from `skills/` directory + classification table |
| `data_map.md` | The manifest + pre-flight dependency check make it redundant |

---

## 11. Conformance Summary

An instance conforms to Minimal AI OS v2.0.0 iff:

1. `verify.py` passes — every kernel hash matches MANIFEST.json.
2. Every skill in `skills/` passes the frontmatter lint (§3).
3. The userland matches the §2 layout and permission table.
4. Every deliverable in `Work/` is date-stamped and carries a `## QA` section (or its compressed score, for quick hits).
5. `Data/alex-log.md` contains a run record for every run.
6. No kernel file has changed outside the deliberate-change protocol.

`verify.py` checks 1–2 mechanically today; 3–6 are the roadmap for the conformance checker.

---

*spec.md — v2.0.0 — Minimal AI OS Canonical — Signal&*

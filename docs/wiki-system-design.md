# Wiki System Design

Inspired by [Karpathy's LLM Knowledge Base approach](https://x.com/karpathy/status/2039805659525644595).

---

## Core Principles

- **Plain markdown is the foundation.** No tool-specific formats. Any editor, any viewer.
- **The wiki is the source of truth**, not `raw/`. The wiki accumulates knowledge from multiple sources and cannot be rebuilt from `raw/` alone.
- **Compile is always incremental**, never a full rebuild. A manifest tracks what has been processed.
- **Scripts are structure-agnostic.** No hardcoded paths. Scripts navigate via `wiki/_index`.
- **Structure is soft.** The AI proposes, evolves, and can reorganize domains over time. Organization is tag-driven, not folder-driven.
- **Obsidian is a viewer**, not the center. The system works without it.
- **Git is the safety net and the timestamp.** Dates appear only in queue filenames for human readability — nowhere else.
- **No dead-ends.** Every design choice should be reversible or evolvable.
- **Grep over metadata.** If something is grep-able, don't maintain it as structured data.

---

## Directory Structure

```
vault/
  raw/                          ← flat drop zone, human source material only
                                   AI classifies on ingest via tags
  queue/
    session-log/
      open/                     ← Session AI dumps land here
      processed/                ← Wiki AI moves entries here after ingestion
                                   (periodically purged; git history is the record)
    lint/
      open/                     ← Lint AI writes case files here
      resolved/                 ← Resolver moves case files here after fixing
                                   (periodically purged)

  wiki/                         ← flat, all articles at one level
    article-name.md             ← AI assigns folder freely unless user specifies
    _index                      ← article registry (tab-separated: filename, tags, title)

  assets/
    some-spec.pdf
    some-spec.meta.md           ← AI-generated sidecar: abstract + why it's here
    some-diagram.drawio
    some-diagram.meta.md
    links.md                    ← registry of all external URLs

  scripts/                      ← CLI tools driving the pipeline
  outputs/                      ← Q&A answers, charts, slides (filed back into wiki)
```

---

## Organization: Tags over Folders

Folders are not the organizing primitive — tags are. A single article can belong to multiple domains without duplication.

- `wiki/_index` is the machine-readable registry of all articles and their tags (tab-separated, for LLM and Python tooling)
- The AI assigns a folder freely based on dominant tags, and can reorganize as content grows
- The user can pin an article to a folder via the `folder:` frontmatter field — the AI will never move it

``` yaml
---
tags: [tsn, networking, realtime]
folder: tsn                     ← optional, omit to let AI decide
status: draft | stable | needs-review
---
```

PlantUML and DrawIO diagrams are text-based and readable by the AI directly. PlantUML is typically inline in markdown — no sidecar needed. DrawIO files get a sidecar.

---

## Asset Sidecars

Every non-markdown asset (PDF, image, DrawIO file) gets a companion `.meta.md`:

``` markdown
---
type: pdf | image | drawio
tags: [tsn, networking]
---

## Abstract
AI-generated on first compile. Short enough to load in any session
without parsing the full source.

## Why
What prompted adding this. What question it answers.
```

The Wiki AI generates the abstract on first compile and leaves it alone unless flagged for refresh. The abstract is what every other AI reads — the source file is only opened when needed.

---

## Links Registry (`assets/links.md`)

All external URLs in one place. `referenced-by` is not tracked — use grep.

``` markdown
# Links Registry

## https://some-deep-spec.com/tsn-frame-preemption
- **tags:** [tsn, networking]
- **fetch-abstract:** true

### Why
Primary spec reference for frame preemption, not summarized in source docs.

### Abstract
AI-generated when fetch-abstract is true. Left empty otherwise —
the source doc provides enough context.

---

## https://gcc.gnu.org/onlinedocs/gcc/Option-Summary.html
- **tags:** [toolchain]

### Why
Link to GCC options reference, self-explanatory in context.

---
```

- Wiki AI adds new entries when it finds unregistered URLs in source docs or session-log
- `fetch-abstract: true` triggers the AI to fetch and summarize on compile
- Omitting `fetch-abstract` leaves the abstract empty — sufficient when the source doc explains the link

---

## The Four AI Roles

### 1. Wiki AI (Compiler)

- **Reads:** `raw/` and `queue/session-log/open/`
- **Writes:** wiki articles, `wiki/_index`, `assets/links.md`, asset sidecars (directly, via tool use)
- **Mode:** high volume, incremental
- **Triggered:** manually (`wiki compile`), croonable
- Moves processed session-log entries to `queue/session-log/processed/`
- Generates asset abstracts on first encounter
- Registers new external URLs in `assets/links.md`
- Tag indexes are rebuilt by the Python harness post-run (deterministic scan of wiki/)

#### Compile invocation model

The compiler runs Claude CLI in agent mode (`claude -p <prompt>`). It does **not** parse Claude's
output — Claude reads source files and writes wiki articles directly using its file tools.

**File flow:**

1.  Python discovers new files in `raw/` (via manifest) and session entries in `queue/session-log/open/`
2.  For natively readable formats (`.md`, text, images): pass the path as-is
3.  For formats needing conversion (PDF, DOCX, DrawIO): extract to a sibling `.wiki-tmp.txt` file, pass that path; clean up after
4.  Python builds a prompt listing the vault root and all file paths
5.  Claude reads source files, writes wiki articles to `wiki/`, updates `wiki/_index` and `assets/links.md`
6.  Python updates the manifest and moves session entries to `processed/`

**Batching (`compile.max_files`, default 10):**
Large drops are split into batches of at most `max_files` raw files per LLM call.
Session-log entries and new assets are included only in the first batch (they are few
and need not be repeated). Configure in `~/.config/wiki/config.toml`:

``` toml
[compile]
max_files = 10
```

### 2. Lint AI (Diagnostician)

- **Reads:** wiki articles and `wiki/_index`, clustered by tags
- **Writes:** case files to `queue/lint/open/`
- **Touches wiki:** never
- **Mode:** small batches (5–10 articles), deep analysis
- **Triggered:** independently, periodically
- Finds: inconsistencies, outdated content, duplicate coverage, contradictions, missing links
- Does not repair — only diagnoses and writes case files

### 3. Resolver (Interactive Session)

- Not an autonomous job — spun up interactively by the user when there are open lint cases
- Initiated via `/wiki-resolve` skill, which pre-loads the case file and named articles into context
- Flags unresolvable contradictions back into the case file rather than guessing
- Moves case file to `queue/lint/resolved/` when done
- Behaviour differs by `resolver.mode` in config:

**`direct` (single-user):**

- Edits wiki articles on the current branch
- Commits directly

**`branch` (multi-user):**

- Creates a branch `wiki/resolve/<case-name>` before editing
- Edits wiki articles on that branch
- Pushes and opens a PR via `gh pr create` with the case file summary as description
- A designated reviewer merges — preserving the single-writer guarantee on main

### 4. Session AI (Work Sessions)

- **Primary goal:** the actual task — bug hunting, feature design, research
- **Wiki involvement:** opt-in only, never automatic
- **Skill:** `/wiki-log` — structured dump to `queue/session-log/open/`
- Dumps generously, does not curate
- Does not read or touch the wiki directly

---

## Skills (Claude Code Slash Commands)

### `/wiki-log`

Available in any session. Writes a structured entry to `queue/session-log/open/YYYY-MM-DD-<author>-<topic>.md`
where `author` comes from `user.name` in config:

``` markdown
---
tags: [relevant, tags]
author: username
source-files: [path/to/relevant/code]
---

## Findings
- What was discovered, pattern, violation, decision made

## Guideline candidates
- Things that should become documented rules

## Open questions
- Unresolved things worth investigating
```

**Session modes:**

- **Default session:** zero wiki involvement, clean
- **Explicit:** call `/wiki-log` manually at any point
- **Wiki-aware session:** opt in at session start — `/wiki-log` called automatically at end

### `/wiki-resolve`

Initiates an interactive resolver session for a specific lint case:

- Reads the named case file
- Loads the articles listed in it into context
- Injects wiki editing conventions
- User guides, AI edits, flags what it cannot resolve

---

## Lint Case File Format

Written by the Lint AI to `queue/lint/open/YYYY-MM-DD-<topic>.md`:

``` markdown
---
cluster: git-versioning
articles: [git-workflow.md, mr-scheme.md, branching-strategy.md]
tags: [git, versioning, workflow]
status: open
---

## Findings
- git-workflow.md and mr-scheme.md define PR naming differently
- branching-strategy.md assumes gitflow, mr-scheme.md assumes trunk-based
- git-workflow.md references deprecated tooling

## Recommendation
Merge into one canonical article. Trunk-based wins (more recent).
Deprecate git-workflow.md, update backlinks.

## Context for Resolver
Start with the three articles above. Flag unresolvable contradictions
back here rather than guessing.
```

---

## Commands and Skills

Two distinct surfaces — skills for interactive in-session use, CLI scripts for maintenance and automation.

### Skills (Claude Code slash commands — available in any session)

| Skill                  | What it does                                                |
|------------------------|-------------------------------------------------------------|
| `/wiki-log`            | Dumps session findings to `queue/session-log/open/`         |
| `/wiki-ask "question"` | Reads `wiki/_index` + relevant articles, answers in context |
| `/wiki-resolve <case>` | Starts interactive resolver session for a lint case         |

### CLI Scripts (shell — croonable, terminal)

| Command               | What it does                                                           |
|-----------------------|------------------------------------------------------------------------|
| `wiki compile`        | Ingests `raw/` and `queue/session-log/open/`, updates wiki and indexes |
| `wiki lint`           | Clusters articles by tags, writes case files to `queue/lint/open/`     |
| `wiki enhance`        | Suggests new articles, cross-links, connections                        |
| `wiki ask "question"` | Same as `/wiki-ask` but from terminal — suitable for scripted/cron use |

Skills and CLI scripts share underlying implementation where applicable. Git commits are a separate manual step.

---

## Document Lifecycle

| Type                  | Location             | Lifetime                          |
|-----------------------|----------------------|-----------------------------------|
| Source material       | `raw/`               | Permanent                         |
| Session log entries   | `queue/session-log/` | Purge after Wiki AI processes     |
| Lint case files       | `queue/lint/`        | Purge after Resolver closes       |
| Wiki articles         | `wiki/`              | Permanent, evolving               |
| Asset sidecars        | `assets/*.meta.md`   | Permanent, refreshable            |
| Links registry        | `assets/links.md`    | Permanent, append-only entries    |
| Outputs (Q&A, charts) | `outputs/`           | Filed back into wiki or discarded |

---

## Multi-User Considerations

In a multi-user setup the Wiki AI and Lint AI run on a shared server — single writer,
no conflicts. Session AIs run locally and only write to `queue/session-log/open/`, which is safe
for multiple concurrent authors (filenames include `author` to avoid collisions).

The Resolver is the only role that writes to the wiki interactively. In multi-user mode it uses
`resolver.mode = branch` to avoid direct writes to main. The server wiki AI and lint AI can be
triggered by cron or a git post-receive hook (future).

**Future addition:** a "resolution queue" where the Resolver writes a structured resolution
document instead of editing the wiki directly, and the server Wiki AI applies it. This would
eliminate the branch/PR overhead for small fixes but loses the interactive nature of the
Resolver session.

---

## Deferred Decisions

- **Vault split:** whether tech/finance/research eventually become separate vaults
- **Reorganization approval:** when the AI proposes restructuring, does it ask first or act and let git undo?
- **Automation:** cron scheduling, git post-receive hook for server, wiki-aware session auto-logging
- **Resolution queue:** structured resolution documents as an alternative to branch-based Resolver

---

## What This Is Not

- Not Obsidian-dependent — plain markdown works in any editor
- Not a RAG system — the AI navigates via `wiki/_index` and reads relevant docs directly
- Not rebuilable from `raw/` alone — the wiki is the product, not a cache
- Not a fixed structure — domains and layout evolve as content grows
- Not timestamp-heavy — git is the record; dates appear only in queue filenames

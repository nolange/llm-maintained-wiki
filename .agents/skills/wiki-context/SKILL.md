---
name: wiki-context
description: >
  Wiki system conventions and boundaries. Loaded automatically when working
  with vault files (wiki/, queue/, assets/, raw/) or discussing the wiki
  system, compile, lint, or vault operations.
compatibility: Claude Code only — uses user-invocable, paths, and ${CLAUDE_SKILL_DIR}.
user-invocable: false
paths: wiki/**,queue/**,assets/**,raw/**
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/wiki:*)
---

# Wiki system conventions

## Vault structure

```
raw/                        flat drop zone — source material only
queue/session-log/open/     session AI dumps (unprocessed)
queue/session-log/processed/
queue/lint/open/            lint case files (unresolved)
queue/lint/resolved/
wiki/                       flat article store
wiki/_index                 tab-separated registry: path<TAB>tags<TAB>title
assets/                     PDFs, images, drawio + .meta.md sidecars
assets/links.md             external URL registry
outputs/                    Q&A answers, charts, slides
```

## Article frontmatter

```yaml
---
tags: [tag1, tag2]
folder: name       # optional — AI assigns if absent; never move if user set it
status: draft | stable | needs-review
---
```

## Hard rules

- Never edit `wiki/_index` by hand — only Wiki AI (`wiki compile`) maintains it
- Never change `folder:` if it was set by the user
- Session AI writes only to `queue/session-log/open/` — never to `wiki/` directly
- Resolver writes to `wiki/` articles and moves case files — nothing else
- Do not reconstruct wiki articles from `raw/` — the wiki is the source of truth
- Grep for relationships; do not add `referenced-by` metadata

## Wiki CLI

> **Claude Code only** — `${CLAUDE_SKILL_DIR}` is not substituted in other tools. If running outside Claude Code, invoke the wiki CLI directly: `python3 -m wiki <command>` from the project root, or via the `llm-wiki.sh` wrapper.

The wiki CLI is available at `${CLAUDE_SKILL_DIR}/scripts/wiki`. Use it for maintenance operations — never edit vault files manually when a CLI command does the job.

| Command | What it does | When to use |
|---|---|---|
| `${CLAUDE_SKILL_DIR}/scripts/wiki compile` | Ingest `raw/` and session-log queue into wiki articles | After dropping source files |
| `${CLAUDE_SKILL_DIR}/scripts/wiki lint` | Detect contradictions and inconsistencies → case files | Periodic quality sweep |
| `${CLAUDE_SKILL_DIR}/scripts/wiki enhance` | Surface gaps, thin articles, missing cross-links | Periodic improvement sweep |
| `${CLAUDE_SKILL_DIR}/scripts/wiki check` | Validate vault integrity (no LLM) | Before committing |
| `${CLAUDE_SKILL_DIR}/scripts/wiki check --fix` | Validate and auto-fix frontmatter normalization | After editing articles |
| `${CLAUDE_SKILL_DIR}/scripts/wiki ask "question"` | Answer a question via CLI (writes to outputs/) | Scripted/batch use |

Always run `check --fix` after editing wiki articles directly.

## AI role boundaries

| Role       | Writes to                        | Never touches              |
|------------|----------------------------------|----------------------------|
| Wiki AI    | `wiki/`, `wiki/_index`           | `queue/`, `raw/`           |
| Lint AI    | `queue/lint/open/`               | `wiki/`, `raw/`            |
| Resolver   | `wiki/` articles, `queue/lint/resolved/` | `raw/`, `_index` tags unless article changed |
| Session AI | `queue/session-log/open/`        | everything else            |

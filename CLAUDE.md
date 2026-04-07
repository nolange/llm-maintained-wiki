# Wiki Project

LLM-driven personal knowledge base system, inspired by [Karpathy's approach](https://x.com/karpathy/status/2039805659525644595).

## Quick reference

```bash
python3 -m wiki --help
python3 -m wiki init
python3 -m wiki check
python3 -m unittest tests/test_structural.py -v
```

## Project layout

```
wiki/           Python package (source of truth for all logic)
  cli.py        Entry point — argparse subcommands
  config.py     Config loading (TOML + dataclass)
  manifest.py   sha256sum-format tracking of processed raw/ files
  frontmatter.py YAML frontmatter read/write
  llm.py        LLM CLI wrapper (claude / copilot)
  ingest.py     Text extraction (md, pdf, docx, adoc, rst, drawio, images)
  vault.py      Vault initialization logic
  prompts/      LLM system prompts (compile, lint, enhance, ask)
docs/           Design and implementation documents
tests/
  fixtures/     mock_claude.py, config.toml, fixture responses
  test_structural.py  Unit tests (no LLM, no vault required)
.claude/commands/     Wiki skills (wiki-log, wiki-ask, wiki-resolve)
pyproject.toml
```

## Vault

Data lives separately at `~/wiki/` (configured in `~/.config/wiki/config.toml`).

`~/wiki/.claude/commands/` is a symlink to `.claude/commands/` in this project.

Vault structure:
```
raw/                  flat drop zone for source material
queue/session-log/    open/ → processed/  (session AI dumps)
queue/lint/           open/ → resolved/   (lint case files)
wiki/                 flat article store + _index (tab-separated registry)
assets/               PDFs, images, drawio + .meta.md sidecars
assets/links.md       external URL registry
outputs/              Q&A answers, charts, slides
```

## Environment

- **Python 3.11+** — no `from __future__ import annotations`, use native union syntax (`X | Y`)
- **Dependencies:** PyYAML, requests — pre-installed, do not run pip
- **Run with:** `python3` (not `python`)
- **Tests:** `python3 -m unittest tests/test_structural.py -v`
- **System tools:** claude, git, jq, pdftotext, pandoc

## Config (`~/.config/wiki/config.toml`)

```toml
[vault]
path = "~/wiki"

[user]
name = "username"

[resolver]
mode = "direct"        # "branch" for multi-user: creates PR instead of direct edit

[llm]
backend = "claude"     # or "copilot"

[claude]
path = "claude"
args = []

[copilot]
path = "copilot"
args = ["--allow-all-tools"]

[compile]
max_files = 10          # max source files per LLM batch (split large drops)
```

## Key conventions

- **No hardcoded paths** — everything goes through `config.Config.vault_path`
- **No fixed wiki structure** — articles are flat, organized by tags, AI assigns folders unless `folder:` is set in frontmatter
- **Manifest** uses sha256sum format (`<hash>  <path>`), verifiable with `sha256sum -c raw/.manifest`
- **Compile is always incremental** — never rebuilds the full wiki
- **The wiki is the source of truth** — not `raw/`; cannot be reconstructed from `raw/` alone
- **Grep over metadata** — don't track `referenced-by`; use grep

## Article frontmatter

```yaml
---
tags: [tsn, networking, realtime]
folder: tsn            # optional — AI assigns if absent, never moved if set by user
status: draft | stable | needs-review
---
```

## AI roles

| Role | Triggered by | Writes to |
|---|---|---|
| Wiki AI | `wiki compile` | wiki articles, indexes |
| Lint AI | `wiki lint` | queue/lint/open/ |
| Resolver | `/wiki-resolve` skill | wiki articles (direct or via PR) |
| Session AI | any session | queue/session-log/open/ via `/wiki-log` |

## Skills

Skills live in `.claude/commands/` and are available in any Claude Code session opened in this project or in `~/wiki/` (symlinked).

- `/wiki-log` — dump session findings to queue/session-log/open/
- `/wiki-ask` — answer a question using the wiki
- `/wiki-resolve <case-file>` — interactively resolve a lint case

## Multi-user

Set `resolver.mode = "branch"` — the Resolver creates a `wiki/resolve/<case>` branch and opens a PR instead of editing main directly. Wiki AI and Lint AI run on a shared server (cron or git post-receive hook). Session AIs run locally and write to queue/session-log/open/ only.

## Design documents

- `docs/wiki-system-design.md` — architecture, principles, data formats
- `docs/implementation-plan.md` — phase-by-phase build plan with done criteria

# Wiki Vault

This is a personal wiki vault. Read `wiki/_index` to see all available articles.

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
- **Always use standard markdown links** in article bodies: `[display text](relative-path.md)` — never `[[wikilinks]]`

## Markdown format

All wiki articles use **GitHub Flavored Markdown (GFM)**:

- Fenced code blocks (`` ``` `` or `~~~~`), never indented code blocks.
- Fenced blocks inside list items must be indented to the list item's content column — a fence at column 0 breaks out of the list.
- Pipe tables.
- Straight/ASCII quotes — no curly `""` or `''`.
- Math: `$…$` inline, `$$…$$` display.
- Always a blank line before lists, tables, fenced blocks, and headings.
- Lines under 100 characters; prefer breaking at a sentence boundary.
- **German prose punctuation**: use `:` as the term-definition separator (e.g. `**Term**: description`), not `—`. Reserve `—` for genuine parenthetical asides.
- **Loose lists**: a blank line followed by text indented to the list-item content column is a continuation paragraph inside that item — preserve this structure rather than collapsing it inline.

### Pandoc normalisation

Run pandoc on an article to check for structural issues (tables not parsed as
tables, lists broken, etc.) or to normalise formatting in-place:

```bash
# Check — inspect output on stdout
pandoc --wrap=preserve -s \
  -f markdown-smart+yaml_metadata_block \
  -t gfm+tex_math_dollars+yaml_metadata_block \
  <file>

# Normalise in-place
pandoc --wrap=preserve -s \
  -f markdown-smart+yaml_metadata_block \
  -t gfm+tex_math_dollars+yaml_metadata_block \
  <file> -o <file>
```

Offer to run this after editing articles, or whenever a formatting problem is suspected.

## Wiki CLI

Use `scripts/wiki <command>` from the vault root. Never edit vault files manually when a CLI command does the job.

| Command | What it does | When to use |
|---|---|---|
| `scripts/wiki compile` | Ingest `raw/` and session-log queue into wiki articles | After dropping source files |
| `scripts/wiki lint` | Detect contradictions and inconsistencies → case files | Periodic quality sweep |
| `scripts/wiki enhance` | Surface gaps, thin articles, missing cross-links | Periodic improvement sweep |
| `scripts/wiki check` | Validate vault integrity (no LLM) | Before committing |
| `scripts/wiki check --fix` | Validate and auto-fix frontmatter normalization | After editing articles |
| `scripts/wiki ask "question"` | Answer a question via CLI (writes to outputs/) | Scripted/batch use |

Always run `check --fix` after editing wiki articles directly.

## AI role boundaries

| Role       | Writes to                                        | Never touches                                        |
|------------|--------------------------------------------------|------------------------------------------------------|
| Wiki AI    | `wiki/`, `wiki/_index`                           | `queue/`, `raw/`                                     |
| Lint AI    | `queue/lint/open/`                               | `wiki/`, `raw/`                                      |
| Resolver   | `wiki/` articles, `queue/lint/resolved/`         | `raw/`, `_index` tags unless article changed         |
| Session AI | `queue/session-log/open/`                        | everything else                                      |

---
name: wiki-compare
description: >
  Compare an external document against a personal wiki to find conflicts,
  knowledge gaps, and sync opportunities. Use this skill when given a document
  (source code, specification, asciidoc, markdown, PDF, etc.) and asked to
  check it against the wiki, find what the wiki is missing, spot contradictions,
  or propose wiki updates. Produces a structured report with Conflicts, Wiki
  Gaps, Document Issues, and proposed edits.
compatibility: >
  Requires a wiki vault. Vault path is read from ~/.config/wiki/config.toml
  (key: vault.path). Falls back to ~/wiki. System tools: pandoc or pdftotext
  for binary formats.
argument-hint: <document-path>
disable-model-invocation: true
allowed-tools: Read Write Bash(pdftotext:*) Bash(pandoc:*) Bash(python3:*)
---

# Wiki Compare

Compare an external document against the wiki knowledge base and surface what
needs to be reconciled.

## Setup

Read the vault path:

```bash
python3 -c "
import tomllib, pathlib, os
cfg = pathlib.Path('~/.config/wiki/config.toml').expanduser()
if cfg.exists():
    data = tomllib.loads(cfg.read_text())
    print(pathlib.Path(data['vault']['path']).expanduser())
else:
    print(pathlib.Path('~/wiki').expanduser())
"
```

The wiki lives at `<vault>/wiki/`. The index is `<vault>/wiki/_index`.

## Step 1 — Load the wiki index

Read `<vault>/wiki/_index`. Format: `relative-path<TAB>tags<TAB>title` (lines
starting with `#` are comments). Build a lookup: `stem → {path, tags, title}`.

## Step 2 — Read the target document

Read the file the user provided. If it is a binary or structured format, extract
plain text first:

| Format       | Command                                      |
|--------------|----------------------------------------------|
| PDF          | `pdftotext <file> -`                         |
| docx / odt   | `pandoc -t plain <file>`                     |
| asciidoc     | `pandoc -f asciidoc -t plain <file>` or read raw |
| markdown/txt | read directly                                |

## Step 3 — Identify related wiki articles

From the document, extract:
- Main topics (headings, repeated nouns, domain terms)
- Explicit tag-like labels if present

Match against wiki article tags and titles. Cast wide: include any article whose
tag set overlaps with the document's topic area. Read the **full body** of every
matched article.

If no articles match, say so and stop — do not fabricate a comparison.

## Step 4 — Cross-compare

Produce a report with four sections. See [references/report-format.md](references/report-format.md)
for the exact output structure.

**Conflicts** — statements in the two sources that contradict each other
(different values, opposite procedures, incompatible constraints). For each:
- Quote or paraphrase the wiki passage (article + section)
- Quote or paraphrase the document passage
- State the conflict clearly

**Wiki gaps** — facts, decisions, or constraints in the document that are absent
from all matched wiki articles. These are candidates for adding to the wiki.

**Document issues** — wiki knowledge the document appears to ignore or contradict
where the wiki is likely authoritative. Flag these; do not edit the document.

**Cross-link opportunities** — matched articles that should link to each other
but currently do not.

## Step 5 — Propose and execute wiki updates

After the report, list proposed wiki edits:
- Article to update
- Section to add or change
- Exact new content

Ask the user which edits to approve. For each approved edit: read the article,
make the targeted change, write it back. Do not rewrite surrounding content.

If `_index` tags need updating for a changed article, update them too.

## Rules

- Do not invent facts. Only draw from what the documents say.
- Make surgical edits only — never rewrite a whole article.
- Do not modify the external document unless explicitly asked.
- If either source is ambiguous on a point, say so rather than guessing.

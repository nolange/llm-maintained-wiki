# wiki — LLM-driven personal knowledge base

A personal wiki system where dropping files into a folder is enough to build and maintain a structured knowledge base. Inspired by [Karpathy's approach](https://x.com/karpathy/status/2039805659525644595).

The system has four automated roles:

| Role       | Command         | What it does                                          |
|------------|-----------------|-------------------------------------------------------|
| Wiki AI    | `wiki compile`  | Turns raw source files into structured wiki articles  |
| Lint AI    | `wiki lint`     | Finds contradictions, duplicates, and inconsistencies |
| Resolver   | `/wiki-resolve` | Fixes lint cases interactively in Claude Code         |
| Session AI | `/wiki-log`     | Captures findings from a work session into the queue  |

---

## Requirements

- **Python 3.11+**
- **[Claude Code CLI](https://claude.ai/code)** (`claude`) — the default LLM backend
- **pdftotext** — for PDF ingestion (`apt install poppler-utils` / `brew install poppler`)
- **pandoc** — for DOCX, ODT, AsciiDoc, reStructuredText (`apt install pandoc` / `brew install pandoc`)
- **git** — for version control of the vault
- **gh** — GitHub CLI, required only for multi-user branch mode (`apt install gh` / `brew install gh`)

To verify:

``` bash
claude --version
pdftotext -v
pandoc --version
git --version
```

---

## Installation

``` bash
git clone <this-repo> ~/CLionProjects/karpathy
cd ~/CLionProjects/karpathy
```

No pip install needed — dependencies (PyYAML, requests) are pre-installed on the target system.

Verify everything is wired up:

``` bash
python3 -m wiki --help
```

---

## Setup

### 1. Create the config file

``` bash
mkdir -p ~/.config/wiki
cat > ~/.config/wiki/config.toml << 'EOF'
[vault]
path = "~/wiki"

[user]
name = "yourname"         # used in session-log filenames

[resolver]
mode = "direct"           # "branch" for multi-user (creates PRs instead)

[llm]
backend = "claude"

[claude]
path = "claude"
args = ["-p"]

[compile]
max_files = 10            # max source files per LLM batch
EOF
```

For **Copilot** instead of Claude (*untested*):

``` toml
[llm]
backend = "copilot"

[copilot]
path = "copilot"
args = ["--autopilot", "--max-autopilot-continues", "10", "-p"]
```

### 2. Initialize the vault

``` bash
python3 -m wiki init
```

This creates the full directory structure at `~/wiki/`:

```
~/wiki/
  raw/                        ← drop source files here
  queue/
    session-log/open/         ← session AI writes here
    session-log/processed/
    lint/open/                ← lint cases waiting for resolution
    lint/resolved/
  wiki/                       ← compiled articles live here
    _index.md                 ← article registry (AI-maintained)
  assets/                     ← PDFs, images, drawio files
    links.md                  ← external URL registry
  outputs/                    ← ask answers and enhance reports
  .gitignore
```

### 3. Initialize a git repository

The wiki is the source of truth. Version control it:

``` bash
cd ~/wiki
git init
git add -A
git commit -m "init: vault structure"
```

### 4. Link skills into the vault (optional but recommended)

The Claude Code slash commands (`/wiki-log`, `/wiki-ask`, `/wiki-resolve`) are available
when Claude Code is opened in this project directory. To also use them from `~/wiki/`:

``` bash
mkdir -p ~/wiki/.claude
ln -s ~/CLionProjects/karpathy/.claude/commands ~/wiki/.claude/commands
```

---

## Workflow

### Step 1 — Add source material

Drop files into `~/wiki/raw/`. Supported formats:

| Format                | How it's processed                  |
|-----------------------|-------------------------------------|
| `.md`                 | Read directly                       |
| `.pdf`                | Text extracted with `pdftotext`     |
| `.docx` `.odt`        | Converted to Markdown with `pandoc` |
| `.adoc` `.rst`        | Converted to Markdown with `pandoc` |
| `.drawio`             | Diagram structure extracted to YAML |
| `.png` `.jpg` `.jpeg` | Passed to Claude multimodal         |

``` bash
cp ~/Downloads/tsn-spec.pdf ~/wiki/raw/
cp ~/notes/architecture.md ~/wiki/raw/
```

### Step 2 — Compile

``` bash
python3 -m wiki compile
```

The Wiki AI reads each new/changed file in `raw/`, produces or updates a wiki article in
`wiki/`, updates `wiki/_index.md`, rebuilds tag indexes, and registers any external URLs
found in `assets/links.md`.

Also processes open session-log entries from `queue/session-log/open/` (moves them to
`processed/` after).

Compile is **incremental** — only files new or changed since the last run are processed.
Running it twice on the same input is a no-op.

```
Compiling: 2 raw file(s), 0 session log entry(s), 0 new asset(s).
Running 1 LLM batch(es) (max 10 files each).
Done.
```

### Step 3 — Check integrity

``` bash
python3 -m wiki check
```

Validates the vault without calling any LLM:

- Every article has `tags` (list) and `status` (`draft`/`stable`/`needs-review`) in frontmatter
- All links in `_index.md` resolve to files on disk and vice versa
- Every non-markdown file in `assets/` has a `.meta.md` sidecar
- Every entry in `assets/links.md` has a `### Why` section

Exits with code 0 on success, code 1 with a list of violations. Suitable as a git pre-commit hook:

``` bash
echo 'python3 -m wiki check' >> ~/wiki/.git/hooks/pre-commit
chmod +x ~/wiki/.git/hooks/pre-commit
```

### Step 4 — Lint

``` bash
python3 -m wiki lint
```

Clusters articles by shared tags, then asks the Lint AI to read each cluster as a set and
look for real problems: contradictions, duplicates, outdated content, inconsistencies,
missing links.

Each problem produces a case file in `queue/lint/open/`:

```
queue/lint/open/lint-tsn-2026-04-05.md
```

Clusters where **all** articles have `status: stable` are skipped.

```
Linting cluster 'tsn' (4 article(s))...
Linting cluster 'networking' (2 article(s))...
Processed 2 cluster(s).
```

### Step 5 — Resolve lint cases (interactive)

Open Claude Code in the wiki directory and run the resolve skill:

``` bash
cd ~/wiki
claude   # opens Claude Code interactively
```

Then inside Claude Code:

```
/wiki-resolve queue/lint/open/lint-tsn-2026-04-05.md
```

The Resolver reads the case file and the affected articles, presents the findings, and
works through the fixes interactively with you. When done:

- **`direct` mode**: edits articles on the current branch, moves case file to `resolved/`
- **`branch` mode**: creates `wiki/resolve/<case>` branch, opens a PR, moves case file to `resolved/`

If a contradiction cannot be resolved without more context, it flags the case rather than guessing.

After resolving, commit:

``` bash
git add -A && git commit -m "resolve: tsn-scheduling-conflict"
```

### Step 6 — Enhance

``` bash
python3 -m wiki enhance
```

Surveys the wiki structure and writes a report to `outputs/enhance-YYYY-MM-DD.md` with
concrete suggestions:

- Missing cross-links between related articles
- Topic gaps — recurring themes with no dedicated article
- Article candidates — topics implied by existing articles
- Thin articles that could be expanded

Enhance is **suggestions only** — it does not modify wiki articles. You decide what to act on.

```
Generating enhancement report...
Report written to: /home/you/wiki/outputs/enhance-2026-04-05.md
```

### Step 7 — Ask

**Non-interactive** (answer written to `outputs/`, suitable for scripting):

``` bash
python3 -m wiki ask "How does TSN Credit-Based Shaper work?"
```

The script selects the most relevant articles by keyword matching, passes them to the LLM,
and writes the answer to `outputs/YYYY-MM-DD-<topic>.md`.

```
Querying wiki (3 article(s): tsn-cbs.md, tsn-overview.md, 802.1q.md)...
Answer written to: /home/you/wiki/outputs/2026-04-05-how-does-tsn-credit-based-shape.md
```

**Interactive** (live session with wiki context pre-loaded):

``` bash
python3 -m wiki ask -i "How does TSN Credit-Based Shaper work?"
# or
python3 -m wiki ask --interactive "How does TSN Credit-Based Shaper work?"
```

Launches Claude in interactive mode with the pre-selected articles already loaded as
context. You can ask follow-up questions, explore related topics, or request specific
formatting — all within the same session.

### Step 8 — Session logging (in Claude Code)

During any work session in Claude Code, capture findings without interrupting the session:

```
/wiki-log
```

The Session AI collects discoveries, decisions, guideline candidates, and open questions
from the current session and writes them to `queue/session-log/open/`. The next `wiki compile`
run will incorporate them into the wiki.

---

## Supported article frontmatter

``` yaml
---
tags: [tsn, networking, realtime]
folder: tsn            # optional — AI assigns if absent, never moved if user set it
status: draft          # draft | stable | needs-review
---
```

Articles with `status: stable` are skipped by `wiki lint`.

---

## Multi-user (*untested*)

Set `resolver.mode = "branch"` in config. The Resolver creates a branch and opens a PR
instead of editing main directly. Wiki AI and Lint AI run on a shared server (cron or git
post-receive hook). Session AIs run locally and write only to `queue/session-log/open/`.

---

## Quick reference

``` bash
python3 -m wiki init                          # create vault structure
python3 -m wiki compile                       # ingest raw/ → wiki articles
python3 -m wiki check                         # validate integrity (no LLM)
python3 -m wiki lint                          # detect problems → case files
python3 -m wiki enhance                       # surface gaps and suggestions
python3 -m wiki ask "question"               # batch answer → outputs/
python3 -m wiki ask -i "question"            # interactive session with context
python3 -m wiki --help
```

Claude Code skills (run inside a `claude` session):

```
/wiki-log                                     # capture session findings
/wiki-ask "question"                          # answer using wiki
/wiki-resolve queue/lint/open/<case>.md      # resolve a lint case
```

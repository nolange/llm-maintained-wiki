# Wiki System — Implementation Plan

## Dependencies

```
System: claude, git, jq, pdftotext, pandoc
Python: PyYAML, requests (Python 3.11+)
```

---

## Repository Layout

```
~/wiki/
  raw/
    .manifest                   ← sha256sum format: "<hash>  <relative_path>"
  queue/
    session-log/
      open/
      processed/
    lint/
      open/
      resolved/
  wiki/
    _index
  assets/
    links.md
  outputs/
  scripts/
    wiki.py                     ← CLI entry point
    lib/
      config.py                 ← config loading
      manifest.py               ← manifest read/write
      claude.py                 ← claude CLI wrapper
      frontmatter.py            ← YAML frontmatter read/write
      ingest.py                 ← raw file text extraction and conversion
    prompts/
      compile.md                ← Wiki AI system prompt
      lint.md                   ← Lint AI system prompt
      enhance.md                ← Enhance AI system prompt
      ask.md                    ← Ask AI system prompt
  tests/
    test_structural.py          ← wiki check tests
    test_smoke.py               ← end-to-end smoke tests
    fixtures/
      mock_claude.py            ← fake claude executable
      responses/                ← fixture response files keyed by prompt type
  .agents/
    skills/
      wiki-log/SKILL.md         ← /wiki-log skill
      wiki-ask/SKILL.md         ← /wiki-ask skill
      wiki-resolve/SKILL.md     ← /wiki-resolve skill
      wiki-compare/SKILL.md     ← /wiki-compare skill
  .claude/
    skills/                     ← symlink → ../.agents/skills
  .gitignore
```

Config lives outside the vault:

```
~/.config/wiki/config.toml
```

---

## Config System

`~/.config/wiki/config.toml`:

``` toml
[vault]
path = "~/wiki"

[user]
name = "username"                   ← used in session-log filenames to avoid collisions

[resolver]
mode = "direct"                 ← "direct": edit main branch (single-user)
                                   "branch": create branch + open PR (multi-user)

[claude]
path = "claude"
args = ["-p"]

[copilot]
path = "copilot"
args = ["--allow-all-tools", "-p"]

[llm]
backend = "claude"              ← "claude" or "copilot"
```

Resolution order for config file (highest wins):
1. `--config <path>` CLI flag
2. `~/.config/wiki/config.toml`

`lib/config.py` exposes `load(path: Path | None) -> Config` and a `vault_path() -> Path`
used everywhere. No other code touches paths or the claude binary path directly.

Test config example (`tests/fixtures/config.toml`):

``` toml
[vault]
path = "/tmp/wiki-test-vault"

[claude]
path = "tests/fixtures/mock_claude.py"
```

---

## Manifest

`raw/.manifest` in standard sha256sum format:

```
abc123...  raw/tech/tsn-spec.pdf
def456...  raw/some-article.md
```

- Verifiable with `sha256sum -c raw/.manifest`
- On compile: files absent from manifest or with changed hash are treated as new
- After successful compilation of a file: manifest entry is updated
- Committed alongside wiki changes
- `lib/manifest.py` exposes: `load() -> dict[str, str]`, `is_new(path) -> bool`, `mark_done(path)`

---

## Claude CLI Wrapper (`lib/claude.py`)

All LLM calls go through one function:

``` python
def run(prompt: str, context: str = "") -> str
```

- Reads `claude` binary path from config
- Invokes `<claude_path> -p "<prompt>\n\n<context>"` via subprocess
- Captures stdout, raises on non-zero exit
- Simple retry: 3 attempts with 5s backoff (stdlib, no third-party retry lib)
- No special mock code path — tests point `claude.path` to `tests/fixtures/mock_claude.py`

Prompts are loaded from `scripts/prompts/*.md`, not hardcoded. This keeps the AI
behaviour tunable separately from the plumbing.

---

## Frontmatter Utils (`lib/frontmatter.py`)

``` python
def read(path: Path) -> tuple[dict, str]      # returns (metadata, body)
def write(path: Path, meta: dict, body: str)  # writes file with frontmatter
def read_tag(path: Path, key: str) -> Any     # reads single key without full parse
```

Uses PyYAML. Frontmatter delimited by `---`. Files without frontmatter return empty dict.

---

## Ingest (`lib/ingest.py`)

Extracts plain text or structured representation from source files:

| Extension             | Tool                     | Output                   |
|-----------------------|--------------------------|--------------------------|
| `.md`                 | read directly            | str                      |
| `.adoc` `.rst`        | `pandoc` → markdown      | str                      |
| `.pdf`                | `pdftotext`              | str                      |
| `.docx` `.odt`        | `pandoc` → markdown      | str                      |
| `.drawio`             | custom XML parser → YAML | str                      |
| `.png` `.jpg` `.jpeg` | pass path directly       | Path (claude multimodal) |
| other                 | skip, log warning        | None                     |

DrawIO conversion extracts nodes, edges, and labels into YAML — lossy but sufficient
for AI understanding of diagram semantics:

``` yaml
nodes:
  - id: "1"
    label: "Service A"
    shape: rectangle
edges:
  - from: "1"
    to: "2"
    label: "reads/writes"
```

---

## Phase 1 — Foundation

**Goal:** vault exists, config works, skeleton CLI runs.

Deliverables:

- `scripts/wiki.py` — argparse skeleton, all subcommands registered but not implemented
- `lib/config.py` — `load()` with `--config` flag + default path, exposes `llm_backend()`, `resolver_mode()`, `user_name()`
- `lib/manifest.py` — sha256sum format, load/save/is_new/mark_done
- `lib/frontmatter.py` — read/write via PyYAML
- `lib/claude.py` — `run()` with retry, binary path from config
- `lib/ingest.py` — format dispatch table, all converters
- `scripts/init.py` — creates vault directory structure and blank seed files
- `tests/fixtures/mock_claude.py` — reads prompt type, returns matching fixture response
- `tests/fixtures/config.toml` — points at temp vault and mock claude
- `.gitignore`

Done when: `python scripts/init.py --config <path>` creates the full vault structure
and `python scripts/wiki.py --help` lists all subcommands.

---

## Phase 2 — Compile (`wiki compile`)

**Goal:** drop files in `raw/`, run compile, wiki articles and indexes appear.

Steps the Wiki AI performs (driven by `prompts/compile.md`):

1.  Find new/changed files in `raw/` via manifest
2.  Extract text via `lib/ingest.py`
3.  Read `wiki/_index` for existing structure context
4.  For each new file: call Claude to produce or update a wiki article
5.  Assign tags and folder (respecting `folder:` frontmatter if user set it)
6.  Update `wiki/_index`
7.  Scan compiled content for external URLs → add missing entries to `assets/links.md`
8.  For new assets: generate sidecar `.meta.md` via Claude
9.  For `fetch-abstract: true` entries in `assets/links.md`: fetch via `requests`, generate abstract
10. Process `queue/session-log/open/` — same pipeline, move to `processed/` after
11. Update manifest

Deliverables:

- `wiki compile` subcommand implemented
- `prompts/compile.md`
- URL registry maintenance

Done when: dropping a markdown file in `raw/`, running `wiki compile`, produces a wiki
article with frontmatter and an updated `wiki/_index`.

---

## Phase 3 — Skills

Four Claude Code skills in agentskills.io format. Each is a directory under `.agents/skills/` containing a `SKILL.md` with YAML frontmatter and instructions — no Python. `.claude/skills/` is a symlink to `.agents/skills/` so Claude Code picks them up.

### `/wiki-log` (`.agents/skills/wiki-log/SKILL.md`)

Instructions tell the session AI to:

- Collect findings, guideline candidates, open questions from the current session
- Write a structured entry to `queue/session-log/open/YYYY-MM-DD-<topic>.md`

### `/wiki-ask "question"` (`.agents/skills/wiki-ask/SKILL.md`)

Instructions tell the session AI to:

- Read `wiki/_index.md` to orient
- Identify relevant articles by tag and title
- Read those articles
- Answer the question in context
- Write substantial answers to `outputs/YYYY-MM-DD-<topic>.md`

### `/wiki-resolve <case-file>` (`.agents/skills/wiki-resolve/SKILL.md`)

Instructions tell the session AI to:

- Read the named case file from `queue/lint/open/`
- Read all articles listed in it
- Read `resolver.mode` from config and follow the appropriate flow:

**`direct` mode (single-user / personal):**

- Edit articles on the current branch
- Commit changes
- Move case file to `queue/lint/resolved/`

**`branch` mode (multi-user / work):**

- Create branch `wiki/resolve/<case-name>`
- Edit articles on that branch
- Commit, push, open PR via `gh pr create` using case file summary as description
- Move case file to `queue/lint/resolved/`
- Note the PR URL in the resolved case file for traceability

In both modes: flag unresolvable contradictions back into the case file rather than guessing.

Done when: all three `.md` skill files exist and are invokable in a Claude Code session.

---

## Phase 4 — Lint (`wiki lint`)

**Goal:** detect problems in existing wiki content and produce actionable case files.

Lint is *corrective* — it finds things that are wrong: contradictions, duplicates,
outdated content, inconsistencies between articles covering the same topic.

Steps the Lint AI performs (driven by `prompts/lint.md`):

1.  Read `wiki/_index` to get all articles and their tags
2.  Cluster articles by shared tags
3.  For each cluster (up to 10 articles): read all, call Claude to analyse
4.  If issues found: write case file to `queue/lint/open/YYYY-MM-DD-<cluster>.md`
5.  Skip clusters where all articles have `status: stable`

Deliverables:

- `wiki lint` subcommand
- `prompts/lint.md`

Done when: seeding two wiki articles with a deliberate inconsistency and shared tag,
running `wiki lint` produces a case file naming both articles and describing the conflict.

---

## Phase 5 — Enhance (`wiki enhance`)

**Goal:** surface opportunities to grow and connect the wiki.

Enhance is *additive* — it finds things that are missing: cross-links between articles
that reference each other's concepts without linking, topic gaps where coverage is thin,
and candidates for new articles based on recurring themes.

Steps (driven by `prompts/enhance.md`):

1.  Read `wiki/_index` + all article frontmatter
2.  Call Claude to identify: missing cross-links, topic gaps, article candidates
3.  Write suggestions to `outputs/enhance-YYYY-MM-DD.md`
4.  Does not modify wiki — suggestions only, you decide what to act on

Deliverables:

- `wiki enhance` subcommand
- `prompts/enhance.md`

---

## Phase 6 — Ask CLI (`wiki ask "question"`)

Same logic as `/wiki-ask` skill but from terminal. Writes answer to `outputs/` and
prints the path. Suitable for scripted use and cron-generated reports.

Deliverables:

- `wiki ask` subcommand
- `prompts/ask.md` (shared with `/wiki-ask` skill)

---

## Phase 7 — Testing

### Mock Claude (`tests/fixtures/mock_claude.py`)

A small executable that the test config points `claude.path` at. Reads the prompt,
detects the prompt type (compile / lint / enhance / ask), and returns a matching
fixture response from `tests/fixtures/responses/`. Deterministic, free, fast.

No special code paths in `lib/claude.py` — the mock is just another executable.

### Structural validator (`wiki check`)

Validates wiki integrity without LLM:

- Every article has required frontmatter keys (`tags`, `status`)
- All internal links resolve to real files
- All articles in `wiki/_index` exist on disk and vice versa
- All asset sidecars exist for non-markdown files in `assets/`
- All entries in `assets/links.md` have a `### Why` section

Exits with a list of violations and exit code 1. Suitable as a git pre-commit hook.

### Smoke tests (`tests/test_smoke.py`)

End-to-end scenarios using the test config (temp vault + mock claude).
Assertions are structural only — LLM output is non-deterministic, mock output is not.

| Test | Setup | Assert |
|----|----|----|
| compile basic | drop `.md` in `raw/`, run compile | article in `wiki/`, has frontmatter, in `wiki/_index` |
| compile PDF | drop `.pdf` in `raw/`, run compile | article in `wiki/`, sidecar in `assets/` |
| compile adoc | drop `.adoc` in `raw/`, run compile | article in `wiki/` |
| compile drawio | drop `.drawio` in `assets/`, run compile | sidecar `.meta.md` exists |
| compile session-log | write entry to `queue/session-log/open/`, run compile | entry moved to `processed/`, manifest updated |
| URL registry | source doc with external URL, run compile | URL in `assets/links.md` |
| lint produces case | two articles with shared tag and seeded inconsistency | case file in `queue/lint/open/` |
| manifest idempotent | run compile twice on same input | manifest unchanged, no duplicate articles |
| check passes | clean vault | exit code 0 |
| check fails | article missing `tags` key | exit code 1, violation listed |

### Structural tests (`tests/test_structural.py`)

Unit tests for `lib/` modules — no LLM involved:

- `manifest.py`: load, is_new, mark_done, sha256sum format round-trip
- `frontmatter.py`: read/write round-trip, missing frontmatter, malformed YAML
- `ingest.py`: format dispatch, DrawIO YAML conversion
- `config.py`: resolution order, `--config` override, missing file

---

## Deferred

- Cron setup and git post-receive hook for server triggering
- Wiki-aware session auto-logging
- Vault split (tech/finance/research)
- Reorganization approval workflow
- Resolution queue: structured resolution documents as alternative to branch-based Resolver

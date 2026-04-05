#!/usr/bin/env python3
"""Mock claude/copilot CLI for tests — agent mode.

Simulates Claude's direct file-writing behavior based on prompt type:
- compile: writes a deterministic test article to wiki/
- lint:    writes a deterministic case file to queue/lint/open/
- enhance: writes a deterministic enhance report to outputs/
- ask:     writes a deterministic answer to outputs/
"""

import re
import sys
from pathlib import Path


def _vault(_prompt: str) -> Path:
    # llm.py always sets cwd=vault when invoking the LLM binary
    return Path.cwd()


def _handle_compile(vault: Path) -> None:
    wiki_dir = vault / "wiki"
    wiki_dir.mkdir(exist_ok=True)

    (wiki_dir / "test-article.md").write_text(
        "---\ntags: [test, example]\nstatus: draft\n---\n\n# Test Article\n\nCompiled from source material.\n",
        encoding="utf-8",
    )
    (vault / "wiki" / "_index.md").write_text(
        "# Wiki Index\n\n- [Test Article](test-article.md) — tags: [test, example]\n",
        encoding="utf-8",
    )


def _handle_lint(vault: Path, prompt: str) -> None:
    m = re.search(r"## Cluster: tag `([^`]+)`", prompt)
    tag = m.group(1) if m else "test"
    from datetime import date
    today = date.today().isoformat()
    case_dir = vault / "queue" / "lint" / "open"
    case_dir.mkdir(parents=True, exist_ok=True)
    case_file = case_dir / f"lint-{tag}-{today}.md"
    case_file.write_text(
        f"---\ncluster: {tag}\narticles: [article-a.md, article-b.md]\ntags: [{tag}]\nstatus: open\n---\n\n"
        "## Findings\n- Mock inconsistency found between articles.\n\n"
        "## Recommendation\nUpdate article-a.md to match article-b.md.\n\n"
        "## Context for Resolver\n- Both articles are valid; prefer article-b.md wording.\n",
        encoding="utf-8",
    )


def _handle_enhance(vault: Path) -> None:
    from datetime import date
    today = date.today().isoformat()
    outputs_dir = vault / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    report = outputs_dir / f"enhance-{today}.md"
    report.write_text(
        f"# Wiki Enhancement Report — {today}\n\n"
        "## Missing Cross-Links\nNone identified.\n\n"
        "## Topic Gaps\nNone identified.\n\n"
        "## Article Candidates\nNone identified.\n\n"
        "## Thin Articles\nNone identified.\n",
        encoding="utf-8",
    )


def _handle_ask(vault: Path, prompt: str) -> None:
    from datetime import date
    m = re.search(r"## Question\s*\n\s*(.+)", prompt)
    question = m.group(1).strip() if m else "unknown"
    today = date.today().isoformat()
    slug = re.sub(r"[^a-z0-9]+", "-", question.lower())[:40].strip("-")
    outputs_dir = vault / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    answer_file = outputs_dir / f"{today}-{slug}.md"
    answer_file.write_text(
        f"# Answer: {question}\n\nThis is a mock answer. The wiki does not cover this topic.\n\n"
        "## Gaps\n- No relevant articles found.\n",
        encoding="utf-8",
    )


def main() -> None:
    prompt = sys.argv[-1] if len(sys.argv) > 1 else ""
    lower = prompt.lower()

    vault = _vault(prompt)

    if "source files to process" in lower or "session-log entries" in lower:
        _handle_compile(vault)
    elif "## cluster: tag" in lower:
        _handle_lint(vault, prompt)
    elif "enhancement report" in lower or "enhance-" in lower or "wiki enhance" in lower:
        _handle_enhance(vault)
    elif "## question" in lower:
        _handle_ask(vault, prompt)
    # else: no-op


if __name__ == "__main__":
    main()

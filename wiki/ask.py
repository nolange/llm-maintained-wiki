"""wiki ask — answer a question using the wiki."""

import re
import logging
import subprocess
from datetime import date
from pathlib import Path

from . import frontmatter
from .config import Config
from .llm import run as llm_run

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_MAX_ARTICLES = 5


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Article selection
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _score_article(question_tokens: set[str], path: Path, meta: dict) -> int:
    """Simple keyword relevance score."""
    article_tokens = _tokenize(path.stem)
    for tag in meta.get("tags", []):
        article_tokens.update(_tokenize(tag))
    return len(question_tokens & article_tokens)


def _select_articles(wiki_dir: Path, question: str) -> list[Path]:
    """Return up to _MAX_ARTICLES most relevant article paths."""
    question_tokens = _tokenize(question)
    scored: list[tuple[int, Path]] = []

    for md_path in sorted(wiki_dir.glob("*.md")):
        if md_path.name.startswith("_"):
            continue
        try:
            meta, _ = frontmatter.read(md_path)
        except Exception:
            continue
        score = _score_article(question_tokens, md_path, meta)
        scored.append((score, md_path))

    scored.sort(key=lambda x: (-x[0], x[1].name))

    # Include any article with score > 0, up to _MAX_ARTICLES; fall back to top-scored
    relevant = [p for s, p in scored if s > 0][:_MAX_ARTICLES]
    if not relevant and scored:
        relevant = [scored[0][1]]
    return relevant


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_ask_prompt(
    vault: Path,
    question: str,
    index_content: str,
    article_paths: list[Path],
    output_path: Path | None = None,
) -> str:
    instructions = _load_prompt("ask")
    today = date.today().isoformat()

    lines = [
        instructions,
        "",
        f"## Vault root\n\n{vault}",
        "",
        f"## Today's date\n\n{today}",
        "",
        f"## Question\n\n{question}",
        "",
        "## Wiki Index (`wiki/_index.md`)",
        "",
        index_content.strip(),
        "",
    ]

    if article_paths:
        lines.append("## Pre-selected articles\n")
        for p in article_paths:
            lines.append(f"- {p}")
        lines.append("")

    lines.append("## Instructions")
    lines.append("")
    lines.append("Read the pre-selected articles and answer the question.")
    if output_path:
        lines.append(
            f"If the answer is substantial (more than a few sentences), also write it to: `{output_path}`"
        )
    lines.append("")
    lines.append("Distinguish clearly between what the wiki states, what is inferred, and what is not covered.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------

def _prepare(cfg: Config, question: str) -> tuple[Path, str, list[Path], Path] | None:
    """Shared setup for both ask modes. Returns (vault, index_content, articles, output_path)."""
    vault = cfg.vault_path
    wiki_dir = vault / "wiki"
    index_path = wiki_dir / "_index.md"

    if not wiki_dir.exists():
        print("Wiki directory does not exist. Run `wiki init` first.")
        return None

    if not index_path.exists():
        print("Wiki index not found. Run `wiki compile` first.")
        return None

    index_content = index_path.read_text(encoding="utf-8")
    article_paths = _select_articles(wiki_dir, question)

    today = date.today().isoformat()
    slug = re.sub(r"[^a-z0-9]+", "-", question.lower())[:40].strip("-")
    output_path = vault / "outputs" / f"{today}-{slug}.md"

    return vault, index_content, article_paths, output_path


def ask(cfg: Config, question: str, dry_run: bool = False) -> None:
    """Non-interactive: call LLM, write answer to outputs/, print path."""
    result = _prepare(cfg, question)
    if result is None:
        return
    vault, index_content, article_paths, output_path = result

    if article_paths:
        names = ", ".join(p.name for p in article_paths)
        print(f"Querying wiki ({len(article_paths)} article(s): {names})...")
    else:
        print("Querying wiki (no articles matched — wiki may be empty)...")

    prompt = _build_ask_prompt(vault, question, index_content, article_paths, output_path)
    llm_run(prompt, config=cfg, cwd=vault, dry_run=dry_run)

    if not dry_run and output_path.exists():
        print(f"Answer written to: {output_path}")


def ask_interactive(cfg: Config, question: str) -> None:
    """Interactive: launch LLM in interactive mode with wiki context pre-loaded.

    The context (index + pre-selected articles) is passed as the initial message.
    The LLM binary is invoked without the -p flag so it starts an interactive session.
    """
    result = _prepare(cfg, question)
    if result is None:
        return
    vault, index_content, article_paths, _ = result

    if article_paths:
        names = ", ".join(p.name for p in article_paths)
        print(f"Starting interactive session ({len(article_paths)} article(s) pre-loaded: {names})")
    else:
        print("Starting interactive session (no articles pre-loaded — wiki may be empty)")

    # Build context prompt without an output_path instruction (user drives the session)
    initial_prompt = _build_ask_prompt(vault, question, index_content, article_paths, output_path=None)

    # Strip -p (or --print) from args so the LLM starts in interactive mode
    interactive_args = [a for a in cfg.llm_args if a not in ("-p", "--print")]
    cmd = [cfg.llm_path, *interactive_args, initial_prompt]

    try:
        subprocess.run(cmd, cwd=vault)
    except FileNotFoundError:
        print(f"Error: LLM binary not found: {cfg.llm_path!r}. Check [claude] path in config.")

"""wiki enhance — surface opportunities to grow and connect the wiki."""

import logging
import random
from datetime import date
from pathlib import Path

from . import frontmatter
from .config import Config
from .llm import run as llm_run

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def _collect_frontmatter_summary(wiki_dir: Path, max_articles: int | None = None) -> str:
    """Return a compact frontmatter listing, randomly sampled to max_articles if set."""
    all_paths = sorted(
        p for p in wiki_dir.rglob("*.md") if not p.name.startswith("_")
    )
    if max_articles is not None and len(all_paths) > max_articles:
        paths = random.sample(all_paths, max_articles)
        sampled = True
    else:
        paths = all_paths
        sampled = False

    lines = []
    for md_path in sorted(paths):
        try:
            meta, _ = frontmatter.read(md_path)
        except Exception:
            continue
        tags = meta.get("tags", [])
        status = meta.get("status", "unknown")
        lines.append(f"- **{md_path.name}** — tags: {tags}, status: {status}")

    if not lines:
        return "(no articles)"
    if sampled:
        lines.append(
            f"\n_(showing {max_articles} of {len(all_paths)} articles — sampled randomly)_"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_enhance_prompt(vault: Path, frontmatter_summary: str, user_prompt: str | None = None) -> str:
    instructions = _load_prompt("enhance")
    today = date.today().isoformat()
    output_path = f"outputs/enhance-{today}.md"

    lines = [
        instructions,
        "",
        f"## Today's date\n\n{today}",
        "",
        "## Wiki Index\n\n@wiki/_index",
        "",
        "## Article Frontmatter Summary",
        "",
        frontmatter_summary,
        "",
        "## Instructions",
        "",
        f"Write the enhancement report to: `{output_path}`",
        "",
        "Use today's date in the report heading.",
    ]

    if user_prompt:
        lines += [
            "",
            "## Additional user instructions",
            "",
            user_prompt,
        ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

_DEFAULT_MAX_ARTICLES = 50


def enhance(cfg: Config, dry_run: bool = False, max_articles: int = _DEFAULT_MAX_ARTICLES, user_prompt: str | None = None) -> None:
    vault = cfg.vault_path
    wiki_dir = vault / "wiki"
    index_path = wiki_dir / "_index"

    if not wiki_dir.exists():
        print("Wiki directory does not exist. Run `wiki init` first.")
        return

    if not index_path.exists():
        print("Wiki index not found. Run `wiki compile` first.")
        return

    all_articles = [p for p in wiki_dir.rglob("*.md") if not p.name.startswith("_")]
    total = len(all_articles)
    frontmatter_summary = _collect_frontmatter_summary(wiki_dir, max_articles)

    today = date.today().isoformat()
    output_path = vault / "outputs" / f"enhance-{today}.md"

    if total > max_articles:
        print(f"Generating enhancement report ({max_articles}/{total} articles sampled)...")
    else:
        print(f"Generating enhancement report ({total} article(s))...")
    prompt = _build_enhance_prompt(vault, frontmatter_summary, user_prompt=user_prompt)
    llm_run(prompt, config=cfg, cwd=vault, dry_run=dry_run)

    if not dry_run:
        if output_path.exists():
            print(f"Report written to: {output_path}")
        else:
            print("Done. (No output file created — wiki may be empty or LLM produced no report.)")

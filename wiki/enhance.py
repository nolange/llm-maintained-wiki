"""wiki enhance — surface opportunities to grow and connect the wiki."""

import logging
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

def _collect_frontmatter_summary(wiki_dir: Path) -> str:
    """Return a compact frontmatter listing for all articles."""
    lines = []
    for md_path in sorted(wiki_dir.glob("*.md")):
        if md_path.name.startswith("_"):
            continue
        try:
            meta, _ = frontmatter.read(md_path)
        except Exception:
            continue
        tags = meta.get("tags", [])
        status = meta.get("status", "unknown")
        lines.append(f"- **{md_path.name}** — tags: {tags}, status: {status}")
    return "\n".join(lines) if lines else "(no articles)"


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_enhance_prompt(vault: Path, index_content: str, frontmatter_summary: str) -> str:
    instructions = _load_prompt("enhance")
    today = date.today().isoformat()
    output_path = vault / "outputs" / f"enhance-{today}.md"

    lines = [
        instructions,
        "",
        f"## Vault root\n\n{vault}",
        "",
        f"## Today's date\n\n{today}",
        "",
        "## Wiki Index (`wiki/_index.md`)",
        "",
        index_content.strip(),
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

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def enhance(cfg: Config, dry_run: bool = False) -> None:
    vault = cfg.vault_path
    wiki_dir = vault / "wiki"
    index_path = wiki_dir / "_index.md"

    if not wiki_dir.exists():
        print("Wiki directory does not exist. Run `wiki init` first.")
        return

    if not index_path.exists():
        print("Wiki index not found. Run `wiki compile` first.")
        return

    index_content = index_path.read_text(encoding="utf-8")
    frontmatter_summary = _collect_frontmatter_summary(wiki_dir)

    today = date.today().isoformat()
    output_path = vault / "outputs" / f"enhance-{today}.md"

    print(f"Generating enhancement report...")
    prompt = _build_enhance_prompt(vault, index_content, frontmatter_summary)
    llm_run(prompt, config=cfg, cwd=vault, dry_run=dry_run)

    if not dry_run:
        if output_path.exists():
            print(f"Report written to: {output_path}")
        else:
            print("Done. (No output file created — wiki may be empty or LLM produced no report.)")

"""wiki lint — analyse wiki articles for inconsistencies and produce case files."""

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
# Article discovery and clustering
# ---------------------------------------------------------------------------

def _read_articles(wiki_dir: Path) -> list[tuple[Path, dict, str]]:
    """Return (path, meta, body) for each non-index article."""
    result = []
    for md_path in sorted(wiki_dir.glob("*.md")):
        if md_path.name.startswith("_"):
            continue
        try:
            meta, body = frontmatter.read(md_path)
            result.append((md_path, meta, body))
        except Exception as exc:
            logger.warning(f"Skipping {md_path.name}: {exc}")
    return result


def _cluster_by_tag(
    articles: list[tuple[Path, dict, str]],
) -> dict[str, list[tuple[Path, dict, str]]]:
    """Group articles by tag. Returns only clusters with 2+ articles."""
    tag_map: dict[str, list[tuple[Path, dict, str]]] = {}
    for path, meta, body in articles:
        for tag in meta.get("tags", []):
            tag_map.setdefault(tag, []).append((path, meta, body))
    return {tag: entries for tag, entries in tag_map.items() if len(entries) >= 2}


def _all_stable(entries: list[tuple[Path, dict, str]]) -> bool:
    return all(meta.get("status") == "stable" for _, meta, _ in entries)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_lint_prompt(vault: Path, tag: str, entries: list[tuple[Path, dict, str]]) -> str:
    instructions = _load_prompt("lint")
    today = date.today().isoformat()

    lines = [
        instructions,
        "",
        f"## Vault root\n\n{vault}",
        "",
        f"## Today's date\n\n{today}",
        "",
        f"## Cluster: tag `{tag}`",
        "",
        "Articles in this cluster:",
        "",
    ]

    for path, meta, body in entries:
        lines.append(f"### {path.name}")
        lines.append("")
        lines.append(f"**Path:** {path}")
        lines.append("")
        lines.append("**Content:**")
        lines.append("")
        lines.append(f"```markdown")
        lines.append(body.strip())
        lines.append("```")
        lines.append("")

    lines += [
        "## Instructions",
        "",
        f"Write any case files to `{vault}/queue/lint/open/` using the filename format "
        "`lint-<cluster>-<YYYY-MM-DD>.md`.",
        "",
        "If no issues are found, output only `## No issues found` and do not create any files.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def lint(cfg: Config, dry_run: bool = False) -> None:
    vault = cfg.vault_path
    wiki_dir = vault / "wiki"

    if not wiki_dir.exists():
        print("Wiki directory does not exist. Run `wiki init` first.")
        return

    articles = _read_articles(wiki_dir)
    if not articles:
        print("No articles found to lint.")
        return

    clusters = _cluster_by_tag(articles)
    if not clusters:
        print("No multi-article clusters found.")
        return

    # Sort for deterministic processing order
    sorted_clusters = sorted(clusters.items())

    skipped = 0
    processed = 0
    for tag, entries in sorted_clusters:
        # Cap cluster size at 10 as per design
        entries = entries[:10]

        if _all_stable(entries):
            logger.info(f"Skipping stable cluster: {tag}")
            skipped += 1
            continue

        print(f"Linting cluster '{tag}' ({len(entries)} article(s))...")
        prompt = _build_lint_prompt(vault, tag, entries)
        llm_run(prompt, config=cfg, cwd=vault, dry_run=dry_run)
        processed += 1

    summary_parts = [f"Processed {processed} cluster(s)."]
    if skipped:
        summary_parts.append(f"Skipped {skipped} stable cluster(s).")
    print(" ".join(summary_parts))

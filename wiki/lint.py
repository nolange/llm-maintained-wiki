"""wiki lint — analyse wiki articles for inconsistencies and produce case files."""

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
# Article discovery and clustering
# ---------------------------------------------------------------------------

def _read_articles(wiki_dir: Path) -> list[tuple[Path, dict, str]]:
    """Return (path, meta, body) for each non-index article."""
    result = []
    for md_path in sorted(wiki_dir.rglob("*.md")):
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


def _open_case_clusters(vault: Path) -> set[str]:
    """Return the set of cluster/tag names that already have an open lint case."""
    open_dir = vault / "queue" / "lint" / "open"
    if not open_dir.exists():
        return set()
    clusters: set[str] = set()
    for case_path in open_dir.glob("*.md"):
        try:
            meta, _ = frontmatter.read(case_path)
        except Exception:
            continue
        # Accept either 'cluster' key or fall back to tags list
        if "cluster" in meta:
            clusters.add(str(meta["cluster"]))
        for tag in meta.get("tags", []):
            clusters.add(str(tag))
    return clusters


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_lint_prompt(vault: Path, tag: str, entries: list[tuple[Path, dict, str]], user_prompt: str | None = None) -> str:
    instructions = _load_prompt("lint")
    today = date.today().isoformat()

    def rel(p: Path) -> str:
        try:
            return str(p.relative_to(vault))
        except ValueError:
            return str(p)

    lines = [
        instructions,
        "",
        f"## Today's date\n\n{today}",
        "",
        f"## Cluster: tag `{tag}`",
        "",
        "Read each article in this cluster:",
        "",
    ]

    for path, _meta, _body in entries:
        lines.append(f"- @{rel(path)}")

    lines += [
        "",
        "## Instructions",
        "",
        f"Write any case files to `queue/lint/open/` using the filename format "
        "`lint-<cluster>-<YYYY-MM-DD>.md`.",
        "",
        "If no issues are found, output only `## No issues found` and do not create any files.",
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

_DEFAULT_MAX_CALLS = 5


def lint(cfg: Config, dry_run: bool = False, max_calls: int = _DEFAULT_MAX_CALLS, user_prompt: str | None = None) -> None:
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

    open_clusters = _open_case_clusters(vault)

    candidates: list[tuple[str, list[tuple[Path, dict, str]]]] = []
    skipped_stable = 0
    skipped_open = 0

    for tag, entries in clusters.items():
        entries = entries[:10]  # cap cluster size
        if _all_stable(entries):
            logger.info(f"Skipping stable cluster: {tag}")
            skipped_stable += 1
        elif tag in open_clusters:
            logger.info(f"Skipping cluster with open report: {tag}")
            skipped_open += 1
        else:
            candidates.append((tag, entries))

    if not candidates:
        parts = ["Nothing to lint."]
        if skipped_open:
            parts.append(f"{skipped_open} cluster(s) already have open reports.")
        if skipped_stable:
            parts.append(f"{skipped_stable} stable cluster(s) skipped.")
        print(" ".join(parts))
        return

    # Randomly sample up to max_calls from the candidate pool
    sample = random.sample(candidates, min(max_calls, len(candidates)))
    total = len(candidates)
    print(
        f"Linting {len(sample)}/{total} candidate cluster(s) "
        f"(max={max_calls}"
        + (f", {skipped_open} already have open reports" if skipped_open else "")
        + (f", {skipped_stable} stable skipped" if skipped_stable else "")
        + ")."
    )

    for tag, entries in sample:
        print(f"  Cluster '{tag}' ({len(entries)} article(s))...")
        prompt = _build_lint_prompt(vault, tag, entries, user_prompt=user_prompt)
        llm_run(prompt, config=cfg, cwd=vault, dry_run=dry_run, task="lint")

    print(f"Done. ({len(sample)} LLM call(s))")

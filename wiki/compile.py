"""wiki compile — ingest raw/ and session-log/ into wiki articles."""

import logging
import re
import shutil
from pathlib import Path

from . import frontmatter, ingest, manifest
from .config import Config
from .llm import run as llm_run

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def _find_new_raw_files(vault: Path, mfst: dict[str, str]) -> list[Path]:
    raw_dir = vault / "raw"
    if not raw_dir.exists():
        return []
    files = []
    for path in sorted(raw_dir.rglob("*")):
        if path.is_dir() or path.name == ".manifest":
            continue
        if manifest.is_new(mfst, vault, path):
            files.append(path)
    return files


def _find_session_entries(vault: Path) -> list[Path]:
    open_dir = vault / "queue" / "session-log" / "open"
    if not open_dir.exists():
        return []
    return sorted(open_dir.glob("*.md"))


def _find_new_assets(vault: Path) -> list[Path]:
    """Assets in assets/ that do not yet have a .meta.md sidecar."""
    assets_dir = vault / "assets"
    if not assets_dir.exists():
        return []
    result = []
    for path in sorted(assets_dir.iterdir()):
        if path.is_dir() or path.suffix == ".md":
            continue
        sidecar = path.with_name(path.name + ".meta.md")
        if not sidecar.exists():
            result.append(path)
    return result


# ---------------------------------------------------------------------------
# Readable file preparation
# ---------------------------------------------------------------------------

def _ensure_readable(raw_paths: list[Path]) -> list[tuple[Path, Path]]:
    """Return (original_path, readable_path) pairs.

    For natively-readable formats, readable_path == original_path.
    For formats needing conversion (PDF, DOCX, DrawIO), a temp file is created.
    Files that cannot be converted are omitted with a warning.
    """
    result = []
    for path in raw_paths:
        readable = ingest.extract_to_file(path)
        if readable is None:
            logger.warning(f"Skipping unsupported format: {path.name}")
        else:
            result.append((path, readable))
    return result


def _cleanup_temp(pairs: list[tuple[Path, Path]]) -> None:
    """Delete temp files created by _ensure_readable."""
    for original, readable in pairs:
        if readable != original and readable.exists():
            readable.unlink()


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_agent_prompt(
    vault: Path,
    readable_raw: list[tuple[Path, Path]],
    session_paths: list[Path],
    new_asset_paths: list[Path],
) -> str:
    instructions = _load_prompt("compile")

    # All paths are relative to vault (which is the working directory).
    def rel(p: Path) -> str:
        try:
            return str(p.relative_to(vault))
        except ValueError:
            return str(p)

    lines = [instructions, ""]

    if readable_raw:
        lines.append("## Source files to process\n")
        for original, readable in readable_raw:
            if readable == original:
                lines.append(f"- @{rel(readable)}")
            else:
                lines.append(f"- @{rel(readable)}  (extracted from {original.name})")
        lines.append("")

    if session_paths:
        lines.append("## Session-log entries to process\n")
        for p in session_paths:
            lines.append(f"- @{rel(p)}")
        lines.append("")

    if new_asset_paths:
        lines.append("## Assets needing sidecars\n")
        for p in new_asset_paths:
            lines.append(f"- @{rel(p)}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Batching
# ---------------------------------------------------------------------------

def _make_batches(
    readable_raw: list[tuple[Path, Path]],
    session_paths: list[Path],
    new_asset_paths: list[Path],
    max_files: int,
) -> list[tuple[list[tuple[Path, Path]], list[Path], list[Path]]]:
    """Split work into LLM batches of at most max_files raw files each.

    Session entries and new assets are included only in the first batch — they
    are few and should not be repeated across batches.  If there are no raw
    files but there is session/asset work, a single batch is returned.
    """
    if not readable_raw:
        if session_paths or new_asset_paths:
            return [([], session_paths, new_asset_paths)]
        return []

    result = []
    for i in range(0, len(readable_raw), max_files):
        chunk = readable_raw[i : i + max_files]
        result.append((
            chunk,
            session_paths if i == 0 else [],
            new_asset_paths if i == 0 else [],
        ))
    return result


# ---------------------------------------------------------------------------
# Post-run tag index rebuild
# ---------------------------------------------------------------------------

def _rebuild_all_tag_indexes(vault: Path) -> None:
    """Scan all wiki articles and regenerate per-tag index files."""
    wiki_dir = vault / "wiki"
    if not wiki_dir.exists():
        return

    tag_map: dict[str, list[tuple[str, str]]] = {}
    for md_path in sorted(wiki_dir.glob("*.md")):
        if md_path.name.startswith("_"):
            continue
        try:
            meta, body = frontmatter.read(md_path)
        except Exception:
            continue
        article_tags = meta.get("tags", [])
        title = md_path.stem
        for line in body.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        for tag in article_tags:
            tag_map.setdefault(tag, []).append((md_path.name, title))

    for tag, entries in tag_map.items():
        lines = [f"# Tag Index: {tag}\n"]
        for filename, title in sorted(entries):
            lines.append(f"- [{title}]({filename})")
        index_path = wiki_dir / f"_index_{tag}.md"
        index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    logger.info(f"Rebuilt {len(tag_map)} tag index(es)")


# ---------------------------------------------------------------------------
# URL registry (Python-only, no LLM)
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"https?://[^\s\)\]\>\"']+")


def _extract_urls(paths: list[Path]) -> set[str]:
    """Return all unique HTTP(S) URLs found across the given text files."""
    urls: set[str] = set()
    for path in paths:
        if not path.exists() or path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            urls.update(_URL_RE.findall(text))
        except OSError:
            pass
    return urls


def _update_links_registry(vault: Path, urls: set[str]) -> None:
    """Append stub entries for URLs not already in assets/links.md."""
    if not urls:
        return
    links_path = vault / "assets" / "links.md"
    existing = links_path.read_text(encoding="utf-8") if links_path.exists() else ""

    new_entries = [u for u in sorted(urls) if u not in existing]
    if not new_entries:
        return

    with open(links_path, "a", encoding="utf-8") as f:
        for url in new_entries:
            f.write(f"\n## {url}\n- **tags:** []\n\n### Why\n<!-- TODO -->\n")

    logger.info(f"Registered {len(new_entries)} new URL(s) in assets/links.md")


# ---------------------------------------------------------------------------
# Session-log cleanup
# ---------------------------------------------------------------------------

def _move_to_processed(vault: Path, entries: list[Path]) -> None:
    processed_dir = vault / "queue" / "session-log" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    for path in entries:
        dest = processed_dir / path.name
        shutil.move(str(path), dest)
        logger.info(f"Moved to processed: {path.name}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compile(cfg: Config, dry_run: bool = False) -> None:
    vault = cfg.vault_path

    # 1. Discover new work
    mfst = manifest.load(vault)
    raw_files_paths = _find_new_raw_files(vault, mfst)
    session_entries_paths = _find_session_entries(vault)
    new_asset_paths = _find_new_assets(vault)

    if not raw_files_paths and not session_entries_paths and not new_asset_paths:
        print("Nothing new to compile.")
        return

    print(
        f"Compiling: {len(raw_files_paths)} raw file(s), "
        f"{len(session_entries_paths)} session log entry(s), "
        f"{len(new_asset_paths)} new asset(s)."
    )

    # 2. Prepare readable versions of source files
    readable_raw = _ensure_readable(raw_files_paths)

    # 3. Split into batches and call LLM once per batch
    batches = _make_batches(readable_raw, session_entries_paths, new_asset_paths, cfg.compile_max_files)
    print(f"Running {len(batches)} LLM batch(es) (max {cfg.compile_max_files} files each).")

    for i, (raw_batch, sessions, assets) in enumerate(batches, 1):
        if len(batches) > 1:
            print(f"  Batch {i}/{len(batches)}...")
        prompt = _build_agent_prompt(vault, raw_batch, sessions, assets)
        llm_run(prompt, config=cfg, cwd=vault, dry_run=dry_run)

    if dry_run:
        _cleanup_temp(readable_raw)
        return

    # 4. Extract URLs from source material and update links registry (before temp cleanup)
    source_paths = [readable for _, readable in readable_raw] + list(session_entries_paths)
    urls = _extract_urls(source_paths)
    _update_links_registry(vault, urls)

    # 5. Clean up any temp extraction files
    _cleanup_temp(readable_raw)

    # 6. Rebuild tag indexes from updated wiki/
    _rebuild_all_tag_indexes(vault)

    # 7. Update manifest for processed raw files
    for path in raw_files_paths:
        manifest.mark_done(mfst, vault, path)
    manifest.save(vault, mfst)

    # 8. Move processed session log entries
    _move_to_processed(vault, session_entries_paths)

    print("Done.")

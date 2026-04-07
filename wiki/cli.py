"""wiki — CLI entry point."""

import argparse
import re
import sys
from pathlib import Path

from . import config, frontmatter, vault as vault_mod


def _parse_index_filenames(index_path: Path) -> list[str]:
    """Parse filenames from the tab-separated wiki/_index registry."""
    if not index_path.exists():
        return []
    filenames = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        filename = line.split("\t")[0].strip()
        if filename:
            filenames.append(filename)
    return filenames


# ---------------------------------------------------------------------------
# Subcommand stubs (implemented in later phases)
# ---------------------------------------------------------------------------

def cmd_compile(args: argparse.Namespace, cfg: config.Config) -> None:
    from .compile import compile
    compile(cfg, dry_run=args.dry_run)


def cmd_lint(args: argparse.Namespace, cfg: config.Config) -> None:
    from .lint import lint
    lint(cfg, dry_run=args.dry_run, max_calls=args.max_calls, user_prompt=args.prompt)


def cmd_enhance(args: argparse.Namespace, cfg: config.Config) -> None:
    from .enhance import enhance
    enhance(cfg, dry_run=args.dry_run, max_articles=args.max_articles, user_prompt=args.prompt)


def cmd_ask(args: argparse.Namespace, cfg: config.Config) -> None:
    from .ask import ask, ask_interactive
    if args.interactive:
        ask_interactive(cfg, args.question)
    else:
        ask(cfg, args.question, dry_run=args.dry_run)


# ---------------------------------------------------------------------------
# `wiki init`
# ---------------------------------------------------------------------------

def cmd_init(args: argparse.Namespace, cfg: config.Config) -> None:
    vault_mod.init(cfg)


# ---------------------------------------------------------------------------
# `wiki reindex` — rebuild _index from article frontmatter (no LLM)
# ---------------------------------------------------------------------------

def cmd_reindex(args: argparse.Namespace, cfg: config.Config) -> None:
    wiki_dir = cfg.vault_path / "wiki"
    index_path = wiki_dir / "_index"

    if not wiki_dir.exists():
        print("Wiki directory does not exist. Run `wiki init` first.")
        return

    lines = ["# filename\ttags\ttitle"]
    count = 0
    for md_path in sorted(wiki_dir.glob("*.md")):
        try:
            meta, body = frontmatter.read(md_path)
        except Exception as exc:
            print(f"  skip {md_path.name}: {exc}")
            continue
        tags = ",".join(meta.get("tags", []))
        title = md_path.stem
        for line in body.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        lines.append(f"{md_path.name}\t{tags}\t{title}")
        count += 1

    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Rebuilt _index with {count} article(s).")


# ---------------------------------------------------------------------------
# `wiki check` — structural validator (no LLM)
# ---------------------------------------------------------------------------

def cmd_check(args: argparse.Namespace, cfg: config.Config) -> None:
    violations: list[str] = []

    vault = cfg.vault_path
    wiki_dir = vault / "wiki"
    assets_dir = vault / "assets"
    index_path = wiki_dir / "_index"
    links_path = assets_dir / "links.md"

    # 1. Every article must have tags (list) and status (str)
    article_files = list(wiki_dir.glob("*.md")) if wiki_dir.exists() else []

    for md_path in sorted(article_files):
        try:
            meta, _ = frontmatter.read(md_path)
        except Exception as exc:
            violations.append(f"[frontmatter] {md_path.name}: failed to parse — {exc}")
            continue

        if "tags" not in meta:
            violations.append(f"[frontmatter] {md_path.name}: missing required key 'tags'")
        elif not isinstance(meta["tags"], list):
            violations.append(
                f"[frontmatter] {md_path.name}: 'tags' must be a list, "
                f"got {type(meta['tags']).__name__}"
            )

        if "status" not in meta:
            violations.append(f"[frontmatter] {md_path.name}: missing required key 'status'")
        elif not isinstance(meta["status"], str):
            violations.append(
                f"[frontmatter] {md_path.name}: 'status' must be a string, "
                f"got {type(meta['status']).__name__}"
            )

    # 2. Every article in _index must exist on disk
    indexed_filenames = _parse_index_filenames(index_path)
    for filename in indexed_filenames:
        if not (wiki_dir / filename).exists():
            violations.append(
                f"[index] '{filename}' listed in _index but does not exist on disk"
            )

    # 3. Every article on disk must be listed in _index
    indexed_set = set(indexed_filenames)
    for md_path in sorted(article_files):
        if md_path.name not in indexed_set:
            violations.append(
                f"[index] '{md_path.name}' exists on disk but is not listed in _index"
            )

    # 4. Every non-markdown file in assets/ must have a .meta.md sidecar
    if assets_dir.exists():
        for asset_path in sorted(assets_dir.iterdir()):
            if asset_path.is_dir() or asset_path.suffix == ".md":
                continue
            sidecar = asset_path.with_name(asset_path.name + ".meta.md")
            if not sidecar.exists():
                violations.append(
                    f"[assets] '{asset_path.name}' has no sidecar '{sidecar.name}'"
                )

    # 5. Every entry in assets/links.md must have a ### Why section
    if links_path.exists():
        links_text = links_path.read_text(encoding="utf-8")
        for entry in re.split(r"(?m)^## ", links_text)[1:]:
            first_line = entry.splitlines()[0].strip() if entry.strip() else "(unknown)"
            if "### Why" not in entry:
                violations.append(
                    f"[links] Entry '## {first_line}' is missing a '### Why' section"
                )

    if violations:
        for v in violations:
            print(v)
        sys.exit(1)
    else:
        print("OK")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="wiki",
        description="LLM-driven personal wiki management tool.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to config TOML file (default: ~/.config/wiki/config.toml).",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    def _add_dry_run(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "-n", "--dry-run",
            action="store_true",
            default=False,
            dest="dry_run",
            help="Show what would be sent to the LLM without calling it.",
        )

    sub.add_parser("init", help="Initialize vault directory structure.")
    sub.add_parser("reindex", help="Rebuild wiki/_index from article frontmatter (no LLM).")
    sub.add_parser("check", help="Validate wiki structural integrity (no LLM).")

    compile_p = sub.add_parser("compile", help="Compile raw/ and session-log/ into wiki articles.")
    _add_dry_run(compile_p)

    lint_p = sub.add_parser("lint", help="Analyse wiki for inconsistencies and produce case files.")
    lint_p.add_argument(
        "-m", "--max-calls",
        type=int,
        default=5,
        dest="max_calls",
        metavar="N",
        help="Max LLM calls per run — clusters are sampled randomly (default: 5).",
    )
    lint_p.add_argument(
        "-p", "--prompt",
        type=str,
        default=None,
        metavar="TEXT",
        help="Additional instructions appended to the lint prompt (e.g. focus area or extra constraints).",
    )
    _add_dry_run(lint_p)

    enhance_p = sub.add_parser("enhance", help="Suggest new articles, cross-links, and topic gaps.")
    enhance_p.add_argument(
        "-m", "--max-articles",
        type=int,
        default=50,
        dest="max_articles",
        metavar="N",
        help="Max articles included in the prompt — sampled randomly (default: 50).",
    )
    enhance_p.add_argument(
        "-p", "--prompt",
        type=str,
        default=None,
        metavar="TEXT",
        help="Additional instructions appended to the enhance prompt (e.g. focus area or extra constraints).",
    )
    _add_dry_run(enhance_p)

    ask_p = sub.add_parser("ask", help="Answer a question using the wiki.")
    ask_p.add_argument("question", type=str, help="The question to ask.")
    ask_p.add_argument(
        "-i", "--interactive",
        action="store_true",
        default=False,
        help="Launch an interactive LLM session with wiki context pre-loaded.",
    )
    _add_dry_run(ask_p)

    args = parser.parse_args()
    cfg = config.load(args.config)

    dispatch = {
        "init": cmd_init,
        "reindex": cmd_reindex,
        "compile": cmd_compile,
        "lint": cmd_lint,
        "enhance": cmd_enhance,
        "check": cmd_check,
        "ask": cmd_ask,
    }

    dispatch[args.command](args, cfg)


if __name__ == "__main__":
    main()

"""Vault initialization — creates the directory structure and seed files."""

from pathlib import Path

from .config import Config

_TEMPLATES = Path(__file__).parent / "templates"
_PROJECT_ROOT = Path(__file__).parent.parent

_SEED_INDEX = "# filename\ttags\ttitle\n"

_SEED_LINKS = """\
# Links Registry

<!-- AI-maintained. Add fetch-abstract: true to trigger abstract generation on compile. -->
"""

_SEED_GITIGNORE = """\
__pycache__/
outputs/
logs/
.obsidian/
"""


def _create_dir(path: Path) -> None:
    if path.exists():
        print(f"  skip (exists): {path}")
    else:
        path.mkdir(parents=True, exist_ok=True)
        print(f"  created dir:  {path}")


def _create_file(path: Path, content: str = "") -> None:
    if path.exists():
        print(f"  skip (exists): {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"  created file: {path}")


def _create_symlink(link: Path, target: Path) -> None:
    if link.exists() or link.is_symlink():
        print(f"  skip (exists): {link}")
    else:
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
        print(f"  created link: {link} -> {target}")


def init(cfg: Config) -> None:
    """Create the full vault directory structure and seed files."""
    vault = cfg.vault_path
    print(f"Initializing vault at: {vault}\n")

    _create_dir(vault / "raw")
    _create_dir(vault / "queue" / "session-log" / "open")
    _create_dir(vault / "queue" / "session-log" / "processed")
    _create_dir(vault / "queue" / "lint" / "open")
    _create_dir(vault / "queue" / "lint" / "resolved")
    _create_dir(vault / "wiki")
    _create_dir(vault / "assets")
    _create_dir(vault / "outputs")
    _create_dir(vault / "logs")

    _create_file(vault / "raw" / ".manifest", "")
    _create_file(vault / "wiki" / "_index", _SEED_INDEX)
    _create_file(vault / "assets" / "links.md", _SEED_LINKS)
    _create_file(vault / ".gitignore", _SEED_GITIGNORE)
    _create_file(vault / "AGENTS.md", (_TEMPLATES / "vault-AGENTS.md").read_text(encoding="utf-8"))
    _create_symlink(vault / "CLAUDE.md", Path("AGENTS.md"))
    _create_symlink(vault / "scripts" / "wiki", _PROJECT_ROOT / "llm-wiki.sh")

    print("\nDone.")

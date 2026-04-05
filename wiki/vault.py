"""Vault initialization — creates the directory structure and seed files."""

from pathlib import Path

from .config import Config

_SEED_INDEX = """\
# Wiki Index

<!-- AI-maintained. Do not edit manually. -->

## Articles

(none yet)
"""

_SEED_LINKS = """\
# Links Registry

<!-- AI-maintained. Add fetch-abstract: true to trigger abstract generation on compile. -->
"""

_SEED_GITIGNORE = """\
__pycache__/
*.pyc
.DS_Store
outputs/
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

    _create_file(vault / "raw" / ".manifest", "")
    _create_file(vault / "wiki" / "_index.md", _SEED_INDEX)
    _create_file(vault / "assets" / "links.md", _SEED_LINKS)
    _create_file(vault / ".gitignore", _SEED_GITIGNORE)

    print("\nDone.")

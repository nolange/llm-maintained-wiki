"""YAML frontmatter read/write for markdown files."""

import logging
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from a text string. Returns (metadata_dict, body_str)."""
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Malformed YAML frontmatter: {e}") from e
    return meta, text[m.end():]


def read(path: Path) -> tuple[dict, str]:
    """Return (metadata_dict, body_str). Empty dict if no frontmatter."""
    text = path.read_text(encoding="utf-8")
    try:
        return parse(text)
    except ValueError as e:
        logger.warning(f"{path}: {e}")
        return {}, text


def normalized(meta: dict, body: str) -> str:
    """Return the canonical serialisation of a file with this frontmatter and body."""
    fm = yaml.dump(meta, default_flow_style=False, allow_unicode=True)
    return f"---\n{fm}---\n\n{body.lstrip('\n')}"


def write(path: Path, meta: dict, body: str) -> None:
    """Write a markdown file with YAML frontmatter."""
    path.write_text(normalized(meta, body), encoding="utf-8")


def read_key(path: Path, key: str) -> Any:
    """Read a single frontmatter key without returning the full body."""
    meta, _ = read(path)
    return meta.get(key)

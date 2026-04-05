"""YAML frontmatter read/write for markdown files."""

import logging
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def read(path: Path) -> tuple[dict, str]:
    """Return (metadata_dict, body_str). Empty dict if no frontmatter."""
    text = path.read_text(encoding="utf-8")
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        logger.warning(f"Malformed YAML frontmatter in {path}: {e}")
        return {}, text
    body = text[m.end():]
    return meta, body


def write(path: Path, meta: dict, body: str) -> None:
    """Write a markdown file with YAML frontmatter."""
    fm = yaml.dump(meta, default_flow_style=False, allow_unicode=True)
    path.write_text(f"---\n{fm}---\n{body}", encoding="utf-8")


def read_key(path: Path, key: str) -> Any:
    """Read a single frontmatter key without returning the full body."""
    meta, _ = read(path)
    return meta.get(key)

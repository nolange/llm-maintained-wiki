"""Manifest tracking for processed raw/ files.

Format: standard sha256sum lines — "<hash>  <relative_path>"
Verifiable with: sha256sum -c raw/.manifest
"""

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_MANIFEST_FILE = Path("raw") / ".manifest"


def _manifest_path(vault: Path) -> Path:
    return vault / _MANIFEST_FILE


def load(vault: Path) -> dict[str, str]:
    """Return {relative_path: sha256_hash} from the manifest file."""
    path = _manifest_path(vault)
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("  ", 1)
        if len(parts) == 2:
            hash_val, rel_path = parts
            result[rel_path] = hash_val
        else:
            logger.warning(f"Malformed manifest line: {line!r}")
    return result


def save(vault: Path, manifest: dict[str, str]) -> None:
    """Write manifest to disk in sha256sum format."""
    path = _manifest_path(vault)
    lines = [f"{hash_val}  {rel_path}" for rel_path, hash_val in sorted(manifest.items())]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def compute_hash(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def is_new(manifest: dict[str, str], vault: Path, path: Path) -> bool:
    """Return True if the file is absent from the manifest or its hash has changed."""
    rel = str(path.relative_to(vault))
    if rel not in manifest:
        return True
    return manifest[rel] != compute_hash(path)


def mark_done(manifest: dict[str, str], vault: Path, path: Path) -> None:
    """Update the manifest entry for a file in-place."""
    rel = str(path.relative_to(vault))
    manifest[rel] = compute_hash(path)

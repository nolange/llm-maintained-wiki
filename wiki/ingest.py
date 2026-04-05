"""Extract text from source files for LLM consumption."""

import logging
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
_PANDOC_EXTENSIONS = {".adoc", ".rst", ".docx", ".odt"}
# Formats Claude CLI can read natively (no extraction needed)
_NATIVE_EXTENSIONS = {".md", ".txt", ".py", ".c", ".h", ".cpp", ".rs", ".go", ".js", ".ts", ".json", ".yaml", ".toml"}


def extract_to_file(path: Path) -> Path | None:
    """Return a path that Claude can read directly.

    For natively-readable formats (text, images), returns the original path.
    For formats requiring conversion (PDF, DOCX, DrawIO), extracts content
    to a sibling temp file (``<name>.wiki-tmp.txt``) and returns that path.
    Returns None for unsupported formats.
    """
    suffix = path.suffix.lower()

    if suffix in _NATIVE_EXTENSIONS or suffix in _IMAGE_EXTENSIONS:
        return path

    content = extract(path)
    if content is None:
        return None
    if isinstance(content, Path):
        return content  # images already handled above, but be safe

    tmp = path.with_name(path.name + ".wiki-tmp.txt")
    tmp.write_text(content, encoding="utf-8")
    return tmp


def extract(path: Path) -> str | Path | None:
    """Extract content from a source file.

    Returns:
        str   — extracted text (for text-based formats)
        Path  — the original path (for images; LLM handles multimodal natively)
        None  — unsupported format (warning logged)
    """
    suffix = path.suffix.lower()

    if suffix == ".md":
        return path.read_text(encoding="utf-8")

    if suffix in _IMAGE_EXTENSIONS:
        return path

    if suffix in _PANDOC_EXTENSIONS:
        return _pandoc(path)

    if suffix == ".pdf":
        return _pdftotext(path)

    if suffix == ".drawio":
        return _drawio_to_yaml(path)

    logger.warning(f"Unsupported file format: {path.suffix} ({path.name})")
    return None


def _pandoc(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["pandoc", "-t", "gfm+tex_math_dollars", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"pandoc failed for {path.name}: {e.stderr.strip()}")
        return None
    except FileNotFoundError:
        logger.error("pandoc not found — install it to process this file type")
        return None


def _pdftotext(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["pdftotext", str(path), "-"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"pdftotext failed for {path.name}: {e.stderr.strip()}")
        return None
    except FileNotFoundError:
        logger.error("pdftotext not found — install poppler-utils to process PDFs")
        return None


def _drawio_to_yaml(path: Path) -> str | None:
    """Convert DrawIO XML to a compact YAML representation of nodes and edges."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()

        nodes: list[dict] = []
        edges: list[dict] = []

        for cell in root.iter("mxCell"):
            cell_id = cell.get("id", "")
            if cell_id in ("0", "1"):
                continue  # skip DrawIO root cells

            label = (cell.get("value") or "").strip()
            style = cell.get("style", "")

            if cell.get("vertex") == "1":
                node: dict = {"id": cell_id}
                if label:
                    node["label"] = label
                if "ellipse" in style:
                    node["shape"] = "ellipse"
                elif "rhombus" in style:
                    node["shape"] = "diamond"
                else:
                    node["shape"] = "rectangle"
                nodes.append(node)

            elif cell.get("edge") == "1":
                edge: dict = {}
                if cell.get("source"):
                    edge["from"] = cell.get("source")
                if cell.get("target"):
                    edge["to"] = cell.get("target")
                if label:
                    edge["label"] = label
                if edge:
                    edges.append(edge)

        data: dict = {}
        if nodes:
            data["nodes"] = nodes
        if edges:
            data["edges"] = edges

        return yaml.dump(data, default_flow_style=False, allow_unicode=True)

    except ET.ParseError as e:
        logger.error(f"Failed to parse DrawIO XML in {path.name}: {e}")
        return None

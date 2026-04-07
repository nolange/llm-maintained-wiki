"""Structural unit tests for the wiki package. No LLM calls."""

import tempfile
import unittest
from pathlib import Path

from wiki import config, manifest, frontmatter, ingest


# ---------------------------------------------------------------------------
# Manifest tests
# ---------------------------------------------------------------------------

class TestManifest(unittest.TestCase):

    def _temp_vault(self) -> Path:
        tmp = Path(tempfile.mkdtemp())
        (tmp / "raw").mkdir()
        (tmp / "raw" / ".manifest").write_text("", encoding="utf-8")
        return tmp

    def test_load_empty(self):
        vault = self._temp_vault()
        self.assertEqual(manifest.load(vault), {})

    def test_round_trip(self):
        vault = self._temp_vault()
        data = {"raw/file.md": "abc123", "raw/other.pdf": "def456"}
        manifest.save(vault, data)
        self.assertEqual(manifest.load(vault), data)

    def test_sha256sum_format(self):
        vault = self._temp_vault()
        manifest.save(vault, {"raw/file.md": "abc123"})
        content = (vault / "raw" / ".manifest").read_text()
        self.assertRegex(content.strip(), r"^[a-f0-9]+  .+$")

    def test_is_new_absent(self):
        vault = self._temp_vault()
        f = vault / "raw" / "test.md"
        f.write_text("hello")
        self.assertTrue(manifest.is_new({}, vault, f))

    def test_is_new_changed(self):
        vault = self._temp_vault()
        f = vault / "raw" / "test.md"
        f.write_text("hello")
        mfst: dict[str, str] = {}
        manifest.mark_done(mfst, vault, f)
        f.write_text("hello world")
        self.assertTrue(manifest.is_new(mfst, vault, f))

    def test_is_new_unchanged(self):
        vault = self._temp_vault()
        f = vault / "raw" / "test.md"
        f.write_text("hello")
        mfst: dict[str, str] = {}
        manifest.mark_done(mfst, vault, f)
        self.assertFalse(manifest.is_new(mfst, vault, f))

    def test_mark_done(self):
        vault = self._temp_vault()
        f = vault / "raw" / "test.md"
        f.write_text("hello")
        mfst: dict[str, str] = {}
        manifest.mark_done(mfst, vault, f)
        self.assertIn("raw/test.md", mfst)
        self.assertEqual(mfst["raw/test.md"], manifest.compute_hash(f))


# ---------------------------------------------------------------------------
# Frontmatter tests
# ---------------------------------------------------------------------------

class TestFrontmatter(unittest.TestCase):

    def _tmp(self, content: str) -> Path:
        p = Path(tempfile.mktemp(suffix=".md"))
        p.write_text(content, encoding="utf-8")
        return p

    def test_read_with_frontmatter(self):
        p = self._tmp("---\ntags: [tsn]\nstatus: draft\n---\n# Title\nBody.")
        meta, body = frontmatter.read(p)
        self.assertEqual(meta["tags"], ["tsn"])
        self.assertEqual(meta["status"], "draft")
        self.assertIn("Body.", body)

    def test_read_without_frontmatter(self):
        p = self._tmp("# Title\nNo frontmatter.")
        meta, body = frontmatter.read(p)
        self.assertEqual(meta, {})
        self.assertIn("No frontmatter.", body)

    def test_write_round_trip(self):
        p = Path(tempfile.mktemp(suffix=".md"))
        frontmatter.write(p, {"tags": ["test"], "status": "draft"}, "# Hello\nWorld.")
        meta, body = frontmatter.read(p)
        self.assertEqual(meta["tags"], ["test"])
        self.assertIn("World.", body)
        # blank line after closing ---
        self.assertIn("---\n\n#", p.read_text())

    def test_normalized_blank_line_after_delimiter(self):
        # body with no leading newline
        result = frontmatter.normalized({"status": "draft"}, "# Body")
        self.assertIn("---\n\n#", result)

    def test_normalized_strips_leading_newlines(self):
        # body with leading newlines gets exactly one blank line
        result = frontmatter.normalized({"status": "draft"}, "\n\n# Body")
        self.assertIn("---\n\n#", result)
        self.assertNotIn("---\n\n\n", result)

    def test_parse_round_trip(self):
        text = "---\nstatus: draft\ntags:\n- foo\n---\n\n# Title\nBody."
        meta, body = frontmatter.parse(text)
        self.assertEqual(meta["status"], "draft")
        self.assertEqual(frontmatter.normalized(meta, body), text)

    def test_read_key(self):
        p = self._tmp("---\nstatus: stable\n---\nBody.")
        self.assertEqual(frontmatter.read_key(p, "status"), "stable")

    def test_read_key_missing(self):
        p = self._tmp("---\ntags: [tsn]\n---\nBody.")
        self.assertIsNone(frontmatter.read_key(p, "nonexistent"))

    def test_malformed_yaml(self):
        p = self._tmp("---\n: bad: yaml: [\n---\nBody.")
        meta, body = frontmatter.read(p)
        self.assertEqual(meta, {})
        self.assertIn("Body.", body)


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

class TestConfig(unittest.TestCase):

    def _cfg(self, content: str) -> Path:
        p = Path(tempfile.mktemp(suffix=".toml"))
        p.write_text(content, encoding="utf-8")
        return p

    def test_load_basic(self):
        p = self._cfg("""
[vault]
path = "/tmp/test-wiki"
[user]
name = "testuser"
[resolver]
mode = "direct"
[llm]
backend = "claude"
[claude]
path = "claude"
args = ["-p"]
""")
        cfg = config.load(p)
        self.assertEqual(cfg.vault_path, Path("/tmp/test-wiki"))
        self.assertEqual(cfg.user_name, "testuser")
        self.assertEqual(cfg.resolver_mode, "direct")

    def test_vault_path_expanded(self):
        p = self._cfg("[vault]\npath = \"~/wiki\"\n[llm]\nbackend = \"claude\"\n[claude]\npath = \"claude\"\nargs = [\"-p\"]\n")
        cfg = config.load(p)
        self.assertFalse(str(cfg.vault_path).startswith("~"))
        self.assertTrue(cfg.vault_path.is_absolute())

    def test_missing_config_raises(self):
        with self.assertRaises(FileNotFoundError):
            config.load(Path("/nonexistent/config.toml"))

    def test_llm_backend_claude(self):
        p = self._cfg("[llm]\nbackend = \"claude\"\n[claude]\npath = \"/usr/bin/claude\"\nargs = [\"-p\"]\n")
        cfg = config.load(p)
        self.assertEqual(cfg.llm_path, "/usr/bin/claude")
        self.assertEqual(cfg.llm_args, ["-p"])

    def test_llm_backend_copilot(self):
        p = self._cfg("[llm]\nbackend = \"copilot\"\n[copilot]\npath = \"copilot\"\nargs = [\"--allow-all-tools\", \"-p\"]\n")
        cfg = config.load(p)
        self.assertEqual(cfg.llm_backend, "copilot")
        self.assertIn("--allow-all-tools", cfg.llm_args)

    def test_compile_max_files_default(self):
        p = self._cfg("[llm]\nbackend = \"claude\"\n[claude]\npath = \"claude\"\nargs = [\"-p\"]\n")
        cfg = config.load(p)
        self.assertEqual(cfg.compile_max_files, 10)

    def test_compile_max_files_custom(self):
        p = self._cfg("[llm]\nbackend = \"claude\"\n[claude]\npath = \"claude\"\nargs = [\"-p\"]\n[compile]\nmax_files = 5\n")
        cfg = config.load(p)
        self.assertEqual(cfg.compile_max_files, 5)


# ---------------------------------------------------------------------------
# Ingest tests
# ---------------------------------------------------------------------------

class TestIngest(unittest.TestCase):

    def test_markdown_passthrough(self):
        p = Path(tempfile.mktemp(suffix=".md"))
        p.write_text("# Hello\nWorld.")
        result = ingest.extract(p)
        self.assertIsInstance(result, str)
        self.assertIn("Hello", result)

    def test_unknown_format(self):
        p = Path(tempfile.mktemp(suffix=".xyz"))
        p.write_text("data")
        self.assertIsNone(ingest.extract(p))

    def test_image_returns_path(self):
        p = Path(tempfile.mktemp(suffix=".png"))
        p.write_bytes(b"\x89PNG\r\n")
        result = ingest.extract(p)
        self.assertIsInstance(result, Path)

    def test_drawio_conversion(self):
        xml = """<?xml version="1.0"?>
<mxGraphModel><root>
<mxCell id="0"/><mxCell id="1" parent="0"/>
<mxCell id="2" value="Node A" vertex="1" parent="1"><mxGeometry/></mxCell>
<mxCell id="3" value="Node B" vertex="1" parent="1"><mxGeometry/></mxCell>
<mxCell id="4" value="connects" edge="1" source="2" target="3" parent="1"><mxGeometry/></mxCell>
</root></mxGraphModel>"""
        p = Path(tempfile.mktemp(suffix=".drawio"))
        p.write_text(xml)
        result = ingest.extract(p)
        self.assertIsInstance(result, str)
        self.assertIn("Node A", result)
        self.assertIn("connects", result)


if __name__ == "__main__":
    unittest.main()

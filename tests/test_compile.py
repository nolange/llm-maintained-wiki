"""Tests for wiki compile. Uses mock LLM — no real API calls."""

import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from wiki import config, manifest
from wiki.compile import (
    _extract_urls,
    _find_new_raw_files,
    _find_session_entries,
    _make_batches,
    _rebuild_all_tag_indexes,
    _update_links_registry,
    compile,
)

MOCK_CLAUDE = Path(__file__).parent / "fixtures" / "mock_claude.py"


def _make_config(vault: Path, compile_max_files: int = 10) -> config.Config:
    return config.Config(
        vault_path=vault,
        user_name="testuser",
        resolver_mode="direct",
        llm_backend="claude",
        llm_path=str(MOCK_CLAUDE),
        llm_args=["-p"],
        compile_max_files=compile_max_files,
    )


def _make_vault(tmp: Path) -> Path:
    vault = tmp / "vault"
    (vault / "raw").mkdir(parents=True)
    (vault / "wiki").mkdir()
    (vault / "assets").mkdir()
    (vault / "queue" / "session-log" / "open").mkdir(parents=True)
    (vault / "queue" / "session-log" / "processed").mkdir()
    (vault / "queue" / "lint" / "open").mkdir(parents=True)
    (vault / "queue" / "lint" / "resolved").mkdir()
    (vault / "outputs").mkdir()
    (vault / "raw" / ".manifest").write_text("")
    (vault / "wiki" / "_index.md").write_text("# Wiki Index\n\n(none yet)\n")
    (vault / "assets" / "links.md").write_text("# Links Registry\n")
    return vault


# ---------------------------------------------------------------------------
# _find_new_raw_files
# ---------------------------------------------------------------------------

class TestFindNewFiles(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault = _make_vault(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_finds_new_file(self):
        (self.vault / "raw" / "new.md").write_text("# New\ncontent")
        mfst = manifest.load(self.vault)
        found = _find_new_raw_files(self.vault, mfst)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].name, "new.md")

    def test_skips_processed_file(self):
        f = self.vault / "raw" / "existing.md"
        f.write_text("content")
        mfst: dict[str, str] = {}
        manifest.mark_done(mfst, self.vault, f)
        self.assertEqual(_find_new_raw_files(self.vault, mfst), [])

    def test_detects_changed_file(self):
        f = self.vault / "raw" / "changed.md"
        f.write_text("original")
        mfst: dict[str, str] = {}
        manifest.mark_done(mfst, self.vault, f)
        f.write_text("modified")
        self.assertEqual(len(_find_new_raw_files(self.vault, mfst)), 1)


# ---------------------------------------------------------------------------
# _find_session_entries
# ---------------------------------------------------------------------------

class TestSessionEntries(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault = _make_vault(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_finds_session_entries(self):
        entry = self.vault / "queue" / "session-log" / "open" / "2026-04-04-test.md"
        entry.write_text("---\ntags: [test]\n---\n## Findings\n- something\n")
        found = _find_session_entries(self.vault)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].name, entry.name)

    def test_empty_when_no_entries(self):
        self.assertEqual(_find_session_entries(self.vault), [])


# ---------------------------------------------------------------------------
# _make_batches
# ---------------------------------------------------------------------------

class TestBatching(unittest.TestCase):

    def _raw(self, n: int) -> list[tuple[Path, Path]]:
        return [(Path(f"raw/f{i}.md"), Path(f"raw/f{i}.md")) for i in range(n)]

    def test_single_batch_within_limit(self):
        batches = _make_batches(self._raw(3), [], [], max_files=10)
        self.assertEqual(len(batches), 1)
        self.assertEqual(len(batches[0][0]), 3)

    def test_splits_into_multiple_batches(self):
        batches = _make_batches(self._raw(5), [], [], max_files=2)
        self.assertEqual(len(batches), 3)
        self.assertEqual(len(batches[0][0]), 2)
        self.assertEqual(len(batches[1][0]), 2)
        self.assertEqual(len(batches[2][0]), 1)

    def test_sessions_only_in_first_batch(self):
        sessions = [Path("queue/session-log/open/s.md")]
        batches = _make_batches(self._raw(4), sessions, [], max_files=2)
        self.assertEqual(len(batches), 2)
        self.assertEqual(batches[0][1], sessions)
        self.assertEqual(batches[1][1], [])

    def test_session_only_no_raw_files(self):
        sessions = [Path("queue/session-log/open/s.md")]
        batches = _make_batches([], sessions, [], max_files=10)
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0][1], sessions)

    def test_empty_input_returns_empty(self):
        self.assertEqual(_make_batches([], [], [], max_files=10), [])

    def test_assets_only_in_first_batch(self):
        assets = [Path("assets/diagram.drawio")]
        batches = _make_batches(self._raw(4), [], assets, max_files=2)
        self.assertEqual(batches[0][2], assets)
        self.assertEqual(batches[1][2], [])


# ---------------------------------------------------------------------------
# _rebuild_all_tag_indexes
# ---------------------------------------------------------------------------

class TestTagIndexes(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault = _make_vault(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_rebuilds_indexes_for_all_tags(self):
        (self.vault / "wiki" / "tsn-overview.md").write_text(
            "---\ntags: [tsn, networking]\nstatus: draft\n---\n\n# TSN Overview\n\nContent.\n"
        )
        _rebuild_all_tag_indexes(self.vault)
        self.assertTrue((self.vault / "wiki" / "_index_tsn.md").exists())
        self.assertTrue((self.vault / "wiki" / "_index_networking.md").exists())
        content = (self.vault / "wiki" / "_index_tsn.md").read_text()
        self.assertIn("TSN Overview", content)
        self.assertIn("tsn-overview.md", content)

    def test_no_index_when_wiki_empty(self):
        _rebuild_all_tag_indexes(self.vault)
        self.assertEqual(list((self.vault / "wiki").glob("_index_*.md")), [])

    def test_two_articles_same_tag(self):
        (self.vault / "wiki" / "article-a.md").write_text(
            "---\ntags: [tsn]\nstatus: draft\n---\n# Article A\n"
        )
        (self.vault / "wiki" / "article-b.md").write_text(
            "---\ntags: [tsn]\nstatus: draft\n---\n# Article B\n"
        )
        _rebuild_all_tag_indexes(self.vault)
        content = (self.vault / "wiki" / "_index_tsn.md").read_text()
        self.assertIn("Article A", content)
        self.assertIn("Article B", content)


# ---------------------------------------------------------------------------
# URL registry
# ---------------------------------------------------------------------------

class TestLinksRegistry(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault = _make_vault(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_extracts_urls_from_file(self):
        p = Path(tempfile.mktemp(suffix=".md"))
        p.write_text("See https://example.com/spec and https://other.org/doc for details.")
        urls = _extract_urls([p])
        self.assertIn("https://example.com/spec", urls)
        self.assertIn("https://other.org/doc", urls)
        p.unlink()

    def test_registers_new_url(self):
        _update_links_registry(self.vault, {"https://example.com/spec"})
        content = (self.vault / "assets" / "links.md").read_text()
        self.assertIn("https://example.com/spec", content)
        self.assertIn("### Why", content)
        self.assertIn("<!-- TODO -->", content)

    def test_skips_existing_url(self):
        links_path = self.vault / "assets" / "links.md"
        links_path.write_text("# Links\n\n## https://example.com/spec\n")
        _update_links_registry(self.vault, {"https://example.com/spec"})
        self.assertEqual(links_path.read_text().count("https://example.com/spec"), 1)

    def test_tags_left_empty(self):
        _update_links_registry(self.vault, {"https://example.com/spec"})
        content = (self.vault / "assets" / "links.md").read_text()
        self.assertIn("- **tags:** []", content)


# ---------------------------------------------------------------------------
# Integration: full compile with mock LLM
# ---------------------------------------------------------------------------

class TestCompileIntegration(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault = _make_vault(self.tmp)
        self.cfg = _make_config(self.vault)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_compile_creates_article(self):
        (self.vault / "raw" / "source.md").write_text("# Source\ncontent")
        compile(self.cfg)
        articles = [p for p in (self.vault / "wiki").glob("*.md") if not p.name.startswith("_")]
        self.assertGreater(len(articles), 0)

    def test_compile_updates_index(self):
        (self.vault / "raw" / "source.md").write_text("# Source\ncontent")
        compile(self.cfg)
        index = (self.vault / "wiki" / "_index.md").read_text()
        self.assertIn("test-article.md", index)

    def test_compile_updates_manifest(self):
        (self.vault / "raw" / "source.md").write_text("content")
        compile(self.cfg)
        mfst = manifest.load(self.vault)
        self.assertTrue(any("source.md" in k for k in mfst))

    def test_compile_moves_session_log(self):
        entry = self.vault / "queue" / "session-log" / "open" / "2026-04-04-test.md"
        entry.write_text("---\ntags: [test]\n---\n## Findings\n- something\n")
        compile(self.cfg)
        self.assertFalse(entry.exists())
        self.assertTrue(
            (self.vault / "queue" / "session-log" / "processed" / "2026-04-04-test.md").exists()
        )

    def test_compile_nothing_new(self):
        captured = io.StringIO()
        sys.stdout = captured
        try:
            compile(self.cfg)
        finally:
            sys.stdout = sys.__stdout__
        self.assertIn("Nothing new", captured.getvalue())

    def test_compile_batches_large_input(self):
        """5 files with max_files=2 → 3 batches; all files end up in manifest."""
        cfg = _make_config(self.vault, compile_max_files=2)
        for i in range(5):
            (self.vault / "raw" / f"source{i}.md").write_text(f"# Source {i}\ncontent")
        compile(cfg)
        mfst = manifest.load(self.vault)
        self.assertEqual(len([k for k in mfst if k.endswith(".md")]), 5)

    def test_compile_idempotent(self):
        """Running compile twice on the same input does not reprocess files."""
        (self.vault / "raw" / "source.md").write_text("content")
        compile(self.cfg)
        mfst_after_first = manifest.load(self.vault)
        compile(self.cfg)
        mfst_after_second = manifest.load(self.vault)
        self.assertEqual(mfst_after_first, mfst_after_second)


if __name__ == "__main__":
    unittest.main()

"""Tests for wiki lint, enhance, and ask. Uses mock LLM — no real API calls."""

import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from wiki import config, frontmatter
from wiki.ask import _select_articles, _tokenize, ask
from wiki.enhance import _collect_frontmatter_summary, enhance
from wiki.lint import _all_stable, _cluster_by_tag, _open_case_clusters, _read_articles, lint

MOCK_CLAUDE = Path(__file__).parent / "fixtures" / "mock_claude.py"
TODAY = date.today().isoformat()


def _make_config(vault: Path) -> config.Config:
    return config.Config(
        vault_path=vault,
        user_name="testuser",
        resolver_mode="direct",
        llm_backend="claude",
        llm_path=str(MOCK_CLAUDE),
        llm_args=["-p"],
        compile_max_files=10,
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


def _write_article(wiki_dir: Path, name: str, tags: list[str], status: str = "draft") -> Path:
    p = wiki_dir / name
    p.write_text(
        f"---\ntags: {tags}\nstatus: {status}\n---\n\n# {name.replace('.md','').title()}\n\nContent.\n",
        encoding="utf-8",
    )
    return p


# ===========================================================================
# lint unit tests
# ===========================================================================

class TestReadArticles(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault = _make_vault(self.tmp)
        self.wiki = self.vault / "wiki"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_reads_articles_skips_index(self):
        _write_article(self.wiki, "article-a.md", ["tsn"])
        articles = _read_articles(self.wiki)
        names = [p.name for p, _, _ in articles]
        self.assertIn("article-a.md", names)
        self.assertNotIn("_index.md", names)

    def test_returns_empty_when_no_articles(self):
        self.assertEqual(_read_articles(self.wiki), [])


class TestClusterByTag(unittest.TestCase):
    def _make_entry(self, name: str, tags: list[str]) -> tuple:
        return (Path(name), {"tags": tags, "status": "draft"}, "body")

    def test_groups_by_tag(self):
        entries = [
            self._make_entry("a.md", ["tsn", "networking"]),
            self._make_entry("b.md", ["tsn"]),
            self._make_entry("c.md", ["networking"]),
        ]
        clusters = _cluster_by_tag(entries)
        self.assertIn("tsn", clusters)
        self.assertEqual(len(clusters["tsn"]), 2)
        self.assertIn("networking", clusters)
        self.assertEqual(len(clusters["networking"]), 2)

    def test_excludes_single_article_clusters(self):
        entries = [self._make_entry("a.md", ["solo"])]
        clusters = _cluster_by_tag(entries)
        self.assertNotIn("solo", clusters)


class TestOpenCaseClusters(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault = _make_vault(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_detects_open_cluster_by_cluster_key(self):
        case = self.vault / "queue" / "lint" / "open" / "lint-tsn-2026-01-01.md"
        case.write_text("---\ncluster: tsn\nstatus: open\n---\n\n## Findings\n- conflict\n")
        result = _open_case_clusters(self.vault)
        self.assertIn("tsn", result)

    def test_detects_open_cluster_by_tags(self):
        case = self.vault / "queue" / "lint" / "open" / "lint-net-2026-01-01.md"
        case.write_text("---\ntags: [networking, tsn]\nstatus: open\n---\n\n## Findings\n")
        result = _open_case_clusters(self.vault)
        self.assertIn("networking", result)
        self.assertIn("tsn", result)

    def test_empty_when_no_open_cases(self):
        self.assertEqual(_open_case_clusters(self.vault), set())


class TestAllStable(unittest.TestCase):
    def _entry(self, status: str) -> tuple:
        return (Path("x.md"), {"status": status}, "")

    def test_all_stable_true(self):
        self.assertTrue(_all_stable([self._entry("stable"), self._entry("stable")]))

    def test_not_all_stable(self):
        self.assertFalse(_all_stable([self._entry("stable"), self._entry("draft")]))

    def test_empty_is_stable(self):
        self.assertTrue(_all_stable([]))


class TestLintIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault = _make_vault(self.tmp)
        self.wiki = self.vault / "wiki"
        self.cfg = _make_config(self.vault)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_lint_produces_case_file(self):
        _write_article(self.wiki, "article-a.md", ["tsn"])
        _write_article(self.wiki, "article-b.md", ["tsn"])
        lint(self.cfg)
        cases = list((self.vault / "queue" / "lint" / "open").glob("*.md"))
        self.assertGreater(len(cases), 0)

    def test_lint_case_has_required_fields(self):
        _write_article(self.wiki, "article-a.md", ["tsn"])
        _write_article(self.wiki, "article-b.md", ["tsn"])
        lint(self.cfg)
        cases = list((self.vault / "queue" / "lint" / "open").glob("*.md"))
        self.assertGreater(len(cases), 0)
        meta, body = frontmatter.read(cases[0])
        self.assertIn("cluster", meta)
        self.assertIn("status", meta)
        self.assertEqual(meta["status"], "open")

    def test_lint_skips_stable_clusters(self):
        _write_article(self.wiki, "article-a.md", ["tsn"], status="stable")
        _write_article(self.wiki, "article-b.md", ["tsn"], status="stable")
        lint(self.cfg)
        cases = list((self.vault / "queue" / "lint" / "open").glob("*.md"))
        self.assertEqual(len(cases), 0)

    def test_lint_no_articles(self):
        # Should not raise, just print a message
        lint(self.cfg)

    def test_lint_no_multi_article_cluster(self):
        _write_article(self.wiki, "solo.md", ["unique"])
        lint(self.cfg)
        cases = list((self.vault / "queue" / "lint" / "open").glob("*.md"))
        self.assertEqual(len(cases), 0)

    def test_lint_skips_cluster_with_open_report(self):
        _write_article(self.wiki, "article-a.md", ["tsn"])
        _write_article(self.wiki, "article-b.md", ["tsn"])
        # Pre-seed an open case for the same cluster
        case = self.vault / "queue" / "lint" / "open" / "lint-tsn-2026-01-01.md"
        case.write_text("---\ncluster: tsn\nstatus: open\n---\n\n## Findings\n- existing issue\n")
        lint(self.cfg)
        # Should not have created a second case
        cases = list((self.vault / "queue" / "lint" / "open").glob("*.md"))
        self.assertEqual(len(cases), 1)

    def test_lint_max_calls_limits_invocations(self):
        # Create 6 clusters (one tag each, 2 articles each)
        for i in range(6):
            _write_article(self.wiki, f"a{i}.md", [f"tag{i}"])
            _write_article(self.wiki, f"b{i}.md", [f"tag{i}"])
        lint(self.cfg, max_calls=2)
        # At most 2 case files should be created
        cases = list((self.vault / "queue" / "lint" / "open").glob("*.md"))
        self.assertLessEqual(len(cases), 2)


# ===========================================================================
# enhance unit tests
# ===========================================================================

class TestCollectFrontmatterSummary(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault = _make_vault(self.tmp)
        self.wiki = self.vault / "wiki"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_includes_article_info(self):
        _write_article(self.wiki, "tsn-overview.md", ["tsn", "networking"])
        summary = _collect_frontmatter_summary(self.wiki)
        self.assertIn("tsn-overview.md", summary)
        self.assertIn("tsn", summary)
        self.assertIn("draft", summary)

    def test_empty_wiki_returns_placeholder(self):
        summary = _collect_frontmatter_summary(self.wiki)
        self.assertIn("no articles", summary)

    def test_sampling_limits_articles(self):
        for i in range(10):
            _write_article(self.wiki, f"article-{i}.md", ["tag"])
        summary = _collect_frontmatter_summary(self.wiki, max_articles=3)
        count = summary.count("article-")
        self.assertEqual(count, 3)
        self.assertIn("sampled randomly", summary)

    def test_no_sampling_when_under_limit(self):
        for i in range(5):
            _write_article(self.wiki, f"article-{i}.md", ["tag"])
        summary = _collect_frontmatter_summary(self.wiki, max_articles=10)
        self.assertNotIn("sampled randomly", summary)


class TestEnhanceIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault = _make_vault(self.tmp)
        self.wiki = self.vault / "wiki"
        self.cfg = _make_config(self.vault)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_enhance_writes_report(self):
        _write_article(self.wiki, "article-a.md", ["tsn"])
        enhance(self.cfg)
        report = self.vault / "outputs" / f"enhance-{TODAY}.md"
        self.assertTrue(report.exists())

    def test_enhance_report_has_sections(self):
        _write_article(self.wiki, "article-a.md", ["tsn"])
        enhance(self.cfg)
        report = self.vault / "outputs" / f"enhance-{TODAY}.md"
        content = report.read_text()
        self.assertIn("## Missing Cross-Links", content)
        self.assertIn("## Topic Gaps", content)
        self.assertIn("## Article Candidates", content)
        self.assertIn("## Thin Articles", content)

    def test_enhance_no_wiki_dir(self):
        import shutil as _shutil
        _shutil.rmtree(self.vault / "wiki")
        # Should not raise
        enhance(self.cfg)


# ===========================================================================
# ask unit tests
# ===========================================================================

class TestTokenize(unittest.TestCase):
    def test_lowercases_and_splits(self):
        tokens = _tokenize("TSN Scheduling")
        self.assertIn("tsn", tokens)
        self.assertIn("scheduling", tokens)


class TestSelectArticles(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault = _make_vault(self.tmp)
        self.wiki = self.vault / "wiki"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_returns_relevant_articles(self):
        _write_article(self.wiki, "tsn-scheduling.md", ["tsn", "scheduling"])
        _write_article(self.wiki, "unrelated.md", ["finance"])
        selected = _select_articles(self.wiki, "How does TSN scheduling work?")
        names = [p.name for p in selected]
        self.assertIn("tsn-scheduling.md", names)

    def test_empty_wiki_returns_empty(self):
        selected = _select_articles(self.wiki, "any question")
        self.assertEqual(selected, [])

    def test_max_articles_limit(self):
        for i in range(10):
            _write_article(self.wiki, f"article-{i}.md", ["tsn"])
        selected = _select_articles(self.wiki, "tsn question")
        self.assertLessEqual(len(selected), 5)


class TestAskIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault = _make_vault(self.tmp)
        self.wiki = self.vault / "wiki"
        self.cfg = _make_config(self.vault)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_ask_writes_answer_file(self):
        _write_article(self.wiki, "tsn-overview.md", ["tsn"])
        ask(self.cfg, "What is TSN?")
        outputs = list((self.vault / "outputs").glob("*.md"))
        # Filter out enhance reports
        answers = [p for p in outputs if not p.name.startswith("enhance")]
        self.assertGreater(len(answers), 0)

    def test_ask_no_wiki(self):
        import shutil as _shutil
        _shutil.rmtree(self.vault / "wiki")
        # Should not raise
        ask(self.cfg, "What is TSN?")


if __name__ == "__main__":
    unittest.main()

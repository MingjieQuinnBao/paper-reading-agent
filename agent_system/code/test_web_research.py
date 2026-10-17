"""Behavior checks for the two web search modes without paid API calls."""

from __future__ import annotations

import unittest
import urllib.error
from unittest.mock import patch

from web_research.service import research
from web_research.service import _deep_sources, _source_list
from web_research.normalize import deduplicate
from web_research.retrieval import public_output, search_sources
from web_research.tool import search as search_tool


class WebResearchTests(unittest.TestCase):
    def test_deep_shortlist_keeps_relevant_academic_record(self) -> None:
        web = [{"title": f"Audio CAPTCHA guide {index}", "source_type": "web"}
               for index in range(6)]
        paper = {"title": "Audio CAPTCHA study", "source_type": "academic"}
        selected = _deep_sources("audio CAPTCHA", web + [paper])
        self.assertEqual(6, len(selected))
        self.assertIs(paper, selected[-1])
        unrelated = {"title": "A different field", "source_type": "academic"}
        self.assertEqual(web, _deep_sources("audio CAPTCHA", web + [unrelated]))

    def test_bibliography_renders_as_separate_numbered_entries(self) -> None:
        from chat_ui import render_markdown
        sources = [
            {"title": "First source", "url": "https://example.org/one", "providers": ["Tavily"]},
            {"title": "Second source", "url": "https://example.org/two", "providers": ["Crossref"]},
        ]
        rendered = render_markdown("### 來源\n\n" + _source_list(sources))
        self.assertIn("<ol>", rendered)
        self.assertEqual(2, rendered.count("<li>"))
        old = "### 來源\n\n[1] [First](https://example.org/one) — Tavily\n[2] [Second](https://example.org/two) — Tavily"
        self.assertEqual(2, render_markdown(old).count("<li>"))

    def test_retrieval_tool_selects_sources_without_chat_or_model(self) -> None:
        paper = {"provider": "Crossref", "title": "Reusable tool", "url": "https://doi.org/10.1000/test"}
        with patch("web_research.retrieval.academic.search_crossref", return_value=[paper]) as crossref, \
             patch("web_research.retrieval.academic.search_arxiv") as arxiv, \
             patch("web_research.retrieval.tavily.search") as tavily:
            result = search_tool("reusable tool", providers="crossref", keys={})
        crossref.assert_called_once()
        arxiv.assert_not_called()
        tavily.assert_not_called()
        self.assertEqual(["Crossref"], result["providers"])
        self.assertEqual(["Crossref"], list(result["source_status"]))
        self.assertEqual("academic", result["results"][0]["source_type"])
        with self.assertRaises(ValueError):
            search_tool("query", providers="unknown", keys={})

    def test_quick_search_returns_provider_results_without_model(self) -> None:
        item = {"title": "Relevant paper", "url": "https://example.org/paper",
                "snippet": "A useful research result.", "raw_content": "", "provider": "Tavily"}
        streamed: list[str] = []
        with patch("web_research.retrieval.tavily.search", return_value=[item]) as search, \
             patch("web_research.retrieval.academic.search_crossref", return_value=[]), \
             patch("web_research.retrieval.academic.search_arxiv", return_value=[]):
            result = research("research result", "quick", {"TAVILY_API_KEY": "test"}, on_delta=streamed.append)
        search.assert_called_once_with("research result", "test", False)
        self.assertIn("https://example.org/paper", result["answer"])
        self.assertEqual("search", result["model"])
        self.assertEqual(result["answer"], "".join(streamed))

    def test_deep_research_filters_reranks_extracts_and_streams(self) -> None:
        first = {"title": "First study", "url": "https://example.org/first",
                 "snippet": "baseline result", "raw_content": "Important evidence about the research question and its method. " * 4,
                 "provider": "Tavily"}
        duplicate = {**first, "raw_content": "short"}
        second = {"title": "Second study", "url": "https://example.org/second",
                  "snippet": "method research", "raw_content": "Independent method evidence for this research question. " * 4,
                  "provider": "Bocha"}
        invalid = {**second, "url": "javascript:alert(1)"}
        streamed: list[str] = []
        steps: list[dict[str, str]] = []

        def synthesize(prompt: str, delta) -> str:
            self.assertIn("Independent method evidence", prompt)
            delta("Supported finding [1].")
            return "Supported finding [1]."

        with patch("web_research.retrieval.tavily.search", return_value=[first, duplicate, invalid]), \
             patch("web_research.retrieval.bocha.search", return_value=[second]), \
             patch("web_research.retrieval.academic.search_crossref", return_value=[]), \
             patch("web_research.retrieval.academic.search_arxiv", return_value=[]):
            result = research("baseline result", "deep",
                              {"TAVILY_API_KEY": "test", "BOCHA_API_KEY": "test"},
                              on_delta=streamed.append, on_process=steps.append,
                              rerank=lambda _: '{"order":[2,1]}', synthesize=synthesize)
        self.assertEqual(2, len(result["sources"]))
        self.assertEqual("Second study", result["sources"][0]["title"])
        self.assertIn("### 來源", result["answer"])
        self.assertEqual(result["answer"], "".join(streamed))
        self.assertEqual(["processSearch", "processFilter", "processRerank", "processExtract", "processResearchDraft"],
                         [step["key"] for step in steps])

    def test_deep_research_continues_if_one_provider_has_no_quota(self) -> None:
        item = {"title": "Available source", "url": "https://example.org/source",
                "snippet": "Relevant findings from the available source.", "raw_content": "", "provider": "Tavily"}
        no_quota = urllib.error.HTTPError("https://api.bochaai.com/v1/web-search", 403, "Forbidden", {}, None)
        with patch("web_research.retrieval.tavily.search", return_value=[item]), \
             patch("web_research.retrieval.bocha.search", side_effect=no_quota), \
             patch("web_research.retrieval.academic.search_crossref", return_value=[]), \
             patch("web_research.retrieval.academic.search_arxiv", return_value=[]):
            result = research("available source", "deep",
                              {"TAVILY_API_KEY": "test", "BOCHA_API_KEY": "test"})
        self.assertEqual(1, len(result["sources"]))
        self.assertIn("Bocha HTTP 403", result["answer"])
        no_quota.close()

    def test_crossref_and_arxiv_merge_by_doi_and_keep_metadata(self) -> None:
        merged = deduplicate([
            {"provider": "Crossref", "title": "A Shared Academic Paper", "url": "https://doi.org/10.1234/Example",
             "snippet": "Abstract from Crossref", "doi": "10.1234/Example", "authors": ["Ada Lovelace"], "year": 2024},
            {"provider": "arXiv", "title": "A Shared Academic Paper", "url": "http://arxiv.org/abs/2401.12345v2",
             "snippet": "Longer abstract from arXiv about the shared academic paper", "doi": "10.1234/example",
             "arxiv_id": "2401.12345", "year": 2024},
        ])
        self.assertEqual(1, len(merged))
        self.assertEqual(["Crossref", "arXiv"], merged[0]["providers"])
        self.assertEqual("10.1234/example", merged[0]["doi"])
        self.assertEqual("2401.12345", merged[0]["arxiv_id"])
        self.assertEqual(2024, merged[0]["year"])
        self.assertEqual(1, len(merged[0]["alternate_urls"]))

    def test_four_provider_fanout_returns_structured_summary(self) -> None:
        web = {"provider": "Tavily", "title": "A Shared Academic Paper", "url": "https://example.org/paper?utm_source=search",
               "snippet": "Web abstract", "raw_content": "Web full text"}
        same_web = {**web, "provider": "Bocha", "url": "http://www.example.org/paper"}
        crossref = {"provider": "Crossref", "title": "A Shared Academic Paper", "url": "https://doi.org/10.1234/example",
                    "snippet": "Metadata abstract", "doi": "10.1234/example", "year": 2024}
        arxiv = {"provider": "arXiv", "title": "A Shared Academic Paper", "url": "https://arxiv.org/abs/2401.12345",
                 "snippet": "Preprint abstract", "doi": "10.1234/example", "arxiv_id": "2401.12345", "year": 2024}
        with patch("web_research.retrieval.tavily.search", return_value=[web]) as tavily, \
             patch("web_research.retrieval.bocha.search", return_value=[same_web]) as bocha, \
             patch("web_research.retrieval.academic.search_crossref", return_value=[crossref]) as crossref_search, \
             patch("web_research.retrieval.academic.search_arxiv", return_value=[arxiv]) as arxiv_search:
            result = search_sources("shared academic paper", "deep",
                                    {"TAVILY_API_KEY": "t", "BOCHA_API_KEY": "b"})
        self.assertEqual(1, tavily.call_count)
        self.assertEqual(1, bocha.call_count)
        self.assertEqual(1, crossref_search.call_count)
        self.assertEqual(1, arxiv_search.call_count)
        self.assertEqual(4, result["summary"]["raw_count"])
        self.assertEqual(2, result["summary"]["unique_count"])
        self.assertEqual(2, result["summary"]["duplicates_removed"])
        self.assertEqual({"Tavily", "Bocha", "Crossref", "arXiv"}, set(result["source_status"]))
        self.assertNotIn("raw_content", public_output(result)["results"][0])


if __name__ == "__main__":
    unittest.main()

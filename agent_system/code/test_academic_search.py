from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

import agent_core
from academic_metadata import arxiv, crossref, openalex_arxiv, paper_info, service


class AcademicSearchTests(unittest.TestCase):
    def test_paper_info_collects_deposited_references_and_scoped_coverage(self) -> None:
        record = {
            "DOI": "10.1234/example", "title": ["Example study"],
            "author": [{"given": "Ada", "family": "Lovelace"}],
            "published": {"date-parts": [[2024, 5, 1]]},
            "reference-count": 2,
            "reference": [
                {"DOI": "10.2222/first", "article-title": "First work", "year": "2020"},
                {"unstructured": "Second work, 2021"},
            ],
        }
        with patch.object(crossref, "work", return_value=record) as work, \
             patch.object(arxiv, "search") as arxiv_search:
            result = paper_info.collect("10.1234/example")
        work.assert_called_once_with("10.1234/example")
        arxiv_search.assert_not_called()
        self.assertEqual("verified", result["match_status"])
        self.assertEqual("Ada Lovelace", result["paper"]["authors"][0])
        self.assertEqual("registered", result["coverage"]["crossref"])
        self.assertEqual("not_checked", result["coverage"]["other_indexes"])
        self.assertEqual("deposited", result["references_status"])
        self.assertEqual(2, len(result["references"]))
        self.assertEqual("https://doi.org/10.2222/first", result["references"][0]["url"])

    def test_paper_info_does_not_assign_unrelated_title_match(self) -> None:
        record = {"DOI": "10.1234/wrong", "title": ["Unrelated study"]}
        with patch.object(crossref, "search_works", return_value=[record]), \
             patch.object(crossref, "work") as work, \
             patch.object(arxiv, "search", return_value=[]):
            result = paper_info.collect("Example study")
        work.assert_not_called()
        self.assertEqual("not_verified", result["match_status"])
        self.assertIsNone(result["paper"])
        self.assertEqual([], result["references"])
        self.assertEqual(1, len(result["candidates"]))

    def test_crossref_doi_uses_single_work_endpoint(self) -> None:
        payload = {"message": {"DOI": "10.1234/example", "title": ["Example study"],
                               "author": [{"given": "Ada", "family": "Lovelace"}],
                               "published": {"date-parts": [[2024, 5, 1]]}}}
        with patch.object(crossref, "get", return_value=json.dumps(payload).encode()) as get:
            result = crossref.search("https://doi.org/10.1234/example", 5)
        self.assertIn("/works/10.1234%2Fexample", get.call_args.args[0])
        self.assertEqual(result[0]["authors"], ["Ada Lovelace"])
        self.assertEqual(result[0]["year"], 2024)

    def test_arxiv_atom_metadata_and_id_lookup(self) -> None:
        feed = b'''<feed xmlns="http://www.w3.org/2005/Atom"
            xmlns:arxiv="http://arxiv.org/schemas/atom"><entry>
            <id>http://arxiv.org/abs/2301.08243v2</id><title>Example Paper</title>
            <published>2023-01-20T00:00:00Z</published><summary>Abstract text</summary>
            <author><name>First Author</name></author><arxiv:doi>10.1234/example</arxiv:doi>
            </entry></feed>'''
        with patch.object(arxiv, "get", return_value=feed) as get:
            result = arxiv.search("2301.08243", 5)
        self.assertIn("id_list=2301.08243", get.call_args.args[0])
        self.assertEqual(result[0]["arxiv_id"], "2301.08243")
        self.assertEqual(result[0]["doi"], "10.1234/example")

    def test_arxiv_reuses_cached_feed_and_spaces_distinct_requests(self) -> None:
        feed = b'<feed xmlns="http://www.w3.org/2005/Atom" />'
        with patch.object(arxiv, "get", return_value=feed) as get, \
             patch.object(arxiv.time, "sleep") as sleep, \
             patch.object(arxiv, "_NEXT_REQUEST_AT", 0), \
             patch.object(arxiv, "_CACHE", {}):
            first = arxiv.search("2401.00001", 1)
            again = arxiv.search("2401.00001", 1)
            second = arxiv.search("2401.00002", 1)
        self.assertEqual(first, again)
        self.assertEqual([], second)
        self.assertEqual(2, get.call_count)
        sleep.assert_called_once()

    def test_arxiv_429_uses_labelled_openalex_fallback_and_cooldown(self) -> None:
        error = urllib.error.HTTPError("https://export.arxiv.org/api/query", 429, "Rate exceeded", {}, None)
        fallback = [{"source": "arxiv", "metadata_source": "OpenAlex", "title": "Example",
                     "url": "https://arxiv.org/abs/2301.08243", "arxiv_id": "2301.08243"}]
        with patch.object(arxiv, "get", side_effect=error) as get, \
             patch.object(openalex_arxiv, "search", return_value=fallback) as search, \
             patch.object(arxiv, "_NEXT_REQUEST_AT", 0), \
             patch.object(arxiv, "_UNAVAILABLE_UNTIL", 0), \
             patch.object(arxiv, "_LAST_FAILURE", ""), \
             patch.object(arxiv, "_CACHE", {}):
            first = arxiv.search("2301.08243", 1)
            second = arxiv.search("2301.08243", 1)
        self.assertEqual(1, get.call_count)
        self.assertEqual(2, search.call_count)
        self.assertEqual("OpenAlex", first.retrieved_via)
        self.assertEqual("HTTP 429", first.upstream_error)
        self.assertEqual("2301.08243", second[0]["arxiv_id"])
        error.close()

    def test_openalex_fallback_requires_actual_arxiv_location(self) -> None:
        item = {"display_name": "Example", "publication_year": 2023,
                "locations": [{"landing_page_url": "http://arxiv.org/abs/2301.08243",
                               "source": {"id": openalex_arxiv.ARXIV_SOURCE}}],
                "authorships": [{"author": {"display_name": "Ada Lovelace"}}],
                "abstract_inverted_index": {"A": [0], "result": [1]}}
        with patch.object(openalex_arxiv, "get", return_value=json.dumps({"results": [item]}).encode()):
            found = openalex_arxiv.search("2301.08243", 1)
        self.assertEqual("A result", found[0]["abstract"])
        self.assertEqual("OpenAlex", found[0]["metadata_source"])
        with patch.object(openalex_arxiv, "get", return_value=json.dumps({"results": [item]}).encode()):
            self.assertEqual([], openalex_arxiv.search("2301.08244", 1))

    def test_one_service_failure_preserves_other_results(self) -> None:
        paper = {"source": "arxiv", "title": "Available paper"}
        with patch.object(crossref, "search", side_effect=TimeoutError("timeout")), \
             patch.object(arxiv, "search", return_value=[paper]):
            result = service.search_academic("available paper")
        self.assertEqual(result["source_status"]["crossref"]["status"], "error")
        self.assertEqual(result["source_status"]["arxiv"]["status"], "ok")
        self.assertEqual(result["results"], [paper])

    def test_http_route_returns_json_and_rejects_invalid_limit(self) -> None:
        server = agent_core.ThreadingHTTPServer(("127.0.0.1", 0), agent_core.AgentHandler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}/api/academic-search"
            expected = {"query": "test", "source_status": {}, "results": []}
            with patch.object(agent_core.academic_search, "search_academic", return_value=expected):
                with urllib.request.urlopen(base + "?query=test") as response:
                    self.assertEqual(response.headers.get_content_type(), "application/json")
                    self.assertEqual(json.load(response), expected)
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(base + "?query=test&limit=oops")
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_paper_info_route_accepts_query_and_imported_source(self) -> None:
        server = agent_core.ThreadingHTTPServer(("127.0.0.1", 0), agent_core.AgentHandler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}/api/paper-info"
            expected = {"match_status": "verified", "paper": {"title": "Example study"}}
            with patch.object(agent_core.academic_search, "collect_paper_info", return_value=expected) as collect:
                with urllib.request.urlopen(base + "?query=10.1234%2Fexample") as response:
                    self.assertEqual(json.load(response), expected)
                collect.assert_called_once_with("10.1234/example")
            with patch.object(agent_core, "paper_info_for_source", return_value=expected) as collect_source:
                with urllib.request.urlopen(base + "?source=paper_123") as response:
                    self.assertEqual(json.load(response), expected)
                collect_source.assert_called_once_with("paper_123")
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_multi_source_route_returns_unified_json(self) -> None:
        server = agent_core.ThreadingHTTPServer(("127.0.0.1", 0), agent_core.AgentHandler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}/api/multi-source-search"
            expected = {"query": "test", "mode": "deep", "summary": {"unique_count": 1},
                        "source_status": {"Crossref": {"status": "ok", "count": 1}},
                        "results": [{"title": "Paper", "provider": "Crossref"}]}
            with patch.object(agent_core, "multi_source_search", return_value=expected) as search:
                with urllib.request.urlopen(base + "?query=test&mode=deep&limit=5") as response:
                    self.assertEqual(response.headers.get_content_type(), "application/json")
                    self.assertEqual(json.load(response), expected)
                search.assert_called_once_with("test", "deep", 5)
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(base + "?query=test&limit=oops")
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)


if __name__ == "__main__":
    unittest.main()

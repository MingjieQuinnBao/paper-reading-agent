# Paper Reading Agent

A local web app for importing a research paper, asking questions, and keeping conversation history. The interface supports Simplified Chinese, Traditional Chinese, and English. It accepts PDF, Markdown, and plain text; pasted text also works.

## Run locally

From the repository root in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r agent_system\requirements.txt
.\.venv\Scripts\python.exe agent_system\code\agent_core.py server --port 8787
```

Open <http://127.0.0.1:8787>, then import a paper or paste its text. Scanned PDFs need OCR before import.

Use **Settings** at the bottom left for language, appearance, send key, scrolling, answer speed, and thought process display. The rounded dialog groups these options under General, Appearance, and Responses; preferences are saved in the browser.

Empty new chats stay out of the sidebar until they contain a question, an imported paper, or a custom title. Answers appear progressively in the chat; DeepSeek uses its streaming response, while offline answers are revealed in short pieces. New answers show an expandable thought process with paper reading, evidence retrieval, model selection, and answer drafting steps; these steps are saved with the chat.

For DeepSeek answers, set `DEEPSEEK_API_KEY` in your local environment or in the repository root `.env` before starting the server. The app can also read a local `api_key.txt` in the repository root. Without a key, it uses its offline rule reader. Keep API keys out of Git.

Lecture 4 search credentials are stored locally in the same `.env` as `TAVILY_API_KEY` and `BOCHA_API_KEY`. The `.env` and original key text files are ignored by Git.

## Quick search and deep research (Lecture 4, Step 2)

Use the mode control beside the chat send button. The three positions are **Paper reading**, **Quick search**, and **Deep research**. Quick search makes one retrieval pass across the configured web providers and Crossref/arXiv, then directly shows linked results and snippets. Deep research uses the same four-source retrieval, filters and deduplicates results, reranks them with DeepSeek, extracts relevant content blocks, then streams an answer with numbered source references. Progress appears in the conversation while each stage runs. If DeepSeek is unavailable, deep research shows extracted source content instead of claiming an AI synthesis. Search works without importing a paper.

Deep research retains one title-relevant academic record in its six-source shortlist when the ranker would otherwise return only web pages. It does not add an unrelated academic record merely to increase source variety. Provider failures remain visible in the search status.

## Paper information collection (Lecture 4, Step 5)

Look up one paper by DOI, DOI URL, arXiv ID, or exact title. The result includes title, authors, year, DOI, venue, per-database coverage, and the reference list deposited in its Crossref record. Title matches are checked before the metadata is attributed to the requested paper. A failed or ambiguous match returns candidates without claiming their metadata belongs to that paper.

```powershell
.\.venv\Scripts\python.exe agent_system\code\paper_info_cli.py "10.1038/nature12373"
.\.venv\Scripts\python.exe agent_system\code\paper_info_cli.py "Nanometre-scale thermometry in a living cell" --output results\paper-info.json
```

The same data is available through `GET /api/paper-info?query=10.1038%2Fnature12373` and `from academic_metadata import collect_paper_info`. To try an imported paper, use `/api/paper-info?source=current` in a browser with that paper selected, or pass its source ID. This uses the imported filename as a title query and only attributes metadata if the title is verified; truncated filenames may require an explicit DOI or full title query. `coverage.crossref=registered` means a Crossref record was verified; `coverage.arxiv=record_found` means an arXiv metadata record was verified. `other_indexes=not_checked` does not claim Scopus or Web of Science indexing. A missing Crossref reference list is reported as `not_available_in_crossref_record`; it does not mean the paper has no references. Crossref reference deposits are optional.

## Unified multi-source API (Lecture 4, Step 3)

`GET /api/multi-source-search?query=...&mode=quick&limit=20` fans out to Tavily and 博查 when keys are configured, plus Crossref and arXiv. `mode=deep` requests expanded web content; `limit` accepts 1–40. The JSON response contains `query`, `mode`, `retrieved_at_utc`, `source_status` for all four providers, a `summary`, and normalized `results`. Each result has a stable `id`, `source_type`, `provider`/`providers`, title, URL and alternate URLs, snippet, DOI/arXiv ID, authors, year, and venue. The summary reports raw, valid, unique, and returned counts, duplicate count, web/academic counts, and providers that succeeded or failed. DOI, arXiv ID, canonical URL, and exact academic title are used for deduplication. A failed provider does not discard other providers' results.

## Reusable retrieval tool (Lecture 4, Step 4)

The retrieval layer can be used without a paper, chat session, or language model. Choose any combination of `Tavily`, `Bocha`, `Crossref`, and `arXiv`; names are case insensitive. The same normalized JSON schema and provider status are returned from each entry point. `quick` and `deep` control provider search depth; neither invokes AI synthesis in this tool.

```powershell
.\.venv\Scripts\python.exe agent_system\code\retrieval_cli.py "machine learning" --providers Crossref,arXiv --mode quick --limit 10
.\.venv\Scripts\python.exe agent_system\code\retrieval_cli.py "10.1145/3368089.3409751" --providers Crossref --output results\search.json
```

Python callers can import `from web_research.tool import search` with `agent_system/code` on `PYTHONPATH`, then call `search("query", providers=["Crossref", "arXiv"], limit=10)`. Web credentials can be supplied via `keys={"TAVILY_API_KEY": "..."}` or loaded from the project `.env`/process environment. Crossref and arXiv require no key. HTTP callers may use `/api/multi-source-search?query=machine%20learning&providers=Crossref,arXiv&mode=quick&limit=10`. Unselected providers are omitted from `source_status`; selected providers report `ok`, `unconfigured`, or `error` independently. The CLI writes JSON to stdout unless `--output` is specified.

The arXiv API client serializes requests within this process, waits at least 3 seconds between distinct calls, and caches identical successful lookups for 10 minutes. arXiv's API terms require no more than one request every three seconds and one connection at a time. When the arXiv API returns HTTP 429 or times out, the client temporarily stops calling that endpoint and queries OpenAlex for records with a verified arXiv source and abstract URL. This is a separate metadata index, not a successful arXiv API response: `source_status.arXiv.status` is `degraded`, `via` is `OpenAlex`, and each record has `metadata_source=OpenAlex`. If both services fail, arXiv remains an error and other sources' results are retained. Other processes or clients using the same network can still consume the arXiv upstream rate allowance.

## Academic metadata API (Lecture 4, Step 1)

The backend exposes `GET /api/academic-search?query=...` for Crossref and arXiv metadata. Add `source=crossref` or `source=arxiv` to query one service, and `limit=1` through `20` to control results per service. The JSON response includes normalized paper records and a separate status for each requested service. Crossref and arXiv do not require the Tavily, 博查, or DeepSeek keys for this endpoint.

Example: `http://127.0.0.1:8787/api/academic-search?query=joint%20embedding%20predictive%20architecture&limit=3`

The metadata backend is split into `academic_metadata/crossref.py`, `academic_metadata/arxiv.py`, and `academic_metadata/service.py`. `web_server.py` handles HTTP routes; `reader_views.py` renders the original reading and diagnostics pages. `diagnostics.py` handles log extraction and acceptance checks, and `cli.py` parses commands. `agent_core.py` retains paper processing, answer generation, and compatibility entry points for the existing commands and tests.

Conversation records, imported papers, and execution logs stay in local folders under `agent_system/` and are ignored by Git.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s agent_system\code -p "test_*.py" -v
```

`materials/论文_带毒版.md` is a fictional teaching fixture for the audit tests. One PDF import test expects an optional local paper at `agent_system/inputs/2022_LeCun_Autonomous_Machine_Intelligence.pdf` and skips when it is absent.

This project was developed for *Frontiers in Computer Science I*.

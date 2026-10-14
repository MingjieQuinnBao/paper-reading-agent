# Paper Reading Agent

A local web app for importing a research paper, asking questions, and keeping conversation history. The interface is in Simplified Chinese. It accepts PDF, Markdown, and plain text; pasted text also works.

## Run locally

From the repository root in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r agent_system\requirements.txt
.\.venv\Scripts\python.exe agent_system\code\agent_core.py server --port 8787
```

Open <http://127.0.0.1:8787>, then import a paper or paste its text. Scanned PDFs need OCR before import.

For DeepSeek answers, set `DEEPSEEK_API_KEY` in your local environment before starting the server. Without a key, the app uses its offline rule reader. Keep API keys out of this repository.

Conversation records, imported papers, and execution logs stay in local folders under `agent_system/` and are ignored by Git.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s agent_system\code -p "test_*.py" -v
```

`materials/论文_带毒版.md` is a fictional teaching fixture for the audit tests. One PDF import test expects an optional local paper at `agent_system/inputs/2022_LeCun_Autonomous_Machine_Intelligence.pdf` and skips when it is absent.

This project was developed for *Frontiers in Computer Science I*.

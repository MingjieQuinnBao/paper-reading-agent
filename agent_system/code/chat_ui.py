"""Small server-rendered chat interface; no browser-side conversation state."""

from __future__ import annotations

import html
import re
import secrets
from pathlib import Path
from typing import Any

import bleach
import mistune


_markdown = mistune.create_markdown(escape=True, plugins=["table", "strikethrough", "url"])
_allowed_tags = frozenset({
    "a", "blockquote", "br", "code", "del", "em", "h1", "h2", "h3", "h4", "h5", "h6",
    "hr", "li", "ol", "p", "pre", "strong", "table", "tbody", "td", "th", "thead", "tr", "ul",
})


def render_markdown(value: Any) -> str:
    # Mistune treats TeX delimiters as Markdown escapes. Restore them after sanitizing,
    # so earlier malformed Markdown cannot duplicate their backslashes.
    source = str(value)
    # Older research answers stored bibliography entries on adjacent Markdown
    # lines, which Markdown renders as one paragraph. Reformat on display too.
    if "### 來源\n\n" in source:
        before, heading, bibliography = source.partition("### 來源\n\n")
        bibliography = re.sub(
            r"(?m)^\[(\d+)\] (?=\[[^\n]+\]\(https?://)",
            lambda match: f"\n\n{match.group(1)}. ", bibliography,
        )
        source = before + heading + bibliography.lstrip("\n")
    nonce = secrets.token_hex(12)
    delimiters = (r"\(", r"\)", r"\[", r"\]")
    markers = [f"TEXDELIM{nonce}{index}END" for index in range(len(delimiters))]
    for delimiter, marker in zip(delimiters, markers):
        source = source.replace(delimiter, marker)
    rendered = bleach.clean(
        _markdown(source), tags=_allowed_tags,
        attributes={"a": ["href", "title"], "th": ["align"], "td": ["align"]},
        protocols=["http", "https", "mailto"], strip=True,
    )
    for delimiter, marker in zip(delimiters, markers):
        rendered = rendered.replace(marker, delimiter)
    return rendered


PAGE = (Path(__file__).with_name("static") / "chat.html").read_text(encoding="utf-8")


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


_PROCESS_LABELS = {
    "processPaperPages": "讀取論文，共 {pages} 頁",
    "processPaperSections": "讀取論文，共 {pages} 節",
    "processEvidence": "檢索相關內容：{pages}",
    "processRoute": "選擇模型：{model}",
    "processReading": "閱讀論文並分析問題",
    "processPart": "閱讀論文片段 {position}",
    "processCombine": "整理各段閱讀筆記",
    "processDraft": "整合證據並撰寫回答",
    "processOffline": "根據檢索結果整理回答",
    "processFallback": "切換至本地閱讀流程",
    "processDone": "回答完成",
    "processSearch": "搜尋來源：{position}",
    "processFilter": "篩選來源：{position}",
    "processRerank": "重排結果：{position}",
    "processExtract": "提取內容塊：{position}",
    "processResearchDraft": "根據來源撰寫回答",
}


def render_process(steps: Any) -> str:
    if not isinstance(steps, list) or not steps:
        return ""
    items = []
    for step in steps:
        if not isinstance(step, dict) or step.get("key") not in _PROCESS_LABELS:
            continue
        key = step["key"]
        values = {name: str(step.get(name, "")) for name in ("pages", "position", "model")}
        label = _PROCESS_LABELS[key].format(**values)
        attrs = " ".join(f'data-{name}="{_esc(value)}"' for name, value in values.items() if value)
        items.append(f'<li><span data-i18n="{key}" {attrs}>{_esc(label)}</span></li>')
    if not items:
        return ""
    return ('<details class="reasoning-process"><summary data-i18n="reasoningTitle">思考過程</summary>'
            f'<ol>{"".join(items)}</ol></details>')


def render(
    session: dict[str, Any], sessions: list[dict[str, Any]], config: Any,
    paper_name: str = "", search: str = "", error: str = "", draft: str = "", paper_text: str = "",
) -> str:
    session_id = session["session_id"]
    links = []
    for item in sessions:
        active = " active" if item["session_id"] == session_id else ""
        item_id = _esc(item["session_id"])
        raw_title = item.get("title") or "新对话"
        title = _esc(raw_title)
        title_markup = '<span data-i18n="newChat">新对话</span>' if raw_title == "新对话" else title
        title_i18n = ' data-i18n-title="newChat"' if raw_title == "新对话" else ''
        links.append(
            f'<div class="session-item{active}">'
            f'<a class="session-link" href="/?session={item_id}" title="{title}"{title_i18n}>{title_markup}</a>'
            '<details class="session-menu"><summary aria-label="对话操作" data-i18n-aria="conversationActions" title="对话操作" data-i18n-title="conversationActions">⋯</summary>'
            '<div class="menu-panel"><button class="menu-action" type="button" data-rename data-i18n="rename">重命名</button>'
            f'<form class="rename-form" method="post" action="/rename" hidden><input type="hidden" name="session_id" value="{item_id}">'
            f'<input name="title" aria-label="对话名称" data-i18n-aria="conversationName" value="{title}" maxlength="80" required><button type="submit" data-i18n="save">保存</button></form>'
            f'<form class="delete-form" method="post" action="/delete"><input type="hidden" name="session_id" value="{item_id}">'
            '<button class="menu-action danger" type="submit" data-i18n="delete">删除</button></form></div></details></div>'
        )
    if not links:
        links.append('<span class="side-title" data-i18n="noChats">暂无对话</span>')

    query = search.strip().casefold()
    if query:
        if query.startswith("#"):
            query = query[1:]
        if query.isdigit():
            shown = [turn for turn in session["turns"] if turn.get("number") == int(query)]
        else:
            shown = [turn for turn in session["turns"] if
                     query in str(turn.get("question", "")).casefold() or
                     query in str(turn.get("answer", "")).casefold()]
    else:
        shown = session["turns"]
    bubbles = []
    for turn in shown:
        annotations = "".join(f'<span class="tag alert">{_esc(label)}</span>' for label in turn.get("annotations", []))
        evidence = "".join(f'<span class="tag">{_esc(item.get("label", ""))}</span>'
                           for item in turn.get("evidence", []) if isinstance(item, dict) and item.get("label"))
        bubbles.append(
            f'<article class="turn" id="turn-{int(turn["number"])}">'
            f'<p class="turn-title"><span data-i18n="turnPrefix">第</span> {int(turn["number"])} <span data-i18n="turnSuffix">轮</span> · {_esc(turn.get("created_at", ""))}</p>'
            f'<div class="bubble user-bubble">{render_markdown(turn["question"])}</div>'
            f'{render_process(turn.get("process"))}'
            f'<div class="bubble assistant-bubble">{render_markdown(turn["answer"])}'
            f'<div class="turn-meta">{_esc(turn.get("model", ""))} {_esc(turn.get("run_id", ""))}</div>'
            f'{annotations}{evidence}</div></article>'
        )
    if bubbles:
        messages = "".join(bubbles)
    elif query:
        messages = '<div class="empty"><b data-i18n="noResults">没有找到对应轮次</b><span data-i18n="noResultsHint">试试问题关键词或轮次编号。</span></div>'
    else:
        messages = '<div class="empty"><b data-i18n="emptyTitle">开始阅读</b><span data-i18n="emptyHint">导入或粘贴论文，然后提出问题。</span></div>'

    choice = "auto" if config.route_mode == "auto" else config.model
    models = (("auto", "自动"), ("deepseek-flash", "DeepSeek Flash"),
              ("deepseek-v4-pro", "DeepSeek V4 Pro"), ("rule-reader", "Rule Reader"), ("mock-fast", "Mock Fast"))
    options = "".join(f'<option value="{model}"{" selected" if model == choice else ""}'
                      f'{" data-i18n=\"autoModel\"" if model == "auto" else ""}>{label}</option>'
                      for model, label in models)
    values = {
        "{sessions}": "".join(links), "{session_id}": _esc(session_id),
        "{title}": ('<span data-i18n="newChat">新对话</span>'
                    if (session.get("title") or "新对话") == "新对话"
                    else _esc(session["title"])),
        "{paper_status}": (f'<span data-i18n="imported">已导入</span> {_esc(paper_name)}'
                           if paper_name else '<span data-i18n="noPaper">未导入论文</span>'),
        "{error}": f'<div class="error">{_esc(error)}</div>' if error else "",
        "{search}": _esc(search), "{clear_search}": '<a href="/?session=' + _esc(session_id) + '" data-i18n="showAll">显示全部</a>' if search else "",
        "{messages}": messages, "{draft}": _esc(draft), "{paper_text}": _esc(paper_text),
        "{paper_summary}": "导入论文" if not paper_name else "更换论文",
        "{paper_summary_key}": "importPaper" if not paper_name else "replacePaper",
        "{model_options}": options, "{temperature}": str(config.temperature), "{top_p}": str(config.top_p),
        "{max_tokens}": str(config.max_tokens), "{evidence_limit}": str(config.evidence_limit),
    }
    page = PAGE
    for token, value in values.items():
        page = page.replace(token, value)
    return page

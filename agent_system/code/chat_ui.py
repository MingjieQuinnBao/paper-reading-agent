"""Small server-rendered chat interface; no browser-side conversation state."""

from __future__ import annotations

import html
from typing import Any

import bleach
import mistune


_markdown = mistune.create_markdown(escape=True, plugins=["table", "strikethrough", "url"])
_allowed_tags = frozenset({
    "a", "blockquote", "br", "code", "del", "em", "h1", "h2", "h3", "h4", "h5", "h6",
    "hr", "li", "ol", "p", "pre", "strong", "table", "tbody", "td", "th", "thead", "tr", "ul",
})


def render_markdown(value: Any) -> str:
    return bleach.clean(
        _markdown(str(value)), tags=_allowed_tags,
        attributes={"a": ["href", "title"], "th": ["align"], "td": ["align"]},
        protocols=["http", "https", "mailto"], strip=True,
    )


PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>论文阅读 Agent</title><style>
:root{font-family:"Microsoft YaHei",Arial,sans-serif;color:#1e2b32;background:#f5f7f7}*{box-sizing:border-box}
body{margin:0;line-height:1.55}a{color:#0b7771;text-decoration:none}a:hover{text-decoration:underline}
button,input,textarea,select{font:inherit}button{border:0;border-radius:9px;padding:9px 13px;background:#087a74;color:white;font-weight:700;cursor:pointer}button:hover{background:#086962}
button.secondary,.button-link{background:#e9f3f1;color:#176760}.button-link{display:inline-block;border-radius:9px;padding:9px 13px;font-size:13px;font-weight:700}
input,textarea,select{border:1px solid #cbd7d5;border-radius:9px;background:#fff;color:inherit;padding:9px 11px;width:100%}textarea{resize:vertical}
button:focus-visible,input:focus-visible,textarea:focus-visible,select:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid #80c8bd;outline-offset:2px}
.app{min-height:100vh;display:grid;grid-template-columns:250px minmax(0,1fr)}.sidebar{background:#edf3f2;border-right:1px solid #dfe8e6;padding:20px 14px;display:flex;flex-direction:column;gap:16px}
.brand{font-size:18px;font-weight:800;padding:4px 7px}.sidebar form{margin:0}.sidebar .new{width:100%;text-align:left}.side-title{font-size:12px;font-weight:700;color:#71817e;margin:5px 7px}
.session-list{display:flex;flex-direction:column;gap:4px}.session-item{position:relative;display:flex;align-items:center;border-radius:9px;min-width:0}.session-item:hover,.session-item:focus-within{background:#e3eeeb}.session-item.active{background:#d7e9e5}.session-link{display:block;flex:1;min-width:0;color:#304740;border-radius:9px;padding:9px 6px 9px 10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:13px}.session-item.active .session-link{color:#125d57;font-weight:700}.session-link small{display:block;color:#7b8986;font-weight:400}.session-menu{position:relative;flex:none;margin:0;padding:0;border:0}.session-menu>summary{list-style:none;display:grid;place-items:center;width:30px;height:30px;border-radius:7px;color:#51645f;cursor:pointer;font-size:22px;line-height:1}.session-menu>summary::-webkit-details-marker{display:none}.session-menu>summary:hover,.session-menu[open]>summary{background:#d5e5e1}.menu-panel{position:absolute;top:34px;right:0;z-index:20;width:220px;background:#fff;border:1px solid #dce6e3;border-radius:11px;padding:6px;box-shadow:0 10px 28px rgba(20,50,50,.15)}.menu-action{display:block;width:100%;background:transparent;color:#2b423b;text-align:left;font-size:13px;font-weight:500;padding:9px 11px}.menu-action:hover{background:#eef5f3;color:#174b43}.menu-action.danger{color:#a63f38}.menu-action.danger:hover{background:#fff0ed;color:#8b2f29}.rename-form{display:flex;gap:6px;padding:6px}.rename-form[hidden]{display:none}.rename-form input{min-width:0;font-size:12px}.rename-form button{font-size:12px;padding:6px 9px}
.import-form{border-top:1px solid #d7e2df;padding-top:14px;margin-top:auto!important}.import-form label{display:block;font-size:12px;color:#637a75;margin-bottom:6px}.import-form input{font-size:12px}.import-form button{margin-top:8px;width:100%}
.chat{min-width:0;display:flex;flex-direction:column;min-height:100vh}.chat-head{background:#fff;border-bottom:1px solid #e2e9e8;padding:17px clamp(18px,4vw,52px);display:flex;align-items:center;justify-content:space-between;gap:16px}
.chat-head h1{font-size:19px;margin:0;line-height:1.3}.sub{color:#72817e;font-size:12px;margin-top:4px}.head-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.content{width:min(860px,100%);margin:0 auto;padding:24px 24px 8px;flex:1}.search{display:flex;gap:8px;margin-bottom:22px}.search input{max-width:340px}.search button{font-size:13px}.search a{font-size:13px;align-self:center}
.empty{padding:80px 18px;text-align:center;color:#788783}.empty b{display:block;color:#344844;font-size:22px;margin-bottom:5px}
.turn{margin:0 0 32px}.turn-title{color:#84918f;font-size:12px;margin:0 0 9px}.bubble{border-radius:15px;padding:12px 16px;overflow-wrap:anywhere}.bubble>:first-child{margin-top:0}.bubble>:last-child{margin-bottom:0}.bubble p{margin:0 0 12px}.bubble h1,.bubble h2,.bubble h3{line-height:1.35;margin:17px 0 8px}.bubble h1{font-size:20px}.bubble h2{font-size:17px}.bubble h3{font-size:15px}.bubble ul,.bubble ol{padding-left:23px;margin:8px 0 13px}.bubble li{margin:3px 0}.bubble blockquote{border-left:3px solid #91bbb3;margin:12px 0;padding:2px 12px;color:#576c66}.bubble code{background:#e9f0ee;border-radius:4px;padding:1px 4px;font:13px/1.5 Consolas,monospace}.bubble pre{background:#172b2b;color:#f3f7f5;border-radius:9px;padding:13px;overflow:auto;white-space:pre;max-width:100%}.bubble pre code{background:none;color:inherit;padding:0}.bubble table{display:block;overflow-x:auto;border-collapse:collapse;margin:12px 0}.bubble th,.bubble td{border:1px solid #d9e3e0;padding:6px 9px;text-align:left}.user-bubble{background:#e3f1ee;max-width:75%;margin-left:auto}.assistant-bubble{background:#fff;border:1px solid #e5ebea;box-shadow:0 3px 12px rgba(20,50,50,.035);margin-top:11px}.turn-meta{font-size:11px;color:#74827f;margin:10px 0 0}.tag{display:inline-block;border-radius:999px;background:#eef4f3;color:#376a65;padding:2px 8px;margin:0 5px 5px 0;font-size:11px}.tag.alert{background:#fff1e4;color:#935c1f}.error{background:#fff2ed;color:#93452f;padding:11px 14px;border-radius:9px;margin-bottom:18px}
.composer-wrap{position:sticky;bottom:0;background:linear-gradient(transparent,#f5f7f7 14%);padding:14px 24px 22px}.composer{width:min(860px,100%);margin:auto;background:#fff;border:1px solid #dce7e4;border-radius:16px;padding:14px;box-shadow:0 10px 32px rgba(20,50,50,.08)}
.composer textarea.question{min-height:78px;border:0;padding:5px;outline:none}.composer textarea.question:focus-visible{outline:0}.composer-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;border-top:1px solid #edf1f0;padding-top:12px}.composer-row select{width:auto;max-width:190px;font-size:13px}.composer-row .spacer{flex:1}.composer-row button{font-size:13px}
.paper-details,.settings-details{border-top:1px solid #edf1f0;padding-top:10px;margin-top:10px}.paper-details summary,.settings-details summary{font-size:12px;color:#637873;cursor:pointer}.paper-details label,.settings-details label{display:block;font-size:12px;font-weight:700;margin:10px 0 5px}.paper-details textarea{min-height:90px}.or{font-size:11px;color:#899995;margin:7px 0}.settings-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.settings-grid input{font-size:13px}
.status{font-size:12px;color:#176760;margin-top:8px;min-height:16px}
@media(max-width:760px){.app{display:block}.sidebar{padding:10px;display:block;border-right:0;border-bottom:1px solid #dfe8e6}.brand{display:inline-block}.sidebar .new{width:auto}.sidebar form:first-of-type{display:inline-block}.session-list{max-height:170px;overflow-y:auto}.session-link{min-width:0}.menu-panel{right:0}.side-title{display:none}.import-form{display:flex;align-items:center;gap:6px;padding-top:8px;margin-top:8px!important}.import-form label{display:none}.import-form input{max-width:180px}.import-form button{width:auto;margin:0}.chat{min-height:calc(100vh - 104px)}.chat-head{padding:14px 18px}.content{padding:18px}.composer-wrap{padding:10px}.user-bubble{max-width:90%}.settings-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style></head><body><div class="app">
<aside class="sidebar"><div class="brand">论文阅读 Agent</div>
<form method="post" action="/new"><button class="new" type="submit">＋ 新对话</button></form>
<div class="side-title">对话记录</div><nav class="session-list">{sessions}</nav>
<form class="import-form" method="post" action="/import" enctype="multipart/form-data"><label for="session_file">加载对话文件</label><input id="session_file" type="file" name="session_file" accept=".json,application/json" required><button class="secondary" type="submit">加载并续聊</button></form>
</aside><main class="chat"><header class="chat-head"><div><h1>{title}</h1><div class="sub">{paper_status} · {turn_count} 轮对话</div></div><div class="head-actions"><a class="button-link" href="/export?session={session_id}">导出对话</a></div></header>
<div class="content">{error}<form class="search" method="get" action="/"><input type="hidden" name="session" value="{session_id}"><input name="search" value="{search}" placeholder="搜索问题、回答或轮次编号"><button class="secondary" type="submit">查找</button>{clear_search}</form>{messages}</div>
<div class="composer-wrap"><form class="composer" method="post" action="/ask" enctype="multipart/form-data"><input type="hidden" name="session_id" value="{session_id}">
<textarea class="question" name="q" placeholder="问这篇论文的任何问题…">{draft}</textarea>
<details class="paper-details" {paper_open}><summary>{paper_summary}</summary><label for="paper_file">导入论文文件</label><input id="paper_file" name="paper_file" type="file" accept=".pdf,.md,.txt"><div class="or">或</div><label for="paper_text">粘贴论文正文</label><textarea id="paper_text" name="paper_text" placeholder="粘贴论文文本">{paper_text}</textarea></details>
<details class="settings-details"><summary>参数设置</summary><div class="settings-grid"><div><label>temperature</label><input name="temperature" type="number" min="0" max="1.5" step="0.1" value="{temperature}"></div><div><label>top_p</label><input name="top_p" type="number" min="0.1" max="1" step="0.05" value="{top_p}"></div><div><label>max_tokens</label><input name="max_tokens" type="number" min="100" max="6000" step="100" value="{max_tokens}"></div><div><label>证据数</label><input name="evidence_limit" type="number" min="1" max="8" value="{evidence_limit}"></div></div></details>
<div class="composer-row"><select name="model_choice" aria-label="模型">{model_options}</select><span class="spacer"></span><button class="secondary" name="action" value="read" type="submit">生成摘要</button><button name="action" value="ask" type="submit">发送</button></div><div id="submit_status" class="status" role="status"></div>
</form></div></main></div><script>
document.querySelector('.composer').addEventListener('submit',e=>{document.querySelector('#submit_status').textContent=e.submitter?.value==='read'?'正在生成摘要…':'正在回答…'});
document.querySelectorAll('.session-menu').forEach(menu=>menu.addEventListener('toggle',()=>{if(menu.open)document.querySelectorAll('.session-menu').forEach(other=>{if(other!==menu)other.open=false})}));
document.querySelectorAll('[data-rename]').forEach(button=>button.addEventListener('click',()=>{const form=button.nextElementSibling;form.hidden=false;form.querySelector('input[name="title"]').focus()}));
document.querySelectorAll('.delete-form').forEach(form=>form.addEventListener('submit',e=>{if(!window.confirm('确定删除这个对话吗？原始调用日志会保留。'))e.preventDefault()}));
document.addEventListener('click',e=>{if(!e.target.closest('.session-menu'))document.querySelectorAll('.session-menu').forEach(menu=>menu.open=false)});
document.addEventListener('keydown',e=>{if(e.key==='Escape')document.querySelectorAll('.session-menu').forEach(menu=>menu.open=false)});
</script></body></html>"""


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def render(
    session: dict[str, Any], sessions: list[dict[str, Any]], config: Any,
    paper_name: str = "", search: str = "", error: str = "", draft: str = "", paper_text: str = "",
) -> str:
    session_id = session["session_id"]
    links = []
    for item in sessions:
        active = " active" if item["session_id"] == session_id else ""
        item_id = _esc(item["session_id"])
        title = _esc(item.get("title") or "新对话")
        links.append(
            f'<div class="session-item{active}">'
            f'<a class="session-link" href="/?session={item_id}" title="{title}">{title}'
            f'<small>{len(item.get("turns", []))} 轮</small></a>'
            '<details class="session-menu"><summary aria-label="对话操作" title="对话操作">⋯</summary>'
            '<div class="menu-panel"><button class="menu-action" type="button" data-rename>重命名</button>'
            f'<form class="rename-form" method="post" action="/rename" hidden><input type="hidden" name="session_id" value="{item_id}">'
            f'<input name="title" aria-label="对话名称" value="{title}" maxlength="80" required><button type="submit">保存</button></form>'
            f'<form class="delete-form" method="post" action="/delete"><input type="hidden" name="session_id" value="{item_id}">'
            '<button class="menu-action danger" type="submit">删除</button></form></div></details></div>'
        )
    if not links:
        links.append('<span class="side-title">暂无对话</span>')

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
            f'<p class="turn-title">第 {int(turn["number"])} 轮 · {_esc(turn.get("created_at", ""))}</p>'
            f'<div class="bubble user-bubble">{render_markdown(turn["question"])}</div>'
            f'<div class="bubble assistant-bubble">{render_markdown(turn["answer"])}'
            f'<div class="turn-meta">{_esc(turn.get("model", ""))} {_esc(turn.get("run_id", ""))}</div>'
            f'{annotations}{evidence}</div></article>'
        )
    if bubbles:
        messages = "".join(bubbles)
    elif query:
        messages = '<div class="empty"><b>没有找到对应轮次</b>试试问题关键词或轮次编号。</div>'
    else:
        messages = '<div class="empty"><b>开始阅读</b>导入或粘贴论文，然后提出问题。</div>'

    choice = "auto" if config.route_mode == "auto" else config.model
    models = (("auto", "自动"), ("deepseek-flash", "DeepSeek Flash"),
              ("deepseek-v4-pro", "DeepSeek V4 Pro"), ("rule-reader", "Rule Reader"), ("mock-fast", "Mock Fast"))
    options = "".join(f'<option value="{model}"{" selected" if model == choice else ""}>{label}</option>'
                      for model, label in models)
    values = {
        "{sessions}": "".join(links), "{session_id}": _esc(session_id),
        "{title}": _esc(session.get("title") or "新对话"),
        "{paper_status}": _esc("已导入 " + paper_name if paper_name else "未导入论文"),
        "{turn_count}": str(len(session["turns"])), "{error}": f'<div class="error">{_esc(error)}</div>' if error else "",
        "{search}": _esc(search), "{clear_search}": '<a href="/?session=' + _esc(session_id) + '">显示全部</a>' if search else "",
        "{messages}": messages, "{draft}": _esc(draft), "{paper_text}": _esc(paper_text),
        "{paper_open}": "open" if not paper_name else "", "{paper_summary}": "导入论文" if not paper_name else "更换论文",
        "{model_options}": options, "{temperature}": str(config.temperature), "{top_p}": str(config.top_p),
        "{max_tokens}": str(config.max_tokens), "{evidence_limit}": str(config.evidence_limit),
    }
    page = PAGE
    for token, value in values.items():
        page = page.replace(token, value)
    return page

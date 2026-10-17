"""Rendering for the original paper reading and diagnostics pages."""

from __future__ import annotations

import html
from itertools import groupby
from typing import Any


HTML_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>论文阅读 Agent</title>
<style>
:root{font-family:"Microsoft YaHei",Arial,sans-serif;color:#1d2a32;background:#f5f7f7}
*{box-sizing:border-box}body{margin:0;line-height:1.6}a{color:#0d6967;text-decoration:none}a:hover{text-decoration:underline}
header{border-bottom:1px solid #e2e9e8;background:#fff}.topbar{max-width:1200px;margin:auto;padding:20px 28px;display:flex;align-items:center;justify-content:space-between;gap:20px}
h1{font-size:22px;letter-spacing:.01em;margin:0}h2{font-size:17px;margin:0 0 18px}h3{font-size:15px;margin:20px 0 8px}
main{max-width:1200px;margin:28px auto;padding:0 28px;display:grid;grid-template-columns:minmax(320px,390px) minmax(0,1fr);gap:20px;align-items:start}
section{background:#fff;border:1px solid #e3e9e8;border-radius:14px;padding:24px;box-shadow:0 8px 28px rgba(24,52,52,.035)}
label{display:block;font-size:13px;font-weight:700;margin:18px 0 7px}textarea,select,input{width:100%;border:1px solid #cbd7d5;border-radius:9px;padding:10px 12px;font:inherit;background:#fff;color:inherit}
textarea{min-height:118px;resize:vertical}input[type=file]{font-size:13px;padding:9px}.paper-input{min-height:100px}.divider{display:flex;align-items:center;gap:12px;color:#899794;font-size:12px;margin:12px 0}.divider:before,.divider:after{content:"";height:1px;background:#e3e9e8;flex:1}
.loaded{display:inline-flex;align-items:center;gap:8px;background:#edf7f4;color:#21665c;border-radius:999px;padding:5px 11px;font-size:12px;max-width:100%;overflow-wrap:anywhere}.loaded:before{content:"";width:7px;height:7px;background:#48aa8b;border-radius:50%;flex:none}
.muted{color:#71807e;font-size:13px}.source-line{min-height:28px;margin:0 0 5px}.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}.actions{display:flex;gap:10px;margin-top:22px}button{border:0;border-radius:9px;padding:11px 16px;font:inherit;font-weight:700;cursor:pointer;background:#087a74;color:#fff}button:hover{background:#066862}.secondary-action{background:#e9f3f1;color:#176760}.secondary-action:hover{background:#daece8}
button:focus-visible,textarea:focus-visible,select:focus-visible,input:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid #80c8bd;outline-offset:2px}
details{border-top:1px solid #e8eeed;margin-top:18px;padding-top:14px}summary{cursor:pointer;color:#526b67;font-size:13px;font-weight:600}.status{min-height:22px;color:#176760;font-size:13px;margin:12px 0 0}
pre{white-space:pre-wrap;word-break:break-word;font:14px/1.75 "Microsoft YaHei",Arial,sans-serif;margin:0}.answer{font-size:15px;line-height:1.8;white-space:pre-wrap;overflow-wrap:anywhere}.pill{display:inline-block;background:#eef4f3;color:#376a65;border-radius:999px;padding:3px 10px;margin:0 7px 7px 0;font-size:12px}.result-meta{color:#71807e;font-size:12px;margin:0 0 14px}.result-question{font-size:16px;font-weight:700;margin:0 0 16px}.result-section{border-top:1px solid #e8eeed;padding-top:18px;margin-top:18px}.error{background:#fff4f0;color:#8c4232;padding:12px 14px;border-radius:8px}.trace{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0}.trace span{background:#eff4f3;border-radius:6px;padding:4px 8px;font-size:12px;color:#476b66}.trace span+span:before{content:"→ ";color:#94a5a0}.log-card{border-top:1px solid #e8eeed;padding:14px 0}.log-card:first-child{border-top:0}.log-card p{margin:5px 0;font-size:13px}.log-card small{color:#71807e}
.logs-view{display:block;max-width:880px}.logs-view .composer{display:none}
.warning{background:#fff7e8;color:#805b1a;padding:10px 12px;border-radius:8px;font-size:13px}
@media(max-width:820px){main{grid-template-columns:1fr;margin:18px auto;padding:0 16px}section{padding:20px}.topbar{padding:16px}.actions{flex-direction:column}}
</style>
</head>
<body>
<header><div class="topbar"><h1>论文阅读 Agent</h1>{header_action}</div></header>
<main class="{main_class}">
<section class="composer">
<form method="post" action="/ask" enctype="multipart/form-data">
<h2>论文</h2>
<p class="source-line">{paper_status}</p>
<label for="paper_file">导入文件</label>
<input id="paper_file" name="paper_file" type="file" accept=".pdf,.md,.txt">
<div class="divider">或</div>
<label for="paper_text">粘贴正文</label>
<textarea class="paper-input" id="paper_text" name="paper_text" placeholder="粘贴论文文本">{paper_text}</textarea>
<label for="question">问题</label>
<textarea id="question" name="q" placeholder="想了解这篇论文的什么？">{question}</textarea>
<label for="model_choice">模型</label>
<select id="model_choice" name="model_choice">{model_options}</select>
<details><summary>高级设置</summary>
<div class="row"><div><label>temperature</label><input name="temperature" type="number" min="0" max="1.5" step="0.1" value="{temperature}"></div><div><label>top_p</label><input name="top_p" type="number" min="0.1" max="1" step="0.05" value="{top_p}"></div></div>
<div class="row"><div><label>max_tokens</label><input name="max_tokens" type="number" min="100" max="6000" step="100" value="{max_tokens}"></div><div><label>证据数</label><input name="evidence_limit" type="number" min="1" max="8" step="1" value="{evidence_limit}"></div></div>
</details>
<div class="actions"><button type="submit" name="action" value="ask">提问</button><button class="secondary-action" type="submit" name="action" value="read">生成摘要</button></div>
<p id="submit_status" class="status" role="status"></p>
</form>
</section>
<section>
<h2>{panel_title}</h2>
{result}
</section>
</main>
<script>
document.querySelector('form').addEventListener('submit',e=>{document.querySelector('#submit_status').textContent=e.submitter?.value==='read'?'正在生成摘要…':'正在回答…'});
</script>
</body></html>"""


def render_page(core, content: str, cfg: core.AgentConfig | None = None, question: str = "", paper_text: str = "", logs_view: bool = False) -> str:
    cfg = cfg or core.AgentConfig(paper_source="")
    source = cfg.paper_source
    paper_status = (
        f'<span class="loaded">已导入 {html.escape(core.paper_metadata(source)["display_name"])}</span>'
        if source and source in core.load_paper_catalog() and core.paper_path(source).exists()
        else '<span class="muted">导入文件或粘贴正文后开始</span>'
    )
    choice = "auto" if cfg.route_mode == "auto" else cfg.model
    model_options = "".join(
        f'<option value="{model}"{" selected" if choice == model else ""}>{label}</option>'
        for model, label in (("auto", "自动"), ("deepseek-flash", "DeepSeek Flash"),
                             ("deepseek-v4-pro", "DeepSeek V4 Pro"), ("rule-reader", "Rule Reader"),
                             ("mock-fast", "Mock Fast"))
    )
    values = {
        "{question}": html.escape(question),
        "{paper_text}": html.escape(paper_text),
        "{paper_status}": paper_status,
        "{model_options}": model_options,
        "{header_action}": '<a href="/">返回阅读</a>' if logs_view else "",
        "{main_class}": "logs-view" if logs_view else "",
        "{panel_title}": "历史记录" if logs_view else "阅读结果",
        "{temperature}": str(cfg.temperature),
        "{top_p}": str(cfg.top_p),
        "{max_tokens}": str(cfg.max_tokens),
        "{evidence_limit}": str(cfg.evidence_limit),
        "{result}": content,
    }
    page = HTML_PAGE
    for token, value in values.items():
        page = page.replace(token, value)
    return page


def render_result(result: dict[str, Any] | None = None) -> str:
    if not result:
        return '<p class="muted">导入论文后，可以提问或生成摘要。</p>'
    pages = "".join(f'<span class="pill">{html.escape(item.get("label") or "PDF第{}页".format(item["page"]))}</span>' for item in result["evidence"])
    meta = result["meta"]
    actual = meta.get("fallback") or meta.get("actual_model") or meta.get("backend") or result["selected_model"]
    fallback_note = (
        f'<p class="error"><b>云端调用失败，已改用 {html.escape(str(actual))}。</b> '
        f'{html.escape(str(meta.get("error", "")))}</p>'
        if meta.get("fallback") else ""
    )
    length_note = (
        f'<p class="warning">回答达到 max_tokens={result["config"]["max_tokens"]}，可能不完整。可调高后重试。</p>'
        if meta.get("finish_reason") == "length" else ""
    )
    return (
        f'<p class="result-question">{html.escape(result["question"])}</p>'
        f'<p class="result-meta">{html.escape(result["paper_summary"]["display_name"])} · {html.escape(str(actual))}</p>'
        + fallback_note
        + length_note
        + f'<div class="answer">{html.escape(result["answer"])}</div>'
        + f'<div class="result-section">{pages}</div>'
        + render_trace_details(result["trace"], result["run_id"])
    )


def render_trace_details(trace: list[dict[str, Any]] | list[str], run_id: str) -> str:
    names = {"paper_input": "载入论文", "plan": "分析问题", "retrieve": "检索证据", "route": "选择模型",
             "llm_call": "调用模型", "offline_answer": "提取原文", "synthesize": "综合各段",
             "structured_parse": "整理结果", "fallback": "切换后端", "answer": "完成",
             "full_text": "读取全文", "chunked_full_text": "分段读取全文"}
    steps = [item.get("step", "") if isinstance(item, dict) else item for item in trace]
    timeline = "".join(
        f'<span>{html.escape(names.get(step, step))}{" ×" + str(count) if count > 1 else ""}</span>'
        for step, items in groupby(steps) if step for count in [len(list(items))]
    )
    return (
        '<details><summary>运行详情</summary>'
        f'<div class="trace">{timeline}</div>'
        f'<p class="muted">运行 ID：{html.escape(run_id)} · <a href="/logs">历史记录</a></p>'
        '</details>'
    )


def render_paper_reading(result: dict[str, Any]) -> str:
    generated = result["generated"]
    labels = (
        ("summary", "摘要"), ("research_question", "研究问题"),
        ("method", "方法"), ("experiments", "实验"),
        ("conclusions", "结论"), ("limitations", "局限"),
    )
    sections = "".join(f"<h3>{label}</h3><pre>{html.escape(generated[key])}</pre>" for key, label in labels)
    location_type = result["paper_summary"]["location_type"]
    pages = "、".join((f"PDF第{page}页" if location_type == "pdf" else f"文档第{page}节") for page in generated["evidence_pages"])
    return (
        f'<p class="result-meta">{html.escape(result["paper_summary"]["display_name"])} · '
        f'{html.escape(result["actual_model"] or result["selected_model"])} · {pages}</p>'
        + sections
        + render_trace_details(result.get("trace") or ["paper_input", result["input_coverage"], "llm_call", "structured_parse"], result["run_id"])
    )


def render_call_chain_list(core, chains: list[dict[str, Any]]) -> str:
    step_labels = {
        "paper_input": "加载论文", "plan": "规划", "retrieve": "检索证据",
        "route": "选择后端", "full_text": "读取全文", "chunked_full_text": "分段读取全文", "synthesize": "综合各段",
        "llm_call": "调用 LLM", "structured_parse": "解析结构化结果",
        "offline_answer": "离线回答", "fallback": "降级处理", "answer": "生成回答",
        "error": "发生错误", "trace_missing": "缺少轨迹文件",
    }
    status_labels = {"succeeded": "成功", "fell_back": "已降级", "failed": "失败", "incomplete": "日志不完整"}
    cards = []
    for row in reversed(chains[-8:]):
        steps = "".join(f'<span>{html.escape(step_labels.get(step, step))}</span>' for step in row["steps"])
        source_id = row.get("paper_source") or ""
        source = html.escape(core.paper_metadata(source_id)["display_name"] if source_id else "未知论文")
        title = html.escape(row.get("question") or "整篇论文摘要")
        model = html.escape(str(row.get("actual_model") or row.get("selected_model") or "未知后端"))
        cards.append(
            '<div class="log-card">'
            f'<b>{title}</b><p>{source} · {model} · {status_labels.get(row["status"], row["status"])}</p>'
            f'<div class="trace">{steps}</div>'
            f'<small>{html.escape(row["run_id"])}</small>'
            '</div>'
        )
    return "".join(cards) if cards else '<p class="muted">还没有运行记录。</p>'


def render_diff_demo(result: dict[str, Any], acceptance: list[dict[str, Any]]) -> str:
    cases = "".join(
        '<div class="case">'
        f"<h4>{html.escape(row['kind'])}</h4>"
        f'<span class="badge pass">{html.escape(row["judgement"])}</span>'
        f'<div class="pages">用例：{html.escape(row["case"])}</div>'
        f'<div class="pages">证据页码：{html.escape(str(row["evidence_pages"]))}</div>'
        "</div>"
        for row in acceptance
    )
    flow_nodes = "".join(
        f'<span class="node">{html.escape(step)}</span>' + ('<span class="arrow">→</span>' if i < len(result["trace"]) - 1 else "")
        for i, step in enumerate(item["step"] for item in result["trace"])
    )
    pages = "".join(f'<span class="pill">PDF第{item["page"]}页</span>' for item in result["evidence"])
    return (
        '<div class="diff-hero">'
        '<div class="compare">'
        '<span class="badge">3.1</span><h3>系统能跑</h3>'
        '<ul><li>单次问答</li><li>模型切换</li><li>参数调节</li></ul>'
        "</div>"
        '<div class="compare new">'
        '<span class="badge new">3.2</span><h3>交互应用可验收</h3>'
        '<ul><li>论文输入处理</li><li>日志链路提取</li><li>三类用例判定</li></ul>'
        "</div>"
        "</div>"
        '<div class="metrics">'
        f'<div class="metric"><div class="num">{result["paper_summary"]["pages"]}</div><div class="label">论文页码标记</div></div>'
        f'<div class="metric"><div class="num">{len(result["trace"])}</div><div class="label">调用链路节点</div></div>'
        f'<div class="metric"><div class="num">{len(acceptance)}</div><div class="label">验收用例类型</div></div>'
        f'<div class="metric"><div class="num">{sum(1 for row in acceptance if row["passed"])}</div><div class="label">通过用例</div></div>'
        "</div>"
        "<h3>3.2 调用链路视图</h3>"
        f'<div class="flow">{flow_nodes}</div>'
        "<h3>三类验收用例</h3>"
        f'<div class="case-grid">{cases}</div>'
        "<h3>论文输入与证据</h3>"
        f"<p><b>论文输入：</b>{html.escape(result['paper_summary']['paper_source'])}，{result['paper_summary']['chars']} 字符</p>"
        f"<p>{pages}</p>"
        f"<p><b>选中模型：</b>{html.escape(result['selected_model'])}</p>"
        '<h3>Agent 回答</h3>'
        f'<pre class="answer-slim">{html.escape(result["answer"])}</pre>'
    )

\n
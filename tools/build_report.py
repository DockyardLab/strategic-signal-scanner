#!/usr/bin/env python3
"""Build a simple business-first HTML report from a scored signal file."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

LOCAL_TZ = timezone(timedelta(hours=8))
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from feedback import (
    FeedbackState,
    apply_feedback_adjustment,
    feedback_base_url_from_env,
    feedback_identity,
    feedback_token_from_env,
    load_feedback,
)

DEFAULT_ARTIFACT_DIR = REPO_DIR / "artifacts" / "rss"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build HTML report from scored signal JSON.")
    parser.add_argument(
        "--scored-file",
        type=str,
        default="",
        help="Path to a scored_YYYY-MM-DD.json file. If omitted, use the latest one in artifacts/rss.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Optional explicit output path. If omitted, writes report_YYYY-MM-DD.html next to the scored file.",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=180,
        help="Hide items older than this many days from the report. Default: 180.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scored_path = _resolve_scored_file(args.scored_file)
    payload = json.loads(scored_path.read_text(encoding="utf-8"))
    feedback_state, _ = load_feedback(REPO_DIR)
    feedback_base_url = feedback_base_url_from_env()
    feedback_token = feedback_token_from_env()

    items = payload.get("high_signal_items") or _fallback_high_signal_items(payload.get("items") or [])
    report_date = _infer_report_date(payload, scored_path)
    report_dt = _parse_report_datetime(report_date)
    items, hidden_old_count = _filter_recent_items(items, report_dt, max(0, args.max_age_days))
    items = sorted(items, key=_sort_item_key, reverse=True)

    html_text = _build_report_html(
        payload,
        items,
        report_date,
        max(0, args.max_age_days),
        hidden_old_count,
        feedback_state,
        feedback_base_url,
        feedback_token,
    )
    html_text = _apply_long_table_theme(html_text)

    output_path = _resolve_output_path(args.output, scored_path, report_date)
    output_path.write_text(html_text, encoding="utf-8")
    print(f"Report saved: {output_path}")
    return 0


def _resolve_scored_file(scored_file: str) -> Path:
    if scored_file:
        path = Path(scored_file)
        return path if path.is_absolute() else (REPO_DIR / path)

    candidates = sorted(DEFAULT_ARTIFACT_DIR.glob("scored_*.json"))
    if not candidates:
        raise FileNotFoundError(f"No scored_*.json found in {DEFAULT_ARTIFACT_DIR}")
    return candidates[-1]


def _resolve_output_path(output: str, scored_path: Path, report_date: str) -> Path:
    if output:
        out = Path(output)
        return out if out.is_absolute() else (REPO_DIR / out)
    return scored_path.with_name(f"report_{report_date}.html")


def _infer_report_date(payload: dict[str, Any], scored_path: Path) -> str:
    scored_at = str(payload.get("scored_at") or "").strip()
    if scored_at:
        try:
            parsed = datetime.strptime(scored_at, "%Y-%m-%d %H:%M")
            return parsed.astimezone(LOCAL_TZ).strftime("%Y-%m-%d")
        except ValueError:
            pass
    stem = scored_path.stem
    if stem.startswith("scored_"):
        return stem.replace("scored_", "")
    return datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")


def _fallback_high_signal_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in items if int(_analysis(item).get("relevance_score", 0)) >= 3]


def _analysis(item: dict[str, Any]) -> dict[str, Any]:
    analysis = item.get("analysis")
    return analysis if isinstance(analysis, dict) else {}


def _build_report_html(
    payload: dict[str, Any],
    items: list[dict[str, Any]],
    report_date: str,
    max_age_days: int,
    hidden_old_count: int,
    feedback_state: FeedbackState,
    feedback_base_url: str,
    feedback_token: str,
) -> str:
    count = int(payload.get("count") or len(payload.get("items") or []))
    high_signal_count = len(items)
    highest_score = max((int(_analysis(item).get("relevance_score", 0)) for item in items), default=0)
    source_counts = Counter(str(item.get("source", "Unknown")).strip() for item in items if item.get("source"))
    type_counts = Counter(str(_analysis(item).get("signal_type", "Unknown")).strip() for item in items)
    sources = _ordered_unique([str(item.get("source", "")).strip() for item in items if item.get("source")])

    lead = _lead_sentence(items, max_age_days)

    cards = "\n".join(
        _render_item_card(
            item,
            rank=index + 1,
            report_date=report_date,
            feedback_state=feedback_state,
            feedback_base_url=feedback_base_url,
            feedback_token=feedback_token,
        )
        for index, item in enumerate(items)
    )
    source_badges = "\n".join(
        f'<span class="pill pill-blue">{_escape(name)} · {count}</span>' for name, count in source_counts.items()
    ) or '<span class="pill">无</span>'
    type_badges = "\n".join(
        f'<span class="pill pill-green">{_escape(name)} · {count}</span>' for name, count in type_counts.items()
    ) or '<span class="pill">无</span>'

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Strategic Signal Report · {report_date}</title>
  <style>
    :root {{
      --bg: #f6f8fc;
      --panel: rgba(255,255,255,.88);
      --panel-strong: #ffffff;
      --line: #dbe5f4;
      --text: #0f172a;
      --muted: #475569;
      --muted-2: #64748b;
      --blue: #1d4ed8;
      --blue-bg: #dbeafe;
      --green: #15803d;
      --green-bg: #dcfce7;
      --amber: #b45309;
      --amber-bg: #fef3c7;
      --shadow: 0 16px 40px rgba(15,23,42,.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      background: radial-gradient(circle at top left, #ffffff 0%, var(--bg) 50%, #edf4ff 100%);
      color: var(--text);
    }}
    .wrap {{ max-width: 1240px; margin: 0 auto; padding: 32px 24px 56px; }}
    .hero {{
      display: grid; gap: 20px;
      grid-template-columns: 1.6fr 1fr;
      align-items: stretch;
      margin-bottom: 22px;
    }}
    .hero-left, .hero-right, .section, .card, .stat {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }}
    .hero-left {{ padding: 28px 28px 24px; }}
    .hero-right {{ padding: 22px; }}
    .eyebrow {{
      display: inline-flex; align-items: center; gap: 8px;
      padding: 8px 12px; border-radius: 999px;
      background: var(--blue-bg); color: var(--blue); font-size: 13px; font-weight: 700;
    }}
    h1 {{ margin: 14px 0 10px; font-size: 36px; line-height: 1.12; letter-spacing: -.02em; }}
    .lead {{ font-size: 18px; line-height: 1.7; color: var(--muted); margin: 0; }}
    .meta {{ display:flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; color: var(--muted-2); font-size: 13px; }}
    .meta span {{ padding: 7px 10px; border-radius: 999px; background: rgba(255,255,255,.75); border: 1px solid var(--line); }}
    .stat-grid {{ display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
    .stat {{ background: var(--panel-strong); padding: 16px; }}
    .stat .num {{ font-size: 28px; font-weight: 800; margin-bottom: 4px; }}
    .stat .label {{ color: var(--muted-2); font-size: 13px; }}
    .section {{ padding: 18px 20px; margin-top: 18px; }}
    .section-head {{ display:flex; align-items:center; justify-content: space-between; gap: 12px; margin-bottom: 14px; }}
    .section h2 {{ margin: 0; font-size: 22px; }}
    .section p.sub {{ margin: 4px 0 0; color: var(--muted); font-size: 14px; line-height: 1.6; }}
    .chips {{ display:flex; flex-wrap: wrap; gap: 8px; }}
    .pill {{
      display:inline-flex; align-items:center; gap: 8px;
      padding: 8px 12px; border-radius: 999px; border: 1px solid var(--line);
      background: #fff; color: var(--text); font-size: 13px; font-weight: 600;
    }}
    .pill-blue {{ background: var(--blue-bg); color: #1e3a8a; }}
    .pill-green {{ background: var(--green-bg); color: #166534; }}
    .pill-amber {{ background: var(--amber-bg); color: #92400e; }}
    .cards {{ display:grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }}
    .card {{ background: var(--panel-strong); padding: 18px; display:flex; flex-direction: column; gap: 12px; }}
    .card-top {{ display:flex; align-items:flex-start; justify-content: space-between; gap: 12px; }}
    .score {{
      min-width: 52px; height: 52px; border-radius: 16px;
      display:flex; align-items:center; justify-content:center;
      font-size: 22px; font-weight: 900; background: var(--amber-bg); color: var(--amber);
    }}
    .rank {{ font-size: 12px; color: var(--muted-2); font-weight: 700; text-transform: uppercase; letter-spacing: .08em; }}
    .title {{ font-size: 18px; line-height: 1.4; font-weight: 800; margin: 0; }}
    .source {{ color: var(--muted); font-size: 13px; display:flex; flex-wrap: wrap; gap: 8px; align-items:center; }}
    .reason, .signal, .action {{
      border-radius: 16px; padding: 12px 14px; line-height: 1.65; font-size: 14px;
    }}
    .reason {{ background: #f8fafc; border: 1px solid #e2e8f0; color: #334155; }}
    .signal {{ background: #eff6ff; border: 1px solid #bfdbfe; color: #1e3a8a; }}
    .action {{ background: #ecfdf5; border: 1px solid #bbf7d0; color: #166534; }}
    .summary-box {{
      background: #fff7ed;
      border: 1px solid #fed7aa;
      color: #9a3412;
      border-radius: 16px;
      padding: 12px 14px;
      line-height: 1.65;
      font-size: 14px;
    }}
    .report-detail {{
      border: 1px solid #dbe5f4;
      border-radius: 16px;
      background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
      overflow: hidden;
    }}
    .report-detail summary {{
      list-style: none;
      cursor: pointer;
      padding: 12px 14px;
      font-weight: 800;
      color: var(--blue);
      background: rgba(29,78,216,.04);
    }}
    .report-detail summary::-webkit-details-marker {{
      display: none;
    }}
    .detail-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      padding: 14px;
    }}
    .detail-panel {{
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 14px;
      padding: 14px;
      box-shadow: 0 8px 20px rgba(15,23,42,.04);
    }}
    .detail-accent {{
      background: linear-gradient(180deg, #eff6ff 0%, #ffffff 100%);
      border-color: #bfdbfe;
    }}
    .detail-kicker {{
      font-size: 12px;
      letter-spacing: .08em;
      text-transform: uppercase;
      color: var(--muted-2);
      font-weight: 800;
      margin-bottom: 8px;
    }}
    .detail-title {{
      font-size: 18px;
      font-weight: 900;
      line-height: 1.35;
      margin-bottom: 8px;
    }}
    .detail-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 12px;
      font-size: 12px;
      color: var(--muted-2);
    }}
    .detail-meta span {{
      padding: 6px 10px;
      border-radius: 999px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
    }}
    .detail-copy, .detail-bullet {{
      font-size: 14px;
      line-height: 1.7;
      color: #334155;
      margin: 0 0 10px;
    }}
    .detail-bullet:last-child {{
      margin-bottom: 0;
    }}
    .detail-foot {{
      display: flex;
      gap: 10px;
      align-items: center;
      padding: 0 14px 14px;
      color: var(--muted-2);
      font-size: 13px;
    }}
    .detail-foot a {{
      color: var(--blue);
      font-weight: 800;
      text-decoration: none;
    }}
    .links a {{
      display:inline-flex; align-items:center; gap: 8px; text-decoration:none;
      color: var(--blue); font-weight: 700; font-size: 14px;
      padding: 8px 12px; border-radius: 12px; background: rgba(29,78,216,.06);
    }}
    .feedback {{
      display:flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      justify-content: space-between;
      border-top: 1px solid rgba(181,61,42,.12);
      padding-top: 12px;
      margin-top: 4px;
    }}
    .feedback-actions {{
      display:flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .feedback a {{
      display:inline-flex;
      align-items:center;
      gap: 6px;
      text-decoration:none;
      font-weight: 800;
      font-size: 13px;
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid rgba(181,61,42,.22);
      background: #fffaf3;
      color: var(--ink-dp);
    }}
    .feedback a.like {{
      background: #edf7ef;
      border-color: rgba(37, 99, 72, .22);
      color: #166534;
    }}
    .feedback a.dislike {{
      background: #fdf2f2;
      border-color: rgba(185, 28, 28, .22);
      color: #b91c1c;
    }}
    .feedback a.is-selected {{
      box-shadow: 0 8px 20px rgba(84, 60, 39, .12);
      transform: translateY(-1px);
    }}
    .feedback a.like.is-selected {{
      background: #166534;
      border-color: #166534;
      color: #fff;
    }}
    .feedback a.dislike.is-selected {{
      background: #b91c1c;
      border-color: #b91c1c;
      color: #fff;
    }}
    .feedback a.is-pending {{
      opacity: .64;
      pointer-events: none;
    }}
    .feedback-status {{
      font-size: 12px;
      color: var(--muted-2);
    }}
    .footer {{
      margin-top: 18px; padding: 14px 18px; color: var(--muted-2); font-size: 13px;
      text-align: center;
    }}
    .muted {{ color: var(--muted-2); }}
    .empty {{
      padding: 22px; border: 1px dashed #cbd5e1; border-radius: 18px; color: var(--muted);
      background: rgba(255,255,255,.65);
    }}
    @media (max-width: 1100px) {{
      .hero, .cards {{ grid-template-columns: 1fr; }}
      .detail-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div class="hero-left">
        <div class="eyebrow">Strategic Signal Scanner · High-signal report</div>
        <h1>{_escape(f"今日高信号报告 · {report_date}")}</h1>
        <p class="lead">{_escape(lead)}</p>
        <div class="meta">
          <span>共扫描 {count} 条</span>
          <span>高信号 {high_signal_count} 条</span>
          <span>最高分 {highest_score}/5</span>
          <span>来源数 {len(sources)}</span>
          <span>仅保留近 {max_age_days} 天</span>
          {f'<span>已隐藏 {hidden_old_count} 条过旧内容</span>' if hidden_old_count else ''}
        </div>
      </div>
      <div class="hero-right">
        <div class="stat-grid">
          <div class="stat">
            <div class="num">{high_signal_count}</div>
            <div class="label">高信号条目</div>
          </div>
          <div class="stat">
            <div class="num">{highest_score}</div>
            <div class="label">最高评分</div>
          </div>
          <div class="stat">
            <div class="num">{len(sources)}</div>
            <div class="label">命中来源</div>
          </div>
          <div class="stat">
            <div class="num">{count}</div>
            <div class="label">总扫描数</div>
          </div>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-head">
        <div>
          <h2>信号分布</h2>
          <p class="sub">按来源和内容类型汇总本期信号。</p>
        </div>
      </div>
      <div class="chips" style="margin-bottom: 10px;">{source_badges}</div>
      <div class="chips">{type_badges}</div>
    </div>

    <div class="section">
      <div class="section-head">
        <div>
          <h2>本期重点</h2>
          <p class="sub">按相关性从高到低排列，只看近 {max_age_days} 天内的内容。</p>
        </div>
      </div>
      {cards if items else f'<div class="empty">本期没有近 {max_age_days} 天内、且达到 3 分以上的高信号内容。</div>'}
    </div>

    <div class="footer">报告来源：{_escape(str(payload.get("source_file") or scored_path.name))} · 生成时间：{_escape(str(payload.get("scored_at") or ""))} · 已过滤近 {max_age_days} 天外的内容</div>
  </div>
  <script>
    document.addEventListener('click', async function (event) {{
      const target = event.target.closest('[data-feedback-vote]');
      if (!target) return;
      event.preventDefault();

      const feedback = target.closest('.feedback');
      const status = feedback ? feedback.querySelector('.feedback-status') : null;
      const actions = feedback ? feedback.querySelectorAll('[data-feedback-vote]') : [];
      const vote = target.getAttribute('data-feedback-vote');

      actions.forEach(function (item) {{
        item.classList.remove('is-selected');
        item.classList.add('is-pending');
      }});
      if (status) status.textContent = '正在记录反馈...';

      try {{
        const response = await fetch(target.href, {{ method: 'GET', mode: 'cors', credentials: 'omit' }});
        if (!response.ok) throw new Error('feedback request failed');
        actions.forEach(function (item) {{
          item.classList.remove('is-pending');
        }});
        target.classList.add('is-selected');
        if (status) {{
          status.textContent = vote === 'like'
            ? '已记录：这条对你有用。下一次 report 会参考这个判断。'
            : '已记录：这条不相关。下一次会降低类似内容权重。';
        }}
      }} catch (error) {{
        actions.forEach(function (item) {{
          item.classList.remove('is-pending');
        }});
        if (status) status.textContent = '这次没有记录成功，可以稍后再点一次。';
      }}
    }});
  </script>
</body>
</html>
"""


def _render_item_card(
    item: dict[str, Any],
    rank: int,
    report_date: str,
    feedback_state: FeedbackState,
    feedback_base_url: str,
    feedback_token: str,
) -> str:
    analysis = _analysis(item)
    score = int(analysis.get("relevance_score", 0))
    score_class = "pill-amber" if score >= 5 else "pill-blue" if score >= 4 else "pill-green"
    signal_type = str(analysis.get("signal_type", ""))
    source = str(item.get("source") or analysis.get("source") or "未知")
    title = str(item.get("title") or analysis.get("title") or "未命名")
    url = str(item.get("url") or analysis.get("url") or "#")
    reason = str(analysis.get("relevance_reason") or "")
    signal = str(analysis.get("key_signal") or "")
    action = str(analysis.get("rosy_action_hint") or "")
    summary = str(analysis.get("summary_zh") or "")
    published = str(item.get("published") or item.get("date") or analysis.get("date") or "")
    age_label = _age_label(published)
    feedback_patch = apply_feedback_adjustment(item, feedback_state)
    feedback_status = str(feedback_patch.get("feedback_status") or "neutral")
    feedback_bar = _render_feedback_bar(item, feedback_base_url, feedback_token, feedback_status, published, report_date)

    action_html = f'<div class="action"><strong>建议动作：</strong>{_escape(action)}</div>' if action else ""
    summary_html = f'<div class="summary-box"><strong>一句话摘要：</strong>{_escape(summary)}</div>' if summary else ""
    detail_html = _render_item_detail(item, rank)

    return f"""
      <div class="card">
        <div class="card-top">
          <div>
            <div class="rank">Rank #{rank}</div>
            <h3 class="title">{_escape(title)}</h3>
            <div class="source">
              <span>{_escape(source)}</span>
              {f'<span>· {_escape(published)}</span>' if published else ''}
              {f'<span>· {_escape(age_label)}</span>' if age_label else ''}
              <span class="pill {score_class}">{score}/5 · {_escape(signal_type or '未知')}</span>
            </div>
          </div>
          <div class="score">{score}</div>
        </div>
        <div class="reason"><strong>为什么相关：</strong>{_escape(reason)}</div>
        <div class="signal"><strong>核心信号：</strong>{_escape(signal)}</div>
        {summary_html}
        {action_html}
        <details class="report-detail">
          <summary>打开 Report · 查看与我方业务相关性</summary>
          {detail_html}
        </details>
        {feedback_bar}
        <div class="links"><a href="{_escape(url)}" target="_blank" rel="noreferrer">打开原文</a></div>
      </div>
    """


def _render_item_detail(item: dict[str, Any], rank: int) -> str:
    analysis = _analysis(item)
    score = int(analysis.get("relevance_score", 0))
    source = str(item.get("source") or analysis.get("source") or "未知")
    title = str(item.get("title") or analysis.get("title") or "未命名")
    url = str(item.get("url") or analysis.get("url") or "#")
    reason = str(analysis.get("relevance_reason") or "")
    signal = str(analysis.get("key_signal") or "")
    action = str(analysis.get("rosy_action_hint") or "")
    summary = str(analysis.get("summary_zh") or "")
    signal_type = str(analysis.get("signal_type") or "")
    published = str(item.get("published") or item.get("date") or analysis.get("date") or "")

    return f"""
          <div class="detail-grid">
            <div class="detail-panel">
              <div class="detail-kicker">它在说什么</div>
              <div class="detail-title">{_escape(title)}</div>
              <div class="detail-meta">
                <span>{_escape(source)}</span>
                {f'<span>{_escape(published)}</span>' if published else ''}
                <span>{score}/5</span>
                <span>{_escape(signal_type or '未知')}</span>
              </div>
              <p class="detail-copy">{_escape(summary or signal or reason)}</p>
            </div>
            <div class="detail-panel detail-accent">
              <div class="detail-kicker">与业务相关性</div>
              <div class="detail-bullet"><strong>与业务相关性：</strong>{_escape(reason)}</div>
              <div class="detail-bullet"><strong>最核心的变化：</strong>{_escape(signal)}</div>
              {f'<div class="detail-bullet"><strong>建议动作：</strong>{_escape(action)}</div>' if action else ''}
              <div class="detail-bullet muted">点击右下角「打开原文」可以回到来源；这个展开区是给你快速判断“值不值得继续看”的。</div>
            </div>
          </div>
          <div class="detail-foot">
            <a href="{_escape(url)}" target="_blank" rel="noreferrer">打开原文</a>
            <span>·</span>
            <span>Rank #{rank}</span>
          </div>
    """


def _render_feedback_bar(
    item: dict[str, Any],
    feedback_base_url: str,
    feedback_token: str,
    feedback_status: str,
    published: str,
    report_date: str,
) -> str:
    if not feedback_base_url:
        return ""

    title = str(item.get("title") or item.get("analysis", {}).get("title") or "未命名")
    source = str(item.get("source") or item.get("analysis", {}).get("source") or "未知")
    url = str(item.get("url") or item.get("analysis", {}).get("url") or "")
    item_id = str(item.get("feedback_id") or feedback_identity(item))
    base_params = {
        "item_id": item_id,
        "title": title,
        "source": source,
        "url": url,
        "published": published,
        "report_date": report_date,
        "return_to": "",
    }
    if feedback_token:
        base_params["token"] = feedback_token
    like_url = f"{feedback_base_url}/feedback?{urlencode({**base_params, 'vote': 'like'})}"
    dislike_url = f"{feedback_base_url}/feedback?{urlencode({**base_params, 'vote': 'dislike'})}"

    status_text = {
        "liked": "你已经标记为喜欢",
        "source-liked": "这个来源之前被你多次喜欢",
        "disliked": "你已经标记为不相关",
        "source-disliked": "这个来源之前被你多次标记不相关",
    }.get(feedback_status, "可以给这条信号一个反馈，帮助下次更准。")

    return f"""
      <div class="feedback">
        <div class="feedback-actions">
          <a class="like" href="{_escape(like_url)}" data-feedback-vote="like" aria-label="标记这条信号有用">↑ 有用</a>
          <a class="dislike" href="{_escape(dislike_url)}" data-feedback-vote="dislike" aria-label="标记这条信号不相关">↓ 不相关</a>
        </div>
        <div class="feedback-status">{_escape(status_text)}</div>
      </div>
    """


def _lead_sentence(items: list[dict[str, Any]], max_age_days: int) -> str:
    if not items:
        return f"本期没有近 {max_age_days} 天内足够高信号的内容。"
    top = items[0]
    analysis = _analysis(top)
    source = str(top.get("source") or analysis.get("source") or "未知来源")
    signal = str(analysis.get("key_signal") or analysis.get("summary_zh") or "暂无摘要")
    return f"本期最值得看的内容来自 {source}，核心信号是：{signal}"


def _parse_report_datetime(report_date: str) -> datetime:
    try:
        return datetime.strptime(report_date, "%Y-%m-%d").replace(tzinfo=LOCAL_TZ)
    except ValueError:
        return datetime.now(LOCAL_TZ)


def _parse_datetime_text(raw: str) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00") if text.endswith("Z") else text
    for candidate in (normalized, normalized.replace(" ", "T")):
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=LOCAL_TZ)
            return parsed.astimezone(LOCAL_TZ)
        except ValueError:
            continue
    return None


def _item_datetime(item: dict[str, Any]) -> datetime | None:
    analysis = _analysis(item)
    for raw in (
        item.get("published"),
        item.get("date"),
        analysis.get("date"),
    ):
        parsed = _parse_datetime_text(str(raw or ""))
        if parsed is not None:
            return parsed
    return None


def _filter_recent_items(
    items: list[dict[str, Any]],
    report_dt: datetime,
    max_age_days: int,
) -> tuple[list[dict[str, Any]], int]:
    cutoff = report_dt - timedelta(days=max_age_days)
    fresh_items: list[dict[str, Any]] = []
    hidden_old_count = 0
    for item in items:
        dt = _item_datetime(item)
        if dt is not None and dt < cutoff:
            hidden_old_count += 1
            continue
        fresh_items.append(item)
    return fresh_items, hidden_old_count


def _sort_item_key(item: dict[str, Any]) -> tuple[int, float]:
    analysis = _analysis(item)
    score = int(analysis.get("relevance_score", 0))
    dt = _item_datetime(item)
    timestamp = dt.timestamp() if dt is not None else float("-inf")
    return score, timestamp


def _age_label(published: str) -> str:
    dt = _parse_datetime_text(published)
    if dt is None:
        return ""
    now = datetime.now(LOCAL_TZ)
    days = max(0, (now.date() - dt.date()).days)
    if days <= 0:
        return "今天"
    if days == 1:
        return "1天前"
    return f"{days}天前"


def _ordered_unique(values: list[str]) -> list[str]:
    seen = OrderedDict()
    for value in values:
        if value and value not in seen:
            seen[value] = None
    return list(seen.keys())


def _escape(text: str) -> str:
    return html.escape(text, quote=True)


def _apply_long_table_theme(html_text: str) -> str:
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,600;12..96,700;12..96,800&family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600;1,9..144,400;1,9..144,500;1,9..144,600&display=swap');
    :root {
      --paper: #FAF1E2;
      --paper-d: #F2E5CF;
      --paper-vd: #E8D7B6;
      --ink: #B53D2A;
      --ink-dp: #8E2D1F;
      --line: rgba(181, 61, 42, .18);
      --bg: #0a0a0a;
      --panel: rgba(255, 251, 244, .92);
      --panel-strong: #fffaf2;
      --text: #8f3c29;
      --muted: #9c5d4a;
      --muted-2: #a77563;
      --shadow: 0 18px 42px rgba(142,45,31,.07);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: 'Fraunces', Georgia, serif;
      color: var(--text);
      background: #0a0a0a;
      overflow-x: hidden;
    }
    body::before {
      content: '';
      position: fixed;
      inset: 0;
      pointer-events: none;
      opacity: 0.09;
      background-image: radial-gradient(circle at 1px 1px, rgba(181,61,42,0.55) 0.5px, transparent 1px);
      background-size: 4px 4px;
      z-index: 0;
    }
    .wrap {
      position: relative;
      z-index: 1;
      max-width: 1280px;
      margin: 0 auto;
      padding: 36px 24px 56px;
    }
    .hero {
      display: grid;
      grid-template-columns: 1.6fr 1fr;
      gap: 20px;
      margin-bottom: 22px;
    }
    .hero-left, .hero-right, .section, .card, .stat {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(8px);
    }
    .hero-left { padding: 30px 30px 26px; }
    .hero-right { padding: 22px; }
    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid rgba(181,61,42,.36);
      background: var(--paper-vd);
      color: var(--ink-dp);
      font-family: 'Bricolage Grotesque', sans-serif;
      font-size: 13px;
      font-weight: 800;
      letter-spacing: .02em;
      text-transform: uppercase;
    }
    h1 {
      margin: 14px 0 10px;
      font-family: 'Bricolage Grotesque', sans-serif;
      font-size: 40px;
      line-height: 1.06;
      letter-spacing: -.03em;
      text-transform: uppercase;
    }
    .lead { font-size: 18px; line-height: 1.8; color: var(--muted); margin: 0; max-width: 980px; }
    .meta { display:flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; color: var(--muted-2); font-size: 13px; }
    .meta span { padding: 7px 10px; border-radius: 999px; background: rgba(255,250,242,.8); border: 1px solid rgba(181,61,42,.16); }
    .stat-grid { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .stat { background: var(--panel-strong); padding: 16px; }
    .stat .num { font-family: 'Bricolage Grotesque', sans-serif; font-size: 28px; font-weight: 800; margin-bottom: 4px; }
    .stat .label { color: var(--muted-2); font-size: 13px; }
    .section { padding: 18px 20px; margin-top: 18px; }
    .section-head { display:flex; align-items:flex-end; justify-content: space-between; gap: 12px; margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px solid rgba(181,61,42,.14); }
    .section h2 { margin: 0; font-family: 'Bricolage Grotesque', sans-serif; font-size: 24px; text-transform: uppercase; letter-spacing: -.02em; }
    .section p.sub { margin: 4px 0 0; color: var(--muted); font-size: 14px; line-height: 1.6; }
    .chips { display:flex; flex-wrap: wrap; gap: 8px; }
    .pill {
      display:inline-flex;
      align-items:center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid rgba(181,61,42,.26);
      background: #fffaf3;
      color: var(--ink-dp);
      font-size: 13px;
      font-weight: 700;
    }
    .pill-blue, .pill-green, .pill-amber { background: var(--paper-d); color: var(--ink-dp); }
    .cards { display:grid; grid-template-columns: 1fr; gap: 16px; }
    .card {
      background: linear-gradient(180deg, rgba(255,250,242,.98) 0%, rgba(248,239,225,.95) 100%);
      padding: 20px;
      display:flex;
      flex-direction: column;
      gap: 12px;
    }
    .card-top { display:flex; align-items:flex-start; justify-content: space-between; gap: 12px; padding-bottom: 12px; border-bottom: 1px solid rgba(181,61,42,.16); }
    .score {
      min-width: 56px;
      height: 56px;
      border-radius: 18px;
      display:flex;
      align-items:center;
      justify-content:center;
      font-family: 'Bricolage Grotesque', sans-serif;
      font-size: 22px;
      font-weight: 900;
      background: var(--paper-vd);
      color: var(--ink-dp);
      border: 1px solid rgba(181,61,42,.22);
    }
    .rank { font-family: 'Bricolage Grotesque', sans-serif; font-size: 12px; color: var(--muted-2); font-weight: 800; text-transform: uppercase; letter-spacing: .08em; }
    .title { font-family: 'Bricolage Grotesque', sans-serif; font-size: 20px; line-height: 1.35; font-weight: 800; margin: 0; letter-spacing: -.02em; }
    .source { color: var(--muted); font-size: 13px; display:flex; flex-wrap: wrap; gap: 8px; align-items:center; margin-top: 8px; }
    .reason, .signal, .action {
      border-radius: 16px;
      padding: 12px 14px;
      line-height: 1.7;
      font-size: 14px;
      background: rgba(255,255,255,.55);
      border: 1px solid rgba(181,61,42,.16);
      color: #8f3c29;
    }
    .summary-box {
      background: rgba(232,215,182,.24);
      border: 1px solid rgba(181,61,42,.18);
      color: #8f3c29;
      border-radius: 16px;
      padding: 12px 14px;
      line-height: 1.7;
      font-size: 14px;
    }
    .report-detail { border: 1px solid rgba(181,61,42,.22); border-radius: 16px; background: linear-gradient(180deg, rgba(255,250,242,.95) 0%, rgba(242,229,207,.65) 100%); overflow: hidden; }
    .report-detail summary {
      list-style: none;
      cursor: pointer;
      padding: 12px 14px;
      font-family: 'Bricolage Grotesque', sans-serif;
      font-weight: 800;
      color: var(--ink-dp);
      background: rgba(181,61,42,.05);
    }
    .report-detail summary::-webkit-details-marker { display: none; }
    .detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; padding: 14px; }
    .detail-panel {
      background: rgba(255,250,242,.88);
      border: 1px solid rgba(181,61,42,.16);
      border-radius: 14px;
      padding: 14px;
      box-shadow: 0 8px 20px rgba(142,45,31,.04);
    }
    .detail-accent { background: linear-gradient(180deg, rgba(232,215,182,.35) 0%, rgba(255,250,242,.92) 100%); border-color: rgba(181,61,42,.22); }
    .detail-kicker { font-family: 'Bricolage Grotesque', sans-serif; font-size: 12px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted-2); font-weight: 800; margin-bottom: 8px; }
    .detail-title { font-family: 'Bricolage Grotesque', sans-serif; font-size: 18px; font-weight: 900; line-height: 1.35; margin-bottom: 8px; }
    .detail-meta { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; font-size: 12px; color: var(--muted-2); }
    .detail-meta span { padding: 6px 10px; border-radius: 999px; background: rgba(255,250,242,.86); border: 1px solid rgba(181,61,42,.14); }
    .detail-copy, .detail-bullet { font-size: 14px; line-height: 1.75; color: #7d3827; margin: 0 0 10px; }
    .detail-bullet:last-child { margin-bottom: 0; }
    .detail-foot { display: flex; gap: 10px; align-items: center; padding: 0 14px 14px; color: var(--muted-2); font-size: 13px; }
    .detail-foot a { color: var(--ink-dp); font-weight: 800; text-decoration: none; }
    .links a { display:inline-flex; align-items:center; gap: 8px; text-decoration:none; color: var(--ink-dp); font-weight: 800; font-size: 14px; padding: 10px 14px; border-radius: 999px; background: rgba(181,61,42,.05); border: 1px solid rgba(181,61,42,.22); }
    .footer { margin-top: 18px; padding: 14px 18px; color: var(--muted-2); font-size: 13px; text-align: center; font-family: 'Fraunces', Georgia, serif; font-style: italic; }
    .muted { color: var(--muted-2); }
    .empty { padding: 22px; border: 1px dashed rgba(181,61,42,.30); border-radius: 18px; color: var(--muted); background: rgba(255,250,242,.7); }
    @media (max-width: 1100px) {
      .hero, .detail-grid { grid-template-columns: 1fr; }
    }
    </style>
    """
    return re.sub(r"<style>.*?</style>", f"<style>\n{css.strip()}\n  </style>", html_text, count=1, flags=re.S)


if __name__ == "__main__":
    raise SystemExit(main())

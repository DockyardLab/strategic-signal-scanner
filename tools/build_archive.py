#!/usr/bin/env python3
"""Build a browsable archive index for daily signal reports."""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

LOCAL_TZ = timezone(timedelta(hours=8))
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
DATE_RE = re.compile(r"^scored_(\d{4}-\d{2}-\d{2})\.json$")
FEEDX_RE = re.compile(r"^scored_feedx_(\d{4}-\d{2}-\d{2})\.json$")


@dataclass
class DayEntry:
    date: str
    report_path: Path | None
    scored_path: Path
    total_count: int
    high_signal_count: int
    highest_score: int
    top_sources: list[str]
    top_types: list[str]
    title: str
    kind: str = "daily"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build HTML archive index from scored artifacts.")
    parser.add_argument(
        "--artifact-dir",
        type=str,
        default="artifacts/rss",
        help="Directory containing scored_*.json and where archive outputs should be written.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Output HTML path. Defaults to artifacts/rss/archive_index.html.",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=365,
        help="Only include reports newer than this many days.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact_dir = _resolve_artifact_dir(args.artifact_dir)
    output = _resolve_output(args.output, artifact_dir)
    entries = _collect_entries(max(0, args.max_age_days), artifact_dir)
    html_text = _render_archive(entries, max(0, args.max_age_days))
    html_text = _apply_long_table_theme(html_text)
    output.write_text(html_text, encoding="utf-8")
    print(f"Archive saved: {output}")
    return 0


def _resolve_artifact_dir(path: str) -> Path:
    out = Path(path)
    return out if out.is_absolute() else (REPO_DIR / out)


def _resolve_output(output: str, artifact_dir: Path) -> Path:
    if output:
        out = Path(output)
        return out if out.is_absolute() else (REPO_DIR / out)
    return artifact_dir / "archive_index.html"


def _collect_entries(max_age_days: int, artifact_dir: Path) -> list[DayEntry]:
    scored_files = sorted(artifact_dir.glob("scored_*.json"))
    cutoff = datetime.now(LOCAL_TZ).date() - timedelta(days=max_age_days)
    entries: list[DayEntry] = []

    for scored_path in scored_files:
        daily_match = DATE_RE.match(scored_path.name)
        special_match = FEEDX_RE.match(scored_path.name)
        if not daily_match and not special_match:
            continue
        kind = "feedx" if special_match else "daily"
        match = special_match or daily_match
        date = match.group(1)
        dt = _parse_date(date)
        if dt is None or dt.date() < cutoff:
            continue

        report_path = _ensure_report(scored_path, artifact_dir)
        payload = json.loads(scored_path.read_text(encoding="utf-8"))
        items = payload.get("items") or []
        high_items = payload.get("high_signal_items") or _high_signal_items(items)
        total_count = int(payload.get("count") or len(items))
        high_signal_count = int(payload.get("high_signal_count") or len(high_items))
        highest_score = max((_score_of(item) for item in high_items), default=0)
        source_counts = Counter(str(item.get("source", "Unknown")) for item in high_items)
        type_counts = Counter(str(_analysis(item).get("signal_type", "Unknown")) for item in high_items)

        entries.append(
            DayEntry(
                date=date,
                report_path=report_path if report_path.exists() else None,
                scored_path=scored_path,
                total_count=total_count,
                high_signal_count=high_signal_count,
                highest_score=highest_score,
                top_sources=[name for name, _ in source_counts.most_common(3)],
                top_types=[name for name, _ in type_counts.most_common(3)],
                title=_entry_title(payload, kind, date),
                kind=kind,
            )
        )

    entries.sort(key=lambda e: e.date, reverse=True)
    return entries


def _ensure_report(scored_path: Path, artifact_dir: Path) -> Path:
    report_path = artifact_dir / scored_path.name.replace("scored_", "report_", 1).replace(".json", ".html")
    if report_path.exists() and report_path.stat().st_mtime >= scored_path.stat().st_mtime:
        return report_path

    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "build_report.py"),
        "--scored-file",
        str(scored_path),
        "--output",
        str(report_path),
        "--max-age-days",
        "365",
    ]
    subprocess.run(cmd, check=True)
    return report_path


def _entry_title(payload: dict[str, Any], kind: str, date: str) -> str:
    if kind == "feedx":
        return "Follow Builders · FeedX"
    source_file = str(payload.get("source_file") or "").strip()
    if source_file:
        return source_file.replace("scored_", "").replace("raw_", "")
    return f"{date} report"


def _render_archive(entries: list[DayEntry], max_age_days: int) -> str:
    now = datetime.now(LOCAL_TZ)
    daily_entries = [entry for entry in entries if entry.kind == "daily"]
    special_entries = [entry for entry in entries if entry.kind != "daily"]
    month_groups = _group_daily_entries_by_month(daily_entries)

    latest_date = daily_entries[0].date if daily_entries else (special_entries[0].date if special_entries else "暂无")
    total_days = len(daily_entries)
    total_signals = sum(entry.high_signal_count for entry in entries)
    source_names = sorted({name for entry in entries for name in entry.top_sources})
    source_chips = "".join(f'<span class="chip chip-blue">{_escape(name)}</span>' for name in source_names[:16]) or '<span class="chip">暂无</span>'

    recent_entries = daily_entries[:3]
    recent_cards = []
    for index, entry in enumerate(recent_entries):
        label = "最近一次" if index == 0 else ""
        recent_cards.append(_render_day_card(label, entry))

    feedx_cards = "\n".join(_render_day_card("FeedX", entry) for entry in special_entries)
    month_nav = "\n".join(
        f'<a class="chip chip-green" href="#month-{_escape(month_key)}">{_escape(_month_label(month_key))} · {len(month_entries)}天</a>'
        for month_key, month_entries in month_groups
    )
    month_sections = "\n".join(_render_month_section(month_key, month_entries) for month_key, month_entries in month_groups)
    if not month_sections:
        month_sections = '<div class="empty">暂时没有可展示的归档页面。</div>'

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Strategic Signal Archive</title>
  <style>
    :root {{
      --bg: #f5efdf;
      --panel: rgba(255, 250, 241, .94);
      --panel-strong: #fffaf3;
      --line: #e8dcc8;
      --text: #2f3a3f;
      --muted: #66717a;
      --muted-2: #8a7f71;
      --blue: #4f6f8f;
      --blue-bg: #e6eff7;
      --green: #5f7f66;
      --green-bg: #edf5ea;
      --amber: #9a7b47;
      --amber-bg: #fbf1df;
      --shadow: 0 16px 36px rgba(98,82,57,.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
      background: radial-gradient(circle at top left, #fffdf7 0%, var(--bg) 48%, #efe5d4 100%);
      color: var(--text);
    }}
    .wrap {{ max-width: 1280px; margin: 0 auto; padding: 34px 24px 56px; }}
    .hero, .section, .day-card, .empty {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(8px);
    }}
    .hero {{ padding: 28px; margin-bottom: 20px; }}
    .eyebrow {{ display:inline-flex; align-items:center; gap:8px; padding:8px 12px; border-radius:999px; background:var(--blue-bg); color:var(--blue); font-size:13px; font-weight:800; }}
    h1 {{ margin: 14px 0 10px; font-size: 38px; line-height: 1.1; letter-spacing: -.02em; }}
    .lead {{ font-size: 18px; line-height: 1.7; color: var(--muted); margin: 0; max-width: 960px; }}
    .meta {{ display:flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; color: var(--muted-2); font-size: 13px; }}
    .meta span {{ padding: 7px 10px; border-radius: 999px; background: rgba(255,255,255,.72); border: 1px solid var(--line); }}
    .section {{ padding: 18px 20px; margin-top: 18px; }}
    .section-head {{ display:flex; justify-content: space-between; gap: 12px; align-items:flex-end; margin-bottom: 14px; }}
    .section h2 {{ margin: 0; font-size: 22px; }}
    .section p.sub {{ margin: 4px 0 0; color: var(--muted); font-size: 14px; line-height: 1.6; }}
    .chip-row {{ display:flex; flex-wrap: wrap; gap: 8px; }}
    .chip {{ display:inline-flex; align-items:center; gap:8px; padding: 7px 10px; border-radius: 999px; border: 1px solid var(--line); background: #fff; color: var(--text); font-size: 12px; font-weight: 700; }}
    .chip-blue {{ background: var(--blue-bg); color: #425d79; }}
    .chip-green {{ background: var(--green-bg); color: #4d6f55; }}
    .chip-amber {{ background: var(--amber-bg); color: #8b6a34; }}
    .grid {{ display:grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }}
    .date-list {{ display:flex; flex-direction: column; gap: 10px; }}
    .date-row {{
      display: grid;
      grid-template-columns: 160px 1fr 120px;
      gap: 14px;
      align-items: center;
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid #e6d7c0;
      background: rgba(255,255,255,.72);
      text-decoration: none;
      color: inherit;
      transition: transform .15s ease, box-shadow .15s ease;
    }}
    .date-row:hover {{ transform: translateY(-1px); box-shadow: 0 12px 26px rgba(98,82,57,.10); }}
    .date-row.disabled {{ opacity: .55; pointer-events: none; }}
    .date-main {{ display:flex; flex-direction: column; gap: 4px; }}
    .date-main .date {{ font-size: 20px; font-weight: 900; }}
    .date-main .sub {{ color: var(--muted-2); font-size: 13px; }}
    .date-stats {{ display:flex; flex-wrap: wrap; gap: 8px; }}
    .date-stats .chip {{ background: #fff; }}
    .date-arrow {{ justify-self: end; color: var(--blue); font-weight: 800; font-size: 13px; }}
    .day-card {{ display:block; padding: 18px; text-decoration:none; color: inherit; transition: transform .15s ease, box-shadow .15s ease; background: var(--panel-strong); }}
    .day-card:hover {{ transform: translateY(-2px); box-shadow: 0 18px 42px rgba(98,82,57,.12); }}
    .day-card.disabled {{ opacity: .55; pointer-events: none; }}
    .day-card-top {{ display:flex; justify-content: space-between; align-items:flex-start; gap: 12px; }}
    .day-date {{ font-size: 22px; font-weight: 900; }}
    .day-age {{ margin-top: 4px; color: var(--muted-2); font-size: 13px; }}
    .day-score {{ min-width: 52px; height: 52px; border-radius: 16px; display:flex; align-items:center; justify-content:center; font-size: 22px; font-weight: 900; background: var(--amber-bg); color: var(--amber); }}
    .day-title {{ margin-top: 10px; font-size: 18px; font-weight: 800; }}
    .day-meta {{ margin-top: 8px; font-size: 13px; line-height: 1.6; color: var(--muted); }}
    .day-chip-row {{ display:flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }}
    .day-links {{ margin-top: 12px; padding-top: 12px; border-top: 1px solid #eadfcb; color: var(--blue); font-size: 13px; font-weight: 700; word-break: break-all; }}
    .empty {{ padding: 20px; border: 1px dashed #d7c7ad; color: var(--muted); }}
    .footer {{ margin-top: 18px; color: var(--muted-2); font-size: 13px; text-align: center; }}
    @media (max-width: 1100px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div class="eyebrow">Strategic Signal Archive · Daily browsing</div>
      <h1>信号归档首页</h1>
      <p class="lead">这里是每天的高信号归档：先看近三次抓取结果。每一天都是一份独立 report，可以直接点进去，再从 report 里继续查看与我方业务的相关性分析。</p>
      <div class="meta">
        <span>报告天数 {total_days}</span>
        <span>累计高信号 {total_signals}</span>
        <span>最新日期 {latest_date}</span>
        <span>仅展示近 {max_age_days} 天</span>
      </div>
    </div>

    <div class="section">
      <div class="section-head">
        <div>
          <h2>近三次</h2>
          <p class="sub">优先展示最近 3 份已有 report，按实际归档结果倒序排列。</p>
        </div>
      </div>
      {f'<div class="grid">{"".join(recent_cards)}</div>' if recent_cards else '<div class="empty">暂时没有可展示的归档页面。</div>'}
    </div>

    {f'''
    <div class="section">
      <div class="section-head">
        <div>
          <h2>Follow Builders · FeedX</h2>
          <p class="sub">builders 上游前沿探测器的日更专题，单独展示，方便和日常 report 分开看。</p>
        </div>
      </div>
      <div class="grid">{feedx_cards}</div>
    </div>
    ''' if special_entries else ''}

    <div class="section">
      <div class="section-head">
        <div>
          <h2>完整日期列表</h2>
          <p class="sub">按日期倒序排列，点击任意一天就能进入那天的 report。</p>
        </div>
      </div>
      <div class="chip-row">{month_nav or '<span class="chip">暂无月份分组</span>'}</div>
      <div style="height:14px"></div>
      {month_sections}
      <div style="height:16px"></div>
      <div class="chip-row">{source_chips}</div>
    </div>

    <div class="footer">Archive index · source files live in artifacts/rss · each day links to its corresponding report</div>
  </div>
</body>
</html>"""


def _group_daily_entries_by_month(entries: list[DayEntry]) -> list[tuple[str, list[DayEntry]]]:
    groups: list[tuple[str, list[DayEntry]]] = []
    current_month = ""
    current_entries: list[DayEntry] = []
    for entry in entries:
        month = entry.date[:7]
        if month != current_month:
            if current_entries:
                groups.append((current_month, current_entries))
            current_month = month
            current_entries = []
        current_entries.append(entry)
    if current_entries:
        groups.append((current_month, current_entries))
    return groups


def _month_label(month_key: str) -> str:
    try:
        dt = datetime.strptime(month_key, "%Y-%m")
    except ValueError:
        return month_key
    return f"{dt.year}年{dt.month}月"


def _render_month_section(month_key: str, entries: list[DayEntry]) -> str:
    label = _month_label(month_key)
    month_rows = "\n".join(_render_date_row(entry) for entry in entries)
    if not month_rows:
        month_rows = '<div class="empty">暂时没有可展示的归档页面。</div>'
    return f'''
    <div id="month-{_escape(month_key)}" style="margin-bottom: 16px; padding-top: 2px;">
      <div class="section-head" style="margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #eadfcb;">
        <div>
          <h2>{_escape(label)}</h2>
          <p class="sub">{len(entries)} 天 report，按日期倒序排列。</p>
        </div>
        <div class="chip chip-amber">{len(entries)} 天</div>
      </div>
      <div class="date-list">{month_rows}</div>
    </div>
    '''


def _render_day_card(label: str, entry: DayEntry) -> str:
    report_href = _rel_path(entry.report_path)
    scored_href = _rel_path(entry.scored_path)
    source_text = ", ".join(entry.top_sources[:3]) or "无"
    type_text = ", ".join(entry.top_types[:3]) or "无"
    age_text = "最新抓取" if label == "最近一次" else _age_label(_parse_date(entry.date) or datetime.now(LOCAL_TZ))
    return f"""
    <a class="day-card" href="{_escape(report_href)}">
      <div class="day-card-top">
        <div>
          <div class="day-date">{_escape(entry.title)}{(" · " + _escape(entry.date)) if entry.kind == "daily" else ""}</div>
          <div class="day-age">{_escape(age_text)}</div>
        </div>
        <div class="day-score">{entry.high_signal_count}</div>
      </div>
      <div class="day-title">{_escape(entry.title)}</div>
      <div class="day-meta">高信号 {entry.high_signal_count} · 总扫描 {entry.total_count} · 最高分 {entry.highest_score}/5</div>
      <div class="day-chip-row">
        <span class="chip chip-blue">来源: {_escape(source_text)}</span>
        <span class="chip chip-green">主题: {_escape(type_text)}</span>
      </div>
      <div class="day-links">查看日报 · {_escape(report_href)} · {_escape(scored_href)}</div>
    </a>
    """


def _render_empty_card(label: str, date: str) -> str:
    label_text = f"{_escape(label)} · " if label else ""
    return f"""
    <div class="day-card disabled">
      <div class="day-card-top">
        <div>
          <div class="day-date">{label_text}{_escape(date)}</div>
          <div class="day-age">暂无报告</div>
        </div>
        <div class="day-score">0</div>
      </div>
      <div class="day-title">暂无归档页面</div>
      <div class="day-meta">这一天还没有可展示的 scored/report 文件。</div>
      <div class="day-chip-row"><span class="chip">等待抓取</span></div>
    </div>
    """


def _render_date_row(entry: DayEntry) -> str:
    report_href = _rel_path(entry.report_path)
    scored_href = _rel_path(entry.scored_path)
    source_text = ", ".join(entry.top_sources[:2]) or "无"
    type_text = ", ".join(entry.top_types[:2]) or "无"
    label = _age_label(_parse_date(entry.date) or datetime.now(LOCAL_TZ))
    return f"""
    <a class="date-row" href="{_escape(report_href)}">
      <div class="date-main">
        <div class="date">{_escape(entry.date)}</div>
        <div class="sub">{_escape(label)} · 点击打开当天 report</div>
      </div>
      <div class="date-stats">
        <span class="chip chip-blue">高信号 {entry.high_signal_count}</span>
        <span class="chip chip-green">最高分 {entry.highest_score}/5</span>
        <span class="chip chip-amber">{_escape(source_text)}</span>
        <span class="chip">{_escape(type_text)}</span>
      </div>
      <div class="date-arrow">查看 · {_escape(scored_href)}</div>
    </a>
    """


def _high_signal_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in items if _score_of(item) >= 3]


def _score_of(item: dict[str, Any]) -> int:
    return int((_analysis(item).get("relevance_score", 0)))


def _analysis(item: dict[str, Any]) -> dict[str, Any]:
    analysis = item.get("analysis")
    return analysis if isinstance(analysis, dict) else {}


def _parse_date(date: str) -> datetime | None:
    try:
        return datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=LOCAL_TZ)
    except ValueError:
        return None


def _age_label(dt: datetime) -> str:
    days = max(0, (datetime.now(LOCAL_TZ).date() - dt.date()).days)
    if days <= 0:
        return "今天"
    if days == 1:
        return "1天前"
    return f"{days}天前"


def _escape(text: str) -> str:
    return html.escape(text, quote=True)


def _rel_path(path: Path | None) -> str:
    return path.name if path else ""


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
    .wrap { position: relative; z-index: 1; max-width: 1280px; margin: 0 auto; padding: 36px 24px 56px; }
    .hero, .section, .day-card, .empty {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(8px);
    }
    .hero { padding: 28px; margin-bottom: 20px; }
    .eyebrow {
      display:inline-flex; align-items:center; gap:8px;
      padding:8px 12px; border-radius:999px;
      border:1px solid rgba(181,61,42,.36);
      background: var(--paper-vd);
      color: var(--ink-dp);
      font-family: 'Bricolage Grotesque', sans-serif;
      font-size:13px; font-weight:800;
      letter-spacing:.02em; text-transform:uppercase;
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
    .meta { display:flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; color: var(--muted-2); font-size: 13px; }
    .meta span { padding: 7px 10px; border-radius: 999px; background: rgba(255,250,242,.8); border: 1px solid rgba(181,61,42,.16); }
    .section { padding: 18px 20px; margin-top: 18px; }
    .section-head { display:flex; justify-content: space-between; gap: 12px; align-items:flex-end; margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px solid rgba(181,61,42,.14); }
    .section h2 { margin: 0; font-family: 'Bricolage Grotesque', sans-serif; font-size: 24px; text-transform: uppercase; letter-spacing: -.02em; }
    .section p.sub { margin: 4px 0 0; color: var(--muted); font-size: 14px; line-height: 1.6; }
    .chip-row { display:flex; flex-wrap: wrap; gap: 8px; }
    .chip {
      display:inline-flex; align-items:center; gap:8px;
      padding: 7px 10px;
      border-radius: 999px;
      border: 1px solid rgba(181,61,42,.26);
      background: #fffaf3;
      color: var(--ink-dp);
      font-size: 12px;
      font-weight: 700;
    }
    .chip-blue, .chip-green, .chip-amber { background: var(--paper-d); color: var(--ink-dp); }
    .grid { display:grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
    .date-list { display:flex; flex-direction: column; gap: 10px; }
    .date-row {
      display: grid;
      grid-template-columns: 160px 1fr 120px;
      gap: 14px;
      align-items: center;
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid rgba(181,61,42,.18);
      background: rgba(255,250,242,.75);
      text-decoration: none;
      color: inherit;
      transition: transform .15s ease, box-shadow .15s ease;
    }
    .date-row:hover { transform: translateY(-1px); box-shadow: 0 12px 26px rgba(142,45,31,.10); }
    .date-row.disabled { opacity: .55; pointer-events: none; }
    .date-main { display:flex; flex-direction: column; gap: 4px; }
    .date-main .date { font-family: 'Bricolage Grotesque', sans-serif; font-size: 20px; font-weight: 900; letter-spacing: -.02em; }
    .date-main .sub { color: var(--muted-2); font-size: 13px; }
    .date-stats { display:flex; flex-wrap: wrap; gap: 8px; }
    .date-stats .chip { background: #fff; }
    .date-arrow { justify-self: end; color: var(--ink-dp); font-family: 'Bricolage Grotesque', sans-serif; font-weight: 800; font-size: 13px; }
    .day-card {
      display:block;
      padding: 18px;
      text-decoration:none;
      color: inherit;
      transition: transform .15s ease, box-shadow .15s ease;
      background: var(--panel-strong);
    }
    .day-card:hover { transform: translateY(-2px); box-shadow: 0 18px 42px rgba(142,45,31,.12); }
    .day-card.disabled { opacity: .55; pointer-events: none; }
    .day-card-top { display:flex; justify-content: space-between; align-items:flex-start; gap: 12px; }
    .day-date { font-family: 'Bricolage Grotesque', sans-serif; font-size: 22px; font-weight: 900; letter-spacing: -.02em; }
    .day-age { margin-top: 4px; color: var(--muted-2); font-size: 13px; }
    .day-score {
      min-width: 52px; height: 52px; border-radius: 16px;
      display:flex; align-items:center; justify-content:center;
      font-family: 'Bricolage Grotesque', sans-serif;
      font-size: 22px; font-weight: 900;
      background: var(--paper-vd); color: var(--ink-dp);
      border: 1px solid rgba(181,61,42,.22);
    }
    .day-title { margin-top: 10px; font-family: 'Bricolage Grotesque', sans-serif; font-size: 18px; font-weight: 800; letter-spacing: -.02em; }
    .day-meta { margin-top: 8px; font-size: 13px; line-height: 1.6; color: var(--muted); }
    .day-chip-row { display:flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
    .day-links { margin-top: 12px; padding-top: 12px; border-top: 1px solid rgba(181,61,42,.16); color: var(--ink-dp); font-size: 13px; font-weight: 700; word-break: break-all; }
    .empty { padding: 20px; border: 1px dashed rgba(181,61,42,.30); color: var(--muted); background: rgba(255,250,242,.7); }
    .footer { margin-top: 18px; color: var(--muted-2); font-size: 13px; text-align: center; font-family: 'Fraunces', Georgia, serif; font-style: italic; }
    @media (max-width: 1100px) { .grid { grid-template-columns: 1fr; } .date-row { grid-template-columns: 1fr; } }
    </style>
    """
    return re.sub(r"<style>.*?</style>", f"<style>\n{css.strip()}\n  </style>", html_text, count=1, flags=re.S)


if __name__ == "__main__":
    raise SystemExit(main())

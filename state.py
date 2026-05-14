"""Persistent capture state for seen URLs and source freshness."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

LOCAL_TZ = timezone(timedelta(hours=8))
DEFAULT_STATE_PATH = Path("artifacts/rss/state.json")
FALLBACK_STATE_PATH = Path("/private/tmp/strategy_agent_v1/artifacts/rss/state.json")


@dataclass
class CaptureState:
    seen_urls: dict[str, str] = field(default_factory=dict)
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)


def load_state(base_dir: Path | None = None) -> tuple[CaptureState, Path]:
    primary_path = _resolve_state_path(base_dir)
    for state_path in (primary_path, FALLBACK_STATE_PATH):
        if not state_path.exists():
            continue
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        seen_urls = payload.get("seen_urls") or {}
        sources = payload.get("sources") or {}
        if not isinstance(seen_urls, dict):
            seen_urls = {}
        if not isinstance(sources, dict):
            sources = {}
        return CaptureState(seen_urls=dict(seen_urls), sources=dict(sources)), state_path
    return CaptureState(), primary_path


def save_state(state: CaptureState, base_dir: Path | None = None) -> Path:
    payload = {
        "saved_at": datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M"),
        "seen_urls": state.seen_urls,
        "sources": state.sources,
    }
    for state_path in (_resolve_state_path(base_dir), FALLBACK_STATE_PATH):
        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return state_path
        except PermissionError:
            continue
    raise PermissionError("Unable to save capture state to primary or fallback locations.")


def source_is_fresh(source_state: dict[str, Any], refresh_hours: float, now: datetime | None = None) -> bool:
    last_success = str(source_state.get("last_success") or "").strip()
    if not last_success:
        return False
    parsed = _parse_timestamp(last_success)
    if parsed is None:
        return False
    now = now or datetime.now(LOCAL_TZ)
    delta = now - parsed
    return delta < timedelta(hours=refresh_hours)


def mark_source_success(
    state: CaptureState,
    source_key: str,
    source_name: str,
    feed_url: str,
    article_urls: list[str],
    latest_url: str = "",
    latest_published: str = "",
) -> None:
    now_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M")
    source_state = state.sources.setdefault(source_key, {})
    source_state["name"] = source_name
    source_state["feed_url"] = feed_url
    source_state["last_success"] = now_str
    source_state["article_urls"] = article_urls[:20]
    source_state["article_count"] = len([url for url in article_urls if url])
    if latest_url:
        source_state["latest_url"] = latest_url
    elif article_urls:
        source_state["latest_url"] = article_urls[0]
    if latest_published:
        source_state["latest_published"] = latest_published
    elif "latest_published" not in source_state:
        source_state["latest_published"] = ""
    for url in article_urls:
        if url:
            state.seen_urls[url] = now_str


def _resolve_state_path(base_dir: Path | None = None) -> Path:
    if base_dir is None:
        base_dir = Path.cwd()
    state_path = base_dir / DEFAULT_STATE_PATH
    return state_path


def _parse_timestamp(raw: str) -> datetime | None:
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return parsed.replace(tzinfo=LOCAL_TZ)

"""Persistent capture state for seen URLs and source freshness."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

LOCAL_TZ = timezone(timedelta(hours=8))
DEFAULT_STATE_PATH = Path("artifacts/rss/state.json")
FALLBACK_STATE_PATH = Path("/private/tmp/strategy_agent_v1/artifacts/rss/state.json")
_TRACKING_PARAMS = {"fbclid", "gclid", "igshid", "mc_cid", "mc_eid"}


@dataclass
class CaptureState:
    seen_urls: dict[str, str] = field(default_factory=dict)
    seen_title_hashes: dict[str, str] = field(default_factory=dict)
    seen_content_hashes: dict[str, str] = field(default_factory=dict)
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
        seen_title_hashes = payload.get("seen_title_hashes") or payload.get("seen_fingerprints") or {}
        seen_content_hashes = payload.get("seen_content_hashes") or {}
        sources = payload.get("sources") or {}
        if not isinstance(seen_urls, dict):
            seen_urls = {}
        if not isinstance(seen_title_hashes, dict):
            seen_title_hashes = {}
        if not isinstance(seen_content_hashes, dict):
            seen_content_hashes = {}
        if not isinstance(sources, dict):
            sources = {}
        return (
            CaptureState(
                seen_urls=dict(seen_urls),
                seen_title_hashes=dict(seen_title_hashes),
                seen_content_hashes=dict(seen_content_hashes),
                sources=dict(sources),
            ),
            state_path,
        )
    return CaptureState(), primary_path


def save_state(state: CaptureState, base_dir: Path | None = None) -> Path:
    payload = {
        "saved_at": datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M"),
        "seen_urls": state.seen_urls,
        "seen_title_hashes": state.seen_title_hashes,
        "seen_content_hashes": state.seen_content_hashes,
        "seen_fingerprints": state.seen_title_hashes,
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
            state.seen_urls[canonicalize_url(url)] = now_str


def remember_article(state: CaptureState, article: dict[str, Any], now_str: str | None = None) -> None:
    now_str = now_str or datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M")
    keys = article_dedupe_keys(article)
    if keys["url"]:
        state.seen_urls[keys["url"]] = now_str
    if keys["title_hash"]:
        state.seen_title_hashes[keys["title_hash"]] = now_str
    if keys["content_hash"]:
        state.seen_content_hashes[keys["content_hash"]] = now_str


def article_dedupe_keys(article: dict[str, Any]) -> dict[str, str]:
    title = _normalize_text(str(article.get("title", "")))
    source = _normalize_text(str(article.get("source", "")))
    published = _normalize_text(str(article.get("published", "")))
    content = _normalize_text(str(article.get("summary") or article.get("content") or ""))
    url = canonicalize_url(str(article.get("url", "")))

    title_basis = " | ".join(part for part in (source, title, published) if part)
    content_basis = " | ".join(part for part in (source, title, content[:500]) if part)
    return {
        "url": url,
        "title_hash": _hash_text(title_basis) if title_basis else "",
        "content_hash": _hash_text(content_basis) if content_basis else "",
    }


def canonicalize_url(raw_url: str) -> str:
    url = str(raw_url or "").strip()
    if not url:
        return ""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return url
    if not parsed.scheme or not parsed.netloc:
        return url
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in _TRACKING_PARAMS and not key.startswith("utm_")
    ]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(filtered_query, doseq=True), ""))


def _normalize_text(raw: str) -> str:
    return " ".join(raw.split()).strip().lower()


def _hash_text(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _resolve_state_path(base_dir: Path | None = None) -> Path:
    if base_dir is None:
        base_dir = Path.cwd()
    return base_dir / DEFAULT_STATE_PATH


def _parse_timestamp(raw: str) -> datetime | None:
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return parsed.replace(tzinfo=LOCAL_TZ)

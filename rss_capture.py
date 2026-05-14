#!/usr/bin/env python3
"""Capture real RSS / Atom / web source entries into a canonical article JSON file."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fetcher import fetch_articles
from sources import DEFAULT_ITEMS_PER_FEED, RSS_FEEDS, get_feeds
from state import CaptureState, load_state, mark_source_success, save_state, source_is_fresh

LOCAL_TZ = timezone(timedelta(hours=8))
SCRIPT_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture RSS / Atom entries")
    parser.add_argument(
        "--items-per-feed",
        type=int,
        default=DEFAULT_ITEMS_PER_FEED,
        help="Newest items to keep from each feed.",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=None,
        help="Optional total cap across all feeds.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="artifacts/rss",
        help="Directory to save the captured JSON.",
    )
    parser.add_argument(
        "--group",
        type=str,
        default="all",
        choices=("all", "cloudrun", "front", "youtube_front", "youtube", "upstream", "fast", "podcasts", "podcasts_rss", "podcasts_web", "slow", "late"),
        help="Source group to capture.",
    )
    parser.add_argument(
        "--ignore-state",
        action="store_true",
        help="Ignore seen-url and refresh-window state for this run.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.output_dir)
    if not out_dir.is_absolute():
        out_dir = SCRIPT_DIR / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    state, state_path = load_state(SCRIPT_DIR)

    print("Fetching real sources...", flush=True)
    feeds = get_feeds(args.group)
    if not args.ignore_state:
        feeds = _filter_feeds_by_state(feeds, state)
    articles = fetch_articles(
        feeds,
        items_per_feed=args.items_per_feed,
        max_articles=args.max_articles,
    )
    print(f"Captured {len(articles)} articles.", flush=True)

    kept_articles = _dedupe_against_state(articles, state, args.ignore_state)
    print(f"Deduped to {len(kept_articles)} new articles.", flush=True)

    date_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
    out_path = out_dir / f"raw_{date_str}.json"
    payload = json.dumps(kept_articles, ensure_ascii=False, indent=2)

    try:
        out_path.write_text(payload, encoding="utf-8")
        print(f"Saved: {out_path}", flush=True)
    except PermissionError:
        fallback_dir = Path("/private/tmp/strategy_agent_v1/artifacts/rss")
        fallback_dir.mkdir(parents=True, exist_ok=True)
        fallback_path = fallback_dir / f"raw_{date_str}.json"
        fallback_path.write_text(payload, encoding="utf-8")
        print(
            f"Saved: {fallback_path} (fallback, because the project directory was not writable here)",
            flush=True,
        )

    if not args.ignore_state:
        _update_state_from_articles(state, feeds, kept_articles)
        saved_state = save_state(state, SCRIPT_DIR)
        print(f"State saved: {saved_state}", flush=True)
    return 0


def _filter_feeds_by_state(feeds: list[dict[str, Any]], state: CaptureState) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    now = datetime.now(LOCAL_TZ)
    for feed in feeds:
        if not isinstance(feed, dict):
            filtered.append(feed)
            continue
        refresh_hours = feed.get("refresh_hours")
        source_name = str(feed.get("name", "")).strip()
        feed_url = str(feed.get("url", "")).strip()
        source_key = _source_key(source_name, feed_url)
        try:
            refresh_value = float(refresh_hours) if refresh_hours is not None else None
        except (TypeError, ValueError):
            refresh_value = None
        if refresh_value is not None:
            source_state = state.sources.get(source_key, {})
            if source_is_fresh(source_state, refresh_value, now=now):
                print(f"Skipping fresh source: {source_name} (refresh window not elapsed)", flush=True)
                continue
        filtered.append(feed)
    return filtered


def _dedupe_against_state(articles: list[dict[str, Any]], state: CaptureState, ignore_state: bool) -> list[dict[str, Any]]:
    if ignore_state:
        return articles
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set(state.seen_urls.keys())
    for article in articles:
        if not isinstance(article, dict):
            continue
        url = str(article.get("url", "")).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(article)
    return deduped


def _update_state_from_articles(state: CaptureState, feeds: list[dict[str, Any]], articles: list[dict[str, Any]]) -> None:
    by_source: dict[str, list[dict[str, str]]] = {}
    for article in articles:
        if not isinstance(article, dict):
            continue
        source_name = str(article.get("source", "")).strip()
        feed_url = str(article.get("feed_url", "")).strip()
        source_key = _source_key(source_name, feed_url)
        by_source.setdefault(source_key, []).append(
            {
                "url": str(article.get("url", "")).strip(),
                "published": str(article.get("published", "")).strip(),
            }
        )
    for feed in feeds:
        if not isinstance(feed, dict):
            continue
        source_name = str(feed.get("name", "")).strip()
        feed_url = str(feed.get("url", "")).strip()
        source_key = _source_key(source_name, feed_url)
        source_articles = by_source.get(source_key, [])
        urls = [item.get("url", "") for item in source_articles if item.get("url", "")]
        latest_url = source_articles[0].get("url", "") if source_articles else ""
        latest_published = source_articles[0].get("published", "") if source_articles else ""
        mark_source_success(
            state,
            source_key,
            source_name,
            feed_url,
            urls,
            latest_url=latest_url,
            latest_published=latest_published,
        )


def _source_key(source_name: str, feed_url: str) -> str:
    return f"{source_name}::{feed_url}".strip()


if __name__ == "__main__":
    raise SystemExit(main())

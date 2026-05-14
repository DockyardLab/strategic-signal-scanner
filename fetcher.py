"""RSS / Atom fetching utilities for Strategic Signal Scanner."""

from __future__ import annotations

import html
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

LOCAL_TZ = timezone(timedelta(hours=8))


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self.parts).split())


def fetch_articles(
    feeds: list[dict[str, Any]] | list[tuple[str, str]],
    items_per_feed: int = 5,
    timeout_seconds: float | None = None,
    max_articles: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch and normalize entries from RSS/Atom feeds and web sources."""
    articles: list[dict[str, Any]] = []
    timeout = timeout_seconds if timeout_seconds is not None else _env_float("FETCH_TIMEOUT_SECONDS", 12.0)

    for feed in feeds:
        source_name, feed_url, source_type, source_tier, source_timeout = _normalize_source(feed)
        effective_timeout = source_timeout if source_timeout is not None else timeout
        started_at = time.monotonic()
        print(f"Fetching: {source_name}", flush=True)

        try:
            if source_type in {"rss", "atom", "feed"}:
                source_articles = _fetch_rss_source(source_name, feed_url, effective_timeout, items_per_feed)
            elif source_type in {"youtube"}:
                source_articles = _fetch_youtube_source(source_name, feed_url, effective_timeout, items_per_feed)
            elif source_type in {"follow_builders_x", "follow_builders_blogs", "follow_builders_podcasts"}:
                source_articles = _fetch_follow_builders_source(
                    source_name,
                    feed_url,
                    source_type,
                    effective_timeout,
                    items_per_feed,
                )
            else:
                source_articles = _fetch_web_source(source_name, feed_url, effective_timeout, items_per_feed)
        except Exception as exc:  # noqa: BLE001
            print(f"Skipping: {source_name} ({exc})", flush=True)
            continue

        kept = 0
        for article in source_articles[: max(0, items_per_feed)]:
            if source_tier is not None and "tier" not in article:
                article["tier"] = source_tier
            articles.append(article)
            kept += 1
            if max_articles is not None and len(articles) >= max_articles:
                break

        elapsed = time.monotonic() - started_at
        print(
            f"Fetched: {source_name} ({kept} items, {elapsed:.1f}s)",
            flush=True,
        )

        if max_articles is not None and len(articles) >= max_articles:
            break

    return articles


def _normalize_source(feed: dict[str, Any] | tuple[str, str]) -> tuple[str, str, str, int | None, float | None]:
    if isinstance(feed, dict):
        name = str(feed.get("name", "")).strip()
        url = str(feed.get("url", "")).strip()
        source_type = str(feed.get("type") or feed.get("kind") or "rss").strip().lower()
        tier_value = feed.get("tier")
        try:
            tier = int(tier_value) if tier_value is not None and str(tier_value).strip() else None
        except (TypeError, ValueError):
            tier = None
        timeout_value = feed.get("timeout_seconds")
        try:
            timeout_seconds = float(timeout_value) if timeout_value is not None and str(timeout_value).strip() else None
        except (TypeError, ValueError):
            timeout_seconds = None
        return name, url, source_type, tier, timeout_seconds
    name, url = feed
    return str(name).strip(), str(url).strip(), "rss", None, None


def _fetch_follow_builders_source(
    source_name: str,
    feed_url: str,
    source_type: str,
    timeout: float,
    items_per_feed: int,
) -> list[dict[str, Any]]:
    payload = _download_json(feed_url, timeout)
    articles: list[dict[str, Any]] = []
    source_type = source_type.lower()

    if source_type == "follow_builders_x":
        builders = payload.get("x") or []
        for builder in builders:
            builder_name = _clean_text(str(builder.get("name") or source_name))
            handle = _clean_text(str(builder.get("handle") or ""))
            bio = _clean_text(str(builder.get("bio") or ""))
            for tweet in builder.get("tweets") or []:
                text = _clean_text(str(tweet.get("text") or ""))
                tweet_url = _clean_text(str(tweet.get("url") or ""))
                if not text or not tweet_url:
                    continue
                published = _normalize_web_published(str(tweet.get("createdAt") or ""))
                title = _truncate(text.replace("\n", " "), 120)
                summary = _truncate(text, 400)
                if handle:
                    title = f"{builder_name} (@{handle}): {title}"
                content_parts = [part for part in (builder_name, handle, bio, text) if part]
                articles.append(
                    {
                        "source": builder_name,
                        "source_type": "json",
                        "feed_url": feed_url,
                        "title": title,
                        "url": tweet_url,
                        "published": published,
                        "date": published[:10] if published else "",
                        "summary": summary,
                        "content": _truncate("\n\n".join(content_parts), 2200),
                        "fetched_at": datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M"),
                    }
                )

    elif source_type == "follow_builders_blogs":
        blogs = payload.get("blogs") or []
        for blog in blogs:
            blog_name = _clean_text(str(blog.get("name") or source_name))
            title = _clean_text(str(blog.get("title") or blog_name))
            url = _clean_text(str(blog.get("url") or ""))
            if not url:
                continue
            published = _normalize_web_published(str(blog.get("publishedAt") or ""))
            summary = _clean_text(str(blog.get("description") or "")) or _truncate(_clean_text(str(blog.get("content") or "")), 400)
            content = _clean_text(str(blog.get("content") or ""))
            if not content:
                content = summary or title
            articles.append(
                {
                    "source": blog_name,
                    "source_type": "json",
                    "feed_url": feed_url,
                    "title": title,
                    "url": url,
                    "published": published,
                    "date": published[:10] if published else "",
                    "summary": summary,
                    "content": _truncate(content, 2200),
                    "fetched_at": datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M"),
                }
            )

    elif source_type == "follow_builders_podcasts":
        podcasts = payload.get("podcasts") or []
        for episode in podcasts:
            podcast_name = _clean_text(str(episode.get("name") or source_name))
            title = _clean_text(str(episode.get("title") or podcast_name))
            url = _clean_text(str(episode.get("url") or ""))
            if not url:
                continue
            published = _normalize_web_published(str(episode.get("publishedAt") or ""))
            transcript = _clean_text(str(episode.get("transcript") or ""))
            summary = _truncate(transcript, 400)
            content = transcript or summary or title
            articles.append(
                {
                    "source": podcast_name,
                    "source_type": "json",
                    "feed_url": feed_url,
                    "title": title,
                    "url": url,
                    "published": published,
                    "date": published[:10] if published else "",
                    "summary": summary,
                    "content": _truncate(content, 2200),
                    "fetched_at": datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M"),
                }
            )

    return articles[: max(0, items_per_feed)]


def _fetch_rss_source(source_name: str, feed_url: str, timeout: float, items_per_feed: int) -> list[dict[str, Any]]:
    raw_xml = _download_feed(feed_url, timeout)
    entries = _parse_feed(raw_xml)
    return [_entry_to_article(source_name, feed_url, entry) for entry in entries[: max(0, items_per_feed)]]


def _fetch_youtube_source(source_name: str, page_url: str, timeout: float, items_per_feed: int) -> list[dict[str, Any]]:
    feed_url = _resolve_youtube_feed_url(page_url, timeout)
    raw_xml = _download_feed(feed_url, timeout)
    entries = _parse_feed(raw_xml)
    articles = []
    for entry in entries[: max(0, items_per_feed)]:
        article = _entry_to_article(source_name, feed_url, entry)
        article["source_type"] = "youtube"
        article["source_url"] = page_url
        articles.append(article)
    return articles


def _fetch_web_source(source_name: str, page_url: str, timeout: float, items_per_feed: int) -> list[dict[str, Any]]:
    html_text = _download_page(page_url, timeout)

    anthro_cards = _extract_anthropic_cards(source_name, page_url, html_text)
    if anthro_cards:
        articles: list[dict[str, Any]] = []
        for candidate in anthro_cards[: max(0, items_per_feed)]:
            candidate_url = candidate["url"]
            try:
                candidate_html = _download_page(candidate_url, timeout)
                articles.append(
                    _page_to_article(
                        source_name=source_name,
                        source_url=page_url,
                        page_url=candidate_url,
                        html_text=candidate_html,
                        fallback_title=candidate.get("title", ""),
                        fallback_summary=candidate.get("summary", ""),
                        fallback_published=candidate.get("published", ""),
                    )
                )
            except Exception:
                articles.append(
                    _page_to_article(
                        source_name=source_name,
                        source_url=page_url,
                        page_url=candidate_url,
                        html_text=html_text,
                        fallback_title=candidate.get("title", ""),
                        fallback_summary=candidate.get("summary", ""),
                        fallback_published=candidate.get("published", ""),
                    )
                )
        return articles

    candidates = _extract_web_candidates(html_text, page_url)

    articles: list[dict[str, Any]] = []
    if candidates:
        for candidate in candidates[: max(0, items_per_feed)]:
            candidate_url = candidate["url"]
            try:
                candidate_html = _download_page(candidate_url, timeout)
                articles.append(
                    _page_to_article(
                        source_name=source_name,
                        source_url=page_url,
                        page_url=candidate_url,
                        html_text=candidate_html,
                        fallback_title=candidate.get("title", ""),
                        fallback_summary=candidate.get("summary", ""),
                        fallback_published=candidate.get("published", ""),
                    )
                )
            except Exception:
                articles.append(
                    _page_to_article(
                        source_name=source_name,
                        source_url=page_url,
                        page_url=candidate_url,
                        html_text=html_text,
                        fallback_title=candidate.get("title", ""),
                        fallback_summary=candidate.get("summary", ""),
                        fallback_published=candidate.get("published", ""),
                    )
                )
        return articles

    return [
        _page_to_article(
            source_name=source_name,
            source_url=page_url,
            page_url=page_url,
            html_text=html_text,
        )
    ]


def _extract_anthropic_cards(source_name: str, page_url: str, html_text: str) -> list[dict[str, str]]:
    source = source_name.lower()
    if "anthropic news" in source:
        return _extract_anthropic_news_cards(page_url, html_text)
    if "anthropic research" in source:
        return _extract_anthropic_research_cards(page_url, html_text)
    return []


def _extract_anthropic_news_cards(page_url: str, html_text: str) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    pattern = re.compile(
        r'<a\s+href="([^"]+)"[^>]*class="[^"]*FeaturedGrid[^"]*"[^>]*>([\s\S]*?)</a>',
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(html_text):
        href = match.group(1).strip()
        block = match.group(2)
        title = _clean_text(_strip_tags(_extract_first_tag(block, "h4")))
        summary = _clean_text(_strip_tags(_extract_first_tag(block, "p")))
        published = _extract_time_datetime(block)
        if not title:
            continue
        card_url = urljoin(page_url, href)
        if not _looks_like_article_url(card_url, page_url):
            continue
        cards.append(
            {
                "title": title,
                "url": card_url,
                "summary": summary,
                "published": published,
            }
        )
    return _dedupe_candidates(cards)


def _extract_anthropic_research_cards(page_url: str, html_text: str) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    pattern = re.compile(
        r'<a\s+href="([^"]+)"[^>]*class="[^"]*PublicationList[^"]*listItem[^"]*"[^>]*>([\s\S]*?)</a>',
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(html_text):
        href = match.group(1).strip()
        block = match.group(2)
        title = _clean_text(_strip_tags(_extract_first_tag(block, "span", class_contains="title")))
        if not title:
            title = _clean_text(_strip_tags(_extract_first_tag(block, "h4")))
        summary = _clean_text(_strip_tags(_extract_first_tag(block, "p")))
        published = _extract_time_datetime(block)
        card_url = urljoin(page_url, href)
        if not title or not _looks_like_article_url(card_url, page_url):
            continue
        cards.append(
            {
                "title": title,
                "url": card_url,
                "summary": summary,
                "published": published,
            }
        )
    return _dedupe_candidates(cards)


def _download_feed(url: str, timeout_seconds: float) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "StrategicSignalScanner/0.1 (+https://example.com)",
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.1",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def _resolve_youtube_feed_url(page_url: str, timeout_seconds: float) -> str:
    normalized = _clean_text(page_url)
    if "feeds/videos.xml" in normalized:
        return normalized
    if "channel_id=" in normalized:
        return normalized if "feeds/videos.xml" in normalized else f"https://www.youtube.com/feeds/videos.xml?{urlparse(normalized).query}"

    candidate_pages = [normalized]
    stripped = normalized.rstrip("/")
    for suffix in ("/videos", "/about"):
        candidate = f"{stripped}{suffix}"
        if candidate not in candidate_pages:
            candidate_pages.append(candidate)

    for candidate_page in candidate_pages:
        try:
            html_text = _download_page(candidate_page, timeout_seconds)
        except Exception:
            continue
        channel_id = _extract_youtube_channel_id(html_text)
        if channel_id:
            return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    raise ValueError(f"Could not resolve a YouTube RSS feed from {page_url}")


def _extract_youtube_channel_id(html_text: str) -> str:
    patterns = [
        r'feeds/videos\.xml\?channel_id=([A-Za-z0-9_-]+)',
        r'["\']channelId["\']\s*:\s*["\']([A-Za-z0-9_-]+)["\']',
        r'itemprop=["\']channelId["\'][^>]*content=["\']([A-Za-z0-9_-]+)["\']',
        r'channel_id=([A-Za-z0-9_-]+)',
        r'/channel/([A-Za-z0-9_-]+)',
        r'["\']externalId["\']\s*:\s*["\']([A-Za-z0-9_-]+)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return ""


def _download_json(url: str, timeout_seconds: float) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "User-Agent": "StrategicSignalScanner/0.1 (+https://example.com)",
            "Accept": "application/json, text/plain;q=0.9, */*;q=0.1",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read()
    decoded = raw.decode("utf-8", errors="replace")
    payload = json.loads(decoded)
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object at the feed root")
    return payload


def _download_page(url: str, timeout_seconds: float) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "StrategicSignalScanner/0.1 (+https://example.com)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read()
    return raw.decode("utf-8", errors="replace")


def _parse_feed(raw_xml: bytes) -> list[ET.Element]:
    root = ET.fromstring(raw_xml)
    root_name = _local_name(root.tag)

    if root_name == "feed":
        return list(root.findall(".//{*}entry"))

    items = list(root.findall(".//item"))
    if items:
        return items

    rdf_items = list(root.findall(".//{*}item"))
    if rdf_items:
        return rdf_items

    return list(root.findall(".//{*}entry"))


def _extract_web_candidates(html_text: str, page_url: str) -> list[dict[str, str]]:
    base_url = page_url
    candidates: list[dict[str, str]] = []

    for block in re.finditer(r"<article\b[\s\S]*?</article>", html_text, flags=re.IGNORECASE):
        article_html = block.group(0)
        candidate = _extract_candidate_from_block(article_html, base_url)
        if candidate:
            candidates.append(candidate)

    if candidates:
        return _dedupe_candidates(candidates)

    # Fallback: look for headline-like anchors on the page.
    for match in re.finditer(r"<a\b([^>]+)>([\s\S]*?)</a>", html_text, flags=re.IGNORECASE):
        attrs = match.group(1)
        inner_html = match.group(2)
        href = _read_attr(attrs, "href")
        if not href:
            continue
        candidate_url = urljoin(base_url, href)
        if not _looks_like_article_url(candidate_url, base_url):
            continue
        title = _clean_text(_strip_tags(inner_html))
        if not _looks_like_title(title):
            continue
        candidates.append(
            {
                "title": title,
                "url": candidate_url,
                "summary": "",
                "published": "",
            }
        )

    if candidates:
        return _dedupe_candidates(candidates)

    page_title = _extract_meta(html_text, "og:title") or _extract_meta(html_text, "twitter:title") or _extract_tag_text(html_text, "title")
    page_url_final = _extract_meta(html_text, "og:url") or page_url
    summary = _extract_meta(html_text, "description") or _extract_meta(html_text, "og:description") or ""
    if page_title:
        return [
            {
                "title": _clean_text(page_title),
                "url": urljoin(base_url, page_url_final),
                "summary": _clean_text(summary),
                "published": _extract_meta(html_text, "article:published_time") or "",
            }
        ]

    return []


def _extract_candidate_from_block(article_html: str, base_url: str) -> dict[str, str] | None:
    link_match = re.search(r"<a\b[^>]+href=[\"']([^\"']+)[\"'][^>]*>([\s\S]*?)</a>", article_html, flags=re.IGNORECASE)
    title_match = re.search(r"<h[1-3]\b[^>]*>([\s\S]*?)</h[1-3]>", article_html, flags=re.IGNORECASE)
    time_match = re.search(r"<time\b[^>]*datetime=[\"']([^\"']+)[\"']", article_html, flags=re.IGNORECASE)

    href = link_match.group(1).strip() if link_match else ""
    title = _clean_text(_strip_tags(title_match.group(1) if title_match else (link_match.group(2) if link_match else "")))
    if not href or not title:
        return None

    candidate_url = urljoin(base_url, href)
    if not _looks_like_article_url(candidate_url, base_url):
        return None

    summary = _clean_text(_strip_tags(article_html))[:400]
    return {
        "title": title,
        "url": candidate_url,
        "summary": summary,
        "published": time_match.group(1).strip() if time_match else "",
    }


def _page_to_article(
    *,
    source_name: str,
    source_url: str,
    page_url: str,
    html_text: str,
    fallback_title: str = "",
    fallback_summary: str = "",
    fallback_published: str = "",
) -> dict[str, Any]:
    title = (
        _clean_text(_extract_meta(html_text, "og:title"))
        or _clean_text(_extract_meta(html_text, "twitter:title"))
        or _clean_text(_extract_tag_text(html_text, "title"))
        or _clean_text(_extract_first_heading(html_text))
        or _clean_text(fallback_title)
        or source_name
    )
    summary = (
        _clean_text(_extract_meta(html_text, "description"))
        or _clean_text(_extract_meta(html_text, "og:description"))
        or _clean_text(_extract_meta(html_text, "twitter:description"))
        or _clean_text(fallback_summary)
    )
    published = (
        _extract_meta(html_text, "article:published_time")
        or _extract_meta(html_text, "article:modified_time")
        or _extract_meta(html_text, "og:updated_time")
        or _extract_time_datetime(html_text)
        or fallback_published
    )
    content = _extract_article_text(html_text)
    if not content:
        content = summary or title
    content = _truncate(_clean_text(content), 2200)

    normalized_published = _normalize_web_published(published)

    return {
        "source": source_name,
        "source_type": "web",
        "feed_url": source_url,
        "title": title,
        "url": page_url,
        "published": normalized_published,
        "date": normalized_published[:10] if normalized_published else "",
        "summary": summary,
        "content": content,
        "fetched_at": datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M"),
    }


def _extract_article_text(html_text: str) -> str:
    for pattern in (
        r"<article\b[\s\S]*?</article>",
        r"<main\b[\s\S]*?</main>",
        r"<div\b[^>]*(?:class|id)=[\"'][^\"']*(?:content|article|post|entry|story)[^\"']*[\"'][^>]*>[\s\S]*?</div>",
    ):
        match = re.search(pattern, html_text, flags=re.IGNORECASE)
        if match:
            text = _clean_text(_strip_tags(match.group(0)))
            if len(text) > 120:
                return text

    paragraphs = [
        _clean_text(_strip_tags(chunk))
        for chunk in re.findall(r"<p\b[^>]*>([\s\S]*?)</p>", html_text, flags=re.IGNORECASE)
    ]
    paragraphs = [paragraph for paragraph in paragraphs if len(paragraph) > 40]
    if paragraphs:
        return " ".join(paragraphs[:8])

    return ""


def _extract_meta(html_text: str, name: str) -> str:
    pattern = re.compile(
        rf"<meta[^>]+(?:property|name)=[\"']{re.escape(name)}[\"'][^>]+content=[\"']([^\"']+)[\"'][^>]*>",
        flags=re.IGNORECASE,
    )
    match = pattern.search(html_text)
    return match.group(1).strip() if match else ""


def _extract_tag_text(html_text: str, tag: str) -> str:
    match = re.search(rf"<{re.escape(tag)}\b[^>]*>([\s\S]*?)</{re.escape(tag)}>", html_text, flags=re.IGNORECASE)
    return _clean_text(_strip_tags(match.group(1))) if match else ""


def _extract_first_heading(html_text: str) -> str:
    for tag in ("h1", "h2", "h3"):
        text = _extract_tag_text(html_text, tag)
        if text:
            return text
    return ""


def _extract_first_tag(html_text: str, tag: str, class_contains: str | None = None) -> str:
    if class_contains:
        pattern = re.compile(
            rf"<{re.escape(tag)}\b[^>]*class=[\"'][^\"']*{re.escape(class_contains)}[^\"']*[\"'][^>]*>([\s\S]*?)</{re.escape(tag)}>",
            flags=re.IGNORECASE,
        )
    else:
        pattern = re.compile(rf"<{re.escape(tag)}\b[^>]*>([\s\S]*?)</{re.escape(tag)}>", flags=re.IGNORECASE)
    match = pattern.search(html_text)
    return match.group(1).strip() if match else ""


def _extract_time_datetime(html_text: str) -> str:
    match = re.search(r"<time\b[^>]*datetime=[\"']([^\"']+)[\"']", html_text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    text_match = re.search(r"<time\b[^>]*>([\s\S]*?)</time>", html_text, flags=re.IGNORECASE)
    return _clean_text(_strip_tags(text_match.group(1))) if text_match else ""


def _normalize_web_published(raw: str) -> str:
    if not raw:
        return ""
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        parsed = _parse_iso_datetime(raw)
        if parsed is None:
            parsed = _parse_human_date(raw)

    if parsed is None:
        return raw
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M")


def _parse_human_date(raw: str) -> datetime | None:
    cleaned = raw.strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _read_attr(attrs: str, name: str) -> str:
    match = re.search(rf"{re.escape(name)}=[\"']([^\"']+)[\"']", attrs, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _looks_like_article_url(candidate_url: str, base_url: str) -> bool:
    parsed = urlparse(candidate_url)
    base_parsed = urlparse(base_url)
    if not parsed.scheme.startswith("http"):
        return False
    if parsed.netloc and base_parsed.netloc and parsed.netloc != base_parsed.netloc:
        return False
    path = (parsed.path or "").lower()
    if not path or path == "/" or path in {"/feed", "/rss"}:
        return False
    if any(token in path for token in ("/tag/", "/tags/", "/category/", "/categories/", "/author/", "/search", "/about", "/privacy", "/terms", "/jobs", "/login", "/signup")):
        return False
    if any(path.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".css", ".js", ".xml", ".pdf")):
        return False
    return True


def _looks_like_title(title: str) -> bool:
    cleaned = title.strip()
    if len(cleaned) < 10 or len(cleaned) > 160:
        return False
    word_count = len(cleaned.split())
    return word_count >= 2


def _dedupe_candidates(candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for candidate in candidates:
        url = candidate.get("url", "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(candidate)
    return deduped


def _entry_to_article(source_name: str, feed_url: str, entry: ET.Element) -> dict[str, Any]:
    title = _clean_text(_first_text(entry, "title"))
    link = _extract_link(entry)
    published = _extract_published(entry)
    summary = _clean_text(
        _first_text(entry, "summary")
        or _first_text(entry, "description")
        or _first_text(entry, "{http://www.w3.org/2005/Atom}summary")
        or _first_text(entry, "{http://purl.org/rss/1.0/modules/content/}encoded")
    )
    content = _clean_text(
        _first_text(entry, "{http://purl.org/rss/1.0/modules/content/}encoded")
        or _first_text(entry, "content")
        or summary
    )

    if not content:
        content = summary

    content = _truncate(content, 2200)

    return {
        "source": source_name,
        "source_type": "rss",
        "feed_url": feed_url,
        "title": title,
        "url": link,
        "published": published,
        "date": published[:10] if published else "",
        "summary": summary,
        "content": content,
        "fetched_at": datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M"),
    }


def _first_text(entry: ET.Element, tag_name: str) -> str:
    target = _local_name(tag_name)
    for element in entry.iter():
        if _local_name(element.tag) == target and element.text and element.text.strip():
            return element.text.strip()
    return ""


def _extract_link(entry: ET.Element) -> str:
    for element in entry.iter():
        if _local_name(element.tag) != "link":
            continue
        href = element.attrib.get("href")
        if href and href.strip():
            rel = element.attrib.get("rel", "").strip().lower()
            if not rel or rel == "alternate":
                return href.strip()
        if element.text and element.text.strip():
            return element.text.strip()

    return ""


def _extract_published(entry: ET.Element) -> str:
    raw = (
        _first_text(entry, "published")
        or _first_text(entry, "updated")
        or _first_text(entry, "pubDate")
        or _first_text(entry, "dc:date")
        or ""
    )

    parsed = None
    if raw:
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            parsed = _parse_iso_datetime(raw)

    if parsed is None:
        return raw if raw else ""

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    local = parsed.astimezone(LOCAL_TZ)
    return local.strftime("%Y-%m-%d %H:%M")


def _parse_iso_datetime(raw: str) -> datetime | None:
    normalized = raw.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _clean_text(value: str) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    extractor = _TextExtractor()
    extractor.feed(text)
    cleaned = extractor.text() if extractor.parts else text
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _strip_tags(value: str) -> str:
    if not value:
        return ""
    return re.sub(r"<[^>]*>", " ", value)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 1)].rstrip() + "…"


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    if ":" in tag:
        return tag.rsplit(":", 1)[1]
    return tag


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)).strip())
    except ValueError:
        return default

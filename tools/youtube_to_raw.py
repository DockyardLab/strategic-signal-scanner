#!/usr/bin/env python3
"""Convert a YouTube transcript into a Strategic Signal Scanner raw item."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path


LOCAL_TZ = timezone(timedelta(hours=8))
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert a YouTube transcript into a raw scanner item.")
    parser.add_argument("--video-url", required=True, help="YouTube video URL.")
    parser.add_argument("--title", required=True, help="Video title.")
    parser.add_argument("--source", default="YouTube", help="Source name shown in the scanner.")
    parser.add_argument("--date", required=True, help="Video date in YYYY-MM-DD.")
    parser.add_argument(
        "--summary",
        default="",
        help="Optional short summary. If omitted, a summary will be generated from the transcript.",
    )
    parser.add_argument(
        "--transcript-file",
        required=True,
        help="Path to an .srt, .vtt, or plain text transcript file.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output path. Defaults to artifacts/rss/raw_youtube_<video_id>.json",
    )
    parser.add_argument(
        "--max-content-chars",
        type=int,
        default=12000,
        help="Cap transcript content to this many characters after cleaning.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    transcript_path = Path(args.transcript_file)
    if not transcript_path.exists():
        raise FileNotFoundError(f"Transcript file not found: {transcript_path}")

    transcript_text = transcript_path.read_text(encoding="utf-8", errors="replace")
    content = _clean_transcript(transcript_text, transcript_path.suffix.lower(), max(0, args.max_content_chars))
    summary = args.summary.strip() or _summarize(content)
    video_id = _extract_video_id(args.video_url)

    payload = [
        {
            "source": args.source,
            "source_type": "youtube",
            "feed_url": args.video_url,
            "title": args.title,
            "url": args.video_url,
            "published": f"{args.date} 00:00" if args.date else "",
            "date": args.date,
            "summary": summary,
            "content": content,
            "fetched_at": datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M"),
            "tier": 1,
            "video_id": video_id,
        }
    ]

    output_path = _resolve_output_path(args.output, video_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Raw YouTube item saved: {output_path}")
    return 0


def _resolve_output_path(output: str, video_id: str) -> Path:
    if output:
        path = Path(output)
        return path if path.is_absolute() else (REPO_DIR / path)
    return REPO_DIR / "artifacts" / "rss" / f"raw_youtube_{video_id}.json"


def _extract_video_id(url: str) -> str:
    match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    if match:
        return match.group(1)
    return "youtube"


def _clean_transcript(text: str, suffix: str, max_chars: int) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    last_text = ""

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.isdigit():
            continue
        if _looks_like_timestamp(stripped):
            continue
        if stripped in {"WEBVTT", "Kind: captions", "Language: en"}:
            continue
        cleaned = _normalize_whitespace(_strip_html(stripped))
        if not cleaned:
            continue
        if cleaned == last_text:
            continue
        kept.append(cleaned)
        last_text = cleaned

    joined = " ".join(kept)
    joined = _normalize_whitespace(joined)
    if max_chars and len(joined) > max_chars:
        joined = joined[:max_chars].rsplit(" ", 1)[0].strip()
    return joined


def _summarize(content: str) -> str:
    if not content:
        return "YouTube transcript for signal scanning."
    summary = content[:260]
    summary = summary.rsplit(" ", 1)[0].strip()
    return summary


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def _looks_like_timestamp(text: str) -> bool:
    return bool(re.match(r"^\d{1,2}:\d{2}(?::\d{2})?\s+-->\s+\d{1,2}:\d{2}(?::\d{2})?", text))


if __name__ == "__main__":
    raise SystemExit(main())

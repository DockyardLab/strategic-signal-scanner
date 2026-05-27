#!/usr/bin/env python3
"""Score captured raw source JSON with the signal replay pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from signal_replay import (
    _analyze,
    _build_gemini_prompt,
    _compare,
    _load_local_env,
    _load_system_instruction,
    _print_report,
)


LOCAL_TZ = timezone(timedelta(hours=8))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score a raw RSS capture file")
    parser.add_argument("raw_json", type=str, help="Path to artifacts/rss/raw_YYYY-MM-DD.json")
    parser.add_argument(
        "--mode",
        choices=("mock", "gemini"),
        default="mock",
        help="mock = zero token local scoring; gemini = real model scoring",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-3.1-flash-lite-preview",
        help="Gemini model used only in gemini mode.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on how many raw items to score.",
    )
    parser.add_argument(
        "--print-prompt",
        action="store_true",
        help="Print the assembled Gemini prompt for each sample without calling the API.",
    )
    parser.add_argument(
        "--debug-response",
        action="store_true",
        help="Print the raw Gemini response before JSON parsing.",
    )
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=3,
        help="How many times to retry Gemini on retryable errors.",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=3,
        help="Minimum relevance score to show in the terminal report and high-signal output.",
    )
    return parser.parse_args()


def main() -> int:
    _load_local_env()
    args = parse_args()
    raw_path = Path(args.raw_json)
    if not raw_path.is_absolute():
        raw_path = REPO_DIR / raw_path
    if not raw_path.exists():
        print(f"Raw file not found: {raw_path}", file=sys.stderr)
        return 1

    data = json.loads(raw_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print("Raw file must be a JSON list of articles.", file=sys.stderr)
        return 1

    raw_items: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            raw_items.append(item)
        if args.limit is not None and len(raw_items) >= max(0, args.limit):
            break

    if not raw_items:
        print("No usable items found in raw file.", file=sys.stderr)
        return 1

    results = []
    scored_items: list[dict[str, Any]] = []
    total = len(raw_items)

    for index, item in enumerate(raw_items, start=1):
        sample = {
            "id": f"raw_{index:02d}",
            "input": {
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "date": item.get("date", ""),
                "url": item.get("url", ""),
                "content": item.get("content", "") or item.get("summary", ""),
            },
            "expected": {},
            "note": f"converted from {raw_path.name}",
        }

        print(f"Running {index}/{total}: {index:02d}.json [{args.mode}]", flush=True)
        if args.print_prompt:
            system_instruction = _load_system_instruction()
            prompt = _build_gemini_prompt(system_instruction, dict(sample.get("input") or {}))
            print(prompt)
            print()
            continue

        actual = _analyze(
            sample,
            mode=args.mode,
            model=args.model,
            debug_response=args.debug_response,
            retry_attempts=args.retry_attempts,
        )
        results.append(_compare(sample.get("id") or f"raw_{index:02d}", {}, actual))

        merged = dict(item)
        merged["analysis"] = actual
        scored_items.append(merged)

    if args.print_prompt:
        return 0

    scored_payload = {
        "source_file": raw_path.name,
        "scored_at": datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M"),
        "mode": args.mode,
        "model": args.model if args.mode == "gemini" else None,
        "count": len(scored_items),
        "items": scored_items,
    }

    high_signal_items: list[dict[str, Any]] = []
    for item in scored_items:
        analysis = item.get("analysis") or {}
        try:
            score = int(analysis.get("relevance_score", 0))
        except (TypeError, ValueError):
            score = 0
        if score >= max(0, args.min_score):
            high_signal_items.append(item)
    scored_payload["high_signal_items"] = sorted(
        high_signal_items,
        key=lambda item: int((item.get("analysis") or {}).get("relevance_score", 0)),
        reverse=True,
    )
    scored_payload["high_signal_count"] = len(high_signal_items)

    scored_name = raw_path.name.replace("raw_", "scored_", 1)
    scored_path = raw_path.with_name(scored_name)
    try:
        scored_path.write_text(json.dumps(scored_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except PermissionError:
        fallback_dir = Path("/private/tmp/strategy_agent_v1/artifacts/rss")
        fallback_dir.mkdir(parents=True, exist_ok=True)
        scored_path = fallback_dir / scored_name
        scored_path.write_text(json.dumps(scored_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Scored file saved: {scored_path}", flush=True)
    report_paths = [Path(f"{result.sample_id}.json") for result in results]
    visible_results = []
    visible_paths = []
    for path, result in zip(report_paths, results):
        score = result.actual.get("relevance_score", 0)
        try:
            score_value = int(score)
        except (TypeError, ValueError):
            score_value = 0
        if score_value >= max(0, args.min_score):
            visible_paths.append(path)
            visible_results.append(result)
    if visible_results:
        _print_report(visible_paths, visible_results, args.mode, args.model)
    else:
        print(f"No items reached the min score threshold of {args.min_score}.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

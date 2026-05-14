#!/usr/bin/env python3
"""One-command pipeline: capture real source items, then score them."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from sources import DEFAULT_ITEMS_PER_FEED


SCRIPT_DIR = Path(__file__).resolve().parent
LOCAL_TZ = timezone(timedelta(hours=8))
RSS_CAPTURE_SCRIPT = SCRIPT_DIR / "rss_capture.py"
SCORE_RAW_SCRIPT = SCRIPT_DIR / "score_raw_rss.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture real RSS / Atom / web source entries and score them in one pass."
    )
    parser.add_argument(
        "--items-per-feed",
        type=int,
        default=DEFAULT_ITEMS_PER_FEED,
        help="Newest items to keep from each feed during capture.",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=None,
        help="Optional total cap across all feeds during capture.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="artifacts/rss",
        help="Directory used by rss_capture.py to save the raw JSON.",
    )
    parser.add_argument(
        "--group",
        type=str,
        default="all",
        choices=("all", "cloudrun", "front", "youtube_front", "youtube", "upstream", "fast", "podcasts", "podcasts_rss", "podcasts_web", "slow", "late"),
        help="Source group to capture and score.",
    )
    parser.add_argument(
        "--ignore-state",
        action="store_true",
        help="Ignore seen-url and refresh-window state for this run.",
    )
    parser.add_argument(
        "--score-mode",
        choices=("mock", "gemini"),
        default="mock",
        help="mock = zero-token local scoring; gemini = real model scoring.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-3.1-flash-lite-preview",
        help="Gemini model used only when --score-mode gemini is selected.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on how many captured items to score.",
    )
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=3,
        help="Retry count forwarded to the scoring step.",
    )
    parser.add_argument(
        "--print-prompt",
        action="store_true",
        help="Forward --print-prompt to the scoring step.",
    )
    parser.add_argument(
        "--debug-response",
        action="store_true",
        help="Forward --debug-response to the scoring step.",
    )
    return parser.parse_args()


def _candidate_raw_files(output_dir: Path) -> list[Path]:
    date_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
    fallback_dir = Path("/private/tmp/strategy_agent_v1/artifacts/rss")
    candidates = [
        output_dir / f"raw_{date_str}.json",
        fallback_dir / f"raw_{date_str}.json",
    ]

    if output_dir.exists():
        candidates.extend(sorted(output_dir.glob("raw_*.json")))
    if fallback_dir.exists():
        candidates.extend(sorted(fallback_dir.glob("raw_*.json")))

    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _pick_latest_existing(paths: Iterable[Path]) -> Path | None:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def main() -> int:
    args = parse_args()

    capture_cmd = [
        sys.executable,
        str(RSS_CAPTURE_SCRIPT),
        "--items-per-feed",
        str(args.items_per_feed),
    ]
    if args.max_articles is not None:
        capture_cmd.extend(["--max-articles", str(args.max_articles)])
    if args.output_dir:
        capture_cmd.extend(["--output-dir", args.output_dir])
    if args.group:
        capture_cmd.extend(["--group", args.group])
    if args.ignore_state:
        capture_cmd.append("--ignore-state")

    print("Step 1/2: capturing RSS / Atom entries...", flush=True)
    capture_result = subprocess.run(capture_cmd, cwd=str(SCRIPT_DIR))
    if capture_result.returncode != 0:
        return capture_result.returncode

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = SCRIPT_DIR / output_dir
    raw_path = _pick_latest_existing(_candidate_raw_files(output_dir))
    if raw_path is None:
        print(
            "Capture finished, but no raw JSON file was found in the expected output locations.",
            file=sys.stderr,
        )
        return 1

    score_cmd = [
        sys.executable,
        str(SCORE_RAW_SCRIPT),
        str(raw_path),
        "--mode",
        args.score_mode,
        "--model",
        args.model,
        "--retry-attempts",
        str(args.retry_attempts),
    ]
    if args.limit is not None:
        score_cmd.extend(["--limit", str(args.limit)])
    if args.print_prompt:
        score_cmd.append("--print-prompt")
    if args.debug_response:
        score_cmd.append("--debug-response")

    print(f"Step 2/2: scoring {raw_path.name} with mode={args.score_mode}...", flush=True)
    score_result = subprocess.run(score_cmd, cwd=str(SCRIPT_DIR))
    return score_result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Cloud Run Job entrypoint for the Strategic Signal Scanner pipeline."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import shutil
from pathlib import Path

from mailer import send_notification_email


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent


def main() -> int:
    output_dir = _env_path("OUTPUT_DIR", "/tmp/artifacts/rss")
    output_dir.mkdir(parents=True, exist_ok=True)
    _clear_previous_outputs(output_dir)

    group = _env("RUN_GROUP", "cloudrun")
    score_mode = _env("SCORE_MODE", "gemini")
    model = _env("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
    items_per_feed = _env("ITEMS_PER_FEED", "1")
    max_articles = _env("MAX_ARTICLES", "30")
    retry_attempts = _env("RETRY_ATTEMPTS", "5")
    max_age_days = _env("MAX_AGE_DAYS", "180")
    ignore_state = _env_bool("IGNORE_STATE", False)
    report_max_age_days = _env("REPORT_MAX_AGE_DAYS", max_age_days)
    state_path = REPO_DIR / "artifacts" / "rss" / "state.json"
    feedback_path = REPO_DIR / "artifacts" / "rss" / "feedback.json"

    print("Cloud Run Job started.", flush=True)
    print(f"  output_dir={output_dir}", flush=True)
    print(f"  group={group}", flush=True)
    print(f"  score_mode={score_mode}", flush=True)
    print(f"  model={model}", flush=True)

    bucket = _env("ARCHIVE_BUCKET", "")
    prefix = _env("ARCHIVE_PREFIX", "signal-archive").strip("/")

    if bucket:
        _download_state_from_bucket(bucket, prefix, state_path)
        _download_feedback_from_bucket(bucket, prefix, feedback_path)

    capture_cmd = [
        sys.executable,
        str(SCRIPT_DIR / "capture_and_score.py"),
        "--group",
        group,
        "--items-per-feed",
        items_per_feed,
        "--max-articles",
        max_articles,
        "--output-dir",
        str(output_dir),
        "--score-mode",
        score_mode,
        "--model",
        model,
        "--retry-attempts",
        retry_attempts,
    ]
    if ignore_state:
        capture_cmd.append("--ignore-state")

    _run(capture_cmd, cwd=SCRIPT_DIR)

    if bucket:
        _sync_archive_history_from_bucket(bucket, prefix, output_dir)
        _mirror_state_into_output_dir(state_path, output_dir)
        _mirror_feedback_into_output_dir(feedback_path, output_dir)

    scored_files = sorted(output_dir.glob("scored_*.json"), key=lambda p: p.stat().st_mtime)
    if not scored_files:
        print(f"No scored_*.json found in {output_dir}", file=sys.stderr)
        return 1

    scored_path = scored_files[-1]
    report_path = output_dir / scored_path.name.replace("scored_", "report_", 1).replace(".json", ".html")

    build_report_cmd = [
        sys.executable,
        str(SCRIPT_DIR / "build_report.py"),
        "--scored-file",
        str(scored_path),
        "--output",
        str(report_path),
        "--max-age-days",
        report_max_age_days,
    ]
    _run(build_report_cmd, cwd=SCRIPT_DIR)

    build_archive_cmd = [
        sys.executable,
        str(SCRIPT_DIR / "build_archive.py"),
        "--artifact-dir",
        str(output_dir),
        "--output",
        str(output_dir / "archive_index.html"),
        "--max-age-days",
        max_age_days,
    ]
    _run(build_archive_cmd, cwd=SCRIPT_DIR)

    if bucket:
        _upload_artifacts(output_dir, bucket, prefix)
    else:
        print("ARCHIVE_BUCKET not set; keeping artifacts local only.", flush=True)

    _send_summary_email(output_dir, bucket, prefix, report_path, scored_path)

    print("Cloud Run Job finished successfully.", flush=True)
    return 0


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name, "true" if default else "false").lower()
    return raw in {"1", "true", "yes", "on"}


def _env_path(name: str, default: str) -> Path:
    value = _env(name, default)
    path = Path(value)
    return path if path.is_absolute() else (REPO_DIR / path)


def _clear_previous_outputs(output_dir: Path) -> None:
    patterns = ("raw_*.json", "scored_*.json", "report_*.html", "archive_index.html")
    for pattern in patterns:
        for path in output_dir.glob(pattern):
            try:
                path.unlink()
            except FileNotFoundError:
                continue


def _run(cmd: list[str], cwd: Path) -> None:
    print(f"Running: {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, cwd=str(cwd))
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def _storage_client():
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise RuntimeError(
            "google-cloud-storage is required for archive synchronization."
        ) from exc
    return storage.Client()


def _download_state_from_bucket(bucket_name: str, prefix: str, state_path: Path) -> None:
    client = _storage_client()
    bucket = client.bucket(bucket_name)
    blob_name = f"{prefix}/state.json" if prefix else "state.json"
    blob = bucket.get_blob(blob_name)
    if blob is None:
        print(f"No remote state found at gs://{bucket_name}/{blob_name}; starting fresh.", flush=True)
        return

    state_path.parent.mkdir(parents=True, exist_ok=True)
    blob.download_to_filename(str(state_path))
    print(f"Downloaded archive state from gs://{bucket_name}/{blob_name}", flush=True)


def _mirror_state_into_output_dir(state_path: Path, output_dir: Path) -> None:
    if not state_path.exists():
        return
    target = output_dir / "state.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(state_path, target)
    print(f"Mirrored state into {target}", flush=True)


def _download_feedback_from_bucket(bucket_name: str, prefix: str, feedback_path: Path) -> None:
    client = _storage_client()
    bucket = client.bucket(bucket_name)
    blob_name = f"{prefix}/feedback.json" if prefix else "feedback.json"
    blob = bucket.get_blob(blob_name)
    if blob is None:
        print(f"No remote feedback found at gs://{bucket_name}/{blob_name}; starting fresh.", flush=True)
        return

    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    blob.download_to_filename(str(feedback_path))
    print(f"Downloaded feedback state from gs://{bucket_name}/{blob_name}", flush=True)


def _mirror_feedback_into_output_dir(feedback_path: Path, output_dir: Path) -> None:
    if not feedback_path.exists():
        return
    target = output_dir / "feedback.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(feedback_path, target)
    print(f"Mirrored feedback into {target}", flush=True)


def _sync_archive_history_from_bucket(bucket_name: str, prefix: str, output_dir: Path) -> None:
    client = _storage_client()
    bucket = client.bucket(bucket_name)
    prefix_path = f"{prefix}/" if prefix else ""
    print(f"Syncing archive history from gs://{bucket_name}/{prefix_path}...", flush=True)
    for blob in client.list_blobs(bucket_name, prefix=prefix_path or None):
        name = blob.name
        if prefix_path and name.startswith(prefix_path):
            name = name[len(prefix_path):]
        if not name.startswith("scored_") or not name.endswith(".json"):
            continue
        local_path = output_dir / name
        if local_path.exists():
            continue
        local_path.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(local_path))
        print(f"  downloaded {blob.name}", flush=True)


def _upload_artifacts(output_dir: Path, bucket_name: str, prefix: str) -> None:
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise RuntimeError(
            "google-cloud-storage is required when ARCHIVE_BUCKET is set."
        ) from exc

    client = storage.Client()
    bucket = client.bucket(bucket_name)

    print(f"Uploading artifacts to gs://{bucket_name}/{prefix}/...", flush=True)
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(output_dir).as_posix()
        blob_name = f"{prefix}/{rel}" if prefix else rel
        blob = bucket.blob(blob_name)
        blob.cache_control = "no-cache, max-age=0"
        content_type = _content_type_for(path.suffix.lower())
        blob.upload_from_filename(str(path), content_type=content_type)
        print(f"  uploaded {blob_name}", flush=True)


def _send_summary_email(output_dir: Path, bucket: str, prefix: str, report_path: Path, scored_path: Path) -> None:
    if not bucket:
        print("No bucket configured; skipping email summary links to public archive.", flush=True)
        return

    scored_payload = _load_json(scored_path)
    date_str = scored_path.stem.replace("scored_", "")
    archive_url = (
        f"https://storage.googleapis.com/{bucket}/{prefix}/archive_index.html"
        if prefix
        else f"https://storage.googleapis.com/{bucket}/archive_index.html"
    )
    report_url = (
        f"https://storage.googleapis.com/{bucket}/{prefix}/{report_path.name}"
        if prefix
        else f"https://storage.googleapis.com/{bucket}/{report_path.name}"
    )
    high_signal_count = int(scored_payload.get("high_signal_count") or 0)
    count = int(scored_payload.get("count") or 0)

    body = "\n".join(
        [
            "Hello，",
            "",
            f"今天的 Strategic Signal Scanner 已完成（{date_str}）。",
            "",
            f"抓取数量：{count}",
            f"高信号数量：{high_signal_count}",
            "",
            "Archive 首页：",
            archive_url,
            "",
            "今日报告：",
            report_url,
            "",
            "—— Strategic Signal Scanner",
        ]
    )
    html_body = f"""
    <html>
      <body style="font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;line-height:1.7;color:#4a2f21;">
        <p>Hello，</p>
        <p>今天的 <strong>Strategic Signal Scanner</strong> 已完成（{date_str}）。</p>
        <p>抓取数量：<strong>{count}</strong><br/>
        高信号数量：<strong>{high_signal_count}</strong></p>
        <p><a href="{archive_url}">打开 Archive 首页</a><br/>
        <a href="{report_url}">打开今日报告</a></p>
        <p>—— Strategic Signal Scanner</p>
      </body>
    </html>
    """
    try:
        send_notification_email(
            subject=f"Strategic Signal Scanner · {date_str}",
            body=body,
            html_body=html_body,
        )
    except Exception as exc:
        print(f"Email notification skipped or failed: {exc}", flush=True)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _content_type_for(suffix: str) -> str:
    return {
        ".html": "text/html; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
        ".svg": "image/svg+xml",
    }.get(suffix, "application/octet-stream")


if __name__ == "__main__":
    raise SystemExit(main())

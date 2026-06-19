#!/usr/bin/env python3
"""Small HTTP service for recording report feedback clicks."""

from __future__ import annotations

import json
import os
import sys
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from feedback import FeedbackState, load_feedback, record_feedback, save_feedback


class FeedbackHandler(BaseHTTPRequestHandler):
    server_version = "StrategicSignalFeedback/1.0"

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._send_text("ok\n", HTTPStatus.OK)
            return
        if parsed.path != "/feedback":
            self._send_text("not found\n", HTTPStatus.NOT_FOUND)
            return

        params = {key: values[-1] for key, values in parse_qs(parsed.query, keep_blank_values=True).items() if values}
        try:
            _validate_token(params)
            item = _item_from_params(params)
            vote = str(params.get("vote") or "").strip().lower()
            if vote not in {"like", "dislike"}:
                raise ValueError("vote must be like or dislike")
            state, _ = load_feedback(REPO_DIR)
            entry = record_feedback(
                state,
                item,
                vote,
                report_url=str(params.get("return_to") or params.get("report_url") or ""),
                comment=str(params.get("comment") or ""),
                user_agent=str(self.headers.get("User-Agent") or ""),
            )
            saved_path = save_feedback(state, REPO_DIR)
            _upload_feedback(saved_path)
            print(f"Recorded feedback: {entry['vote']} for {entry['item_id']}", flush=True)
            redirect_target = str(params.get("return_to") or params.get("report_url") or "").strip()
            if redirect_target:
                self.send_response(HTTPStatus.FOUND)
                self.send_header("Location", redirect_target)
                self.end_headers()
            else:
                self._send_html(_success_page(entry), HTTPStatus.OK)
        except Exception as exc:  # noqa: BLE001
            self._send_text(f"feedback error: {exc}\n", HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        print(f"{self.address_string()} - {format % args}", flush=True)

    def _send_text(self, body: str, status: HTTPStatus) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_html(self, body: str, status: HTTPStatus) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def _item_from_params(params: dict[str, str]) -> dict[str, Any]:
    return {
        "title": params.get("title", ""),
        "source": params.get("source", ""),
        "url": params.get("url", ""),
        "published": params.get("published", ""),
        "analysis": {"source": params.get("source", ""), "title": params.get("title", ""), "url": params.get("url", "")},
    }


def _validate_token(params: dict[str, str]) -> None:
    expected = os.getenv("FEEDBACK_TOKEN", "").strip()
    if not expected:
        return
    supplied = str(params.get("token") or "").strip()
    if supplied != expected:
        raise PermissionError("invalid feedback token")


def _success_page(entry: dict[str, Any]) -> str:
    vote_label = "喜欢" if entry.get("vote") == "like" else "不相关"
    title = str(entry.get("title") or "这条信号")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>反馈已记录</title>
  <style>
    body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; background: #fffef8; color: #292827; font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; }}
    main {{ max-width: 560px; margin: 24px; padding: 28px; border: 1px solid #eadbca; border-radius: 24px; background: #fffaf3; box-shadow: 0 18px 50px rgba(84, 60, 39, .12); }}
    h1 {{ margin: 0 0 10px; font-size: 28px; }}
    p {{ margin: 8px 0; line-height: 1.7; color: #6f655c; }}
    strong {{ color: #a14632; }}
  </style>
</head>
<body>
  <main>
    <h1>反馈已记录</h1>
    <p>你把 <strong>{escape(title)}</strong> 标记为：<strong>{vote_label}</strong>。</p>
    <p>下一次生成 report 时，系统会用这条文章级反馈调整排序和过滤。</p>
  </main>
</body>
</html>"""


def _upload_feedback(feedback_path: Path) -> None:
    bucket_name = os.getenv("ARCHIVE_BUCKET", "").strip()
    if not bucket_name or not feedback_path.exists():
        return
    prefix = os.getenv("ARCHIVE_PREFIX", "signal-archive").strip("/")
    blob_name = f"{prefix}/feedback.json" if prefix else "feedback.json"
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise RuntimeError("google-cloud-storage is required to upload feedback to Cloud Storage.") from exc

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.cache_control = "no-cache, max-age=0"
    blob.upload_from_filename(str(feedback_path), content_type="application/json")
    print(f"Uploaded feedback to gs://{bucket_name}/{blob_name}", flush=True)


def main() -> int:
    port = int(os.getenv("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), FeedbackHandler)
    print(f"Feedback service listening on :{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

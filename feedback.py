"""Persistent feedback state for signal report items."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from state import article_dedupe_keys

LOCAL_TZ = timezone(timedelta(hours=8))
DEFAULT_FEEDBACK_PATH = Path("artifacts/rss/feedback.json")
FALLBACK_FEEDBACK_PATH = Path("/private/tmp/strategy_agent_v1/artifacts/rss/feedback.json")


@dataclass
class FeedbackState:
    decisions: dict[str, dict[str, Any]] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    source_tallies: dict[str, dict[str, int]] = field(default_factory=dict)


def load_feedback(base_dir: Path | None = None) -> tuple[FeedbackState, Path]:
    primary_path = _resolve_feedback_path(base_dir)
    for feedback_path in (primary_path, FALLBACK_FEEDBACK_PATH):
        if not feedback_path.exists():
            continue
        try:
            payload = json.loads(feedback_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        state = _state_from_payload(payload)
        return state, feedback_path
    return FeedbackState(), primary_path


def save_feedback(state: FeedbackState, base_dir: Path | None = None) -> Path:
    primary_path = _resolve_feedback_path(base_dir)
    payload = _state_to_payload(state)
    for feedback_path in (primary_path, FALLBACK_FEEDBACK_PATH):
        try:
            feedback_path.parent.mkdir(parents=True, exist_ok=True)
            feedback_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return feedback_path
        except PermissionError:
            continue
    raise PermissionError("Unable to save feedback state to primary or fallback locations.")


def record_feedback(
    state: FeedbackState,
    item: dict[str, Any],
    vote: str,
    *,
    comment: str = "",
    report_url: str = "",
    user_agent: str = "",
    created_at: str | None = None,
) -> dict[str, Any]:
    vote = vote.strip().lower()
    if vote not in {"like", "dislike"}:
        raise ValueError("vote must be 'like' or 'dislike'")

    item_id = feedback_identity(item)
    source = _normalize_source(str(item.get("source") or item.get("analysis", {}).get("source") or "未知"))
    title = str(item.get("title") or item.get("analysis", {}).get("title") or "").strip()
    url = str(item.get("url") or item.get("analysis", {}).get("url") or "").strip()
    published = str(item.get("published") or item.get("date") or item.get("analysis", {}).get("date") or "").strip()

    entry = {
        "item_id": item_id,
        "vote": vote,
        "source": source,
        "title": title,
        "url": url,
        "published": published,
        "report_url": report_url.strip(),
        "comment": comment.strip(),
        "user_agent": user_agent.strip(),
        "created_at": created_at or datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M"),
    }
    state.history.append(entry)
    state.decisions[item_id] = entry
    _rebuild_source_tallies(state)
    return entry


def feedback_identity(item: dict[str, Any]) -> str:
    keys = article_dedupe_keys(item)
    if keys.get("url"):
        return f"url:{keys['url']}"
    if keys.get("title_hash"):
        return f"title:{keys['title_hash']}"
    if keys.get("content_hash"):
        return f"content:{keys['content_hash']}"
    basis = json.dumps(
        {
            "title": str(item.get("title", "")),
            "source": str(item.get("source", "")),
            "published": str(item.get("published", "")),
            "url": str(item.get("url", "")),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return f"fallback:{hashlib.sha256(basis.encode('utf-8')).hexdigest()}"


def apply_feedback_adjustment(
    item: dict[str, Any],
    feedback_state: FeedbackState,
) -> dict[str, Any]:
    item_id = feedback_identity(item)
    source = _normalize_source(str(item.get("source") or item.get("analysis", {}).get("source") or "未知"))
    decision = feedback_state.decisions.get(item_id)
    status = "neutral"
    adjustment = 0
    note = ""
    hidden = False

    if decision:
        vote = str(decision.get("vote") or "").strip().lower()
        if vote == "like":
            status = "liked"
            adjustment += 2
            note = "你之前标记过喜欢"
        elif vote == "dislike":
            status = "disliked"
            adjustment -= 100
            note = "你之前标记过不相关"
            hidden = True
    else:
        tally = feedback_state.source_tallies.get(source, {"like": 0, "dislike": 0})
        like_count = int(tally.get("like", 0))
        dislike_count = int(tally.get("dislike", 0))
        net = like_count - dislike_count
        if net >= 2:
            status = "source-liked"
            adjustment += 1
            note = "这个来源之前被你多次喜欢"
        elif net <= -2:
            status = "source-disliked"
            adjustment -= 1
            note = "这个来源之前被你多次标记不相关"

    return {
        "feedback_id": item_id,
        "feedback_status": status,
        "feedback_adjustment": adjustment,
        "feedback_note": note,
        "feedback_hidden": hidden,
    }


def feedback_base_url_from_env(default: str = "") -> str:
    import os

    value = os.getenv("FEEDBACK_BASE_URL", default)
    return value.strip().rstrip("/")


def feedback_token_from_env(default: str = "") -> str:
    import os

    value = os.getenv("FEEDBACK_TOKEN", default)
    return value.strip()


def _state_from_payload(payload: dict[str, Any]) -> FeedbackState:
    decisions = payload.get("decisions") or {}
    history = payload.get("history") or payload.get("entries") or []
    source_tallies = payload.get("source_tallies") or {}

    if not isinstance(decisions, dict):
        decisions = {}
    if not isinstance(history, list):
        history = []
    if not isinstance(source_tallies, dict):
        source_tallies = {}

    state = FeedbackState(
        decisions=dict(decisions),
        history=list(history),
        source_tallies=dict(source_tallies),
    )
    _rebuild_source_tallies(state)
    return state


def _state_to_payload(state: FeedbackState) -> dict[str, Any]:
    _rebuild_source_tallies(state)
    return {
        "saved_at": datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M"),
        "decisions": state.decisions,
        "history": state.history,
        "source_tallies": state.source_tallies,
    }


def _rebuild_source_tallies(state: FeedbackState) -> None:
    tallies: dict[str, Counter[str]] = {}
    for decision in state.decisions.values():
        if not isinstance(decision, dict):
            continue
        source = _normalize_source(str(decision.get("source") or "未知"))
        vote = str(decision.get("vote") or "").strip().lower()
        if vote not in {"like", "dislike"}:
            continue
        tallies.setdefault(source, Counter())[vote] += 1

    state.source_tallies = {
        source: {"like": int(counter.get("like", 0)), "dislike": int(counter.get("dislike", 0))}
        for source, counter in tallies.items()
    }


def _resolve_feedback_path(base_dir: Path | None = None) -> Path:
    if base_dir is None:
        base_dir = Path.cwd()
    return base_dir / DEFAULT_FEEDBACK_PATH


def _normalize_source(raw: str) -> str:
    return " ".join(raw.split()).strip().lower()

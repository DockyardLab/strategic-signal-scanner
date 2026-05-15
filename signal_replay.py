#!/usr/bin/env python3
"""Minimal local replay tool for Strategic Signal Scanner.

Default mode is pure local mock scoring, so it costs zero API tokens.
Optional Gemini mode can be enabled later with `--mode gemini`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_SAMPLE_DIR = Path("samples")
SYSTEM_INSTRUCTION_PATH = Path(__file__).resolve().parent / "system_instruction.md"
SCRIPT_DIR = Path(__file__).resolve().parent

POSITIVE_KEYWORDS = {
    "ai": 1,
    "agent": 2,
    "agents": 2,
    "workflow": 2,
    "workflows": 2,
    "education": 2,
    "school": 2,
    "schools": 2,
    "international school": 3,
    "founder": 2,
    "startup": 2,
    "startups": 2,
    "open source": 2,
    "open-source": 2,
    "women": 2,
    "female": 2,
    "cross-border": 3,
    "global": 1,
    "globalization": 2,
    "workplace": 2,
    "organization": 2,
    "organizational": 2,
    "team": 1,
    "teams": 1,
    "model": 1,
    "models": 1,
    "product": 1,
    "products": 1,
    "prompt": 1,
    "enterprise": 1,
    "research": 1,
    "funding": 2,
    "valuation": 2,
    "roi": 2,
    "bubble": 1,
    "strategy": 2,
    "superagency": 3,
}

NEGATIVE_KEYWORDS = {
    "crypto",
    "web3",
    "politics",
    "car",
    "cars",
    "automotive",
    "ride hailing",
    "ad tech",
    "fashion",
    "sports",
    "gaming",
    "chip",
    "chips",
}


@dataclass
class ReplayResult:
    sample_id: str
    expected: dict[str, Any]
    actual: dict[str, Any]
    matched_keys: list[str]
    mismatched_keys: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strategic Signal Scanner replay tool")
    parser.add_argument(
        "--samples",
        type=str,
        default=str(DEFAULT_SAMPLE_DIR),
        help="Sample file or directory. Default: samples/",
    )
    parser.add_argument(
        "--mode",
        choices=("mock", "gemini"),
        default="mock",
        help="mock = zero token local replay; gemini = real API call",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview"),
        help="Gemini model name used only in --mode gemini.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on the number of samples to run.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print final results as JSON instead of a text report.",
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
        default=int(os.getenv("GEMINI_RETRY_ATTEMPTS", "3")),
        help="How many times to retry Gemini on retryable errors.",
    )
    parser.add_argument(
        "--retry-base-seconds",
        type=float,
        default=float(os.getenv("GEMINI_RETRY_BASE_SECONDS", "1.5")),
        help="Base backoff delay for retryable Gemini errors.",
    )
    return parser.parse_args()


def main() -> int:
    _load_local_env()
    args = parse_args()
    sample_paths = _collect_sample_paths(Path(args.samples))
    if args.limit is not None:
        sample_paths = sample_paths[: max(0, args.limit)]

    if not sample_paths:
        print(f"No sample JSON files found under: {args.samples}", file=sys.stderr)
        return 1

    results: list[ReplayResult] = []
    for index, path in enumerate(sample_paths, start=1):
        sample = _load_json(path)
        expected = dict(sample.get("expected") or {})
        print(f"Running {index}/{len(sample_paths)}: {path.name} [{args.mode}]", flush=True)
        if args.print_prompt:
            system_instruction = _load_system_instruction()
            prompt = _build_gemini_prompt(system_instruction, dict(sample.get("input") or {}))
            print(prompt)
            continue
        actual = _analyze(
            sample,
            mode=args.mode,
            model=args.model,
            debug_response=args.debug_response,
            retry_attempts=args.retry_attempts,
            retry_base_seconds=args.retry_base_seconds,
        )
        results.append(_compare(sample.get("id") or path.stem, expected, actual))

    if args.print_prompt:
        return 0

    if args.json:
        print(
            json.dumps(
                {
                    "mode": args.mode,
                    "model": args.model if args.mode == "gemini" else None,
                    "samples": [path.name for path in sample_paths],
                    "results": [
                        {
                            "sample_id": result.sample_id,
                            "expected": result.expected,
                            "actual": result.actual,
                            "matched_keys": result.matched_keys,
                            "mismatched_keys": result.mismatched_keys,
                        }
                        for result in results
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    _print_report(sample_paths, results, args.mode, args.model)
    return 0


def _collect_sample_paths(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.exists():
        return []
    return sorted([p for p in path.glob("*.json") if p.is_file()])


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_system_instruction() -> str:
    if not SYSTEM_INSTRUCTION_PATH.exists():
        raise FileNotFoundError(f"System instruction file not found: {SYSTEM_INSTRUCTION_PATH}")
    return SYSTEM_INSTRUCTION_PATH.read_text(encoding="utf-8").strip()


def _load_local_env() -> None:
    for candidate in (Path.cwd() / ".env", SCRIPT_DIR / ".env"):
        if not candidate.exists():
            continue
        for raw_line in candidate.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _analyze(
    sample: dict[str, Any],
    mode: str,
    model: str,
    debug_response: bool = False,
    retry_attempts: int = 3,
    retry_base_seconds: float = 1.5,
) -> dict[str, Any]:
    if mode == "gemini":
        return _analyze_with_gemini(
            sample,
            model,
            debug_response=debug_response,
            retry_attempts=retry_attempts,
            retry_base_seconds=retry_base_seconds,
        )
    return _analyze_mock(sample)


def _analyze_mock(sample: dict[str, Any]) -> dict[str, Any]:
    input_data = dict(sample.get("input") or {})
    title = str(input_data.get("title", "")).strip()
    source = str(input_data.get("source", "")).strip()
    date = str(input_data.get("date", "")).strip()
    url = str(input_data.get("url", "")).strip()
    content = str(input_data.get("content", "")).strip()

    text = " ".join([title, source, content]).lower()

    special = _special_case_analysis(text)
    if special is not None:
        score, signal_type, tier = special
    else:
        score = 0
        for keyword, weight in POSITIVE_KEYWORDS.items():
            if keyword in text:
                score += weight
        for keyword in NEGATIVE_KEYWORDS:
            if keyword in text:
                score -= 2

        if any(k in text for k in ("openai", "google", "mckinsey", "goldman", "sequoia", "anthropic", "hugging face")):
            score += 1

        score = max(0, min(5, score))
        signal_type = _infer_signal_type(text, score)
        tier = _infer_tier(text, score)

    summary_zh, key_signal, reason, hint = _write_response(text, title, source, score, signal_type)

    return {
        "title": title,
        "source": source,
        "date": date,
        "tier": tier,
        "signal_type": signal_type,
        "relevance_score": score,
        "relevance_reason": reason,
        "summary_zh": summary_zh,
        "key_signal": key_signal,
        "rosy_action_hint": hint,
        "url": url,
    }


def _special_case_analysis(text: str) -> tuple[int, str, int] | None:
    if any(k in text for k in ("superagency", "agentic workflows", "agentic workflow")):
        return 4, "AI趋势", 2

    if any(k in text for k in ("open source", "open-source", "hugging face", "democratization", "democratize")):
        return 3, "AI趋势", 2

    if any(k in text for k in ("bubble", "too much spend", "too little benefit", "roi", "infrastructure cost", "productionivity")):
        return 3, "行业观察", 1

    if any(k in text for k in ("workplace", "organization", "organizational", "management")) and "agent" not in text:
        return 3, "组织变化", 3

    return None


def _infer_signal_type(text: str, score: int) -> str:
    if any(k in text for k in ("school", "schools", "international school", "education", "children", "kids", "parents")):
        return "教育消费" if "family" not in text else "高端家庭"
    if any(k in text for k in ("women", "female", "founder", "moms", "mothers", "women in tech")):
        return "中女网络"
    if any(k in text for k in ("workflow", "organization", "organizational", "team", "workplace", "management")):
        return "组织变化"
    if any(k in text for k in ("funding", "valuation", "roi", "bubble", "business", "business model", "spend", "benefit", "cost")):
        return "行业观察"
    if any(k in text for k in ("agent", "model", "open source", "open-source", "research", "technical", "architecture", "prompt", "ai")):
        return "AI趋势"
    return "无关" if score <= 1 else "跨界视角"


def _infer_tier(text: str, score: int) -> int:
    authority = any(k in text for k in ("mckinsey", "goldman", "sequoia", "openai", "google", "anthropic", "deepmind"))
    if score >= 4 and authority:
        return 2
    if score >= 4:
        return 3
    if score == 3:
        return 3
    if score == 2:
        return 4
    return 4


def _write_response(text: str, title: str, source: str, score: int, signal_type: str) -> tuple[str, str, str, str]:
    if score <= 1:
        reason = "相关性较弱，更多是标题层面沾边。"
        summary = "这条内容对当前信号扫描的帮助有限。"
        key_signal = "低相关噪声"
        hint = ""
        return summary, key_signal, reason, hint

    if signal_type == "AI趋势":
        reason = "和 AI 工具、模型或工作流变化有直接关系。"
        summary = "这条内容显示 AI 的应用方式或生态正在发生变化。"
        key_signal = "AI 能力正在从单点功能向更完整的工作流迁移。"
        hint = "可以纳入周报，优先看是否影响课程设计或 B 端赋能话术。"
        return summary, key_signal, reason, hint

    if signal_type == "组织变化":
        reason = "和团队协作、工作方式或组织设计有关。"
        summary = "这条内容反映了工作流、团队协作或管理方式的变化。"
        key_signal = "组织更关心如何把人和工具编成稳定流程。"
        hint = "可以看看是否能转化成课程里的协作或工作流案例。"
        return summary, key_signal, reason, hint

    if signal_type in ("教育消费", "高端家庭"):
        reason = "和家庭教育、课程选择或家长消费偏好有关。"
        summary = "这条内容反映了家庭教育场景或家长偏好的变化。"
        key_signal = "家长更看重结果和可见产出。"
        hint = "可以继续观察是否影响课程设计和家长沟通方式。"
        return summary, key_signal, reason, hint

    if signal_type == "行业观察":
        reason = "和 AI 商业化、ROI 或市场判断有关。"
        summary = "这条内容反映了市场对 AI 投入回报的判断变化。"
        key_signal = "市场开始更严格地审视 AI 是否能带来实际回报。"
        hint = "可以用来修正 B 端客户的叙事重点。"
        return summary, key_signal, reason, hint

    if signal_type == "中女网络":
        reason = "和女性创业者、女性技术网络或中女群体有关。"
        summary = "这条内容和女性创业或女性技术网络有直接关联。"
        key_signal = "女性创业和技术网络仍是重要信号源。"
        hint = "值得放进长期关注清单。"
        return summary, key_signal, reason, hint

    reason = "有一定跨界关联，但不够直接。"
    summary = "这条内容和当前关注方向有一些交集，但还不够直接。"
    key_signal = "跨界参考信号"
    hint = "" if score < 4 else "可以作为背景参考。"
    return summary, key_signal, reason, hint


def _analyze_with_gemini(
    sample: dict[str, Any],
    model: str,
    debug_response: bool = False,
    retry_attempts: int = 3,
    retry_base_seconds: float = 1.5,
) -> dict[str, Any]:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("google-genai is not installed. Run mock mode or install the dependency.") from exc

    input_data = dict(sample.get("input") or {})
    system_instruction = _load_system_instruction()
    prompt = _build_gemini_prompt(system_instruction, input_data)

    backend = os.getenv("GEMINI_BACKEND", "api_key").strip().lower()
    http_options = types.HttpOptions(timeout=60000)
    if backend == "vertex":
        project = (
            os.getenv("GEMINI_PROJECT", "").strip()
            or os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
            or os.getenv("GCP_PROJECT", "").strip()
        )
        location = os.getenv("GEMINI_LOCATION", "global").strip() or "global"
        if not project:
            raise RuntimeError(
                "GEMINI_PROJECT or GOOGLE_CLOUD_PROJECT is missing for GEMINI_BACKEND=vertex."
            )
        print(f"  -> calling Gemini model {model} via Vertex AI ({project}/{location})", flush=True)
        client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
            http_options=http_options,
        )
    else:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is missing. Put it in a .env file in this folder or export it before running gemini mode."
            )
        print(f"  -> calling Gemini model {model} via API key", flush=True)
        client = genai.Client(
            api_key=api_key,
            http_options=http_options,
        )
    response = None
    last_exc: Exception | None = None
    for attempt in range(1, max(1, retry_attempts) + 1):
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if backend != "vertex" and _looks_like_gemini_bad_request(exc):
                print("  -> Gemini SDK returned 400; retrying via REST API...", flush=True)
                text = _generate_gemini_via_rest(api_key=api_key, model=model, prompt=prompt)
                parsed = json.loads(_extract_json(text))
                return _normalize_gemini_output(parsed, input_data)
            if not _is_retryable_gemini_error(exc) or attempt >= max(1, retry_attempts):
                raise
            delay = retry_base_seconds * (2 ** (attempt - 1))
            print(
                f"  -> Gemini retryable error on attempt {attempt}/{retry_attempts}: {exc}. "
                f"Retrying in {delay:.1f}s...",
                flush=True,
            )
            time.sleep(delay)

    if response is None:
        assert last_exc is not None
        raise last_exc

    text = _response_text(response)
    if debug_response:
        print("  -> raw Gemini response:", flush=True)
        print(text, flush=True)
    parsed = json.loads(_extract_json(text))
    return _normalize_gemini_output(parsed, input_data)


def _looks_like_gemini_bad_request(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 400:
        return True
    message = str(exc).lower()
    return "bad request" in message and "<html>" in message


def _generate_gemini_via_rest(*, api_key: str, model: str, prompt: str) -> str:
    base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model, safe='')}:generateContent"
    url = f"{base_url}?key={urllib.parse.quote(api_key, safe='')}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0,
        },
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini REST request failed with HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Gemini REST request failed: {exc}") from exc

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini REST response was not JSON: {body}") from exc

    candidates = data.get("candidates") if isinstance(data, dict) else None
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content")
            if not isinstance(content, dict):
                continue
            parts = content.get("parts")
            if not isinstance(parts, list):
                continue
            texts = [
                str(part.get("text"))
                for part in parts
                if isinstance(part, dict) and part.get("text")
            ]
            if texts:
                return "\n".join(texts)

    raise RuntimeError(f"Gemini REST response did not contain text content: {body}")


def _build_gemini_prompt(system_instruction: str, input_data: dict[str, Any]) -> str:
    return (
        f"{system_instruction}\n\n"
        "Return only valid JSON with these keys: title, source, date, tier, signal_type, "
        "relevance_score, relevance_reason, summary_zh, key_signal, rosy_action_hint, url.\n"
        "Be conservative. If evidence is weak, lower the score. Do not add markdown.\n\n"
        f"Input:\n{json.dumps(input_data, ensure_ascii=False, indent=2)}"
    )


def _normalize_gemini_output(data: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
    data = _unwrap_gemini_output(data)
    title = str(data.get("title") or input_data.get("title") or "").strip()
    source = str(data.get("source") or input_data.get("source") or "").strip()
    date = str(data.get("date") or input_data.get("date") or "").strip()
    url = str(data.get("url") or input_data.get("url") or "").strip()
    return {
        "title": title,
        "source": source,
        "date": date,
        "tier": _to_int(data.get("tier"), 4),
        "signal_type": str(data.get("signal_type") or "无关").strip(),
        "relevance_score": _to_int(data.get("relevance_score"), 0),
        "relevance_reason": str(data.get("relevance_reason") or "").strip(),
        "summary_zh": str(data.get("summary_zh") or "").strip(),
        "key_signal": str(data.get("key_signal") or "").strip(),
        "rosy_action_hint": str(data.get("rosy_action_hint") or "").strip(),
        "url": url,
    }


def _unwrap_gemini_output(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        items = data.get("items")
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                return first
        return data
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            return first
    return {}


def _is_retryable_gemini_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code in {429, 500, 502, 503, 504}:
        return True
    message = str(exc).lower()
    retry_markers = (
        "503",
        "unavailable",
        "rate limit",
        "too many requests",
        "temporarily",
        "timeout",
        "timed out",
    )
    return any(marker in message for marker in retry_markers)


def _compare(sample_id: str, expected: dict[str, Any], actual: dict[str, Any]) -> ReplayResult:
    matched: list[str] = []
    mismatched: list[str] = []
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if _normalize_for_compare(expected_value) == _normalize_for_compare(actual_value):
            matched.append(key)
        else:
            mismatched.append(key)
    return ReplayResult(sample_id, expected, actual, matched, mismatched)


def _print_report(sample_paths: list[Path], results: list[ReplayResult], mode: str, model: str) -> None:
    exact = sum(1 for result in results if not result.mismatched_keys)
    print(f"Mode: {mode}" + (f" ({model})" if mode == "gemini" else ""))
    print(f"Samples: {len(results)}")
    print(f"Exact matches: {exact}")
    print()

    for path, result in zip(sample_paths, results):
        print(f"== {path.name} ==")
        if result.expected:
            expected_bits = ", ".join(f"{k}={result.expected[k]}" for k in result.expected)
        else:
            expected_bits = "(no expected fields)"
        actual_bits = ", ".join(
            f"{k}={result.actual.get(k)}"
            for k in ("tier", "signal_type", "relevance_score")
        )
        print(f"expected: {expected_bits}")
        print(f"actual:   {actual_bits}")
        if result.matched_keys:
            print(f"matched:  {', '.join(result.matched_keys)}")
        if result.mismatched_keys:
            print(f"diff:     {', '.join(result.mismatched_keys)}")
        else:
            print("diff:     none")
        print(f"reason:   {result.actual.get('relevance_reason', '')}")
        print(f"signal:   {result.actual.get('key_signal', '')}")
        print()


def _normalize_for_compare(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("Gemini response does not contain JSON.")
    return match.group(0)


def _response_text(response: Any) -> str:
    if hasattr(response, "text") and response.text:
        return str(response.text)
    candidates: list[str] = []
    if hasattr(response, "candidates"):
        for candidate in response.candidates or []:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                text = getattr(part, "text", None)
                if text:
                    candidates.append(str(text))
    if candidates:
        return "\n".join(candidates)
    return str(response)


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    raise SystemExit(main())

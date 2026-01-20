from __future__ import annotations

from pathlib import Path
from typing import Any

from talentmatch.infra.llm import AzureLlmProvider
from util.common import assert_true, build_check_context, load_settings_from_context, print_fail, print_ok


def extract_text(response: Any) -> str:
    if response is None:
        return ""
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(response, str):
        return response.strip()
    return ""


def run() -> int:
    """
    Public contract: validates AzureLlmProvider can create a chat model and return a pong-like response.
    :return: process exit code (0 success, 1 failure)
    """

    context = build_check_context(Path(__file__))
    settings = load_settings_from_context(context)
    if settings is None:
        return 1

    try:
        provider = AzureLlmProvider(settings)
        print_ok("AzureLlmProvider(settings) succeeded")
    except Exception as exc:
        print_fail(f"AzureLlmProvider(settings) failed: {exc}")
        return 1

    try:
        model = provider.chat("cv_markdown")
        print_ok('provider.chat("cv_markdown") succeeded')
    except Exception as exc:
        print_fail(f'provider.chat("cv_markdown") failed: {exc}')
        return 1

    prompt = "Ping. Reply with exactly: pong"

    try:
        response = model.invoke(prompt)
        print_ok("model.invoke(prompt) succeeded")
    except Exception as exc:
        print_fail(f"model.invoke(prompt) failed: {exc}")
        return 1

    text = extract_text(response)
    ok = assert_true(bool(text), ok="model returned non-empty content", fail="model returned empty content")
    if not ok:
        return 1

    normalized = text.strip().lower().strip(".! ")
    ok = assert_true(
        normalized.startswith("pong") or normalized == "pong",
        ok='received "pong" response',
        fail=f'unexpected response: "{text}"',
    )
    if not ok:
        return 1

    print_ok(f"sample response: {text[:120]}")
    print_ok("LLM provider checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

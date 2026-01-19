from __future__ import annotations

from pathlib import Path
from typing import Any

from util.common import assert_true, build_check_context, load_settings_from_context, print_fail, print_ok
from talentmatch.infra.llm import AzureChatOpenAIProvider


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
    """Public contract: validates LLM provider can create a chat model and run a minimal prompt."""

    context = build_check_context(Path(__file__))
    settings = load_settings_from_context(context)
    if settings is None:
        return 1

    try:
        provider = AzureChatOpenAIProvider(settings)
        print_ok("AzureChatOpenAIProvider(settings) succeeded")
    except Exception as exc:
        print_fail(f"AzureChatOpenAIProvider(settings) failed: {exc}")
        return 1

    try:
        model = provider.get_chat_model("json_to_markdown")
        print_ok('provider.get_chat_model("json_to_markdown") succeeded')
    except Exception as exc:
        print_fail(f'provider.get_chat_model("json_to_markdown") failed: {exc}')
        return 1

    prompt = "Ping. Reply with a single short word."

    try:
        response = model.invoke(prompt)
        print_ok("model.invoke(prompt) succeeded")
    except Exception as first_exc:
        try:
            from langchain_core.messages import HumanMessage

            response = model.invoke([HumanMessage(content=prompt)])
            print_ok("model.invoke([HumanMessage]) succeeded")
        except Exception as second_exc:
            print_fail(f"model.invoke failed: {first_exc} | {second_exc}")
            return 1

    text = extract_text(response)
    ok = assert_true(bool(text), ok="model returned non-empty content", fail="model returned empty content")
    if not ok:
        return 1

    print_ok(f"sample response: {text[:120]}")
    print_ok("LLM provider checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

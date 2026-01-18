from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from talentmatch.infra.llm import AzureChatOpenAIProvider
from talentmatch.runtime import load_settings


@dataclass(frozen=True)
class CheckContext:
    repo_root: Path
    settings_path: Path


def print_ok(message: str) -> None:
    print(f"✅ {message}")


def print_fail(message: str) -> None:
    print(f"❌ {message}")


def assert_true(condition: bool, *, ok: str, fail: str) -> bool:
    if condition:
        print_ok(ok)
        return True
    print_fail(fail)
    return False


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
    context = CheckContext(
        repo_root=Path(__file__).resolve().parents[1],
        settings_path=Path(__file__).resolve().parents[1] / "configs" / "settings.toml",
    )

    if not context.settings_path.exists():
        print_fail(f'Settings TOML not found: "{context.settings_path}"')
        return 1

    try:
        settings = load_settings(str(context.settings_path))
        print_ok("runtime.load_settings() succeeded")
    except Exception as exc:
        print_fail(f"runtime.load_settings() failed: {exc}")
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
    response = None

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

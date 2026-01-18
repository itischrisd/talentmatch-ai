from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class JsonCoverageChecklist:
    """Public contract: produces a list of dot-paths for every JSON element (including list markers)."""

    @staticmethod
    def build(payload: Mapping[str, Any]) -> str:
        paths = _flatten_json_paths(payload)
        return "\n".join([f"- {path}" for path in paths])


@dataclass(frozen=True)
class PromptTemplateRenderer:
    """Public contract: renders a prompt template using a JSON payload and a coverage checklist."""

    template: str

    def render(self, payload: Mapping[str, Any]) -> str:
        checklist = JsonCoverageChecklist().build(payload)
        json_text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        return self.template.format(checklist=checklist, payload=json_text).strip()


def strip_markdown_code_fences(text: str) -> str:
    """Public contract: removes common Markdown code fence wrappers while keeping content intact."""
    cleaned = text.replace("```markdown", "").replace("```", "")
    return cleaned.strip()


def coerce_llm_text(response: Any) -> str:
    """Public contract: extracts content from typical LangChain responses."""
    if response is None:
        return ""
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(response, str):
        return response.strip()
    return ""


def _flatten_json_paths(value: Any) -> list[str]:
    paths: list[str] = []
    _walk_json(value, prefix="", out=paths)
    return paths


def _walk_json(value: Any, *, prefix: str, out: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_str = str(key)
            child_prefix = f"{prefix}.{key_str}" if prefix else key_str
            _walk_json(child, prefix=child_prefix, out=out)
        if prefix:
            out.append(prefix)
        return

    if isinstance(value, list):
        item_prefix = f"{prefix}[]" if prefix else "[]"
        if not value:
            out.append(item_prefix)
            return
        for item in value:
            _walk_json(item, prefix=item_prefix, out=out)
        out.append(item_prefix)
        return

    if prefix:
        out.append(prefix)

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from talentmatch.infra.llm import AzureChatOpenAIProvider
from talentmatch.infra.llm.azure_openai import LlmUseCaseName
from talentmatch.infra.llm.prompts import PromptTemplateRenderer, coerce_llm_text, strip_markdown_code_fences
from talentmatch.runtime import load_prompts


@dataclass(frozen=True)
class StoreCvStructMarkdownResult:
    """Result of storing a CV Markdown document under a UUID-based filename."""
    uuid: str


class CvStructMarkdownStore:
    """Stores the Markdown representation of a structured CV under {uuid}.md using an LLM."""

    def __init__(
            self,
            settings: Any,
            *,
            provider: AzureChatOpenAIProvider | None = None,
            use_case: LlmUseCaseName = "json_to_markdown",
    ) -> None:
        self._settings = settings
        self._provider = provider or AzureChatOpenAIProvider(settings)
        self._use_case = use_case
        self._base_dir = Path(settings.paths.cv_markdown_dir)

    def store(self, uuid: str, cv_struct: Mapping[str, Any]) -> StoreCvStructMarkdownResult:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._base_dir / f"{uuid}.md"

        prompts = load_prompts()
        template = prompts.datasets.cv_json_to_markdown
        prompt_text = PromptTemplateRenderer(template=template).render(cv_struct)

        model = self._provider.get_chat_model(self._use_case)
        response = model.invoke(prompt_text)
        markdown = strip_markdown_code_fences(coerce_llm_text(response))

        if not markdown:
            raise ValueError("LLM returned empty Markdown for CV")

        normalized = markdown.lstrip()
        if not normalized.startswith("# "):
            markdown = "# CV\n\n" + normalized

        if not markdown.endswith("\n"):
            markdown += "\n"

        file_path.write_text(markdown, encoding="utf-8")
        return StoreCvStructMarkdownResult(uuid=uuid)

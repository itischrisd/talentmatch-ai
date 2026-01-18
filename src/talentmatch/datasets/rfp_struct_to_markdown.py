from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from talentmatch.infra.llm import AzureChatOpenAIProvider
from talentmatch.infra.llm.azure_openai import LlmUseCaseName
from talentmatch.infra.llm.prompts import PromptTemplateRenderer, coerce_llm_text, strip_markdown_code_fences
from talentmatch.runtime import load_prompts


@dataclass(frozen=True)
class StoreRfpStructMarkdownResult:
    """Result of storing an RFP Markdown document under a UUID-based filename."""
    uuid: str


class RfpStructMarkdownStore:
    """Stores the Markdown representation of a structured RFP under {uuid}.md using an LLM."""

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
        self._base_dir = Path(settings.paths.rfp_markdown_dir)

    def store(self, uuid: str, rfp_struct: Mapping[str, Any]) -> StoreRfpStructMarkdownResult:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._base_dir / f"{uuid}.md"

        prompts = load_prompts()
        template = prompts.datasets.rfp_json_to_markdown
        prompt_text = PromptTemplateRenderer(template=template).render(rfp_struct)

        model = self._provider.get_chat_model(self._use_case)
        response = model.invoke(prompt_text)
        markdown = strip_markdown_code_fences(coerce_llm_text(response))

        if not markdown:
            raise ValueError("LLM returned empty Markdown for RFP")

        file_path.write_text(markdown + ("\n" if not markdown.endswith("\n") else ""), encoding="utf-8")
        return StoreRfpStructMarkdownResult(uuid=uuid)

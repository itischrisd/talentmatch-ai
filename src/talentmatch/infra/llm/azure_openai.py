from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from talentmatch.config.config_models import Settings

LlmUseCaseName = Literal[
    "dataset_generation",
    "json_to_markdown",
    "agent_orchestrator",
    "matching_judge",
]


@dataclass(frozen=True)
class _ResolvedAzureChatModelConfig:
    endpoint: str
    api_key: str
    api_version: str
    deployment: str
    temperature: float
    max_tokens: int
    top_p: float
    timeout_s: int


class AzureChatOpenAIProvider:
    """
    Central factory for AzureChatOpenAI instances configured by runtime settings
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: dict[str, Any] = {}

    def get_chat_model(self, use_case: LlmUseCaseName) -> Any:
        """
        Return a cached AzureChatOpenAI instance for the given use-case
        :param use_case: the LLM use-case name
        :return: AzureChatOpenAI instance
        """

        if use_case in self._cache:
            return self._cache[use_case]

        model_cls = self._import_azure_chat_openai()
        resolved = self._resolve_chat_model_config(use_case)

        model = model_cls(
            azure_endpoint=resolved.endpoint,
            api_key=resolved.api_key,
            api_version=resolved.api_version,
            azure_deployment=resolved.deployment,
            temperature=resolved.temperature,
            max_tokens=resolved.max_tokens,
            top_p=resolved.top_p,
            timeout=float(resolved.timeout_s),
        )

        self._cache[use_case] = model
        return model

    @staticmethod
    def _import_azure_chat_openai() -> Any:
        from langchain_openai import AzureChatOpenAI

        return AzureChatOpenAI

    def _resolve_chat_model_config(self, use_case: LlmUseCaseName) -> _ResolvedAzureChatModelConfig:
        azure = self._settings.azure_openai
        use_case_cfg = getattr(self._settings.llm.use_cases, use_case)

        deployment = azure.chat_deployment if use_case_cfg.deployment == "default" else use_case_cfg.deployment

        return _ResolvedAzureChatModelConfig(
            endpoint=azure.endpoint,
            api_key=azure.api_key,
            api_version=azure.api_version,
            deployment=deployment,
            temperature=use_case_cfg.temperature,
            max_tokens=use_case_cfg.max_tokens,
            top_p=use_case_cfg.top_p,
            timeout_s=use_case_cfg.request_timeout_s,
        )

from __future__ import annotations

from typing import Any

from langchain_openai import AzureChatOpenAI

from talentmatch.config.config_models import Settings


class AzureLlmProvider:
    """
    Creates and caches AzureChatOpenAI clients configured by runtime settings
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: dict[str, AzureChatOpenAI] = {}

    def chat(self, use_case: str) -> AzureChatOpenAI:
        """
        Create or retrieve a cached AzureChatOpenAI client for the specified use-case
        :param use_case: the use-case name as defined in settings.llm.use_cases
        :return: AzureChatOpenAI client
        """

        cached = self._cache.get(use_case)
        if cached is not None:
            return cached

        use_case_cfg = self._settings.llm.use_cases[use_case]
        azure = self._settings.azure_openai

        deployment = azure.chat_deployment if use_case_cfg.model == "default" else use_case_cfg.model

        client = AzureChatOpenAI(
            azure_endpoint=azure.endpoint,
            api_key=azure.api_key,
            api_version=azure.api_version,
            azure_deployment=deployment,
            temperature=use_case_cfg.temperature,
            max_tokens=use_case_cfg.max_tokens,
            top_p=use_case_cfg.top_p,
            timeout=float(use_case_cfg.request_timeout_s),
        )

        self._cache[use_case] = client
        return client

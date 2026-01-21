from __future__ import annotations

from typing import Any

from langchain.agents import create_react_agent
from langchain_core.prompts import BasePromptTemplate, PromptTemplate

from talentmatch.infra.llm import AzureLlmProvider
from talentmatch.tools.knowledge_graph_tools import ingest_programmer_cvs


def create_kg_agent(
    *,
    llm_provider: AzureLlmProvider,
    prompt_text: str,
    use_case: str = "kg_agent",
) -> Any:
    """
    Create a ReAct agent for Knowledge Graph ingestion tasks.

    :param llm_provider: LLM provider instance (configured via settings)
    :param prompt_text: ReAct prompt template text (must include required variables)
    :param use_case: LLM use-case name from settings.llm.use_cases
    :return: LangChain Runnable/agent created by create_react_agent
    """

    llm = llm_provider.chat(use_case)
    prompt: BasePromptTemplate = PromptTemplate.from_template(prompt_text)

    return create_react_agent(
        llm=llm,
        tools=[ingest_programmer_cvs],
        prompt=prompt,
    )

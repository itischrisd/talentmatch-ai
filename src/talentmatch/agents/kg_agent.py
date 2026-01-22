from __future__ import annotations

from typing import Any

from langgraph.prebuilt import create_react_agent

from talentmatch.infra.llm import AzureLlmProvider
from talentmatch.tools.knowledge_graph_tools import ingest_files


def create_kg_agent(
        *,
        llm_provider: AzureLlmProvider,
        prompt_text: str,
        use_case: str = "kg_agent",
        name: str = "kg_agent",
) -> Any:
    """
    Create a ReAct agent for Knowledge Graph ingestion tasks (LangGraph prebuilt agent).

    :param llm_provider: LLM provider instance (configured via settings)
    :param prompt_text: system prompt text for the agent
    :param use_case: LLM use-case name from settings.llm.use_cases
    :param name: stable agent name used by the supervisor for routing/handoff
    :return: LangGraph runnable agent
    """

    llm = llm_provider.chat(use_case)

    return create_react_agent(
        model=llm,
        tools=[ingest_files],
        name=name,
        prompt=prompt_text,
    )

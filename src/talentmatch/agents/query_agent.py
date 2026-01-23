from __future__ import annotations

from typing import Any

from langgraph.prebuilt import create_react_agent

from talentmatch.infra.llm import AzureLlmProvider
from talentmatch.tools.knowledge_graph_tools import query_knowledge_graph


def create_query_agent(
        *,
        llm_provider: AzureLlmProvider,
        prompt_text: str,
        use_case: str = "query_agent",
        name: str = "query_agent",
) -> Any:
    """
    Create a ReAct agent for Knowledge Graph querying tasks.

    :param llm_provider: LLM provider instance (configured via settings)
    :param prompt_text: system prompt text for the agent
    :param use_case: LLM use-case name from settings.llm.use_cases
    :param name: stable agent name used by the supervisor for routing/handoff
    :return: LangGraph runnable agent
    """

    llm = llm_provider.chat(use_case)

    return create_react_agent(
        model=llm,
        tools=[query_knowledge_graph],
        name=name,
        prompt=prompt_text,
    )

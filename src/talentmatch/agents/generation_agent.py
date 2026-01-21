from __future__ import annotations

from typing import Any

from langgraph.prebuilt import create_react_agent

from talentmatch.infra.llm import AzureLlmProvider
from talentmatch.tools.generation_tools import generate_dataset, generate_single_rfp


def create_generation_agent(
        *,
        llm_provider: AzureLlmProvider,
        prompt_text: str,
        use_case: str = "generation_agent",
        name: str = "generation_agent",
) -> Any:
    """
    Create a ReAct agent for dataset / RFP generation (LangGraph prebuilt agent).

    NOTE:
    - langgraph-supervisor expects LangGraph-compatible agents that operate on {"messages": ...}
    - prompt_text is treated as a system prompt for the LangGraph ReAct agent

    :param llm_provider: LLM provider instance (configured via settings)
    :param prompt_text: system prompt text for the agent
    :param use_case: LLM use-case name from settings.llm.use_cases
    :param name: stable agent name used by the supervisor for routing/handoff
    :return: LangGraph runnable agent
    """

    llm = llm_provider.chat(use_case)

    return create_react_agent(
        model=llm,
        tools=[generate_dataset, generate_single_rfp],
        name=name,
        prompt=prompt_text,
    )

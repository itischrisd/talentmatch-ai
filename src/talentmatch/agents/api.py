from __future__ import annotations

from typing import Any

from langgraph_supervisor import create_supervisor

from talentmatch.config import load_prompts, load_settings, Prompts
from talentmatch.infra.llm import AzureLlmProvider
from .generation_agent import create_generation_agent as _create_generation_agent
from .kg_agent import create_kg_agent as _create_kg_agent


def _create_agents(prompts: Prompts, llm_provider: AzureLlmProvider) -> list[Any]:
    """
    Main entry point for the agents module.

    Loads settings and prompts from TOML, builds the LLM provider, and creates
    the configured agents with their prompts and tools.

    :return: dict with agent instances keyed by name
    """

    generation_agent = _create_generation_agent(
        llm_provider=llm_provider,
        prompt_text=prompts.agents.generation_react,
        use_case="generation_agent",
    )

    kg_agent = _create_kg_agent(
        llm_provider=llm_provider,
        prompt_text=prompts.agents.kg_react,
        use_case="kg_agent",
    )

    return [
        generation_agent,
        kg_agent,
    ]


def create_supervised_graph() -> Any:
    """
    Create agent graph with supervisor
    :return: agent graph instance
    """

    settings = load_settings()
    prompts = load_prompts()
    llm_provider = AzureLlmProvider(settings)
    agents = _create_agents(prompts, llm_provider)

    supervisor = create_supervisor(
        agents=agents,
        model=llm_provider.chat("supervisor")
    )

    return supervisor.compile()

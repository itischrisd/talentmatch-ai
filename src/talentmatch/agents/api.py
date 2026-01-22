from __future__ import annotations

import logging
from typing import Any

from langgraph_supervisor import create_supervisor

from talentmatch.config import Prompts, load_prompts, load_settings
from talentmatch.infra.llm import AzureLlmProvider
from .generation_agent import create_generation_agent as _create_generation_agent
from .kg_agent import create_kg_agent as _create_kg_agent

logger = logging.getLogger(__name__)


def _create_agents(prompts: Prompts, llm_provider: AzureLlmProvider) -> list[Any]:
    """
    Create worker agents for the supervisor.

    :param prompts: prompts loaded from configs/prompts.toml
    :param llm_provider: configured LLM provider
    :return: list of LangGraph-compatible agent runnables (named)
    """

    logger.info("Creating worker agents: generation_agent, kg_agent")

    generation_agent = _create_generation_agent(
        llm_provider=llm_provider,
        prompt_text=prompts.agents.generation_react,
        use_case="generation_agent",
        name="generation_agent",
    )

    kg_agent = _create_kg_agent(
        llm_provider=llm_provider,
        prompt_text=prompts.agents.kg_react,
        use_case="kg_agent",
        name="kg_agent",
    )

    return [generation_agent, kg_agent]


def create_supervised_graph() -> Any:
    """
    Create agent graph with supervisor.

    IMPORTANT:
    - worker agents must be LangGraph-compatible and have stable names
    - "supervisor" must exist in settings.llm.use_cases

    :return: compiled supervisor graph
    """

    logger.info("Creating supervisor graph")

    settings = load_settings()
    prompts = load_prompts()
    llm_provider = AzureLlmProvider(settings)

    agents = _create_agents(prompts, llm_provider)

    supervisor = create_supervisor(
        agents=agents,
        model=llm_provider.chat("supervisor"),
        prompt=prompts.agents.supervisor,
    )

    compiled = supervisor.compile()
    logger.info("Supervisor graph compiled")
    return compiled

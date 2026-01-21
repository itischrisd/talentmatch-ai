from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .generation_tools import GenerationTools
from .knowledge_graph_tools import KnowledgeGraphTools

ToolCallable = Callable[..., Any]

__all__ = [
    "GenerationTools",
    "KnowledgeGraphTools",
    "ToolCallable",
    "all_tools",
]


def all_tools() -> tuple[ToolCallable, ...]:
    """
    Return all tool callables exposed by this package.

    :return: Tuple of callables compatible with LangChain/LangGraph tool binding.
    """
    return (
        *GenerationTools.toolset(),
        *KnowledgeGraphTools.toolset(),
    )

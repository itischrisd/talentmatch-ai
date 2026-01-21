from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

ToolCallable = Callable[..., Any]

__all__ = [
    "GenerationTools",
]


class GenerationTools:
    """
    Toolset exposing public operations from the generation module.
    """

    @staticmethod
    def toolset() -> tuple[ToolCallable, ...]:
        """
        Return the tool callables exposed by this toolset.

        :return: Tuple of tool callables.
        """
        return (
            GenerationTools.generate_dataset,
            GenerationTools.generate_single_rfp,
        )

    @staticmethod
    def generate_dataset() -> dict[str, Any]:
        """
        Generate the complete dataset based on configured policies and counts.

        :return: Dictionary with generated dataset details.
        """
        from talentmatch.generation import generate_dataset as _generate_dataset

        logger.info("Tool call: generation.generate_dataset")
        return _generate_dataset()

    @staticmethod
    def generate_single_rfp() -> dict[str, Any]:
        """
        Generate a single RFP record along with Markdown and PDF output.

        :return: Dictionary with generated RFP details.
        """
        from talentmatch.generation import generate_single_rfp as _generate_single_rfp

        logger.info("Tool call: generation.generate_single_rfp")
        return _generate_single_rfp()

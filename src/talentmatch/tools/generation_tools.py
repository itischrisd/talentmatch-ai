from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def generate_dataset() -> dict[str, Any]:
    """
    Generate dataset artifacts (programmers, projects, CV PDFs, and RFP PDFs).

    :return: Dictionary with generated dataset details.
    """
    from talentmatch.generation import generate_dataset as _generate_dataset

    logger.info("Tool call: generation.generate_dataset")
    return _generate_dataset()


@tool
def generate_single_rfp() -> dict[str, Any]:
    """
    Generate a single RFP record along with Markdown and PDF output.

    :return: Dictionary with generated RFP details.
    """
    from talentmatch.generation import generate_single_rfp as _generate_single_rfp

    logger.info("Tool call: generation.generate_single_rfp")
    return _generate_single_rfp()


@tool
def generate_one_cv() -> dict[str, Any]:
    """
    Generate a single programmer CV (Markdown + PDF) and save it to the configured programmers_dir.

    :return: Dictionary with generated CV details.
    """
    from talentmatch.generation import generate_one_cv as _generate_one_cv

    logger.info("Tool call: generation.generate_one_cv")
    return _generate_one_cv()

from __future__ import annotations

import logging
import sys

from talentmatch.config.config_models import Settings


def configure_logging(*, settings: Settings) -> None:
    """
    Configure application-wide logging so INFO-level messages are visible when running under Streamlit.

    Streamlit tends to show only WARNING+ by default (unless logging is configured). This function forces a consistent
    root logger configuration and applies a small amount of noise reduction for common chatty libraries.
    """

    level_name = str(settings.logging.level).upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

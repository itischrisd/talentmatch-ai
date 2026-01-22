from __future__ import annotations

from talentmatch.config import load_settings
from talentmatch.infra.logging import configure_logging
from talentmatch.ui import run


def _main() -> None:
    settings = load_settings()
    configure_logging(settings=settings)
    run()


_main()

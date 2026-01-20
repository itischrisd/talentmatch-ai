from __future__ import annotations

from typing import Final

ALLOWED_NODES: Final[tuple[str, ...]] = (
    "Person",
    "Company",
    "University",
    "Skill",
    "Technology",
    "Project",
    "Certification",
    "Location",
    "JobTitle",
    "Industry",
)

ALLOWED_RELATIONSHIPS: Final[tuple[tuple[str, str, str], ...]] = (
    ("Person", "WORKED_AT", "Company"),
    ("Person", "STUDIED_AT", "University"),
    ("Person", "HAS_SKILL", "Skill"),
    ("Person", "LOCATED_IN", "Location"),
    ("Person", "HOLDS_POSITION", "JobTitle"),
    ("Person", "WORKED_ON", "Project"),
    ("Person", "EARNED", "Certification"),
    ("JobTitle", "AT_COMPANY", "Company"),
    ("Project", "USED_TECHNOLOGY", "Technology"),
    ("Project", "FOR_COMPANY", "Company"),
    ("Company", "IN_INDUSTRY", "Industry"),
    ("Skill", "RELATED_TO", "Technology"),
    ("Certification", "ISSUED_BY", "Company"),
    ("University", "LOCATED_IN", "Location"),
)

NODE_PROPERTIES: Final[tuple[str, ...]] = (
    "start_date",
    "end_date",
    "level",
    "years_experience",
)

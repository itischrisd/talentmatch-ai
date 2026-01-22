from __future__ import annotations

from typing import Final

ALLOWED_NODES: Final[tuple[str, ...]] = (
    "Certification",
    "Company",
    "Industry",
    "JobTitle",
    "Location",
    "Person",
    "Project",
    "RFP",
    "Skill",
    "Technology",
    "University",
)

ALLOWED_RELATIONSHIPS: Final[tuple[tuple[str, str, str], ...]] = (
    ("Certification", "ISSUED_BY", "Company"),
    ("Company", "IN_INDUSTRY", "Industry"),
    ("JobTitle", "AT_COMPANY", "Company"),
    ("Person", "EARNED", "Certification"),
    ("Person", "HAS_SKILL", "Skill"),
    ("Person", "HOLDS_POSITION", "JobTitle"),
    ("Person", "LOCATED_IN", "Location"),
    ("Person", "STUDIED_AT", "University"),
    ("Person", "WORKED_AT", "Company"),
    ("Person", "WORKED_ON", "Project"),
    ("Person", "ASSIGNED_TO", "Project"),
    ("Project", "FOR_COMPANY", "Company"),
    ("Project", "USED_TECHNOLOGY", "Technology"),
    ("RFP", "REQUIRES", "Skill"),
    ("Skill", "RELATED_TO", "Technology"),
    ("University", "LOCATED_IN", "Location"),
)

NODE_PROPERTIES: Final[tuple[str, ...]] = (
    "start_date",
    "end_date",
    "level",
    "years_experience",
    "allocation_percent",
)

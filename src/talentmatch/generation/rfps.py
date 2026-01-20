from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

from faker import Faker

from talentmatch.config.config_models import DatasetsSettings


class RfpGenerator:
    """
    Generates RFP records
    """

    def __init__(self, faker: Faker, datasets: DatasetsSettings) -> None:
        self._faker = faker
        self._datasets = datasets

    def generate(self, count: int) -> list[dict[str, Any]]:
        """
        Generate RFP record
        :param count: number of RFPs to generate
        :return: list of generated RFP records
        """

        policy = self._datasets.rfps

        rfps: list[dict[str, Any]] = []
        for idx in range(1, count + 1):
            start = self._date_from_today_offset(policy.start_date_offset_days.pick())
            project_type = random.choice(policy.rfp_types)

            rfps.append(
                {
                    "id": f"RFP-{idx:03d}",
                    "title": policy.title_template.format(project_type=project_type),
                    "client": random.choice(policy.clients),
                    "description": policy.description_template.format(project_type=project_type),
                    "project_type": project_type,
                    "duration_months": policy.duration_months.pick(),
                    "team_size": policy.team_size.pick(),
                    "budget_range": random.choice(policy.budget_ranges),
                    "start_date": start.isoformat(),
                    "requirements": self._generate_requirements(),
                    "location": self._faker.city(),
                    "remote_allowed": random.random() < float(policy.remote_allowed_probability),
                }
            )

        return rfps

    def _generate_requirements(self) -> list[dict[str, Any]]:
        policy = self._datasets.rfps.requirements
        count = min(policy.requirement_count.pick(), len(policy.skills))
        chosen = random.sample(policy.skills, count)

        requirements: list[dict[str, Any]] = []
        for skill_name in chosen:
            preferred_count = min(int(policy.preferred_certifications_max_count), len(policy.preferred_certifications))
            preferred = random.sample(policy.preferred_certifications, random.randint(0, preferred_count))

            requirements.append(
                {
                    "skill_name": skill_name,
                    "min_proficiency": random.choice(policy.min_proficiency_levels),
                    "is_mandatory": random.random() < float(policy.mandatory_probability),
                    "preferred_certifications": preferred,
                }
            )

        return requirements

    @staticmethod
    def _date_from_today_offset(offset_days: int) -> date:
        return date.today() + timedelta(days=int(offset_days))

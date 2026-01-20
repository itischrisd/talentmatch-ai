from __future__ import annotations

import random
from typing import Any

from faker import Faker

from talentmatch.config.config_models import DatasetsSettings


class ProgrammerGenerator:
    """
    Generates programmer profiles
    """

    def __init__(self, faker: Faker, datasets: DatasetsSettings) -> None:
        self._faker = faker
        self._datasets = datasets

    def generate(self, count: int) -> list[dict[str, Any]]:
        """
        Generate programmer profile records
        :param count: number of programmer profiles to generate
        :return: list of programmer profile records
        """

        profiles: list[dict[str, Any]] = []
        for idx in range(1, count + 1):
            profiles.append(
                {
                    "id": idx,
                    "name": self._faker.name(),
                    "email": self._faker.email(),
                    "location": self._faker.city(),
                    "skills": self._generate_skills(),
                    "projects": self._generate_project_names(),
                    "certifications": self._generate_certifications(),
                }
            )
        return profiles

    def _generate_skills(self) -> list[dict[str, str]]:
        skills = self._datasets.skills
        chosen = random.sample(skills.catalog, min(skills.count.pick(), len(skills.catalog)))

        result: list[dict[str, str]] = []
        for name in chosen:
            proficiency = random.choices(skills.proficiency_levels, weights=skills.proficiency_weights, k=1)[0]
            result.append({"name": name, "proficiency": proficiency})
        return result

    def _generate_project_names(self) -> list[str]:
        policy = self._datasets.programmers
        return random.sample(policy.project_names, min(policy.project_count.pick(), len(policy.project_names)))

    def _generate_certifications(self) -> list[str]:
        policy = self._datasets.programmers
        count = min(policy.certification_count.pick(), len(policy.certifications))
        return random.sample(policy.certifications, count)

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from faker import Faker


@dataclass(frozen=True)
class GenerateStructuredCvResult:
    """Result of generating a single structured CV."""
    uuid: str
    cv: Dict[str, Any]


class StructuredCvGenerator:
    """Generates a structured CV as a plain dict using runtime-provided settings."""

    def __init__(self, settings: Any) -> None:
        self._settings = settings
        self._faker = Faker()

    def generate_one(self) -> GenerateStructuredCvResult:
        cv_uuid = str(uuid4())
        cv_policy = self._settings.datasets.cv

        person = self._generate_person(cv_policy)
        skills = self._generate_skills(cv_policy)
        certifications = self._generate_certifications(cv_policy)
        education = self._generate_education(cv_policy, person_location=person["location"])
        experience = self._generate_experience(
            cv_policy,
            seniority=person["seniority"],
            skills=skills,
            person_location=person["location"],
        )
        projects = self._generate_projects(cv_policy, skills=skills, experience=experience)
        summary = self._generate_summary(cv_policy, skills=skills, experience=experience, certifications=certifications)

        cv: Dict[str, Any] = {
            "uuid": cv_uuid,
            "schema_version": cv_policy.schema_version,
            "person": person,
            "summary": summary,
            "skills": skills,
            "certifications": certifications,
            "experience": experience,
            "projects": projects,
            "education": education,
        }

        return GenerateStructuredCvResult(uuid=cv_uuid, cv=cv)

    def generate_many(self, count: int) -> List[GenerateStructuredCvResult]:
        if count <= 0:
            raise ValueError(self._settings.datasets.cv.errors.count_must_be_positive)
        return [self.generate_one() for _ in range(count)]

    def _generate_person(self, cv_policy: Any) -> Dict[str, Any]:
        first_name = self._faker.first_name()
        last_name = self._faker.last_name()

        name = cv_policy.person.name_format.format(first_name=first_name, last_name=last_name)
        email = self._generate_email(cv_policy, first_name=first_name, last_name=last_name)
        location = random.choice(cv_policy.person.locations)

        seniority = self._choose_weighted(
            items=list(cv_policy.person.seniority.labels),
            weights=list(cv_policy.person.seniority.weights),
        )
        headline = cv_policy.person.headline_by_seniority[seniority]
        links = self._generate_links(cv_policy, first_name=first_name, last_name=last_name)

        return {
            "name": name,
            "email": email,
            "location": location,
            "seniority": seniority,
            "headline": headline,
            "links": links,
        }

    def _generate_email(self, cv_policy: Any, *, first_name: str, last_name: str) -> str:
        local_part_raw = cv_policy.person.email_local_part_format.format(first_name=first_name, last_name=last_name)
        local_part = self._normalize_identifier(cv_policy, local_part_raw)
        domain = random.choice(cv_policy.person.email_domains)
        return cv_policy.person.email_format.format(local_part=local_part, domain=domain)

    def _generate_links(self, cv_policy: Any, *, first_name: str, last_name: str) -> List[Dict[str, str]]:
        slug_raw = cv_policy.person.link_slug_format.format(first_name=first_name, last_name=last_name)
        slug = self._normalize_identifier(cv_policy, slug_raw)
        return [{"type": link.type, "url": link.url_template.format(slug=slug)} for link in cv_policy.person.links]

    def _generate_skills(self, cv_policy: Any) -> List[Dict[str, str]]:
        all_skills = list(cv_policy.skills.all)

        min_count = cv_policy.skills.count.min
        max_count = min(cv_policy.skills.count.max, len(all_skills))
        selected = random.sample(all_skills, k=random.randint(min_count, max_count))

        levels = list(cv_policy.skills.proficiency.levels)
        weights = list(cv_policy.skills.proficiency.weights)

        skills = [{"name": name, "proficiency": self._choose_weighted(items=levels, weights=weights)} for name in
                  selected]
        return self._sort_skills_by_proficiency(levels, skills)

    @staticmethod
    def _sort_skills_by_proficiency(levels: List[str], skills: List[Dict[str, str]]) -> List[Dict[str, str]]:
        order = {level: index for index, level in enumerate(levels)}
        return sorted(skills, key=lambda s: order.get(s["proficiency"], len(order)))

    @staticmethod
    def _generate_certifications(cv_policy: Any) -> List[str]:
        items = list(cv_policy.certifications.all)
        min_count = cv_policy.certifications.count.min
        max_count = min(cv_policy.certifications.count.max, len(items))
        count = random.randint(min_count, max_count)
        return random.sample(items, k=count) if count > 0 else []

    @staticmethod
    def _generate_education(cv_policy: Any, *, person_location: str) -> List[Dict[str, Any]]:
        min_count = cv_policy.education.count.min
        max_count = cv_policy.education.count.max
        count = random.randint(min_count, max_count)

        universities = list(cv_policy.education.universities)
        degrees = list(cv_policy.education.degrees)
        fields = list(cv_policy.education.fields)
        duration_years = list(cv_policy.education.duration_years)

        current_year = date.today().year
        end_year_min_offset = cv_policy.education.end_year_offset.min
        end_year_max_offset = cv_policy.education.end_year_offset.max

        entries: List[Dict[str, Any]] = []
        for _ in range(count):
            end_year = random.randint(current_year - end_year_max_offset, current_year - end_year_min_offset)
            years = random.choice(duration_years)
            start_year = end_year - years

            entries.append(
                {
                    "institution": random.choice(universities),
                    "degree": random.choice(degrees),
                    "field": random.choice(fields),
                    "location": person_location,
                    "start_year": start_year,
                    "end_year": end_year,
                }
            )

        return sorted(entries, key=lambda e: e["end_year"], reverse=True)

    def _generate_experience(
            self,
            cv_policy: Any,
            *,
            seniority: str,
            skills: List[Dict[str, str]],
            person_location: str,
    ) -> List[Dict[str, Any]]:
        jobs_range = cv_policy.experience.jobs_by_seniority.__getattribute__(seniority)
        target_jobs = random.randint(jobs_range.min, jobs_range.max)

        company_names = list(cv_policy.experience.company_names)
        job_titles = list(cv_policy.experience.job_titles)
        domains = list(cv_policy.experience.domains)

        duration_min = cv_policy.experience.job_duration_months.min
        duration_max = cv_policy.experience.job_duration_months.max
        gap_min = cv_policy.experience.gap_days.min
        gap_max = cv_policy.experience.gap_days.max

        max_total_years = cv_policy.experience.max_total_years
        month_to_days = cv_policy.experience.month_to_days
        total_days_budget = max_total_years * 365

        templates = list(cv_policy.text.bullets_templates)

        end_date = date.today()
        used_days = 0

        experience: List[Dict[str, Any]] = []
        for index in range(target_jobs):
            duration_months = random.randint(duration_min, duration_max)
            duration_days = duration_months * month_to_days

            if used_days + duration_days > total_days_budget:
                break

            start_date = end_date - timedelta(days=duration_days)
            used_days += duration_days

            domain = random.choice(domains)
            tech_stack = self._pick_tech_stack(cv_policy, skills)
            responsibilities = self._generate_responsibilities(cv_policy, templates=templates, tech_stack=tech_stack,
                                                               domain=domain)

            experience.append(
                {
                    "company": random.choice(company_names),
                    "title": random.choice(job_titles),
                    "domain": domain,
                    "location": person_location,
                    "start_date": start_date.isoformat(),
                    "end_date": None if index == 0 else end_date.isoformat(),
                    "responsibilities": responsibilities,
                    "tech_stack": tech_stack,
                }
            )

            end_date = start_date - timedelta(days=random.randint(gap_min, gap_max))

        return experience

    @staticmethod
    def _pick_tech_stack(cv_policy: Any, skills: List[Dict[str, str]]) -> List[str]:
        names = [s["name"] for s in skills]
        min_count = min(cv_policy.experience.tech_stack_size.min, len(names))
        max_count = min(cv_policy.experience.tech_stack_size.max, len(names))
        count = random.randint(min_count, max_count) if max_count > 0 else 0
        return random.sample(names, k=count) if count > 0 else []

    @staticmethod
    def _generate_responsibilities(cv_policy: Any, *, templates: List[str], tech_stack: List[str], domain: str) -> List[
        str]:
        min_count = cv_policy.experience.responsibilities_count.min
        max_count = cv_policy.experience.responsibilities_count.max
        count = random.randint(min_count, max_count)

        fallback_skill = cv_policy.text.fallback_skill

        items: List[str] = []
        for _ in range(count):
            template = random.choice(templates)
            skill = random.choice(tech_stack) if tech_stack else fallback_skill
            items.append(template.format(skill=skill, domain=domain))
        return items

    def _generate_projects(self, cv_policy: Any, *, skills: List[Dict[str, str]], experience: List[Dict[str, Any]]) -> \
            List[Dict[str, Any]]:
        count = random.randint(cv_policy.projects.count.min, cv_policy.projects.count.max)

        project_types = list(cv_policy.projects.project_types)
        name_prefixes = list(cv_policy.projects.name_prefixes)
        name_template = cv_policy.projects.name_template
        impact_verbs = list(cv_policy.projects.impact_verbs)
        metrics = list(cv_policy.projects.metrics)
        description_template = cv_policy.projects.description_template
        highlight_templates = list(cv_policy.projects.highlight_templates)

        primary_tech_count = cv_policy.projects.primary_tech_count
        highlights_count = cv_policy.projects.highlights_count
        attach_company_probability = cv_policy.projects.attach_company_probability

        all_skill_names = [s["name"] for s in skills]

        projects: List[Dict[str, Any]] = []
        for _ in range(count):
            project_type = random.choice(project_types)
            name = name_template.format(prefix=random.choice(name_prefixes), project_type=project_type)

            tech_stack = self._pick_project_stack(cv_policy, all_skill_names)
            company = self._pick_project_company(experience, probability=attach_company_probability)

            verb = random.choice(impact_verbs)
            metric = random.choice(metrics)

            description = description_template.format(
                verb=verb,
                project_type=project_type,
                project_type_lower=project_type.lower(),
            )

            highlights = [
                template.format(
                    tech_stack=", ".join(tech_stack[:primary_tech_count]),
                    metric=metric,
                )
                for template in self._take_random(highlight_templates, k=highlights_count)
            ]

            projects.append(
                {
                    "name": name,
                    "type": project_type,
                    "company": company,
                    "description": description,
                    "highlights": highlights,
                    "tech_stack": tech_stack,
                }
            )

        return projects

    @staticmethod
    def _pick_project_stack(cv_policy: Any, all_skill_names: List[str]) -> List[str]:
        min_count = min(cv_policy.projects.tech_stack_size.min, len(all_skill_names))
        max_count = min(cv_policy.projects.tech_stack_size.max, len(all_skill_names))
        count = random.randint(min_count, max_count) if max_count > 0 else 0
        return random.sample(all_skill_names, k=count) if count > 0 else []

    @staticmethod
    def _pick_project_company(experience: List[Dict[str, Any]], *, probability: float) -> Optional[str]:
        if not experience:
            return None
        if random.random() >= probability:
            return None
        return random.choice(experience)["company"]

    def _generate_summary(
            self,
            cv_policy: Any,
            *,
            skills: List[Dict[str, str]],
            experience: List[Dict[str, Any]],
            certifications: List[str],
    ) -> str:
        templates = list(cv_policy.text.summary_templates)
        template = random.choice(templates)

        years = self._estimate_years_of_experience(cv_policy, experience)
        top_skills = [s["name"] for s in skills[: cv_policy.text.summary_top_skills]]

        certs = ", ".join(certifications[: cv_policy.text.summary_max_certs])
        cert_part = (
            cv_policy.text.summary_cert_part_template.format(certs=certs)
            if certifications
            else cv_policy.text.summary_cert_part_empty
        )

        return template.format(years=years, skills=", ".join(top_skills), cert_part=cert_part).strip()

    @staticmethod
    def _estimate_years_of_experience(cv_policy: Any, experience: List[Dict[str, Any]]) -> int:
        if not experience:
            return cv_policy.text.min_years_of_experience

        month_to_days = cv_policy.experience.month_to_days
        total_months = 0

        for job in experience:
            start = date.fromisoformat(job["start_date"])
            end = date.today() if job["end_date"] is None else date.fromisoformat(job["end_date"])
            total_months += max(1, (end - start).days // month_to_days)

        years = total_months // 12
        return max(cv_policy.text.min_years_of_experience, min(cv_policy.text.max_years_of_experience, years))

    @staticmethod
    def _choose_weighted(*, items: List[str], weights: List[float]) -> str:
        return random.choices(items, weights=weights, k=1)[0]

    @staticmethod
    def _take_random(items: List[str], *, k: int) -> List[str]:
        if k <= 0:
            return []
        if k >= len(items):
            return list(items)
        return random.sample(items, k=k)

    @staticmethod
    def _normalize_identifier(cv_policy: Any, value: str) -> str:
        result = value
        for old, new in cv_policy.text.identifier_replacements.items():
            result = result.replace(old, new)
        return result.lower()

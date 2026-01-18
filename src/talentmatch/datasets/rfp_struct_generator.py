from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, List, Mapping
from uuid import uuid4

from faker import Faker


@dataclass(frozen=True)
class GenerateStructuredRfpResult:
    """Public contract: output of generating one structured RFP."""
    uuid: str
    rfp_struct: Mapping[str, Any]


class StructuredRfpGenerator:
    """Public contract: generates structured RFP documents based on runtime policies."""

    def __init__(self, settings: Any) -> None:
        self._settings = settings
        self._faker = Faker()

    def generate_one(self) -> GenerateStructuredRfpResult:
        """Public contract: returns one RFP struct aligned to the configured schema_version."""
        rfp_policy = self._settings.datasets.rfp
        rfp_uuid = str(uuid4())

        domain = self._choose(rfp_policy.catalog.domains)
        project_type = self._choose(rfp_policy.catalog.project_types)

        client = self._choose(rfp_policy.catalog.clients) if rfp_policy.catalog.clients else self._faker.company()

        contract_type = self._choose(rfp_policy.catalog.contract_types)
        location = self._choose(rfp_policy.catalog.locations)
        remote_mode = self._choose(rfp_policy.catalog.remote_modes)
        remote_allowed = remote_mode.lower() != "on-site"

        budget_range = self._choose(rfp_policy.catalog.budget_ranges)

        start_date = self._random_future_date(
            min_days=rfp_policy.text.start_date_min_days,
            max_days=rfp_policy.text.start_date_max_days,
        )
        duration_months = random.randint(
            rfp_policy.text.duration_months_min,
            rfp_policy.text.duration_months_max,
        )

        team_size = random.randint(
            rfp_policy.text.team_size_min,
            rfp_policy.text.team_size_max,
        )

        rfp_id = self._format_rfp_id(rfp_policy, rfp_uuid)
        title = self._format_title(
            rfp_policy=rfp_policy,
            domain=domain,
            project_type=project_type,
            client=client,
        )

        executive_summary = self._format_executive_summary(
            rfp_policy=rfp_policy,
            title=title,
            client=client,
            domain=domain,
            project_type=project_type,
            duration_months=duration_months,
            team_size=team_size,
            budget_range=budget_range,
            start_date=start_date,
            location=location,
            remote_allowed=remote_allowed,
        )

        business_context = self._format_business_context(
            rfp_policy=rfp_policy,
            client=client,
            domain=domain,
            project_type=project_type,
        )

        objectives = self._generate_objectives(rfp_policy, domain=domain, project_type=project_type)
        tech_reqs = self._generate_technical_requirements(rfp_policy)

        staffing_profile = self._generate_staffing_profile(
            rfp_policy=rfp_policy,
            project_type=project_type,
            team_size=team_size,
            required_skills=[x["skill_name"] for x in tech_reqs["required_skills"]],
        )

        deliverables = self._generate_deliverables(rfp_policy, domain=domain, project_type=project_type)
        milestones = self._generate_milestones(
            rfp_policy,
            duration_months=duration_months,
            domain=domain,
            project_type=project_type,
        )

        acceptance_criteria = self._generate_acceptance_criteria(rfp_policy, domain=domain, project_type=project_type)
        proposal_guidelines = self._generate_proposal_guidelines(rfp_policy)
        evaluation_process = self._format_evaluation_process(rfp_policy, client=client)

        contact_information = {
            "name": "[Contact Person]",
            "email": "[Contact Email]",
            "phone": "[Contact Phone Number]",
        }

        rfp_struct: dict[str, Any] = {
            "uuid": rfp_uuid,
            "schema_version": rfp_policy.schema_version,
            "rfp_id": rfp_id,
            "title": title,
            "client": client,
            "domain": domain,
            "project_type": project_type,
            "contract_type": contract_type,
            "location": location,
            "remote_mode": remote_mode,
            "remote_allowed": remote_allowed,
            "budget_range": budget_range,
            "start_date": start_date.isoformat(),
            "duration_months": duration_months,
            "team_size": team_size,
            "staffing_profile": staffing_profile,
            "executive_summary": executive_summary,
            "business_context": business_context,
            "objectives": objectives,
            "technical_requirements": tech_reqs,
            "deliverables": deliverables,
            "milestones": milestones,
            "acceptance_criteria": acceptance_criteria,
            "proposal_submission_guidelines": proposal_guidelines,
            "evaluation_process": evaluation_process,
            "contact_information": contact_information,
        }

        return GenerateStructuredRfpResult(uuid=rfp_uuid, rfp_struct=rfp_struct)

    def generate_many(self, *, count: int) -> List[GenerateStructuredRfpResult]:
        """Public contract: returns a list of generated RFP structs; count must be positive."""
        rfp_policy = self._settings.datasets.rfp
        if count <= 0:
            raise ValueError(rfp_policy.errors.count_must_be_positive)
        return [self.generate_one() for _ in range(count)]

    @staticmethod
    def _format_rfp_id(rfp_policy: Any, rfp_uuid: str) -> str:
        token_source = rfp_uuid.replace("-", "").upper()
        token = token_source[: rfp_policy.text.id_token_length]
        return rfp_policy.text.id_template.format(token=token)

    def _format_title(self, *, rfp_policy: Any, domain: str, project_type: str, client: str) -> str:
        template = self._choose(rfp_policy.text.title_templates)
        return template.format(domain=domain, project_type=project_type, client=client)

    def _format_executive_summary(
            self,
            *,
            rfp_policy: Any,
            title: str,
            client: str,
            domain: str,
            project_type: str,
            duration_months: int,
            team_size: int,
            budget_range: str,
            start_date: date,
            location: str,
            remote_allowed: bool,
    ) -> str:
        template = self._choose(rfp_policy.text.executive_summary_templates)
        return template.format(
            title=title,
            client=client,
            domain=domain,
            project_type=project_type,
            duration_months=duration_months,
            team_size=team_size,
            budget_range=budget_range,
            start_date=start_date.strftime("%B %d, %Y"),
            location=location,
            remote_allowed="Remote Work Allowed" if remote_allowed else "On-site Only",
        )

    def _format_business_context(self, *, rfp_policy: Any, client: str, domain: str, project_type: str) -> str:
        template = self._choose(rfp_policy.text.business_context_templates)
        return template.format(client=client, domain=domain, project_type=project_type)

    @staticmethod
    def _generate_objectives(rfp_policy: Any, *, domain: str, project_type: str) -> List[str]:
        count = random.randint(rfp_policy.text.objectives_min_count, rfp_policy.text.objectives_max_count)
        templates = list(rfp_policy.text.objective_templates)
        random.shuffle(templates)
        picked = templates[:count] if len(templates) >= count else templates
        return [t.format(domain=domain, project_type=project_type) for t in picked]

    def _generate_technical_requirements(self, rfp_policy: Any) -> dict[str, Any]:
        required_count = random.randint(
            rfp_policy.text.required_skills_min_count,
            rfp_policy.text.required_skills_max_count,
        )
        preferred_count = random.randint(
            rfp_policy.text.preferred_skills_min_count,
            rfp_policy.text.preferred_skills_max_count,
        )

        skills_pool = list(rfp_policy.catalog.skills)
        random.shuffle(skills_pool)

        required_skills = skills_pool[:required_count]
        remaining_pool = [s for s in skills_pool if s not in required_skills]
        random.shuffle(remaining_pool)
        preferred_skills = remaining_pool[:preferred_count]

        required_objs = [
            self._make_skill_requirement(
                rfp_policy=rfp_policy,
                skill=skill,
                is_mandatory=True,
            )
            for skill in required_skills
        ]
        preferred_objs = [
            self._make_skill_requirement(
                rfp_policy=rfp_policy,
                skill=skill,
                is_mandatory=False,
            )
            for skill in preferred_skills
        ]

        return {
            "required_skills": required_objs,
            "preferred_skills": preferred_objs,
        }

    def _make_skill_requirement(self, *, rfp_policy: Any, skill: str, is_mandatory: bool) -> dict[str, Any]:
        max_certs = rfp_policy.text.preferred_certifications_max_count
        cert_count = random.randint(0, max_certs)
        certs_pool = list(rfp_policy.catalog.certifications)
        certs = random.sample(certs_pool, k=min(cert_count, len(certs_pool)))

        return {
            "skill_name": skill,
            "min_proficiency": self._choose(rfp_policy.catalog.proficiency_levels),
            "is_mandatory": bool(is_mandatory),
            "preferred_certifications": certs,
        }

    def _generate_staffing_profile(
            self,
            *,
            rfp_policy: Any,
            project_type: str,
            team_size: int,
            required_skills: list[str],
    ) -> list[dict[str, Any]]:
        staffing_policy = rfp_policy.staffing
        role_set = self._select_role_set(staffing_policy.role_sets, project_type)

        base_roles = self._unique(staffing_policy.always_roles + role_set["core_roles"])
        if len(base_roles) > team_size:
            base_roles = base_roles[:team_size]

        counts: dict[str, int] = {r: 1 for r in base_roles}
        remaining = team_size - len(base_roles)

        allowed_roles = self._unique(role_set["core_roles"] + role_set["optional_roles"])
        if not allowed_roles:
            allowed_roles = self._unique(staffing_policy.always_roles)

        while remaining > 0:
            role = self._choose_weighted_roles(allowed_roles, staffing_policy.role_weights)
            if counts.get(role, 0) >= staffing_policy.max_per_role:
                continue
            counts[role] = counts.get(role, 0) + 1
            remaining -= 1

        role_skill_map = {x.role: list(x.skills) for x in staffing_policy.role_skill_map}

        profile: list[dict[str, Any]] = []
        for role in sorted(counts.keys()):
            key_skills = role_skill_map.get(role)
            if not key_skills:
                pool = self._unique(required_skills + list(rfp_policy.catalog.skills))
                k = min(4, max(2, len(pool)))
                key_skills = random.sample(pool, k=k)

            seniority = self._choose_weighted_str(staffing_policy.seniority_weights)

            responsibilities = self._generate_role_responsibilities(
                rfp_policy=rfp_policy,
                role=role,
                project_type=project_type,
            )

            profile.append(
                {
                    "role": role,
                    "count": counts[role],
                    "seniority": seniority,
                    "key_skills": key_skills,
                    "responsibilities": responsibilities,
                }
            )

        return profile

    @staticmethod
    def _generate_role_responsibilities(*, rfp_policy: Any, role: str, project_type: str) -> list[str]:
        min_c = rfp_policy.text.role_responsibilities_min_count
        max_c = rfp_policy.text.role_responsibilities_max_count
        count = random.randint(min_c, max_c)

        templates = list(rfp_policy.text.role_responsibility_templates)
        random.shuffle(templates)
        picked = templates[:count] if len(templates) >= count else templates

        return [t.format(role=role, project_type=project_type) for t in picked]

    @staticmethod
    def _generate_deliverables(rfp_policy: Any, *, domain: str, project_type: str) -> List[str]:
        count = random.randint(rfp_policy.text.deliverables_min_count, rfp_policy.text.deliverables_max_count)
        templates = list(rfp_policy.text.deliverable_templates)
        random.shuffle(templates)
        picked = templates[:count] if len(templates) >= count else templates
        return [t.format(domain=domain, project_type=project_type) for t in picked]

    def _generate_milestones(
            self,
            rfp_policy: Any,
            *,
            duration_months: int,
            domain: str,
            project_type: str,
    ) -> list[dict[str, Any]]:
        count = random.randint(rfp_policy.text.milestones_min_count, rfp_policy.text.milestones_max_count)

        title_templates = list(rfp_policy.text.milestone_title_templates)
        desc_templates = list(rfp_policy.text.milestone_description_templates)
        random.shuffle(title_templates)
        random.shuffle(desc_templates)

        month_offsets = self._spread_months(duration_months, count)

        milestones: list[dict[str, Any]] = []
        for i in range(count):
            title_t = title_templates[i % len(title_templates)]
            desc_t = desc_templates[i % len(desc_templates)]
            milestones.append(
                {
                    "title": title_t.format(domain=domain, project_type=project_type),
                    "description": desc_t.format(domain=domain, project_type=project_type),
                    "target_month": month_offsets[i],
                }
            )
        return milestones

    @staticmethod
    def _generate_acceptance_criteria(rfp_policy: Any, *, domain: str, project_type: str) -> List[str]:
        count = random.randint(
            rfp_policy.text.acceptance_criteria_min_count,
            rfp_policy.text.acceptance_criteria_max_count,
        )
        templates = list(rfp_policy.text.acceptance_criteria_templates)
        random.shuffle(templates)
        picked = templates[:count] if len(templates) >= count else templates
        return [t.format(domain=domain, project_type=project_type) for t in picked]

    @staticmethod
    def _generate_proposal_guidelines(rfp_policy: Any) -> List[str]:
        count = random.randint(
            rfp_policy.text.proposal_guidelines_min_count,
            rfp_policy.text.proposal_guidelines_max_count,
        )
        templates = list(rfp_policy.text.proposal_guideline_templates)
        random.shuffle(templates)
        picked = templates[:count] if len(templates) >= count else templates
        return list(picked)

    def _format_evaluation_process(self, rfp_policy: Any, *, client: str) -> str:
        template = self._choose(rfp_policy.text.evaluation_process_templates)
        return template.format(client=client)

    @staticmethod
    def _random_future_date(*, min_days: int, max_days: int) -> date:
        days = random.randint(min_days, max_days)
        return date.today() + timedelta(days=days)

    @staticmethod
    def _choose(items: List[str]) -> str:
        return random.choice(items)

    @staticmethod
    def _unique(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for x in items:
            if x not in seen:
                out.append(x)
                seen.add(x)
        return out

    @staticmethod
    def _select_role_set(role_sets: list[Any], project_type: str) -> dict[str, Any]:
        pt = project_type.lower()
        for rs in role_sets:
            keywords = [k.lower() for k in rs.match_keywords]
            if any(k in pt for k in keywords):
                return {
                    "name": rs.name,
                    "core_roles": list(rs.core_roles),
                    "optional_roles": list(rs.optional_roles),
                }

        if role_sets:
            rs = role_sets[0]
            return {
                "name": rs.name,
                "core_roles": list(rs.core_roles),
                "optional_roles": list(rs.optional_roles),
            }

        return {"name": "default", "core_roles": [], "optional_roles": []}

    @staticmethod
    def _choose_weighted_roles(roles: list[str], weights_map: dict[str, float]) -> str:
        weights = [float(weights_map.get(r, 1.0)) for r in roles]
        return random.choices(roles, weights=weights, k=1)[0]

    @staticmethod
    def _choose_weighted_str(weights_map: dict[str, float]) -> str:
        items = list(weights_map.keys())
        weights = [float(weights_map[k]) for k in items]
        return random.choices(items, weights=weights, k=1)[0]

    @staticmethod
    def _spread_months(duration_months: int, count: int) -> list[int]:
        if count <= 1:
            return [max(1, duration_months)]
        step = max(1, duration_months // count)
        months = [min(duration_months, step * (i + 1)) for i in range(count)]
        months[-1] = max(1, min(duration_months, months[-1]))
        return months

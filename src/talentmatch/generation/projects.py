from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

from faker import Faker

from talentmatch.config.config_models import DatasetsSettings


class ProjectGenerator:
    """
    Generates projects and assigns programmers to them
    """

    def __init__(self, faker: Faker, datasets: DatasetsSettings) -> None:
        self._faker = faker
        self._datasets = datasets

    def generate(self, count: int, programmer_profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Generate project records and optionally assign programmers
        :param count: number of projects to generate
        :param programmer_profiles: list of programmer profiles for assignment
        :return: list of generated project records
        """

        projects_policy = self._datasets.projects
        skill_names = self._collect_skill_names(programmer_profiles)

        projects: list[dict[str, Any]] = []
        for idx in range(1, count + 1):
            start = self._date_from_today_offset(projects_policy.start_date_offset_days.pick())
            duration_months = projects_policy.duration_months.pick()
            status = random.choices(projects_policy.status.labels, weights=projects_policy.status.weights, k=1)[0]
            end = self._project_end_date(status, start, duration_months)

            project_type = random.choice(projects_policy.project_types)
            client = random.choice(projects_policy.clients)

            projects.append(
                {
                    "id": f"PRJ-{idx:03d}",
                    "name": projects_policy.name_template.format(project_type=project_type, client=client),
                    "client": client,
                    "description": projects_policy.description_template.format(project_type=project_type,
                                                                               client=client),
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat() if end else None,
                    "estimated_duration_months": duration_months,
                    "budget": self._maybe_budget(),
                    "status": status,
                    "team_size": projects_policy.team_size.pick(),
                    "requirements": self._generate_requirements(skill_names),
                    "assigned_programmers": [],
                }
            )

        return self._assign_programmers(projects, programmer_profiles)

    def _maybe_budget(self) -> int | None:
        policy = self._datasets.projects
        if random.random() >= float(policy.budget_has_value_probability):
            return None
        return policy.budget_amount.pick()

    def _generate_requirements(self, skill_names: list[str]) -> list[dict[str, Any]]:
        policy = self._datasets.projects
        skills_policy = self._datasets.skills

        count = min(policy.requirements_count.pick(), len(skill_names))
        chosen = random.sample(skill_names, count)

        requirements: list[dict[str, Any]] = []
        for skill_name in chosen:
            requirements.append(
                {
                    "skill_name": skill_name,
                    "min_proficiency": random.choice(skills_policy.proficiency_levels),
                    "is_mandatory": random.random() < float(policy.mandatory_probability),
                }
            )
        return requirements

    def _assign_programmers(
            self, projects: list[dict[str, Any]], programmer_profiles: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        assignments_policy = self._datasets.assignments
        projects_policy = self._datasets.projects

        assignments_by_programmer: dict[int, list[tuple[date, date]]] = {int(p["id"]): [] for p in programmer_profiles}

        assignable = [p for p in projects if p.get("status") in set(projects_policy.assignable_statuses)]

        for project in assignable:
            if random.random() > float(assignments_policy.assignment_probability):
                continue

            eligible = self._eligible_programmers(project, programmer_profiles, assignments_by_programmer)
            if not eligible:
                continue

            team_size = max(int(project.get("team_size", 0)), 0)
            if team_size <= 0:
                continue

            selection = random.sample(eligible, min(team_size, len(eligible)))
            for programmer in selection:
                self._assign_one(programmer, project, assignments_by_programmer)

        self._ensure_min_programmers_per_project(assignable, programmer_profiles, assignments_by_programmer)
        self._ensure_min_projects_per_programmer(assignable, programmer_profiles, assignments_by_programmer)

        return projects

    def _assign_one(
            self,
            programmer: dict[str, Any],
            project: dict[str, Any],
            assignments_by_programmer: dict[int, list[tuple[date, date]]],
    ) -> None:
        programmer_id = int(programmer["id"])
        already = {int(a.get("programmer_id")) for a in project.get("assigned_programmers", []) if
                   a.get("programmer_id") is not None}
        if programmer_id in already:
            return

        start = date.fromisoformat(project["start_date"])
        end = self._compute_assignment_end(project)

        allocation_percent = self._pick_allocation_percent()

        project["assigned_programmers"].append(
            {
                "programmer_name": programmer["name"],
                "programmer_id": programmer["id"],
                "assignment_start_date": start.isoformat(),
                "assignment_end_date": end.isoformat(),
                "allocation_percent": int(allocation_percent),
            }
        )
        assignments_by_programmer[programmer_id].append((start, end))

    def _pick_allocation_percent(self) -> int:
        policy = self._datasets.assignments.allocation_percent
        values = policy.values()
        return int(random.choice(values)) if values else 100

    def _ensure_min_programmers_per_project(
            self,
            assignable_projects: list[dict[str, Any]],
            programmer_profiles: list[dict[str, Any]],
            assignments_by_programmer: dict[int, list[tuple[date, date]]],
    ) -> None:
        assignments_policy = self._datasets.assignments

        minimum = int(assignments_policy.min_programmers_per_project)
        if minimum <= 0:
            return

        for project in assignable_projects:
            team_size = max(int(project.get("team_size", 0)), 0)
            if team_size <= 0:
                continue

            required = min(team_size, minimum)
            while len(project.get("assigned_programmers", [])) < required:
                eligible = self._eligible_programmers(project, programmer_profiles, assignments_by_programmer)
                if not eligible:
                    break

                already = {int(a.get("programmer_id")) for a in project.get("assigned_programmers", []) if
                           a.get("programmer_id") is not None}
                eligible = [p for p in eligible if int(p["id"]) not in already]
                if not eligible:
                    break

                self._assign_one(random.choice(eligible), project, assignments_by_programmer)

    def _ensure_min_projects_per_programmer(
            self,
            assignable_projects: list[dict[str, Any]],
            programmer_profiles: list[dict[str, Any]],
            assignments_by_programmer: dict[int, list[tuple[date, date]]],
    ) -> None:
        assignments_policy = self._datasets.assignments

        minimum = int(assignments_policy.min_projects_per_programmer)
        if minimum <= 0:
            return

        counts: dict[int, int] = {int(p["id"]): 0 for p in programmer_profiles}
        for project in assignable_projects:
            for a in project.get("assigned_programmers", []):
                pid = a.get("programmer_id")
                if pid is None:
                    continue
                counts[int(pid)] = counts.get(int(pid), 0) + 1

        for programmer in programmer_profiles:
            programmer_id = int(programmer["id"])
            while counts.get(programmer_id, 0) < minimum:
                candidates = self._candidate_projects_for_programmer(programmer, assignable_projects,
                                                                     assignments_by_programmer)
                if not candidates:
                    break

                candidates.sort(key=lambda p: len(p.get("assigned_programmers", [])))
                top = candidates[: min(5, len(candidates))]
                chosen = random.choice(top)

                self._assign_one(programmer, chosen, assignments_by_programmer)
                counts[programmer_id] = counts.get(programmer_id, 0) + 1

    def _candidate_projects_for_programmer(
            self,
            programmer: dict[str, Any],
            assignable_projects: list[dict[str, Any]],
            assignments_by_programmer: dict[int, list[tuple[date, date]]],
    ) -> list[dict[str, Any]]:
        programmer_id = int(programmer["id"])

        result: list[dict[str, Any]] = []
        for project in assignable_projects:
            team_size = max(int(project.get("team_size", 0)), 0)
            if team_size <= 0:
                continue
            if len(project.get("assigned_programmers", [])) >= team_size:
                continue

            already = {int(a.get("programmer_id")) for a in project.get("assigned_programmers", []) if
                       a.get("programmer_id") is not None}
            if programmer_id in already:
                continue

            if not self._is_programmer_eligible_for_project(programmer, project, assignments_by_programmer):
                continue

            result.append(project)

        return result

    def _is_programmer_eligible_for_project(
            self,
            programmer: dict[str, Any],
            project: dict[str, Any],
            assignments_by_programmer: dict[int, list[tuple[date, date]]],
    ) -> bool:
        mandatory = [r for r in project.get("requirements", []) if r.get("is_mandatory")]
        if not self._meets_mandatory_requirements(programmer, mandatory):
            return False

        project_start = date.fromisoformat(project["start_date"])
        project_end = self._project_effective_end(project)
        programmer_id = int(programmer["id"])
        if self._has_overlap(assignments_by_programmer[programmer_id], project_start, project_end):
            return False

        return True

    def _eligible_programmers(
            self,
            project: dict[str, Any],
            programmer_profiles: list[dict[str, Any]],
            assignments_by_programmer: dict[int, list[tuple[date, date]]],
    ) -> list[dict[str, Any]]:
        mandatory = [r for r in project.get("requirements", []) if r.get("is_mandatory")]
        project_start = date.fromisoformat(project["start_date"])
        project_end = self._project_effective_end(project)

        eligible: list[dict[str, Any]] = []
        for programmer in programmer_profiles:
            programmer_id = int(programmer["id"])
            if not self._meets_mandatory_requirements(programmer, mandatory):
                continue
            if self._has_overlap(assignments_by_programmer[programmer_id], project_start, project_end):
                continue
            eligible.append(programmer)

        return eligible

    def _meets_mandatory_requirements(self, programmer: dict[str, Any], mandatory: list[dict[str, Any]]) -> bool:
        if not mandatory:
            return True

        levels = self._datasets.skills.proficiency_levels
        prof_rank = {name: i for i, name in enumerate(levels, start=1)}
        programmer_skills = {s.get("name"): s.get("proficiency") for s in programmer.get("skills", [])}

        for req in mandatory:
            skill = req.get("skill_name")
            min_prof = req.get("min_proficiency")
            actual = programmer_skills.get(skill)
            if actual is None:
                return False
            if prof_rank.get(str(actual), 0) < prof_rank.get(str(min_prof), 0):
                return False

        return True

    def _compute_assignment_end(self, project: dict[str, Any]) -> date:
        policy = self._datasets.assignments
        start = date.fromisoformat(project["start_date"])
        end = self._project_effective_end(project)

        buffer_days = policy.assignment_end_days_before.pick()
        adjusted = end - timedelta(days=int(buffer_days))
        if adjusted <= start:
            return start + timedelta(days=1)
        return adjusted

    @staticmethod
    def _project_effective_end(project: dict[str, Any]) -> date:
        end_raw = project.get("end_date")
        if isinstance(end_raw, str) and end_raw:
            return date.fromisoformat(end_raw)

        start = date.fromisoformat(project["start_date"])
        duration_months = int(project.get("estimated_duration_months", 1))
        return start + timedelta(days=max(duration_months, 1) * 30)

    @staticmethod
    def _has_overlap(intervals: list[tuple[date, date]], start: date, end: date) -> bool:
        for a_start, a_end in intervals:
            if max(a_start, start) <= min(a_end, end):
                return True
        return False

    def _project_end_date(self, status: str, start: date, duration_months: int) -> date | None:
        policy = self._datasets.projects
        if status == policy.completed_status:
            return start + timedelta(days=int(duration_months) * 30)
        return None

    def _collect_skill_names(self, programmer_profiles: list[dict[str, Any]]) -> list[str]:
        names: set[str] = set()
        for profile in programmer_profiles:
            for skill in profile.get("skills", []):
                skill_name = skill.get("name")
                if isinstance(skill_name, str) and skill_name:
                    names.add(skill_name)

        return sorted(names) if names else list(self._datasets.skills.catalog)

    @staticmethod
    def _date_from_today_offset(offset_days: int) -> date:
        return date.today() + timedelta(days=int(offset_days))

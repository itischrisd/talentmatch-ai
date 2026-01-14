from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.talentmatch.datasets import StructuredCvGenerator
from src.talentmatch.runtime import load_settings

CHECK_OK = "✅"
CHECK_FAIL = "❌"

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CheckContext:
    repo_root: Path
    settings_path: Path


def print_ok(message: str) -> None:
    print(f"{CHECK_OK} {message}")


def print_fail(message: str) -> None:
    print(f"{CHECK_FAIL} {message}")


def is_uuid(value: Any) -> bool:
    return isinstance(value, str) and UUID_RE.match(value) is not None


def assert_true(condition: bool, *, ok: str, fail: str) -> bool:
    if condition:
        print_ok(ok)
        return True
    print_fail(fail)
    return False


def assert_in(value: Any, allowed: list[Any], *, label: str) -> bool:
    return assert_true(
        value in allowed,
        ok=f'{label} is valid: "{value}"',
        fail=f'{label} invalid: "{value}", allowed={allowed}',
    )


def assert_between(value: int, *, min_value: int, max_value: int, label: str) -> bool:
    return assert_true(
        min_value <= value <= max_value,
        ok=f"{label} within range: {value}",
        fail=f"{label} out of range: {value}, expected [{min_value}, {max_value}]",
    )


def assert_json_serializable(value: Any, *, label: str) -> bool:
    try:
        json.dumps(value, ensure_ascii=False)
        print_ok(f"{label} is JSON-serializable")
        return True
    except Exception as exc:
        print_fail(f"{label} is not JSON-serializable: {exc}")
        return False


def validate_cv_shape(cv: dict[str, Any], settings: Any) -> int:
    failures = 0
    cv_policy = settings.datasets.cv

    failures += 0 if assert_true(is_uuid(cv.get("uuid")), ok='uuid has valid format',
                                 fail=f'uuid invalid: {cv.get("uuid")}') else 1
    failures += 0 if assert_true(cv.get("schema_version") == cv_policy.schema_version,
                                 ok="schema_version matches settings",
                                 fail=f'schema_version differs: {cv.get("schema_version")} expected={cv_policy.schema_version}') else 1

    required_top_level = ["person", "summary", "skills", "certifications", "experience", "projects", "education"]
    for key in required_top_level:
        failures += 0 if assert_true(key in cv, ok=f'top-level key present: "{key}"',
                                     fail=f'top-level key missing: "{key}"') else 1

    person = cv.get("person", {})
    failures += 0 if assert_true(isinstance(person, dict), ok="person is dict", fail="person is not dict") else 1

    if isinstance(person, dict):
        failures += 0 if assert_true(isinstance(person.get("name"), str) and person["name"].strip(),
                                     ok="person.name ok", fail=f'person.name invalid: {person.get("name")}') else 1
        failures += 0 if assert_true(isinstance(person.get("email"), str) and person["email"].strip(),
                                     ok="person.email ok", fail=f'person.email invalid: {person.get("email")}') else 1
        failures += 0 if assert_true(isinstance(person.get("location"), str) and person["location"].strip(),
                                     ok="person.location ok",
                                     fail=f'person.location invalid: {person.get("location")}') else 1
        failures += 0 if assert_true(isinstance(person.get("headline"), str) and person["headline"].strip(),
                                     ok="person.headline ok",
                                     fail=f'person.headline invalid: {person.get("headline")}') else 1

        failures += 0 if assert_in(person.get("location"), list(cv_policy.person.locations),
                                   label="person.location") else 1
        failures += 0 if assert_in(person.get("seniority"), list(cv_policy.person.seniority.labels),
                                   label="person.seniority") else 1

        links = person.get("links", [])
        failures += 0 if assert_true(isinstance(links, list), ok="person.links is list",
                                     fail="person.links is not list") else 1
        if isinstance(links, list):
            expected_types = [link.type for link in cv_policy.person.links]
            for i, link in enumerate(links):
                label = f"person.links[{i}]"
                failures += 0 if assert_true(isinstance(link, dict), ok=f"{label} is dict",
                                             fail=f"{label} is not dict") else 1
                if isinstance(link, dict):
                    failures += 0 if assert_in(link.get("type"), expected_types, label=f"{label}.type") else 1
                    failures += 0 if assert_true(isinstance(link.get("url"), str) and link["url"].strip(),
                                                 ok=f"{label}.url ok",
                                                 fail=f'{label}.url invalid: {link.get("url")}') else 1

    summary = cv.get("summary")
    failures += 0 if assert_true(isinstance(summary, str) and summary.strip(), ok="summary ok",
                                 fail=f"summary invalid: {summary}") else 1

    skills = cv.get("skills", [])
    failures += 0 if assert_true(isinstance(skills, list), ok="skills is list", fail="skills is not list") else 1
    if isinstance(skills, list):
        failures += 0 if assert_between(len(skills), min_value=cv_policy.skills.count.min,
                                        max_value=min(cv_policy.skills.count.max, len(cv_policy.skills.all)),
                                        label="skills count") else 1

        allowed_proficiency = list(cv_policy.skills.proficiency.levels)
        allowed_skill_names = set(cv_policy.skills.all)
        for i, skill in enumerate(skills):
            label = f"skills[{i}]"
            failures += 0 if assert_true(isinstance(skill, dict), ok=f"{label} is dict",
                                         fail=f"{label} is not dict") else 1
            if isinstance(skill, dict):
                failures += 0 if assert_true(skill.get("name") in allowed_skill_names, ok=f"{label}.name ok",
                                             fail=f'{label}.name invalid: {skill.get("name")}') else 1
                failures += 0 if assert_in(skill.get("proficiency"), allowed_proficiency,
                                           label=f"{label}.proficiency") else 1

    certifications = cv.get("certifications", [])
    failures += 0 if assert_true(isinstance(certifications, list), ok="certifications is list",
                                 fail="certifications is not list") else 1
    if isinstance(certifications, list):
        failures += 0 if assert_between(len(certifications), min_value=cv_policy.certifications.count.min,
                                        max_value=min(cv_policy.certifications.count.max,
                                                      len(cv_policy.certifications.all)),
                                        label="certifications count") else 1

    education = cv.get("education", [])
    failures += 0 if assert_true(isinstance(education, list), ok="education is list",
                                 fail="education is not list") else 1
    if isinstance(education, list):
        failures += 0 if assert_between(len(education), min_value=cv_policy.education.count.min,
                                        max_value=cv_policy.education.count.max, label="education count") else 1
        for i, entry in enumerate(education):
            label = f"education[{i}]"
            failures += 0 if assert_true(isinstance(entry, dict), ok=f"{label} is dict",
                                         fail=f"{label} is not dict") else 1
            if isinstance(entry, dict):
                failures += 0 if assert_true(isinstance(entry.get("institution"), str) and entry["institution"].strip(),
                                             ok=f"{label}.institution ok",
                                             fail=f'{label}.institution invalid: {entry.get("institution")}') else 1
                failures += 0 if assert_true(isinstance(entry.get("degree"), str) and entry["degree"].strip(),
                                             ok=f"{label}.degree ok",
                                             fail=f'{label}.degree invalid: {entry.get("degree")}') else 1
                failures += 0 if assert_true(isinstance(entry.get("field"), str) and entry["field"].strip(),
                                             ok=f"{label}.field ok",
                                             fail=f'{label}.field invalid: {entry.get("field")}') else 1

    experience = cv.get("experience", [])
    failures += 0 if assert_true(isinstance(experience, list), ok="experience is list",
                                 fail="experience is not list") else 1
    if isinstance(experience, list):
        for i, job in enumerate(experience):
            label = f"experience[{i}]"
            failures += 0 if assert_true(isinstance(job, dict), ok=f"{label} is dict",
                                         fail=f"{label} is not dict") else 1
            if isinstance(job, dict):
                failures += 0 if assert_true(isinstance(job.get("company"), str) and job["company"].strip(),
                                             ok=f"{label}.company ok",
                                             fail=f'{label}.company invalid: {job.get("company")}') else 1
                failures += 0 if assert_true(isinstance(job.get("title"), str) and job["title"].strip(),
                                             ok=f"{label}.title ok",
                                             fail=f'{label}.title invalid: {job.get("title")}') else 1
                failures += 0 if assert_true(isinstance(job.get("domain"), str) and job["domain"].strip(),
                                             ok=f"{label}.domain ok",
                                             fail=f'{label}.domain invalid: {job.get("domain")}') else 1

                responsibilities = job.get("responsibilities", [])
                failures += 0 if assert_true(isinstance(responsibilities, list), ok=f"{label}.responsibilities is list",
                                             fail=f"{label}.responsibilities is not list") else 1
                if isinstance(responsibilities, list):
                    failures += 0 if assert_between(
                        len(responsibilities),
                        min_value=cv_policy.experience.responsibilities_count.min,
                        max_value=cv_policy.experience.responsibilities_count.max,
                        label=f"{label}.responsibilities count",
                    ) else 1

                tech_stack = job.get("tech_stack", [])
                failures += 0 if assert_true(isinstance(tech_stack, list), ok=f"{label}.tech_stack is list",
                                             fail=f"{label}.tech_stack is not list") else 1
                if isinstance(tech_stack, list):
                    failures += 0 if assert_between(
                        len(tech_stack),
                        min_value=min(cv_policy.experience.tech_stack_size.min, len(cv_policy.skills.all)),
                        max_value=min(cv_policy.experience.tech_stack_size.max, len(cv_policy.skills.all)),
                        label=f"{label}.tech_stack count",
                    ) else 1

    projects = cv.get("projects", [])
    failures += 0 if assert_true(isinstance(projects, list), ok="projects is list", fail="projects is not list") else 1
    if isinstance(projects, list):
        failures += 0 if assert_between(len(projects), min_value=cv_policy.projects.count.min,
                                        max_value=cv_policy.projects.count.max, label="projects count") else 1
        for i, project in enumerate(projects):
            label = f"projects[{i}]"
            failures += 0 if assert_true(isinstance(project, dict), ok=f"{label} is dict",
                                         fail=f"{label} is not dict") else 1
            if isinstance(project, dict):
                failures += 0 if assert_true(isinstance(project.get("name"), str) and project["name"].strip(),
                                             ok=f"{label}.name ok",
                                             fail=f'{label}.name invalid: {project.get("name")}') else 1
                failures += 0 if assert_in(project.get("type"), list(cv_policy.projects.project_types),
                                           label=f"{label}.type") else 1

                highlights = project.get("highlights", [])
                failures += 0 if assert_true(isinstance(highlights, list), ok=f"{label}.highlights is list",
                                             fail=f"{label}.highlights is not list") else 1
                if isinstance(highlights, list):
                    failures += 0 if assert_between(
                        len(highlights),
                        min_value=cv_policy.projects.highlights_count,
                        max_value=cv_policy.projects.highlights_count,
                        label=f"{label}.highlights count",
                    ) else 1

                tech_stack = project.get("tech_stack", [])
                failures += 0 if assert_true(isinstance(tech_stack, list), ok=f"{label}.tech_stack is list",
                                             fail=f"{label}.tech_stack is not list") else 1
                if isinstance(tech_stack, list):
                    failures += 0 if assert_between(
                        len(tech_stack),
                        min_value=min(cv_policy.projects.tech_stack_size.min, len(cv_policy.skills.all)),
                        max_value=min(cv_policy.projects.tech_stack_size.max, len(cv_policy.skills.all)),
                        label=f"{label}.tech_stack count",
                    ) else 1

    failures += 0 if assert_json_serializable(cv, label="cv") else 1
    return failures


def run() -> int:
    context = CheckContext(
        repo_root=Path(__file__).resolve().parents[1],
        settings_path=Path(__file__).resolve().parents[1] / "configs" / "settings.toml",
    )

    if not context.settings_path.exists():
        print_fail(f'Settings TOML not found: "{context.settings_path}"')
        return 1

    try:
        settings = load_settings(str(context.settings_path))
        print_ok("runtime.load_settings() succeeded")
    except Exception as exc:
        print_fail(f"runtime.load_settings() failed: {exc}")
        return 1

    failures = 0

    try:
        generator = StructuredCvGenerator(settings)
        print_ok("StructuredCvGenerator(settings) succeeded")
    except Exception as exc:
        print_fail(f"StructuredCvGenerator(settings) failed: {exc}")
        return 1

    try:
        result = generator.generate_one()
        print_ok("generate_one() succeeded")
    except Exception as exc:
        print_fail(f"generate_one() failed: {exc}")
        return 1

    failures += validate_cv_shape(result.cv, settings)

    try:
        batch = generator.generate_many(3)
        print_ok("generate_many(3) succeeded")
    except Exception as exc:
        print_fail(f"generate_many(3) failed: {exc}")
        return 1

    failures += 0 if assert_true(len(batch) == 3, ok="generate_many(3) returned 3 results",
                                 fail=f"generate_many(3) returned {len(batch)} results") else 1
    failures += 0 if assert_true(len({item.uuid for item in batch}) == 3, ok="batch UUIDs are unique",
                                 fail="batch UUIDs are not unique") else 1

    if failures == 0:
        print_ok("CV structured generator checks passed")
        return 0

    print_fail(f"CV structured generator checks failed: {failures} issue(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())

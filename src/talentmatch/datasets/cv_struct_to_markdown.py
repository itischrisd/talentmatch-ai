from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class StoreCvStructMarkdownResult:
    """Result of storing a structured CV as Markdown."""
    uuid: str


class CvStructMarkdownRenderer:
    """Renders a structured CV dict into a Markdown document using runtime-provided settings."""

    def __init__(self, settings: Any) -> None:
        self._settings = settings
        self._policy = settings.datasets.cv.markdown

    def render(self, cv_struct: Mapping[str, Any]) -> str:
        person = self._as_mapping(cv_struct.get("person", {}))

        name = self._as_str(person.get("name"))
        email = self._as_str(person.get("email"))
        location = self._as_str(person.get("location"))
        links = self._format_links(self._as_list(person.get("links", [])))

        lines: list[str] = []
        lines.append(self._policy.h1_template.format(name=name))
        lines.append(self._policy.contact_template.format(email=email, location=location, links=links))
        lines.append("")

        summary = self._as_str(cv_struct.get("summary", ""))
        lines.extend(self._section(self._policy.summary_title, [summary] if summary else []))

        skills = self._as_list(cv_struct.get("skills", []))
        skill_lines = [
            self._policy.skill_item_template.format(
                name=self._as_str(self._as_mapping(item).get("name")),
                proficiency=self._as_str(self._as_mapping(item).get("proficiency")),
            )
            for item in skills
        ]
        lines.extend(self._section(self._policy.skills_title, skill_lines))

        certifications = [self._policy.certification_item_template.format(name=self._as_str(c)) for c in
                          self._as_list(cv_struct.get("certifications", []))]
        lines.extend(self._section(self._policy.certifications_title, certifications))

        experience = self._as_list(cv_struct.get("experience", []))
        experience_blocks: list[str] = []
        for job in experience:
            job_map = self._as_mapping(job)
            experience_blocks.extend(self._format_experience(job_map))
            experience_blocks.append("")
        lines.extend(self._section(self._policy.experience_title, self._trim_trailing_blanks(experience_blocks)))

        projects = self._as_list(cv_struct.get("projects", []))
        project_blocks: list[str] = []
        for project in projects:
            project_map = self._as_mapping(project)
            project_blocks.extend(self._format_project(project_map))
            project_blocks.append("")
        lines.extend(self._section(self._policy.projects_title, self._trim_trailing_blanks(project_blocks)))

        education = self._as_list(cv_struct.get("education", []))
        education_lines = [self._format_education_item(self._as_mapping(item)) for item in education]
        lines.extend(self._section(self._policy.education_title, education_lines))

        return "\n".join(self._trim_trailing_blanks(lines)).strip() + "\n"

    def _section(self, title: str, body_lines: list[str]) -> list[str]:
        if not body_lines:
            return []
        lines = [self._policy.section_header_template.format(title=title)]
        lines.extend(self._to_bullets(body_lines))
        lines.append("")
        return lines

    def _to_bullets(self, items: list[str]) -> list[str]:
        normalized = [s.strip() for s in items if isinstance(s, str) and s.strip()]
        return [f"- {item}" for item in normalized]

    def _format_links(self, links: list[Any]) -> str:
        urls = []
        for item in links:
            link = self._as_mapping(item)
            url = link.get("url")
            if isinstance(url, str) and url.strip():
                urls.append(url.strip())
        return self._policy.links_separator.join(urls)

    def _format_experience(self, job: Mapping[str, Any]) -> list[str]:
        title = self._as_str(job.get("title"))
        company = self._as_str(job.get("company"))
        domain = self._as_str(job.get("domain"))

        start = self._format_date(self._as_optional_str(job.get("start_date")))
        end = self._format_date(self._as_optional_str(job.get("end_date"))) if job.get(
            "end_date") else self._policy.present_label
        date_range = self._policy.experience_date_range_template.format(start=start, end=end)

        lines = [
            self._policy.experience_header_template.format(
                title=title,
                company=company,
                domain=domain,
                date_range=date_range,
            )
        ]

        responsibilities = self._as_list(job.get("responsibilities", []))
        for item in responsibilities:
            text = self._as_str(item)
            if text:
                lines.append(self._policy.experience_responsibility_template.format(text=text))

        tech_stack = self._as_list(job.get("tech_stack", []))
        tech_stack_text = ", ".join([self._as_str(x) for x in tech_stack if self._as_str(x)])
        if tech_stack_text:
            lines.append(self._policy.experience_tech_stack_template.format(tech_stack=tech_stack_text))

        return lines

    def _format_project(self, project: Mapping[str, Any]) -> list[str]:
        name = self._as_str(project.get("name"))
        project_type = self._as_str(project.get("type"))
        company = self._as_optional_str(project.get("company"))
        description = self._as_str(project.get("description"))

        lines = [self._policy.project_header_template.format(name=name, type=project_type)]

        if company:
            lines.append(self._policy.project_company_template.format(company=company))

        if description:
            lines.append(self._policy.project_description_template.format(text=description))

        highlights = self._as_list(project.get("highlights", []))
        for item in highlights:
            text = self._as_str(item)
            if text:
                lines.append(self._policy.project_highlight_template.format(text=text))

        tech_stack = self._as_list(project.get("tech_stack", []))
        tech_stack_text = ", ".join([self._as_str(x) for x in tech_stack if self._as_str(x)])
        if tech_stack_text:
            lines.append(self._policy.project_tech_stack_template.format(tech_stack=tech_stack_text))

        return lines

    def _format_education_item(self, item: Mapping[str, Any]) -> str:
        degree = self._as_str(item.get("degree"))
        field = self._as_str(item.get("field"))
        institution = self._as_str(item.get("institution"))
        start_year = item.get("start_year")
        end_year = item.get("end_year")
        return self._policy.education_item_template.format(
            degree=degree,
            field=field,
            institution=institution,
            start_year=start_year,
            end_year=end_year,
        )

    def _format_date(self, iso_value: str | None) -> str:
        if not iso_value:
            return ""
        try:
            parsed = datetime.fromisoformat(iso_value)
            return parsed.strftime(self._policy.date_format)
        except Exception:
            return iso_value

    @staticmethod
    def _trim_trailing_blanks(lines: list[str]) -> list[str]:
        trimmed = list(lines)
        while trimmed and not trimmed[-1].strip():
            trimmed.pop()
        return trimmed

    @staticmethod
    def _as_mapping(value: Any) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        return value if isinstance(value, list) else []

    @staticmethod
    def _as_str(value: Any) -> str:
        return value.strip() if isinstance(value, str) else ""

    @staticmethod
    def _as_optional_str(value: Any) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None


class CvStructMarkdownStore:
    """Stores the Markdown representation of a structured CV under {uuid}.md using runtime-provided base directory."""

    def __init__(self, settings: Any, renderer: CvStructMarkdownRenderer | None = None) -> None:
        self._settings = settings
        self._renderer = renderer or CvStructMarkdownRenderer(settings)
        self._base_dir = Path(settings.paths.cv_markdown_dir)

    def store(self, uuid: str, cv_struct: Mapping[str, Any]) -> StoreCvStructMarkdownResult:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._base_dir / f"{uuid}.md"
        markdown = self._renderer.render(cv_struct)

        file_path.write_text(markdown, encoding="utf-8")
        return StoreCvStructMarkdownResult(uuid=uuid)

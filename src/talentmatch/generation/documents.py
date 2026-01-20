from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Protocol

import markdown
from weasyprint import CSS, HTML

from talentmatch.config.prompts_models import Prompts


class _Invokable(Protocol):
    def invoke(self, prompt: str) -> Any: ...


class DocumentService:
    """
    Renders CVs and RFPs using an LLM and converts Markdown to PDFs
    """

    def __init__(
            self,
            *,
            prompts: Prompts,
            proficiency_levels: list[str],
            pdf_css: str,
            cv_llm: _Invokable,
            rfp_llm: _Invokable
    ) -> None:
        self._prompts = prompts
        self._proficiency_levels = proficiency_levels
        self._pdf_css = pdf_css
        self._cv_llm = cv_llm
        self._rfp_llm = rfp_llm

    def render_cv_markdown(self, profile: dict) -> str:
        """
        Render CV Markdown using the configured template
        :param profile: programmer profile data
        :return: string of rendered CV in Markdown
        """

        skills_text = ", ".join(f"{s.get('name')} ({s.get('proficiency')})" for s in profile.get("skills", []))
        projects_text = ", ".join(profile.get("projects", []))
        certs_text = ", ".join(profile.get("certifications", []))

        template = self._prompts.datasets.cv_markdown
        prompt = template.format(
            name=profile.get("name", ""),
            email=profile.get("email", ""),
            location=profile.get("location", ""),
            skills=skills_text,
            projects=projects_text,
            certifications=certs_text,
            proficiency_levels=", ".join(self._proficiency_levels),
        )
        return self._invoke_llm_markdown(self._cv_llm, prompt, empty_error="LLM returned empty content for CV")

    def render_rfp_markdown(self, rfp: dict) -> str:
        """
        Render RFP Markdown using the configured template
        :param rfp: RFP data
        :return: string of rendered RFP in Markdown
        """

        required_label = self._prompts.datasets.requirement_labels.required
        preferred_label = self._prompts.datasets.requirement_labels.preferred

        lines: list[str] = []
        for req in rfp.get("requirements", []):
            label = required_label if req.get("is_mandatory") else preferred_label
            certs = req.get("preferred_certifications") or []
            cert_text = f" (Preferred certifications: {', '.join(certs)})" if certs else ""
            lines.append(f"- {label}: {req.get('skill_name')} - {req.get('min_proficiency')} level{cert_text}")

        remote = (
            self._prompts.datasets.remote_work_labels.allowed
            if rfp.get("remote_allowed")
            else self._prompts.datasets.remote_work_labels.not_allowed
        )

        template = self._prompts.datasets.rfp_markdown
        prompt = template.format(
            title=rfp.get("title", ""),
            client=rfp.get("client", ""),
            project_type=rfp.get("project_type", ""),
            description=rfp.get("description", ""),
            duration_months=rfp.get("duration_months", ""),
            team_size=rfp.get("team_size", ""),
            budget_range=rfp.get("budget_range", ""),
            start_date=rfp.get("start_date", ""),
            location=rfp.get("location", ""),
            remote_work=remote,
            requirements="\n".join(lines),
        )
        return self._invoke_llm_markdown(self._rfp_llm, prompt, empty_error="LLM returned empty content for RFP")

    def write_markdown_pdf(self, markdown_content: str, *, filename: str, output_dir: Path) -> Path:
        """
        Convert Markdown to PDF and return the resulting file path
        :param markdown_content: content in Markdown format
        :param filename: name of the output PDF file (without extension)
        :param output_dir: directory to write the PDF file to
        :return: path to the resulting PDF file
        """

        output_dir.mkdir(parents=True, exist_ok=True)
        html_content = markdown.markdown(markdown_content)
        pdf_path = output_dir / f"{filename}.pdf"
        HTML(string=html_content).write_pdf(str(pdf_path), stylesheets=[CSS(string=self._pdf_css)])
        return pdf_path

    def _invoke_llm_markdown(self, llm: _Invokable, prompt: str, *, empty_error: str) -> str:
        response = llm.invoke(prompt)
        content = str(getattr(response, "content", ""))
        cleaned = self._strip_fenced_code_blocks(content).strip()
        if not cleaned:
            raise ValueError(empty_error)
        return cleaned

    @staticmethod
    def _strip_fenced_code_blocks(text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", stripped)
            stripped = re.sub(r"\n?```$", "", stripped)
        return stripped.replace("```markdown", "").replace("```", "")

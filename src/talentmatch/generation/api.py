from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from faker import Faker

from talentmatch.config import load_prompts, load_settings, Prompts, Settings
from talentmatch.generation.documents import DocumentService
from talentmatch.generation.io import ensure_dirs, safe_filename, write_json
from talentmatch.generation.programmers import ProgrammerGenerator
from talentmatch.generation.projects import ProjectGenerator
from talentmatch.generation.rfps import RfpGenerator
from talentmatch.infra.llm import AzureLlmProvider

logger = logging.getLogger(__name__)


def generate_dataset() -> dict[str, Any]:
    """
    Generate the complete dataset using counts and policies from TOML
    :return: dictionary with generated dataset details
    """

    settings, prompts, faker, cv_llm, rfp_llm = _prepare_settings_and_llms()

    programmers_dir = Path(settings.paths.programmers_dir)
    projects_dir = Path(settings.paths.projects_dir)
    rfps_dir = Path(settings.paths.rfps_dir)

    ensure_dirs(programmers_dir, projects_dir, rfps_dir)

    documents = DocumentService(
        prompts=prompts,
        proficiency_levels=settings.datasets.skills.proficiency_levels,
        pdf_css=settings.datasets.rendering.pdf_css,
        cv_llm=cv_llm,
        rfp_llm=rfp_llm,
    )

    programmer_generator = ProgrammerGenerator(faker, settings.datasets)
    project_generator = ProjectGenerator(faker, settings.datasets)
    rfp_generator = RfpGenerator(faker, settings.datasets)

    logger.info("Generating %s programmer profiles", settings.generation.num_programmers)
    profiles = programmer_generator.generate(settings.generation.num_programmers)

    for profile in profiles:
        pid = int(profile.get("id", 0))
        profile["person_id"] = f"P-{pid:03d}"

    logger.info("Generating %s projects", settings.generation.num_projects)
    projects = project_generator.generate(settings.generation.num_projects, profiles)

    _enrich_profiles_with_project_assignments(profiles, projects)

    cv_files: list[str] = []
    for idx, profile in enumerate(profiles, start=1):
        logger.info("Generating CV %s/%s: %s", idx, settings.generation.num_programmers, profile["name"])
        markdown_content = documents.render_cv_markdown(profile)
        filename = safe_filename(f"cv_{int(profile['id']):03d}_{profile['name']}")
        pdf_path = documents.write_markdown_pdf(markdown_content, filename=filename, output_dir=programmers_dir)
        cv_files.append(str(pdf_path))

    logger.info("Generating %s RFPs", settings.generation.num_rfps)
    rfps = rfp_generator.generate(settings.generation.num_rfps)

    rfp_files: list[str] = []
    for idx, rfp in enumerate(rfps, start=1):
        logger.info("Generating RFP PDF %s/%s: %s", idx, settings.generation.num_rfps, rfp["title"])
        markdown_content = documents.render_rfp_markdown(rfp)
        filename = safe_filename(f"rfp_{rfp['id']}_{rfp['title']}")
        pdf_path = documents.write_markdown_pdf(markdown_content, filename=filename, output_dir=rfps_dir)
        rfp_files.append(str(pdf_path))

    profiles_path = programmers_dir / "programmer_profiles.json"
    projects_path = projects_dir / "projects.json"
    rfps_path = rfps_dir / "rfps.json"

    write_json(profiles_path, profiles)
    write_json(projects_path, projects)
    write_json(rfps_path, rfps)

    return {
        "profiles": profiles,
        "projects": projects,
        "rfps": rfps,
        "cv_files": cv_files,
        "rfp_files": rfp_files,
        "profiles_file": str(profiles_path),
        "projects_file": str(projects_path),
        "rfps_file": str(rfps_path),
    }


def generate_single_rfp() -> dict[str, Any]:
    """
    Generate a single RFP record along with Markdown and PDF output
    :return: dictionary with generated RFP details
    """

    settings, prompts, faker, cv_llm, rfp_llm = _prepare_settings_and_llms()

    rfps_dir = Path(settings.paths.rfps_dir)
    ensure_dirs(rfps_dir)

    documents = DocumentService(
        prompts=prompts,
        proficiency_levels=settings.datasets.skills.proficiency_levels,
        pdf_css=settings.datasets.rendering.pdf_css,
        cv_llm=cv_llm,
        rfp_llm=rfp_llm,
    )

    generator = RfpGenerator(faker, settings.datasets)
    rfp = generator.generate(1)[0]
    markdown_content = documents.render_rfp_markdown(rfp)
    filename = safe_filename(f"rfp_{rfp['id']}_{rfp['title']}")
    pdf_path = documents.write_markdown_pdf(markdown_content, filename=filename, output_dir=rfps_dir)

    return {"rfp": rfp, "pdf_file": str(pdf_path)}


def _enrich_profiles_with_project_assignments(
        profiles: list[dict[str, Any]],
        projects: list[dict[str, Any]],
) -> None:
    """
    Add structured project assignment info (incl. allocation %) to programmer profiles so CV generation can include it.
    """

    by_id: dict[int, dict[str, Any]] = {int(p["id"]): p for p in profiles if p.get("id") is not None}
    assignments_by_programmer: dict[int, list[dict[str, Any]]] = {int(p["id"]): [] for p in profiles if
                                                                  p.get("id") is not None}

    for project in projects:
        for a in project.get("assigned_programmers", []) or []:
            pid = a.get("programmer_id")
            if pid is None:
                continue
            pid_int = int(pid)
            if pid_int not in assignments_by_programmer:
                continue

            assignments_by_programmer[pid_int].append(
                {
                    "project_id": project.get("id", ""),
                    "project_name": project.get("name", ""),
                    "client": project.get("client", ""),
                    "assignment_start_date": a.get("assignment_start_date", ""),
                    "assignment_end_date": a.get("assignment_end_date", ""),
                    "allocation_percent": a.get("allocation_percent", None),
                }
            )

    for pid, profile in by_id.items():
        items = assignments_by_programmer.get(pid, [])
        items.sort(key=lambda x: str(x.get("assignment_start_date", "")), reverse=True)

        profile["project_assignments"] = items
        # keep a simple list too (useful for any old code / quick display)
        profile["projects"] = [f"{i.get('project_id', '')}" for i in items if i.get("project_id")]


def _prepare_settings_and_llms() -> tuple[Settings, Prompts, Faker, Any, Any]:
    settings = load_settings()
    prompts = load_prompts()

    faker = Faker()
    llm_provider = AzureLlmProvider(settings)
    cv_llm = llm_provider.chat("cv_markdown")
    rfp_llm = llm_provider.chat("rfp_markdown")
    return settings, prompts, faker, cv_llm, rfp_llm

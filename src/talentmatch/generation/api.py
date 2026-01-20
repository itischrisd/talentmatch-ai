from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from faker import Faker
from langchain_openai import AzureChatOpenAI

from talentmatch.config import load_prompts, load_settings, Prompts, Settings
from talentmatch.generation.documents import DocumentService
from talentmatch.generation.io import ensure_dirs, safe_filename, write_json
from talentmatch.generation.programmers import ProgrammerGenerator
from talentmatch.generation.projects import ProjectGenerator
from talentmatch.generation.rfps import RfpGenerator
from talentmatch.infra.llm import AzureLlmProvider

logger = logging.getLogger(__name__)


def generate_dataset(*, settings_toml_path: str | None = None, prompts_toml_path: str | None = None) -> dict[str, Any]:
    """
    Generate the complete dataset using counts and policies from TOML
    :param settings_toml_path: path to settings TOML file
    :param prompts_toml_path: path to prompts TOML file
    :return: dictionary with generated dataset details
    """

    settings, prompts, faker, cv_llm, rfp_llm = _prepare_settings_and_llms(prompts_toml_path, settings_toml_path)

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

    cv_files: list[str] = []
    for idx, profile in enumerate(profiles, start=1):
        logger.info("Generating CV %s/%s: %s", idx, settings.generation.num_programmers, profile["name"])
        markdown_content = documents.render_cv_markdown(profile)
        filename = safe_filename(f"cv_{profile['id']:03d}_{profile['name']}")
        pdf_path = documents.write_markdown_pdf(markdown_content, filename=filename, output_dir=programmers_dir)
        cv_files.append(str(pdf_path))

    logger.info("Generating %s projects", settings.generation.num_projects)
    projects = project_generator.generate(settings.generation.num_projects, profiles)

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


def generate_single_rfp(
        *, settings_toml_path: str | None = None, prompts_toml_path: str | None = None
) -> dict[str, Any]:
    """
    Generate a single RFP record along with Markdown and PDF output
    :param settings_toml_path: path to settings TOML file
    :param prompts_toml_path: path to prompts TOML file
    :return: dictionary with generated RFP details
    """

    settings, prompts, faker, cv_llm, rfp_llm = _prepare_settings_and_llms(prompts_toml_path, settings_toml_path)

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

    return {"rfp": rfp, "markdown": markdown_content, "pdf_file": str(pdf_path)}


def _prepare_settings_and_llms(prompts_toml_path: str | None, settings_toml_path: str | None) -> tuple[
    Settings, Prompts, Faker, AzureChatOpenAI, AzureChatOpenAI]:
    settings = load_settings(settings_toml_path)
    prompts = load_prompts(prompts_toml_path)

    faker = Faker()
    llm_provider = AzureLlmProvider(settings)
    cv_llm = llm_provider.chat("cv_markdown")
    rfp_llm = llm_provider.chat("rfp_markdown")
    return settings, prompts, faker, cv_llm, rfp_llm

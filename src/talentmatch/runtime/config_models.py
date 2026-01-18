from __future__ import annotations

from pydantic import BaseModel, field_validator


class PathsSettings(BaseModel):
    cv_struct_json_dir: str
    cv_pdf_dir: str
    cv_markdown_dir: str
    rfp_struct_json_dir: str
    rfp_markdown_dir: str
    rfp_pdf_dir: str


class AzureOpenAISettings(BaseModel):
    endpoint: str
    api_key: str
    api_version: str
    chat_deployment: str


class LlmUseCaseSettings(BaseModel):
    deployment: str
    temperature: float
    max_tokens: int
    top_p: float
    request_timeout_s: int

    @field_validator("temperature", "top_p")
    @classmethod
    def validate_probability(cls, value: float) -> float:
        if not (0.0 <= value <= 1.0):
            raise ValueError("Value must be within [0.0, 1.0]")
        return value


class LlmUseCasesSettings(BaseModel):
    json_to_markdown: LlmUseCaseSettings


class LlmSettings(BaseModel):
    use_cases: LlmUseCasesSettings


class CvCountRange(BaseModel):
    min: int
    max: int


class CvSeniorityPolicy(BaseModel):
    labels: list[str]
    weights: list[float]


class CvPersonLinkPolicy(BaseModel):
    type: str
    url_template: str


class CvPersonPolicy(BaseModel):
    name_format: str
    email_local_part_format: str
    email_format: str
    link_slug_format: str
    email_domains: list[str]
    locations: list[str]
    seniority: CvSeniorityPolicy
    headline_by_seniority: dict[str, str]
    links: list[CvPersonLinkPolicy]


class CvSkillsProficiencyPolicy(BaseModel):
    levels: list[str]
    weights: list[float]


class CvSkillsPolicy(BaseModel):
    all: list[str]
    count: CvCountRange
    proficiency: CvSkillsProficiencyPolicy


class CvCertificationsPolicy(BaseModel):
    all: list[str]
    count: CvCountRange


class CvEducationEndYearOffsetPolicy(BaseModel):
    min: int
    max: int


class CvEducationPolicy(BaseModel):
    universities: list[str]
    degrees: list[str]
    fields: list[str]
    duration_years: list[int]
    count: CvCountRange
    end_year_offset: CvEducationEndYearOffsetPolicy


class CvJobsBySeniorityRange(BaseModel):
    min: int
    max: int


class CvJobsBySeniorityPolicy(BaseModel):
    junior: CvJobsBySeniorityRange
    mid: CvJobsBySeniorityRange
    senior: CvJobsBySeniorityRange
    lead: CvJobsBySeniorityRange


class CvJobDurationMonthsPolicy(BaseModel):
    min: int
    max: int


class CvGapDaysPolicy(BaseModel):
    min: int
    max: int


class CvTechStackSizePolicy(BaseModel):
    min: int
    max: int


class CvResponsibilitiesCountPolicy(BaseModel):
    min: int
    max: int


class CvExperiencePolicy(BaseModel):
    max_total_years: int
    month_to_days: int
    company_names: list[str]
    job_titles: list[str]
    domains: list[str]
    jobs_by_seniority: CvJobsBySeniorityPolicy
    job_duration_months: CvJobDurationMonthsPolicy
    gap_days: CvGapDaysPolicy
    tech_stack_size: CvTechStackSizePolicy
    responsibilities_count: CvResponsibilitiesCountPolicy


class CvProjectsPolicy(BaseModel):
    count: CvCountRange
    project_types: list[str]
    name_prefixes: list[str]
    name_template: str
    impact_verbs: list[str]
    metrics: list[str]
    description_template: str
    attach_company_probability: float
    primary_tech_count: int
    highlights_count: int
    highlight_templates: list[str]
    tech_stack_size: CvTechStackSizePolicy


class CvTextPolicy(BaseModel):
    fallback_skill: str
    summary_top_skills: int
    summary_max_certs: int
    summary_cert_part_template: str
    summary_cert_part_empty: str
    min_years_of_experience: int
    max_years_of_experience: int
    identifier_replacements: dict[str, str]
    summary_templates: list[str]
    bullets_templates: list[str]


class CvMarkdownPolicy(BaseModel):
    h1_template: str
    contact_template: str
    links_separator: str

    section_header_template: str

    summary_title: str
    skills_title: str
    certifications_title: str
    experience_title: str
    projects_title: str
    education_title: str

    date_format: str
    present_label: str

    skill_item_template: str
    certification_item_template: str

    experience_header_template: str
    experience_date_range_template: str
    experience_responsibility_template: str
    experience_tech_stack_template: str

    project_header_template: str
    project_company_template: str
    project_description_template: str
    project_highlight_template: str
    project_tech_stack_template: str

    education_item_template: str


class CvErrorsPolicy(BaseModel):
    count_must_be_positive: str


class CvDatasetPolicy(BaseModel):
    schema_version: str
    errors: CvErrorsPolicy
    person: CvPersonPolicy
    skills: CvSkillsPolicy
    certifications: CvCertificationsPolicy
    education: CvEducationPolicy
    experience: CvExperiencePolicy
    projects: CvProjectsPolicy
    text: CvTextPolicy
    markdown: CvMarkdownPolicy


class RfpErrorsPolicy(BaseModel):
    count_must_be_positive: str


class RfpTextPolicy(BaseModel):
    id_token_length: int
    id_template: str
    title_templates: list[str]

    start_date_min_days: int
    start_date_max_days: int
    duration_months_min: int
    duration_months_max: int

    team_size_min: int
    team_size_max: int

    executive_summary_templates: list[str]
    business_context_templates: list[str]

    objectives_min_count: int
    objectives_max_count: int
    objective_templates: list[str]

    required_skills_min_count: int
    required_skills_max_count: int
    preferred_skills_min_count: int
    preferred_skills_max_count: int
    preferred_certifications_max_count: int

    deliverables_min_count: int
    deliverables_max_count: int
    deliverable_templates: list[str]

    milestones_min_count: int
    milestones_max_count: int
    milestone_title_templates: list[str]
    milestone_description_templates: list[str]

    acceptance_criteria_min_count: int
    acceptance_criteria_max_count: int
    acceptance_criteria_templates: list[str]

    proposal_guidelines_min_count: int
    proposal_guidelines_max_count: int
    proposal_guideline_templates: list[str]

    evaluation_process_templates: list[str]

    role_responsibilities_min_count: int
    role_responsibilities_max_count: int
    role_responsibility_templates: list[str]


class RfpCatalogPolicy(BaseModel):
    domains: list[str]
    clients: list[str]
    project_types: list[str]

    contract_types: list[str]
    locations: list[str]
    remote_modes: list[str]
    budget_ranges: list[str]

    skills: list[str]
    certifications: list[str]
    proficiency_levels: list[str]


class RfpStaffingRoleSetPolicy(BaseModel):
    name: str
    match_keywords: list[str]
    core_roles: list[str]
    optional_roles: list[str]


class RfpRoleSkillMapPolicy(BaseModel):
    role: str
    skills: list[str]


class RfpStaffingPolicy(BaseModel):
    always_roles: list[str]
    max_per_role: int
    role_weights: dict[str, float]
    seniority_weights: dict[str, float]
    role_sets: list[RfpStaffingRoleSetPolicy]
    role_skill_map: list[RfpRoleSkillMapPolicy]


class RfpDatasetPolicy(BaseModel):
    schema_version: str
    errors: RfpErrorsPolicy
    text: RfpTextPolicy
    catalog: RfpCatalogPolicy
    staffing: RfpStaffingPolicy


class DatasetsSettings(BaseModel):
    cv: CvDatasetPolicy
    rfp: RfpDatasetPolicy


class Settings(BaseModel):
    paths: PathsSettings
    azure_openai: AzureOpenAISettings
    llm: LlmSettings
    datasets: DatasetsSettings

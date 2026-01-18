from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator


class AppSettings(BaseModel):
    name: str
    env: Literal["dev", "prod"]
    timezone: str


class PathsSettings(BaseModel):
    data_dir: str
    runs_dir: str
    inbox_dir: str
    raw_dir: str
    generated_dir: str
    interim_dir: str
    indexes_dir: str
    reports_dir: str
    cv_struct_json_dir: str
    cv_pdf_dir: str
    cv_markdown_dir: str
    rfp_struct_json_dir: str


class RunsSettings(BaseModel):
    use_run_folders: bool
    default_run_prefix: str


class AzureOpenAISettings(BaseModel):
    endpoint: str
    api_key: str
    api_version: str
    chat_deployment: str
    embed_deployment: str
    temperature: float
    max_tokens: int
    top_p: float
    request_timeout_s: int

    @field_validator("temperature", "top_p")
    @classmethod
    def validate_probability(cls, value: float) -> float:
        if not (0.0 <= value <= 1.0):
            raise ValueError("Value must be within [0.0, 1.0].")
        return value


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
    dataset_generation: LlmUseCaseSettings
    json_to_markdown: LlmUseCaseSettings
    agent_orchestrator: LlmUseCaseSettings
    matching_judge: LlmUseCaseSettings


class LlmSettings(BaseModel):
    use_cases: LlmUseCasesSettings


class Neo4jKeySettings(BaseModel):
    person_key: str
    skill_key: str
    company_key: str
    project_key: str
    rfp_key: str


class Neo4jSettings(BaseModel):
    uri: str
    user: str
    password: str
    database: str
    database_default: str
    keys: Neo4jKeySettings


class ChromaSettings(BaseModel):
    url: str
    tenant: str
    database: str
    collection_cv: str
    collection_rfp: str


class IngestSettings(BaseModel):
    default_cv_pdf_dir: str
    default_rfp_dir: str
    default_assignments_dir: str


class ChunkingSettings(BaseModel):
    chunk_size: int
    chunk_overlap: int
    separator: str


class RagVectorHybridSettings(BaseModel):
    enabled: bool
    bm25_weight: float
    vector_weight: float

    @field_validator("bm25_weight", "vector_weight")
    @classmethod
    def validate_weight(cls, value: float) -> float:
        if not (0.0 <= value <= 1.0):
            raise ValueError("Value must be within [0.0, 1.0].")
        return value

    @field_validator("vector_weight")
    @classmethod
    def validate_weight_sum(cls, value: float, info) -> float:
        bm25_weight = info.data.get("bm25_weight")
        if bm25_weight is not None and abs((bm25_weight + value) - 1.0) > 1e-6:
            raise ValueError("bm25_weight + vector_weight must equal 1.0.")
        return value


class RagVectorQueryExpansionSettings(BaseModel):
    enabled: bool
    n_variants: int


class RagVectorRerankSettings(BaseModel):
    enabled: bool
    top_n: int


class RagVectorSettings(BaseModel):
    k: int
    score_threshold: float
    use_mmr: bool
    mmr_lambda: float
    include_metadata: bool
    hybrid: RagVectorHybridSettings
    query_expansion: RagVectorQueryExpansionSettings
    rerank: RagVectorRerankSettings

    @field_validator("mmr_lambda")
    @classmethod
    def validate_mmr_lambda(cls, value: float) -> float:
        if not (0.0 <= value <= 1.0):
            raise ValueError("mmr_lambda must be within [0.0, 1.0].")
        return value


class RagGraphSettings(BaseModel):
    mode: Literal["cypher_qa", "template"]
    max_returned_rows: int
    allow_write_queries: bool


class KgSettings(BaseModel):
    strict_schema: bool
    max_nodes_per_cv: int
    max_edges_per_cv: int


class MatchingWeightsSettings(BaseModel):
    skills: float
    experience: float
    availability: float

    @field_validator("skills", "experience", "availability")
    @classmethod
    def validate_weight(cls, value: float) -> float:
        if not (0.0 <= value <= 1.0):
            raise ValueError("Weight must be within [0.0, 1.0].")
        return value

    @field_validator("availability")
    @classmethod
    def validate_sum(cls, value: float, info) -> float:
        skills = info.data.get("skills")
        experience = info.data.get("experience")
        if skills is None or experience is None:
            return value
        if abs((skills + experience + value) - 1.0) > 1e-6:
            raise ValueError("skills + experience + availability must equal 1.0.")
        return value


class MatchingAvailabilitySettings(BaseModel):
    default_allocation: float
    time_unit: Literal["day", "week"]
    assume_open_end_assignments: bool

    @field_validator("default_allocation")
    @classmethod
    def validate_allocation(cls, value: float) -> float:
        if value <= 0.0:
            raise ValueError("default_allocation must be > 0.")
        return value


class MatchingLlmJudgeSettings(BaseModel):
    enabled: bool
    temperature: float
    max_tokens: int

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, value: float) -> float:
        if not (0.0 <= value <= 1.0):
            raise ValueError("temperature must be within [0.0, 1.0].")
        return value


class MatchingSettings(BaseModel):
    top_k: int
    min_score: float
    weights: MatchingWeightsSettings
    availability: MatchingAvailabilitySettings
    llm_judge: MatchingLlmJudgeSettings


class BiSettings(BaseModel):
    default_engine: Literal["graph", "vector"]
    fallback_engine: Literal["graph", "vector"]


class OrchestrationSettings(BaseModel):
    enabled: bool
    memory_enabled: bool
    max_turns: int


class EvaluationRagasSettings(BaseModel):
    enabled: bool
    faithfulness: bool
    answer_relevancy: bool
    context_precision: bool
    context_recall: bool


class EvaluationSettings(BaseModel):
    enabled: bool
    n_questions_smoke: int
    measure_latency: bool
    ragas: EvaluationRagasSettings


class LoggingSettings(BaseModel):
    json_logs: bool
    log_prompts: bool


class ProjectsPolicy(BaseModel):
    default_count: int
    start_date_past_years: int
    start_date_future_months: int
    duration_months_min: int
    duration_months_max: int
    team_size_min: int
    team_size_max: int
    budget_amount_min: int
    budget_amount_max: int
    budget_is_optional: bool
    budget_present_probability: float
    end_date_only_for_completed: bool
    project_type_labels: list[str]
    client_name_labels: list[str]
    name_template: str
    description_template: str
    status_weights: dict[str, int]

    @field_validator("budget_present_probability")
    @classmethod
    def validate_budget_probability(cls, value: float) -> float:
        if not (0.0 <= value <= 1.0):
            raise ValueError("budget_present_probability must be within [0.0, 1.0].")
        return value

    @field_validator("duration_months_max")
    @classmethod
    def validate_duration_range(cls, value: int, info) -> int:
        minimum = info.data.get("duration_months_min")
        if minimum is not None and value < minimum:
            raise ValueError("duration_months_max must be >= duration_months_min.")
        return value

    @field_validator("team_size_max")
    @classmethod
    def validate_team_size_range(cls, value: int, info) -> int:
        minimum = info.data.get("team_size_min")
        if minimum is not None and value < minimum:
            raise ValueError("team_size_max must be >= team_size_min.")
        return value


class ProjectRequirementsPolicy(BaseModel):
    requirements_count_min: int
    requirements_count_max: int
    mandatory_probability: float
    skills_source: Literal["from_profiles", "fallback_list"]
    fallback_skill_names: list[str]
    proficiency_levels: list[str]

    @field_validator("mandatory_probability")
    @classmethod
    def validate_mandatory_probability(cls, value: float) -> float:
        if not (0.0 <= value <= 1.0):
            raise ValueError("mandatory_probability must be within [0.0, 1.0].")
        return value

    @field_validator("requirements_count_max")
    @classmethod
    def validate_requirements_range(cls, value: int, info) -> int:
        minimum = info.data.get("requirements_count_min")
        if minimum is not None and value < minimum:
            raise ValueError("requirements_count_max must be >= requirements_count_min.")
        return value


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
    default_seed: int
    projects: ProjectsPolicy
    project_requirements: ProjectRequirementsPolicy
    cv: CvDatasetPolicy
    rfp: RfpDatasetPolicy


class Settings(BaseModel):
    app: AppSettings
    paths: PathsSettings
    runs: RunsSettings
    azure_openai: AzureOpenAISettings
    llm: LlmSettings
    neo4j: Neo4jSettings
    chroma: ChromaSettings
    ingest: IngestSettings
    chunking: ChunkingSettings
    rag_vector: RagVectorSettings
    rag_graph: RagGraphSettings
    kg: KgSettings
    matching: MatchingSettings
    bi: BiSettings
    orchestration: OrchestrationSettings
    evaluation: EvaluationSettings
    logging: LoggingSettings
    datasets: DatasetsSettings

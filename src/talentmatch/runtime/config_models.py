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


class DatasetsSettings(BaseModel):
    default_seed: int
    projects: ProjectsPolicy
    project_requirements: ProjectRequirementsPolicy


class Settings(BaseModel):
    app: AppSettings
    paths: PathsSettings
    runs: RunsSettings
    azure_openai: AzureOpenAISettings
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

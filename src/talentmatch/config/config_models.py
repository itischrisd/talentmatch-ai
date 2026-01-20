from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator, AliasChoices


class ConfigurationError(ValueError):
    """
    Raised when configuration is missing or invalid
    """


class IntRange(BaseModel):
    """
    Closed integer range used by generators
    """

    min: int = Field(..., ge=0)
    max: int = Field(..., ge=0)

    @model_validator(mode="after")
    def validate_order(self) -> IntRange:
        if self.max < self.min:
            raise ConfigurationError("Range max must be >= min")
        return self

    def pick(self) -> int:
        from random import randint

        return randint(int(self.min), int(self.max))


class PathsSettings(BaseModel):
    """
    Output paths for generated artifacts
    """

    programmers_dir: str
    rfps_dir: str
    projects_dir: str


class GenerationSettings(BaseModel):
    """
    Counts of generated items
    """

    num_programmers: int = Field(..., gt=0)
    num_projects: int = Field(..., gt=0)
    num_rfps: int = Field(..., gt=0)


class AzureOpenAiSettings(BaseModel):
    """
    Azure OpenAI settings (secrets provided via environment)
    """

    endpoint: str
    api_key: SecretStr
    api_version: str
    chat_deployment: str


class LlmUseCaseSettings(BaseModel):
    """
    LLM parameters for a specific generation use-case
    """

    deployment: str = Field(validation_alias=AliasChoices("deployment", "model"))
    temperature: float = Field(..., ge=0.0, le=1.0)
    max_tokens: int = Field(..., gt=0)
    top_p: float = Field(..., ge=0.0, le=1.0)
    request_timeout_s: int = Field(..., gt=0)


class LlmSettings(BaseModel):
    """
    LLM configuration root
    """

    use_cases: dict[str, LlmUseCaseSettings]



class SkillsDataset(BaseModel):
    """
    Skill catalog and proficiency policy
    """

    catalog: list[str]
    count: IntRange
    proficiency_levels: list[str]
    proficiency_weights: list[float]

    @model_validator(mode="after")
    def validate_proficiency_policy(self) -> SkillsDataset:
        if not self.catalog:
            raise ConfigurationError("datasets.skills.catalog must not be empty")
        if not self.proficiency_levels:
            raise ConfigurationError("datasets.skills.proficiency_levels must not be empty")
        if len(self.proficiency_levels) != len(self.proficiency_weights):
            raise ConfigurationError("datasets.skills proficiency_levels and proficiency_weights must match in length")
        return self


class ProgrammerDataset(BaseModel):
    """
    Programmer-profile generation policy
    """

    project_names: list[str]
    project_count: IntRange
    certifications: list[str]
    certification_count: IntRange

    @model_validator(mode="after")
    def validate_lists(self) -> ProgrammerDataset:
        if not self.project_names:
            raise ConfigurationError("datasets.programmers.project_names must not be empty")
        if not self.certifications:
            raise ConfigurationError("datasets.programmers.certifications must not be empty")
        return self


class ProjectStatusPolicy(BaseModel):
    """
    Project status labels and sampling weights
    """

    labels: list[str]
    weights: list[float]

    @model_validator(mode="after")
    def validate_weights(self) -> ProjectStatusPolicy:
        if not self.labels:
            raise ConfigurationError("datasets.projects.status.labels must not be empty")
        if len(self.labels) != len(self.weights):
            raise ConfigurationError("datasets.projects.status labels and weights must match in length")
        return self


class ProjectsDataset(BaseModel):
    """
    Project generation policy
    """

    project_types: list[str]
    clients: list[str]
    name_template: str
    description_template: str
    start_date_offset_days: IntRange
    duration_months: IntRange
    team_size: IntRange
    budget_amount: IntRange
    budget_has_value_probability: float
    status: ProjectStatusPolicy
    completed_status: str
    assignable_statuses: list[str]
    requirements_count: IntRange
    mandatory_probability: float

    @field_validator("budget_has_value_probability", "mandatory_probability")
    @classmethod
    def validate_probability(cls, value: float) -> float:
        if not (0.0 <= float(value) <= 1.0):
            raise ConfigurationError("Probability must be within [0.0, 1.0]")
        return float(value)

    @model_validator(mode="after")
    def validate_statuses(self) -> ProjectsDataset:
        if self.completed_status not in self.status.labels:
            raise ConfigurationError(
                "datasets.projects.completed_status must be present in datasets.projects.status.labels")
        unknown = [s for s in self.assignable_statuses if s not in self.status.labels]
        if unknown:
            raise ConfigurationError("datasets.projects.assignable_statuses must be a subset of status.labels")
        return self


class RfpRequirementDataset(BaseModel):
    """
    RFP requirement catalog policy
    """

    skills: list[str]
    preferred_certifications: list[str]
    requirement_count: IntRange
    min_proficiency_levels: list[str]
    mandatory_probability: float
    preferred_certifications_max_count: int = Field(..., ge=0)

    @field_validator("mandatory_probability")
    @classmethod
    def validate_probability(cls, value: float) -> float:
        if not (0.0 <= float(value) <= 1.0):
            raise ConfigurationError("Probability must be within [0.0, 1.0]")
        return float(value)

    @model_validator(mode="after")
    def validate_lists(self) -> RfpRequirementDataset:
        if not self.skills:
            raise ConfigurationError("datasets.rfps.requirements.skills must not be empty")
        if not self.min_proficiency_levels:
            raise ConfigurationError("datasets.rfps.requirements.min_proficiency_levels must not be empty")
        return self


class RfpsDataset(BaseModel):
    """
    RFP generation policy
    """

    rfp_types: list[str]
    clients: list[str]
    budget_ranges: list[str]
    title_template: str
    description_template: str
    start_date_offset_days: IntRange
    duration_months: IntRange
    team_size: IntRange
    remote_allowed_probability: float
    requirements: RfpRequirementDataset

    @field_validator("remote_allowed_probability")
    @classmethod
    def validate_probability(cls, value: float) -> float:
        if not (0.0 <= float(value) <= 1.0):
            raise ConfigurationError("Probability must be within [0.0, 1.0]")
        return float(value)

    @model_validator(mode="after")
    def validate_lists(self) -> RfpsDataset:
        if not self.rfp_types:
            raise ConfigurationError("datasets.rfps.rfp_types must not be empty")
        if not self.clients:
            raise ConfigurationError("datasets.rfps.clients must not be empty")
        if not self.budget_ranges:
            raise ConfigurationError("datasets.rfps.budget_ranges must not be empty")
        return self


class AssignmentsDataset(BaseModel):
    """
    Assignment generation policy
    """

    assignment_probability: float
    assignment_end_days_before: IntRange

    @field_validator("assignment_probability")
    @classmethod
    def validate_probability(cls, value: float) -> float:
        if not (0.0 <= float(value) <= 1.0):
            raise ConfigurationError("Probability must be within [0.0, 1.0]")
        return float(value)


class RenderingDataset(BaseModel):
    """
    Rendering policy for PDF output
    """

    pdf_css: str


class DatasetsSettings(BaseModel):
    """
    All dataset catalogs and generation policies
    """

    skills: SkillsDataset
    programmers: ProgrammerDataset
    projects: ProjectsDataset
    rfps: RfpsDataset
    assignments: AssignmentsDataset
    rendering: RenderingDataset


class Settings(BaseModel):
    """
    Application settings root
    """

    paths: PathsSettings
    generation: GenerationSettings
    llm: LlmSettings
    datasets: DatasetsSettings
    azure_openai: AzureOpenAiSettings

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Settings:
        return cls.model_validate(payload)

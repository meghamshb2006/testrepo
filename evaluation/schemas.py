from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class BenchmarkCase(BaseModel):
    case_id: str
    question: str

    expected_drawing_ids: list[str] = Field(default_factory=list)
    expected_drawing_numbers: list[str] = Field(default_factory=list)
    expected_filenames: list[str] = Field(default_factory=list)

    expected_answer_terms: list[str] = Field(default_factory=list)
    forbidden_answer_terms: list[str] = Field(default_factory=list)

    expected_confidence_level: str | None = None

    answerable: bool = True
    category: str | None = None
    notes: str | None = None

    candidate_limit: int | None = None
    top_k: int | None = None
    max_context_characters: int | None = None

    @field_validator("case_id", "question")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("must not be blank")

        return value.strip()

    @field_validator("expected_confidence_level")
    @classmethod
    def validate_confidence_level(cls, value: str | None) -> str | None:
        if value is None:
            return value

        normalised = value.strip().upper()

        if normalised not in {"HIGH", "MEDIUM", "LOW"}:
            raise ValueError(
                "expected_confidence_level must be HIGH, MEDIUM, or LOW"
            )

        return normalised

    @field_validator(
        "candidate_limit",
        "top_k",
        "max_context_characters",
    )
    @classmethod
    def must_be_positive_when_set(cls, value: int | None) -> int | None:
        if value is None:
            return value

        if not isinstance(value, int) or value < 1:
            raise ValueError("must be an integer >= 1")

        return value

    @model_validator(mode="after")
    def validate_limit_relationship(self) -> BenchmarkCase:
        if (
            self.top_k is not None
            and self.candidate_limit is not None
            and self.top_k > self.candidate_limit
        ):
            raise ValueError("top_k must not exceed candidate_limit")

        return self


class BenchmarkDataset(BaseModel):
    name: str
    version: str
    description: str | None = None
    cases: list[BenchmarkCase]

    @field_validator("name", "version")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("must not be blank")

        return value.strip()

    @model_validator(mode="after")
    def validate_unique_case_ids(self) -> BenchmarkDataset:
        case_ids = [case.case_id for case in self.cases]
        duplicates = sorted(
            {
                case_id
                for case_id in case_ids
                if case_ids.count(case_id) > 1
            }
        )

        if duplicates:
            raise ValueError(
                "duplicate case_id values: " + ", ".join(duplicates)
            )

        return self


class RetrievalEvaluationResult(BaseModel):
    case_id: str
    question: str
    expected_identifiers: list[str] = Field(default_factory=list)
    retrieved_identifiers: list[str] = Field(default_factory=list)
    hit_at_1: bool
    hit_at_3: bool
    hit_at_5: bool
    reciprocal_rank: float
    result_count: int
    candidate_count: int
    latency_ms: float
    error: str | None = None
    category: str | None = None
    context_length: int = 0
    confidence_score: float | None = None
    confidence_level: str | None = None
    expected_confidence_level: str | None = None
    confidence_level_match: bool | None = None
    exact_identifier_match: bool | None = None
    diagnostics: dict | None = None


class AnswerEvaluationResult(BaseModel):
    case_id: str
    question: str
    answer: str
    answerable: bool
    grounded: bool
    expected_terms_found: list[str] = Field(default_factory=list)
    expected_terms_missing: list[str] = Field(default_factory=list)
    forbidden_terms_found: list[str] = Field(default_factory=list)
    source_match: bool
    refusal_correct: bool | None = None
    latency_ms: float
    error: str | None = None
    category: str | None = None


class EvaluationSummary(BaseModel):
    dataset_name: str
    dataset_version: str
    total_cases: int

    retrieval_cases: int
    answer_cases: int

    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    mean_reciprocal_rank: float

    answer_term_recall: float
    source_accuracy: float
    refusal_accuracy: float
    grounded_response_rate: float

    retrieval_latency_mean_ms: float
    retrieval_latency_p95_ms: float
    answer_latency_mean_ms: float
    answer_latency_p95_ms: float

    mean_context_length: float = 0.0
    confidence_high_rate: float = 0.0
    confidence_medium_rate: float = 0.0
    confidence_low_rate: float = 0.0
    confidence_accuracy: float | None = None

    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    exact_identifier_match_rate: float = 0.0
    mean_retrieved_documents: float = 0.0
    confidence_calibration: float | None = None
    category_metrics: dict[str, dict[str, float]] = Field(default_factory=dict)

    failures: int

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import (
    CandidateCreator,
    Convertibility,
    EvidenceAccessStatus,
    EvidenceSourceKind,
    FindingSeverity,
    MatchMode,
    ReviewDecision,
    RiskLevel,
)

SCHEMA_VERSION: Literal["1.0"] = "1.0"


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class VersionedModel(DomainModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION


class SourceFile(DomainModel):
    role: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SourceManifest(DomainModel):
    files: tuple[SourceFile, ...]


class Finding(DomainModel):
    code: str = Field(min_length=1)
    severity: FindingSeverity
    message: str = Field(min_length=1)
    data_path: str | None = None
    question_id: str | None = None
    related_constraints: tuple[str, ...] = ()
    blocking: bool = False


class ValidationReport(VersionedModel):
    report_id: str = Field(min_length=1)
    candidate_id: str | None = None
    revision: int | None = Field(default=None, ge=1)
    input_checks: tuple[Finding, ...] = ()
    syntax_checks: tuple[Finding, ...] = ()
    type_checks: tuple[Finding, ...] = ()
    coverage_checks: tuple[Finding, ...] = ()
    logic_checks: tuple[Finding, ...] = ()
    validator_version: str = Field(min_length=1)
    is_valid: bool
    validated_at: datetime

    @model_validator(mode="after")
    def validity_matches_findings(self) -> ValidationReport:
        findings = (
            self.input_checks
            + self.syntax_checks
            + self.type_checks
            + self.coverage_checks
            + self.logic_checks
        )
        if self.is_valid and any(item.blocking for item in findings):
            raise ValueError("is_valid cannot be true when a blocking finding exists")
        return self


class Question(VersionedModel):
    question_id: str = Field(min_length=1)
    ordinal: int = Field(ge=0)
    raw_text: str = Field(min_length=1)
    source_location: str = Field(min_length=1)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    intent_family: str | None = None
    requires_external_evidence: bool = False


class AtomicConstraint(DomainModel):
    constraint_id: str = Field(min_length=1)
    semantic_role: str = Field(min_length=1)
    target_concept: str = Field(min_length=1)
    match_mode: MatchMode | None = None
    typed_value: Any | None = None
    polarity: Literal["positive", "negative"] = "positive"
    group_path: tuple[str, ...] = ()
    boundary_semantics: dict[str, Any] | None = None
    must_preserve: bool = True
    evidence_refs: tuple[str, ...] = ()


class NormalizedIntent(VersionedModel):
    question_id: str = Field(min_length=1)
    intent_version: str = Field(min_length=1)
    atomic_constraints: tuple[AtomicConstraint, ...]
    required_semantics: tuple[str, ...] = ()
    external_facts: tuple[str, ...] = ()
    convertibility: Convertibility = Convertibility.UNKNOWN
    warnings: tuple[Finding, ...] = ()


class QueryPayload(DomainModel):
    kind: Literal["query"] = "query"
    intent: NormalizedIntent
    ast: dict[str, Any]
    rendered_query: str = Field(min_length=1)


class RejectionPayload(DomainModel):
    kind: Literal["rejection"] = "rejection"
    rejection_text: str = Field(min_length=1)
    reason_code: str = Field(min_length=1)
    unsupported_constraints: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()


CandidatePayload = Annotated[QueryPayload | RejectionPayload, Field(discriminator="kind")]


class CandidateAnswer(VersionedModel):
    candidate_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    created_by: CandidateCreator
    input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    payload: CandidatePayload


class EvidenceFact(DomainModel):
    name: str = Field(min_length=1)
    value: str = Field(min_length=1)
    source_excerpt_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class EvidenceRecord(VersionedModel):
    evidence_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    source_kind: EvidenceSourceKind
    source_locator: str = Field(min_length=1)
    original_source_locator: str | None = None
    retrieved_at: datetime | None = None
    content_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    access_status: EvidenceAccessStatus
    extracted_facts: tuple[EvidenceFact, ...] = ()
    equivalence_assessment: dict[str, Any] | None = None
    verified_by: str | None = None
    verified_at: datetime | None = None
    is_sufficient: bool = False


class RiskItem(DomainModel):
    item_id: str = Field(min_length=1)
    code: str = Field(min_length=1)
    description: str = Field(min_length=1)
    required: bool = True
    resolved: bool = False
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    notes: str | None = None


class RiskAssessment(VersionedModel):
    question_id: str = Field(min_length=1)
    risk_level: RiskLevel
    risk_items: tuple[RiskItem, ...] = ()
    requires_manual_confirmation: bool = True
    requires_evidence_review: bool = False
    assessment_version: str = Field(min_length=1)


class ReviewRecord(VersionedModel):
    review_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    candidate_revision: int = Field(ge=1)
    validation_report_id: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    decision: ReviewDecision
    reviewed_evidence_ids: tuple[str, ...] = ()
    checked_risk_item_ids: tuple[str, ...] = ()
    revision_note: str | None = None
    confirmed_at: datetime | None = None


class FinalAnswer(VersionedModel):
    question_id: str = Field(min_length=1)
    candidate_revision: int = Field(ge=1)
    answer_kind: Literal["query", "rejection"]
    query_text: str = Field(min_length=1)
    validation_report_id: str = Field(min_length=1)
    review_record_id: str = Field(min_length=1)
    finalized_at: datetime
    finalization_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class AnswerItem(DomainModel):
    question_id: str = Field(alias="题号", min_length=1)
    query: str = Field(alias="查询语句", min_length=1)


class AnswerSheet(DomainModel):
    participant_name: str = Field(alias="选手名称", min_length=1)
    package_id: str = Field(alias="参赛包编号", min_length=1)
    answers: tuple[AnswerItem, ...] = Field(alias="答案", min_length=1)


class CompetitionPackage(VersionedModel):
    run_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    issued_at: datetime | None = None
    participant_name: str | None = None
    source_manifest: SourceManifest
    questions: tuple[Question, ...] = Field(min_length=1)
    template_question_ids: tuple[str, ...] = Field(min_length=1)
    original_order: tuple[str, ...] = Field(min_length=1)
    rules_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    import_report: ValidationReport
    created_at: datetime

    @model_validator(mode="after")
    def validate_question_identity(self) -> CompetitionPackage:
        question_ids = [question.question_id for question in self.questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("question IDs must be unique")
        if set(question_ids) != set(self.template_question_ids):
            raise ValueError("question and template ID sets must match")
        if self.original_order != tuple(question_ids):
            raise ValueError("original_order must exactly match source question order")
        if len({question.ordinal for question in self.questions}) != len(self.questions):
            raise ValueError("question ordinals must be unique")
        return self

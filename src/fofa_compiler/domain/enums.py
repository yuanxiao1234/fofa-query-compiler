from enum import StrEnum

FIXED_REJECTION_TEXT = "该需求不能直接转换为FOFA搜索语句"


class ProcessingStatus(StrEnum):
    IMPORTED = "imported"
    CANDIDATE_READY = "candidate_ready"
    VALIDATION_FAILED = "validation_failed"
    BLOCKED_EVIDENCE = "blocked_evidence"
    AWAITING_REVIEW = "awaiting_review"
    REVIEW_CHANGES_REQUIRED = "review_changes_required"
    READY_TO_FINALIZE = "ready_to_finalize"
    FINALIZED = "finalized"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    SUFFICIENT = "sufficient"
    BLOCKED = "blocked"


class EvidenceSourceKind(StrEnum):
    OFFICIAL_PRIMARY = "official_primary"
    OFFICIAL_ALTERNATIVE = "official_alternative"
    VERIFIED_ARCHIVE = "verified_archive"
    USER_PROVIDED = "user_provided"
    PROJECT_RULE_REFERENCE = "project_rule_reference"


class EvidenceAccessStatus(StrEnum):
    ACCESSIBLE = "accessible"
    UNAVAILABLE = "unavailable"
    CHANGED = "changed"
    INVALID = "invalid"


class MatchMode(StrEnum):
    EXACT = "exact"
    CONTAINS = "contains"
    REGEX = "regex"
    EXISTS = "exists"
    COMPARISON = "comparison"
    RANGE = "range"


class LogicalOperator(StrEnum):
    AND = "and"
    OR = "or"
    NOT = "not"


class Convertibility(StrEnum):
    UNKNOWN = "unknown"
    CONVERTIBLE = "convertible"
    NOT_CONVERTIBLE = "not_convertible"
    BLOCKED_EVIDENCE = "blocked_evidence"


class CandidateCreator(StrEnum):
    RULE = "rule"
    LLM_ADAPTER = "llm_adapter"
    REVIEWER = "reviewer"


class ReviewDecision(StrEnum):
    CONFIRMED = "confirmed"
    REVISED = "revised"
    RETURNED = "returned"


class FindingSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

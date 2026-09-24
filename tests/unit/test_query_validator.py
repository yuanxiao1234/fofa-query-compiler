from datetime import UTC, datetime

from fofa_compiler.domain.enums import Convertibility, MatchMode
from fofa_compiler.domain.ir import And, Predicate
from fofa_compiler.domain.models import AtomicConstraint, NormalizedIntent
from fofa_compiler.domain.query_validator import validate_query


def predicate(field: str, value, value_type: str, constraint: str = "c1") -> Predicate:  # type: ignore[no-untyped-def]
    return Predicate.model_validate(
        {
            "field": field,
            "operator": "=",
            "value": value,
            "value_type": value_type,
            "constraint_refs": [constraint],
            "evidence_refs": [f"fields.yaml:{field}"],
        }
    )


def intent(*constraint_ids: str) -> NormalizedIntent:
    return NormalizedIntent(
        question_id="Q1",
        intent_version="test/1",
        atomic_constraints=tuple(
            AtomicConstraint(
                constraint_id=value,
                semantic_role="field_match",
                target_concept=value,
                match_mode=MatchMode.EXACT,
            )
            for value in constraint_ids
        ),
        convertibility=Convertibility.CONVERTIBLE,
    )


def test_valid_query_passes_all_layers() -> None:
    report = validate_query(
        intent=intent("c1"),
        node=predicate("port", 443, "integer"),
        validated_at=datetime(2026, 9, 24, tzinfo=UTC),
    )
    assert report.is_valid is True


def test_unknown_field_invalid_value_and_missing_coverage_are_all_reported() -> None:
    report = validate_query(
        intent=intent("c1", "c2"),
        node=predicate("unknown", 70000, "integer"),
        validated_at=datetime(2026, 9, 24, tzinfo=UTC),
    )
    assert report.is_valid is False
    assert {finding.code for finding in report.type_checks} == {"UNKNOWN_FIELD"}
    assert {finding.code for finding in report.coverage_checks} == {"MISSING_REQUIRED_CONSTRAINT"}


def test_contradiction_is_blocking() -> None:
    report = validate_query(
        intent=intent("c1", "c2"),
        node=And(
            children=(
                predicate("country", "US", "text", "c1"),
                predicate("country", "CN", "text", "c2"),
            )
        ),
        validated_at=datetime(2026, 9, 24, tzinfo=UTC),
    )
    assert report.is_valid is False
    assert report.logic_checks[0].code == "MUTUALLY_EXCLUSIVE_VALUES"


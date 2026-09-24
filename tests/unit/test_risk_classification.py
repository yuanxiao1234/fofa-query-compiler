from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fofa_compiler.domain.enums import CandidateCreator, RiskLevel
from fofa_compiler.domain.models import (
    CandidateAnswer,
    NormalizedIntent,
    QueryPayload,
    Question,
)
from fofa_compiler.domain.risk import assess_risk


@pytest.mark.parametrize(
    ("ast", "text", "external", "expected"),
    [
        (
            {
                "kind": "predicate",
                "field": "title",
                "operator": "=",
                "value": "a.*",
                "value_type": "regex",
                "constraint_refs": ["c"],
                "evidence_refs": ["e"],
            },
            "普通题",
            False,
            "REGEX",
        ),
        (
            {
                "kind": "group",
                "child": {
                    "kind": "not",
                    "child": {
                        "kind": "predicate",
                        "field": "title",
                        "operator": "=",
                        "value": "x",
                        "value_type": "text",
                        "constraint_refs": ["c"],
                        "evidence_refs": ["e"],
                    },
                },
            },
            "普通题",
            False,
            "COMPLEX_GROUPING",
        ),
        (
            {
                "kind": "predicate",
                "field": "cert.fingerprint",
                "operator": "=",
                "value": "a" * 40,
                "value_type": "hash",
                "constraint_refs": ["c"],
                "evidence_refs": ["e"],
            },
            "普通题",
            False,
            "FINGERPRINT",
        ),
        (
            {
                "kind": "predicate",
                "field": "title",
                "operator": "=",
                "value": 'a"b',
                "value_type": "text",
                "constraint_refs": ["c"],
                "evidence_refs": ["e"],
            },
            "普通题",
            False,
            "ESCAPING",
        ),
        (
            {
                "kind": "predicate",
                "field": "title",
                "operator": "=",
                "value": "x",
                "value_type": "text",
                "constraint_refs": ["c"],
                "evidence_refs": ["e"],
            },
            "需要外部资料",
            True,
            "EXTERNAL_EVIDENCE",
        ),
    ],
)
def test_high_risk_reasons(
    ast: dict[str, object], text: str, external: bool, expected: str
) -> None:
    question = Question(
        question_id="Q1",
        ordinal=0,
        raw_text=text,
        source_location="x",
        fingerprint="0" * 64,
        requires_external_evidence=external,
    )
    candidate = CandidateAnswer(
        candidate_id="c1",
        question_id="Q1",
        revision=1,
        created_by=CandidateCreator.RULE,
        input_fingerprint="1" * 64,
        created_at=datetime(2026, 9, 24, tzinfo=UTC),
        payload=QueryPayload(
            intent=NormalizedIntent(question_id="Q1", intent_version="1", atomic_constraints=()),
            ast=ast,
            rendered_query="test",
        ),
    )

    assessment = assess_risk(question, candidate)

    assert assessment.risk_level is RiskLevel.HIGH
    assert expected in {item.code for item in assessment.risk_items}
    assert assessment.requires_evidence_review is (external or expected == "FINGERPRINT")

from typing import Any

import pytest

from fofa_compiler.domain.errors import ValidationError
from fofa_compiler.infrastructure.semantic_parser import SemanticParser


class Provider:
    def __init__(self, value: dict[str, Any]) -> None:
        self.value = value

    def propose(self, *, question_id: str, raw_text: str) -> dict[str, Any]:
        return self.value


def valid_proposal(question_id: str = "Q1") -> dict[str, Any]:
    return {
        "intent": {
            "question_id": question_id,
            "intent_version": "provider/1",
            "atomic_constraints": [
                {
                    "constraint_id": f"{question_id}:c1",
                    "semantic_role": "field_match",
                    "target_concept": "ip",
                }
            ],
            "convertibility": "convertible",
        },
        "node": {
            "kind": "predicate",
            "field": "ip",
            "operator": "=",
            "value": "1.1.1.1",
            "value_type": "ipv4",
            "constraint_refs": [f"{question_id}:c1"],
            "evidence_refs": ["fields.yaml:ip"],
        },
    }


def test_offline_rule_does_not_call_provider() -> None:
    class FailingProvider:
        def propose(self, *, question_id: str, raw_text: str) -> dict[str, Any]:
            raise AssertionError("provider must not be called")

    parsed = SemanticParser(provider=FailingProvider()).parse(
        "M001-S009", "请查询 IP 地址为 20.247.40.92 的资产。"
    )
    assert parsed is not None
    assert parsed.rule_id == "core.ip.exact"


def test_provider_may_only_return_validated_structured_ir() -> None:
    parsed = SemanticParser(provider=Provider(valid_proposal())).parse("Q1", "unmatched")
    assert parsed is not None
    assert parsed.rule_id == "provider.structured_ir"


@pytest.mark.parametrize(
    "proposal",
    [
        {**valid_proposal(), "rendered_query": 'ip="1.1.1.1"'},
        {"intent": valid_proposal()["intent"], "node": {"kind": "unknown"}},
        valid_proposal("OTHER"),
    ],
)
def test_provider_query_strings_invalid_nodes_and_wrong_ids_are_rejected(
    proposal: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        SemanticParser(provider=Provider(proposal)).parse("Q1", "unmatched")


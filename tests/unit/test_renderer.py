import pytest
from pydantic import TypeAdapter, ValidationError

from fofa_compiler.domain.ir import And, Group, Not, Or, Predicate, QueryNode
from fofa_compiler.domain.renderer import escape_literal, normalize, render


def predicate(field: str, operator: str, value: str | int, value_type: str = "text") -> Predicate:
    return Predicate.model_validate(
        {
            "field": field,
            "operator": operator,
            "value": value,
            "value_type": value_type,
            "constraint_refs": [f"constraint:{field}"],
            "evidence_refs": [f"field:{field}"],
        }
    )


def test_predicates_quote_text_and_typed_integers() -> None:
    assert render(predicate("ip", "=", "20.247.40.92", "ipv4")) == 'ip="20.247.40.92"'
    # FOFA comparison values remain quoted even when the IR retains an integer type.
    assert render(predicate("port", "=", 3000, "integer")) == 'port="3000"'


def test_literal_escaping_preserves_quotes_backslashes_and_control_characters() -> None:
    raw = '"exception": "Symfony\\Component"\nnext\tvalue'
    assert escape_literal(raw) == '\\"exception\\": \\"Symfony\\\\Component\\"\\nnext\\tvalue'
    assert render(predicate("body", "=", raw)) == (
        'body="\\"exception\\": \\"Symfony\\\\Component\\"\\nnext\\tvalue"'
    )


def test_nested_boolean_precedence_is_always_explicit() -> None:
    node = And(
        children=(
            Or(children=(predicate("title", "=", "Jenkins"), predicate("body", "=", "jenkins"))),
            predicate("country", "!=", "CN"),
        )
    )
    assert render(node) == '((title="Jenkins" || body="jenkins") && country!="CN")'


def test_group_and_not_are_retained() -> None:
    node = Group(child=Not(child=predicate("domain", "=", "example.com")))
    assert render(node) == '(!(domain="example.com"))'


def test_normalization_is_deterministic_without_flattening_groups() -> None:
    first = predicate("port", "=", 443, "integer")
    second = Group(child=predicate("country", "=", "JP"))
    a = normalize(And(children=(first, second)))
    b = normalize(And(children=(second, first)))
    assert a == b
    assert render(a) == '((country="JP") && port="443")'


def test_discriminated_union_rejects_unknown_nodes_and_invalid_value_types() -> None:
    adapter = TypeAdapter(QueryNode)
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "xor", "children": []})
    with pytest.raises(ValidationError):
        predicate("port", "=", "3000", "integer")

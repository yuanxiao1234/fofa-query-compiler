from fofa_compiler.domain.contradictions import find_contradictions
from fofa_compiler.domain.ir import And, Or, Predicate


def predicate(field: str, operator: str, value: str) -> Predicate:
    return Predicate(
        field=field,
        operator=operator,  # type: ignore[arg-type]
        value=value,
        value_type="text",
        constraint_refs=("c",),
        evidence_refs=("e",),
    )


def test_same_single_value_field_cannot_require_different_values() -> None:
    node = And(children=(predicate("country", "=", "US"), predicate("country", "=", "CN")))
    assert find_contradictions(node)[0].code == "MUTUALLY_EXCLUSIVE_VALUES"


def test_same_value_cannot_be_required_and_excluded() -> None:
    node = And(children=(predicate("country", "=", "US"), predicate("country", "!=", "US")))
    assert find_contradictions(node)[0].code == "REQUIRED_AND_EXCLUDED"


def test_multi_value_text_fields_are_not_falsely_rejected() -> None:
    node = And(children=(predicate("body", "=", "admin"), predicate("body", "=", "login")))
    assert find_contradictions(node) == ()


def test_alternatives_are_not_contradictions() -> None:
    node = Or(children=(predicate("country", "=", "US"), predicate("country", "=", "CN")))
    assert find_contradictions(node) == ()


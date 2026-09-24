from __future__ import annotations

from dataclasses import dataclass

from fofa_compiler.domain.ir import And, Group, Not, Or, Predicate, QueryNode

SINGLE_VALUE_FIELDS = {
    "asn",
    "cert.is_equal",
    "cert.is_expired",
    "cert.is_match",
    "cert.is_valid",
    "cert.sn",
    "city",
    "country",
    "ip",
    "port",
    "region",
    "status_code",
    "tls.version",
}


@dataclass(frozen=True, slots=True)
class LogicProblem:
    code: str
    message: str
    field: str


def _predicate_key(predicate: Predicate) -> tuple[str, str]:
    return predicate.field, str(predicate.value)


def _and_scope_predicates(node: QueryNode) -> list[Predicate]:
    if isinstance(node, Predicate):
        return [node]
    if isinstance(node, Group):
        return _and_scope_predicates(node.child)
    if isinstance(node, And):
        values: list[Predicate] = []
        for child in node.children:
            if not isinstance(child, Or):
                values.extend(_and_scope_predicates(child))
        return values
    return []


def find_contradictions(node: QueryNode) -> tuple[LogicProblem, ...]:
    problems: list[LogicProblem] = []

    def visit(current: QueryNode) -> None:
        if isinstance(current, And):
            predicates = _and_scope_predicates(current)
            required: dict[str, set[str]] = {}
            excluded: set[tuple[str, str]] = set()
            for predicate in predicates:
                key = _predicate_key(predicate)
                if predicate.operator in {"!=", "!==", "!*="}:
                    excluded.add(key)
                elif predicate.operator in {"=", "=="}:
                    required.setdefault(predicate.field, set()).add(str(predicate.value))
            for field, values in required.items():
                if field in SINGLE_VALUE_FIELDS and len(values) > 1:
                    problems.append(
                        LogicProblem(
                            code="MUTUALLY_EXCLUSIVE_VALUES",
                            message=f"单值字段 {field} 同时要求多个不同值",
                            field=field,
                        )
                    )
                if any((field, value) in excluded for value in values):
                    problems.append(
                        LogicProblem(
                            code="REQUIRED_AND_EXCLUDED",
                            message=f"字段 {field} 的同一值被同时要求和排除",
                            field=field,
                        )
                    )
            for child in current.children:
                visit(child)
        elif isinstance(current, Or):
            for child in current.children:
                visit(child)
        elif isinstance(current, Group):
            visit(current.child)
        elif isinstance(current, Not) and isinstance(current.child, Not):
            problems.append(
                LogicProblem(
                    code="REDUNDANT_DOUBLE_NEGATION",
                    message="查询包含可消除的双重否定",
                    field="",
                )
            )

    visit(node)
    return tuple(problems)


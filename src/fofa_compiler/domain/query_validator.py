from __future__ import annotations

import hashlib
from datetime import datetime

from fofa_compiler.domain.contradictions import find_contradictions
from fofa_compiler.domain.enums import FindingSeverity
from fofa_compiler.domain.ir import And, Group, Not, Or, Predicate, QueryNode
from fofa_compiler.domain.models import Finding, NormalizedIntent, ValidationReport
from fofa_compiler.domain.renderer import render
from fofa_compiler.domain.value_validation import validate_predicate_value
from fofa_compiler.rules.registry import load_rule_data


def _predicates(node: QueryNode) -> tuple[Predicate, ...]:
    if isinstance(node, Predicate):
        return (node,)
    if isinstance(node, (Not, Group)):
        return _predicates(node.child)
    if isinstance(node, (And, Or)):
        return tuple(item for child in node.children for item in _predicates(child))
    return ()


def validate_query(
    *,
    intent: NormalizedIntent,
    node: QueryNode,
    validated_at: datetime,
    candidate_id: str | None = None,
    revision: int | None = None,
) -> ValidationReport:
    syntax_checks: list[Finding] = []
    type_checks: list[Finding] = []
    coverage_checks: list[Finding] = []
    logic_checks: list[Finding] = []
    registry = load_rule_data("fields.yaml").get("fields", {})
    predicates = _predicates(node)

    for predicate in predicates:
        field_data = registry.get(predicate.field) if isinstance(registry, dict) else None
        if not isinstance(field_data, dict):
            type_checks.append(
                Finding(
                    code="UNKNOWN_FIELD",
                    severity=FindingSeverity.ERROR,
                    message=f"字段 {predicate.field} 未在注册表中定义",
                    related_constraints=predicate.constraint_refs,
                    blocking=True,
                )
            )
            continue
        operators = field_data.get("operators", [])
        if predicate.operator not in operators:
            type_checks.append(
                Finding(
                    code="UNSUPPORTED_OPERATOR",
                    severity=FindingSeverity.ERROR,
                    message=f"字段 {predicate.field} 不支持操作符 {predicate.operator}",
                    related_constraints=predicate.constraint_refs,
                    blocking=True,
                )
            )
        value_types = field_data.get("value_types", [])
        if predicate.value_type not in value_types:
            type_checks.append(
                Finding(
                    code="UNSUPPORTED_VALUE_TYPE",
                    severity=FindingSeverity.ERROR,
                    message=f"字段 {predicate.field} 不支持值类型 {predicate.value_type}",
                    related_constraints=predicate.constraint_refs,
                    blocking=True,
                )
            )
        for value_problem in validate_predicate_value(predicate):
            type_checks.append(
                Finding(
                    code=value_problem.code,
                    severity=FindingSeverity.ERROR,
                    message=value_problem.message,
                    related_constraints=predicate.constraint_refs,
                    blocking=True,
                )
            )

    required = {
        item.constraint_id for item in intent.atomic_constraints if item.must_preserve
    }
    represented = {reference for predicate in predicates for reference in predicate.constraint_refs}
    for missing in sorted(required - represented):
        coverage_checks.append(
            Finding(
                code="MISSING_REQUIRED_CONSTRAINT",
                severity=FindingSeverity.ERROR,
                message=f"必需原子约束 {missing} 未映射到查询 AST",
                related_constraints=(missing,),
                blocking=True,
            )
        )

    for logic_problem in find_contradictions(node):
        logic_checks.append(
            Finding(
                code=logic_problem.code,
                severity=FindingSeverity.ERROR,
                message=logic_problem.message,
                blocking=True,
            )
        )

    try:
        rendered = render(node)
        if not rendered:
            raise ValueError("empty rendered query")
    except (TypeError, ValueError) as exc:
        syntax_checks.append(
            Finding(
                code="RENDER_FAILURE",
                severity=FindingSeverity.ERROR,
                message=f"查询无法确定性渲染: {exc}",
                blocking=True,
            )
        )
        rendered = ""

    all_findings = syntax_checks + type_checks + coverage_checks + logic_checks
    report_seed = (
        f"{intent.question_id}\0{candidate_id or ''}\0{revision or ''}\0{rendered}\0"
        + "\0".join(item.code for item in all_findings)
    )
    return ValidationReport(
        report_id="validation-" + hashlib.sha256(report_seed.encode()).hexdigest()[:20],
        candidate_id=candidate_id,
        revision=revision,
        syntax_checks=tuple(syntax_checks),
        type_checks=tuple(type_checks),
        coverage_checks=tuple(coverage_checks),
        logic_checks=tuple(logic_checks),
        validator_version="query-validator/1",
        is_valid=not any(item.blocking for item in all_findings),
        validated_at=validated_at,
    )

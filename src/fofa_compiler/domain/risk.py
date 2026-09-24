from __future__ import annotations

from fofa_compiler.domain.enums import RiskLevel
from fofa_compiler.domain.models import CandidateAnswer, Question, RiskAssessment, RiskItem


def _walk_ast(node: object, *, depth: int = 0) -> tuple[set[str], int, bool]:
    if not isinstance(node, dict):
        return set(), depth, False
    kind = node.get("kind")
    fields: set[str] = set()
    escaping = False
    maximum_depth = depth
    if kind == "predicate":
        field = node.get("field")
        value = node.get("value")
        value_type = node.get("value_type")
        if isinstance(field, str):
            fields.add(field)
        if value_type == "regex":
            fields.add("__regex__")
        escaping = isinstance(value, str) and any(char in value for char in ('"', "\\", "\n"))
    for child in node.get("children", ()):
        child_fields, child_depth, child_escaping = _walk_ast(child, depth=depth + 1)
        fields.update(child_fields)
        maximum_depth = max(maximum_depth, child_depth)
        escaping = escaping or child_escaping
    if "child" in node:
        child_fields, child_depth, child_escaping = _walk_ast(node["child"], depth=depth + 1)
        fields.update(child_fields)
        maximum_depth = max(maximum_depth, child_depth)
        escaping = escaping or child_escaping
    return fields, maximum_depth, escaping


def assess_risk(question: Question, candidate: CandidateAnswer) -> RiskAssessment:
    codes: list[tuple[str, str]] = []
    requires_evidence = question.requires_external_evidence
    if candidate.payload.kind == "rejection":
        codes.append(("SAFE_REJECTION", "核对拒绝结论及固定文本"))
    else:
        fields, depth, escaping = _walk_ast(candidate.payload.ast)
        if "__regex__" in fields:
            codes.append(("REGEX", "核对正则表达式语义与边界"))
        if depth >= 2:
            codes.append(("COMPLEX_GROUPING", "核对嵌套布尔分组与否定范围"))
        if escaping:
            codes.append(("ESCAPING", "核对引号、反斜杠和换行转义"))
        if any("fingerprint" in field or "jarm" in field for field in fields):
            codes.append(("FINGERPRINT", "核对指纹来源及算法"))
            requires_evidence = True
        if any(field.startswith(("cert.", "tls.")) for field in fields):
            codes.append(("CERTIFICATE_TLS", "核对证书或 TLS 字段语义"))
        if candidate.payload.intent.warnings:
            codes.append(("LOW_CONFIDENCE", "核对自动解析警告和不完整证明"))
    if question.requires_external_evidence:
        codes.append(("EXTERNAL_EVIDENCE", "核对外部事实及来源"))

    unique = dict(codes)
    items = tuple(
        RiskItem(
            item_id=f"{question.question_id}:{code.lower()}",
            code=code,
            description=description,
        )
        for code, description in unique.items()
    )
    return RiskAssessment(
        question_id=question.question_id,
        risk_level=RiskLevel.HIGH if items else RiskLevel.LOW,
        risk_items=items,
        requires_evidence_review=requires_evidence,
        assessment_version="risk-rules/1",
    )

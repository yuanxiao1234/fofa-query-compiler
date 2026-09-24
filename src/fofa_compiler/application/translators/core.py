from __future__ import annotations

import re
from dataclasses import dataclass

from fofa_compiler.domain.enums import Convertibility, MatchMode
from fofa_compiler.domain.ir import And, Predicate, QueryNode
from fofa_compiler.domain.models import AtomicConstraint, NormalizedIntent
from fofa_compiler.rules.registry import field_evidence_ref, mapping


@dataclass(frozen=True, slots=True)
class RuleTranslation:
    rule_id: str
    intent: NormalizedIntent
    node: QueryNode


def _predicate(
    *,
    question_id: str,
    index: int,
    field: str,
    operator: str,
    value: str | int,
    value_type: str,
    concept: str,
    match_mode: MatchMode,
) -> tuple[Predicate, AtomicConstraint]:
    constraint_id = f"{question_id}:c{index}"
    evidence_ref = field_evidence_ref(field)
    predicate = Predicate.model_validate(
        {
            "field": field,
            "operator": operator,
            "value": value,
            "value_type": value_type,
            "constraint_refs": [constraint_id],
            "evidence_refs": [evidence_ref],
        }
    )
    constraint = AtomicConstraint(
        constraint_id=constraint_id,
        semantic_role="field_match",
        target_concept=concept,
        match_mode=match_mode,
        typed_value=value,
        evidence_refs=(evidence_ref,),
    )
    return predicate, constraint


def _result(
    question_id: str,
    rule_id: str,
    parts: list[tuple[Predicate, AtomicConstraint]],
) -> RuleTranslation:
    predicates = tuple(item[0] for item in parts)
    constraints = tuple(item[1] for item in parts)
    node: QueryNode = predicates[0] if len(predicates) == 1 else And(children=predicates)
    return RuleTranslation(
        rule_id=rule_id,
        intent=NormalizedIntent(
            question_id=question_id,
            intent_version="core-rules/1",
            atomic_constraints=constraints,
            required_semantics=tuple(item.target_concept for item in constraints),
            convertibility=Convertibility.CONVERTIBLE,
        ),
        node=node,
    )


def _country(question_id: str, index: int, source_name: str) -> tuple[Predicate, AtomicConstraint]:
    mapped = mapping("countries", source_name)
    return _predicate(
        question_id=question_id,
        index=index,
        field="country",
        operator="=",
        value=str(mapped["value"]),
        value_type="text",
        concept=f"country:{source_name}",
        match_mode=MatchMode.EXACT,
    )


def _protocol(question_id: str, index: int, source_name: str) -> tuple[Predicate, AtomicConstraint]:
    mapped = mapping("protocols", source_name)
    return _predicate(
        question_id=question_id,
        index=index,
        field="protocol",
        operator="=",
        value=str(mapped["value"]),
        value_type="text",
        concept=f"protocol:{source_name}",
        match_mode=MatchMode.EXACT,
    )


def translate_core(question_id: str, raw_text: str) -> RuleTranslation | None:
    """Translate only fully recognized core sentences; never return a partial query."""
    text = " ".join(raw_text.split())
    match = re.fullmatch(r"请查询 IP 地址为 ([0-9.]+) 的资产。", text)
    if match:
        return _result(
            question_id,
            "core.ip.exact",
            [
                _predicate(
                    question_id=question_id,
                    index=1,
                    field="ip",
                    operator="=",
                    value=match.group(1),
                    value_type="ipv4",
                    concept="ip_address",
                    match_mode=MatchMode.EXACT,
                )
            ],
        )

    match = re.fullmatch(r"请查询 ([0-9./]+) 网段内的全部资产。", text)
    if match:
        return _result(
            question_id,
            "core.ip.cidr",
            [
                _predicate(
                    question_id=question_id,
                    index=1,
                    field="ip",
                    operator="=",
                    value=match.group(1),
                    value_type="cidr",
                    concept="ip_network",
                    match_mode=MatchMode.EXACT,
                )
            ],
        )

    match = re.fullmatch(r"请查询主域是 ([A-Za-z0-9.-]+) 的全部资产。", text)
    if match:
        return _result(
            question_id,
            "core.domain.exact",
            [
                _predicate(
                    question_id=question_id,
                    index=1,
                    field="domain",
                    operator="==",
                    value=match.group(1),
                    value_type="text",
                    concept="root_domain",
                    match_mode=MatchMode.EXACT,
                )
            ],
        )

    match = re.fullmatch(r"搜索网站名为 ([A-Za-z0-9.-]+) 的资产。", text)
    if match:
        return _result(
            question_id,
            "core.host.exact",
            [
                _predicate(
                    question_id=question_id,
                    index=1,
                    field="host",
                    operator="==",
                    value=match.group(1),
                    value_type="text",
                    concept="website_host",
                    match_mode=MatchMode.EXACT,
                )
            ],
        )

    match = re.fullmatch(r"我想找域名里带有 ([^ ]+) 的所有网站。", text)
    if match:
        return _result(
            question_id,
            "core.domain.contains",
            [
                _predicate(
                    question_id=question_id,
                    index=1,
                    field="domain",
                    operator="=",
                    value=match.group(1),
                    value_type="text",
                    concept="domain_substring",
                    match_mode=MatchMode.CONTAINS,
                )
            ],
        )

    match = re.fullmatch(r"搜索位于(.+)的资产。", text)
    if match:
        try:
            country_part = _country(question_id, 1, match.group(1))
        except ValueError:
            return None
        return _result(question_id, "core.country.exact", [country_part])

    match = re.fullmatch(r"搜索自治系统号为 ([0-9]+) 的资产。", text)
    if match:
        return _result(
            question_id,
            "core.asn.exact",
            [
                _predicate(
                    question_id=question_id,
                    index=1,
                    field="asn",
                    operator="=",
                    value=int(match.group(1)),
                    value_type="integer",
                    concept="autonomous_system_number",
                    match_mode=MatchMode.EXACT,
                )
            ],
        )

    match = re.fullmatch(r"请查询开放 ([0-9]+) 端口的资产。", text)
    if match:
        return _result(
            question_id,
            "core.port.exact",
            [
                _predicate(
                    question_id=question_id,
                    index=1,
                    field="port",
                    operator="=",
                    value=int(match.group(1)),
                    value_type="integer",
                    concept="open_port",
                    match_mode=MatchMode.EXACT,
                )
            ],
        )

    match = re.fullmatch(r"搜索 (SSH) 协议且端口为 ([0-9]+) 的资产。", text)
    if match:
        return _result(
            question_id,
            "core.protocol.port",
            [
                _protocol(question_id, 1, match.group(1)),
                _predicate(
                    question_id=question_id,
                    index=2,
                    field="port",
                    operator="=",
                    value=int(match.group(2)),
                    value_type="integer",
                    concept="open_port",
                    match_mode=MatchMode.EXACT,
                ),
            ],
        )

    match = re.fullmatch(r"我想看使用 (TCP) 协议的数据。", text)
    if match:
        return _result(
            question_id, "core.protocol.exact", [_protocol(question_id, 1, match.group(1))]
        )

    match = re.fullmatch(
        r"我想找互联网上提供 (SNMP) 网络管理服务的资产，不限定端口。",  # noqa: RUF001
        text,
    )
    if match:
        return _result(
            question_id, "core.protocol.service", [_protocol(question_id, 1, match.group(1))]
        )

    match = re.fullmatch(r"我想找中国的 (DNS) 服务。", text)
    if match:
        return _result(
            question_id,
            "core.country.protocol",
            [_country(question_id, 1, "中国"), _protocol(question_id, 2, match.group(1))],
        )

    match = re.fullmatch(r"我想搜索暴露在公网的 (GitLab) 资产。", text)
    if match:
        mapped = mapping("products", match.group(1))
        return _result(
            question_id,
            "core.product.app",
            [
                _predicate(
                    question_id=question_id,
                    index=1,
                    field=str(mapped["field"]),
                    operator="=",
                    value=str(mapped["value"]),
                    value_type="text",
                    concept=f"product:{match.group(1)}",
                    match_mode=MatchMode.EXACT,
                )
            ],
        )

    return None

from __future__ import annotations

import re

from fofa_compiler.application.translators.core import (
    RuleTranslation,
    _country,
    _predicate,
    _result,
)
from fofa_compiler.domain.enums import MatchMode
from fofa_compiler.domain.ir import Predicate
from fofa_compiler.domain.models import AtomicConstraint


def _text(
    question_id: str,
    index: int,
    field: str,
    value: str,
    concept: str,
    *,
    exact: bool = False,
) -> tuple[Predicate, AtomicConstraint]:
    return _predicate(
        question_id=question_id,
        index=index,
        field=field,
        operator="==" if exact else "=",
        value=value,
        value_type="text",
        concept=concept,
        match_mode=MatchMode.EXACT if exact else MatchMode.CONTAINS,
    )


def _boolean(
    question_id: str, index: int, field: str, value: bool, concept: str
) -> tuple[Predicate, AtomicConstraint]:
    return _predicate(
        question_id=question_id,
        index=index,
        field=field,
        operator="=",
        value=value,
        value_type="boolean",
        concept=concept,
        match_mode=MatchMode.EXACT,
    )


def _serial(question_id: str, index: int, value: str) -> tuple[Predicate, AtomicConstraint]:
    return _predicate(
        question_id=question_id,
        index=index,
        field="cert.sn",
        operator="=",
        value=value,
        value_type="certificate_serial",
        concept="certificate_serial_number",
        match_mode=MatchMode.EXACT,
    )


def translate_certificate(question_id: str, raw_text: str) -> RuleTranslation | None:
    text = " ".join(raw_text.split())

    match = re.fullmatch(r"请帮我查询由 (.+) 组织签发、而且证书还没有过期的资产。", text)
    if match:
        return _result(
            question_id,
            "certificate.issuer_org.unexpired",
            [
                _text(question_id, 1, "cert.issuer.org", match.group(1), "issuer_organization"),
                _boolean(question_id, 2, "cert.is_expired", False, "certificate_unexpired"),
            ],
        )

    match = re.fullmatch(r"我想找证书持有者名称是 ([^、]+)、但域名不是 ([^ ]+) 的域名数据。", text)
    if match:
        subject = _text(
            question_id, 1, "cert.subject.cn", match.group(1), "subject_common_name", exact=True
        )
        domain = _predicate(
            question_id=question_id,
            index=2,
            field="domain",
            operator="!=",
            value=match.group(2),
            value_type="text",
            concept="excluded_root_domain",
            match_mode=MatchMode.EXACT,
        )
        return _result(question_id, "certificate.subject_cn.domain_exclusion", [subject, domain])

    simple_patterns = (
        (r"请查询证书全文中包含 (.+) 的资产。", "cert", "certificate.content"),
        (
            r"搜索证书持有者组织名称包含 (.+) 这个关键词的资产。",
            "cert.subject.org",
            "certificate.subject_org",
        ),
        (r"证书里面只要有(.+)这个根域名的都给我找出来。", "cert.domain", "certificate.domain"),
        (r"我想搜索证书持有者名称根域是 (.+) 的资产。", "cert.domain", "certificate.domain"),
    )
    for expression, field, rule_id in simple_patterns:
        match = re.fullmatch(expression, text)
        if match:
            return _result(
                question_id,
                rule_id,
                [_text(question_id, 1, field, match.group(1), rule_id)],
            )

    match = re.fullmatch(r"请查询证书包含 (.+)，但根域名不是 (.+) 的资产。", text)  # noqa: RUF001
    if match:
        excluded = _predicate(
            question_id=question_id,
            index=2,
            field="domain",
            operator="!=",
            value=match.group(2),
            value_type="text",
            concept="excluded_root_domain",
            match_mode=MatchMode.EXACT,
        )
        return _result(
            question_id,
            "certificate.content.domain_exclusion",
            [_text(question_id, 1, "cert", match.group(1), "certificate_content"), excluded],
        )

    match = re.fullmatch(r"找仍在使用 TLS ([0-9.]+)，且证书尚未过期的资产。", text)  # noqa: RUF001
    if match:
        return _result(
            question_id,
            "certificate.tls_version.unexpired",
            [
                _text(
                    question_id,
                    1,
                    "tls.version",
                    f"TLS {match.group(1)}",
                    "tls_version",
                    exact=True,
                ),
                _boolean(question_id, 2, "cert.is_expired", False, "certificate_unexpired"),
            ],
        )

    match = re.fullmatch(
        r"找 JARM 为 ([0-9a-f]+)、网站响应码为 ([0-9]+)，且响应头包含 (.+) 的资产。",  # noqa: RUF001
        text,
    )
    if match:
        return _result(
            question_id,
            "certificate.jarm.web_constraints",
            [
                _text(question_id, 1, "jarm", match.group(1), "jarm", exact=True),
                _predicate(
                    question_id=question_id,
                    index=2,
                    field="status_code",
                    operator="=",
                    value=int(match.group(2)),
                    value_type="integer",
                    concept="http_status_code",
                    match_mode=MatchMode.EXACT,
                ),
                _text(question_id, 3, "header", match.group(3), "header_marker"),
            ],
        )

    if text == "我想找证书颁发者与持有者不匹配的资产。":
        return _result(
            question_id,
            "certificate.issuer_subject_mismatch",
            [_boolean(question_id, 1, "cert.is_equal", False, "issuer_subject_mismatch")],
        )

    match = re.fullmatch(r"帮我找(.+)的资产，要求证书与域名不匹配。", text)  # noqa: RUF001
    if match:
        try:
            country = _country(question_id, 1, match.group(1))
        except ValueError:
            return None
        return _result(
            question_id,
            "certificate.country.domain_mismatch",
            [
                country,
                _boolean(
                    question_id, 2, "cert.is_match", False, "certificate_domain_mismatch"
                ),
            ],
        )

    match = re.fullmatch(r"查找(.+) TLS JA3S 指纹等于 ([0-9a-f]+) 的资产。", text)
    if match:
        try:
            country = _country(question_id, 1, match.group(1))
        except ValueError:
            return None
        return _result(
            question_id,
            "certificate.country.ja3s",
            [
                country,
                _text(question_id, 2, "tls.ja3s", match.group(2), "tls_ja3s", exact=True),
            ],
        )

    match = re.fullmatch(
        r"查找使用以下 TLS 证书的资产：证书颁发者通用名称为 (.+)，证书详情中的 Serial Number 显示为 ([0-9A-Fa-f:]+)。 转换成fofa能查的特征。",  # noqa: E501, RUF001
        text,
    )
    if match:
        serial_decimal = str(int(match.group(2).replace(":", ""), 16))
        return _result(
            question_id,
            "certificate.issuer_cn.serial",
            [
                _text(
                    question_id,
                    1,
                    "cert.issuer.cn",
                    match.group(1),
                    "issuer_common_name",
                    exact=True,
                ),
                _serial(question_id, 2, serial_decimal),
            ],
        )
    return None

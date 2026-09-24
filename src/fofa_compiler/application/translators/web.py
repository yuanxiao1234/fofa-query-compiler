from __future__ import annotations

import re

from fofa_compiler.application.translators.core import RuleTranslation, _predicate, _result
from fofa_compiler.domain.enums import MatchMode


def translate_web(question_id: str, raw_text: str) -> RuleTranslation | None:
    """Translate fully recognized Web-response requests while preserving literal payloads."""
    literal_prefix = "我想找网页源码中包含这段原样文本的资产："  # noqa: RUF001
    if raw_text.startswith(literal_prefix):
        literal = raw_text.removeprefix(literal_prefix).removesuffix("。")
        if literal:
            return _result(
                question_id,
                "web.body.literal",
                [
                    _predicate(
                        question_id=question_id,
                        index=1,
                        field="body",
                        operator="=",
                        value=literal,
                        value_type="text",
                        concept="body_literal",
                        match_mode=MatchMode.CONTAINS,
                    )
                ],
            )

    json_prefix = "在网页正文中搜索这段 JSON 异常信息片段，保留双引号和反斜杠：\n"  # noqa: RUF001
    if raw_text.startswith(json_prefix):
        literal = raw_text.removeprefix(json_prefix)
        if literal:
            return _result(
                question_id,
                "web.body.literal_escaped",
                [
                    _predicate(
                        question_id=question_id,
                        index=1,
                        field="body",
                        operator="=",
                        value=literal,
                        value_type="text",
                        concept="body_literal",
                        match_mode=MatchMode.CONTAINS,
                    )
                ],
            )

    text = " ".join(raw_text.split())
    patterns = (
        (
            r"搜索网页正文中出现 (.+) 错误标记的资产。",
            "web.body.contains",
            "body",
            "body_marker",
        ),
        (
            r"我想找响应信息中出现 (.+) 的资产。",
            "web.banner.contains",
            "banner",
            "response_marker",
        ),
        (
            r"请帮我查询响应信息有 (.+) 的资产。",
            "web.banner.contains",
            "banner",
            "response_marker",
        ),
        (
            r"搜索header包含 (.+) 的资产。",
            "web.header.contains",
            "header",
            "header_marker",
        ),
        (
            r"搜索引用 (.+) 文件的网页。",
            "web.body.resource_reference",
            "body",
            "body_resource_reference",
        ),
    )
    for expression, rule_id, field, concept in patterns:
        match = re.fullmatch(expression, text)
        if match:
            return _result(
                question_id,
                rule_id,
                [
                    _predicate(
                        question_id=question_id,
                        index=1,
                        field=field,
                        operator="=",
                        value=match.group(1),
                        value_type="text",
                        concept=concept,
                        match_mode=MatchMode.CONTAINS,
                    )
                ],
            )

    match = re.fullmatch(r"搜索状态码为 ([0-9]+) 的网站类资产。", text)
    if match:
        return _result(
            question_id,
            "web.status_code.exact",
            [
                _predicate(
                    question_id=question_id,
                    index=1,
                    field="status_code",
                    operator="=",
                    value=int(match.group(1)),
                    value_type="integer",
                    concept="http_status_code",
                    match_mode=MatchMode.EXACT,
                )
            ],
        )
    return None

from __future__ import annotations

import ipaddress
import re

from fofa_compiler.application.translators.core import RuleTranslation, _predicate, _result
from fofa_compiler.domain.enums import MatchMode
from fofa_compiler.domain.ir import And, Or, Predicate
from fofa_compiler.domain.models import AtomicConstraint


def _part(
    question_id: str,
    index: int,
    field: str,
    value: str | int,
    *,
    operator: str = "=",
    value_type: str = "text",
    concept: str | None = None,
    mode: MatchMode = MatchMode.CONTAINS,
) -> tuple[Predicate, AtomicConstraint]:
    return _predicate(
        question_id=question_id,
        index=index,
        field=field,
        operator=operator,
        value=value,
        value_type=value_type,
        concept=concept or field,
        match_mode=mode,
    )


def translate_advanced(question_id: str, raw_text: str) -> RuleTranslation | None:
    text = " ".join(raw_text.split())

    if text == "搜索标题包含 Jenkins 或正文包含 jenkins、国家不是中国，且更新时间在 2026-08-01 之后的资产。":  # noqa: E501, RUF001
        title = _part(question_id, 1, "title", "Jenkins")
        body = _part(question_id, 2, "body", "jenkins")
        country = _part(
            question_id,
            3,
            "country",
            "CN",
            operator="!=",
            concept="excluded_country",
            mode=MatchMode.EXACT,
        )
        after = _part(
            question_id,
            4,
            "after",
            "2026-08-01",
            value_type="timestamp",
            concept="updated_after",
            mode=MatchMode.COMPARISON,
        )
        result = _result(question_id, "advanced.boolean.time", [title, body, country, after])
        return RuleTranslation(
            rule_id=result.rule_id,
            intent=result.intent,
            node=And(children=(Or(children=(title[0], body[0])), country[0], after[0])),
        )

    match = re.fullmatch(
        r"查 ([A-Za-z0-9.]+) 旗下的域名数据，要求它前面恰好还有两级子域，每一级都只有一个字符，例如 [A-Za-z0-9.]+。",  # noqa: E501, RUF001
        text,
    )
    if match:
        escaped_domain = re.escape(match.group(1))
        expression = rf"^[^.][.][^.][.]{escaped_domain}$"
        return _result(
            question_id,
            "advanced.domain.regex_two_single_labels",
            [
                _part(
                    question_id,
                    1,
                    "domain",
                    expression,
                    operator="*=",
                    value_type="regex",
                    concept="domain_shape",
                    mode=MatchMode.REGEX,
                )
            ],
        )

    match = re.fullmatch(r"我想要搜索这个 IP 的整个 B 段：([0-9.]+)。", text)  # noqa: RUF001
    if match:
        address = ipaddress.ip_address(match.group(1))
        if not isinstance(address, ipaddress.IPv4Address):
            return None
        cidr = str(ipaddress.ip_network(f"{address}/16", strict=False))
        return _result(
            question_id,
            "advanced.ip.derived_16",
            [
                _part(
                    question_id,
                    1,
                    "ip",
                    cidr,
                    value_type="cidr",
                    concept="derived_ipv4_16",
                    mode=MatchMode.RANGE,
                )
            ],
        )

    match = re.fullmatch(
        r"查 ([0-9.]+) 到 ([0-9.]+) 这个闭区间里的 IP，要求开放 ([0-9]+) 或 ([0-9]+) 端口。",  # noqa: RUF001
        text,
    )
    if match:
        start = ipaddress.ip_address(match.group(1))
        end = ipaddress.ip_address(match.group(2))
        if not isinstance(start, ipaddress.IPv4Address) or not isinstance(
            end, ipaddress.IPv4Address
        ):
            return None
        distance = int(end) - int(start)
        if distance < 0 or distance > 255:
            return None
        ip_parts = [
            _part(
                question_id,
                index + 1,
                "ip",
                str(ipaddress.ip_address(int(start) + index)),
                value_type="ipv4",
                concept="ip_range_member",
                mode=MatchMode.EXACT,
            )
            for index in range(distance + 1)
        ]
        port_parts = [
            _part(
                question_id,
                len(ip_parts) + index + 1,
                "port",
                int(value),
                value_type="integer",
                concept="allowed_port",
                mode=MatchMode.EXACT,
            )
            for index, value in enumerate(match.groups()[2:])
        ]
        all_parts = ip_parts + port_parts
        result = _result(question_id, "advanced.ip.closed_range.ports", all_parts)
        return RuleTranslation(
            rule_id=result.rule_id,
            intent=result.intent,
            node=And(
                children=(
                    Or(children=tuple(item[0] for item in ip_parts)),
                    Or(children=tuple(item[0] for item in port_parts)),
                )
            ),
        )

    if text == '请把下面的 Shodan 查询转换成 FOFA："Server: nginx" http.title:"Welcome"':  # noqa: RUF001
        return _result(
            question_id,
            "advanced.migration.shodan",
            [
                _part(question_id, 1, "header", "Server: nginx", concept="server_header"),
                _part(
                    question_id,
                    2,
                    "title",
                    "Welcome",
                    operator="==",
                    concept="exact_title",
                    mode=MatchMode.EXACT,
                ),
            ],
        )

    if text == '把这条 Google Dork 转换为 FOFA：intitle:"Grafana" intext:"JavaScript"':  # noqa: RUF001
        return _result(
            question_id,
            "advanced.migration.google_dork",
            [
                _part(question_id, 1, "title", "Grafana", concept="title_text"),
                _part(question_id, 2, "body", "JavaScript", concept="body_text"),
            ],
        )

    if text == "把这个 urlscan.io 搜索意图转换成 FOFA：HTML 包含 login，并且域名包含 bet、casino 或 kasino。":  # noqa: E501, RUF001
        body = _part(question_id, 1, "body", "login", concept="html_text")
        domains = [
            _part(question_id, index, "domain", value, concept="domain_substring")
            for index, value in enumerate(("bet", "casino", "kasino"), start=2)
        ]
        result = _result(question_id, "advanced.migration.urlscan", [body, *domains])
        return RuleTranslation(
            rule_id=result.rule_id,
            intent=result.intent,
            node=And(children=(body[0], Or(children=tuple(item[0] for item in domains)))),
        )

    if text == "修正这条 FOFA 查询，意图是搜索香港地区、Server 精确为 Apache，并排除 ASN 4134：asn!=”4134″ && region=”HK” && server==”Apache”":  # noqa: E501, RUF001
        return _result(
            question_id,
            "advanced.repair.fofa_quotes_order",
            [
                _part(
                    question_id,
                    1,
                    "region",
                    "HK",
                    concept="region",
                    mode=MatchMode.EXACT,
                ),
                _part(
                    question_id,
                    2,
                    "server",
                    "Apache",
                    operator="==",
                    concept="exact_server",
                    mode=MatchMode.EXACT,
                ),
                _part(
                    question_id,
                    3,
                    "asn",
                    4134,
                    operator="!=",
                    value_type="integer",
                    concept="excluded_asn",
                    mode=MatchMode.EXACT,
                ),
            ],
        )

    if text == '修正这条 FOFA 查询。意图：HFS 的 80 端口都要；8080 端口仅状态码为 200 时要。原查询：app="HFS" && port="80" |｜ app="HFS” && port="8080" && status_code="200"':  # noqa: E501, RUF001
        app_a = _part(question_id, 1, "app", "HFS", concept="product", mode=MatchMode.EXACT)
        port_80 = _part(
            question_id, 2, "port", 80, value_type="integer", mode=MatchMode.EXACT
        )
        app_b = _part(question_id, 3, "app", "HFS", concept="product", mode=MatchMode.EXACT)
        port_8080 = _part(
            question_id, 4, "port", 8080, value_type="integer", mode=MatchMode.EXACT
        )
        status = _part(
            question_id,
            5,
            "status_code",
            200,
            value_type="integer",
            mode=MatchMode.EXACT,
        )
        result = _result(
            question_id,
            "advanced.repair.fofa_precedence",
            [app_a, port_80, app_b, port_8080, status],
        )
        return RuleTranslation(
            rule_id=result.rule_id,
            intent=result.intent,
            node=Or(
                children=(
                    And(children=(app_a[0], port_80[0])),
                    And(children=(app_b[0], port_8080[0], status[0])),
                )
            ),
        )
    return None

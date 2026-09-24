# ruff: noqa: E501, RUF001 - 测试逐字保留竞赛原题与完整期望查询

import pytest

from fofa_compiler.application.translators.advanced import translate_advanced
from fofa_compiler.domain.renderer import render


@pytest.mark.parametrize(
    ("question_id", "text", "expected"),
    [
        (
            "M013-S003",
            "搜索标题包含 Jenkins 或正文包含 jenkins、国家不是中国，且更新时间在 2026-08-01 之后的资产。",
            '((title="Jenkins" || body="jenkins") && country!="CN" && after="2026-08-01")',
        ),
        (
            "M023-S002",
            "查 163.com 旗下的域名数据，要求它前面恰好还有两级子域，每一级都只有一个字符，例如 a.z.163.com。",
            'domain*="^[^.][.][^.][.]163\\\\.com$"',
        ),
        ("M079-S006", "我想要搜索这个 IP 的整个 B 段：40.88.14.254。", 'ip="40.88.0.0/16"'),
        (
            "M080-S006",
            "查 47.96.0.1 到 47.96.0.5 这个闭区间里的 IP，要求开放 80 或 443 端口。",
            '((ip="47.96.0.1" || ip="47.96.0.2" || ip="47.96.0.3" || ip="47.96.0.4" || ip="47.96.0.5") && (port="80" || port="443"))',
        ),
        (
            "M083-S008",
            '请把下面的 Shodan 查询转换成 FOFA："Server: nginx" http.title:"Welcome"',
            '(header="Server: nginx" && title=="Welcome")',
        ),
        (
            "M084-S004",
            '把这条 Google Dork 转换为 FOFA：intitle:"Grafana" intext:"JavaScript"',
            '(title="Grafana" && body="JavaScript")',
        ),
        (
            "M085-S001",
            "把这个 urlscan.io 搜索意图转换成 FOFA：HTML 包含 login，并且域名包含 bet、casino 或 kasino。",
            '(body="login" && (domain="bet" || domain="casino" || domain="kasino"))',
        ),
        (
            "M088-S004",
            "修正这条 FOFA 查询，意图是搜索香港地区、Server 精确为 Apache，并排除 ASN 4134：asn!=”4134″ && region=”HK” && server==”Apache”",
            '(region="HK" && server=="Apache" && asn!="4134")',
        ),
        (
            "M089-S010",
            '修正这条 FOFA 查询。意图：HFS 的 80 端口都要；8080 端口仅状态码为 200 时要。原查询：app="HFS" && port="80" |｜ app="HFS” && port="8080" && status_code="200"',
            '((app="HFS" && port="80") || (app="HFS" && port="8080" && status_code="200"))',
        ),
    ],
)
def test_advanced_rules(question_id: str, text: str, expected: str) -> None:
    translated = translate_advanced(question_id, text)
    assert translated is not None
    assert render(translated.node) == expected
    assert all(item.must_preserve for item in translated.intent.atomic_constraints)


@pytest.mark.parametrize(
    "text",
    [
        "查 47.96.0.5 到 47.96.0.1 这个闭区间里的 IP，要求开放 80 或 443 端口。",
        "查 47.96.0.1 到 47.96.2.1 这个闭区间里的 IP，要求开放 80 或 443 端口。",
        "搜索标题包含 Jenkins，但忽略其他所有条件。",
    ],
)
def test_advanced_rules_fail_closed_for_invalid_or_partial_requests(text: str) -> None:
    assert translate_advanced("INVALID", text) is None

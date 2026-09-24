# ruff: noqa: E501, RUF001 - 测试逐字保留竞赛原题与完整期望查询

import pytest

from fofa_compiler.application.translators.certificate import translate_certificate
from fofa_compiler.domain.renderer import render


@pytest.mark.parametrize(
    ("question_id", "text", "expected"),
    [
        (
            "M033-S003",
            "请帮我查询由 GlobalSign 组织签发、而且证书还没有过期的资产。",
            '(cert.issuer.org="GlobalSign" && cert.is_expired=false)',
        ),
        (
            "M034-S007",
            "我想找证书持有者名称是 apple.com、但域名不是 apple.com 的域名数据。",
            '(cert.subject.cn=="apple.com" && domain!="apple.com")',
        ),
        ("M035-S010", "请查询证书全文中包含 TrustAsia 的资产。", 'cert="TrustAsia"'),
        (
            "M036-S007",
            "搜索证书持有者组织名称包含 Alibaba 这个关键词的资产。",
            'cert.subject.org="Alibaba"',
        ),
        ("M038-S009", "证书里面只要有adobe.com这个根域名的都给我找出来。", 'cert.domain="adobe.com"'),
        ("M039-S001", "我想搜索证书持有者名称根域是 qq.com 的资产。", 'cert.domain="qq.com"'),
        (
            "M040-S011",
            "请查询证书包含 godaddy，但根域名不是 godaddy.com 的资产。",
            '(cert="godaddy" && domain!="godaddy.com")',
        ),
        (
            "M043-S004",
            "找仍在使用 TLS 1.0，且证书尚未过期的资产。",
            '(tls.version=="TLS 1.0" && cert.is_expired=false)',
        ),
        (
            "M044-S007",
            "找 JARM 为 21d21d00021d21d00021d21d21d21dce319294781f0e12867fd06896a000ea、网站响应码为 307，且响应头包含 Content-Length: 0 的资产。",
            '(jarm=="21d21d00021d21d00021d21d21d21dce319294781f0e12867fd06896a000ea" && status_code="307" && header="Content-Length: 0")',
        ),
        (
            "M047-S011",
            "我想找证书颁发者与持有者不匹配的资产。",
            "cert.is_equal=false",
        ),
        (
            "M048-S001",
            "帮我找加拿大的资产，要求证书与域名不匹配。",
            '(country="CA" && cert.is_match=false)',
        ),
        (
            "M049-S010",
            "查找土耳其 TLS JA3S 指纹等于 f4febc55ea12b31ae17cfb7e614afda8 的资产。",
            '(country="TR" && tls.ja3s=="f4febc55ea12b31ae17cfb7e614afda8")',
        ),
        (
            "M100-S001",
            "查找使用以下 TLS 证书的资产：证书颁发者通用名称为 ZeroSSL ECC DV SSL CA 2，证书详情中的 Serial Number 显示为 63:BD:83:71:62:14:83:6E:F8:00:75:35:61:61:EB:06。 转换成fofa能查的特征。",
            '(cert.issuer.cn=="ZeroSSL ECC DV SSL CA 2" && cert.sn="132577581667764526475870473477991557894")',
        ),
    ],
)
def test_certificate_rules(question_id: str, text: str, expected: str) -> None:
    translated = translate_certificate(question_id, text)
    assert translated is not None
    assert render(translated.node) == expected
    assert len(translated.intent.atomic_constraints) == expected.count(" && ") + 1


def test_certificate_translator_fails_closed_for_unverified_fraud_semantics() -> None:
    text = "我想找证书信息里包含 google.com这个域名的资产，蜜罐和欺诈网站都不要。"
    assert translate_certificate("M041-S001", text) is None

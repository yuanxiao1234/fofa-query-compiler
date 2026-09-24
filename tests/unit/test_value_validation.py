import ipaddress

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fofa_compiler.domain.ir import Predicate
from fofa_compiler.domain.value_validation import validate_predicate_value


def predicate(field: str, value, value_type: str) -> Predicate:  # type: ignore[no-untyped-def]
    return Predicate.model_validate(
        {
            "field": field,
            "operator": "=",
            "value": value,
            "value_type": value_type,
            "constraint_refs": ["c1"],
            "evidence_refs": ["e1"],
        }
    )


@given(st.ip_addresses(v=4))
def test_every_valid_ipv4_is_accepted(value: ipaddress.IPv4Address) -> None:
    assert validate_predicate_value(predicate("ip", str(value), "ipv4")) == ()


@given(st.ip_addresses(v=6))
def test_ipv6_is_rejected_when_declared_as_ipv4(value: ipaddress.IPv6Address) -> None:
    assert validate_predicate_value(predicate("ip", str(value), "ipv4"))[0].code == (
        "IP_VERSION_MISMATCH"
    )


@pytest.mark.parametrize("value", [1, 65535])
def test_valid_port_boundaries(value: int) -> None:
    assert validate_predicate_value(predicate("port", value, "integer")) == ()


@pytest.mark.parametrize("value", [0, 65536, 1000000])
def test_invalid_port_boundaries(value: int) -> None:
    assert validate_predicate_value(predicate("port", value, "integer"))[0].code == "INVALID_PORT"


@pytest.mark.parametrize("value", [0, 4294967295])
def test_valid_asn_boundaries(value: int) -> None:
    assert validate_predicate_value(predicate("asn", value, "integer")) == ()


@pytest.mark.parametrize("value", [-1, 4294967296])
def test_invalid_asn_boundaries(value: int) -> None:
    assert validate_predicate_value(predicate("asn", value, "integer"))[0].code == "INVALID_ASN"


@pytest.mark.parametrize(
    ("value", "value_type"),
    [
        ("124.255.254.0/24", "cidr"),
        ("47.96.0.1-47.96.0.5", "ip_range"),
        ("2026-08-01", "timestamp"),
        ("2026-08-01T10:00:00+08:00", "timestamp"),
        ("f4febc55ea12b31ae17cfb7e614afda8", "hash"),
        ("132577581667764526475870473477991557894", "certificate_serial"),
    ],
)
def test_valid_structured_values(value: str, value_type: str) -> None:
    assert validate_predicate_value(predicate("value", value, value_type)) == ()


@pytest.mark.parametrize(
    ("value", "value_type", "code"),
    [
        ("124.255.254.1/24", "cidr", "INVALID_CIDR"),
        ("47.96.0.5-47.96.0.1", "ip_range", "REVERSED_IP_RANGE"),
        ("1.1.1.1-::1", "ip_range", "MIXED_IP_RANGE_VERSION"),
        ("2026-02-30", "timestamp", "INVALID_TIMESTAMP"),
        ("2026-08-01T10:00:00", "timestamp", "NAIVE_TIMESTAMP"),
        ("not-a-hash", "hash", "INVALID_HASH"),
        ("0", "certificate_serial", "INVALID_CERTIFICATE_SERIAL"),
        ("[", "regex", "INVALID_REGEX"),
    ],
)
def test_invalid_structured_values(value: str, value_type: str, code: str) -> None:
    assert validate_predicate_value(predicate("value", value, value_type))[0].code == code

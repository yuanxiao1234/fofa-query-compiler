from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from datetime import datetime

from fofa_compiler.domain.ir import Predicate

HEX_HASH_LENGTHS = {32, 40, 56, 62, 64, 96, 128}


@dataclass(frozen=True, slots=True)
class ValueProblem:
    code: str
    message: str


def _problem(code: str, message: str) -> tuple[ValueProblem, ...]:
    return (ValueProblem(code=code, message=message),)


def validate_ip_range(value: str) -> tuple[ValueProblem, ...]:
    parts = re.split(r"\s*(?:-|到)\s*", value, maxsplit=1)
    if len(parts) != 2:
        return _problem("INVALID_IP_RANGE", "IP 闭区间必须包含起点和终点")
    try:
        start = ipaddress.ip_address(parts[0])
        end = ipaddress.ip_address(parts[1])
    except ValueError:
        return _problem("INVALID_IP_RANGE", "IP 闭区间包含无效地址")
    if start.version != end.version:
        return _problem("MIXED_IP_RANGE_VERSION", "IP 闭区间两端必须使用同一 IP 版本")
    if int(start) > int(end):
        return _problem("REVERSED_IP_RANGE", "IP 闭区间起点不得晚于终点")
    return ()


def validate_timestamp(value: str) -> tuple[ValueProblem, ...]:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return _problem("INVALID_TIMESTAMP", "时间必须是合法 ISO 8601 日期或时间")
    if "T" in value and parsed.tzinfo is None:
        return _problem("NAIVE_TIMESTAMP", "包含时间的边界必须带时区")
    return ()


def validate_hash(value: str) -> tuple[ValueProblem, ...]:
    if len(value) not in HEX_HASH_LENGTHS or re.fullmatch(r"[0-9a-fA-F]+", value) is None:
        return _problem("INVALID_HASH", "哈希必须是受支持长度的十六进制字符串")
    return ()


def validate_certificate_serial(value: str) -> tuple[ValueProblem, ...]:
    if re.fullmatch(r"[0-9]+", value) is None or int(value) <= 0:
        return _problem("INVALID_CERTIFICATE_SERIAL", "证书序列号必须是正十进制整数")
    return ()


def validate_predicate_value(predicate: Predicate) -> tuple[ValueProblem, ...]:
    value = predicate.value
    value_type = predicate.value_type
    if value_type in {"ipv4", "ipv6"}:
        try:
            address = ipaddress.ip_address(str(value))
        except ValueError:
            return _problem("INVALID_IP", "IP 地址格式无效")
        expected_version = 4 if value_type == "ipv4" else 6
        if address.version != expected_version:
            return _problem("IP_VERSION_MISMATCH", "IP 地址版本与声明类型不一致")
    elif value_type == "cidr":
        try:
            ipaddress.ip_network(str(value), strict=True)
        except ValueError:
            return _problem("INVALID_CIDR", "CIDR 无效或不是规范网络地址")
    elif value_type == "ip_range":
        return validate_ip_range(str(value))
    elif value_type == "timestamp":
        return validate_timestamp(str(value))
    elif value_type == "hash":
        return validate_hash(str(value))
    elif value_type == "certificate_serial":
        return validate_certificate_serial(str(value))
    elif value_type == "regex":
        try:
            re.compile(str(value))
        except re.error:
            return _problem("INVALID_REGEX", "正则表达式无法编译")
    elif value_type == "text" and not str(value):
        return _problem("EMPTY_TEXT", "文本值不能为空")

    if predicate.field == "port" and (not isinstance(value, int) or not 1 <= value <= 65535):
        return _problem("INVALID_PORT", "端口必须位于 1 到 65535")
    if predicate.field == "asn" and (
        not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 4294967295
    ):
        return _problem("INVALID_ASN", "ASN 必须位于 0 到 4294967295")
    if predicate.field == "status_code" and (
        not isinstance(value, int) or not 100 <= value <= 599
    ):
        return _problem("INVALID_STATUS_CODE", "HTTP 状态码必须位于 100 到 599")
    return ()


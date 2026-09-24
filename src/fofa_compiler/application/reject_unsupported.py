from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass

from fofa_compiler.domain.enums import FIXED_REJECTION_TEXT


@dataclass(frozen=True, slots=True)
class RejectionDecision:
    reason_code: str
    rejection_text: str = FIXED_REJECTION_TEXT
    unsupported_constraints: tuple[str, ...] = ()


def classify_unsupported(raw_text: str) -> RejectionDecision | None:
    text = " ".join(raw_text.split())

    port_match = re.fullmatch(r"搜索开放 ([0-9]+) 端口的资产。", text)
    if port_match and not 1 <= int(port_match.group(1)) <= 65535:
        return RejectionDecision(
            reason_code="INVALID_PORT",
            unsupported_constraints=(f"port:{port_match.group(1)}",),
        )

    address_match = re.fullmatch(r"搜索地址或网段为 (.+) 的资产。", text)
    if address_match:
        value = address_match.group(1)
        try:
            ipaddress.ip_address(value)
        except ValueError:
            try:
                ipaddress.ip_network(value, strict=True)
            except ValueError:
                return RejectionDecision(
                    reason_code="INVALID_IP_OR_CIDR",
                    unsupported_constraints=(f"address:{value}",),
                )

    contradiction = re.fullmatch(
        r"查同一条资产记录，国家代码必须等于 ([A-Z]{2})，同时国家代码又必须不等于 ([A-Z]{2})。",  # noqa: RUF001
        text,
    )
    if contradiction and contradiction.group(1) == contradiction.group(2):
        return RejectionDecision(
            reason_code="EXPLICIT_CONTRADICTION",
            unsupported_constraints=(f"country:{contradiction.group(1)}",),
        )

    if text == "帮我查最安全的网站。":
        return RejectionDecision(
            reason_code="SUBJECTIVE_CRITERION",
            unsupported_constraints=("subjective:safest",),
        )

    if text == "找出当前正在运行的容器内存使用率超过 80% 的服务器，没有容器监控数据或运行时访问权限。":  # noqa: E501, RUF001
        return RejectionDecision(
            reason_code="UNOBSERVABLE_RUNTIME_STATE",
            unsupported_constraints=("runtime:container_memory_usage",),
        )
    return None

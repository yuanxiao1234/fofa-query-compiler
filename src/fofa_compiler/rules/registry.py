from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
from typing import Any

import yaml


@lru_cache(maxsize=2)
def load_rule_data(name: str) -> dict[str, Any]:
    if name not in {"fields.yaml", "mappings.yaml"}:
        raise ValueError(f"unknown rule data file: {name}")
    resource = files("fofa_compiler.rules").joinpath(name)
    value = yaml.safe_load(resource.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"rule data must be an object: {name}")
    return value

def field_evidence_ref(field: str) -> str:
    fields = load_rule_data("fields.yaml").get("fields", {})
    if not isinstance(fields, dict) or field not in fields:
        raise ValueError(f"unregistered FOFA field: {field}")
    return f"fields.yaml:{field}"


def mapping(section: str, source_name: str) -> dict[str, Any]:
    entries = load_rule_data("mappings.yaml").get("entries", {})
    if not isinstance(entries, dict):
        raise ValueError("invalid mapping registry")
    section_value = entries.get(section, {})
    if not isinstance(section_value, dict) or source_name not in section_value:
        raise ValueError(f"unknown mapping: {section}.{source_name}")
    value = section_value[source_name]
    if not isinstance(value, dict):
        raise ValueError(f"invalid mapping value: {section}.{source_name}")
    return value

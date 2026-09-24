from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from fofa_compiler.domain.models import DomainModel

type ScalarValue = str | int | bool


class Predicate(DomainModel):
    kind: Literal["predicate"] = "predicate"
    field: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_.]*$")
    operator: Literal["=", "==", "!=", "!==", "*=", "!*=", ">", ">=", "<", "<="]
    value: ScalarValue
    value_type: Literal[
        "text",
        "integer",
        "boolean",
        "timestamp",
        "ipv4",
        "ipv6",
        "cidr",
        "ip_range",
        "hash",
        "certificate_serial",
        "regex",
    ]
    constraint_refs: tuple[str, ...] = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def value_matches_type(self) -> Predicate:
        if self.value_type == "integer" and (
            not isinstance(self.value, int) or isinstance(self.value, bool)
        ):
            raise ValueError("integer predicates require an integer value")
        if self.value_type == "boolean" and not isinstance(self.value, bool):
            raise ValueError("boolean predicates require a boolean value")
        if self.value_type not in {"integer", "boolean"} and not isinstance(self.value, str):
            raise ValueError(f"{self.value_type} predicates require a string value")
        return self


class And(DomainModel):
    kind: Literal["and"] = "and"
    children: tuple[QueryNode, ...] = Field(min_length=2)


class Or(DomainModel):
    kind: Literal["or"] = "or"
    children: tuple[QueryNode, ...] = Field(min_length=2)


class Not(DomainModel):
    kind: Literal["not"] = "not"
    child: QueryNode


class Group(DomainModel):
    kind: Literal["group"] = "group"
    child: QueryNode


type QueryNode = Annotated[
    Predicate | And | Or | Not | Group,
    Field(discriminator="kind"),
]


And.model_rebuild()
Or.model_rebuild()
Not.model_rebuild()
Group.model_rebuild()

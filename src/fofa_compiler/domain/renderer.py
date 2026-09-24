from __future__ import annotations

from fofa_compiler.domain.ir import And, Group, Not, Or, Predicate, QueryNode


def escape_literal(value: str) -> str:
    """Escape a FOFA double-quoted literal without changing its text semantics."""
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def _render_value(predicate: Predicate) -> str:
    if predicate.value_type == "boolean":
        return "true" if predicate.value else "false"
    return f'"{escape_literal(str(predicate.value))}"'


def render(node: QueryNode) -> str:
    if isinstance(node, Predicate):
        return f"{node.field}{node.operator}{_render_value(node)}"
    if isinstance(node, And):
        return "(" + " && ".join(render(child) for child in node.children) + ")"
    if isinstance(node, Or):
        return "(" + " || ".join(render(child) for child in node.children) + ")"
    if isinstance(node, Not):
        return f"!({render(node.child)})"
    if isinstance(node, Group):
        return f"({render(node.child)})"
    raise TypeError(f"unsupported query node: {type(node).__name__}")


def _sort_key(node: QueryNode) -> tuple[str, str]:
    return node.kind, render(node)


def normalize(node: QueryNode) -> QueryNode:
    """Canonicalize commutative children while retaining all explicit grouping."""
    if isinstance(node, Predicate):
        return node
    if isinstance(node, Not):
        return Not(child=normalize(node.child))
    if isinstance(node, Group):
        return Group(child=normalize(node.child))
    children = tuple(sorted((normalize(child) for child in node.children), key=_sort_key))
    if isinstance(node, And):
        return And(children=children)
    return Or(children=children)

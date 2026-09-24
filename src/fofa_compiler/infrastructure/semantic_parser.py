from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from pydantic import TypeAdapter

from fofa_compiler.application.translators.advanced import translate_advanced
from fofa_compiler.application.translators.certificate import translate_certificate
from fofa_compiler.application.translators.core import RuleTranslation, translate_core
from fofa_compiler.application.translators.web import translate_web
from fofa_compiler.domain.errors import ErrorLocation, ValidationError
from fofa_compiler.domain.ir import QueryNode
from fofa_compiler.domain.models import NormalizedIntent

Translator = Callable[[str, str], RuleTranslation | None]


class SemanticProvider(Protocol):
    def propose(self, *, question_id: str, raw_text: str) -> dict[str, Any]: ...


def _contains_forbidden_output(value: Any) -> bool:
    if isinstance(value, dict):
        forbidden = {"query", "query_text", "rendered_query", "fofa_query", "answer"}
        return bool(forbidden.intersection(value)) or any(
            _contains_forbidden_output(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_output(item) for item in value)
    return False


class SemanticParser:
    def __init__(
        self,
        *,
        provider: SemanticProvider | None = None,
        translators: tuple[Translator, ...] | None = None,
    ) -> None:
        self.provider = provider
        self.translators = translators or (
            translate_core,
            translate_web,
            translate_certificate,
            translate_advanced,
        )
        self._node_adapter: TypeAdapter[QueryNode] = TypeAdapter(QueryNode)

    def parse(self, question_id: str, raw_text: str) -> RuleTranslation | None:
        for translator in self.translators:
            translated = translator(question_id, raw_text)
            if translated is not None:
                return translated
        if self.provider is None:
            return None

        proposal = self.provider.propose(question_id=question_id, raw_text=raw_text)
        if _contains_forbidden_output(proposal):
            raise ValidationError(
                "语义提供方只能返回结构化意图和 IR，不能返回最终查询",  # noqa: RUF001
                location=ErrorLocation(question_id=question_id),
            )
        try:
            intent = NormalizedIntent.model_validate(proposal["intent"])
            node = self._node_adapter.validate_python(proposal["node"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValidationError(
                "语义提供方返回了无效的结构化结果",
                location=ErrorLocation(question_id=question_id),
            ) from exc
        if intent.question_id != question_id:
            raise ValidationError(
                "语义提供方返回的题号与请求不一致",
                location=ErrorLocation(question_id=question_id),
            )
        return RuleTranslation(rule_id="provider.structured_ir", intent=intent, node=node)

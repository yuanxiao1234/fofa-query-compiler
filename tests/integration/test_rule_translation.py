import json
from pathlib import Path

import pytest

from fofa_compiler.application.translators.core import translate_core
from fofa_compiler.application.translators.web import translate_web
from fofa_compiler.domain.renderer import render

FIXTURE = Path(__file__).parents[1] / "fixtures" / "intent_cases.json"


def cases() -> list[dict[str, object]]:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(value, list)
    return value


@pytest.mark.parametrize("case", cases(), ids=lambda case: str(case["question_id"]))
def test_core_rule_translation_preserves_all_reviewed_constraints(
    case: dict[str, object],
) -> None:
    translator = translate_web if str(case["family"]).startswith("web.") else translate_core
    translated = translator(str(case["question_id"]), str(case["text"]))
    assert translated is not None
    assert translated.rule_id == case["family"]
    assert render(translated.node) == case["expected_query"]

    expected = case["atomic_constraints"]
    assert isinstance(expected, list)
    assert len(translated.intent.atomic_constraints) == len(expected)
    actual_values = [constraint.typed_value for constraint in translated.intent.atomic_constraints]
    assert actual_values == [constraint["value"] for constraint in expected]


def test_core_translator_fails_closed_for_partially_recognized_complex_request() -> None:
    text = "搜索标题包含 Jenkins、国家不是中国，且更新时间在 2026-08-01 之后的资产。"  # noqa: RUF001
    assert translate_core("M013-S003", text) is None


def test_core_translator_fails_closed_for_unknown_country() -> None:
    assert translate_core("Q-UNKNOWN", "搜索位于不存在国的资产。") is None


def test_web_translator_fails_closed_for_multi_constraint_request() -> None:
    text = "搜索正文包含 Jenkins，但标题不包含同一个关键词的资产。"  # noqa: RUF001
    assert translate_web("M068-S005", text) is None

from datetime import UTC, datetime
from pathlib import Path

from fofa_compiler.application.import_package import ImportRequest, import_package
from fofa_compiler.domain.models import CompetitionPackage
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository

ROOT = Path(__file__).parents[2]


def test_imports_real_100_question_package_without_modifying_sources(tmp_path: Path) -> None:
    request = ImportRequest(
        questions_path=ROOT / "题目" / "题目.md",
        package_path=ROOT / "题目" / "参赛包.md",
        template_path=ROOT / "题目" / "答案模板.md",
    )
    source_paths = (request.questions_path, request.package_path, request.template_path)
    before = {path: path.read_bytes() for path in source_paths}
    repository = JsonWorkspaceRepository(tmp_path / "run")

    package = import_package(
        request, repository=repository, now=datetime(2026, 9, 24, tzinfo=UTC)
    )

    assert package.package_id == "pkg-08e82c8d"
    assert len(package.questions) == 100
    assert package.original_order[0] == "M001-S009"
    assert package.original_order[-1] == "M100-S001"
    assert repository.load_model("package.json", CompetitionPackage) == package
    assert {path: path.read_bytes() for path in source_paths} == before


def test_import_accepts_bom_crlf_and_surrounding_whitespace(tmp_path: Path) -> None:
    questions = tmp_path / "questions.json"
    package_file = tmp_path / "package.txt"
    template = tmp_path / "template.json"
    questions.write_bytes('\ufeff[{"题号":" Q1 ","自然语言输入":" 查询资产。 "}]\r\n'.encode())
    package_file.write_text(" pkg-demo \r\n2026-09-24T08:00:00+08:00\r\n", encoding="utf-8")
    template.write_text(
        '{"选手名称":"","参赛包编号":" pkg-demo ","答案":[{"题号":" Q1 ","查询语句":""}]}',
        encoding="utf-8",
    )

    imported = import_package(
        ImportRequest(questions, package_file, template),
        repository=JsonWorkspaceRepository(tmp_path / "workspace"),
        now=datetime(2026, 9, 24, tzinfo=UTC),
    )
    assert imported.original_order == ("Q1",)
    assert imported.questions[0].raw_text == "查询资产。"

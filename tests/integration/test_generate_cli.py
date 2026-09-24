import json
from pathlib import Path

from fofa_compiler.cli import main


def prepare_files(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    questions = tmp_path / "questions.json"
    package = tmp_path / "package.txt"
    template = tmp_path / "template.json"
    workspace = tmp_path / "workspace"
    questions.write_text(
        '[{"题号":"Q1","自然语言输入":"请查询开放 3000 端口的资产。"}]',
        encoding="utf-8",
    )
    package.write_text("pkg-cli\n2026-09-24T08:00:00+08:00\n", encoding="utf-8")
    template.write_text(
        '{"选手名称":"","参赛包编号":"pkg-cli","答案":[{"题号":"Q1","查询语句":""}]}',
        encoding="utf-8",
    )
    return questions, package, template, workspace


def test_generate_all_and_one_share_application_service(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    questions, package, template, workspace = prepare_files(tmp_path)
    assert (
        main(
            [
                "package",
                "import",
                "--questions",
                str(questions),
                "--package",
                str(package),
                "--template",
                str(template),
                "--workspace",
                str(workspace),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(["generate", "all", "--workspace", str(workspace)]) == 0
    all_result = json.loads(capsys.readouterr().out)
    assert all_result["generated"] == 1
    assert all_result["items"][0]["query"] == 'port="3000"'

    assert (
        main(
            [
                "generate",
                "one",
                "--workspace",
                str(workspace),
                "--question-id",
                "Q1",
            ]
        )
        == 0
    )
    one_result = json.loads(capsys.readouterr().out)
    assert one_result["items"][0]["candidate_id"] == all_result["items"][0]["candidate_id"]


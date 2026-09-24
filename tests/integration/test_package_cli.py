import json
from pathlib import Path

from fofa_compiler.cli import main

ROOT = Path(__file__).parents[2]


def test_package_import_and_status_commands(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    workspace = tmp_path / "workspace"
    result = main(
        [
            "package",
            "import",
            "--questions",
            str(ROOT / "题目" / "题目.md"),
            "--package",
            str(ROOT / "题目" / "参赛包.md"),
            "--template",
            str(ROOT / "题目" / "答案模板.md"),
            "--workspace",
            str(workspace),
        ]
    )
    imported = json.loads(capsys.readouterr().out)
    assert result == 0
    assert imported["valid"] is True
    assert imported["question_count"] == 100

    result = main(["package", "status", "--workspace", str(workspace)])
    status = json.loads(capsys.readouterr().out)
    assert result == 0
    assert status["package_id"] == "pkg-08e82c8d"
    assert status["question_count"] == 100

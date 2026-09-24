import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from fofa_compiler import __version__
from fofa_compiler.application.container import build_container
from fofa_compiler.application.generate_answers import generate_answers
from fofa_compiler.application.import_package import ImportRequest, import_package
from fofa_compiler.domain.errors import FofaCompilerError
from fofa_compiler.infrastructure.semantic_parser import SemanticParser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fofa-compiler")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subcommands = parser.add_subparsers(dest="command")
    package_parser = subcommands.add_parser("package", help="导入或查看参赛包")
    package_commands = package_parser.add_subparsers(dest="package_command")
    import_parser = package_commands.add_parser("import", help="导入并校验参赛包")
    import_parser.add_argument("--questions", required=True, type=Path)
    import_parser.add_argument("--package", required=True, type=Path)
    import_parser.add_argument("--template", required=True, type=Path)
    import_parser.add_argument("--workspace", required=True, type=Path)
    status_parser = package_commands.add_parser("status", help="显示已导入参赛包状态")
    status_parser.add_argument("--workspace", required=True, type=Path)
    generate_parser = subcommands.add_parser("generate", help="生成候选答案")
    generate_commands = generate_parser.add_subparsers(dest="generate_command")
    generate_all = generate_commands.add_parser("all", help="生成全部题目")
    generate_all.add_argument("--workspace", required=True, type=Path)
    generate_one = generate_commands.add_parser("one", help="生成单道题目")
    generate_one.add_argument("--workspace", required=True, type=Path)
    generate_one.add_argument("--question-id", required=True)
    subcommands.add_parser("review", help="逐题复核")
    subcommands.add_parser("evidence", help="管理证据")
    subcommands.add_parser("export", help="导出合规答卷")
    subcommands.add_parser("web", help="启动本地 Web 界面")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "package" and args.package_command is None:
        parser.parse_args(["package", "--help"])
    if args.command == "generate" and args.generate_command is None:
        parser.parse_args(["generate", "--help"])
    try:
        if args.command == "package" and args.package_command == "import":
            container = build_container(args.workspace)
            package = import_package(
                ImportRequest(args.questions, args.package, args.template),
                repository=container.workspace,
                now=container.clock.now(),
            )
            print(
                json.dumps(
                    {
                        "package_id": package.package_id,
                        "question_count": len(package.questions),
                        "run_id": package.run_id,
                        "valid": package.import_report.is_valid,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        elif args.command == "package" and args.package_command == "status":
            container = build_container(args.workspace)
            print(
                json.dumps(
                    container.workspace.load_json("state.json"),
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        elif args.command == "generate":
            container = build_container(args.workspace)
            summary = generate_answers(
                repository=container.workspace,
                audit_log=container.audit_log,
                parser=SemanticParser(),
                now=container.clock.now(),
                question_id=args.question_id if args.generate_command == "one" else None,
            )
            print(json.dumps(asdict(summary), ensure_ascii=False, sort_keys=True))
            return 5 if summary.failed else 0
    except FofaCompilerError as exc:
        print(
            json.dumps(
                {
                    "error": exc.code,
                    "message": exc.message,
                    "location": {
                        "file": exc.location.file,
                        "json_path": exc.location.json_path,
                        "question_id": exc.location.question_id,
                    },
                    "details": exc.details,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 3
    return 0

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from fofa_compiler import __version__
from fofa_compiler.application.container import build_container
from fofa_compiler.application.evidence import EvidenceInput, add_evidence
from fofa_compiler.application.export_answers import export_answers
from fofa_compiler.application.generate_answers import generate_answers
from fofa_compiler.application.import_package import ImportRequest, import_package
from fofa_compiler.application.review_answer import amend_answer, confirm_answer
from fofa_compiler.domain.enums import EvidenceAccessStatus, EvidenceSourceKind
from fofa_compiler.domain.errors import AtomicWriteError, ExportBlockedError, FofaCompilerError
from fofa_compiler.domain.models import CandidateAnswer, CompetitionPackage, RiskAssessment
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
    review_parser = subcommands.add_parser("review", help="逐题复核")
    review_commands = review_parser.add_subparsers(dest="review_command")
    for name in ("show", "amend", "confirm"):
        command = review_commands.add_parser(name)
        command.add_argument("--workspace", required=True, type=Path)
        command.add_argument("--question-id", required=True)
        if name in {"amend", "confirm"}:
            command.add_argument("--reviewer", required=True)
        if name == "amend":
            command.add_argument("--query", required=True)
        if name == "confirm":
            command.add_argument("--risk-item", action="append", default=[])
            command.add_argument("--evidence-id", action="append", default=[])
    evidence_parser = subcommands.add_parser("evidence", help="管理证据")
    evidence_commands = evidence_parser.add_subparsers(dest="evidence_command")
    evidence_add = evidence_commands.add_parser("add")
    evidence_add.add_argument("--workspace", required=True, type=Path)
    evidence_add.add_argument("--question-id", required=True)
    evidence_add.add_argument("--source", required=True)
    evidence_add.add_argument(
        "--kind", required=True, choices=[item.value for item in EvidenceSourceKind]
    )
    evidence_add.add_argument("--fact", action="append", default=[])
    evidence_add.add_argument("--content-file", type=Path)
    evidence_add.add_argument("--verified-by")
    evidence_add.add_argument("--original-source")
    evidence_add.add_argument("--equivalent", action="store_true")
    evidence_add.add_argument("--unavailable", action="store_true")
    export_parser = subcommands.add_parser("export", help="导出合规答卷")
    export_parser.add_argument("--workspace", required=True, type=Path)
    export_parser.add_argument("--participant", required=True)
    export_parser.add_argument("--output", required=True, type=Path)
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
    if args.command == "review" and args.review_command is None:
        parser.parse_args(["review", "--help"])
    if args.command == "evidence" and args.evidence_command is None:
        parser.parse_args(["evidence", "--help"])
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
        elif args.command == "export":
            container = build_container(args.workspace)
            export_summary = export_answers(
                container.workspace,
                participant_name=args.participant,
                output_path=args.output,
            )
            print(json.dumps(asdict(export_summary), ensure_ascii=False, sort_keys=True))
        elif args.command == "review":
            container = build_container(args.workspace)
            if args.review_command == "show":
                package = container.workspace.load_model("package.json", CompetitionPackage)
                question = next(
                    (item for item in package.questions if item.question_id == args.question_id),
                    None,
                )
                candidate = container.workspace.load_model(
                    f"items/{args.question_id}/current.json", CandidateAnswer
                )
                risk = container.workspace.load_model(
                    f"items/{args.question_id}/risks.json", RiskAssessment
                )
                print(
                    json.dumps(
                        {
                            "question": question.model_dump(mode="json") if question else None,
                            "candidate": candidate.model_dump(mode="json"),
                            "risk": risk.model_dump(mode="json"),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
            elif args.review_command == "amend":
                candidate = amend_answer(
                    container.workspace,
                    args.question_id,
                    args.query,
                    reviewer=args.reviewer,
                    now=container.clock.now(),
                )
                print(candidate.model_dump_json())
            else:
                final = confirm_answer(
                    container.workspace,
                    args.question_id,
                    reviewer=args.reviewer,
                    checked_risk_item_ids=tuple(args.risk_item),
                    reviewed_evidence_ids=tuple(args.evidence_id),
                    now=container.clock.now(),
                )
                print(final.model_dump_json())
        elif args.command == "evidence" and args.evidence_command == "add":
            container = build_container(args.workspace)
            content = args.content_file.read_bytes() if args.content_file else None
            record = add_evidence(
                container.workspace,
                EvidenceInput(
                    question_id=args.question_id,
                    source_kind=EvidenceSourceKind(args.kind),
                    source_locator=args.source,
                    facts=tuple(args.fact),
                    content=content,
                    verified_by=args.verified_by,
                    access_status=(
                        EvidenceAccessStatus.UNAVAILABLE
                        if args.unavailable
                        else EvidenceAccessStatus.ACCESSIBLE
                    ),
                    original_source_locator=args.original_source,
                    equivalence_assessment={"equivalent": True} if args.equivalent else None,
                ),
                now=container.clock.now(),
            )
            print(record.model_dump_json())
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
        if isinstance(exc, ExportBlockedError):
            return 9
        if isinstance(exc, AtomicWriteError):
            return 10
        return 3
    return 0

import argparse
from collections.abc import Sequence

from fofa_compiler import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fofa-compiler")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser("package", help="导入或查看参赛包")
    subcommands.add_parser("generate", help="生成候选答案")
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

"""Command line interface: ``python -m md_knowledge_graph ROOT [options]``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .errors import KnowledgeGraphError, clip
from .graph import Graph, build_graph, dump_json, render_index
from .loader import load_notes

_EXIT_OK = 0
_EXIT_FINDINGS = 1
_EXIT_ERROR = 2
_FAILURE_CODES: dict[str, int] = {
    "frontmatter": _EXIT_ERROR,
    "root_missing": _EXIT_ERROR,
    "too_large": _EXIT_FINDINGS,
    "too_many_notes": _EXIT_FINDINGS,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="md-knowledge-graph",
        description="Build an INDEX.md and a JSON graph from Markdown notes.",
    )
    parser.add_argument("root", type=Path, help="directory holding the Markdown notes")
    parser.add_argument(
        "--index",
        type=Path,
        metavar="PATH",
        help="index file to write or, with --check, to verify (default: ROOT/INDEX.md)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        metavar="PATH",
        help="graph file to write or, with --check, to verify (default: ROOT/graph.json)",
    )
    parser.add_argument(
        "--group-by",
        choices=["folder", "tag"],
        default="folder",
        help="how the index groups notes",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail on invalid frontmatter, oversized files and broken links",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="write nothing; exit 1 if an output file differs from what would be generated",
    )
    return parser


def _same(path: Path, data: bytes) -> bool:
    try:
        return path.read_bytes() == data
    except FileNotFoundError:
        return False


def _summary(graph: Graph) -> str:
    nodes, edges = len(graph.nodes), len(graph.edges)
    broken, orphans = len(graph.broken), len(graph.orphans)
    return f"{nodes} notes, {edges} links, {broken} broken, {orphans} orphans"


def _run(args: argparse.Namespace) -> int:
    result = load_notes(args.root, strict=args.strict)
    graph = build_graph(result.notes)
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    for item in graph.broken:
        where = f"{item.source}:{item.line}"
        print(f"{where}: {item.reason} link [[{clip(item.target)}]]", file=sys.stderr)
    index_path: Path | None = args.index
    json_path: Path | None = args.json
    if index_path is None and json_path is None:
        index_path = args.root / "INDEX.md"
        json_path = args.root / "graph.json"
    outputs: list[tuple[Path, str]] = []
    if index_path is not None:
        outputs.append((index_path, render_index(graph, group_by=args.group_by)))
    if json_path is not None:
        outputs.append((json_path, dump_json(graph)))
    status = _EXIT_OK
    for path, text in outputs:
        data = text.encode("utf-8")
        if not args.check:
            path.write_bytes(data)
        elif not _same(path, data):
            print(f"out of date: {path}", file=sys.stderr)
            status = _EXIT_FINDINGS
    if args.strict and graph.broken:
        status = _EXIT_FINDINGS
    print(_summary(graph))
    return status


def main(argv: list[str] | None = None) -> int:
    """Run the command line interface and return the process exit code.

    Exit codes: 0 success; 1 findings (broken links under ``--strict``, outdated files
    under ``--check``) or a size-limit failure; 2 usage, IO or parse error.
    """
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else _EXIT_ERROR
    try:
        return _run(args)
    except KnowledgeGraphError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return _FAILURE_CODES[exc.code]
    except OSError as exc:
        print(f"error: {exc.strerror or type(exc).__name__}", file=sys.stderr)
        return _EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

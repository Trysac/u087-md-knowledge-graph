# Architecture

## Purpose

`trysac-md-knowledge-graph` is a small Python library and command line tool. It indexes a directory of Markdown notes with YAML frontmatter and wiki links, builds a link graph, reports broken links and orphans, and renders an INDEX.md and a JSON graph.

## Shape

```text
CLI (__main__.py) ----+
                      +--> loader.py --> parser.py --> models.py
caller code ----------+         |
 (public API, __init__.py)       +--> graph.py (build_graph, render_index, Graph.to_json)
                                        |
                                 errors.py (KnowledgeGraphError, clip)
```

- **Modules**: `models.py` (frozen `Link` and `Note`), `parser.py` (`parse_note`), `loader.py` (`load_notes`, `LoadResult`), `graph.py` (`build_graph`, `render_index`, `Graph`, `Edge`, `BrokenLink`, `dump_json`), `errors.py`, `__main__.py` (CLI).
- **Public API**: the names listed in `__all__` of `src/md_knowledge_graph/__init__.py`. Other names are internal.
- **I/O**: confined to `loader.py` (reading files under the root) and `__main__.py` (writing or checking outputs). Parsing and graph building are pure.
- **Errors**: domain failures raise `KnowledgeGraphError` with a stable `code`. The CLI maps codes to exit statuses and prints messages to stderr.
- **Logging**: the package logs under `md_knowledge_graph` with a `NullHandler` only.

## Data flow

1. `load_notes` walks the root, applies excludes, and calls `parse_note` for each `.md` file.
2. `build_graph` assigns ids (lowercase stem, or `folder/stem` for duplicate stems), resolves links, and computes edges, broken links, orphans and backlinks.
3. `render_index` and `Graph.to_json` produce the output text; the CLI writes or compares it.

## Decisions

Architecture decisions are recorded in ADRs when they are made. No ADR files are part of this snapshot.
